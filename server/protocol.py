"""WebSocket framing helpers for the nested-worlds server.

RFC 6455 behaviors that matter for a real multiplayer surface:

  * Client frames MUST be masked (§5.1) — an unmasked client frame is a
    protocol error and the connection is closed, instead of quietly
    accepting non-compliant traffic.
  * Fragmented messages (§5.4) are reassembled: a text/binary frame with
    FIN=0 accumulates continuation frames until FIN=1 and is returned as
    one payload, instead of mangling each fragment into a separate
    "message".
  * Pings (§5.5.2) are answered with pongs carrying the same payload, so
    conforming clients' keepalives work against this server.
  * Close frames are echoed before the connection is reported closed, so
    the closing handshake completes cleanly.
"""
from __future__ import annotations

import struct


_MAX_FRAME = 64 * 1024


class ProtocolError(ValueError):
    """A frame violated RFC 6455; the caller should close the connection."""


def _ws_recvall(sock, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionResetError("WebSocket connection closed")
        buf.extend(chunk)
    return bytes(buf)


def _recv_frame(sock) -> tuple[int, bool, bytes]:
    """Read one frame; return (opcode, fin, unmasked payload)."""
    header = _ws_recvall(sock, 2)
    b0, b1 = header[0], header[1]
    fin = bool(b0 & 0x80)
    opcode = b0 & 0x0F
    masked = bool(b1 & 0x80)
    length = b1 & 0x7F
    if length == 126:
        length = struct.unpack(">H", _ws_recvall(sock, 2))[0]
    elif length == 127:
        length = struct.unpack(">Q", _ws_recvall(sock, 8))[0]
    if opcode >= 0x8:
        # RFC 6455 §5.5: control frames carry at most 125 bytes of payload
        # and MUST NOT be fragmented. Before this check a 64KB "ping" was
        # accepted (and buffered) — spec-violating control traffic is an
        # attack shape, not a client to accommodate.
        if length > 125:
            raise ProtocolError("control frame payload exceeds 125 bytes")
        if not fin:
            raise ProtocolError("fragmented control frame")
    if length > _MAX_FRAME:
        raise ProtocolError("WebSocket frame too large")
    if not masked and opcode != 0x8:
        # RFC 6455 §5.1: a server MUST close the connection upon receiving
        # an unmasked client frame. (A bare unmasked close is tolerated so
        # the closing handshake can still complete.)
        raise ProtocolError("client frame not masked")
    mask_key = _ws_recvall(sock, 4) if masked else b""
    payload = bytearray(_ws_recvall(sock, length))
    if masked:
        for i in range(len(payload)):
            payload[i] ^= mask_key[i % 4]
    return opcode, fin, bytes(payload)


def ws_recv(sock, send_lock=None) -> bytes | None:
    """Return the next complete data-message payload.

    Reassembles fragmented messages, answers pings with pongs, ignores
    unsolicited pongs (returning b'' so callers treat them as a handled
    control event), and returns None once the peer closes. Raises
    ProtocolError on RFC violations — callers close the connection.

    `send_lock` serializes the pong/close echoes written from the reader
    thread against the player's writer thread (see rooms.Player) so two
    threads never interleave bytes of different frames on one socket.
    """
    fragments: list[bytes] = []
    while True:
        opcode, fin, payload = _recv_frame(sock)

        if opcode == 0x8:  # close — echo it so the handshake completes
            try:
                _send_frame(sock, 0x8, payload[:125], lock=send_lock)
            except OSError:
                pass
            return None
        if opcode == 0x9:  # ping → pong with the same payload
            try:
                _send_frame(sock, 0xA, payload[:125], lock=send_lock)
            except OSError:
                pass
            if fragments:
                continue  # §5.4: control frames may interleave a fragmented message
            return b""
        if opcode == 0xA:  # unsolicited pong — fine, nothing to do
            if fragments:
                continue
            return b""

        if opcode in (0x1, 0x2):  # text / binary
            if fragments:
                raise ProtocolError("new data frame during fragmented message")
            if fin:
                return payload
            fragments.append(payload)
        elif opcode == 0x0:  # continuation
            if not fragments:
                raise ProtocolError("continuation frame with nothing to continue")
            fragments.append(payload)
            if sum(len(f) for f in fragments) > _MAX_FRAME:
                raise ProtocolError("fragmented message too large")
            if fin:
                return b"".join(fragments)
        else:
            raise ProtocolError(f"unsupported opcode 0x{opcode:X}")


def _send_frame(sock, opcode: int, data: bytes, lock=None) -> None:
    n = len(data)
    b0 = 0x80 | opcode
    if n <= 125:
        frame = bytes([b0, n]) + data
    elif n <= 65535:
        frame = struct.pack(">BBH", b0, 126, n) + data
    else:
        frame = struct.pack(">BBQ", b0, 127, n) + data
    if lock is not None:
        with lock:
            sock.sendall(frame)
    else:
        sock.sendall(frame)


def ws_send(sock, data: str | bytes, send_lock=None) -> None:
    if isinstance(data, str):
        data = data.encode()
    _send_frame(sock, 0x1, data, lock=send_lock)
