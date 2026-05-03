"""HTTP request dispatch for the nested-worlds server."""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import mimetypes
import uuid
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs, urlparse

import causality
import persistence
from causality import CausalityBus, DAMPENING, EventKind
from agents.agent import Agent
from agents.personas import by_name as persona_by_name, for_name as persona_for_name
from multiverse.generator import generate_node_hierarchy
from multiverse.node import SpatialNode
from multiverse.utils import apply_ripple_scores, build_depth_map, count_nodes, find_node
from puzzles.engine import PuzzleEngine
from server import imageprompt
from server.protocol import ws_recv
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
    arguments.
    """
    seed  = int(params.get("seed",        42))
    depth = int(params.get("depth",        6))
    min_b = int(params.get("min_breadth",  1))
    max_b = int(params.get("max_breadth",  3))
    root = generate_node_hierarchy(seed=seed, max_depth=depth,
                                   min_breadth=min_b, max_breadth=max_b)
    # Hydrate persisted causal pressure so ripple_score isn't reset to 0
    # every endpoint call (closes the residual ADR-002 §1 callout).
    apply_ripple_scores(root, persistence.load_ripple_scores(seed))
    return root, seed, depth, min_b, max_b


def _node_to_dict(node: SpatialNode) -> dict:
    return {
        "id": node.id,
        "name": node.name,
        "level": node.level,
        "properties": node.properties,
        "children": [_node_to_dict(c) for c in node.children],
    }


def _record_mutation_handler(seed: int):
    """Bus handler that persists each fired causal event into world_mutations.

    Agent-emitted events carry the agent name in `event.payload["agent"]`;
    `record_mutation`'s player_name slot is reserved for human players, so we
    keep player_name=None here and rely on the payload for attribution.
    """
    def handler(node: SpatialNode, event: causality.CausalEvent) -> None:
        persistence.record_mutation(
            seed, node.name, event.kind.name, None, dict(event.payload)
        )
    return handler


def _record_ripple_handler(seed: int):
    """Bus handler that writes the post-fire ripple_score into node_runtime_state.

    `CausalityBus._fire` updates `node.ripple_score` before invoking
    handlers, so by the time we run the value is already the new
    cumulative pressure for this node.
    """
    def handler(node: SpatialNode, _event: causality.CausalEvent) -> None:
        persistence.upsert_ripple_score(seed, node.name, node.ripple_score)
    return handler


# ── Handler ────────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    # ── response helpers ──

    def _send_security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")

    def _send_json(self, data: object, status: int = 200) -> None:
        body = json.dumps(data, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._send_security_headers()
        self.end_headers()
        self.wfile.write(body)

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
                "script-src 'self' https://d3js.org; "
                "connect-src 'self' ws: wss:; "
                "style-src 'self' 'unsafe-inline';",
            )
        self.end_headers()
        self.wfile.write(body)

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

    def _sse_event(self, data: dict) -> None:
        payload = f"data: {json.dumps(data)}\n\n".encode()
        self.wfile.write(payload)
        self.wfile.flush()

    # ── GET ──

    def do_GET(self):
        parsed = urlparse(self.path)
        qs     = parse_qs(parsed.query)
        path   = parsed.path.rstrip("/")

        def param(key: str, default: str = "") -> str:
            vals = qs.get(key)
            return vals[0] if vals else default

        if path in ("", "/"):
            self._send_file(_STATIC_DIR / "index.html")

        elif path == "/explorer.js":
            self._send_file(_STATIC_DIR / "explorer.js",
                            content_type="application/javascript; charset=utf-8")

        elif path == "/app" or path.startswith("/app/"):
            self._serve_frontend(path)

        elif path == "/health":
            self._send_json({"status": "ok"})

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
            self._send_json({"mutations": persistence.get_mutations(seed)})

        elif path == "/world":
            try:
                root, seed, depth, min_b, max_b = _build_world(_flatten_qs(qs))
            except ValueError as exc:
                return self._send_error(str(exc))
            node_count = count_nodes(root)
            persistence.save_world(seed, node_count, depth, min_b, max_b)
            self._send_json({"seed": seed, "node_count": node_count,
                             "world": _node_to_dict(root)})

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
            # Per-request bus carrying a recorder so traversal events land in
            # world_mutations alongside puzzle solves.
            agent_bus = CausalityBus()
            agent_bus.register_handler(_record_mutation_handler(seed))
            agent_bus.register_handler(_record_ripple_handler(seed))
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
        path = urlparse(self.path).path.rstrip("/")
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
            node_name       = str(body.get("node_name", "Unknown"))[:128]
            node_level      = str(body.get("node_level", "Room"))[:64]
            node_properties = body.get("node_properties", {})
            if not isinstance(node_properties, dict):
                node_properties = {}
            message = str(body.get(
                "message",
                "Describe yourself to a traveler who has just arrived.",
            ))[:1024]
            try:
                seed = int(body.get("seed", 0))
            except (ValueError, TypeError):
                seed = 0
            raw_player = body.get("player_name")
            player_name = (str(raw_player)[:32].strip() or None) if raw_player else None
            node = SpatialNode(
                name=node_name,
                level=node_level,
                properties=node_properties,
            )
            try:
                import consciousness
                history = persistence.get_node_history(seed, node_name) if seed else []
                response = consciousness.speak(node, message, history=history)
                if seed:
                    persistence.record_mutation(
                        seed, node_name, "PLAYER_SPEAK", player_name,
                        {"message": message[:128]},
                    )
                self._send_json({"response": response})
            except ImportError:
                self._send_error("consciousness module requires: pip install anthropic")
            except Exception as exc:
                _log.warning("speak error: %s", exc)
                self._send_error("Service unavailable", 503)

        elif path == "/puzzle/attempt":
            self._do_puzzle_attempt(body)

        elif path == "/image":
            self._do_image(body)

        elif path == "/agent/voice":
            self._do_agent_voice(body)

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

        room = get_room(seed)
        with room.lock:
            room.players[session_id] = player

        player.send({"type": "welcome", "session_id": session_id,
                     "players": snapshot(room)})
        broadcast(room, {"type": "player_join", "name": name, "session_id": session_id},
                  exclude=session_id)

        try:
            while True:
                payload = ws_recv(sock)
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
        except (OSError, ConnectionResetError, BrokenPipeError):
            pass
        finally:
            with room.lock:
                room.players.pop(session_id, None)
            broadcast(room, {"type": "player_leave", "name": name,
                             "session_id": session_id})

    # ── Observe (SSE) ──

    def _do_image(self, body: dict) -> None:
        import os
        import urllib.request as _urlreq

        node_id    = str(body.get("node_id",    "unknown"))[:128]
        node_name  = str(body.get("node_name",  ""))[:128]
        node_level = str(body.get("node_level", "Room"))[:64]
        node_props = body.get("node_properties", {})
        if not isinstance(node_props, dict):
            node_props = {}
        seed       = str(body.get("seed", "0"))[:16]

        try:
            seed_int = int(seed)
        except ValueError:
            seed_int = 0
        history: list[dict] = []
        ripple_score = 0.0
        if seed_int and node_name:
            history = persistence.get_node_history(seed_int, node_name, limit=1000)
            ripple_score = persistence.get_ripple_score(seed_int, node_name)

        # Cache key folds in:
        #   - history bucket (every 5 interactions → fresh image even if
        #     style modifiers don't shift), and
        #   - style signature (modifier flips, including ripple_score crossing
        #     its threshold → fresh image even if the bucket hasn't advanced).
        history_bucket = len(history) // 5
        sig            = imageprompt.style_signature(
            node_level, node_props, history, ripple_score=ripple_score,
        )
        node_key       = f"{seed}:{node_id}:{history_bucket}:{sig}"
        cached         = persistence.get_cached_image(node_key)
        if cached:
            return self._send_json({"url": cached})

        fal_key = os.environ.get("FAL_KEY", "")
        if not fal_key:
            return self._send_json({"url": None, "error": "FAL_KEY not set"})

        prompt = imageprompt.assemble_prompt(
            node_level, node_name, node_props, history,
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

    def _do_agent_voice(self, body: dict) -> None:
        """POST /agent/voice — let an agent speak in its persona's voice."""
        agent_name = str(body.get("agent_name", "Scout"))[:32]
        node_name  = str(body.get("node_name",  "Unknown"))[:128]
        node_level = str(body.get("node_level", "Room"))[:64]
        message    = str(body.get(
            "message", "Where are you, and what do you see?",
        ))[:1024]
        persona_arg = str(body.get("persona", ""))[:32]
        persona = persona_by_name(persona_arg) or persona_for_name(agent_name)
        node = SpatialNode(name=node_name, level=node_level, properties={})
        try:
            import consciousness
            response = consciousness.voice_agent(persona, agent_name, node, message)
            self._send_json({
                "agent":    agent_name,
                "persona":  persona.name,
                "node":     node_name,
                "response": response,
            })
        except ImportError:
            self._send_error("consciousness module requires: pip install anthropic")
        except Exception as exc:
            _log.warning("agent voice error: %s", exc)
            self._send_error("Service unavailable", 503)

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

        depth_map = build_depth_map(target)
        room      = get_room(seed)

        agent_enter(room, agent_name, persona=persona.name)

        def handler(node: SpatialNode, event: causality.CausalEvent) -> None:
            d        = depth_map.get(node.id, 0)
            strength = round(DAMPENING ** d, 4)
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
        bus.register_handler(_record_mutation_handler(seed))
        bus.register_handler(_record_ripple_handler(seed))
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

            # Propagate causal ripple from the solved node — bidirectional
            # since causality.propagate() defaults to direction="both".
            # Each fired event fans out to all connected WebSocket clients.
            causal_depth_map = build_depth_map(target)
            solve_bus = CausalityBus()

            def _causal_handler(n: SpatialNode, ev: causality.CausalEvent,
                                 _room=room, _dm=causal_depth_map,
                                 _origin=effective_node) -> None:
                d = _dm.get(n.id, 0)
                broadcast(_room, {
                    "type":     "causal_event",
                    "node":     n.name,
                    "level":    n.level,
                    "kind":     ev.kind.name,
                    "strength": round(DAMPENING ** d, 4),
                    "depth":    d,
                    "origin":   _origin,
                })

            solve_bus.register_handler(_causal_handler)
            solve_bus.register_handler(_record_mutation_handler(seed))
            solve_bus.register_handler(_record_ripple_handler(seed))
            solve_bus.propagate(target, EventKind.PUZZLE_SOLVED,
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
