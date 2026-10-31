"""HTTP read budget and handler-thread cap.

A stalled or dribbling client used to hold a handler thread with no socket
deadline, and nothing bounded how many of those threads could exist. The
WebSocket cap applies only after the upgrade request has been read. These
tests use small limits so they fail fast instead of sleeping out the defaults.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import socket
import struct
import threading
import time
import urllib.error
import urllib.request

import pytest

from server import _Handler, _ThreadedServer, observability
from server import guard


_READ_TIMEOUT = "0.5"


@pytest.fixture
def limited(monkeypatch):
    monkeypatch.setenv(guard.HTTP_READ_TIMEOUT_ENV, _READ_TIMEOUT)
    monkeypatch.setenv(guard.MAX_HANDLER_THREADS_ENV, "8")
    server = _ThreadedServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield port
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)


def _health(port: int) -> int:
    with urllib.request.urlopen(
        f"http://127.0.0.1:{port}/health", timeout=2
    ) as resp:
        return resp.status


def _read_http(sock: socket.socket, timeout: float = 2.0):
    sock.settimeout(timeout)
    data = bytearray()
    while b"\r\n\r\n" not in data:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data.extend(chunk)
        if len(data) > 65536:
            break
    head, _, rest = bytes(data).partition(b"\r\n\r\n")
    lines = head.decode("iso-8859-1", "replace").split("\r\n")
    status = int(lines[0].split(" ", 2)[1])
    headers = {}
    for line in lines[1:]:
        if ":" in line:
            key, value = line.split(":", 1)
            headers[key.strip().lower()] = value.strip()
    length = int(headers.get("content-length", "0") or 0)
    while len(rest) < length:
        chunk = sock.recv(length - len(rest))
        if not chunk:
            break
        rest += chunk
    return status, headers, rest[:length]


def _client_frame(payload: bytes, opcode: int = 0x1) -> bytes:
    mask = b"\x37\x42\x9a\xc1"
    masked = bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))
    return bytes([0x80 | opcode, 0x80 | len(payload)]) + mask + masked


class _FrameReader:
    def __init__(self, sock: socket.socket, pending: bytes = b""):
        self._sock = sock
        self._buf = bytearray(pending)

    def _read(self, n: int) -> bytes:
        while len(self._buf) < n:
            chunk = self._sock.recv(4096)
            if not chunk:
                raise ConnectionError("socket closed")
            self._buf.extend(chunk)
        out = bytes(self._buf[:n])
        del self._buf[:n]
        return out

    def frame(self) -> tuple[int, bytes]:
        header = self._read(2)
        opcode = header[0] & 0x0F
        length = header[1] & 0x7F
        if length == 126:
            length = struct.unpack(">H", self._read(2))[0]
        elif length == 127:
            length = struct.unpack(">Q", self._read(8))[0]
        return opcode, self._read(length)


def _upgrade(port: int, path: str = "/ws?seed=42&name=Ada"):
    sock = socket.create_connection(("127.0.0.1", port), timeout=2)
    key = base64.b64encode(os.urandom(16)).decode()
    request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: 127.0.0.1:{port}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "\r\n"
    )
    sock.sendall(request.encode())
    sock.settimeout(2)
    data = bytearray()
    while b"\r\n\r\n" not in data:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data.extend(chunk)
    head, _, rest = bytes(data).partition(b"\r\n\r\n")
    status = int(head.decode("iso-8859-1").split("\r\n", 1)[0].split(" ", 2)[1])
    return status, sock, rest


class TestReadBudget:
    def test_prompt_requests_still_complete(self, limited):
        assert _health(limited) == 200
        request = urllib.request.Request(
            f"http://127.0.0.1:{limited}/no-such",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request, timeout=2)
        assert caught.value.code == 404

    def test_silent_client_is_dropped_and_the_thread_is_released(self, limited):
        sock = socket.create_connection(("127.0.0.1", limited))
        started = time.monotonic()
        sock.settimeout(2)
        try:
            try:
                data = sock.recv(64)
            except TimeoutError:
                pytest.fail("silent client was still held after 2s")
            except OSError:
                # A reset is the same outcome as a clean close: the thread
                # is no longer parked on this client.
                data = b""
        finally:
            sock.close()
        assert data == b""
        assert time.monotonic() - started < 2
        assert _health(limited) == 200

    def test_dribbling_client_cannot_refresh_the_deadline(self, limited):
        sock = socket.create_connection(("127.0.0.1", limited))
        sock.settimeout(2)
        started = time.monotonic()
        closed_at = None
        try:
            for _ in range(40):
                if time.monotonic() - started > 1.5:
                    break
                try:
                    # No newline: the request line never completes. Bytes
                    # every 80ms would refresh a pure idle timer of 0.5s.
                    sock.send(b"G")
                except OSError:
                    closed_at = time.monotonic() - started
                    break
                time.sleep(0.08)
        finally:
            sock.close()
        assert closed_at is not None and closed_at < 1.5
        assert _health(limited) == 200

    def test_stalled_body_gets_408(self, limited):
        sock = socket.create_connection(("127.0.0.1", limited), timeout=2)
        sock.sendall(
            b"POST /no-such HTTP/1.1\r\n"
            b"Host: localhost\r\n"
            b"Content-Type: application/json\r\n"
            b"Content-Length: 8\r\n"
            b"Connection: close\r\n"
            b"\r\n"
        )
        try:
            status, _headers, body = _read_http(sock, timeout=2)
        finally:
            sock.close()
        assert status == 408
        assert json.loads(body) == {"error": "request timed out"}
        assert _health(limited) == 200

    def test_kept_alive_socket_gets_a_fresh_read_budget_per_request(self, limited, monkeypatch):
        # The budget is a deadline on the socket, armed at accept. Every
        # response sends Connection: close today; this test keeps the socket
        # open the way a keep-alive client would, so the second request's
        # body read must be judged from that request's own start, not from
        # the connection's.
        from server.handlers import Handler
        monkeypatch.setenv(guard.HTTP_READ_TIMEOUT_ENV, "1.0")
        real = Handler._send_security_headers

        def reopen_unless_client_closes(self):
            real(self)
            if (self.headers.get("Connection") or "").lower() != "close":
                self.close_connection = False

        monkeypatch.setattr(Handler, "_send_security_headers", reopen_unless_client_closes)
        sock = socket.create_connection(("127.0.0.1", limited), timeout=3)
        try:
            sock.sendall(b"GET /health HTTP/1.1\r\nHost: localhost\r\n\r\n")
            first, _headers, _body = _read_http(sock, timeout=2)
            assert first == 200
            time.sleep(0.8)
            sock.sendall(
                b"POST /no-such HTTP/1.1\r\n"
                b"Host: localhost\r\n"
                b"Content-Type: application/json\r\n"
                b"Content-Length: 8\r\n"
                b"Connection: close\r\n"
                b"\r\n"
            )
            # 1.3s after accept, but only 0.5s into this request.
            time.sleep(0.5)
            sock.sendall(b'{"a": 1}')
            second, _headers, body = _read_http(sock, timeout=2)
        finally:
            sock.close()
        assert second == 404, (second, body)
        assert json.loads(body) == {"error": "not found"}

    def test_stalled_second_request_gets_408(self, limited, monkeypatch):
        # The first request finishes, then this client waits before sending
        # the next one and never sends its body. A deadline armed once at
        # accept is already mostly spent, so the 408 would arrive before
        # 0.6s. A per-request budget starts when the second request's first
        # byte arrives, so the wait plus that budget runs past 0.6s.
        # Production sends Connection: close; this test keeps the socket open.
        from server.handlers import Handler
        monkeypatch.setenv(guard.HTTP_READ_TIMEOUT_ENV, "0.5")
        real = Handler._send_security_headers

        def reopen_unless_client_closes(self):
            real(self)
            if (self.headers.get("Connection") or "").lower() != "close":
                self.close_connection = False

        monkeypatch.setattr(Handler, "_send_security_headers", reopen_unless_client_closes)
        sock = socket.create_connection(("127.0.0.1", limited), timeout=3)
        try:
            sock.sendall(b"GET /health HTTP/1.1\r\nHost: localhost\r\n\r\n")
            first, _headers, _body = _read_http(sock, timeout=2)
            assert first == 200
            started = time.monotonic()
            time.sleep(0.3)
            sock.sendall(
                b"POST /no-such HTTP/1.1\r\n"
                b"Host: localhost\r\n"
                b"Content-Type: application/json\r\n"
                b"Content-Length: 8\r\n"
                b"Connection: close\r\n"
                b"\r\n"
            )
            status, _headers, body = _read_http(sock, timeout=2)
        finally:
            sock.close()
        elapsed = time.monotonic() - started
        assert status == 408
        assert json.loads(body) == {"error": "request timed out"}
        assert elapsed > 0.6
        assert elapsed < 1.4
        assert _health(limited) == 200


class TestHandlerCap:
    def test_full_server_returns_503_with_retry_after(self, limited, monkeypatch):
        monkeypatch.setenv(guard.MAX_HANDLER_THREADS_ENV, "1")
        status, held, _pending = _upgrade(limited)
        assert status == 101
        extra = socket.create_connection(("127.0.0.1", limited), timeout=2)
        started = time.monotonic()
        try:
            extra.sendall(b"GET /health HTTP/1.1\r\nHost: localhost\r\n\r\n")
            code, headers, body = _read_http(extra, timeout=2)
            assert time.monotonic() - started < 1
            assert code == 503
            assert headers["retry-after"] == "2"
            assert json.loads(body) == {"error": "server busy"}
            # A refusal must not consume the only slot: a second attempt
            # is still a 503 while the WebSocket is held, not a hang.
            again = socket.create_connection(("127.0.0.1", limited), timeout=2)
            try:
                again.sendall(b"GET /health HTTP/1.1\r\nHost: localhost\r\n\r\n")
                code2, _, _ = _read_http(again, timeout=2)
                assert code2 == 503
            finally:
                again.close()
        finally:
            extra.close()
            held.close()
        # The slot frees when the session thread exits. Poll briefly.
        deadline = time.monotonic() + 2
        last = None
        while time.monotonic() < deadline:
            try:
                last = _health(limited)
            except urllib.error.HTTPError as exc:
                last = exc.code
            if last == 200:
                break
            time.sleep(0.02)
        assert last == 200

    def test_refusal_log_hashes_the_client_address(self, limited, monkeypatch, caplog):
        monkeypatch.setenv(guard.MAX_HANDLER_THREADS_ENV, "1")
        # The refusal is logged at INFO on the accept thread, before the
        # 503 is written. The root logger drops INFO while it is still at
        # WARNING, so this capture has to cover the connect. CI saw an
        # empty list when the capture opened only around the later read.
        with caplog.at_level(logging.INFO):
            status, held, _pending = _upgrade(limited)
            assert status == 101
            extra = socket.create_connection(("127.0.0.1", limited), timeout=2)
            peer_ip, peer_port = extra.getsockname()
            try:
                extra.sendall(b"GET /health HTTP/1.1\r\nHost: localhost\r\n\r\n")
                code, _, _ = _read_http(extra, timeout=2)
                assert code == 503
            finally:
                extra.close()
                held.close()
        refusals = [
            record.getMessage()
            for record in caplog.records
            if "handler threads full" in record.getMessage()
        ]
        assert refusals
        expected = (
            "refusing connection from "
            f"{observability.hash_ip(peer_ip)}: handler threads full"
        )
        for message in refusals:
            assert message == expected
            assert peer_ip not in message
            assert str(peer_port) not in message

    def test_stalled_response_reader_releases_the_slot(self, limited, monkeypatch):
        monkeypatch.setenv(guard.MAX_HANDLER_THREADS_ENV, "1")
        monkeypatch.setenv(guard.HTTP_WRITE_TIMEOUT_ENV, "0.5")
        sock = socket.socket()
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_WINDOW_CLAMP, 2048)
        sock.settimeout(2)
        sock.connect(("127.0.0.1", limited))
        try:
            sock.sendall(
                b"GET /media/places/orchard-v1.png HTTP/1.1\r\n"
                b"Host: localhost\r\n"
                b"Connection: close\r\n"
                b"\r\n"
            )
            saw_503 = False
            recovered = None
            started = time.monotonic()
            while time.monotonic() - started < 3:
                try:
                    code = _health(limited)
                except urllib.error.HTTPError as exc:
                    code = exc.code
                if code == 503:
                    saw_503 = True
                if code == 200 and saw_503:
                    recovered = time.monotonic() - started
                    break
                time.sleep(0.02)
            assert saw_503
            assert recovered is not None and recovered < 2.5
        finally:
            sock.close()

    def test_slow_progressing_reader_receives_the_whole_file(self, limited, monkeypatch):
        # Shorter than the transfer. A whole-body sendall deadline would
        # close the socket before Content-Length bytes arrive.
        monkeypatch.setenv(guard.HTTP_WRITE_TIMEOUT_ENV, "0.2")
        sock = socket.socket()
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_WINDOW_CLAMP, 2048)
        sock.settimeout(2)
        sock.connect(("127.0.0.1", limited))
        try:
            sock.sendall(
                b"GET /media/score/pizzicato.mp3 HTTP/1.1\r\n"
                b"Host: localhost\r\n"
                b"Connection: close\r\n"
                b"\r\n"
            )
            data = bytearray()
            started = time.monotonic()
            while b"\r\n\r\n" not in data:
                chunk = sock.recv(256)
                if not chunk:
                    break
                data.extend(chunk)
            head, _, rest = bytes(data).partition(b"\r\n\r\n")
            status = int(head.split(b"\r\n", 1)[0].split(b" ", 2)[1])
            length = 0
            for line in head.decode("iso-8859-1").split("\r\n")[1:]:
                if line.lower().startswith("content-length:"):
                    length = int(line.split(":", 1)[1].strip())
            body = bytearray(rest)
            while len(body) < length:
                chunk = sock.recv(256)
                if not chunk:
                    break
                body.extend(chunk)
                time.sleep(0.02)
            elapsed = time.monotonic() - started
            assert status == 200
            assert length > 8000
            assert len(body) == length
            assert elapsed > 0.2
        finally:
            sock.close()


class TestWebSocketSurvivesReadBudget:
    def test_session_outruns_the_http_budget_and_answers_pings(self, limited):
        status, sock, pending = _upgrade(limited)
        assert status == 101
        sock.settimeout(2)
        reader = _FrameReader(sock, pending)
        try:
            opcode, payload = reader.frame()
            assert opcode == 0x1
            welcome = json.loads(payload)
            assert welcome["type"] == "welcome"
            # Longer than the 0.5s HTTP budget. If the upgrade left that
            # deadline in place, the session would already be gone.
            time.sleep(0.8)
            sock.sendall(_client_frame(json.dumps({"type": "ping"}).encode()))
            reply = None
            for _ in range(5):
                opcode, payload = reader.frame()
                if opcode == 0x1:
                    reply = json.loads(payload)
                    break
            assert reply == {"type": "pong"}
            sock.sendall(_client_frame(b"stay", opcode=0x9))
            opcode, payload = reader.frame()
            assert opcode == 0xA
            assert payload == b"stay"
        finally:
            sock.close()
        assert _health(limited) == 200


class TestReadBudgetSocket:
    def test_websocket_idle_timeout_survives_the_write_timer(self, monkeypatch):
        from server.handlers import _ReadBudgetSocket

        monkeypatch.setenv(guard.HTTP_WRITE_TIMEOUT_ENV, "0.2")
        local, peer = socket.socketpair()
        try:
            wrapped = _ReadBudgetSocket(local, time.monotonic() + 5)
            wrapped.settimeout(60)
            wrapped.sendall(b"abc")
            assert wrapped.gettimeout() == 60
            assert peer.recv(3) == b"abc"
        finally:
            peer.close()
            local.close()

    def test_sendall_rearms_while_the_peer_keeps_accepting(self, monkeypatch):
        from server.handlers import _ReadBudgetSocket

        monkeypatch.setenv(guard.HTTP_WRITE_TIMEOUT_ENV, "0.2")

        class _Chunked:
            """Accepts one byte per send. Native sendall is the WebSocket path."""

            def __init__(self) -> None:
                self.timeout = None
                self.sent = bytearray()
                self.timeouts: list[float] = []
                self.native = 0

            def settimeout(self, value) -> None:
                self.timeout = value
                if value is not None:
                    self.timeouts.append(value)

            def gettimeout(self):
                return self.timeout

            def send(self, data, *args, **kwargs):
                self.sent.append(memoryview(data)[0])
                return 1

            def sendall(self, data, *args, **kwargs):
                self.native += 1
                self.sent.extend(data)

        inner = _Chunked()
        wrapped = _ReadBudgetSocket(inner, time.monotonic() + 5)
        wrapped.sendall(b"abcdef")
        assert bytes(inner.sent) == b"abcdef"
        assert inner.native == 0
        assert inner.timeouts == [0.2, 0.2, 0.2, 0.2, 0.2, 0.2]

        wrapped.settimeout(60)
        inner.timeouts.clear()
        wrapped.sendall(b"z")
        assert bytes(inner.sent) == b"abcdefz"
        assert inner.native == 1
        assert inner.timeouts == []

    def test_settimeout_clears_an_already_expired_deadline(self):
        from server.handlers import _ReadBudgetSocket

        local, peer = socket.socketpair()
        try:
            wrapped = _ReadBudgetSocket(local, time.monotonic() - 1)
            with pytest.raises(TimeoutError):
                wrapped.recv(1)
            wrapped.settimeout(2)
            peer.sendall(b"x")
            assert wrapped.recv(1) == b"x"
            assert wrapped.gettimeout() == 2
        finally:
            peer.close()
            local.close()

    def test_makefile_read_uses_the_budget(self):
        from server.handlers import _ReadBudgetSocket

        local, peer = socket.socketpair()
        wrapped = _ReadBudgetSocket(local, time.monotonic() + 0.3)
        reader = wrapped.makefile("rb")
        errors: list[str] = []

        def _read() -> None:
            try:
                reader.readline()
            except TimeoutError:
                errors.append("timeout")
            except Exception as exc:  # noqa: BLE001 — the assertion reports it
                errors.append(type(exc).__name__)

        thread = threading.Thread(target=_read)
        thread.start()
        thread.join(1.5)
        try:
            assert not thread.is_alive()
            assert errors == ["timeout"]
        finally:
            peer.close()
            local.close()


class TestLimitParsing:
    def test_timeout_falls_back_unless_it_is_a_positive_number(self, monkeypatch):
        monkeypatch.delenv(guard.HTTP_READ_TIMEOUT_ENV, raising=False)
        assert guard.http_read_timeout() == 30.0
        for raw in ("0", "-1", "nope", "inf", "nan", "  "):
            monkeypatch.setenv(guard.HTTP_READ_TIMEOUT_ENV, raw)
            assert guard.http_read_timeout() == 30.0
        monkeypatch.setenv(guard.HTTP_READ_TIMEOUT_ENV, "0.25")
        assert guard.http_read_timeout() == 0.25
        monkeypatch.setenv(guard.HTTP_READ_TIMEOUT_ENV, " 15 ")
        assert guard.http_read_timeout() == 15.0

    def test_write_timeout_falls_back_unless_it_is_a_positive_number(self, monkeypatch):
        monkeypatch.delenv(guard.HTTP_WRITE_TIMEOUT_ENV, raising=False)
        assert guard.http_write_timeout() == 30.0
        for raw in ("0", "-1", "nope", "inf", "nan", "  "):
            monkeypatch.setenv(guard.HTTP_WRITE_TIMEOUT_ENV, raw)
            assert guard.http_write_timeout() == 30.0
        monkeypatch.setenv(guard.HTTP_WRITE_TIMEOUT_ENV, "0.4")
        assert guard.http_write_timeout() == 0.4

    def test_thread_cap_falls_back_unless_it_is_a_positive_integer(self, monkeypatch):
        monkeypatch.delenv(guard.MAX_HANDLER_THREADS_ENV, raising=False)
        assert guard.max_handler_threads() == 160
        for raw in ("0", "-3", "nope", "4.5", "  "):
            monkeypatch.setenv(guard.MAX_HANDLER_THREADS_ENV, raw)
            assert guard.max_handler_threads() == 160
        monkeypatch.setenv(guard.MAX_HANDLER_THREADS_ENV, " 4 ")
        assert guard.max_handler_threads() == 4
