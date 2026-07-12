"""Player-facing polish: the guide page, the client-error sink, and the
ambient-sound module's serving contract.
"""
from __future__ import annotations

import json
import logging
import threading
import urllib.request

import pytest

import persistence


@pytest.fixture()
def srv():
    from server import _Handler, _ThreadedServer
    server = _ThreadedServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


class TestGuidePage:
    def test_guide_serves_the_how_to_play_page(self, srv):
        with urllib.request.urlopen(f"{srv}/guide") as resp:
            body = resp.read().decode()
        assert resp.status == 200
        assert "How to Play" in body
        assert "attune" in body and "observe" in body  # the 11 verbs table

    def test_guide_is_ungated_like_the_ui_shell(self, srv):
        # The guide is onboarding material — a prospective tester follows the
        # link before they have a key. Minting a key activates the gate.
        persistence.mint_invite_key("nw_gate", "Gatekeeper")
        with urllib.request.urlopen(f"{srv}/guide") as resp:
            assert resp.status == 200


def _client_log_lines(caplog, timeout=2.0):
    """The handler thread logs after responding — poll briefly (same race
    as the access-log E2E tests)."""
    import time
    deadline = time.monotonic() + timeout
    while True:
        lines = [r.getMessage() for r in caplog.records
                 if r.name == "nested_worlds.client"]
        if lines or time.monotonic() > deadline:
            return lines
        time.sleep(0.01)


class TestClientErrorSink:
    def _post(self, srv, body):
        req = urllib.request.Request(
            f"{srv}/client-error", data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"})
        return urllib.request.urlopen(req)

    def test_browser_error_lands_in_the_server_log(self, srv, caplog):
        with caplog.at_level(logging.WARNING, logger="nested_worlds.client"):
            with self._post(srv, {"message": "TypeError: x is undefined",
                                  "source": "app.js:120"}) as resp:
                assert json.loads(resp.read()) == {"ok": True}
            lines = _client_log_lines(caplog)
        assert any("TypeError: x is undefined" in l for l in lines)

    def test_oversized_fields_are_truncated_not_rejected(self, srv, caplog):
        with caplog.at_level(logging.WARNING, logger="nested_worlds.client"):
            with self._post(srv, {"message": "x" * 5000,
                                  "stack": "y" * 5000}) as resp:
                assert resp.status == 200
            lines = _client_log_lines(caplog)
        logged = next(l for l in lines if "client error" in l)
        assert len(logged) < 2200  # 512 msg + 1024 stack + framing

    def test_empty_message_is_a_silent_ok(self, srv, caplog):
        with caplog.at_level(logging.WARNING, logger="nested_worlds.client"):
            with self._post(srv, {}) as resp:
                assert resp.status == 200
            lines = _client_log_lines(caplog, timeout=0.3)
        assert not [l for l in lines if "client error" in l]

    def test_client_error_is_rate_limited(self):
        from server.handlers import _RATE_LIMITED_PATHS
        assert "/client-error" in _RATE_LIMITED_PATHS


class TestNodeSoundServing:
    def test_nodesound_module_is_served(self, srv):
        with urllib.request.urlopen(f"{srv}/nodesound.js") as resp:
            body = resp.read().decode()
        assert resp.status == 200
        assert "javascript" in resp.headers["Content-Type"]
        assert "NodeAmbience" in body
        # Determinism contract, same as the art module.
        assert "Math.random" not in body
        assert "Date.now" not in body
