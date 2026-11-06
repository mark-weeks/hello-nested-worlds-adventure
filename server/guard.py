"""Operational guardrails for the public beta.

Six pieces wired into `server/handlers.py`:

  1. `check_invite_key`   — per-user invite-key gate (the `invite_keys` table),
                            applied to every request including the WebSocket
                            upgrade, and re-checked on an open socket's frames
                            (`ws_session_authorized`). There is no shared key:
                            every credential is individually minted, named, and
                            revocable, so a gated session is always a known,
                            unique player. The gate latches closed once any
                            credential was ever issued.
  2. `RateLimiter`        — per-IP fixed-window limiter for the AI / image /
                            puzzle-attempt endpoints.
  3. `consume_anthropic`  — daily voice-call cap, shared by every text provider,
                            persisted in SQLite under the neutral ``voice`` key.
  4. `consume_fal`        — daily image-call cap, persisted under ``image``.
  5. `ai_disabled`        — env kill switch for `/speak` and `/agent/voice`.
  6. `images_disabled`    — env kill switch for `/image`.

Plus `world_seed` and `validate_world_params`, which confine the public server
to one operator-selected world and clamp the remaining view-depth input so a
bad client can't ask for a 100k-deep tree.

Everything here is read at request time (no caching), so a changed env var
takes effect on the next request without code changes. On Fly the only way
to change one is `fly secrets set` or a deploy, and either restarts the one
machine (every socket reconnects). Counters are stored UTC-day-keyed in
`persistence.cost_budget` and reset naturally at the day boundary.
"""
from __future__ import annotations

import datetime
import hashlib
import logging
import math
import os
import threading
import time
from collections import OrderedDict
from typing import Any, Mapping

import persistence
from multiverse.generator import DEFAULT_WORLD_SEED

_log = logging.getLogger("nested_worlds.guard")

# ── Env vars ────────────────────────────────────────────────────────────────

BETA_KEY_HEADER      = "X-Beta-Key"
BETA_KEY_QUERY       = "key"
# Neutral names are preferred. The legacy vendor names are still accepted.
# When both are set to different integers, the lower one is enforced so a
# rename cannot raise an allowance that is already in effect.
VOICE_CAP_ENV        = "NESTED_WORLDS_VOICE_DAILY_CALLS"
IMAGE_CAP_ENV        = "NESTED_WORLDS_IMAGE_DAILY_CALLS"
ANTHROPIC_CAP_ENV    = "NESTED_WORLDS_ANTHROPIC_DAILY_CALLS"
FAL_CAP_ENV          = "NESTED_WORLDS_FAL_DAILY_CALLS"
# Per-user (per-credential) daily sub-caps. The global caps above bound total
# spend; these bound how much of that budget any single tester can consume, so
# one heavy or careless account can't drain the shared budget and degrade the
# whole cohort to the quiet-fallback string. Enforced only when a credential is
# supplied (i.e. the invite gate is active); local dev with no key is unaffected.
VOICE_PER_USER_CAP_ENV     = "NESTED_WORLDS_VOICE_DAILY_CALLS_PER_USER"
IMAGE_PER_USER_CAP_ENV     = "NESTED_WORLDS_IMAGE_DAILY_CALLS_PER_USER"
ANTHROPIC_PER_USER_CAP_ENV = "NESTED_WORLDS_ANTHROPIC_DAILY_CALLS_PER_USER"
FAL_PER_USER_CAP_ENV       = "NESTED_WORLDS_FAL_DAILY_CALLS_PER_USER"
RATE_LIMIT_ENV       = "NESTED_WORLDS_RATE_LIMIT_PER_MIN"
DISABLE_AI_ENV       = "NESTED_WORLDS_DISABLE_AI"
DISABLE_IMAGES_ENV   = "NESTED_WORLDS_DISABLE_IMAGES"
TRUST_PROXY_ENV      = "NESTED_WORLDS_TRUST_PROXY"
CLIENT_IP_HEADER_ENV = "NESTED_WORLDS_CLIENT_IP_HEADER"
CANONICAL_SEED_ENV    = "NESTED_WORLDS_CANONICAL_SEED"
# Fly (and most edge proxies) set a dedicated, non-spoofable header with the
# real connecting IP. On Fly that's `Fly-Client-IP`. Prefer it over
# X-Forwarded-For, whose leftmost value is client-controlled.
_DEFAULT_CLIENT_IP_HEADER = "Fly-Client-IP"

_DEFAULT_ANTHROPIC_DAILY = 500
_DEFAULT_FAL_DAILY       = 200
# Default per-user sub-caps sit at ~30% of the global default, so any single
# account tops out well before it can exhaust the cohort's daily budget.
_DEFAULT_ANTHROPIC_PER_USER = 150
_DEFAULT_FAL_PER_USER       = 60
_DEFAULT_RATE_PER_MIN    = 20
DEFAULT_CANONICAL_SEED   = DEFAULT_WORLD_SEED

