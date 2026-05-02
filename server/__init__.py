"""Nested-worlds HTTP/WebSocket server.

Entry points:
    run(host, port)      — start the threaded server
    _Handler             — request handler class (re-exported for tests)
    _ThreadedServer      — server class (re-exported for tests)
"""
from __future__ import annotations

import logging
from http.server import HTTPServer
from socketserver import ThreadingMixIn

from server.handlers import Handler as _Handler


class _ThreadedServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


def run(host: str = "127.0.0.1", port: int = 8080) -> None:
    logging.basicConfig(level=logging.WARNING,
                        format="%(asctime)s %(levelname)s %(message)s")
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


__all__ = ["run", "_Handler", "_ThreadedServer"]
