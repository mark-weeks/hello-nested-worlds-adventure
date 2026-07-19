"""Operational guardrails (server/guard.py) — invite gate, rate limit,
cost caps, world-param bounds, kill switches.

Each test runs against a freshly-spawned server on an ephemeral port so
env-var-driven behaviour can be set per test without leaking across cases.
"""
from __future__ import annotations

import base64
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


def _get_json(url: str) -> dict:
    with urllib.request.urlopen(urllib.request.Request(url)) as resp:
        return json.loads(resp.read())


# ── Invite gate ─────────────────────────────────────────────────────────────

class TestInviteGate:
    """The gate is the per-user `invite_keys` table only — there is no shared
    key (removed pre-launch: a shared credential let many players collapse to
    one identity and could play anonymously, ADR-004 §7). No key minted → open
    (local dev / tests). One key minted → every request needs a valid, named
    credential."""

    def _gate_on(self):
        # Minting one active per-user key closes the gate for this test's
        # isolated DB.
        persistence.mint_invite_key("nw_letmein", "Gatekeeper")

    def test_no_key_means_open(self, srv):
        base, _ = srv
        assert _get_status(f"{base}/worlds") == 200

    def test_health_exempt_even_when_gated(self, srv):
        # Platform load balancers shouldn't need a credential to probe liveness.
        self._gate_on()
        base, _ = srv
        assert _get_status(f"{base}/health") == 200

    def test_missing_key_rejected(self, srv):
        self._gate_on()
        base, _ = srv
        assert _get_status(f"{base}/worlds") == 403

    def test_wrong_key_rejected(self, srv):
        self._gate_on()
        base, _ = srv
        assert _get_status(f"{base}/worlds?key=nope") == 403

    def test_key_via_query_param_accepted(self, srv):
        self._gate_on()
        base, _ = srv
        assert _get_status(f"{base}/worlds?key=nw_letmein") == 200

    def test_key_via_header_accepted(self, srv):
        self._gate_on()
        base, _ = srv
        status = _get_status(f"{base}/worlds",
                              headers={guard.BETA_KEY_HEADER: "nw_letmein"})
        assert status == 200


# ── Per-user invite keys ────────────────────────────────────────────────────

class TestPerUserInviteKeys:
    """Per-user keys are the whole gate. These tests cover the three states
    the auth function sees: valid per-user key, revoked per-user key, unknown
    key while the gate is active."""

    @pytest.fixture(autouse=True)
    def _clear_touch_cache(self):
        # The 5-minute touch throttle persists across tests in the same
        # process — reset it so each case sees a clean cache.
        guard._touch_cache.clear()

    def test_active_per_user_key_accepted(self, srv):
        persistence.mint_invite_key("k_alice", "Alice")
        base, _ = srv
        assert _get_status(f"{base}/worlds?key=k_alice") == 200

    def test_revoked_per_user_key_rejected(self, srv):
        persistence.mint_invite_key("k_alice", "Alice")
        persistence.revoke_invite_key("k_alice")
        base, _ = srv
        # After revocation only inactive rows exist — gate is no longer
        # "active" and the server reverts to open. To keep the gate up
        # we add another active row.
        persistence.mint_invite_key("k_bob", "Bob")
        assert _get_status(f"{base}/worlds?key=k_alice") == 403

    def test_unknown_key_rejected_when_per_user_gate_active(self, srv):
        persistence.mint_invite_key("k_alice", "Alice")
        base, _ = srv
        assert _get_status(f"{base}/worlds?key=k_nope") == 403

    def test_per_user_key_via_header_accepted(self, srv):
        persistence.mint_invite_key("k_alice", "Alice")
        base, _ = srv
        status = _get_status(f"{base}/worlds",
                              headers={guard.BETA_KEY_HEADER: "k_alice"})
        assert status == 200

    def test_unit_check_invite_key_touches_last_used(self):
        # Verifies the touch path actually updates the row — guards
        # against a future refactor that breaks the admin CLI's
        # "is Alice still active" signal.
        persistence.mint_invite_key("k_alice", "Alice")
        assert guard.check_invite_key(
            {guard.BETA_KEY_HEADER: "k_alice"}, {}
        ) is True
        row = persistence.lookup_invite_key("k_alice")
        assert row is not None and row["last_used_at"] is not None

    def test_unit_invite_gate_active_reflects_db(self):
        # With no per-user rows the gate is open.
        assert guard.invite_gate_active() is False
        # Mint a row — gate flips active.
        persistence.mint_invite_key("k_alice", "Alice")
        assert guard.invite_gate_active() is True


