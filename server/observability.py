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

_community = logging.getLogger("nested_worlds.community")

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
            "Reinstall with: pip install -e ."
        )
        return
    from sentry_sdk.integrations import logging as sentry_logging
    sentry_logging.ignore_logger("nested_worlds.community")
    # The pinned SDK has a separate logs exclusion. Older SDKs still run with
    # logs disabled by this setup, while events/breadcrumbs remain excluded.
    if hasattr(sentry_logging, "ignore_logger_for_sentry_logs"):
        sentry_logging.ignore_logger_for_sentry_logs("nested_worlds.community")
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


# ── Voice outcomes ──────────────────────────────────────────────────────────
# "Failure stays in fiction" governs what a player reads; it never meant the
# operator should not know. Every player-facing voice surface reports each
# answer here: a structured log line for every quiet one (ERROR for the
# failures an operator must fix, so Sentry raises an event; WARNING for limits
# and switches working as designed) and a daily counter, so `python main.py
# voice-health` and scripts/beta_metrics.py can separate "didn't talk" from
# "talked to silence" (2026-11-03 evaluation, finding R3).
#
# The counters reuse `cost_budget`'s (bucket, UTC day) rows under the
# `voice_outcome:` prefix, as the per-user action caps already do. They hold
# no player text, name, credential or node: surface and reason only.

_voice = logging.getLogger("nested_worlds.voice")

VOICE_OUTCOME_PREFIX = "voice_outcome"
VOICE_SURFACES = ("speak", "agent_voice", "intention")
# `screen`: the moderation classifier failed (timeout, error) or gave no usable
# verdict, so shared text was held before the voice was asked. Moderation's
# own budget, per-user cap and disable switch count as `budget`, `action_cap`
# and `disabled`. Content declines are policy, not outages, and are not
# recorded.
# `busy`: no slot under the provider's concurrency limit opened within the
# wait (`runtime.ProviderBusy`), for the voice call or for the moderation
# classify that would have screened it. It is a failure, not a limit. The
# limits are deliberate stops; this is a player turned away for capacity,
# which an operator fixes by raising the limit or the provider's speed.
# And a voice call passes no timeout, so the adapter's own default bounds
# it: 60 s per attempt on the default adapter, retried twice. A hung
# provider then holds each slot for about 3 minutes (at most 5 if it answers
# errors with a retry-after), and `busy` is the only outcome recorded until
# those calls end and count `provider`.
VOICE_FAILURES = ("provider", "db", "unconfigured", "screen", "busy")
VOICE_LIMITS = ("budget", "action_cap", "disabled")
VOICE_REASONS = ("ok",) + VOICE_LIMITS + VOICE_FAILURES


def voice_bucket(surface: str, reason: str) -> str:
    return f"{VOICE_OUTCOME_PREFIX}:{surface}:{reason}"


_VOICE_COUNTER_WAIT_MS = 50


def voice_outcome(surface: str, reason: str,
                  exc: BaseException | None = None) -> None:
    """Record one voice answer. Never raises; waits at most 50 ms on the store.

    `exc` contributes its class name only: a provider message can carry a
    credential or the player's words. A `db` outcome is logged but not
    counted, because the store is what failed and a second write would only
    wait on it again. The counter write uses a short lock wait so a locked
    store (a long transaction, a redact or restore) cannot hold a quiet
    reply for the usual five-second busy timeout; a counter lost that way is
    logged as unavailable, so under heavy write contention the daily counts
    are a lower bound (one review measured 388 of 400 with 8 writer threads).
    """
    if surface not in VOICE_SURFACES or reason not in VOICE_REASONS:
        raise ValueError(f"unknown voice outcome {surface}/{reason}")
    if reason != "ok":
        level = logging.ERROR if reason in VOICE_FAILURES else logging.WARNING
        _voice.log(level, "voice_fallback surface=%s reason=%s exception=%s",
                   surface, reason, type(exc).__name__ if exc is not None else "-")
    if reason == "db":
        return
    try:
        import persistence
        from server import guard
        persistence.increment_cost_calls(voice_bucket(surface, reason),
                                         guard._utc_day(),
                                         wait_ms=_VOICE_COUNTER_WAIT_MS)
    except Exception as err:  # the answer must still reach the player
        _voice.warning("voice_outcome counter unavailable surface=%s reason=%s "
                       "exception=%s", surface, reason, type(err).__name__)


def voice_outcome_summary(days: int = 1) -> dict[str, dict[str, dict[str, int]]]:
    """``{day: {surface: {reason: count}}}`` for the last `days` UTC days, today included."""
    import datetime

    import persistence
    from server import guard
    today = datetime.date.fromisoformat(guard._utc_day())
    since = (today - datetime.timedelta(days=max(1, int(days)) - 1)).isoformat()
    summary: dict[str, dict[str, dict[str, int]]] = {}
    for bucket, day, calls in persistence.cost_rows(VOICE_OUTCOME_PREFIX + ":", since):
        _, surface, reason = bucket.split(":", 2)
        summary.setdefault(day, {}).setdefault(surface, {})[reason] = calls
    return summary


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


def community_failure(path: str, exc: BaseException) -> None:
    """Local diagnostic only: no exception message, frames, body, identity or query."""
    route = path.rstrip('/')
    if route not in {'/ideas/list', '/ideas/detail', '/ideas/search',
                     '/ideas/submit', '/ideas/vote', '/ideas/withdraw'}:
        route = '/ideas/*'
    _community.error('ideas_request_failed route=%s exception=%s',
                     route, type(exc).__name__, exc_info=False)
