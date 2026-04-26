"""Regression tests for server-side security fixes."""
from __future__ import annotations

import json
import threading
import urllib.request

import pytest

from server import _Handler, _ThreadedServer


@pytest.fixture(scope="module")
def srv_url():
    srv = _ThreadedServer(("127.0.0.1", 0), _Handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{port}"
    srv.shutdown()


def _post_json(url: str, data: dict) -> dict:
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def test_attempt_leak_prevented(srv_url):
    """C-1: attempt=99999 must NOT reveal correct_answer."""
    data = _post_json(
        f"{srv_url}/puzzle/attempt",
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
    assert data.get("correct_answer") is None, (
        "correct_answer must be None when attempt is out-of-bounds"
    )
