"""Operational guardrails (server/guard.py) — invite gate, rate limit,
cost caps, world-param bounds, kill switches.

Each test runs against a freshly-spawned server on an ephemeral port so
env-var-driven behaviour can be set per test without leaking across cases.
"""
from __future__ import annotations

import base64
import http.client
import json
import os
import socket
import threading
import urllib.error
import urllib.request

import pytest

import persistence
from server import _Handler, _ThreadedServer
from server import guard


# ── Per-test server fixture ─────────────────────────────────────────────────

@pytest.fixture
def srv():
    server = _ThreadedServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    # Reset the in-memory rate limiter and WS connection cap between tests so
    # a noisy run can't spill into the next case's window.
    guard.RATE_LIMITER.reset()
    guard.WS_LIMITER.reset()
    yield f"http://127.0.0.1:{port}", port
    server.shutdown()


def _post(url: str, data: dict, headers: dict | None = None):
    body = json.dumps(data).encode()
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=body, headers=req_headers)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read()), resp.status


def _get_status(url: str, headers: dict | None = None) -> int:
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:
        return exc.code


# ── Invite gate ─────────────────────────────────────────────────────────────

class TestInviteGate:
    def test_no_key_means_open(self, srv, monkeypatch):
        monkeypatch.delenv(guard.BETA_KEY_ENV, raising=False)
        base, _ = srv
        assert _get_status(f"{base}/worlds") == 200

    def test_health_exempt_even_with_key_set(self, srv, monkeypatch):
        # Platform load balancers shouldn't need the secret to probe liveness.
        monkeypatch.setenv(guard.BETA_KEY_ENV, "letmein")
        base, _ = srv
        assert _get_status(f"{base}/health") == 200

    def test_missing_key_rejected(self, srv, monkeypatch):
        monkeypatch.setenv(guard.BETA_KEY_ENV, "letmein")
        base, _ = srv
        assert _get_status(f"{base}/worlds") == 403

    def test_wrong_key_rejected(self, srv, monkeypatch):
        monkeypatch.setenv(guard.BETA_KEY_ENV, "letmein")
        base, _ = srv
        assert _get_status(f"{base}/worlds?key=nope") == 403

    def test_key_via_query_param_accepted(self, srv, monkeypatch):
        monkeypatch.setenv(guard.BETA_KEY_ENV, "letmein")
        base, _ = srv
        assert _get_status(f"{base}/worlds?key=letmein") == 200

    def test_key_via_header_accepted(self, srv, monkeypatch):
        monkeypatch.setenv(guard.BETA_KEY_ENV, "letmein")
        base, _ = srv
        status = _get_status(f"{base}/worlds",
                              headers={guard.BETA_KEY_HEADER: "letmein"})
        assert status == 200


# ── Per-user invite keys ────────────────────────────────────────────────────

