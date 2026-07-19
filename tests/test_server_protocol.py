"""Tests for the hand-rolled WebSocket framing in server/protocol.py."""
import io
import struct

import pytest

from server.protocol import _MAX_FRAME, ProtocolError, ws_recv, ws_send


class FakeSock:
    """Minimal stand-in for a connected socket: queues recv bytes, captures sendall."""

    def __init__(self, incoming: bytes = b""):
        self._in = io.BytesIO(incoming)
        self.sent = bytearray()

    def recv(self, n: int) -> bytes:
        return self._in.read(n)

    def sendall(self, data: bytes) -> None:
        self.sent.extend(data)


def _client_frame(payload: bytes, opcode: int = 0x1, *,
                  fin: bool = True, masked: bool = True) -> bytes:
    """Build a client→server frame (browsers always mask; fin=False fragments)."""
    n = len(payload)
    b0 = (0x80 if fin else 0x00) | opcode
    mask_bit = 0x80 if masked else 0x00
    if n <= 125:
        header = bytes([b0, mask_bit | n])
    elif n <= 65535:
        header = struct.pack(">BBH", b0, mask_bit | 126, n)
    else:
        header = struct.pack(">BBQ", b0, mask_bit | 127, n)
    if not masked:
        return header + payload
    mask = b"\x37\x42\x9a\xc1"
    masked_payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    return header + mask + masked_payload


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


class TestRfcCompliance:
    """RFC 6455 behaviors: masking, fragmentation, control-frame handshakes."""

    def test_unmasked_data_frame_is_a_protocol_error(self):
        # §5.1: the server MUST close on an unmasked client frame.
        sock = FakeSock(_client_frame(b"sneaky", masked=False))
        with pytest.raises(ProtocolError, match="not masked"):
            ws_recv(sock)

    def test_unmasked_close_frame_is_tolerated(self):
        # Bare unmasked close still completes the closing handshake.
        sock = FakeSock(_client_frame(b"", opcode=0x8, masked=False))
        assert ws_recv(sock) is None

    def test_fragmented_message_is_reassembled(self):
        frames = (_client_frame(b"hel", fin=False)
                  + _client_frame(b"lo ", opcode=0x0, fin=False)
                  + _client_frame(b"world", opcode=0x0))
        sock = FakeSock(frames)
        assert ws_recv(sock) == b"hello world"

    def test_ping_interleaved_in_fragmented_message(self):
        # §5.4: control frames may arrive mid-message without losing fragments.
        frames = (_client_frame(b"hel", fin=False)
                  + _client_frame(b"keepalive", opcode=0x9)
                  + _client_frame(b"lo", opcode=0x0))
        sock = FakeSock(frames)
        assert ws_recv(sock) == b"hello"
        # The interleaved ping was still answered with a pong.
        assert sock.sent[0] == 0x8A
        assert bytes(sock.sent[2:]) == b"keepalive"


class TestControlFrameLimits:
    """§5.5: control frames carry at most 125 bytes and are never fragmented.

    Before these limits, a 64KB "ping" was accepted, buffered, and answered —
    spec-violating control traffic is an attack shape, not a client quirk.
    """

    def test_oversized_ping_is_a_protocol_error(self):
        sock = FakeSock(_client_frame(b"x" * 126, opcode=0x9))
        with pytest.raises(ProtocolError, match="control frame"):
            ws_recv(sock)
        assert not sock.sent  # no pong for spec-violating traffic

    def test_oversized_close_is_a_protocol_error(self):
        sock = FakeSock(_client_frame(b"x" * 200, opcode=0x8))
        with pytest.raises(ProtocolError, match="control frame"):
            ws_recv(sock)

    def test_boundary_125_byte_ping_is_still_ponged(self):
        payload = b"k" * 125
        sock = FakeSock(_client_frame(payload, opcode=0x9))
        assert ws_recv(sock) == b""
        assert sock.sent[0] == 0x8A and bytes(sock.sent[2:]) == payload

    def test_fragmented_control_frame_is_a_protocol_error(self):
        sock = FakeSock(_client_frame(b"", opcode=0x9, fin=False))
        with pytest.raises(ProtocolError, match="fragmented control"):
            ws_recv(sock)

    def test_continuation_without_start_is_a_protocol_error(self):
        sock = FakeSock(_client_frame(b"orphan", opcode=0x0))
        with pytest.raises(ProtocolError, match="nothing to continue"):
            ws_recv(sock)

    def test_new_data_frame_during_fragmentation_is_a_protocol_error(self):
        frames = (_client_frame(b"hel", fin=False)
                  + _client_frame(b"interloper"))  # new text frame, not continuation
        sock = FakeSock(frames)
        with pytest.raises(ProtocolError, match="during fragmented"):
            ws_recv(sock)

    def test_ping_is_answered_with_matching_pong(self):
        sock = FakeSock(_client_frame(b"are-you-there", opcode=0x9))
        assert ws_recv(sock) == b""
        assert sock.sent[0] == 0x8A  # FIN + pong
        assert sock.sent[1] == len(b"are-you-there")
        assert bytes(sock.sent[2:]) == b"are-you-there"

    def test_close_is_echoed_before_returning_none(self):
        status = struct.pack(">H", 1000)
        sock = FakeSock(_client_frame(status, opcode=0x8))
        assert ws_recv(sock) is None
        assert sock.sent[0] == 0x88  # FIN + close
        assert bytes(sock.sent[2:]) == status

    def test_unsupported_opcode_is_a_protocol_error(self):
        sock = FakeSock(_client_frame(b"", opcode=0x3))  # reserved opcode
        with pytest.raises(ProtocolError, match="unsupported opcode"):
            ws_recv(sock)

    def test_oversized_fragmented_message_rejected(self):
        half = b"x" * (_MAX_FRAME // 2 + 1)
        frames = (_client_frame(half, fin=False)
                  + _client_frame(half, opcode=0x0))
        sock = FakeSock(frames)
        with pytest.raises(ProtocolError, match="too large"):
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
