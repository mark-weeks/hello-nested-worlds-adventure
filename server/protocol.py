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
  * Each frame must finish arriving within `_FRAME_DEADLINE_SEC` of its
    first byte. The session's idle timer bounds only the gap between bytes,
    and every authorization check runs on a completed frame.
"""
from __future__ import annotations

import struct
import time


_MAX_FRAME = 64 * 1024

# Once a frame's first byte arrives, the rest of it (header and payload) must
# arrive within this many seconds, or the frame is a protocol error. The idle
# timer resets on every recv, so without this bound a client trickling one
# byte every 59 s could hold one frame open for weeks, and its session stays
# subscribed to room broadcasts without any frame completing to re-check it.
# The wait before a frame starts is still the session's idle timer. Tests
# shorten this.
_FRAME_DEADLINE_SEC = 10.0


class ProtocolError(ValueError):
    """A frame violated RFC 6455; the caller should close the connection."""


def _recv_by(sock, n: int, deadline: float, idle: float | None) -> bytes:
    """Read exactly `n` more bytes of a frame that has started, by `deadline`.

    Each recv waits for the time left before the deadline, or for the idle
    timeout if that is shorter, so a slow frame is not polled. Raises
    ProtocolError once the deadline passes; the idle timeout still raises
    TimeoutError as before.
    """
    buf = bytearray()
    while len(buf) < n:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ProtocolError("frame too slow")
        by_deadline = idle is None or remaining <= idle
        sock.settimeout(remaining if by_deadline else idle)
        try:
            chunk = sock.recv(n - len(buf))
        except TimeoutError:
            if by_deadline:
                raise ProtocolError("frame too slow") from None
            raise
        if not chunk:
            raise ConnectionResetError("WebSocket connection closed")
        buf.extend(chunk)
    return bytes(buf)


def _recv_frame(sock) -> tuple[int, bool, bytes]:
    """Read one frame; return (opcode, fin, unmasked payload).

    The wait for the frame's first byte runs under the socket's own timeout
    (the session's idle timer). From that byte on, the rest of the frame
    must arrive within `_FRAME_DEADLINE_SEC`. The socket's timeout is
    restored before this returns or raises, so the wait for the next frame
    is the idle timer again.
    """
    idle = sock.gettimeout()
    header = sock.recv(2)
    if not header:
        raise ConnectionResetError("WebSocket connection closed")
    deadline = time.monotonic() + _FRAME_DEADLINE_SEC
    try:
        return _read_frame_rest(sock, header, deadline, idle)
    finally:
        sock.settimeout(idle)


def _read_frame_rest(sock, header: bytes, deadline: float,
                     idle: float | None) -> tuple[int, bool, bytes]:
    """Parse the frame whose first bytes are `header`, reading the rest by
    `deadline`."""
    def recv(n: int) -> bytes:
        return _recv_by(sock, n, deadline, idle)

    if len(header) < 2:
        header += recv(2 - len(header))
    b0, b1 = header[0], header[1]
    fin = bool(b0 & 0x80)
    opcode = b0 & 0x0F
    masked = bool(b1 & 0x80)
    length = b1 & 0x7F
    if length == 126:
        length = struct.unpack(">H", recv(2))[0]
    elif length == 127:
        length = struct.unpack(">Q", recv(8))[0]
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
    mask_key = recv(4) if masked else b""
    payload = bytearray(recv(length))
    if masked:
        for i in range(len(payload)):
            payload[i] ^= mask_key[i % 4]
    return opcode, fin, bytes(payload)


def ws_recv(sock, send_lock=None, on_frame=None,
            before_close=None) -> bytes | None:
    """Return the next complete data-message payload.

    Reassembles fragmented messages, answers pings with pongs, ignores
    unsolicited pongs (returning b'' so callers treat them as a handled
    control event), and returns None once the peer closes. Raises
    ProtocolError on RFC violations — callers close the connection.

    `send_lock` serializes the pong/close echoes written from the reader
    thread against the player's writer thread (see rooms.Player) so two
    threads never interleave bytes of different frames on one socket.

    A frame that opens a fragmented message, and every continuation and
    interleaved control frame while it is open, is read without returning,
    so a caller's per-message checks never see them. `on_frame`, if given,
    is called before each such frame is handled; if it returns False this
    returns None at once (the caller treats that as the session ending, and
    `on_frame` is responsible for any close frame it wants sent).

    `before_close`, if given, is called when the peer's close frame arrives,
    before the echo is written, so the caller can stop its own writer first:
    no data frame may follow a close frame (§5.5.1). If it raises, the
    exception propagates and no echo is written.
    """
    fragments: list[bytes] = []
    while True:
        opcode, fin, payload = _recv_frame(sock)
        opens_message = opcode in (0x1, 0x2) and not fin
        if ((fragments or opens_message) and on_frame is not None
                and not on_frame()):
            return None

        if opcode == 0x8:  # close — echo it so the handshake completes
            if before_close is not None:
                before_close()
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


# RFC 6455 §7.4.1 status codes the server sends.
CLOSE_PROTOCOL_ERROR = 1002
CLOSE_POLICY_VIOLATION = 1008


def send_close(sock, code: int, send_lock=None) -> None:
    """Send a close frame carrying `code` (§5.5.1), no reason text.

    The caller ends the session afterwards; this does not wait for the
    peer's echo. Raises OSError if the socket is already gone.
    """
    _send_frame(sock, 0x8, struct.pack(">H", code), lock=send_lock)


def ws_send(sock, data: str | bytes, send_lock=None) -> None:
    if isinstance(data, str):
        data = data.encode()
    _send_frame(sock, 0x1, data, lock=send_lock)
