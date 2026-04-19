from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from multiverse.generator import generate_node_hierarchy
from multiverse.node import SpatialNode
from agents.agent import Agent
import persistence


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


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # suppress default access log noise
        pass

    def _send_json(self, data: object, status: int = 200) -> None:
        body = json.dumps(data, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, message: str, status: int = 400) -> None:
        self._send_json({"error": message}, status)

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)

        def param(key: str, default: str | None = None) -> str | None:
            vals = qs.get(key)
            return vals[0] if vals else default

        path = parsed.path.rstrip("/")

        if path == "/health":
            self._send_json({"status": "ok"})

        elif path == "/worlds":
            self._send_json(persistence.list_worlds())

        elif path == "/world":
            try:
                seed = int(param("seed", "42"))
                depth = int(param("depth", "5"))
                min_b = int(param("min_breadth", "1"))
                max_b = int(param("max_breadth", "2"))
            except ValueError as exc:
                return self._send_error(str(exc))
            try:
                root = generate_node_hierarchy(seed=seed, max_depth=depth, min_breadth=min_b, max_breadth=max_b)
            except ValueError as exc:
                return self._send_error(str(exc))
            node_count = _count_nodes(root)
            persistence.save_world(seed, node_count, depth, min_b, max_b)
            self._send_json({"seed": seed, "node_count": node_count, "world": _node_to_dict(root)})

        elif path == "/agent":
            try:
                seed = int(param("seed", "42"))
                name = param("name", "Scout")
                threshold = int(param("threshold", "6"))
                max_nodes = int(param("max_nodes", "50"))
            except ValueError as exc:
                return self._send_error(str(exc))
            root = generate_node_hierarchy(seed=seed)
            agent = Agent(name=name, danger_threshold=threshold)
            agent.traverse(root, max_nodes=max_nodes)
            events = [
                {"node": e.node_name, "level": e.level, "state": e.state.name, "action": e.action}
                for e in agent.log
            ]
            run_id = persistence.save_agent_run(name, seed, len(agent.visited), events)
            self._send_json({
                "run_id": run_id,
                "agent": name,
                "seed": seed,
                "nodes_visited": len(agent.visited),
                "events": events,
            })

        else:
            self._send_error("not found", 404)


def run(host: str = "127.0.0.1", port: int = 8080) -> None:
    """Start the HTTP server (blocking)."""
    server = HTTPServer((host, port), _Handler)
    print(f"Nested Worlds Adventure server running at http://{host}:{port}")
    print("Endpoints: /health  /worlds  /world?seed=N  /agent?seed=N")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