# New calls write the neutral keys. Migration 0030 moves rows already
# stored under the legacy keys onto these names, summing a day that has
# both, so the spent allowance is preserved. A leftover legacy row is
# still added at check time and is not written again by a request.
VOICE_BUCKET      = "voice"
IMAGE_BUCKET      = "image"
ANTHROPIC_BUCKET  = "anthropic"
FAL_BUCKET        = "fal_ai"
_LEGACY_BUCKET = {
    VOICE_BUCKET: ANTHROPIC_BUCKET,
    IMAGE_BUCKET: FAL_BUCKET,
}
# Moderation classify calls get their OWN budget line (ADR-004 §2): they must
# never drain the voice budget. The moderation bucket stays "moderation".
# When a moderation budget or per-user cap is spent, shared text is held —
# it is not published. Redaction stays the backstop for text that did land.
MODERATION_BUCKET = "moderation"
MODERATION_CAP_ENV = "NESTED_WORLDS_MODERATION_DAILY_CALLS"
_DEFAULT_MODERATION_DAILY = 2000
# Per-credential classify calls. 60 is 3% of the shared 2000, so one account
# cannot empty the cohort budget. Most lines never call the model. This is a
# starting ceiling to measure, not a tuned rate. 0 refuses credentialed calls.
MODERATION_PER_USER_CAP_ENV = "NESTED_WORLDS_MODERATION_DAILY_CALLS_PER_USER"
_DEFAULT_MODERATION_PER_USER = 60
# Shared-text submissions that enter screen() with a credential (speak,
# chat, ideas, a published profile, a puzzle guess). Name checks do not
# use this counter. A local block does not spend it. It is charged before
# a local clean return, so a clean line still spends it. Resets at UTC
# midnight with the other cost_budget rows.
# 600 is about twenty minutes at the WebSocket chat ceiling (0.5/s) and a
# long day of hand-typed lines. Starting flood ceiling; raise or lower it
# from the logs (outcome=user_cap) once real sessions are measured.
MODERATION_ACTIONS_BUCKET = "moderation_actions"
MODERATION_ACTIONS_PER_USER_ENV = "NESTED_WORLDS_MODERATION_ACTIONS_PER_USER"
_DEFAULT_MODERATION_ACTIONS_PER_USER = 600
# Model-calling actions (voice, inhabitant voice, intention, and a moderation
# classify). Separate from the voice allowance and its NESTED_WORLDS_VOICE_*
# / legacy NESTED_WORLDS_ANTHROPIC_* settings. 200 sits above the existing 150 voice
# sub-cap so ordinary voice still binds there, with room for a few classifies
# and intentions. Starting value to measure. No credential stays uncapped
# here; the global voice cap still applies.
MODEL_ACTIONS_BUCKET = "model_actions"
MODEL_ACTIONS_PER_USER_ENV = "NESTED_WORLDS_MODEL_ACTIONS_PER_USER"
_DEFAULT_MODEL_ACTIONS_PER_USER = 200


# ── World-gen parameter bounds ──────────────────────────────────────────────

# 11 is the depth of the full hierarchy; nobody needs more. Depth is the
# only shape input a request controls: breadth comes from the generator's
# canonical BREADTH_BY_LEVEL profile (the same seed must be the same world
# for every participant), which bounds the worst-case full-depth tree at
# ~12k nodes by construction — the old depth×breadth amplification vector
# (client-supplied breadth 5 at depth 11 → ~12M nodes, an OOM on the beta
# VM) no longer exists. Legacy min_breadth/max_breadth params are accepted
# for URL compatibility and ignored.
MAX_DEPTH        = 11
MIN_DEPTH        = 1


def canonical_seed() -> int | None:
    """Return the one world hosted by this server.

    Production fails closed to the curated launch seed 382 when the setting is
    absent. An empty
    value (or ``off``/``none``) explicitly enables multi-world mode for local
    development and tests; the browser never exposes that mode. Choosing a
    different launch world is therefore an operator action, not a player
    input.
    """
    raw = os.environ.get(CANONICAL_SEED_ENV)
    if raw is None:
        return DEFAULT_CANONICAL_SEED
    raw = raw.strip()
    if raw.lower() in {"", "off", "none"}:
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"invalid {CANONICAL_SEED_ENV}: {raw!r}") from exc


def world_seed(raw: Any = None) -> int:
    """Resolve a request seed without allowing a parallel public world.

    A missing seed selects the configured canonical world. Supplying that
    same seed remains accepted for compatibility with older clients. Any
    other seed is rejected before a world can be materialized, queried, or
    joined. In explicitly enabled local multi-world mode, the historical
    default and arbitrary integer seeds remain available.
    """
    configured = canonical_seed()
    if raw is None or str(raw).strip() == "":
        return configured if configured is not None else DEFAULT_CANONICAL_SEED
    try:
        requested = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid seed: {raw!r}") from exc
    if configured is not None and requested != configured:
        raise ValueError(
            f"this server hosts one shared world (seed {configured})")
    return requested


# ── Node-properties clamp (token-cost guard) ────────────────────────────────
# `/speak` renders node_properties into the *uncached* dynamic system block
# ("k=v; k=v; ..."), billed at full input price on every call. The `message`
# is already capped at 1024 chars, but a request could smuggle an arbitrarily
# large `node_properties` dict (bounded only by the 64 KB body cap) and inflate
# one call's input ~8x. Clamp key/value count and lengths so the rendered
# properties block can't balloon the prompt.

_MAX_PROP_KEYS     = 24
_MAX_PROP_KEY_LEN  = 48
_MAX_PROP_VAL_LEN  = 128
_MAX_PROPS_TOTAL   = 1200   # chars across all rendered "k=v" pairs


def cap_properties(props: Any) -> dict:
    """Return a size-bounded copy of `props` safe to render into a prompt.

    Non-dicts become `{}`. Keys/values are coerced to strings and truncated;
    the whole thing is capped in both key count and total serialized length.
    """
    if not isinstance(props, dict):
        return {}
    out: dict[str, str] = {}
    total = 0
    for k, v in props.items():
        if len(out) >= _MAX_PROP_KEYS:
            break
        ks = str(k)[:_MAX_PROP_KEY_LEN]
        vs = str(v)[:_MAX_PROP_VAL_LEN]
        total += len(ks) + len(vs) + 2  # "k=v; "
        if total > _MAX_PROPS_TOTAL:
            break
        out[ks] = vs
    return out


def validate_world_params(params: Mapping[str, Any]) -> None:
    """Raise ValueError if the depth input is out of range.

    Called from `_build_world` so every endpoint that rebuilds the world
    tree inherits the same clamp without each handler repeating the check.
    Depth is the only client-controllable shape input; breadth is the
    generator's canonical profile (legacy breadth params are ignored, not
    rejected — old clients still send them).
    """
    raw = params.get("depth", 6)
    try:
        v = int(raw)
    except (TypeError, ValueError):
        raise ValueError(f"invalid depth: {raw!r}")
    if v < MIN_DEPTH or v > MAX_DEPTH:
        raise ValueError(
            f"depth must be between {MIN_DEPTH} and {MAX_DEPTH} (got {v})")


# ── Invite key ──────────────────────────────────────────────────────────────