class TestPerUserInviteKeys:
    """Per-user keys must work alongside the shared env key without
    disabling either mechanism. These tests cover the four states the
    auth function actually sees: no creds, valid shared key, valid
    per-user key, revoked per-user key."""

    @pytest.fixture(autouse=True)
    def _clear_touch_cache(self):
        # The 5-minute touch throttle persists across tests in the same
        # process — reset it so each case sees a clean cache.
        guard._touch_cache.clear()

    def test_active_per_user_key_accepted(self, srv, monkeypatch):
        # No shared env key — only the per-user table is configured.
        monkeypatch.delenv(guard.BETA_KEY_ENV, raising=False)
        persistence.mint_invite_key("k_alice", "Alice")
        base, _ = srv
        assert _get_status(f"{base}/worlds?key=k_alice") == 200

    def test_revoked_per_user_key_rejected(self, srv, monkeypatch):
        monkeypatch.delenv(guard.BETA_KEY_ENV, raising=False)
        persistence.mint_invite_key("k_alice", "Alice")
        persistence.revoke_invite_key("k_alice")
        base, _ = srv
        # After revocation only inactive rows exist — gate is no longer
        # "active" and the server reverts to open. To keep the gate up
        # we add another active row.
        persistence.mint_invite_key("k_bob", "Bob")
        assert _get_status(f"{base}/worlds?key=k_alice") == 403

    def test_unknown_key_rejected_when_per_user_gate_active(self, srv, monkeypatch):
        monkeypatch.delenv(guard.BETA_KEY_ENV, raising=False)
        persistence.mint_invite_key("k_alice", "Alice")
        base, _ = srv
        assert _get_status(f"{base}/worlds?key=k_nope") == 403

    def test_per_user_key_via_header_accepted(self, srv, monkeypatch):
        monkeypatch.delenv(guard.BETA_KEY_ENV, raising=False)
        persistence.mint_invite_key("k_alice", "Alice")
        base, _ = srv
        status = _get_status(f"{base}/worlds",
                              headers={guard.BETA_KEY_HEADER: "k_alice"})
        assert status == 200

    def test_shared_and_per_user_keys_both_valid(self, srv, monkeypatch):
        # Mixed mode: env key is set AND per-user keys exist. Either
        # should authorize independently — operators may run the cohort
        # on per-user keys while keeping a shared key for ops scripts.
        monkeypatch.setenv(guard.BETA_KEY_ENV, "shared-secret")
        persistence.mint_invite_key("k_alice", "Alice")
        base, _ = srv
        assert _get_status(f"{base}/worlds?key=shared-secret") == 200
        assert _get_status(f"{base}/worlds?key=k_alice") == 200
        assert _get_status(f"{base}/worlds?key=neither") == 403

    def test_unit_check_invite_key_touches_last_used(self, monkeypatch):
        # Verifies the touch path actually updates the row — guards
        # against a future refactor that breaks the admin CLI's
        # "is Alice still active" signal.
        monkeypatch.delenv(guard.BETA_KEY_ENV, raising=False)
        persistence.mint_invite_key("k_alice", "Alice")
        assert guard.check_invite_key(
            {guard.BETA_KEY_HEADER: "k_alice"}, {}
        ) is True
        row = persistence.lookup_invite_key("k_alice")
        assert row is not None and row["last_used_at"] is not None

    def test_unit_invite_gate_active_reflects_db(self, monkeypatch):
        # With no env key and no per-user rows the gate is open.
        monkeypatch.delenv(guard.BETA_KEY_ENV, raising=False)
        assert guard.invite_gate_active() is False
        # Mint a row — gate flips active.
        persistence.mint_invite_key("k_alice", "Alice")
        assert guard.invite_gate_active() is True


# ── World-parameter bounds ──────────────────────────────────────────────────

class TestWorldBounds:
    def test_runaway_depth_rejected(self, srv):
        base, _ = srv
        assert _get_status(f"{base}/world?depth=99") == 400

    def test_runaway_breadth_rejected(self, srv):
        base, _ = srv
        assert _get_status(f"{base}/world?max_breadth=20") == 400

    def test_min_breadth_above_max_rejected(self, srv):
        base, _ = srv
        assert _get_status(f"{base}/world?min_breadth=4&max_breadth=2") == 400

    def test_in_range_accepted(self, srv):
        base, _ = srv
        assert _get_status(f"{base}/world?depth=4&max_breadth=3") == 200

    def test_unit_validate_rejects_runaway(self):
        with pytest.raises(ValueError):
            guard.validate_world_params({"depth": 9999})

    def test_unit_validate_accepts_defaults(self):
        # Default values must always satisfy the bounds, otherwise legacy
        # callers without explicit params would 400.
        guard.validate_world_params({})


# ── AI kill switch ──────────────────────────────────────────────────────────

class TestAIKillSwitch:
    def test_speak_returns_quiet_when_disabled(self, srv, monkeypatch):
        monkeypatch.setenv(guard.DISABLE_AI_ENV, "1")
        base, _ = srv
        data, status = _post(f"{base}/speak",
                              {"node_name": "X", "message": "hi"})
        assert status == 200
        assert data["response"] == guard.QUIET_RESPONSE

    def test_agent_voice_returns_quiet_when_disabled(self, srv, monkeypatch):
        monkeypatch.setenv(guard.DISABLE_AI_ENV, "1")
        base, _ = srv
        data, status = _post(f"{base}/agent/voice",
                              {"agent_name": "Scout", "node_name": "X",
                               "message": "hi"})
        assert status == 200
        assert data["response"] == guard.QUIET_RESPONSE

    def test_image_returns_disabled_when_image_killed(self, srv, monkeypatch):
        monkeypatch.setenv(guard.DISABLE_IMAGES_ENV, "1")
        base, _ = srv
        data, status = _post(f"{base}/image",
                              {"node_id": "x", "node_name": "X"})
        assert status == 200
        assert data["url"] is None
        assert "disabled" in data["error"]


# ── Daily cost caps ─────────────────────────────────────────────────────────