# ── World-parameter bounds ──────────────────────────────────────────────────

class TestWorldBounds:
    def test_runaway_depth_rejected(self, srv):
        base, _ = srv
        assert _get_status(f"{base}/world?depth=99") == 400

    def test_in_range_accepted(self, srv):
        base, _ = srv
        assert _get_status(f"{base}/world?depth=4") == 200

    def test_unit_validate_rejects_runaway(self):
        with pytest.raises(ValueError):
            guard.validate_world_params({"depth": 9999})

    def test_unit_validate_accepts_defaults(self):
        # Default values must always satisfy the bounds, otherwise legacy
        # callers without explicit params would 400.
        guard.validate_world_params({})

    def test_legacy_breadth_params_ignored_not_rejected(self, srv):
        # Breadth was once a client input; old clients (and saved position
        # records) still send it. The world's shape is now the canonical
        # BREADTH_BY_LEVEL profile — the params must be ignored so legacy
        # URLs keep working, and even absurd values must not change or
        # break anything (the amplification vector is gone by construction).
        base, _ = srv
        assert _get_status(f"{base}/world?depth=4&min_breadth=1&max_breadth=3") == 200
        assert _get_status(f"{base}/world?depth=4&min_breadth=5&max_breadth=2") == 200
        assert _get_status(f"{base}/world?depth=11&min_breadth=5&max_breadth=5") == 200

    def test_breadth_params_cannot_change_the_world(self, srv):
        # The same seed is the same world for every participant: a request
        # carrying breadth params gets identical structure to one without
        # them. (Node ids are per-process UUIDs — compare everything else.)
        base, _ = srv

        def strip_ids(node):
            return {k: ([strip_ids(c) for c in v] if k == "children" else v)
                    for k, v in node.items() if k != "id"}

        plain = _get_json(f"{base}/world?seed=42&depth=4")
        with_params = _get_json(
            f"{base}/world?seed=42&depth=4&min_breadth=1&max_breadth=2")
        assert strip_ids(plain["world"]) == strip_ids(with_params["world"])

    def test_full_depth_world_is_bounded_by_the_profile(self):
        # Worst case at full depth under the canonical profile: the product
        # of per-level maxima stays a single-VM-sized tree (~12k nodes), so
        # no request can amplify into an OOM the way client breadth once
        # could (depth=11 × breadth 5 ≈ 12M nodes).
        from multiverse.generator import BREADTH_BY_LEVEL, LEVELS
        worst, layer = 1, 1
        for level in LEVELS[:-1]:
            layer *= BREADTH_BY_LEVEL[level][1]
            worst += layer
        assert worst < 20_000


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
        # /image resolves node identity server-side now, so the request must
        # name a place that actually exists in the seed-42 world.
        from multiverse.generator import generate_node_hierarchy
        real_node = generate_node_hierarchy(seed=42, max_depth=1).name
        data, status = _post(f"{base}/image",
                              {"node_name": real_node, "seed": 42})
        assert status == 200
        assert data["url"] is None
        # Failure stays in fiction: the exhausted budget answers with the
        # authored quiet line and an images:false flag — never an ops string
        # ("budget", "FAL_KEY") in a player-fetchable payload.
        assert data["images"] is False
        assert "budget" not in data["error"]
        assert "FAL_KEY" not in data["error"]
        assert data["error"]  # an authored line, not an empty string