# Cap how often we touch the DB to update last_used_at — without this, every
# /speak call would fire an UPDATE just to advance the timestamp by a second.
# 5 minutes is short enough to feel live in the admin CLI and long enough to
# stay off the hot path.
_TOUCH_INTERVAL_SEC = 300.0
# Only keys that resolved to a live invite row ever enter the cache, so its
# size tracks the minted-key count — bounded in practice, but a long-lived
# process should not carry every key ever seen. Prune expired entries once
# the cache outgrows this; entries older than the interval are dead weight
# (the next touch would fire the UPDATE regardless).
_TOUCH_CACHE_MAX = 1024
_touch_cache: dict[str, float] = {}
_touch_lock = threading.Lock()


def _maybe_touch(key: str) -> None:
    """Update last_used_at on a per-key, time-throttled basis.

    Race-tolerant: if two threads pass the check simultaneously, both fire
    one UPDATE and the cache converges on the same timestamp — no harm done.
    """
    now = time.time()
    with _touch_lock:
        last = _touch_cache.get(key, 0.0)
        if now - last < _TOUCH_INTERVAL_SEC:
            return
        _touch_cache[key] = now
        if len(_touch_cache) > _TOUCH_CACHE_MAX:
            cutoff = now - _TOUCH_INTERVAL_SEC
            for stale in [k for k, t in _touch_cache.items() if t < cutoff]:
                del _touch_cache[stale]
    persistence.touch_invite_key(key)


def _per_user_key_match(supplied: str) -> bool:
    """Return True iff `supplied` matches an active per-user invite row.

    Updates last_used_at opportunistically (throttled). Always returns
    False for empty strings so callers don't accidentally authorize on a
    missing key.
    """
    if not supplied:
        return False
    row = persistence.lookup_invite_key(supplied)
    if row is None:
        return False
    _maybe_touch(supplied)
    return True


def registered_name(supplied: str) -> str | None:
    """The registered display name for a per-user invite key, else None.

    A per-user key carries a name chosen (and made unique) at registration —
    so it is the player's authoritative identity: unique, non-anonymous, and
    unimpersonatable. The server uses it in preference to any client-supplied
    name (ADR-004 §7). Returns None for an unknown key or no key — the only
    keyless path is ungated local dev, which falls back to the normalized
    client name.
    """
    if not supplied:
        return None
    row = persistence.lookup_invite_key(supplied)
    return row["name"] if row else None


def invite_gate_active() -> bool:
    """True once any credential has ever been issued; True on any error.

    The gate latches. Minting the first per-user key, or creating the first
    registration invite, closes it, and nothing reopens it: revoking every
    key, cancelling every invite, or a redeemed invite whose key was later
    revoked all leave the world closed. Every request then needs a live
    per-user credential. Only a database where nothing was ever issued
    (pure local dev and most tests) leaves the gate off; that is the one
    path on which a session can be nameless, and it never touches real
    play.

    Fails closed: if the latch cannot be read, the gate is treated as
    active and the error is logged by exception class only. The class name
    carries no credential, digest, or player name.
    """
    try:
        return persistence.credentials_ever_issued()
    except Exception as exc:  # noqa: BLE001 — any failure must close the gate
        _log.error("invite gate check failed (%s); treating the gate as "
                   "closed", type(exc).__name__)
        return True


def supplied_key(headers: Mapping[str, str], qs: Mapping[str, list[str]]) -> str:
    """Return the raw beta credential this request presented (header or query),
    stripped; "" if none. Used to key the per-user spend sub-cap."""
    supplied = headers.get(BETA_KEY_HEADER) or headers.get(BETA_KEY_HEADER.lower())
    if not supplied:
        vals = qs.get(BETA_KEY_QUERY)
        supplied = vals[0] if vals else ""
    return (supplied or "").strip()


def check_invite_key(headers: Mapping[str, str], qs: Mapping[str, list[str]]) -> bool:
    """Return True iff this request carries a valid per-user invite credential.

    Authorization is the per-user `invite_keys` table only — each key is
    operator-minted, carries a unique registered name, and is individually
    revocable. There is no shared key: with the gate active, every authorized
    session is a known, named player (ADR-004 §7, no anonymous gameplay). If
    an active row matches, the request is authorized and the row's
    `last_used_at` is bumped (throttled).

    The gate is open only when no credential was ever issued (pure local
    dev / tests); see `invite_gate_active`. Accepts either the `X-Beta-Key`
    header (preferred) or a `?key=` query param so the WebSocket connector —
    which can't easily set headers in the browser — can still authenticate.
    """
    supplied = supplied_key(headers, qs)

    if _per_user_key_match(supplied):
        return True

    # The gate blocks once any credential was ever issued, and when that
    # cannot be read.
    return not invite_gate_active()


# How often an open socket re-checks its authorization on frames that write
# nothing (protocol pings and pongs, application pings, bad JSON, unknown
# types, a move or chat its throttle refused). A move or chat that passes its
# throttle is always re-checked fresh before it writes or broadcasts, so a
# revoked credential never writes again. This interval bounds the rest: a
# revoked session is closed at its first complete frame once this long has
# passed since its last check, and a frame flood costs at most one database
# read per interval instead of one per frame. A socket that sends nothing,
# or holds a frame open, is not left to its frames: the credential sweep
# (`WS_SWEEP_INTERVAL_SEC`) re-checks it on the server's own schedule.
WS_REAUTH_INTERVAL_SEC = 2.0

# The credential sweep (`server.websocket`): one thread per process re-checks
# every open socket whose last successful check, by a frame or by the sweep,
# is this many seconds old, whether or not the client sends anything. A
# socket whose credential was revoked, rotated away or sanctioned, or a
# keyless socket once the gate has latched, stops receiving data frames at
# that check and is closed with 1008, so a client that only listens stays
# subscribed for about this long (plus one database read), not until the
# 60 s idle timeout. 5 s keeps that well inside beta checklist G5's 1 minute.
# The cost is at most one read per open socket per interval, never one per
# broadcast: less than `WS_REAUTH_INTERVAL_SEC` already allows a talking
# socket, and nothing for a socket whose own frames re-checked it within the
# interval. Read on every pass, so tests can shorten it.
WS_SWEEP_INTERVAL_SEC = 5.0


