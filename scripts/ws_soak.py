"""WS soak: measure the capacity numbers instead of reasoning about them.

Usage:
    NESTED_WORLDS_MAX_WS_CONNECTIONS=96 NESTED_WORLDS_MAX_WS_PER_IP=200 \
        python main.py serve --port 8232 &
    python scripts/ws_soak.py 8232 <server-pid>

Opens N_CLIENTS concurrent WebSocket sessions against a local server running
with the production cap (96). Reference run 2026-07-05 (this hardware):
96/96 accepted, 14 shed cleanly, 0 errors, 248k broadcasts in 60s,
latency p50=6.1ms p95=13.9ms p99=30ms, RSS peak 84 MB. Each client joins, moves, and chats on an
interval; one listener measures broadcast latency end to end. Samples the
server's RSS throughout. Reports: connections accepted vs shed (503),
latency percentiles, RSS growth, errors.
"""
import base64
import json
import os
import socket
import statistics
import struct
import sys
import threading
import time

PORT = int(sys.argv[1])
SERVER_PID = int(sys.argv[2])
N_CLIENTS = 110
DURATION = 60.0
CHAT_EVERY = 2.0

accepted, shed, errors = [], [], []
latencies = []
rss_samples = []
lock = threading.Lock()
stop = threading.Event()


def client_frame(payload: bytes) -> bytes:
    n = len(payload)
    if n <= 125:
        header = bytes([0x81, 0x80 | n])
    else:
        header = struct.pack(">BBH", 0x81, 0x80 | 126, n)
    mask = os.urandom(4)
    return header + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload))


def read_frames(sock, on_msg):
    buf = b""
    sock.settimeout(1.0)
    while not stop.is_set():
        try:
            chunk = sock.recv(65536)
        except socket.timeout:
            continue
        except OSError:
            return
        if not chunk:
            return
        buf += chunk
        while len(buf) >= 2:
            length = buf[1] & 0x7F
            offset = 2
            if length == 126:
                if len(buf) < 4:
                    break
                length = int.from_bytes(buf[2:4], "big")
                offset = 4
            if len(buf) < offset + length:
                break
            payload = buf[offset:offset + length]
            buf = buf[offset + length:]
            try:
                on_msg(json.loads(payload))
            except Exception:
                pass


def run_client(i):
    try:
        s = socket.create_connection(("127.0.0.1", PORT), timeout=10)
        key = base64.b64encode(os.urandom(16)).decode()
        s.sendall((f"GET /ws?seed=99&name=Soak{i} HTTP/1.1\r\nHost: t\r\n"
                   "Upgrade: websocket\r\nConnection: Upgrade\r\n"
                   f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = s.recv(4096)
            if not chunk:
                break
            head += chunk
        status = head.split(b" ", 2)[1:2]
        if b"101" not in head.split(b"\r\n", 1)[0]:
            with lock:
                shed.append(i)
            s.close()
            return
        with lock:
            accepted.append(i)

        def on_msg(msg):
            if msg.get("type") == "chat" and msg.get("text", "").startswith("t:"):
                sent = float(msg["text"][2:])
                with lock:
                    latencies.append(time.monotonic() - sent)

        reader = threading.Thread(target=read_frames, args=(s, on_msg), daemon=True)
        reader.start()
        s.sendall(client_frame(json.dumps(
            {"type": "move", "node": "Soakpoint-11"}).encode()))
        end = time.monotonic() + DURATION
        while time.monotonic() < end and not stop.is_set():
            time.sleep(CHAT_EVERY + (i % 10) * 0.05)
            s.sendall(client_frame(json.dumps(
                {"type": "chat", "text": f"t:{time.monotonic()}"}).encode()))
        s.close()
    except Exception as exc:
        with lock:
            errors.append(f"client {i}: {type(exc).__name__} {exc}")


def sample_rss():
    while not stop.is_set():
        try:
            with open(f"/proc/{SERVER_PID}/status") as f:
                for line in f:
                    if line.startswith("VmRSS"):
                        rss_samples.append(int(line.split()[1]) // 1024)
        except OSError:
            pass
        time.sleep(3)


rss_thread = threading.Thread(target=sample_rss, daemon=True)
rss_thread.start()
threads = [threading.Thread(target=run_client, args=(i,), daemon=True)
           for i in range(N_CLIENTS)]
start = time.monotonic()
for t in threads:
    t.start()
    time.sleep(0.03)  # ~30/s ramp, a realistic joining rush
for t in threads:
    t.join(timeout=DURATION + 30)
stop.set()
time.sleep(1)

lat_sorted = sorted(latencies)
def pct(p):
    return lat_sorted[int(len(lat_sorted) * p)] * 1000 if lat_sorted else -1

print(f"clients attempted : {N_CLIENTS}")
print(f"accepted          : {len(accepted)}")
print(f"shed (non-101)    : {len(shed)}")
print(f"errors            : {len(errors)}")
for e in errors[:5]:
    print("  ", e)
print(f"chat broadcasts measured: {len(latencies)}")
if lat_sorted:
    print(f"broadcast latency ms: p50={pct(0.5):.1f} p95={pct(0.95):.1f} "
          f"p99={pct(0.99):.1f} max={lat_sorted[-1]*1000:.1f}")
if rss_samples:
    print(f"server RSS MB: start={rss_samples[0]} peak={max(rss_samples)} "
          f"end={rss_samples[-1]}")
print(f"wall time: {time.monotonic() - start:.1f}s")
