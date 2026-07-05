"""HTTP request dispatch for the nested-worlds server."""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import mimetypes
import struct
import uuid
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs, urlparse

import causality
import persistence
from causality import CausalityBus, EventKind
from causality.staging import stage_cascade
from causality.wiring import wire_world_handlers
from agents.agent import Agent
from agents.personas import by_name as persona_by_name, for_name as persona_for_name
from multiverse.generator import generate_node_hierarchy, resolve_node_by_name
from multiverse.node import SpatialNode
from multiverse.utils import (
    apply_property_overrides, apply_ripple_scores, build_distance_map,
    count_nodes, find_node,
)
from multiverse.verbs import apply_verb, verb_for_level
from puzzles.engine import PuzzleEngine
from server import guard, imageprompt, observability
from server.protocol import ProtocolError, _send_frame, ws_recv
from server.rooms import (
    Player, agent_enter, agent_leave, agent_move, agent_persona,
    broadcast, get_room, record_attempt, snapshot,
)


_STATIC_DIR   = Path(__file__).parent.parent / "static"
_FRONTEND_DIR = _STATIC_DIR / "app"
_log = logging.getLogger("nested_worlds")
_WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
_MAX_BODY = 64 * 1024  # 64 KB


# ── World rebuild ──────────────────────────────────────────────────────────

def _flatten_qs(qs: Mapping[str, list[str]]) -> dict[str, str]:
    return {k: v[0] for k, v in qs.items() if v}


def _build_world(params: Mapping[str, Any]) -> tuple[SpatialNode, int, int, int, int]:
    """Generate a world tree from params dict (scalar values).

    Caller is responsible for catching ValueError on bad ints / generator
    arguments. `guard.validate_world_params` clamps depth/breadth so a
    request can't ask for a runaway tree.
    """
    guard.validate_world_params(params)
    seed  = int(params.get("seed",        42))
    depth = int(params.get("depth",        6))
    min_b = int(params.get("min_breadth",  1))
    max_b = int(params.get("max_breadth",  3))
    root = generate_node_hierarchy(seed=seed, max_depth=depth,
                                   min_breadth=min_b, max_breadth=max_b)
    # Hydrate the world's durable evolution onto the deterministic tree:
    # persisted causal pressure, then the property overlay written by
    # causal-event effects (multiverse/effects.py) — so the world every
    # participant sees carries what has happened in it.
    apply_ripple_scores(root, persistence.load_ripple_scores(seed))
    apply_property_overrides(root, persistence.load_node_property_overrides(seed))
    return root, seed, depth, min_b, max_b


def _resolve_node(seed: int, node_name: str) -> SpatialNode | None:
    """Resolve a client-named node against the canonical world.

    Node identity is server-derived: the client supplies only (seed, name),
    never level or properties — a request can no longer forge a node's
    nature or write history for places that don't exist. Names encode their
    path, so resolution is O(depth) (`resolve_node_by_name`), and the node
    is hydrated with its persisted evolution: ripple pressure and the
    property overlay written by causal-event effects.
    """
    if not node_name:
        return None
    node = resolve_node_by_name(seed, node_name)
    if node is None:
        return None
    node.ripple_score = persistence.get_ripple_score(seed, node.name)
    overlay = persistence.load_node_property_overrides(seed).get(node.name)
    if overlay:
        node.properties.update(overlay)
    return node


def _node_to_dict(node: SpatialNode, activity: dict | None = None) -> dict:
    verb = verb_for_level(node.level)
    return {
        "id": node.id,
        "name": node.name,
        "level": node.level,
        "properties": node.properties,
        # Cumulative causal pressure — surfaced so clients can show how much
        # has happened here, not just what the node was generated as.
        "ripple_score": round(node.ripple_score, 3),
        # How many recorded interactions this node has accumulated — the
        # generative art etches them as trace marks.
        "activity": (activity or {}).get(node.name, 0),
        # The scale-native verb: the one act this level supports.
        "verb": ({"name": verb.name, "tagline": verb.tagline}
                 if verb else None),
        "children": [_node_to_dict(c, activity) for c in node.children],
    }


# ── Handler ────────────────────────────────────────────────────────────────

_RATE_LIMITED_PATHS = frozenset({
    "/speak", "/agent/voice", "/image", "/puzzle/attempt", "/act",
})


