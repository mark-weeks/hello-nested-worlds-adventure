"""Operational guardrails for the public beta.

Six pieces wired into `server/handlers.py`:

  1. `check_invite_key`   — shared-secret gate read from env, applied to every
                            request including the WebSocket upgrade.
  2. `RateLimiter`        — per-IP fixed-window limiter for the AI / image /
                            puzzle-attempt endpoints.
  3. `consume_anthropic`  — daily call cap on Anthropic, persisted in SQLite.
  4. `consume_fal`        — daily call cap on fal.ai, persisted in SQLite.
  5. `ai_disabled`        — env kill switch for `/speak` and `/agent/voice`.
  6. `images_disabled`    — env kill switch for `/image`.

Plus `validate_world_params`, which clamps the four generator inputs the
server accepts from request bodies / query strings so a bad client can't
ask for a 100k-deep tree.

Everything here is read at request time (no caching), so toggling an env
var on the host is immediate. Counters are stored UTC-day-keyed in
`persistence.cost_budget` and reset naturally at the day boundary.
"""
from __future__ import annotations

import datetime
import os
import threading
import time
from typing import Any, Mapping

import persistence


# ── Env vars ────────────────────────────────────────────────────────────────

BETA_KEY_ENV         = "NESTED_WORLDS_BETA_KEY"
BETA_KEY_HEADER      = "X-Beta-Key"
BETA_KEY_QUERY       = "key"
ANTHROPIC_CAP_ENV    = "NESTED_WORLDS_ANTHROPIC_DAILY_CALLS"
FAL_CAP_ENV          = "NESTED_WORLDS_FAL_DAILY_CALLS"
RATE_LIMIT_ENV       = "NESTED_WORLDS_RATE_LIMIT_PER_MIN"
DISABLE_AI_ENV       = "NESTED_WORLDS_DISABLE_AI"
DISABLE_IMAGES_ENV   = "NESTED_WORLDS_DISABLE_IMAGES"
TRUST_PROXY_ENV      = "NESTED_WORLDS_TRUST_PROXY"
CLIENT_IP_HEADER_ENV = "NESTED_WORLDS_CLIENT_IP_HEADER"
# Fly (and most edge proxies) set a dedicated, non-spoofable header with the
# real connecting IP. On Fly that's `Fly-Client-IP`. Prefer it over
# X-Forwarded-For, whose leftmost value is client-controlled.
_DEFAULT_CLIENT_IP_HEADER = "Fly-Client-IP"

_DEFAULT_ANTHROPIC_DAILY = 500
_DEFAULT_FAL_DAILY       = 200
_DEFAULT_RATE_PER_MIN    = 20

ANTHROPIC_BUCKET = "anthropic"
FAL_BUCKET       = "fal_ai"


# ── World-gen parameter bounds ──────────────────────────────────────────────

# 11 is the depth of the full hierarchy; nobody needs more. max_breadth=5 keeps
# worst-case node count at 5**11 ≈ 48M which is already absurd, so the realistic
# bounds bite well before that on smaller depths.
MAX_DEPTH        = 11
MAX_BREADTH      = 5
MIN_DEPTH        = 1
MIN_BREADTH_LO   = 1


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
    """Raise ValueError if any of the four generator inputs is out of range.

    Called from `_build_world` so every endpoint that rebuilds the world tree
    inherits the same clamp without each handler repeating the check.
    """
    def _bounded(key: str, default: int, lo: int, hi: int) -> int:
        raw = params.get(key, default)
        try:
            v = int(raw)
        except (TypeError, ValueError):
            raise ValueError(f"invalid {key}: {raw!r}")
        if v < lo or v > hi:
            raise ValueError(f"{key} must be between {lo} and {hi} (got {v})")
        return v

    depth = _bounded("depth",       6, MIN_DEPTH,      MAX_DEPTH)
    min_b = _bounded("min_breadth", 1, MIN_BREADTH_LO, MAX_BREADTH)
    max_b = _bounded("max_breadth", 3, MIN_BREADTH_LO, MAX_BREADTH)
    if min_b > max_b:
        raise ValueError(f"min_breadth ({min_b}) > max_breadth ({max_b})")