class TestCostCap:
    def test_anthropic_cap_blocks_speak(self, srv, monkeypatch):
        # Cap of zero → first call already over budget; speak returns the
        # fallback without calling Anthropic.
        monkeypatch.setenv(guard.ANTHROPIC_CAP_ENV, "0")
        base, _ = srv
        data, status = _post(f"{base}/speak", {"node_name": "X", "message": "hi"})
        assert status == 200
        assert data["response"] == guard.QUIET_RESPONSE

    def test_anthropic_cap_at_one_blocks_second(self, srv, monkeypatch):
        # First call lands as the lone allowed call; the second is over budget.
        # Both still return 200 — we degrade gracefully rather than 503ing.
        # AI is force-disabled so the first call doesn't try to actually hit
        # Anthropic; we're only testing that the cap sees and counts hits.
        monkeypatch.setenv(guard.ANTHROPIC_CAP_ENV, "1")
        monkeypatch.setenv(guard.DISABLE_AI_ENV, "")  # explicitly enabled

        # Invoke consume_anthropic directly (no fixture needed) to verify
        # the counter logic, since hitting /speak for real needs a network
        # call we don't want in unit tests.
        assert guard.consume_anthropic() is True   # 1st under cap
        assert guard.consume_anthropic() is False  # 2nd over cap

    def test_fal_cap_blocks_image(self, srv, monkeypatch):
        monkeypatch.setenv(guard.FAL_CAP_ENV, "0")
        monkeypatch.setenv("FAL_KEY", "fake-key-so-we-reach-the-cap-check")
        base, _ = srv
        data, status = _post(f"{base}/image",
                              {"node_id": "x", "node_name": "X"})
        assert status == 200
        assert data["url"] is None
        assert "budget" in data["error"]


# ── Per-IP rate limiter ─────────────────────────────────────────────────────

class TestRateLimit:
    def test_burst_blocked_after_cap(self, srv, monkeypatch):
        # Tight limit + AI disabled so each /speak call is a cheap loopback,
        # then the (limit+1)th is rejected with 429.
        monkeypatch.setenv(guard.RATE_LIMIT_ENV, "3")
        monkeypatch.setenv(guard.DISABLE_AI_ENV, "1")
        base, _ = srv
        for _ in range(3):
            _post(f"{base}/speak", {"node_name": "X", "message": "hi"})
        # 4th call: expect 429.
        try:
            _post(f"{base}/speak", {"node_name": "X", "message": "hi"})
        except urllib.error.HTTPError as exc:
            assert exc.code == 429
        else:
            pytest.fail("expected 429 after exceeding rate limit")

    def test_unrelated_endpoint_unaffected_by_limit(self, srv, monkeypatch):
        # Rate-limited paths share a counter, but /worlds isn't on the list
        # so it should always answer regardless of how hot /speak got.
        monkeypatch.setenv(guard.RATE_LIMIT_ENV, "1")
        monkeypatch.setenv(guard.DISABLE_AI_ENV, "1")
        base, _ = srv
        _post(f"{base}/speak", {"node_name": "X", "message": "hi"})
        # Now a /worlds GET should still 200 even though /speak burned its quota.
        assert _get_status(f"{base}/worlds") == 200

    def test_unit_limiter_resets_after_window(self):
        # Drive the limiter directly with synthetic timestamps so we don't
        # have to sleep 60s in CI.
        rl = guard.RateLimiter()
        for _ in range(20):
            assert rl.allow("1.2.3.4", now=0.0) is True
        assert rl.allow("1.2.3.4", now=0.0) is False  # 21st in window — denied
        assert rl.allow("1.2.3.4", now=61.0) is True  # past the window — fresh


# ── Client IP extraction (spoof resistance) ─────────────────────────────────