# ── Per-user spend sub-cap (fairness) ───────────────────────────────────────

class TestPerUserCostCap:
    """REGRESSION (P1): the daily cost cap used to be global-only, so a single
    account could drain the whole cohort's budget (~500 Anthropic calls in
    ~25 min) and degrade everyone to the quiet fallback. A per-credential
    sub-cap must bound how much any one user can consume, independent of others,
    while the no-credential (local dev / legacy) path stays global-only."""

    def test_per_user_cap_bounds_single_account(self, monkeypatch):
        # Global budget is generous; the per-user cap is what bites.
        monkeypatch.setenv(guard.ANTHROPIC_CAP_ENV, "1000")
        monkeypatch.setenv(guard.ANTHROPIC_PER_USER_CAP_ENV, "3")
        alice = "nw_alice"
        results = [guard.consume_anthropic(user_key=alice) for _ in range(5)]
        assert results == [True, True, True, False, False]

    def test_per_user_caps_are_independent(self, monkeypatch):
        monkeypatch.setenv(guard.ANTHROPIC_CAP_ENV, "1000")
        monkeypatch.setenv(guard.ANTHROPIC_PER_USER_CAP_ENV, "2")
        assert [guard.consume_anthropic(user_key="nw_alice") for _ in range(3)] == [True, True, False]
        # Bob has a fresh per-user counter even though Alice exhausted hers.
        assert [guard.consume_anthropic(user_key="nw_bob") for _ in range(3)] == [True, True, False]

    def test_no_credential_path_is_global_only(self, monkeypatch):
        # Local dev / existing callers pass no key: only the global cap applies,
        # so a tiny per-user cap must NOT block them.
        monkeypatch.setenv(guard.ANTHROPIC_CAP_ENV, "1000")
        monkeypatch.setenv(guard.ANTHROPIC_PER_USER_CAP_ENV, "1")
        assert all(guard.consume_anthropic() for _ in range(5))

    def test_global_cap_still_wins_when_lower(self, monkeypatch):
        # If the global cap is the tighter bound, it still stops the user even
        # though their per-user budget isn't exhausted.
        monkeypatch.setenv(guard.ANTHROPIC_CAP_ENV, "2")
        monkeypatch.setenv(guard.ANTHROPIC_PER_USER_CAP_ENV, "100")
        assert [guard.consume_anthropic(user_key="nw_alice") for _ in range(3)] == [True, True, False]

    def test_per_user_fal_cap_bounds_single_account(self, monkeypatch):
        monkeypatch.setenv(guard.FAL_CAP_ENV, "1000")
        monkeypatch.setenv(guard.FAL_PER_USER_CAP_ENV, "2")
        assert [guard.consume_fal(user_key="nw_alice") for _ in range(3)] == [True, True, False]

    def test_over_quota_account_does_not_drain_shared_budget(self, monkeypatch):
        # REGRESSION (P0-2): the previous code incremented the GLOBAL counter
        # before checking the per-user cap, so an account past its sub-cap kept
        # burning the shared budget on every rejected attempt — draining the
        # cohort's budget and denying fresh users, which is precisely what the
        # sub-cap is supposed to prevent. Here Alice (per-user cap 2) makes 5
        # attempts against a global cap of 5; her 3 rejected attempts must NOT
        # consume the global budget, so Bob still gets served.
        monkeypatch.setenv(guard.ANTHROPIC_CAP_ENV, "5")
        monkeypatch.setenv(guard.ANTHROPIC_PER_USER_CAP_ENV, "2")
        alice = [guard.consume_anthropic(user_key="nw_alice") for _ in range(5)]
        assert alice == [True, True, False, False, False]
        # Only Alice's 2 allowed calls should have touched the global counter.
        assert persistence.get_cost_calls(guard.ANTHROPIC_BUCKET, guard._utc_day()) == 2
        # A fresh account is unaffected by Alice's rejected attempts.
        assert [guard.consume_anthropic(user_key="nw_bob") for _ in range(2)] == [True, True]

    def test_over_quota_account_does_not_drain_shared_fal_budget(self, monkeypatch):
        # Same cross-user protection for the fal.ai image budget.
        monkeypatch.setenv(guard.FAL_CAP_ENV, "5")
        monkeypatch.setenv(guard.FAL_PER_USER_CAP_ENV, "2")
        assert [guard.consume_fal(user_key="nw_alice") for _ in range(5)] == [True, True, False, False, False]
        assert persistence.get_cost_calls(guard.FAL_BUCKET, guard._utc_day()) == 2
        assert [guard.consume_fal(user_key="nw_bob") for _ in range(2)] == [True, True]


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

    def test_app_shell_ungated_but_world_gated(self, srv):
        persistence.mint_invite_key("nw_gate", "Gatekeeper")
        base, _ = srv
        # Shell loads with no key (browser can't send one on the <script> tag).
        assert _get_status(f"{base}/app") == 200
        # But the data endpoint the SPA fetches is still gated.
        assert _get_status(f"{base}/world?seed=1&depth=3") == 403
        # ...and works once the key is forwarded (as the fixed SPA does).
        assert _get_status(f"{base}/world?seed=1&depth=3&key=nw_gate") == 200

    def test_is_public_asset_unit(self):
        from server.handlers import Handler
        assert Handler._is_public_asset("/app")
        assert Handler._is_public_asset("/app/assets/index-abc.js")
        assert Handler._is_public_asset("/health")
        assert Handler._is_public_asset("/explorer.js")
        assert Handler._is_public_asset("/d3.v7.min.js")
        assert Handler._is_public_asset("/favicon.ico")
        # Data / paid endpoints are never public.
        for p in ("/world", "/ws", "/agent", "/observe", "/puzzle",
                  "/puzzle/attempt", "/speak", "/image", "/agent/voice",
                  "/players", "/history", "/worlds"):
            assert not Handler._is_public_asset(p), p

    def test_vendored_d3_served_ungated(self, srv):
        # REGRESSION (P1-2): D3 must be served same-origin and ungated so the
        # invite default page never depends on the d3js.org CDN (a blocked /
        # offline CDN or an SRI mismatch used to brick the whole page).
        persistence.mint_invite_key("nw_gate", "Gatekeeper")
        base, _ = srv
        req = urllib.request.Request(f"{base}/d3.v7.min.js")
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            body = resp.read(80).decode("latin-1", "replace")
        # It is really D3 v7 (the UMD banner), not an error page.
        assert "d3js.org v7" in body

    def test_favicon_returns_204_ungated(self, srv):
        # The browser auto-requests /favicon.ico with no key; it must not fall
        # through to a gated 403 in every tester's console.
        persistence.mint_invite_key("nw_gate", "Gatekeeper")
        base, _ = srv
        assert _get_status(f"{base}/favicon.ico") == 204