# ── Invite key ──────────────────────────────────────────────────────────────

def _expected_key() -> str:
    return os.environ.get(BETA_KEY_ENV, "").strip()


# Cap how often we touch the DB to update last_used_at — without this, every
# /speak call would fire an UPDATE just to advance the timestamp by a second.
# 5 minutes is short enough to feel live in the admin CLI and long enough to
# stay off the hot path.
_TOUCH_INTERVAL_SEC = 300.0
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


def invite_gate_active() -> bool:
    """True when any invite mechanism is configured.

    Shared env key OR at least one active per-user key counts as "gated."
    Tests and pure dev mode (no env key, no DB rows) leave the gate off
    and the server stays open.
    """
    if _expected_key():
        return True
    try:
        return bool(persistence.list_invite_keys())
    except Exception:
        # DB not initialized yet (e.g. fresh checkout, no migrations run);
        # behave as if no per-user keys exist.
        return False


def check_invite_key(headers: Mapping[str, str], qs: Mapping[str, list[str]]) -> bool:
    """Return True iff this request carries a valid beta credential.

    Two mechanisms are consulted in order:
      1. The shared `NESTED_WORLDS_BETA_KEY` env var (legacy, single value).
      2. The per-user `invite_keys` table (operator-minted, individually
         revocable). If any active row matches, the request is authorized
         and the row's `last_used_at` is bumped (throttled).

    The gate is open if both mechanisms are unconfigured (env unset AND no
    active per-user rows). Accepts either the `X-Beta-Key` header
    (preferred) or a `?key=` query param so the WebSocket connector — which
    can't easily set headers in the browser — can still authenticate.
    """
    supplied = headers.get(BETA_KEY_HEADER) or headers.get(BETA_KEY_HEADER.lower())
    if not supplied:
        vals = qs.get(BETA_KEY_QUERY)
        supplied = vals[0] if vals else ""
    supplied = (supplied or "").strip()

    expected = _expected_key()
    if expected and supplied and supplied == expected:
        return True

    if _per_user_key_match(supplied):
        return True

    # Gate only blocks when at least one mechanism is configured.
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

    def __init__(self) -> None:
        self._counts: dict[str, tuple[float, int]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _limit_per_min() -> int:
        raw = os.environ.get(RATE_LIMIT_ENV, "").strip()
        if not raw:
            return _DEFAULT_RATE_PER_MIN
        try:
            v = int(raw)
        except ValueError:
            return _DEFAULT_RATE_PER_MIN
        return max(1, v)

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
            return count <= limit

    def reset(self) -> None:
        with self._lock:
            self._counts.clear()


# Module-level singleton — handlers import and call `.allow()` per request.
RATE_LIMITER = RateLimiter()


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


def _consume(bucket: str, env_var: str, default: int) -> bool:
    """Increment today's counter for `bucket`; return True iff still under cap.

    Increment-then-check (rather than peek-then-increment) makes the check
    atomic at the DB level via INSERT ON CONFLICT DO UPDATE. Means a couple
    of concurrent requests can briefly observe the same pre-increment state
    and both tip the counter just past the cap; that's fine for a beta cap
    whose purpose is bounding worst-case spend, not exact accounting.
    """
    cap = _cap_for(env_var, default)
    if cap <= 0:
        return False
    new_count = persistence.increment_cost_calls(bucket, _utc_day())
    return new_count <= cap


def consume_anthropic() -> bool:
    return _consume(ANTHROPIC_BUCKET, ANTHROPIC_CAP_ENV, _DEFAULT_ANTHROPIC_DAILY)


def consume_fal() -> bool:
    return _consume(FAL_BUCKET, FAL_CAP_ENV, _DEFAULT_FAL_DAILY)


# ── Kill switches ───────────────────────────────────────────────────────────

def ai_disabled() -> bool:
    return os.environ.get(DISABLE_AI_ENV, "").strip() == "1"


def images_disabled() -> bool:
    return os.environ.get(DISABLE_IMAGES_ENV, "").strip() == "1"


# ── Friendly fallback strings ───────────────────────────────────────────────

QUIET_RESPONSE = "The worlds are quiet today. Try again tomorrow."
