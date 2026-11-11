"""Measure an authenticated cohort on a disposable staging world.

    .venv/bin/python scripts/ws_soak.py --url https://enfolded-staging.fly.dev \
        --clients 12 --keys-file /private/soak-keys.txt --duration 60

Accept the participation notice with each check identity first. Keys are one per
line or a JSON array, also accepted via ENFOLDED_SOAK_KEYS. They travel only in
X-Beta-Key headers. Use dedicated identities: joins, moves and chat are recorded.
Every mode requires a ready temporary-world notice. --permanent-world-ok
explicitly permits a rehearsal on a permanent world. --no-chat suppresses authored
lines only: joins and moves are still recorded, and the world guard still applies.
A single source needs a staging-only per-IP socket cap >= --clients (default 8).
Run ./setup.sh for the pinned dev WebSocket client. TLS and proxies stay enabled.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import ipaddress
import json
import logging
import math
import os
from pathlib import Path
import secrets
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from websockets.exceptions import ConnectionClosed, InvalidStatus
from websockets.sync.client import connect


class ProbeError(Exception):
    """A bounded diagnostic without credentials or upstream response bodies."""


@dataclass(frozen=True)
class Config:
    url: str = "http://127.0.0.1:8232"
    clients: int = 12
    duration: float = 60.0
    interval: float = 3.0
    timeout: float = 10.0
    chat: bool = True
    server_pid: int | None = None
    permanent_world_ok: bool = False


@dataclass
class Measurements:
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    ready: threading.Condition = field(default_factory=threading.Condition, repr=False)
    start: threading.Event = field(default_factory=threading.Event, repr=False)
    stop: threading.Event = field(default_factory=threading.Event, repr=False)
    attempted: int = 0
    accepted: set[int] = field(default_factory=set)
    shed: set[int] = field(default_factory=set)
    failures: dict[int, str] = field(default_factory=dict)
    sessions: dict[str, int] = field(default_factory=dict)
    chat_sent: dict[str, tuple[float, int]] = field(default_factory=dict)
    chat_seen: set[tuple[int, str]] = field(default_factory=set)
    chat_extra: int = 0
    moves_seen: set[tuple[int, int]] = field(default_factory=set)
    moves_sent: int = 0
    move_deliveries: int = 0
    move_targets: dict[int, list[str]] = field(default_factory=dict)
    move_receipts: dict[tuple[int, int], int] = field(default_factory=dict)
    move_order_errors: int = 0
    pings_sent: int = 0
    pongs: dict[int, int] = field(default_factory=dict)
    ping_ms: list[float] = field(default_factory=list)
    broadcast_ms: list[float] = field(default_factory=list)
    rss_kib: list[int] = field(default_factory=list)
    began: float = 0.0


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward the invite header to a redirect destination.
        return None


def endpoint(url: str) -> tuple[str, str, bool]:
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        parsed.port
        if (parsed.scheme not in {"http", "https"} or not hostname
                or parsed.username is not None or parsed.password is not None
                or parsed.path not in {"", "/"} or parsed.query or parsed.fragment):
            raise ValueError
        try:
            local = ipaddress.ip_address(hostname).is_loopback
        except ValueError:
            local = hostname.lower() == "localhost"
        if parsed.scheme == "http" and not local:
            raise ValueError
        origin = urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
        ws_origin = urlunsplit(("wss" if parsed.scheme == "https" else "ws",
                               parsed.netloc, "", "", ""))
        return origin, ws_origin, local
    except ValueError:
        raise ProbeError("Use an HTTPS origin, or HTTP loopback, without credentials, path or query.") from None


def load_keys(path: Path | None, environ=None) -> list[str]:
    environ = os.environ if environ is None else environ
    try:
        raw = path.read_text() if path else environ.get("ENFOLDED_SOAK_KEYS", "")
        keys = json.loads(raw) if raw.lstrip().startswith("[") else raw.splitlines()
    except (OSError, ValueError):
        raise ProbeError("Could not read invite keys; use one per line or a JSON array of strings.") from None
    if not isinstance(keys, list) or any(not isinstance(k, str) for k in keys):
        raise ProbeError("Invite keys must be strings.")
    keys = [key.strip() for key in keys if key.strip()]
    if any(any(ord(c) < 33 or ord(c) > 126 for c in key) for key in keys):
        raise ProbeError("An invite key contains invalid header characters.")
    if len(set(keys)) != len(keys):
        raise ProbeError("Use a distinct invite key for every client.")
    return keys


def _http_diagnostic(status: int) -> str:
    if status == 403:
        return "HTTP 403: an invite key was refused"
    if status == 428:
        return "HTTP 428: accept the current participation notice with this check identity first"
    if status == 503:
        return "HTTP 503: service unavailable; check connection caps and participation configuration"
    return f"HTTP {status}"


def _get_json(origin: str, path: str, key: str, timeout: float, label: str):
    request = Request(origin + path, headers={"X-Beta-Key": key} if key else {})
    try:
        with build_opener(_NoRedirect()).open(request, timeout=timeout) as response:
            raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ProbeError(label + " response exceeded the probe's 1 MiB limit.")
        return json.loads(raw)
    except HTTPError as exc:
        diagnostic = _http_diagnostic(exc.code)
        exc.close()
        raise ProbeError(label + ": " + diagnostic) from None
    except (URLError, TimeoutError, OSError):
        raise ProbeError(label + " failed; check the origin, TLS trust and connectivity.") from None
    except (ValueError, UnicodeError):
        raise ProbeError(label + " returned an invalid JSON document.") from None


def _world_preflight(origin: str, timeout: float, permanent_world_ok: bool) -> str:
    # This public read carries no credential and cannot accept on anyone's
    # behalf. Fail before /world (which can birth a world) or a WS join.
    metadata = _get_json(origin, "/participation", "", timeout, "World preflight")
    if (not isinstance(metadata, dict) or type(metadata.get("required")) is not bool
            or type(metadata.get("ready")) is not bool):
        raise ProbeError("World preflight returned invalid participation metadata.")
    if not metadata["ready"]:
        raise ProbeError("World preflight: the participation notice is not ready.")
    if metadata["required"]:
        if not isinstance(metadata.get("revision"), str) or not metadata["revision"].strip():
            raise ProbeError("World preflight returned invalid participation metadata.")
        return "temporary"
    if not permanent_world_ok:
        raise ProbeError("The probe requires a declared temporary world; explicitly allow a permanent-world rehearsal with --permanent-world-ok.")
    return "explicit permanent-world override"


def discover_world(origin: str, key: str, timeout: float) -> tuple[int, tuple[str, str]]:
    world = _get_json(origin, "/world?depth=2", key, timeout, "World discovery")
    try:
        root = world["world"]
        seed, name = world["seed"], root["name"]
        child = next(child for child in root["children"] if child["level"] != "Room")
        alternate = child["name"]
        if (isinstance(seed, bool) or not isinstance(seed, int)
                or not isinstance(name, str) or not name
                or not isinstance(alternate, str) or not alternate or alternate == name
                or root["level"] == "Room"):
            raise ValueError
        return seed, (name, alternate)
    except (KeyError, TypeError, ValueError, StopIteration):
        raise ProbeError("World discovery returned an invalid world document.") from None


def _letters(value: int) -> str:
    result = ""
    while True:
        result = chr(ord("a") + value % 26) + result
        value = value // 26 - 1
        if value < 0:
            return result


def _client(index: int, key: str, config: Config, ws_origin: str,
            seed: int, nodes: tuple[str, str], marker: str, result: Measurements) -> None:
    attempted = False
    logger = logging.Logger("enfolded-soak-websocket")
    logger.addHandler(logging.NullHandler())
    try:
        query = urlencode({"seed": seed, "name": "Soak " + _letters(index)})
        # The pinned real client validates RFC 6455, handles pings/close and
        # verifies TLS. No exception text or request headers reach the report.
        with connect(ws_origin + "/ws?" + query,
                     additional_headers={"X-Beta-Key": key} if key else {},
                     compression=None, ping_interval=None, max_queue=64,
                     open_timeout=config.timeout, close_timeout=1,
                     logger=logger) as ws:
            welcome = json.loads(ws.recv(timeout=config.timeout))
            if welcome.get("type") != "welcome" or not welcome.get("session_id"):
                raise ProbeError("No valid welcome frame")
            with result.lock:
                result.accepted.add(index)
                result.sessions[welcome["session_id"]] = index
                result.pongs[index] = 0
                result.move_targets[index] = []
            with result.ready:
                result.attempted += 1
                attempted = True
                result.ready.notify_all()
            while not result.start.wait(0.1):
                if result.stop.is_set():
                    return
            end = result.began + config.duration
            drain_end = end + min(config.timeout, 2.0)
            next_send, pending_ping, sequence = result.began, None, 0
            while not result.stop.is_set() and time.monotonic() < drain_end:
                now = time.monotonic()
                if pending_ping is not None and now - pending_ping > config.timeout:
                    raise ProbeError("Application pong timed out")
                if now < end and now >= next_send:
                    if pending_ping is None:
                        pending_ping = time.monotonic()
                        with result.lock:
                            result.pings_sent += 1
                        ws.send('{"type":"ping"}')
                    with result.lock:
                        result.moves_sent += 1
                        node = nodes[sequence % len(nodes)]
                        result.move_targets[index].append(node)
                    ws.send(json.dumps({"type": "move", "node": node}))
                    if config.chat:
                        text = f"A traveler pauses to listen. {marker} {_letters(index)} {_letters(sequence)}."
                        with result.lock:
                            result.chat_sent[text] = (time.monotonic(), index)
                        ws.send(json.dumps({"type": "chat", "text": text}))
                    sequence += 1
                    next_send = now + config.interval
                try:
                    raw = ws.recv(timeout=min(0.1, max(drain_end - time.monotonic(), 0.001)))
                except TimeoutError:
                    continue
                message = json.loads(raw)
                kind = message.get("type")
                with result.lock:
                    if kind == "pong" and pending_ping is not None:
                        result.ping_ms.append((time.monotonic() - pending_ping) * 1000)
                        result.pongs[index] += 1
                        pending_ping = None
                    elif kind == "player_move" and message.get("session_id") in result.sessions:
                        sender = result.sessions[message["session_id"]]
                        pair = (index, sender)
                        result.moves_seen.add(pair)
                        result.move_deliveries += 1
                        position = result.move_receipts.get(pair, 0)
                        expected = result.move_targets[sender]
                        if position >= len(expected) or message.get("node") != expected[position]:
                            result.move_order_errors += 1
                        result.move_receipts[pair] = position + 1
                    elif kind == "chat" and message.get("text") in result.chat_sent:
                        sent, sender = result.chat_sent[message["text"]]
                        if result.sessions.get(message.get("session_id")) != sender:
                            continue
                        receipt = (index, message["text"])
                        if receipt in result.chat_seen:
                            result.chat_extra += 1
                        else:
                            result.chat_seen.add(receipt)
                            result.broadcast_ms.append((time.monotonic() - sent) * 1000)
                    elif kind == "move_denied":
                        raise ProbeError("Movement between the discovered places was refused")
                    elif kind == "chat_declined":
                        raise ProbeError("The moderation screen held or declined a probe line")
    except InvalidStatus as exc:
        with result.lock:
            if exc.response.status_code == 503:
                result.shed.add(index)
            else:
                result.failures[index] = _http_diagnostic(exc.response.status_code)
    except ProbeError as exc:
        with result.lock:
            result.failures[index] = str(exc)
    except ConnectionClosed:
        with result.lock:
            result.failures[index] = "WebSocket closed before the soak finished"
    except Exception as exc:
        with result.lock:
            result.failures[index] = "Connection or protocol failure (" + type(exc).__name__ + ")"
    finally:
        if not attempted:
            with result.ready:
                result.attempted += 1
                result.ready.notify_all()


def _sample_rss(pid: int, result: Measurements) -> None:
    while not result.stop.is_set():
        try:
            for line in Path(f"/proc/{pid}/status").read_text().splitlines():
                if line.startswith("VmRSS:"):
                    result.rss_kib.append(int(line.split()[1]))
                    break
        except (OSError, ValueError):
            return
        result.stop.wait(0.5)


def _percentiles(values: list[float]) -> dict | None:
    if not values:
        return None
    ordered = sorted(values)
    return {name: round(ordered[min(math.ceil(len(ordered) * fraction) - 1,
                                    len(ordered) - 1)], 2)
            for name, fraction in (("p50", 0.5), ("p95", 0.95), ("p99", 0.99), ("max", 1.0))}


def run_probe(config: Config, keys: list[str]) -> dict:
    origin, ws_origin, local = endpoint(config.url)
    if (config.clients < 1 or any(not math.isfinite(n) or n <= 0
                                for n in (config.duration, config.interval, config.timeout))):
        raise ProbeError("Clients, duration, interval and timeout must be positive finite values.")
    if config.interval < 2:
        raise ProbeError("Use an interval of at least 2 seconds to respect per-person chat limits.")
    if keys and (len(keys) < config.clients or len(set(keys[:config.clients])) != config.clients):
        raise ProbeError("Provide one distinct invite key per client.")
    if not keys and not local:
        raise ProbeError("Hosted soaks require one invite key per client in a key file or ENFOLDED_SOAK_KEYS.")
    world_status = _world_preflight(origin, config.timeout, config.permanent_world_ok)
    seed, nodes = discover_world(origin, keys[0] if keys else "", config.timeout)
    result = Measurements()
    marker = "soak" + "".join("ab"[b % 2] for b in secrets.token_bytes(24))
    threads = [threading.Thread(target=_client, args=(i, keys[i] if keys else "",
               config, ws_origin, seed, nodes, marker, result), daemon=True)
               for i in range(config.clients)]
    sampler = (threading.Thread(target=_sample_rss, args=(config.server_pid, result), daemon=True)
               if config.server_pid else None)
    began = time.monotonic()
    try:
        if sampler:
            sampler.start()
        for thread in threads:
            thread.start()
        deadline = time.monotonic() + config.timeout * 2 + 1
        with result.ready:
            while result.attempted < config.clients:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ProbeError("Client connection attempts did not finish before the deadline.")
                result.ready.wait(remaining)
        result.began = time.monotonic()
        result.start.set()
        for thread in threads:
            thread.join(max(0.01, result.began + config.duration + config.timeout + 4 - time.monotonic()))
        if any(thread.is_alive() for thread in threads):
            raise ProbeError("A probe client did not stop before the deadline.")
    finally:
        result.stop.set()
        result.start.set()
        for thread in threads:
            if thread.ident:
                thread.join(config.timeout + 1)
        if sampler:
            sampler.join(1)
    missing_moves = len(result.accepted) * max(0, len(result.accepted) - 1) - len(result.moves_seen)
    move_differences = [len(result.move_targets[sender]) - result.move_receipts.get((observer, sender), 0)
                        for sender in result.accepted for observer in result.accepted if sender != observer]
    missing_move_deliveries = sum(max(0, n) for n in move_differences)
    extra_move_deliveries = sum(max(0, -n) for n in move_differences)
    missing_chats = len(result.chat_sent) * len(result.accepted) - len(result.chat_seen)
    missing_pongs = sum(result.pongs.get(index, 0) == 0 for index in result.accepted)
    missing_pong_deliveries = result.pings_sent - sum(result.pongs.values())
    passed = (len(result.accepted) == config.clients and not result.failures
              and not result.shed and missing_moves == 0 and missing_chats == 0
              and missing_pongs == 0 and missing_move_deliveries == 0
              and missing_pong_deliveries == 0 and extra_move_deliveries == 0
              and result.move_order_errors == 0 and result.chat_extra == 0)
    return {
        "passed": passed, "clients_attempted": config.clients,
        "accepted": len(result.accepted), "shed_503": len(result.shed),
        "failures": [{"client": i + 1, "reason": result.failures[i]} for i in sorted(result.failures)],
        "canonical_seed": seed, "move_pairs_missing": missing_moves,
        "moves_sent": result.moves_sent, "move_deliveries": result.move_deliveries,
        "move_deliveries_missing": missing_move_deliveries,
        "move_deliveries_extra": extra_move_deliveries,
        "move_order_errors": result.move_order_errors,
        "clients_without_pong": missing_pongs,
        "application_pongs_missing": missing_pong_deliveries,
        "world_status": world_status,
        "chat_lines_sent": len(result.chat_sent),
        "chat_deliveries": len(result.chat_seen) + result.chat_extra,
        "chat_deliveries_unique": len(result.chat_seen),
        "chat_deliveries_extra": result.chat_extra,
        "chat_deliveries_missing": missing_chats,
        "application_ping_rtt_ms": _percentiles(result.ping_ms),
        "chat_broadcast_ms": _percentiles(result.broadcast_ms),
        "server_rss_mib": ({"start": round(result.rss_kib[0] / 1024, 2),
                            "peak": round(max(result.rss_kib) / 1024, 2),
                            "end": round(result.rss_kib[-1] / 1024, 2)} if result.rss_kib else None),
        "elapsed_seconds": round(time.monotonic() - began, 2),
        "capacity_note": "One source needs a staging-only per-IP socket cap at least as large as the client count.",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default="http://127.0.0.1:8232", help="HTTP(S) origin of the disposable test world")
    parser.add_argument("--clients", type=int, default=12)
    parser.add_argument("--duration", type=float, default=60)
    parser.add_argument("--interval", type=float, default=3, help="Seconds between moves/chat, at least 2")
    parser.add_argument("--timeout", type=float, default=10)
    parser.add_argument("--keys-file", type=Path, help="Private file with one key per line or a JSON array")
    parser.add_argument("--no-chat", action="store_true", help="Measure moves and ping RTT without sending chat")
    parser.add_argument("--permanent-world-ok", action="store_true",
                        help="Explicitly permit recorded joins, moves and any enabled chat on a permanent world")
    parser.add_argument("--server-pid", type=int, help="Optional local server PID for Linux RSS sampling")
    args = parser.parse_args(argv)
    try:
        summary = run_probe(Config(args.url, args.clients, args.duration, args.interval,
                                   args.timeout, not args.no_chat, args.server_pid,
                                   args.permanent_world_ok),
                            load_keys(args.keys_file))
    except ProbeError as exc:
        print(json.dumps({"passed": False, "error": str(exc)}, sort_keys=True))
        return 1
    except KeyboardInterrupt:
        print(json.dumps({"passed": False, "error": "Probe interrupted"}, sort_keys=True))
        return 130
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
