"""Operational guardrails (server/guard.py) — invite gate, rate limit,
cost caps, world-param bounds, kill switches.

Each test runs against a freshly-spawned server on an ephemeral port so
env-var-driven behaviour can be set per test without leaking across cases.
"""
from __future__ import annotations

import http.client
import json
import threading
import urllib.error
import urllib.request

import pytest

from server import _Handler, _ThreadedServer
from server import guard


# ── Per-test server fixture ─────────────────────────────────────────────────

@pytest.fixture
def srv():
    server = _ThreadedServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    # Reset the in-memory rate limiter between tests so a noisy run can't
    # spill into the next case's window.
    guard.RATE_LIMITER.reset()
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


# ── Client IP extraction ────────────────────────────────────────────────────

class TestClientIP:
    def test_default_uses_socket_peer(self, monkeypatch):
        monkeypatch.delenv(guard.TRUST_PROXY_ENV, raising=False)
        ip = guard.client_ip(("9.9.9.9", 12345),
                              {"X-Forwarded-For": "1.1.1.1"})
        assert ip == "9.9.9.9"

    def test_xff_honoured_only_when_trust_proxy(self, monkeypatch):
        monkeypatch.setenv(guard.TRUST_PROXY_ENV, "1")
        ip = guard.client_ip(("9.9.9.9", 12345),
                              {"X-Forwarded-For": "1.1.1.1, 2.2.2.2"})
        assert ip == "1.1.1.1"
