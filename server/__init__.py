from __future__ import annotations

import base64
import hashlib
import json
import struct
import threading
import uuid
from dataclasses import dataclass, field
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
_WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


# ── WebSocket protocol ─────────────────────────────────────────────────────

def _ws_recvall(sock, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionResetError("WebSocket connection closed")
        buf.extend(chunk)
    return bytes(buf)


def _ws_recv(sock) -> bytes | None:
    """Return next data-frame payload, b'' for control frames, None on close."""
    header = _ws_recvall(sock, 2)
    b0, b1 = header[0], header[1]
    opcode = b0 & 0x0F
    masked = bool(b1 & 0x80)
    length = b1 & 0x7F
    if length == 126:
        length = struct.unpack(">H", _ws_recvall(sock, 2))[0]
    elif length == 127:
        length = struct.unpack(">Q", _ws_recvall(sock, 8))[0]
    mask_key = _ws_recvall(sock, 4) if masked else b""
    payload = bytearray(_ws_recvall(sock, length))
    if masked:
        for i in range(len(payload)):
            payload[i] ^= mask_key[i % 4]
    if opcode == 0x8:  # close frame
        return None
    if opcode in (0x9, 0xA):  # ping / pong — discard payload
        return b""
    return bytes(payload)


def _ws_send(sock, data: str | bytes) -> None:
    if isinstance(data, str):
        data = data.encode()
    n = len(data)
    if n <= 125:
        frame = bytes([0x81, n]) + data
    elif n <= 65535:
        frame = struct.pack(">BBH", 0x81, 126, n) + data
    else:
        frame = struct.pack(">BBQ", 0x81, 127, n) + data
    sock.sendall(frame)


# ── Multiplayer rooms ──────────────────────────────────────────────────────

@dataclass
class _Player:
    name: str
    seed: int
    current_node: str
    session_id: str
    sock: object
    _lock: threading.Lock = field(default_factory=threading.Lock, compare=False, repr=False)

    def send(self, msg: dict) -> bool:
        try:
            with self._lock:
                _ws_send(self.sock, json.dumps(msg))
            return True
        except OSError:
            return False


@dataclass
class _Room:
    players: dict = field(default_factory=dict)   # session_id → _Player
    lock: threading.Lock = field(default_factory=threading.Lock, compare=False, repr=False)


_rooms: dict[int, _Room] = {}
_rooms_lock = threading.Lock()


def _get_room(seed: int) -> _Room:
    with _rooms_lock:
        if seed not in _rooms:
            _rooms[seed] = _Room()
        return _rooms[seed]


def _broadcast(room: _Room, msg: dict, exclude: str | None = None) -> None:
    with room.lock:
        targets = list(room.players.items())
    failed = []
    for sid, player in targets:
        if sid == exclude:
            continue
        if not player.send(msg):
            failed.append(sid)
    if failed:
        with room.lock:
            for sid in failed:
                room.players.pop(sid, None)


def _room_snapshot(room: _Room) -> list[dict]:
    with room.lock:
        return [{"name": p.name, "node": p.current_node, "session_id": p.session_id}
                for p in room.players.values()]


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

        elif path == "/players":
            try:
                seed = int(param("seed", "42"))
            except ValueError:
                return self._send_error("invalid seed")
            room = _get_room(seed)
            self._send_json({"players": _room_snapshot(room)})

        elif path == "/history":
            try:
                seed = int(param("seed", "42"))
            except ValueError:
                return self._send_error("invalid seed")
            self._send_json({"mutations": persistence.get_mutations(seed)})

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

        elif path == "/ws":
            self._do_ws(qs)

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
        session_id = uuid.uuid4().hex[:8]
        player = _Player(name=name, seed=seed, current_node="", session_id=session_id, sock=sock)

        room = _get_room(seed)
        with room.lock:
            room.players[session_id] = player

        player.send({"type": "welcome", "session_id": session_id,
                     "players": _room_snapshot(room)})
        _broadcast(room, {"type": "player_join", "name": name, "session_id": session_id},
                   exclude=session_id)

        try:
            while True:
                payload = _ws_recv(sock)
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
                    _broadcast(room, {"type": "player_move", "name": name,
                                      "node": node_name, "session_id": session_id},
                               exclude=session_id)
                elif msg_type == "ping":
                    player.send({"type": "pong"})
        except (OSError, ConnectionResetError, BrokenPipeError):
            pass
        finally:
            with room.lock:
                room.players.pop(session_id, None)
            _broadcast(room, {"type": "player_leave", "name": name,
                               "session_id": session_id})

    # ── Observe (SSE) ──

    def _do_observe(self, qs: dict) -> None:
        try:
            root, seed, *_ = _rebuild(qs)
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
                nodes_visited = len(agent.visited)
                self._sse_event({"done": True, "nodes_visited": nodes_visited})
                room = _get_room(seed)
                _broadcast(room, {"type": "agent_done", "node": target.name,
                                   "nodes_visited": nodes_visited})
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

        node_name   = body.get("node_name", "")
        answer      = body.get("answer", "").strip()
        attempt_raw = body.get("attempt", 1)

        root   = generate_node_hierarchy(seed=seed, max_depth=depth,
                                         min_breadth=min_b, max_breadth=max_b)
        target = (_find_node(root, node_name) if node_name else None) or root

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
            room = _get_room(seed)
            _broadcast(room, {"type": "puzzle_solved", "node": effective_node,
                               "puzzle": p.name})

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


# ── Server ─────────────────────────────────────────────────────────────────

class _ThreadedServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


def run(host: str = "127.0.0.1", port: int = 8080) -> None:
    server = _ThreadedServer((host, port), _Handler)
    display = f"http://localhost:{port}" if host in ("0.0.0.0", "") else f"http://{host}:{port}"
    print(f"Nested Worlds Adventure  →  {display}")
    print(f"Multiplayer WebSocket   →  ws://localhost:{port}/ws")
    if host == "127.0.0.1":
        print(f"For network access: restart with --host 0.0.0.0")
    else:
        print(f"Share this URL with beta testers: {display}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