class TestClientIP:
    def test_default_uses_socket_peer(self, monkeypatch):
        monkeypatch.delenv(guard.TRUST_PROXY_ENV, raising=False)
        ip = guard.client_ip(("9.9.9.9", 12345),
                              {"X-Forwarded-For": "1.1.1.1"})
        assert ip == "9.9.9.9"

    def test_fly_client_ip_preferred_when_trust_proxy(self, monkeypatch):
        # The dedicated, proxy-set header is trusted first — it can't be
        # spoofed because Fly overwrites it with the true client IP.
        monkeypatch.setenv(guard.TRUST_PROXY_ENV, "1")
        ip = guard.client_ip(("127.0.0.1", 12345),
                              {"Fly-Client-IP": "203.0.113.7",
                               "X-Forwarded-For": "1.1.1.1, 203.0.113.7"})
        assert ip == "203.0.113.7"

    def test_rightmost_xff_used_not_leftmost(self, monkeypatch):
        # REGRESSION (P0): the edge proxy APPENDS the real client IP, so the
        # right-most entry is the one it added. Reading the left-most entry
        # (the old behaviour) let a client spoof a fresh rate-limit bucket
        # per request. With no Fly-Client-IP we must fall back to the
        # right-most XFF, never the left-most.
        monkeypatch.setenv(guard.TRUST_PROXY_ENV, "1")
        ip = guard.client_ip(("127.0.0.1", 12345),
                              {"X-Forwarded-For": "9.9.9.9, 203.0.113.7"})
        assert ip == "203.0.113.7"        # appended by the proxy
        assert ip != "9.9.9.9"            # attacker-supplied left-most, ignored

    def test_rotating_spoofed_leftmost_maps_to_same_bucket(self, monkeypatch):
        # Two requests from the same real client that rotate the spoofed
        # left-most XFF must resolve to the SAME rate-limit key.
        monkeypatch.setenv(guard.TRUST_PROXY_ENV, "1")
        a = guard.client_ip(("127.0.0.1", 1),
                            {"X-Forwarded-For": "10.0.0.1, 203.0.113.7"})
        b = guard.client_ip(("127.0.0.1", 2),
                            {"X-Forwarded-For": "10.0.0.2, 203.0.113.7"})
        assert a == b == "203.0.113.7"

    def test_custom_client_ip_header_env(self, monkeypatch):
        monkeypatch.setenv(guard.TRUST_PROXY_ENV, "1")
        monkeypatch.setenv(guard.CLIENT_IP_HEADER_ENV, "CF-Connecting-IP")
        ip = guard.client_ip(("127.0.0.1", 12345),
                              {"CF-Connecting-IP": "198.51.100.5",
                               "X-Forwarded-For": "1.1.1.1"})
        assert ip == "198.51.100.5"


# ── Node-properties clamp (token-cost guard) ────────────────────────────────

class TestNodePropertiesCap:
    def test_non_dict_becomes_empty(self):
        assert guard.cap_properties("not a dict") == {}
        assert guard.cap_properties(None) == {}
        assert guard.cap_properties([1, 2, 3]) == {}

    def test_small_dict_passes_through_as_strings(self):
        out = guard.cap_properties({"danger": 5, "biome": "forest"})
        assert out == {"danger": "5", "biome": "forest"}

    def test_oversized_dict_is_bounded(self):
        # REGRESSION (P0): a giant node_properties blob renders into the
        # uncached system block and inflates token cost ~8x. The clamp must
        # bound both key count and total serialized size regardless of input.
        huge = {f"k{i}": "V" * 5000 for i in range(500)}
        out = guard.cap_properties(huge)
        assert len(out) <= guard._MAX_PROP_KEYS
        serialized = "; ".join(f"{k}={v}" for k, v in out.items())
        assert len(serialized) <= guard._MAX_PROPS_TOTAL + 200  # generous slack
        # A single monster value is also truncated.
        one = guard.cap_properties({"x": "Z" * 100000})
        assert len(next(iter(one.values()))) <= guard._MAX_PROP_VAL_LEN


# ── WebSocket connection cap ─────────────────────────────────────────────────

class TestConnectionLimiter:
    def test_per_ip_cap(self, monkeypatch):
        monkeypatch.setenv(guard.MAX_WS_PER_IP_ENV, "2")
        monkeypatch.setenv(guard.MAX_WS_TOTAL_ENV, "100")
        cl = guard.ConnectionLimiter()
        assert cl.acquire("1.2.3.4") is True
        assert cl.acquire("1.2.3.4") is True
        assert cl.acquire("1.2.3.4") is False   # 3rd from same IP denied
        assert cl.acquire("5.6.7.8") is True     # a different IP still fits

    def test_global_cap(self, monkeypatch):
        monkeypatch.setenv(guard.MAX_WS_TOTAL_ENV, "2")
        monkeypatch.setenv(guard.MAX_WS_PER_IP_ENV, "100")
        cl = guard.ConnectionLimiter()
        assert cl.acquire("a") is True
        assert cl.acquire("b") is True
        assert cl.acquire("c") is False          # global cap hit
        cl.release("a")
        assert cl.acquire("c") is True           # slot freed

    def test_release_below_zero_is_safe(self):
        cl = guard.ConnectionLimiter()
        cl.release("nobody")                      # no crash / negative counts
        assert cl.stats()["total"] == 0


