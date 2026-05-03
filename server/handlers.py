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
from multiverse.generator import generate_node_hierarchy
from multiverse.node import SpatialNode
from multiverse.utils import build_depth_map, count_nodes, find_node
from puzzles.engine import PuzzleEngine
from server.protocol import ws_recv
from server.rooms import Player, broadcast, get_room, snapshot


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
    return root, seed, depth, min_b, max_b


def _node_to_dict(node: SpatialNode) -> dict:
    return {
        "id": node.id,
        "name": node.name,
        "level": node.level,
        "properties": node.properties,
        "children": [_node_to_dict(c) for c in node.children],
    }


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
                "img-src 'self' blob: data:;",
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
            root  = generate_node_hierarchy(seed=seed)
            agent = Agent(name=name, danger_threshold=threshold)
            saved = persistence.load_agent_memory(name, seed)
            if saved:
                agent.memory = saved["visited_ids"]
            agent.traverse(root, max_nodes=max_nodes)
            events = [{"node": e.node_name, "level": e.level,
                       "state": e.state.name, "action": e.action}
                      for e in agent.log]
            run_id = persistence.save_agent_run(name, seed, agent.fresh_count, events)
            persistence.save_agent_memory(name, seed, agent.memory, events[-100:])
            self._send_json({"run_id": run_id, "agent": name, "seed": seed,
                             "nodes_visited": agent.fresh_count,
                             "total_known": len(agent.memory),
                             "events": events})

        elif path == "/observe":
            self._do_observe(qs)

        elif path == "/puzzle":
            self._do_puzzle(qs)

        elif path == "/ws":
            self._do_ws(qs)

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
            node = SpatialNode(
                name=node_name,
                level=node_level,
                properties=node_properties,
            )
            try:
                import consciousness
                history = persistence.get_node_history(seed, node_name) if seed else []
                self._send_json({"response": consciousness.speak(node, message, history=history)})
            except ImportError:
                self._send_error("consciousness module requires: pip install anthropic")
            except Exception as exc:
                _log.warning("speak error: %s", exc)
                self._send_error("Service unavailable", 503)

        elif path == "/puzzle/attempt":
            self._do_puzzle_attempt(body)

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

    def _do_observe(self, qs: dict) -> None:
        try:
            root, seed, *_ = _build_world(_flatten_qs(qs))
        except (ValueError, KeyError) as exc:
            return self._send_error(str(exc))

        node_name = qs.get("node_name", [""])[0]
        target    = (find_node(root, node_name) if node_name else None) or root

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self._send_security_headers()
        self.end_headers()

        depth_map = build_depth_map(target)

        room = get_room(seed)

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
            }
            try:
                self._sse_event(payload)
            except (BrokenPipeError, ConnectionResetError):
                pass
            broadcast(room, {"type": "causal_event", **payload})

        # Per-request bus keeps observation isolated from the global event
        # stream — concurrent /observe calls no longer need to serialise.
        bus = CausalityBus()
        bus.register_handler(handler)
        try:
            agent = Agent(name="Observer", danger_threshold=7, bus=bus)
            agent.traverse(target, max_nodes=40)
            nodes_visited = len(agent.visited)
            self._sse_event({"done": True, "nodes_visited": nodes_visited})
            broadcast(get_room(seed), {"type": "agent_done", "node": target.name,
                                       "nodes_visited": nodes_visited})
        except (BrokenPipeError, ConnectionResetError):
            pass

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
        attempt_raw = body.get("attempt", 1)

        target = (find_node(root, node_name) if node_name else None) or root

        engine  = PuzzleEngine(seed=seed)
        engine.attach_puzzles(target)
        puzzles = engine.collect_puzzles(target)

        if not puzzles:
            return self._send_error("no puzzle found")

        p = puzzles[0]
        # Clamp attempt to [1, max_attempts+1] so a client cannot fabricate a
        # false "failed" state (e.g. attempt=99999) to extract correct_answer.
        # Values above max_attempts are still ≥ max_attempts so failed stays
        # computable, but the correct_answer guard below only releases the
        # answer when attempt is within the legitimate range (≤ max_attempts).
        try:
            attempt = max(1, min(int(attempt_raw), p.max_attempts + 1))
        except (ValueError, TypeError):
            attempt = 1

        correct = answer.lower() == p.answer.lower()
        failed  = not correct and attempt >= p.max_attempts
        hint    = (p.hints[attempt - 1]
                   if not correct and not failed and attempt <= len(p.hints)
                   else None)

        if correct:
            effective_node = node_name or target.name
            persistence.record_mutation(seed, effective_node, "PUZZLE_SOLVED",
                                        None, {"puzzle": p.name})
            room = get_room(seed)
            broadcast(room, {"type": "puzzle_solved", "node": effective_node,
                             "puzzle": p.name})

            # Propagate causal ripple downward from the solved node and fan
            # each event out to all connected WebSocket clients in this world.
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
            solve_bus.propagate(target, EventKind.PUZZLE_SOLVED, {"puzzle": p.name})

        self._send_json({
            "correct":        correct,
            "result":         "SOLVED" if correct else ("FAILED" if failed else "UNSOLVED"),
            "hint":           hint,
            "attempt":        attempt,
            "max_attempts":   p.max_attempts,
            # Only reveal the answer when the server confirms failure at the
            # legitimate last attempt (attempt ≤ max_attempts).  An out-of-
            # bounds attempt (clamped to max_attempts+1) is excluded here.
            "correct_answer": p.answer if (failed and attempt <= p.max_attempts) else None,
        })
