"""Integration tests for the HTTP server layer (T-1)."""
from __future__ import annotations

import http.client
import json
import threading
import urllib.error
import urllib.request

import pytest

import persistence
from server import _Handler, _ThreadedServer


@pytest.fixture(scope="module")
def srv():
    server = _ThreadedServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{port}", port
    server.shutdown()


def _get(url: str):
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read()), resp.status, resp.headers


def _post(url: str, data: dict):
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read()), resp.status


class TestServerHTTP:
    def test_health(self, srv):
        base, _ = srv
        data, status, _ = _get(f"{base}/health")
        assert status == 200
        assert data == {"status": "ok"}

    def test_world_valid(self, srv):
        base, _ = srv
        data, status, _ = _get(
            f"{base}/world?seed=1&depth=4&min_breadth=1&max_breadth=2"
        )
        assert status == 200
        assert data["node_count"] > 0

    def test_world_invalid_seed(self, srv):
        base, _ = srv
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            _get(f"{base}/world?seed=abc")
        assert exc_info.value.code == 400

    def test_puzzle_attempt_no_leak(self, srv):
        """C-1 regression: attempt=99999 must not reveal correct_answer."""
        base, _ = srv
        data, _ = _post(
            f"{base}/puzzle/attempt",
            {
                "seed": 42,
                "depth": 6,
                "min_breadth": 1,
                "max_breadth": 3,
                "node_name": "",
                "answer": "definitely_wrong_answer_xyzzy",
                "attempt": 99999,
            },
        )
        assert data.get("correct_answer") is None

    def test_body_too_large(self, srv):
        """H-1: Content-Length > 64 KB must return 413."""
        base, port = srv
        conn = http.client.HTTPConnection("127.0.0.1", port)
        conn.putrequest("POST", "/speak")
        conn.putheader("Content-Type", "application/json")
        conn.putheader("Content-Length", str(65 * 1024 + 1))
        conn.endheaders()
        conn.send(b"{}")
        resp = conn.getresponse()
        status = resp.status
        resp.read()
        conn.close()
        assert status == 413

    def test_players(self, srv):
        base, _ = srv
        data, status, _ = _get(f"{base}/players?seed=1")
        assert status == 200
        assert "players" in data

    def test_static_html(self, srv):
        base, _ = srv
        with urllib.request.urlopen(f"{base}/") as resp:
            assert resp.status == 200
            assert "text/html" in resp.headers.get("Content-Type", "")


class TestMutationRecording:
    """Each interaction surface should leave a row in world_mutations so
    consciousness prompts and the image cache see a richer signal than
    'puzzle solved.'"""

    def test_failed_puzzle_attempt_records_mutation(self, srv):
        base, _ = srv
        seed = 12345
        # Final attempt with a wrong answer — server confirms failure and
        # records PUZZLE_FAILED.
        _post(
            f"{base}/puzzle/attempt",
            {
                "seed": seed, "depth": 6, "min_breadth": 1, "max_breadth": 3,
                "node_name": "", "answer": "wrong-answer", "attempt": 3,
            },
        )
        kinds = {m["type"] for m in persistence.get_mutations(seed)}
        assert "PUZZLE_FAILED" in kinds

    def test_agent_traversal_records_visit_mutations(self, srv):
        base, _ = srv
        seed = 23456
        _get(f"{base}/agent?seed={seed}&name=Recorder&max_nodes=10")
        muts = persistence.get_mutations(seed, limit=50)
        kinds = {m["type"] for m in muts}
        assert "AGENT_VISIT" in kinds, (
            f"agent run should record AGENT_VISIT mutations; got {kinds}"
        )
        # Agent attribution lives in the data payload (player_name slot is
        # reserved for humans).
        agent_muts = [m for m in muts if m["type"] == "AGENT_VISIT"]
        assert any(m["data"].get("agent") == "Recorder" for m in agent_muts)
        # Persona is part of the same payload so consciousness prompts and
        # the event feed can read it without a side lookup.
        assert all("persona" in m["data"] for m in agent_muts)


class TestAgentPersonas:
    """The /agent endpoint should surface the chosen persona, and an
    explicit persona param should override the auto-pick."""

    def test_agent_endpoint_returns_default_persona(self, srv):
        base, _ = srv
        data, _, _ = _get(f"{base}/agent?seed=5&name=Argus&max_nodes=5")
        assert data["persona"] in {"tender", "destabilizer", "scholar", "wanderer"}

    def test_agent_endpoint_honours_explicit_persona(self, srv):
        base, _ = srv
        data, _, _ = _get(
            f"{base}/agent?seed=5&name=Argus&max_nodes=5&persona=destabilizer"
        )
        assert data["persona"] == "destabilizer"

    def test_unknown_persona_falls_back_to_default(self, srv):
        base, _ = srv
        data, _, _ = _get(
            f"{base}/agent?seed=5&name=Argus&max_nodes=5&persona=warlord"
        )
        # Falls back to for_name("Argus"), whatever that resolves to.
        assert data["persona"] in {"tender", "destabilizer", "scholar", "wanderer"}
        assert data["persona"] != "warlord"