class TestWebSocketGate:
    def test_ws_gated_without_key(self, srv):
        # REGRESSION: the WebSocket upgrade must be invite-gated like REST.
        persistence.mint_invite_key("nw_gate", "Gatekeeper")
        _, port = srv
        code, _ = _ws_upgrade(port, "/ws?seed=42&name=A")
        assert code == 403

    def test_ws_accepts_forwarded_key(self, srv):
        persistence.mint_invite_key("nw_gate", "Gatekeeper")
        _, port = srv
        code, sock = _ws_upgrade(port, "/ws?seed=42&name=A&key=nw_gate", hold=True)
        assert code == 101
        if sock:
            sock.close()

    def test_ws_connection_cap_rejects_overflow(self, srv, monkeypatch):
        # REGRESSION (P1-2): concurrent WS connections are capped; the
        # (cap+1)th upgrade is rejected with 503 instead of spawning an
        # unbounded thread.
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


# ── Read-side rate limiting (2026-07-18 evaluation rec 3) ───────────────────

class TestReadRateLimit:
    """The expensive GETs get their own, looser per-IP limiter.

    /world rebuilds and serializes the canonical tree per hit and /agent
    runs an FSM traversal — neither costs API budget, so the cost caps
    never bound them; before READ_RATE_LIMITER they were the one
    unthrottled way to pin the beta VM's CPU.
    """

    def test_expensive_get_is_limited(self, srv, monkeypatch):
        monkeypatch.setenv(guard.READ_RATE_LIMIT_ENV, "2")
        base, _ = srv
        assert _get_status(f"{base}/history?seed=42") == 200
        assert _get_status(f"{base}/history?seed=42") == 200
        assert _get_status(f"{base}/history?seed=42") == 429

    def test_deny_line_stays_in_fiction(self, srv, monkeypatch):
        monkeypatch.setenv(guard.READ_RATE_LIMIT_ENV, "1")
        base, _ = srv
        _get_status(f"{base}/history?seed=42")
        try:
            urllib.request.urlopen(f"{base}/history?seed=42")
        except urllib.error.HTTPError as exc:
            assert exc.code == 429
            body = json.loads(exc.read())
            # The explorer renders this text verbatim in its panels, so the
            # deny must arrive as the world's voice, not ops-speak.
            assert body["error"]
            assert "rate" not in body["error"].lower()
            assert "slow down" not in body["error"].lower()
        else:
            pytest.fail("expected 429 after exceeding the read limit")

    def test_static_shell_and_health_are_never_read_limited(self, srv,
                                                            monkeypatch):
        monkeypatch.setenv(guard.READ_RATE_LIMIT_ENV, "1")
        base, _ = srv
        _get_status(f"{base}/history?seed=42")   # burn the read quota
        assert _get_status(f"{base}/health") == 200
        assert _get_status(f"{base}/") == 200

    def test_read_limiter_is_independent_of_post_limiter(self, srv,
                                                         monkeypatch):
        # Burning the POST quota must not 429 a read, and vice versa.
        monkeypatch.setenv(guard.RATE_LIMIT_ENV, "1")
        monkeypatch.setenv(guard.DISABLE_AI_ENV, "1")
        base, _ = srv
        _post(f"{base}/speak", {"node_name": "X", "message": "hi"})
        assert _get_status(f"{base}/history?seed=42") == 200


