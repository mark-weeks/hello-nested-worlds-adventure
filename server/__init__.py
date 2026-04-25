from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from socketserver import ThreadingMixIn
from urllib.parse import parse_qs, urlparse

import causality
from agents.agent import Agent
from multiverse.generator import generate_node_hierarchy
from multiverse.node import SpatialNode
from puzzles.engine import PuzzleEngine
import persistence

_STATIC_DIR = Path(__file__).parent.parent / "static"
_OBSERVE_LOCK = threading.Lock()
_DAMPENING = 0.6


# ── Helpers ────────────────────────────────────────────────────────────────

def _node_to_dict(node: SpatialNode) -> dict:
    return {
        "id": node.id,
        "name": node.name,
        "level": node.level,
        "properties": node.properties,
        "children": [_node_to_dict(c) for c in node.children],
    }


def _count_nodes(node: SpatialNode) -> int:
    return 1 + sum(_count_nodes(c) for c in node.children)


def _find_node(root: SpatialNode, name: str) -> SpatialNode | None:
    if root.name == name:
        return root
    for child in root.children:
        found = _find_node(child, name)
        if found:
            return found
    return None


def _build_depth_map(node: SpatialNode, depth: int = 0,
                     result: dict | None = None) -> dict[str, int]:
    if result is None:
        result = {}
    result[node.id] = depth
    for child in node.children:
        _build_depth_map(child, depth + 1, result)
    return result


def _rebuild(params: dict) -> tuple[SpatialNode, int, int, int, int]:
    seed  = int(params.get("seed",        ["42"])[0])
    depth = int(params.get("depth",       ["6"])[0])
    min_b = int(params.get("min_breadth", ["1"])[0])
    max_b = int(params.get("max_breadth", ["3"])[0])
    root  = generate_node_hierarchy(seed=seed, max_depth=depth,
                                    min_breadth=min_b, max_breadth=max_b)
    return root, seed, depth, min_b, max_b


# ── Handler ────────────────────────────────────────────────────────────────

class _Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    # ── response helpers ──

    def _send_json(self, data: object, status: int = 200) -> None:
        body = json.dumps(data, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, message: str, status: int = 400) -> None:
        self._send_json({"error": message}, status)

    def _send_file(self, path: Path,
                   content_type: str = "text/html; charset=utf-8") -> None:
        if not path.exists():
            return self._send_error("not found", 404)
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
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

        elif path == "/health":
            self._send_json({"status": "ok"})

        elif path == "/worlds":
            self._send_json(persistence.list_worlds())

        elif path == "/world":
            try:
                seed  = int(param("seed",        "42"))
                depth = int(param("depth",        "6"))
                min_b = int(param("min_breadth",  "1"))
                max_b = int(param("max_breadth",  "3"))
            except ValueError as exc:
                return self._send_error(str(exc))
            try:
                root = generate_node_hierarchy(seed=seed, max_depth=depth,
                                               min_breadth=min_b, max_breadth=max_b)
            except ValueError as exc:
                return self._send_error(str(exc))
            node_count = _count_nodes(root)
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
            agent.traverse(root, max_nodes=max_nodes)
            events = [{"node": e.node_name, "level": e.level,
                       "state": e.state.name, "action": e.action}
                      for e in agent.log]
            run_id = persistence.save_agent_run(name, seed, len(agent.visited), events)
            self._send_json({"run_id": run_id, "agent": name, "seed": seed,
                             "nodes_visited": len(agent.visited), "events": events})

        elif path == "/observe":
            self._do_observe(qs)

        elif path == "/puzzle":
            self._do_puzzle(qs)

        else:
            self._send_error("not found", 404)

    # ── POST ──

    def do_POST(self):
        path = urlparse(self.path).path.rstrip("/")
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length)) if length else {}
        except json.JSONDecodeError:
            return self._send_error("invalid JSON")

        if path == "/speak":
            node = SpatialNode(
                name=body.get("node_name", "Unknown"),
                level=body.get("node_level", "Room"),
                properties=body.get("node_properties", {}),
            )
            message = body.get("message",
                                "Describe yourself to a traveler who has just arrived.")
            try:
                import consciousness
                self._send_json({"response": consciousness.speak(node, message)})
            except ImportError:
                self._send_error("consciousness module requires: pip install anthropic")
            except Exception as exc:
                self._send_error(str(exc))

        elif path == "/puzzle/attempt":
            self._do_puzzle_attempt(body)

        else:
            self._send_error("not found", 404)

    # ── Observe (SSE) ──

    def _do_observe(self, qs: dict) -> None:
        try:
            root, *_ = _rebuild(qs)
        except (ValueError, KeyError) as exc:
            return self._send_error(str(exc))

        node_name = qs.get("node_name", [""])[0]
        target    = (_find_node(root, node_name) if node_name else None) or root

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        depth_map = _build_depth_map(target)

        def handler(node: SpatialNode, event: causality.CausalEvent) -> None:
            d        = depth_map.get(node.id, 0)
            strength = round(_DAMPENING ** d, 4)
            try:
                self._sse_event({
                    "node":     node.name,
                    "level":    node.level,
                    "kind":     event.kind.name,
                    "strength": strength,
                    "depth":    d,
                })
            except (BrokenPipeError, ConnectionResetError):
                pass

        with _OBSERVE_LOCK:
            causality.clear_handlers()
            causality.clear_log()
            causality.register_handler(handler)
            try:
                agent = Agent(name="Observer", danger_threshold=7)
                agent.traverse(target, max_nodes=40)
                self._sse_event({"done": True,
                                 "nodes_visited": len(agent.visited)})
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                causality.clear_handlers()
                causality.clear_log()

    # ── Puzzle ──

    def _do_puzzle(self, qs: dict) -> None:
        try:
            root, seed, *_ = _rebuild(qs)
        except (ValueError, KeyError) as exc:
            return self._send_error(str(exc))

        node_name = qs.get("node_name", [""])[0]
        target    = (_find_node(root, node_name) if node_name else None) or root

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
            seed  = int(body.get("seed",        42))
            depth = int(body.get("depth",        6))
            min_b = int(body.get("min_breadth",  1))
            max_b = int(body.get("max_breadth",  3))
        except (ValueError, TypeError) as exc:
            return self._send_error(str(exc))

        node_name = body.get("node_name", "")
        answer    = body.get("answer", "").strip()
        attempt   = int(body.get("attempt", 1))

        root   = generate_node_hierarchy(seed=seed, max_depth=depth,
                                         min_breadth=min_b, max_breadth=max_b)
        target = (_find_node(root, node_name) if node_name else None) or root

        engine  = PuzzleEngine(seed=seed)
        engine.attach_puzzles(target)
        puzzles = engine.collect_puzzles(target)

        if not puzzles:
            return self._send_error("no puzzle found")

        p       = puzzles[0]
        correct = answer.lower() == p.answer.lower()
        failed  = not correct and attempt >= p.max_attempts
        hint    = (p.hints[attempt - 1]
                   if not correct and not failed and attempt <= len(p.hints)
                   else None)

        self._send_json({
            "correct":        correct,
            "result":         "SOLVED" if correct else ("FAILED" if failed else "UNSOLVED"),
            "hint":           hint,
            "attempt":        attempt,
            "max_attempts":   p.max_attempts,
            "correct_answer": p.answer if failed else None,
        })


# ── Server ─────────────────────────────────────────────────────────────────

class _ThreadedServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


def run(host: str = "127.0.0.1", port: int = 8080) -> None:
    server = _ThreadedServer((host, port), _Handler)
    print(f"Nested Worlds Adventure  →  http://{host}:{port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
