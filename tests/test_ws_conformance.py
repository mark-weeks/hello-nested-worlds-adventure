"""Executable RFC 6455 conformance spec for the hand-rolled WebSocket server.

WHY THIS FILE EXISTS
--------------------
`/ws` is not a library socket. `server/handlers.py` and `server/protocol.py`
implement the RFC 6455 opening handshake and framing by hand, and that
hand-rolled surface once shipped a regression the rest of the suite could not
see: the ``101 Switching Protocols`` upgrade was written on an **HTTP/1.0**
status line. The repo's own minimal test client (a raw socket that only asserts
``b"101" in status``) accepted it, so every in-tree WS test still passed — but
spec-strict real clients, notably the Python ``websockets`` library, reject a
101 that does not arrive as ``HTTP/1.1`` and refuse to open the connection.
Browsers were lenient enough to hide it, so it slipped straight to the class of
client a stricter test would have caught.

``Handler.protocol_version = "HTTP/1.1"`` is the fix. This file makes it
permanent by driving the endpoint with the **real** ``websockets`` client
instead of a bespoke socket. The library performs the full handshake — the
status-line version check, ``Sec-WebSocket-Accept`` validation, masked client
framing (§5.1), and the closing handshake — so if any of that regresses the
connection simply will not open and these tests fail, which the hand-rolled
client never could.

These are behavior tests: they boot the real threaded server and assert on
frames exchanged over a live socket, never on strings in source files.
"""
from __future__ import annotations

import json
import threading
import time

import pytest

# Skip cleanly (rather than error) if the dev extra hasn't been installed yet.
websockets_connect = pytest.importorskip("websockets.sync.client").connect


@pytest.fixture()
def srv():
    """Boot the real threaded server on an ephemeral port; yield the port.

    This is the canonical harness the other WS tests use
    (tests/test_day_one_recording.py) — reused verbatim so the conformance
    guard exercises the exact same server-boot path as everything else.
    """
    from server import _Handler, _ThreadedServer

    server = _ThreadedServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield port
    server.shutdown()


def _connect(port: int, seed: int, name: str):
    """Open a real RFC 6455 connection to /ws with explicit, non-flaky timeouts.

    If the server's 101 handshake regresses (e.g. back to HTTP/1.0, or a bad
    Sec-WebSocket-Accept), ``connect`` raises here instead of returning — that
    failure IS the guard.
    """
    uri = f"ws://127.0.0.1:{port}/ws?seed={seed}&name={name}"
    return websockets_connect(uri, open_timeout=5, close_timeout=5)


def _recv_json_until(ws, want_type: str, timeout: float = 5.0) -> dict:
    """Return the next frame whose ``type`` == ``want_type``, decoded as JSON.

    Reads real frames off the socket, skipping any unrelated ones, until the
    wanted type arrives or the deadline passes (so a broken server fails the
    test fast instead of hanging CI)."""
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AssertionError(f"timed out waiting for a {want_type!r} frame")
        msg = json.loads(ws.recv(timeout=remaining))
        if msg.get("type") == want_type:
            return msg


def test_real_websockets_client_completes_the_opening_handshake(srv):
    """The regression guard: a spec-strict client must be able to open /ws.

    ``connect`` drives the full opening handshake; it would raise on the
    HTTP/1.0-101 defect this file exists for. Reaching the welcome frame proves
    the handshake completed AND that the first server->client frame decodes.
    """
    with _connect(srv, seed=6455, name="Ada") as ws:
        welcome = _recv_json_until(ws, "welcome")
        assert "session_id" in welcome
        assert isinstance(welcome["players"], list)
        # The server adds us to the room before sending welcome, so our own
        # presence is already in the roster it built.
        assert any(p["name"] == "Ada" for p in welcome["players"])


def test_masked_client_text_frame_round_trips_as_a_broadcast(srv):
    """A masked client frame is accepted and the message round-trips.

    ``websockets`` masks client frames per §5.1; the server rejects UNmasked
    client frames, so this only passes if real masked framing works end to end.
    chat is broadcast to every player in the room (including the sender), so a
    single client observes its own message come back.
    """
    with _connect(srv, seed=6456, name="Ada") as ws:
        _recv_json_until(ws, "welcome")
        ws.send(json.dumps({"type": "chat", "text": "hello over rfc6455"}))
        chat = _recv_json_until(ws, "chat")
        assert chat["name"] == "Ada"
        assert chat["text"] == "hello over rfc6455"


def test_a_second_client_join_is_broadcast_to_the_first(srv):
    """Two real clients in one room: the first sees the second's join.

    Exercises multi-connection broadcast over live sockets and confirms both
    connections open, exchange a presence frame, and close cleanly (the ``with``
    blocks run the RFC closing handshake on exit).
    """
    with _connect(srv, seed=6457, name="Ada") as a:
        _recv_json_until(a, "welcome")
        with _connect(srv, seed=6457, name="Bee") as b:
            _recv_json_until(b, "welcome")
            join = _recv_json_until(a, "player_join")
            assert join["name"] == "Bee"