class TestAgentMaxNodesClamp:
    def test_huge_max_nodes_is_clamped(self, srv):
        # An unbounded client value bought arbitrary server CPU with one
        # request; the walk is now capped at 500 visits regardless of ask.
        base, _ = srv
        data = _get_json(
            f"{base}/agent?seed=42&name=ClampScout&max_nodes=999999")
        assert data["nodes_visited"] <= 500

    def test_nonpositive_max_nodes_still_answers(self, srv):
        base, _ = srv
        data = _get_json(f"{base}/agent?seed=42&name=ClampScout2&max_nodes=-5")
        assert data["nodes_visited"] >= 0


class TestBodyShapeRobustness:
    """Malformed-but-valid JSON must be the client's 400, never our 500."""

    def test_json_array_body_is_400_not_500(self, srv):
        # json.loads(b"[1,2]") succeeds, and body.get() would AttributeError
        # into the catch-all 500 without the isinstance guard.
        base, _ = srv
        req = urllib.request.Request(
            f"{base}/speak", data=b"[1, 2, 3]",
            headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req)
        except urllib.error.HTTPError as exc:
            assert exc.code == 400
        else:
            pytest.fail("expected 400 for a JSON array body")

    def test_numeric_answer_is_a_guess_not_a_500(self, srv):
        # {"answer": 7} is a legitimate attempt at a sequence puzzle.
        from multiverse.generator import generate_node_hierarchy
        base, _ = srv
        real_node = generate_node_hierarchy(seed=42, max_depth=1).name
        data, status = _post(f"{base}/puzzle/attempt",
                             {"node_name": real_node, "seed": 42, "answer": 7})
        assert status == 200
        assert "result" in data