def ws_session_authorized(ws_key: str, credentialed: bool) -> bool:
    """Whether an open WebSocket may still act. One database read.

    The upgrade is authorized once, but a session can outlive its
    credential. The message loop calls this before a move or chat writes
    anything, and at most once per `WS_REAUTH_INTERVAL_SEC` on every other
    client frame, control frames and ignored frames included, since any
    frame keeps the session (and its room broadcasts) alive. The credential
    sweep calls it for a socket not checked for `WS_SWEEP_INTERVAL_SEC`:

      * `credentialed` (the socket upgraded with a live per-user key): it
        stays authorized only while that key is live. A revoked or rotated
        key fails, whatever the gate state.
      * otherwise (keyless, or an unrecognized key on an open dev server):
        it stays authorized only while the gate is open, so the first
        credential ever issued ends every keyless session.

    Fails closed: a read error ends the session. Errors are logged by
    exception class only, never with the key.
    """
    if credentialed:
        try:
            return persistence.lookup_invite_key(ws_key) is not None
        except Exception as exc:  # noqa: BLE001 — any failure ends the session
            _log.error("WebSocket credential re-check failed (%s); closing "
                       "the session", type(exc).__name__)
            return False
    return not invite_gate_active()


# ── Client IP (for rate limiting) ───────────────────────────────────────────

def _header_ci(headers: Mapping[str, str], name: str) -> str | None:
    """Case-insensitive header lookup (http.client.HTTPMessage is already CI,
    but plain dicts in tests are not)."""
    return headers.get(name) or headers.get(name.lower()) or headers.get(name.upper())


def client_ip(client_address: tuple, headers: Mapping[str, str]) -> str:
    """Best-effort per-request IP for rate-limiting bookkeeping.

    By default we use the socket peer (`client_address[0]`). When the server
    is fronted by a reverse proxy (Fly, Render, Cloudflare, etc.) the peer is
    the proxy's loopback address and every user collapses into one bucket, so
    set `NESTED_WORLDS_TRUST_PROXY=1` to read a proxy-supplied client IP.

    We must NOT read the *leftmost* `X-Forwarded-For` value: the edge proxy
    *appends* the real client IP to whatever the client already sent, so the
    leftmost entry is fully client-controlled and lets an attacker mint a
    fresh rate-limit bucket per request (spoof bypass). Instead:

      1. Prefer a dedicated, proxy-set header (`Fly-Client-IP` by default,
         overridable via `NESTED_WORLDS_CLIENT_IP_HEADER`). Fly overwrites
         this with the true connecting IP; a client-supplied value is
         discarded, so it can't be spoofed.
      2. Fall back to the *right-most* `X-Forwarded-For` entry — the hop the
         trusted proxy directly in front of us appended — never the leftmost.
      3. Fall back to the socket peer.
    """
    if os.environ.get(TRUST_PROXY_ENV, "").strip() == "1":
        header_name = os.environ.get(CLIENT_IP_HEADER_ENV, "").strip() or _DEFAULT_CLIENT_IP_HEADER
        trusted = _header_ci(headers, header_name)
        if trusted and trusted.strip():
            return trusted.strip()
        xff = _header_ci(headers, "X-Forwarded-For")
        if xff:
            parts = [p.strip() for p in xff.split(",") if p.strip()]
            if parts:
                return parts[-1]  # right-most = appended by the trusted proxy
    return client_address[0] if client_address else "unknown"


# ── Per-IP rate limiter ─────────────────────────────────────────────────────

class RateLimiter:
    """Fixed-window per-IP limiter.

    Trades the smoothness of a token bucket for two-line semantics: each IP
    gets `_limit_per_min()` calls per rolling 60-second window. Window state
    lives in process memory so it's per-instance, which is fine for the
    single-VPS beta the README describes.
    """

    def __init__(self, env_var: str = RATE_LIMIT_ENV,
                 default: int = _DEFAULT_RATE_PER_MIN) -> None:
        self._counts: dict[str, tuple[float, int]] = {}
        self._lock = threading.Lock()
        self._env_var = env_var
        self._default = default

    def _limit_per_min(self) -> int:
        raw = os.environ.get(self._env_var, "").strip()
        if not raw:
            return self._default
        try:
            v = int(raw)
        except ValueError:
            return self._default
        return max(1, v)

    # Every distinct client IP leaves a window entry behind forever without
    # eviction — a slow scan of the IPv4 space would grow the dict without
    # bound. Once it outgrows this, expired windows (>=60s old, which the
    # next `allow` for that key would reset anyway) are dropped in one pass.
    _COUNTS_MAX = 4096

    def allow(self, key: str, *, now: float | None = None) -> bool:
        """Return True if `key` is allowed this call; record it on success."""
        import time
        now = now if now is not None else time.monotonic()
        limit = self._limit_per_min()
        with self._lock:
            window_start, count = self._counts.get(key, (now, 0))
            if now - window_start >= 60.0:
                window_start, count = now, 0
            count += 1
            self._counts[key] = (window_start, count)
            if len(self._counts) > self._COUNTS_MAX:
                for stale in [k for k, (ws, _) in self._counts.items()
                              if now - ws >= 60.0 and k != key]:
                    del self._counts[stale]
            return count <= limit

    def reset(self) -> None:
        with self._lock:
            self._counts.clear()


# Module-level singleton — handlers import and call `.allow()` per request.
RATE_LIMITER = RateLimiter()

# Read-side limiter for the expensive GETs (`/world` rebuilds and serializes
# the full canonical tree per hit; `/agent` runs an FSM traversal). These cost
# no API budget, so the cost caps never bound them — without their own
# limiter, they were the one unthrottled way to pin the single beta VM's CPU.
# The ceiling is deliberately higher than the POST limiter's: normal play
# fetches `/world` on navigation, so a gameplay-shaped browsing pace must
# never trip it.
READ_RATE_LIMIT_ENV       = "NESTED_WORLDS_RATE_LIMIT_GET_PER_MIN"
_DEFAULT_READ_RATE_PER_MIN = 120
READ_RATE_LIMITER = RateLimiter(READ_RATE_LIMIT_ENV, _DEFAULT_READ_RATE_PER_MIN)

