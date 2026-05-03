"""Tests for the hand-rolled WebSocket framing in server/protocol.py."""
import io
import struct

import pytest

from server.protocol import _MAX_FRAME, ws_recv, ws_send


class FakeSock:
    """Minimal stand-in for a connected socket: queues recv bytes, captures sendall."""

    def __init__(self, incoming: bytes = b""):
        self._in = io.BytesIO(incoming)
        self.sent = bytearray()

    def recv(self, n: int) -> bytes:
        return self._in.read(n)

    def sendall(self, data: bytes) -> None:
        self.sent.extend(data)


def _client_frame(payload: bytes, opcode: int = 0x1) -> bytes:
    """Build a masked client→server frame (browsers always mask)."""
    n = len(payload)
    if n <= 125:
        header = bytes([0x80 | opcode, 0x80 | n])
    elif n <= 65535:
        header = struct.pack(">BBH", 0x80 | opcode, 0x80 | 126, n)
    else:
        header = struct.pack(">BBQ", 0x80 | opcode, 0x80 | 127, n)
    mask = b"\x37\x42\x9a\xc1"
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    return header + mask + masked


class TestWsSend:
    def test_short_text_frame(self):
        sock = FakeSock()
        ws_send(sock, "hi")
        # 0x81 = FIN + text, 0x02 = length 2
        assert bytes(sock.sent) == b"\x81\x02hi"

    def test_string_is_utf8_encoded(self):
        sock = FakeSock()
        ws_send(sock, "hé")
        # "hé" → 3 bytes in UTF-8
        assert sock.sent[0:2] == b"\x81\x03"
        assert bytes(sock.sent[2:]) == "hé".encode()

    def test_bytes_passthrough(self):
        sock = FakeSock()
        ws_send(sock, b"\x00\x01\x02")
        assert bytes(sock.sent) == b"\x81\x03\x00\x01\x02"

    def test_medium_frame_uses_16bit_length(self):
        sock = FakeSock()
        payload = b"a" * 200
        ws_send(sock, payload)
        # 0x81, 126, then 16-bit big-endian length 200
        assert sock.sent[0] == 0x81
        assert sock.sent[1] == 126
        assert struct.unpack(">H", bytes(sock.sent[2:4]))[0] == 200
        assert bytes(sock.sent[4:]) == payload

    def test_large_frame_uses_64bit_length(self):
        sock = FakeSock()
        payload = b"x" * 70000  # > 65535 forces 64-bit length
        ws_send(sock, payload)
        assert sock.sent[0] == 0x81
        assert sock.sent[1] == 127
        assert struct.unpack(">Q", bytes(sock.sent[2:10]))[0] == 70000
        assert bytes(sock.sent[10:]) == payload

    def test_boundary_125_uses_short_form(self):
        sock = FakeSock()
        ws_send(sock, b"a" * 125)
        assert sock.sent[0:2] == b"\x81\x7d"  # 0x7d == 125
        assert len(sock.sent) == 2 + 125

    def test_boundary_126_uses_extended_form(self):
        sock = FakeSock()
        ws_send(sock, b"a" * 126)
        assert sock.sent[0] == 0x81
        assert sock.sent[1] == 126


class TestWsRecv:
    def test_decodes_masked_text_frame(self):
        sock = FakeSock(_client_frame(b"hello"))
        assert ws_recv(sock) == b"hello"

    def test_close_frame_returns_none(self):
        sock = FakeSock(_client_frame(b"", opcode=0x8))
        assert ws_recv(sock) is None

    def test_ping_frame_returns_empty(self):
        sock = FakeSock(_client_frame(b"ping-data", opcode=0x9))
        assert ws_recv(sock) == b""

    def test_pong_frame_returns_empty(self):
        sock = FakeSock(_client_frame(b"pong-data", opcode=0xA))
        assert ws_recv(sock) == b""

    def test_medium_length_payload_roundtrip(self):
        payload = b"x" * 200
        sock = FakeSock(_client_frame(payload))
        assert ws_recv(sock) == payload

    def test_oversized_frame_rejected(self):
        # Craft a header claiming a payload larger than _MAX_FRAME without
        # actually providing it — we want the size check to fire first.
        # Use 64-bit length form since _MAX_FRAME (64KB) needs > 16-bit to exceed.
        oversized = _MAX_FRAME + 1
        header = struct.pack(">BBQ", 0x81, 0x80 | 127, oversized)
        sock = FakeSock(header)  # no payload bytes follow; size check fails first
        with pytest.raises(ValueError, match="too large"):
            ws_recv(sock)

    def test_closed_socket_raises(self):
        sock = FakeSock(b"")  # nothing to read → recv returns empty → raise
        with pytest.raises(ConnectionResetError):
            ws_recv(sock)


class TestRoundtrip:
    """Server-emitted frames are unmasked; this verifies our send is parseable."""

    def test_send_produces_well_formed_text_frame(self):
        sock = FakeSock()
        ws_send(sock, "round-trip")
        # First byte: FIN + text opcode
        assert sock.sent[0] == 0x81
        # Second byte: mask bit unset, length 10
        assert sock.sent[1] == 10
        assert bytes(sock.sent[2:]) == b"round-trip"
