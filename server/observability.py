"""Operational observability for the hosted server.

Two pieces:

  * `setup()` — called once at server start. If `SENTRY_DSN` is set and
    `sentry_sdk` is installed, initializes Sentry. Otherwise no-op. Logs a
    warning if the DSN is set but the SDK isn't importable, so misconfigured
    environments fail loudly without crashing.

  * `capture_exception()` — called from request handlers' top-level
    try/except. Forwards to Sentry if configured; falls back to
    `_log.exception` so the trace still lands somewhere.

  * `access_log()` — emits one JSON line per request through the standard
    logging module. The IP is truncated SHA-1 hashed so logs don't leak
    raw addresses; ops only need stable bucketing for spotting abusers.

No state lives at module level beyond `_sentry_ready`, so the importability
check runs at most once per process.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from typing import Any

_log    = logging.getLogger("nested_worlds")
_access = logging.getLogger("nested_worlds.access")

_sentry_ready: bool = False


def setup() -> None:
    """Initialize Sentry from env if both the DSN and SDK are available."""
    global _sentry_ready
    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if not dsn:
        return
    try:
        import sentry_sdk
    except ImportError:
        _log.warning(
            "SENTRY_DSN is set but sentry_sdk is not installed. "
            "Run: pip install 'nested-worlds-adventure[sentry]'"
        )
        return
    sentry_sdk.init(
        dsn=dsn,
        traces_sample_rate=0.0,        # spans off by default — beta is small
        send_default_pii=False,        # never include IP, headers, etc.
        environment=os.environ.get("SENTRY_ENVIRONMENT", "production"),
    )
    _sentry_ready = True
    _log.info("Sentry initialized")


def capture_exception(exc: BaseException | None = None) -> None:
    """Forward an exception to Sentry if configured, log the trace otherwise."""
    if _sentry_ready:
        try:
            import sentry_sdk
            sentry_sdk.capture_exception(exc)
            return
        except Exception:  # pragma: no cover — Sentry SDK self-error
            pass
    _log.exception("unhandled request error", exc_info=exc)


def hash_ip(ip: str) -> str:
    """Stable 8-char hash so the access log can bucket abusers without PII."""
    return hashlib.sha1(ip.encode("utf-8")).hexdigest()[:8]


def access_log(method: str, path: str, status: int, *,
               started: float, ip: str, length: int = 0) -> None:
    """Emit a single JSON access log line via the `nested_worlds.access` logger.

    `path` is the path component only — query strings are deliberately
    excluded so the invite key never lands in logs.
    """
    line: dict[str, Any] = {
        "ts":     time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ip_h":   hash_ip(ip),
        "method": method,
        "path":   path,
        "status": status,
        "ms":     int((time.monotonic() - started) * 1000),
        "len":    length,
    }
    _access.info(json.dumps(line))