class Handler(BaseHTTPRequestHandler):
    # HTTP/1.1 on the status line: spec-strict WebSocket clients (e.g. the
    # Python `websockets` library) reject an upgrade whose 101 arrives as
    # HTTP/1.0. Ordinary responses still close per request — `Connection:
    # close` is sent with the security headers below — so the thread-per-
    # connection model keeps its one-request-per-thread behaviour.
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        # The access-log line is emitted from `_emit_access_log` instead so it
        # carries the structured fields ops actually look at (latency, IP hash,
        # response size). Suppressing the default keeps double-logging out.
        pass

    # ── access logging ──
    #
    # We capture three pieces of state per request — the start time, the
    # most recent send_response status code, and the body length — then
    # emit a single structured line in the do_*() finally block. send_response
    # is overridden because nearly every code path in this handler ultimately
    # calls it, including SSE and the WebSocket upgrade.

    def send_response(self, code, message=None):  # type: ignore[override]
        self._status = code
        super().send_response(code, message)

    def _emit_access_log(self) -> None:
        if not getattr(self, "_started", None):
            return
        path   = urlparse(self.path).path or "/"
        ip     = guard.client_ip(self.client_address, self.headers)
        observability.access_log(
            self.command or "?", path,
            getattr(self, "_status", 0),
            started=self._started,
            ip=ip,
            length=getattr(self, "_resp_len", 0),
        )

    # ── guards ──

    def _authorized(self, qs: Mapping[str, list[str]]) -> bool:
        """Reject the request with 403 if the beta key is required and missing.

        The invite key is an *API credential*, not a page-visibility secret:
        the static UI shell and its JS/CSS assets are served ungated so the
        browser can load the single-page app, which then reads `?key=` from
        its own URL and forwards it on every data / WebSocket / paid call.
        Gating the shell itself is self-defeating — the bundle's own
        `<script>` request carries no key, so the page would render blank and
        never get far enough to send the key anywhere. Health check is exempt
        so platform load balancers can probe without the key. Every
        data-bearing or paid endpoint (`/world`, `/ws`, `/agent`, `/observe`,
        `/puzzle*`, `/speak`, `/image`, `/agent/voice`, `/players`,
        `/history`, `/worlds`) stays gated.
        """
        if self._is_public_asset(urlparse(self.path).path):
            return True
        if guard.check_invite_key(self.headers, qs):
            return True
        self._send_error("forbidden", 403)
        return False

    @staticmethod
    def _is_public_asset(path: str) -> bool:
        """True for the ungated static UI shell + assets (never data endpoints).

        Data / paid endpoints do not live under these prefixes, so exempting
        the shell can't accidentally open one up.
        """
        stripped = path.rstrip("/")
        if stripped in ("", "/health", "/explorer.js", "/d3.v7.min.js",
                        "/nodeart.js", "/nodeart-global.js", "/favicon.ico"):
            return True
        if stripped == "/app" or path.startswith("/app/"):
            return True
        if path.startswith("/easter-egg"):
            return True
        return False

    def _rate_ok(self, path: str) -> bool:
        """Apply per-IP rate limit on the expensive endpoints; 429 on deny."""
        if path not in _RATE_LIMITED_PATHS:
            return True
        ip = guard.client_ip(self.client_address, self.headers)
        if guard.RATE_LIMITER.allow(ip):
            return True
        self._send_error("rate limited — slow down", 429)
        return False

    # ── response helpers ──

    def _send_security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        # One request per connection (see protocol_version note above). The
        # WebSocket upgrade path never calls this helper, so 101 responses
        # keep their Connection: Upgrade header.
        self.send_header("Connection", "close")
        self.close_connection = True

    def _send_json(self, data: object, status: int = 200) -> None:
        body = json.dumps(data, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._send_security_headers()
        self.end_headers()
        self.wfile.write(body)
        self._resp_len = len(body)

    def _send_error(self, message: str, status: int = 400) -> None:
        self._send_json({"error": message}, status)

    def _send_file(self, path: Path,
                   content_type: str = "text/html; charset=utf-8") -> None:
        try:
            path.resolve().relative_to(_STATIC_DIR.resolve())
        except ValueError:
            return self._send_error("forbidden", 403)
        if not path.exists():
            return self._send_error("not found", 404)
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self._send_security_headers()
        if "text/html" in content_type:
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; "
                "script-src 'self'; "
                "connect-src 'self' ws: wss:; "
                "style-src 'self' 'unsafe-inline';",
            )
        self.end_headers()
        self.wfile.write(body)
        self._resp_len = len(body)

    def _serve_frontend(self, path: str) -> None:
        """Serve the built React+PixiJS app from static/app/."""
        rel = path[len("/app"):].lstrip("/")
        file_path = _FRONTEND_DIR / rel if rel else _FRONTEND_DIR / "index.html"
        try:
            file_path.resolve().relative_to(_FRONTEND_DIR.resolve())
        except ValueError:
            return self._send_error("forbidden", 403)
        # SPA fallback: unknown paths get index.html so client-side routing works
        if not file_path.exists() or file_path.is_dir():
            file_path = _FRONTEND_DIR / "index.html"
        if not file_path.exists():
            return self._send_error("not built — run: cd frontend && npm install && npm run build", 404)
        body = file_path.read_bytes()
        mime, _ = mimetypes.guess_type(str(file_path))
        # mimetypes may miss .js on some systems
        if file_path.suffix == ".js":
            mime = "application/javascript"
        elif file_path.suffix == ".css":
            mime = "text/css"
        content_type = mime or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self._send_security_headers()
        if "text/html" in content_type:
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; "
                "script-src 'self'; "
                "connect-src 'self' ws: wss:; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' blob: data: https://fal.media https://*.fal.media;",
            )
        self.end_headers()
        self.wfile.write(body)
        self._resp_len = len(body)

    def _sse_event(self, data: dict) -> None:
        payload = f"data: {json.dumps(data)}\n\n".encode()
        self.wfile.write(payload)
        self.wfile.flush()

    # ── GET ──

    def do_GET(self):
        import time
        self._started = time.monotonic()
        try:
            self._dispatch_get()
        except Exception as exc:
            observability.capture_exception(exc)
            try:
                self._send_error("internal server error", 500)
            except Exception:
                pass
        finally:
            self._emit_access_log()

    def _dispatch_get(self):
        parsed = urlparse(self.path)
        qs     = parse_qs(parsed.query)
        path   = parsed.path.rstrip("/")

        if not self._authorized(qs):
            return

        def param(key: str, default: str = "") -> str:
            vals = qs.get(key)
            return vals[0] if vals else default

        if path in ("", "/"):
            self._send_file(_STATIC_DIR / "index.html")

        elif path == "/explorer.js":
            self._send_file(_STATIC_DIR / "explorer.js",
                            content_type="application/javascript; charset=utf-8")

        elif path == "/d3.v7.min.js":
            # Vendored D3, served same-origin so the explorer never depends on a
            # third-party CDN (see static/index.html).
            self._send_file(_STATIC_DIR / "d3.v7.min.js",
                            content_type="application/javascript; charset=utf-8")

        elif path == "/nodeart.js":
            # The shared per-node generative-art module (ES module), consumed
            # by both browser clients.
            self._send_file(_STATIC_DIR / "nodeart.js",
                            content_type="application/javascript; charset=utf-8")

        elif path == "/nodeart-global.js":
            self._send_file(_STATIC_DIR / "nodeart-global.js",
                            content_type="application/javascript; charset=utf-8")

        elif path == "/app" or path.startswith("/app/"):
            self._serve_frontend(path)

        elif path == "/health":
            self._send_json({"status": "ok"})

        elif path == "/favicon.ico":
            # Browsers request this automatically; there's no icon, so answer
            # 204 (ungated) instead of letting it fall through to a gated 403
            # that clutters every tester's devtools console and the access log.
            self.send_response(204)
            self._send_security_headers()
            self.end_headers()
            self._resp_len = 0

        elif path == "/worlds":
            self._send_json(persistence.list_worlds())

        elif path == "/players":
            try:
                seed = int(param("seed", "42"))
            except ValueError:
                return self._send_error("invalid seed")
            self._send_json({"players": snapshot(get_room(seed))})

        elif path == "/history":
            try:
                seed = int(param("seed", "42"))
            except ValueError:
                return self._send_error("invalid seed")
            node_name = param("node_name", "")[:128]
            if node_name:
                # Node-scoped history: what happened HERE — the client uses
                # this to surface which presences left traces at the current
                # node (and to let the player address them).
                rows = [dict(h, node=node_name) for h in
                        persistence.get_node_history(seed, node_name, limit=20)]
                self._send_json({"mutations": rows, "node": node_name})
            else:
                self._send_json({"mutations": persistence.get_mutations(seed)})

        elif path == "/chronicle":
            # The world's full lived history, paginated backward in time and
            # grouped into deterministically named eras — how a new arrival
            # perceives everything every player and agent did before them.
            from multiverse.chronicle import annotate_eras, current_era
            try:
                seed = int(param("seed", "42"))
                limit = int(param("limit", "50"))
                before_raw = param("before", "")
                before = int(before_raw) if before_raw else None
            except ValueError:
                return self._send_error("invalid chronicle params")
            page = persistence.get_chronicle(seed, limit=limit, before_id=before)
            page["entries"] = annotate_eras(seed, page["entries"])
            page["seed"] = seed
            page["era_now"] = current_era(seed)
            self._send_json(page)

        elif path == "/position":
            # Cross-device resume: the caller's last position, keyed on their
            # per-user invite credential. Empty for shared-key / no-key sessions
            # (those fall back to the client's own localStorage cache).
            key = guard.supplied_key(self.headers, qs)
            self._send_json({"position": persistence.get_player_position(key)})

        elif path == "/world":
            try:
                root, seed, depth, min_b, max_b = _build_world(_flatten_qs(qs))
            except ValueError as exc:
                return self._send_error(str(exc))
            node_count = count_nodes(root)
            persistence.save_world(seed, node_count, depth, min_b, max_b)
            activity = persistence.count_mutations_by_node(seed)
            self._send_json({"seed": seed, "node_count": node_count,
                             "world": _node_to_dict(root, activity)})

        elif path == "/agent":
            try:
                seed      = int(param("seed",      "42"))
                name      = param("name",           "Scout")
                threshold = int(param("threshold",  "6"))
                max_nodes = int(param("max_nodes",  "50"))
            except ValueError as exc:
                return self._send_error(str(exc))
            persona_arg = param("persona", "")
            persona = persona_by_name(persona_arg) or persona_for_name(name)
            root  = generate_node_hierarchy(seed=seed)
            apply_ripple_scores(root, persistence.load_ripple_scores(seed))
            # Per-request bus with the standard record/ripple/effects wiring
            # so traversal events persist and change world substance.
            agent_bus = wire_world_handlers(CausalityBus(), seed)
            agent = Agent(name=name, danger_threshold=threshold, bus=agent_bus,
                          persona=persona)
            saved = persistence.load_agent_memory(name, seed)
            if saved:
                agent.memory = saved["visited_ids"]
            agent.traverse(root, max_nodes=max_nodes)
            events = [{"node": e.node_name, "level": e.level,
                       "state": e.state.name, "action": e.action,
                       "persona": e.persona}
                      for e in agent.log]
            run_id = persistence.save_agent_run(name, seed, agent.fresh_count, events)
            persistence.save_agent_memory(name, seed, agent.memory, events[-100:])
            self._send_json({"run_id": run_id, "agent": name, "seed": seed,
                             "persona": persona.name,
                             "nodes_visited": agent.fresh_count,
                             "total_known": len(agent.memory),
                             "events": events})

        elif path == "/observe":
            self._do_observe(qs)

        elif path == "/puzzle":
            self._do_puzzle(qs)

        elif path == "/ws":
            self._do_ws(qs)

        elif path == "/easter-egg/illusion":
            self._send_file(_STATIC_DIR / "easter-egg" / "illusion.html")

        elif path == "/easter-egg/konami.js":
            self._send_file(_STATIC_DIR / "easter-egg" / "konami.js",
                            content_type="application/javascript")

        else:
            self._send_error("not found", 404)

    # ── POST ──

    def do_POST(self):
        import time
        self._started = time.monotonic()
        try:
            self._dispatch_post()
        except Exception as exc:
            observability.capture_exception(exc)
            try:
                self._send_error("internal server error", 500)
            except Exception:
                pass
        finally:
            self._emit_access_log()

    def _dispatch_post(self):
        parsed = urlparse(self.path)
        path   = parsed.path.rstrip("/")
        qs     = parse_qs(parsed.query)

        if not self._authorized(qs):
            return
        if not self._rate_ok(path):
            return

        # The credential this request presented — used to charge paid calls
        # against the caller's per-user daily sub-cap (empty in open dev mode).
        user_key = guard.supplied_key(self.headers, qs)

        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            length = 0
        if length > _MAX_BODY:
            return self._send_error("payload too large", 413)
        try:
            body = json.loads(self.rfile.read(length)) if length else {}
        except json.JSONDecodeError:
            return self._send_error("invalid JSON")

        if path == "/speak":
            if guard.ai_disabled():
                return self._send_json({"response": guard.QUIET_RESPONSE,
                                        "ai": False})
            node_name = str(body.get("node_name", ""))[:128]
            message = str(body.get(
                "message",
                "Describe yourself to a traveler who has just arrived.",
            ))[:1024]
            try:
                seed = int(body.get("seed", 42))
            except (ValueError, TypeError):
                seed = 42
            raw_player = body.get("player_name")
            player_name = (str(raw_player)[:32].strip() or None) if raw_player else None
            # The speaker's durable conversation identity: the per-user
            # invite credential (hashed) when one was presented, else the
            # display name. Credential-keyed transcripts mean two players
            # who both call themselves "Ada" don't share a memory, and
            # renaming yourself doesn't orphan yours.
            if user_key:
                identity = hashlib.sha256(user_key.encode("utf-8")).hexdigest()[:16]
            else:
                identity = player_name

            import consciousness
            if not guard.consume_anthropic(user_key=user_key):
                return self._send_json({"response": guard.QUIET_RESPONSE,
                                        "ai": False})

            # Node identity is server-derived from the canonical world —
            # never trusted from the request body.
            node = _resolve_node(seed, node_name)
            if node is None:
                return self._send_error("no such place in this world", 404)
            try:
                history = persistence.get_node_history(seed, node.name)
                transcript = persistence.get_player_exchanges(
                    seed, node.name, identity)
                response = consciousness.speak(
                    node, message,
                    history=history,
                    transcript=transcript,
                    ripple_score=node.ripple_score,
                )
                # The exchange — both sides of it — becomes node memory.
                data = {"message": message[:128], "reply": response[:200]}
                if identity:
                    data["identity"] = identity
                persistence.record_mutation(
                    seed, node.name, "PLAYER_SPEAK", player_name, data,
                )
                self._send_json({"response": response, "ai": True})
            except Exception as exc:
                # The world goes quiet in character — no key, SDK failure,
                # or network error must never break the fiction with an
                # HTTP error or a stack trace.
                _log.warning("speak fallback (%s): %s", node.name, exc)
                self._send_json({
                    "response": consciousness.fallback_voice(node),
                    "ai": False,
                })

        elif path == "/puzzle/attempt":
            self._do_puzzle_attempt(body)

        elif path == "/act":
            self._do_act(body)

        elif path == "/image":
            self._do_image(body, user_key=user_key)

        elif path == "/agent/voice":
            self._do_agent_voice(body, user_key=user_key)

        elif path == "/position":
            self._do_save_position(body, user_key=user_key)

        else:
            self._send_error("not found", 404)

    # ── WebSocket ──

    def _do_ws(self, qs: dict) -> None:
        key = self.headers.get("Sec-WebSocket-Key", "")
        if not key:
            return self._send_error("WebSocket upgrade required", 400)

        try:
            seed = int(qs.get("seed", ["42"])[0])
            name = (qs.get("name", ["Anonymous"])[0] or "Anonymous")[:32]
        except (ValueError, IndexError):
            return self._send_error("invalid params", 400)

        # Cap concurrent connections (global + per-IP) before upgrading, so a
        # reconnect flood can't exhaust threads/memory. Reject cheaply with 503.
        ip = guard.client_ip(self.client_address, self.headers)
        if not guard.WS_LIMITER.acquire(ip):
            return self._send_error("too many connections", 503)

        # Everything past acquire() is wrapped so the connection slot is
        # released no matter how the socket dies (handshake failure, loop
        # exit, unexpected error).
        try:
            accept = base64.b64encode(
                hashlib.sha1((key + _WS_GUID).encode()).digest()
            ).decode()
            self.send_response(101, "Switching Protocols")
            self.send_header("Upgrade", "websocket")
            self.send_header("Connection", "Upgrade")
            self.send_header("Sec-WebSocket-Accept", accept)
            self.end_headers()
            self.wfile.flush()

            sock = self.connection
            sock.settimeout(60)  # 60-second idle timeout
            session_id = uuid.uuid4().hex[:8]
            player = Player(name=name, seed=seed, current_node="", session_id=session_id, sock=sock)
            player.start_writer()

            room = get_room(seed)
            with room.lock:
                room.players[session_id] = player

            player.send({"type": "welcome", "session_id": session_id,
                         "players": snapshot(room)})
            broadcast(room, {"type": "player_join", "name": name, "session_id": session_id},
                      exclude=session_id)

            try:
                while True:
                    # send_lock keeps this thread's pong/close echoes from
                    # interleaving with the writer thread's data frames.
                    payload = ws_recv(sock, send_lock=player.send_lock)
                    if payload is None:
                        break
                    if not payload:
                        continue  # control frame
                    try:
                        msg = json.loads(payload)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        continue
                    msg_type = msg.get("type")
                    if msg_type == "move":
                        node_name = str(msg.get("node", ""))[:64]
                        with room.lock:
                            player.current_node = node_name
                        broadcast(room, {"type": "player_move", "name": name,
                                         "node": node_name, "session_id": session_id},
                                  exclude=session_id)
                    elif msg_type == "chat":
                        text = str(msg.get("text", "")).strip()[:256]
                        if text:
                            broadcast(room, {"type": "chat", "name": name,
                                             "text": text, "session_id": session_id})
                            # Attribute the chat to the speaker's current node so
                            # downstream consumers (consciousness history, image
                            # invalidation) see it as a node interaction.
                            if player.current_node:
                                persistence.record_mutation(
                                    seed, player.current_node, "PLAYER_CHAT",
                                    name, {"text": text[:128]},
                                )
                    elif msg_type == "ping":
                        player.send({"type": "pong"})
            except ProtocolError:
                # RFC 6455 violation (unmasked frame, bad fragmentation, …):
                # attempt a 1002 close, then drop the connection.
                try:
                    _send_frame(sock, 0x8, struct.pack(">H", 1002),
                                lock=player.send_lock)
                except OSError:
                    pass
            except (OSError, ConnectionResetError, BrokenPipeError):
                pass
            finally:
                player.stop_writer()
                with room.lock:
                    room.players.pop(session_id, None)
                broadcast(room, {"type": "player_leave", "name": name,
                                 "session_id": session_id})
        finally:
            guard.WS_LIMITER.release(ip)

    # ── Observe (SSE) ──

    def _do_image(self, body: dict, user_key: str = "") -> None:
        import os
        import urllib.request as _urlreq

        if guard.images_disabled():
            return self._send_json({"url": None, "error": "image generation disabled"})

        node_name = str(body.get("node_name", ""))[:128]
        try:
            seed_int = int(body.get("seed", 42))
        except (ValueError, TypeError):
            seed_int = 42

        # Node identity — level, properties, evolution — is server-derived;
        # the client cannot style-inject via forged properties.
        node = _resolve_node(seed_int, node_name)
        if node is None:
            return self._send_error("no such place in this world", 404)

        history = persistence.get_node_history(seed_int, node.name, limit=1000)
        ripple_score = node.ripple_score

        # Cache key folds in:
        #   - history bucket (every 5 interactions → fresh image even if
        #     style modifiers don't shift), and
        #   - style signature (modifier flips, including ripple_score crossing
        #     its threshold → fresh image even if the bucket hasn't advanced).
        history_bucket = len(history) // 5
        sig            = imageprompt.style_signature(
            node.level, node.properties, history, ripple_score=ripple_score,
        )
        node_key       = f"{seed_int}:{node.name}:{history_bucket}:{sig}"
        cached         = persistence.get_cached_image(node_key)
        if cached:
            return self._send_json({"url": cached})

        fal_key = os.environ.get("FAL_KEY", "")
        if not fal_key:
            return self._send_json({"url": None, "error": "FAL_KEY not set"})

        if not guard.consume_fal(user_key=user_key):
            return self._send_json({"url": None, "error": "daily image budget exhausted"})

        prompt = imageprompt.assemble_prompt(
            node.level, node.name, node.properties, history,
            ripple_score=ripple_score,
        )

        try:
            req_body = json.dumps({
                "prompt": prompt,
                "image_size": "landscape_4_3",
                "num_inference_steps": 4,
                "num_images": 1,
            }).encode()
            req = _urlreq.Request(
                "https://fal.run/fal-ai/fast-sdxl",
                data=req_body,
                headers={
                    "Authorization": f"Key {fal_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with _urlreq.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read())
            images = result.get("images", [])
            url = images[0]["url"] if images else None
        except Exception as exc:
            _log.warning("fal.ai image error: %s", exc)
            return self._send_json({"url": None, "error": str(exc)})

        if url:
            persistence.cache_image(node_key, url)
        self._send_json({"url": url})

    def _do_agent_voice(self, body: dict, user_key: str = "") -> None:
        """POST /agent/voice — let an agent speak in its persona's voice.

        The node is resolved server-side and its history is passed in, so
        the voiced agent stands somewhere real and can reference what has
        actually happened there — including its own FSM traces.
        """
        if guard.ai_disabled():
            return self._send_json({"response": guard.QUIET_RESPONSE,
                                    "agent": "", "persona": "", "node": "",
                                    "ai": False})
        if not guard.consume_anthropic(user_key=user_key):
            return self._send_json({"response": guard.QUIET_RESPONSE,
                                    "agent": "", "persona": "", "node": "",
                                    "ai": False})
        agent_name = str(body.get("agent_name", "Scout"))[:32]
        node_name  = str(body.get("node_name",  ""))[:128]
        message    = str(body.get(
            "message", "Where are you, and what do you see?",
        ))[:1024]
        try:
            seed = int(body.get("seed", 42))
        except (ValueError, TypeError):
            seed = 42
        persona_arg = str(body.get("persona", ""))[:32]
        persona = persona_by_name(persona_arg) or persona_for_name(agent_name)

        node = _resolve_node(seed, node_name)
        if node is None:
            return self._send_error("no such place in this world", 404)
        try:
            import consciousness
            history = persistence.get_node_history(seed, node.name)
            agent_memory = persistence.load_agent_memory(agent_name, seed)
            response = consciousness.voice_agent(persona, agent_name, node,
                                                 message, history=history,
                                                 agent_memory=agent_memory)
            self._send_json({
                "agent":    agent_name,
                "persona":  persona.name,
                "node":     node.name,
                "response": response,
                "ai":       True,
            })
        except Exception as exc:
            _log.warning("agent voice fallback (%s): %s", agent_name, exc)
            self._send_json({
                "agent":    agent_name,
                "persona":  persona.name,
                "node":     node.name,
                "response": (
                    f"{agent_name} does not answer. Only the traces of a "
                    f"{persona.name} remain here, already cooling."
                ),
                "ai": False,
            })

    def _do_save_position(self, body: dict, user_key: str = "") -> None:
        """POST /position — persist the caller's last position for cross-device
        resume. No-ops (saved:false) unless the request carries a per-user
        invite key with a live row."""
        node_name = str(body.get("node", ""))[:128].strip()
        if not node_name:
            return self._send_error("missing node")

        def _int(key: str, default: int) -> int:
            try:
                return int(body.get(key, default))
            except (TypeError, ValueError):
                return default

        seed  = _int("seed", 0)
        depth = _int("depth", 6)
        min_b = _int("min_breadth", 1)
        max_b = _int("max_breadth", 3)
        saved = persistence.save_player_position(
            user_key, node_name, seed, depth, min_b, max_b,
        )
        self._send_json({"saved": bool(saved)})

    def _do_observe(self, qs: dict) -> None:
        try:
            root, seed, *_ = _build_world(_flatten_qs(qs))
        except (ValueError, KeyError) as exc:
            return self._send_error(str(exc))

        node_name  = qs.get("node_name", [""])[0]
        agent_name = (qs.get("name", ["Observer"])[0] or "Observer")[:32]
        persona_arg = qs.get("persona", [""])[0]
        persona = persona_by_name(persona_arg) or persona_for_name(agent_name)
        target     = (find_node(root, node_name) if node_name else None) or root

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self._send_security_headers()
        self.end_headers()

        distance_map = build_distance_map(target)
        room         = get_room(seed)

        agent_enter(room, agent_name, persona=persona.name)

        def handler(node: SpatialNode, event: causality.CausalEvent) -> None:
            # The strength shown is the event's REAL propagated strength —
            # not a display-side function of tree depth. `depth` is the hop
            # distance from the observed origin (ancestors included).
            d        = distance_map.get(node.id, 0)
            strength = round(event.strength, 4)
            payload  = {
                "node":     node.name,
                "level":    node.level,
                "kind":     event.kind.name,
                "strength": strength,
                "depth":    d,
                "origin":   target.name,
                "agent":    agent_name,
                "persona":  persona.name,
            }
            try:
                self._sse_event(payload)
            except (BrokenPipeError, ConnectionResetError):
                pass
            broadcast(room, {"type": "causal_event", **payload})

            # Check for agent-to-agent encounters at this node
            others = agent_move(room, agent_name, node.name)
            for other_name in others:
                encounter = {
                    "type":           "agent_encounter",
                    "agent1":         agent_name,
                    "agent1_persona": persona.name,
                    "agent2":         other_name,
                    "agent2_persona": agent_persona(room, other_name),
                    "node":           node.name,
                    "level":          node.level,
                }
                broadcast(room, encounter)

        # Per-request bus keeps observation isolated from the global event
        # stream — concurrent /observe calls no longer need to serialise.
        bus = CausalityBus()
        bus.register_handler(handler)
        wire_world_handlers(bus, seed)
        try:
            agent = Agent(name=agent_name, danger_threshold=7, bus=bus,
                          persona=persona)
            agent.traverse(target, max_nodes=40)
            nodes_visited = len(agent.visited)
            self._sse_event({"done": True, "nodes_visited": nodes_visited})
            broadcast(get_room(seed), {"type": "agent_done", "node": target.name,
                                       "nodes_visited": nodes_visited})
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            agent_leave(room, agent_name)

    # ── Puzzle ──

    def _do_puzzle(self, qs: dict) -> None:
        try:
            root, seed, *_ = _build_world(_flatten_qs(qs))
        except (ValueError, KeyError) as exc:
            return self._send_error(str(exc))

        node_name = qs.get("node_name", [""])[0]
        target    = (find_node(root, node_name) if node_name else None) or root

        engine  = PuzzleEngine(seed=seed)
        engine.attach_puzzles(target)
        puzzles = engine.collect_puzzles(target)

        if not puzzles:
            return self._send_json({"found": False})

        p = puzzles[0]
        self._send_json({
            "found":        True,
            "name":         p.name,
            "kind":         p.kind.name,
            "prompt":       p.prompt,
            "hints_count":  len(p.hints),
            "max_attempts": p.max_attempts,
            # Difficulty is a per-node property (1 gentle … 4 hard), surfaced so
            # a player can pick their own challenge while exploring.
            "difficulty":   p.difficulty,
        })

    def _do_act(self, body: dict) -> None:
        """Perform a node's scale-native verb (multiverse/verbs.py).

        The verb's material change applies exactly once, here at the
        origin (the producer owns the flavor line); the act then rides
        the standard causal rails — recorded in the chronicle, rippled,
        staged outward ring by ring — so mending an object is felt, more
        faintly, by the room that holds it and the molecules inside it.
        """
        try:
            root, seed, *_ = _build_world(body)
        except (ValueError, TypeError) as exc:
            return self._send_error(str(exc))

        node_name   = str(body.get("node_name", ""))[:128]
        verb_name   = str(body.get("verb", ""))[:32].strip().lower()
        raw_player  = body.get("player_name")
        player_name = (str(raw_player)[:32].strip() or None) if raw_player else None

        # Full-tree resolution (not _resolve_node): staging the cascade
        # needs the node's real parent AND children arms.
        target = find_node(root, node_name) if node_name else None
        if target is None:
            return self._send_error("no such place in this world", 404)

        verb = verb_for_level(target.level)
        if verb is None:
            return self._send_error(f"nothing can be done at {target.level} scale")
        if verb_name and verb_name != verb.name:
            return self._send_error(
                f"'{verb_name}' doesn't work at {target.level} scale — "
                f"here you can only {verb.name}", 400)

        token = f"{player_name or 'traveler'}:{target.name}"
        changed, flavor = apply_verb(target, verb, token)

        if changed:
            persistence.upsert_node_properties(seed, target.name, changed)
            persistence.record_mutation(
                seed, target.name, "SCALE_ACT", player_name,
                {"verb": verb.name, "changed": changed},
            )

            room = get_room(seed)
            broadcast(room, {
                "type":    "scale_act",
                "node":    target.name,
                "level":   target.level,
                "verb":    verb.name,
                "actor":   player_name or "someone",
                "changed": changed,
                "flavor":  flavor,
            })

            # The act echoes outward: origin already changed materially
            # (above); every ring beyond it carries ripple + history via
            # the queue, arriving at world speed.
            act_bus = CausalityBus()

            def _act_handler(n: SpatialNode, ev: causality.CausalEvent,
                             _room=room, _origin=target.name) -> None:
                broadcast(_room, {
                    "type":     "causal_event",
                    "node":     n.name,
                    "level":    n.level,
                    "kind":     ev.kind.name,
                    "strength": round(ev.strength, 4),
                    "depth":    0,
                    "origin":   _origin,
                })

            act_bus.register_handler(_act_handler)
            wire_world_handlers(act_bus, seed)
            payload = {"verb": verb.name}
            if player_name:
                payload["actor"] = player_name
            act_bus.emit(target, EventKind.SCALE_ACT, payload)
            stage_cascade(seed, target, EventKind.SCALE_ACT, payload)

        self._send_json({
            "verb":    verb.name,
            "level":   target.level,
            "node":    target.name,
            "changed": changed,
            "flavor":  flavor,
        })

    def _do_puzzle_attempt(self, body: dict) -> None:
        try:
            root, seed, *_ = _build_world(body)
        except (ValueError, TypeError) as exc:
            return self._send_error(str(exc))

        node_name   = body.get("node_name", "")
        answer      = body.get("answer", "").strip()
        raw_player  = body.get("player_name")
        player_name = (str(raw_player)[:32].strip() or None) if raw_player else None

        target = (find_node(root, node_name) if node_name else None) or root

        engine  = PuzzleEngine(seed=seed)
        engine.attach_puzzles(target)
        puzzles = engine.collect_puzzles(target)

        if not puzzles:
            return self._send_error("no puzzle found")

        p              = puzzles[0]
        effective_node = node_name or target.name
        room           = get_room(seed)
        correct        = answer.lower() == p.answer.lower()

        # Co-op: attempts pool across all players in the room. record_attempt
        # holds the room lock while incrementing, so concurrent solvers can't
        # both flip `solver` from None.
        session, just_solved = record_attempt(
            room, effective_node, p.name, player_name, correct,
        )

        # If the puzzle was already solved by an earlier player, return that
        # state without re-firing broadcasts or mutations.
        if session.solver is not None and not just_solved:
            return self._send_json({
                "correct":        True,
                "result":         "SOLVED",
                "hint":           None,
                "attempt":        session.attempts,
                "max_attempts":   p.max_attempts,
                "solver":         session.solver,
                "contributors":   sorted(session.contributors),
                "correct_answer": None,
            })

        failed = not correct and session.attempts >= p.max_attempts
        hint   = (p.hints[session.attempts - 1]
                  if not correct and not failed
                  and session.attempts <= len(p.hints)
                  else None)

        contributors = sorted(session.contributors)

        if just_solved:
            persistence.record_mutation(
                seed, effective_node, "PUZZLE_SOLVED",
                session.solver if session.solver != "anonymous" else None,
                {"puzzle": p.name, "contributors": contributors},
            )
            broadcast(room, {"type": "puzzle_solved", "node": effective_node,
                             "puzzle": p.name, "solver": session.solver,
                             "contributors": contributors})

            # Staged cascade: the origin fires immediately — instant
            # feedback for everyone in the room — and every subsequent ring
            # rides the causal queue, arriving hop by hop (the causal pump
            # fires and broadcasts each one), so players watch the
            # consequence travel across scales instead of it completing
            # invisibly inside this request.
            solve_bus = CausalityBus()

            def _causal_handler(n: SpatialNode, ev: causality.CausalEvent,
                                 _room=room, _origin=effective_node) -> None:
                broadcast(_room, {
                    "type":     "causal_event",
                    "node":     n.name,
                    "level":    n.level,
                    "kind":     ev.kind.name,
                    "strength": round(ev.strength, 4),
                    "depth":    0,
                    "origin":   _origin,
                })

            solve_bus.register_handler(_causal_handler)
            wire_world_handlers(solve_bus, seed)
            solve_bus.emit(target, EventKind.PUZZLE_SOLVED,
                           {"puzzle": p.name, "contributors": contributors})
            stage_cascade(seed, target, EventKind.PUZZLE_SOLVED,
                          {"puzzle": p.name, "contributors": contributors})

        if failed:
            persistence.record_mutation(
                seed, effective_node, "PUZZLE_FAILED", None,
                {"puzzle": p.name, "answer_given": answer[:64],
                 "contributors": contributors},
            )

        self._send_json({
            "correct":        correct,
            "result":         "SOLVED" if correct else ("FAILED" if failed else "UNSOLVED"),
            "hint":           hint,
            "attempt":        session.attempts,
            "max_attempts":   p.max_attempts,
            "solver":         session.solver,
            "contributors":   contributors,
            # Server-tracked attempt count means `failed` only flips at the
            # real last attempt; safe to release the answer there.
            "correct_answer": p.answer if failed else None,
        })
