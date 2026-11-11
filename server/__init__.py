"""Nested-worlds HTTP/WebSocket server.

Entry points:
    run(host, port)      — start the threaded server
    _Handler             — request handler class (re-exported for tests)
    _ThreadedServer      — server class (re-exported for tests)
"""
from __future__ import annotations

import logging
import signal
import sys
import threading
from http.server import HTTPServer
from socketserver import TCPServer, ThreadingMixIn

import persistence
from server import guard, observability, websocket
from server.handlers import Handler as _Handler


# Seconds a client should wait before retrying a saturated process.
# Delta-seconds form (RFC 9110). Fixed so a full server answers the same way
# on every deploy; the cap itself is the tunable.
_BUSY_RETRY_AFTER = "2"
_BUSY_BODY = b'{"error":"server busy"}'


class _HandlerSlots:
    """In-flight handler threads for one listening server.

    The count is taken before the handler thread starts and released when
    that thread exits, so an open WebSocket holds a slot for the session.
    The cap is read on each attempt so an operator change applies without
    restarting the accept loop.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._inflight = 0

    def try_acquire(self) -> bool:
        cap = guard.max_handler_threads()
        with self._lock:
            if self._inflight >= cap:
                return False
            self._inflight += 1
            return True

    def release(self) -> None:
        with self._lock:
            if self._inflight:
                self._inflight -= 1


def _refuse_saturated(request, client_address) -> None:
    """Answer 503 without taking a handler thread or reading the request.

    The write is non-blocking: a peer that will not read must not stall the
    accept loop. The kernel buffer usually takes this small response; if it
    does not, the socket is closed and the client retries.
    """
    # Log before the write. The client can read this 503 and move on as
    # soon as the bytes are queued, and a test that captured only around
    # that read missed the line when the thread was preempted in between.
    logging.info(
        "refusing connection from %s: handler threads full",
        observability.hash_ip(str(client_address[0])),
    )
    body = _BUSY_BODY
    message = (
        "HTTP/1.1 503 Service Unavailable\r\n"
        "Content-Type: application/json\r\n"
        f"Retry-After: {_BUSY_RETRY_AFTER}\r\n"
        "Connection: close\r\n"
        "Cache-Control: no-store\r\n"
        "X-Content-Type-Options: nosniff\r\n"
        f"Content-Length: {len(body)}\r\n"
        "\r\n"
    ).encode("ascii") + body
    try:
        request.setblocking(False)
        request.sendall(message)
    except OSError:
        pass
    # /health is not exempt. This runs before the request is read, so a
    # path exception would have to read first and could be stalled here.
    # A full cap should fail a health check; the response-write timeout is
    # what stops a silent reader from making that failure permanent.


class _ThreadedServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    # Python 3.11 defaults to five waiting connections. An invited cohort can
    # exceed that in one burst before handlers start, causing TCP resets rather
    # than an HTTP response. This backlog is separate from the handler-thread
    # cap and from the guarded WebSocket cap.
    request_queue_size = 64

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._handler_slots = _HandlerSlots()

    def process_request(self, request, client_address):
        if not self._handler_slots.try_acquire():
            _refuse_saturated(request, client_address)
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self._handler_slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._handler_slots.release()

    def server_bind(self):
        # HTTPServer resolves a display hostname with getfqdn on bind. We use the
        # bound address instead, so unavailable reverse DNS cannot stall startup.
        TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[:2]


def model_banner() -> list[str]:
    """Operator lines for the resolved provider and model. No credentials."""
    from consciousness.model_check import check_model_configuration

    labels = {
        "node": "Node voice model",
        "inhabitant": "Inhabitant voice model",
        "intent": "Intention model",
        "moderation": "Moderation model",
    }
    report = check_model_configuration()
    return [
        f"{labels[task.task]:<25}→  {task.provider} {task.display_model} ({task.source})"
        for task in report.tasks
    ]


def _refuse_newer_schema_readonly() -> None:
    """Exit before any migration when the chronicle is newer than this binary.

    Read-only. A missing database is not an error: the first successful
    boot creates it. This must run before ``init_db`` so a config typo
    cannot apply a pending migration and then strand the rollback.
    """
    applied = persistence.read_applied_schema_version()
    known = persistence.known_schema_version()
    if applied is not None and applied > known:
        raise persistence.SchemaTooNewError(
            persistence.schema_too_new_message(applied, known))


def _start_model_spend_retention(*, interval_seconds: float = 60.0,
                                 prune=None) -> tuple[threading.Event, threading.Thread]:
    """Prune private accounting while idle, including an all-off restart."""
    if prune is None:
        from persistence.model_spend import prune_expired
        prune = prune_expired
    stopped = threading.Event()
    logger = logging.getLogger("nested_worlds.model_spend")

    def cleanup():
        while not stopped.is_set():
            try:
                prune()
            except Exception as exc:
                # Database messages and traceback locals may carry private
                # accounting metadata. A later tick retries the cleanup.
                logger.warning("model accounting retention unavailable (%s)",
                               type(exc).__name__)
            if stopped.wait(interval_seconds):
                break

    worker = threading.Thread(target=cleanup, name="model-spend-retention", daemon=True)
    worker.start()
    return stopped, worker


def run(host: str = "127.0.0.1", port: int = 8080) -> None:
    # Schema and configuration before any migration. A release that ships
    # the next migration and a bad seed or model id must exit with the
    # chronicle still on the previous schema, so a same-schema rollback
    # can still boot. Migrations are forward-only.
    try:
        _refuse_newer_schema_readonly()
    except persistence.SchemaTooNewError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
    # Freeze external-call permissions before migrations, observability,
    # workers, or the listener. Merely adding a key cannot activate a route.
    from consciousness import model_policy
    try:
        policy = model_policy.initialize()
    except model_policy.ModelPolicyError:
        print("error: model policy configuration is invalid", file=sys.stderr)
        raise SystemExit(1) from None
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    observability.setup()
    # Validate the world boundary before accepting traffic or starting the
    # heartbeat. A typo here must fail the deploy, not leave a healthy-looking
    # process whose first player request returns 500.
    hosted_seed = guard.canonical_seed()
    # Refuse a blank, unknown, or unusable provider or model on any of the
    # four text tasks, a missing SDK for a task's provider, or a voice or
    # image cap that is not an integer or is negative, before the port
    # opens. A typo must fail the boot, not the first shared-text
    # moderation call. Two valid caps that disagree log one warning and
    # enforce the lower integer: a leftover legacy secret must not
    # crash-loop a restart. Soft model problems log one warning. This does
    # not make a live call. A provider that is not configured still boots:
    # the world answers in fiction until a key is present.
    if policy is None:
        from consciousness.model_check import enforce_model_configuration
        enforce_model_configuration()
    # Controlled configurations were validated by initialize(). Disabled
    # routes deliberately need neither SDKs nor implicit provider/model ids.
    budget_warning = guard.budget_configuration_warning_line()
    if budget_warning:
        logging.getLogger("nested_worlds.guard").warning("%s", budget_warning)
    budget_line = guard.budget_configuration_line()
    if budget_line:
        raise SystemExit(budget_line)
    # Legacy cache advice resolves both voice defaults, even when they are
    # disabled. Controlled routes are described by the offline policy report.
    if policy is None:
        try:
            import consciousness
            consciousness.warn_if_cache_ineffective()
        except ImportError:
            pass
    try:
        persistence.init_db()
    except persistence.SchemaTooNewError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
    server = _ThreadedServer((host, port), _Handler)

    # The world heartbeat: ambient agent life that runs whether or not
    # anyone is connected. Disable with NESTED_WORLDS_HEARTBEAT=0.
    from server import heartbeat
    heartbeat_stop = None
    if heartbeat.enabled():
        heartbeat_stop = heartbeat.start()
    # The causal pump: fires due hops of staged cascades so consequences
    # travel outward over time. Disable with NESTED_WORLDS_CAUSAL_PUMP=0.
    pump_stop = None
    if heartbeat.pump_enabled():
        pump_stop = heartbeat.start_pump()

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
    if hosted_seed is None:
        print("World hosting            →  local multi-world mode")
    else:
        print(f"Shared canonical world   →  seed {hosted_seed}")
    if policy is None:
        for line in model_banner():
            print(line)
    else:
        status = "configured" if policy.enabled_routes else "all external routes disabled"
        print(f"Model policy             →  {status}")
    print(f"Multiplayer WebSocket   →  ws://localhost:{port}/ws")
    if host == "127.0.0.1":
        print("For network access: restart with --host 0.0.0.0")
    else:
        print(f"Share this URL with beta testers: {display}")
    print("Press Ctrl+C to stop.")
    retention = None
    try:
        if policy is not None:
            retention = _start_model_spend_retention()
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if retention is not None:
            stopped, worker = retention
            stopped.set()
            # SQLite waits at most five seconds for its write lock. Bound
            # shutdown too; an unfinished daemon exits with the process.
            worker.join(timeout=6.0)
            if worker.is_alive():
                logging.getLogger("nested_worlds.model_spend").warning(
                    "model accounting retention worker is still stopping")
        if heartbeat_stop is not None:
            heartbeat_stop.set()
        if pump_stop is not None:
            pump_stop.set()
        websocket.stop_credential_sweep()
        server.server_close()
        try:
            persistence.checkpoint()
        except Exception:  # pragma: no cover — shutdown best-effort
            logging.warning("WAL checkpoint on shutdown failed", exc_info=True)


__all__ = ["run", "_Handler", "_ThreadedServer"]