# Failed Ideas credential checks have a separate budget: unauthenticated traffic
# must not spend the shared gameplay read allowance or community write quota.
IDEAS_AUTH_FAILURE_RATE_LIMIT_ENV = "NESTED_WORLDS_IDEAS_AUTH_FAILURES_PER_MIN"
_DEFAULT_IDEAS_AUTH_FAILURES_PER_MIN = 120
IDEAS_AUTH_FAILURE_RATE_LIMITER = RateLimiter(
    IDEAS_AUTH_FAILURE_RATE_LIMIT_ENV, _DEFAULT_IDEAS_AUTH_FAILURES_PER_MIN)


# ── HTTP read budget and handler-thread cap ──────────────────────────────────
#
# These bound the accept path itself. The WebSocket caps below apply only
# after a request line and headers have already been read and the upgrade
# has been accepted, so they do not stop a client that never finishes sending.

HTTP_READ_TIMEOUT_ENV = "NESTED_WORLDS_HTTP_READ_TIMEOUT"
# Seconds to finish the request line, headers, and body. Long enough for a
# 64 KB JSON body on a slow link; short enough that a stalled client cannot
# park a handler thread for the life of the process.
_DEFAULT_HTTP_READ_TIMEOUT = 30.0

HTTP_WRITE_TIMEOUT_ENV = "NESTED_WORLDS_HTTP_WRITE_TIMEOUT"
# Seconds one response send may block when the peer stops reading. This is
# not a budget for the whole response: each send waits at most this long,
# and a client that keeps accepting bytes continues. 30s matches the read
# budget — long enough for a congested link or a brief pause, short enough
# that a silent reader cannot hold a handler slot until restart.
_DEFAULT_HTTP_WRITE_TIMEOUT = 30.0

MAX_HANDLER_THREADS_ENV = "NESTED_WORLDS_MAX_HANDLER_THREADS"
# One thread per in-flight HTTP request and per open WebSocket. 160 sits
# above the WebSocket default (128) and the committed proxy hard limit (150),
# so those existing limits still shed first, while a direct listener cannot
# grow threads without a bound.
_DEFAULT_MAX_HANDLER_THREADS = 160


