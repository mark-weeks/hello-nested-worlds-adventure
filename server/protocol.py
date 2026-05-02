"""WebSocket framing helpers for the nested-worlds server."""
from __future__ import annotations

import struct


_MAX_FRAME = 64 * 1024


def _ws_recvall(sock, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionResetError("WebSocket connection closed")
        buf.extend(chunk)
    return bytes(buf)


def ws_recv(sock) -> bytes | None:
    """Return next data-frame payload, b'' for control frames, None on close."""
    header = _ws_recvall(sock, 2)
    b0, b1 = header[0], header[1]
    opcode = b0 & 0x0F
    masked = bool(b1 & 0x80)
    length = b1 & 0x7F
    if length == 126:
        length = struct.unpack(">H", _ws_recvall(sock, 2))[0]
    elif length == 127:
        length = struct.unpack(">Q", _ws_recvall(sock, 8))[0]
    if length > _MAX_FRAME:
        raise ValueError("WebSocket frame too large")
    mask_key = _ws_recvall(sock, 4) if masked else b""
    payload = bytearray(_ws_recvall(sock, length))
    if masked:
        for i in range(len(payload)):
            payload[i] ^= mask_key[i % 4]
    if opcode == 0x8:  # close frame
        return None
    if opcode in (0x9, 0xA):  # ping / pong — discard payload
        return b""
    return bytes(payload)


def ws_send(sock, data: str | bytes) -> None:
    if isinstance(data, str):
        data = data.encode()
    n = len(data)
    if n <= 125:
        frame = bytes([0x81, n]) + data
    elif n <= 65535:
        frame = struct.pack(">BBH", 0x81, 126, n) + data
    else:
        frame = struct.pack(">BBQ", 0x81, 127, n) + data
    sock.sendall(frame)
