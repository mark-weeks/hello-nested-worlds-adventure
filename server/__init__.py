"""Nested-worlds HTTP/WebSocket server.

Entry points:
    run(host, port)      — start the threaded server
    _Handler             — request handler class (re-exported for tests)
    _ThreadedServer      — server class (re-exported for tests)
"""
from __future__ import annotations

import logging
import signal
import threading
from http.server import HTTPServer
from socketserver import ThreadingMixIn

import persistence
from server import observability
from server.handlers import Handler as _Handler


class _ThreadedServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


def run(host: str = "127.0.0.1", port: int = 8080) -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    observability.setup()
    server = _ThreadedServer((host, port), _Handler)

    # Graceful shutdown on SIGTERM (Fly/Render send it on every deploy/stop).
    # serve_forever() blocks the main thread and shutdown() must be called
    # from another thread, so the handler spins one up. The finally block then
    # closes the listener and checkpoints the WAL so a redeploy doesn't leave a
    # large sidecar to replay on next boot.
    def _graceful(_signum, _frame):
        logging.info("received shutdown signal — draining")
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, _graceful)

    display = f"http://localhost:{port}" if host in ("0.0.0.0", "") else f"http://{host}:{port}"
    print(f"Enfolded  →  {display}")
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
        try:
            persistence.checkpoint()
        except Exception:  # pragma: no cover — shutdown best-effort
            logging.warning("WAL checkpoint on shutdown failed", exc_info=True)


__all__ = ["run", "_Handler", "_ThreadedServer"]