def _seconds_setting(env_var: str, default: float) -> float:
    """Positive finite seconds from `env_var`, or `default`.

    Zero must not mean "wait forever". Read at use time, like the other
    operational limits.
    """
    raw = os.environ.get(env_var, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    if not math.isfinite(value) or value <= 0:
        return default
    return value


def http_read_timeout() -> float:
    """Seconds allowed to read one plain-HTTP request, or the default."""
    return _seconds_setting(HTTP_READ_TIMEOUT_ENV, _DEFAULT_HTTP_READ_TIMEOUT)


def http_write_timeout() -> float:
    """Seconds one plain-HTTP response send may block, or the default.

    A stall timer on each send, not a deadline for the whole body. The
    WebSocket upgrade replaces it by calling ``settimeout`` on the socket.
    """
    return _seconds_setting(HTTP_WRITE_TIMEOUT_ENV, _DEFAULT_HTTP_WRITE_TIMEOUT)


def max_handler_threads() -> int:
    """Concurrent handler-thread cap, or the default when the env is unusable.

    The cap counts every thread inside a request, including a WebSocket
    session after upgrade. Values below 1 and non-integers fall back.
    """
    raw = os.environ.get(MAX_HANDLER_THREADS_ENV, "").strip()
    if not raw:
        return _DEFAULT_MAX_HANDLER_THREADS
    try:
        value = int(raw)
    except ValueError:
        return _DEFAULT_MAX_HANDLER_THREADS
    if value < 1:
        return _DEFAULT_MAX_HANDLER_THREADS
    return value


# ── WebSocket connection cap ─────────────────────────────────────────────────

MAX_WS_TOTAL_ENV   = "NESTED_WORLDS_MAX_WS_CONNECTIONS"
MAX_WS_PER_IP_ENV  = "NESTED_WORLDS_MAX_WS_PER_IP"
_DEFAULT_MAX_WS_TOTAL  = 128
_DEFAULT_MAX_WS_PER_IP = 8


class ConnectionLimiter:
    """Bound concurrent WebSocket connections, globally and per-IP.

    Without this, `/ws` (a long-lived thread per connection with a 60s idle
    timeout) is unbounded — a reconnect-loop attacker opens thousands of
    sockets and exhausts threads/memory on a small VM. Counters are in-memory
    per-process, which matches the single-machine beta.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._total = 0
        self._per_ip: dict[str, int] = {}

    @staticmethod
    def _cap(env_var: str, default: int) -> int:
        raw = os.environ.get(env_var, "").strip()
        if not raw:
            return default
        try:
            return max(1, int(raw))
        except ValueError:
            return default

    def acquire(self, ip: str) -> bool:
        """Reserve a slot for `ip`; return False if a cap is already hit."""
        total_cap = self._cap(MAX_WS_TOTAL_ENV, _DEFAULT_MAX_WS_TOTAL)
        per_ip_cap = self._cap(MAX_WS_PER_IP_ENV, _DEFAULT_MAX_WS_PER_IP)
        with self._lock:
            if self._total >= total_cap:
                return False
            if self._per_ip.get(ip, 0) >= per_ip_cap:
                return False
            self._total += 1
            self._per_ip[ip] = self._per_ip.get(ip, 0) + 1
            return True

    def release(self, ip: str) -> None:
        with self._lock:
            if self._total > 0:
                self._total -= 1
            remaining = self._per_ip.get(ip, 0) - 1
            if remaining <= 0:
                self._per_ip.pop(ip, None)
            else:
                self._per_ip[ip] = remaining

    def stats(self) -> dict:
        with self._lock:
            return {"total": self._total, "unique_ips": len(self._per_ip)}

    def reset(self) -> None:
        with self._lock:
            self._total = 0
            self._per_ip.clear()


WS_LIMITER = ConnectionLimiter()


class TokenBucket:
    """Message throttle (continuous refill).

    ConnectionLimiter bounds how many sockets exist; this bounds what a
    player can DO. Every WS move/chat writes a permanent chronicle row and
    broadcasts to every player in the room, so an unthrottled connection is
    an unbounded chronicle writer and a broadcast amplifier. One bucket per
    message type, per credential for keyed sockets (`CredentialBuckets`) and
    per connection for keyless dev sockets; excess messages are dropped
    silently (an abuse guard, not UX — no human clicks 3 times a second for
    a sustained minute). Not thread-safe on its own: a per-connection bucket
    is read from its socket's one thread, and a shared one is only touched
    under `CredentialBuckets`' lock."""

    def __init__(self, rate: float, burst: int):
        self.rate = float(rate)      # tokens replenished per second
        self.burst = float(burst)    # bucket capacity (initial allowance)
        self.tokens = float(burst)
        self.last = time.monotonic()

    def allow(self) -> bool:
        now = time.monotonic()
        self.tokens = min(self.burst,
                          self.tokens + (now - self.last) * self.rate)
        self.last = now
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


# A burst covers real exploration (a flurry of map clicks); the sustained
# rate is what caps a flood.
WS_MOVE_RATE, WS_MOVE_BURST = 3.0, 20
WS_CHAT_RATE, WS_CHAT_BURST = 0.5, 5


def credential_identity(user_key: str) -> str:
    """The in-memory identity of a credential: sha256 hex, first 16 chars.

    The same scheme as the cost-ledger buckets and chronicle actor identity,
    so the plaintext key is never a dictionary key in process memory.
    """
    return hashlib.sha256(user_key.encode("utf-8")).hexdigest()[:16]


class CredentialBuckets:
    """One shared `TokenBucket` per credential identity, lock-protected.

    Several sockets may carry the same credential (8 per IP by default,
    `MAX_WS_PER_IP_ENV`, and more across IPs); per-socket buckets would give
    one player that many times the chat and move rate. Every socket on a
    credential draws from the same bucket here.

    Bounded: once the registry outgrows `max_entries`, buckets that have
    refilled to their burst are dropped first (indistinguishable from a
    fresh bucket, so nothing is forgiven), then the least recently used.
    """

    def __init__(self, rate: float, burst: int, max_entries: int = 4096):
        self._rate = rate
        self._burst = burst
        self._max = max_entries
        self._lock = threading.Lock()
        self._buckets: OrderedDict[str, TokenBucket] = OrderedDict()

    def allow(self, identity: str) -> bool:
        with self._lock:
            bucket = self._buckets.get(identity)
            if bucket is None:
                bucket = TokenBucket(self._rate, self._burst)
                self._buckets[identity] = bucket
            else:
                self._buckets.move_to_end(identity)
            allowed = bucket.allow()
            if len(self._buckets) > self._max:
                self._evict(keep=identity)
            return allowed

    def _evict(self, keep: str) -> None:
        now = time.monotonic()
        refill = self._burst / self._rate if self._rate > 0 else float("inf")
        for ident in [i for i, b in self._buckets.items()
                      if i != keep and now - b.last >= refill]:
            del self._buckets[ident]
        while len(self._buckets) > self._max:
            oldest = next(iter(self._buckets))
            if oldest == keep:
                break
            del self._buckets[oldest]

    def handle(self, identity: str) -> "_SharedBucket":
        """A per-socket view with the same `.allow()` as a `TokenBucket`."""
        return _SharedBucket(self, identity)

    def __len__(self) -> int:
        with self._lock:
            return len(self._buckets)

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()


class _SharedBucket:
    __slots__ = ("_registry", "_identity")

    def __init__(self, registry: CredentialBuckets, identity: str):
        self._registry = registry
        self._identity = identity

    def allow(self) -> bool:
        return self._registry.allow(self._identity)


WS_MOVE_BUCKETS = CredentialBuckets(WS_MOVE_RATE, WS_MOVE_BURST)
WS_CHAT_BUCKETS = CredentialBuckets(WS_CHAT_RATE, WS_CHAT_BURST)


def ws_message_buckets(credential: str | None):
    """(move, chat) throttles for one socket.

    A socket that upgraded with a live per-user credential shares both
    buckets with every other socket on that credential. A keyless dev
    socket (`credential` empty or None) gets its own pair.
    """
    if credential:
        identity = credential_identity(credential)
        return WS_MOVE_BUCKETS.handle(identity), WS_CHAT_BUCKETS.handle(identity)
    return (TokenBucket(WS_MOVE_RATE, WS_MOVE_BURST),
            TokenBucket(WS_CHAT_RATE, WS_CHAT_BURST))


# ── Daily cost caps ─────────────────────────────────────────────────────────

def _utc_day() -> str:
    return datetime.datetime.utcnow().strftime("%Y-%m-%d")


def _cap_for(env_var: str, default: int) -> int:
    raw = os.environ.get(env_var, "").strip()
    if not raw:
        return default
    try:
        v = int(raw)
    except ValueError:
        return default
    return max(0, v)


def _read_cap(env_var: str) -> tuple[str, int | None]:
    """``(kind, value)`` for one cap variable.

    ``absent`` and ``blank`` carry no number. ``blank`` is a present value
    that is empty or whitespace, and it does not override another setting.
    ``invalid`` is present and not an integer. ``negative`` is an integer
    below zero. ``value`` is a non-negative integer. The raw text is not
    returned: a pasted credential must not land in an operator line.
    """
    if env_var not in os.environ:
        return "absent", None
    raw = os.environ[env_var].strip()
    if not raw:
        return "blank", None
    try:
        value = int(raw)
    except ValueError:
        return "invalid", None
    if value < 0:
        return "negative", None
    return "value", value


class _BudgetCap(tuple):
    """``(cap, hard problems)`` plus disagreement warnings.

    Unpacking stays ``cap, problems``. ``problems`` are startup errors.
    ``warnings`` are two valid integers that differ: the lower cap is
    enforced and the server keeps running.
    """

    warnings: tuple[str, ...]

    def __new__(cls, cap: int, hard: tuple[str, ...],
                warnings: tuple[str, ...] = ()):
        self = tuple.__new__(cls, (cap, hard))
        self.warnings = warnings
        return self


def resolve_budget_cap(neutral_env: str, legacy_env: str, default: int) -> _BudgetCap:
    """The cap to enforce, hard problems, and disagreement warnings.

    Neither name set, or both blank, uses ``default``. One valid integer
    wins. Both valid and equal use that integer. Both valid and different
    use the lower integer, so setting the neutral name cannot raise an
    allowance the legacy name still holds. That disagreement is a warning,
    not a startup failure: a live server must not crash-loop because a
    legacy secret is still set. A non-integer or a negative value refuses
    the allowance (cap 0) instead of falling through to the default or to
    the other name, which could be higher. ``0`` is a valid cap and
    refuses every call. The raw text of a bad value is not included.
    """
    opinions: list[tuple[str, int]] = []
    problems: list[str] = []
    for env_var in (neutral_env, legacy_env):
        kind, value = _read_cap(env_var)
        if kind == "invalid":
            problems.append(f"{env_var} is not an integer")
        elif kind == "negative":
            problems.append(f"{env_var} is negative")
        elif kind == "value" and value is not None:
            opinions.append((env_var, value))
    if problems:
        return _BudgetCap(0, tuple(problems))
    if not opinions:
        return _BudgetCap(default, ())
    if len(opinions) == 1:
        return _BudgetCap(opinions[0][1], ())
    if opinions[0][1] == opinions[1][1]:
        return _BudgetCap(opinions[0][1], ())
    low = min(opinions[0][1], opinions[1][1])
    warning = (
        f"{opinions[0][0]}={opinions[0][1]} and {opinions[1][0]}={opinions[1][1]} "
        f"disagree; the lower cap {low} is enforced"
    )
    return _BudgetCap(low, (), (warning,))


_BUDGET_PAIRS = (
    (VOICE_CAP_ENV, ANTHROPIC_CAP_ENV, _DEFAULT_ANTHROPIC_DAILY),
    (VOICE_PER_USER_CAP_ENV, ANTHROPIC_PER_USER_CAP_ENV, _DEFAULT_ANTHROPIC_PER_USER),
    (IMAGE_CAP_ENV, FAL_CAP_ENV, _DEFAULT_FAL_DAILY),
    (IMAGE_PER_USER_CAP_ENV, FAL_PER_USER_CAP_ENV, _DEFAULT_FAL_PER_USER),
)


def budget_configuration_problems() -> tuple[str, ...]:
    """Hard problems in the voice and image caps. Empty when they resolve.

    A disagreement between two valid integers is not included. That is a
    warning from ``budget_configuration_warnings``.
    """
    found: list[str] = []
    for neutral, legacy, default in _BUDGET_PAIRS:
        found.extend(resolve_budget_cap(neutral, legacy, default)[1])
    return tuple(found)


def budget_configuration_warnings() -> tuple[str, ...]:
    """Valid caps that disagree. The lower integer is what a request uses."""
    found: list[str] = []
    for neutral, legacy, default in _BUDGET_PAIRS:
        found.extend(resolve_budget_cap(neutral, legacy, default).warnings)
    return tuple(found)


def budget_configuration_line() -> str | None:
    """One startup-error line, or None when every cap is a valid integer.

    A disagreement is not an error. ``budget_configuration_warning_line``
    carries that, and the lower cap is what a request enforces.
    """
    problems = budget_configuration_problems()
    if not problems:
        return None
    return "Budget configuration: " + "; ".join(problems)


def budget_configuration_warning_line() -> str | None:
    """One warning when two valid caps disagree, or None."""
    warnings = budget_configuration_warnings()
    if not warnings:
        return None
    return "Budget warning: " + "; ".join(warnings)


def _legacy_bucket(bucket: str) -> str | None:
    """The pre-rename key that still counts toward ``bucket``, if any."""
    for neutral, legacy in _LEGACY_BUCKET.items():
        if bucket == neutral:
            return legacy
        prefix = neutral + ":u:"
        if bucket.startswith(prefix):
            return legacy + bucket[len(neutral):]
    return None


def effective_calls(bucket: str, day: str | None = None) -> int:
    """Calls already spent for ``bucket`` today, including a leftover legacy key.

    Migration 0030 moves existing legacy rows onto ``bucket``. A leftover
    is still added here. New increments land on ``bucket`` only, so the
    same calls are not written a second time.
    """
    day = day or _utc_day()
    total = persistence.get_cost_calls(bucket, day)
    legacy = _legacy_bucket(bucket)
    if legacy:
        total += persistence.get_cost_calls(legacy, day)
    return total


def _consume(bucket: str, env_var: str, default: int) -> bool:
    """Increment today's counter for `bucket`; return True iff still under cap.

    Increment-then-check (rather than peek-then-increment) makes the check
    atomic at the DB level via INSERT ON CONFLICT DO UPDATE. Means a couple
    of concurrent requests can briefly observe the same pre-increment state
    and both tip the counter just past the cap; that's fine for a beta cap
    whose purpose is bounding worst-case spend, not exact accounting.
    ``env_var`` and ``default`` are the single-variable form used by
    moderation. Voice and image pass an already resolved cap through
    ``_consume_capped``.
    """
    cap = _cap_for(env_var, default)
    return _consume_capped(bucket, cap)


def _consume_capped(bucket: str, cap: int) -> bool:
    if cap <= 0:
        return False
    day = _utc_day()
    new_count = persistence.increment_cost_calls(bucket, day)
    legacy = _legacy_bucket(bucket)
    if legacy:
        new_count += persistence.get_cost_calls(legacy, day)
    return new_count <= cap


def _user_bucket(base_bucket: str, user_key: str) -> str:
    """Namespaced per-user counter bucket, keyed by a hash of the credential.

    Hashing keeps the raw invite key out of the `cost_budget` table while still
    giving each credential its own stable daily counter.
    """
    digest = hashlib.sha256(user_key.encode("utf-8")).hexdigest()[:16]
    return f"{base_bucket}:u:{digest}"


def _consume_per_user(base_bucket: str, env_var: str, default: int,
                      user_key: str | None) -> bool:
    """Increment + check the per-user counter. Open when no credential/cap.

    Returns True (allowed) when no credential was supplied — the global cap is
    then the only bound, preserving local-dev and existing-test behaviour where
    no key flows through. Otherwise increments the per-user bucket and returns
    whether it is still within the per-user cap.
    """
    if not user_key:
        return True
    cap = _cap_for(env_var, default)
    return _consume_capped(_user_bucket(base_bucket, user_key), cap)


def _consume_allowance(user_key: str | None, *,
                             neutral_user: str, legacy_user: str, default_user: int,
                             neutral_global: str, legacy_global: str, default_global: int,
                             bucket: str) -> bool:
    """Per-user gate first, then the shared counter. Both read neutral-or-legacy caps."""
    if user_key:
        per_user, _problems = resolve_budget_cap(neutral_user, legacy_user, default_user)
        if not _consume_capped(_user_bucket(bucket, user_key), per_user):
            return False
    global_cap, _problems = resolve_budget_cap(neutral_global, legacy_global, default_global)
    return _consume_capped(bucket, global_cap)


def consume_anthropic(user_key: str | None = None) -> bool:
    """Reserve one voice call against the global cap and, if a credential
    is supplied, the caller's per-user cap. Both must be under budget.

    The allowance is one bucket for every text provider. Node voice,
    inhabitant voice, and intention share it. Switching or mixing providers
    does not open a second allowance. The persisted key is ``voice``.
    Calls already stored under ``anthropic`` for this UTC day still count.
    ``NESTED_WORLDS_VOICE_DAILY_CALLS`` is the neutral cap. The legacy
    ``NESTED_WORLDS_ANTHROPIC_DAILY_CALLS`` is still accepted. When both
    name different integers, the lower one is enforced and startup logs a
    warning instead of exiting. A non-integer or a negative cap refuses
    the call and fails startup.

    Order matters: the per-user sub-cap is checked FIRST, and the shared
    global counter is only incremented once that gate passes. If we charged
    the global budget first (the old order), an account that has already
    blown its per-user cap would keep bumping the shared counter on every
    rejected attempt — draining the cohort's budget and degrading everyone to
    the quiet fallback, which is exactly what the sub-cap exists to prevent.
    A credential-less caller (local dev / legacy) passes the per-user gate
    trivially and is bounded by the global cap alone, unchanged.
    """
    return _consume_allowance(
        user_key,
        neutral_user=VOICE_PER_USER_CAP_ENV,
        legacy_user=ANTHROPIC_PER_USER_CAP_ENV,
        default_user=_DEFAULT_ANTHROPIC_PER_USER,
        neutral_global=VOICE_CAP_ENV,
        legacy_global=ANTHROPIC_CAP_ENV,
        default_global=_DEFAULT_ANTHROPIC_DAILY,
        bucket=VOICE_BUCKET,
    )


# The neutral name. ``consume_anthropic`` stays the function ``generate``
# calls so an existing patch of that name still intercepts the charge.
consume_voice = consume_anthropic


def consume_moderation_action(user_key: str | None = None) -> bool:
    """Reserve one moderation-triggering action against the per-user cap.

    Open when no credential is supplied (local dev and existing tests). A
    False result holds shared text; it does not charge the voice budget.
    """
    return _consume_per_user(
        MODERATION_ACTIONS_BUCKET, MODERATION_ACTIONS_PER_USER_ENV,
        _DEFAULT_MODERATION_ACTIONS_PER_USER, user_key)


def consume_model_action(user_key: str | None = None) -> bool:
    """Reserve one model-calling action against the per-user cap.

    Callers go through ``consciousness.runtime.reserve_model_action``, which
    normalizes an empty credential and is what ``generate`` charges. Does not
    touch the voice allowance. Open when no credential is supplied. A False
    result must not publish shared text and must not call the model.
    """
    return _consume_per_user(
        MODEL_ACTIONS_BUCKET, MODEL_ACTIONS_PER_USER_ENV,
        _DEFAULT_MODEL_ACTIONS_PER_USER, user_key)


def moderation_reserve(user_key: str | None = None) -> str:
    """Reserve one classify call. ``ok``, ``user_cap``, or ``budget``.

    The per-user gate is checked first so a spent personal cap does not
    increment the shared moderation counter. Separate from the voice budget.
    """
    if not _consume_per_user(MODERATION_BUCKET, MODERATION_PER_USER_CAP_ENV,
                             _DEFAULT_MODERATION_PER_USER, user_key):
        return "user_cap"
    if not _consume(MODERATION_BUCKET, MODERATION_CAP_ENV,
                    _DEFAULT_MODERATION_DAILY):
        return "budget"
    return "ok"


def consume_fal(user_key: str | None = None) -> bool:
    """Reserve one image call against the per-user then global caps.

    The persisted key is ``image``. Calls already stored under ``fal_ai``
    for this UTC day still count. ``NESTED_WORLDS_IMAGE_DAILY_CALLS`` is
    the neutral cap. ``NESTED_WORLDS_FAL_DAILY_CALLS`` is still accepted.
    When both name different integers, the lower one is enforced.

    Same ordering rationale as `consume_anthropic`: the per-user gate is
    evaluated before the shared global counter is touched, so a single
    account's over-quota attempts can't exhaust the cohort's image budget.
    """
    return _consume_allowance(
        user_key,
        neutral_user=IMAGE_PER_USER_CAP_ENV,
        legacy_user=FAL_PER_USER_CAP_ENV,
        default_user=_DEFAULT_FAL_PER_USER,
        neutral_global=IMAGE_CAP_ENV,
        legacy_global=FAL_CAP_ENV,
        default_global=_DEFAULT_FAL_DAILY,
        bucket=IMAGE_BUCKET,
    )


consume_image = consume_fal


# ── Kill switches ───────────────────────────────────────────────────────────

def ai_disabled() -> bool:
    return os.environ.get(DISABLE_AI_ENV, "").strip() == "1"


def images_disabled() -> bool:
    return os.environ.get(DISABLE_IMAGES_ENV, "").strip() == "1"


# ── Friendly fallback strings ───────────────────────────────────────────────

QUIET_RESPONSE = "The worlds are quiet today. Try again tomorrow."