# ── Static UI shell is ungated; data endpoints stay gated (P0) ──────────────

def _ws_upgrade(port: int, path: str, hold: bool = False):
    """Perform a raw WebSocket upgrade; return (status_code, socket_or_None).

    When `hold` is True and the upgrade succeeds (101), the open socket is
    returned so the caller can keep the connection (and its limiter slot)
    alive; otherwise the socket is closed before returning.
    """
    s = socket.create_connection(("127.0.0.1", port), timeout=5)
    wskey = base64.b64encode(os.urandom(16)).decode()
    req = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: 127.0.0.1:{port}\r\n"
        f"Upgrade: websocket\r\nConnection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {wskey}\r\nSec-WebSocket-Version: 13\r\n\r\n"
    )
    s.sendall(req.encode())
    s.settimeout(5)
    line = s.recv(256).decode("latin-1", "replace")
    # Status line looks like "HTTP/1.0 101 Switching Protocols"
    try:
        code = int(line.split(" ", 2)[1])
    except (IndexError, ValueError):
        code = 0
    if code == 101 and hold:
        return code, s
    s.close()
    return code, None


class TestStaticAssetGate:
    """REGRESSION (P0-1): the static UI shell + assets must load WITHOUT the
    invite key so the browser can boot the SPA, which then forwards the key
    on data calls. Data endpoints must stay gated."""

    def test_app_shell_ungated_but_world_gated(self, srv, monkeypatch):
        monkeypatch.setenv(guard.BETA_KEY_ENV, "letmein")
        base, _ = srv
        # Shell loads with no key (browser can't send one on the <script> tag).
        assert _get_status(f"{base}/app") == 200
        # But the data endpoint the SPA fetches is still gated.
        assert _get_status(f"{base}/world?seed=1&depth=3") == 403
        # ...and works once the key is forwarded (as the fixed SPA does).
        assert _get_status(f"{base}/world?seed=1&depth=3&key=letmein") == 200

    def test_is_public_asset_unit(self):
        from server.handlers import Handler
        assert Handler._is_public_asset("/app")
        assert Handler._is_public_asset("/app/assets/index-abc.js")
        assert Handler._is_public_asset("/health")
        assert Handler._is_public_asset("/explorer.js")
        # Data / paid endpoints are never public.
        for p in ("/world", "/ws", "/agent", "/observe", "/puzzle",
                  "/puzzle/attempt", "/speak", "/image", "/agent/voice",
                  "/players", "/history", "/worlds"):
            assert not Handler._is_public_asset(p), p


class TestWebSocketGate:
    def test_ws_gated_without_key(self, srv, monkeypatch):
        # REGRESSION: the WebSocket upgrade must be invite-gated like REST.
        monkeypatch.setenv(guard.BETA_KEY_ENV, "letmein")
        _, port = srv
        code, _ = _ws_upgrade(port, "/ws?seed=42&name=A")
        assert code == 403

    def test_ws_accepts_forwarded_key(self, srv, monkeypatch):
        monkeypatch.setenv(guard.BETA_KEY_ENV, "letmein")
        _, port = srv
        code, sock = _ws_upgrade(port, "/ws?seed=42&name=A&key=letmein", hold=True)
        assert code == 101
        if sock:
            sock.close()

    def test_ws_connection_cap_rejects_overflow(self, srv, monkeypatch):
        # REGRESSION (P1-2): concurrent WS connections are capped; the
        # (cap+1)th upgrade is rejected with 503 instead of spawning an
        # unbounded thread.
        monkeypatch.delenv(guard.BETA_KEY_ENV, raising=False)
        monkeypatch.setenv(guard.MAX_WS_TOTAL_ENV, "1")
        monkeypatch.setenv(guard.MAX_WS_PER_IP_ENV, "50")
        guard.WS_LIMITER.reset()
        _, port = srv
        held = []
        try:
            code1, s1 = _ws_upgrade(port, "/ws?seed=42&name=A", hold=True)
            assert code1 == 101
            held.append(s1)
            # Second connection while the first is held → over the cap.
            code2, _ = _ws_upgrade(port, "/ws?seed=42&name=B")
            assert code2 == 503
        finally:
            for s in held:
                if s:
                    s.close()
