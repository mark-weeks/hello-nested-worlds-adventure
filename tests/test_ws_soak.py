"""The staging probe drives real authenticated sockets and fails on lost work."""
from __future__ import annotations

from contextlib import contextmanager
import json
import os
import shutil
import ssl
import subprocess
import threading
import time

import pytest

import persistence
from multiverse import store
from scripts import ws_soak
from server import _Handler, _ThreadedServer, guard, websocket


@contextmanager
def running_server(monkeypatch, *, clients=3, tls=None):
    monkeypatch.setenv("NESTED_WORLDS_CANONICAL_SEED", "382")
    monkeypatch.delenv("NESTED_WORLDS_TEST_WORLD", raising=False)
    monkeypatch.delenv("NESTED_WORLDS_DISABLE_MODERATION", raising=False)
    keys = ["nw_" + f"{i + 1:032x}" for i in range(clients)]
    for i, key in enumerate(keys):
        persistence.mint_invite_key(key, "Check " + ws_soak._letters(i))
    # Birth is intentionally outside a short probe's measurement window.
    store.ensure_born(382)
    requests = []

    class RecordedHandler(_Handler):
        def do_GET(self):
            requests.append((self.path, self.headers.get("X-Beta-Key") in keys))
            return super().do_GET()

    server = _ThreadedServer(("127.0.0.1", 0), RecordedHandler)
    if tls:
        server.socket = tls.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    scheme = "https" if tls else "http"
    try:
        yield f"{scheme}://127.0.0.1:{server.server_port}", keys, requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)
        deadline = time.monotonic() + 2
        while guard.WS_LIMITER.stats()["total"] and time.monotonic() < deadline:
            time.sleep(0.01)
        assert guard.WS_LIMITER.stats()["total"] == 0


def quick_config(url, clients, *, chat=True):
    return ws_soak.Config(url, clients=clients, duration=0.2, timeout=3, chat=chat)


def test_authenticated_twelve_client_cohort_uses_world_root_and_measures_broadcasts(monkeypatch):
    monkeypatch.setenv("NESTED_WORLDS_MAX_WS_PER_IP", "12")
    with running_server(monkeypatch, clients=12) as (url, keys, requests):
        summary = ws_soak.run_probe(quick_config(url, 12), keys)
    assert summary["passed"] is True
    assert summary["accepted"] == 12
    assert summary["shed_503"] == 0
    assert summary["canonical_seed"] == 382
    assert summary["clients_without_pong"] == 0
    assert summary["move_pairs_missing"] == 0
    assert summary["moves_sent"] == 12
    assert summary["move_deliveries"] == 132
    assert summary["move_deliveries_missing"] == 0
    assert summary["application_pongs_missing"] == 0
    assert summary["chat_lines_sent"] == 12
    assert summary["chat_deliveries"] == 144
    assert summary["chat_deliveries_missing"] == 0
    assert summary["chat_broadcast_ms"]["p95"] >= 0
    assert summary["application_ping_rtt_ms"]["p95"] >= 0
    assert requests[0] == ("/world?depth=2", True)
    assert len([path for path, _ in requests if path.startswith("/ws?")]) == 12
    assert all(authenticated for _, authenticated in requests)
    assert all(key not in path for path, _ in requests for key in keys)
    root = store.root_name(382)
    rows = persistence.get_mutations(382, limit=1000)
    assert sum(row["type"] == "PLAYER_JOIN" for row in rows) == 12
    assert sum(row["type"] == "PLAYER_CHAT" for row in rows) == 12
    assert {row["node"] for row in rows if row["type"] == "PLAYER_MOVE"} == {root}


def test_capacity_shedding_is_a_failed_cohort_not_a_successful_connection(monkeypatch):
    monkeypatch.setenv("NESTED_WORLDS_MAX_WS_PER_IP", "2")
    with running_server(monkeypatch) as (url, keys, _):
        summary = ws_soak.run_probe(quick_config(url, 3), keys)
    assert summary["passed"] is False
    assert summary["accepted"] == 2
    assert summary["shed_503"] == 1
    assert summary["failures"] == []


def test_an_invalid_websocket_key_is_not_misreported_as_capacity(monkeypatch):
    with running_server(monkeypatch, clients=2) as (url, keys, _):
        keys[1] = "nw_" + "f" * 32
        summary = ws_soak.run_probe(quick_config(url, 2), keys)
    assert summary["passed"] is False
    assert summary["accepted"] == 1
    assert summary["shed_503"] == 0
    assert summary["failures"] == [{"client": 2, "reason": "HTTP 403: an invite key was refused"}]
    assert keys[1] not in json.dumps(summary)


def test_missing_chat_broadcasts_fail_even_when_all_connections_and_pongs_work(monkeypatch):
    broadcast = websocket.broadcast

    def drop_chat(room, message, **kwargs):
        if message.get("type") != "chat":
            broadcast(room, message, **kwargs)

    monkeypatch.setattr(websocket, "broadcast", drop_chat)
    with running_server(monkeypatch, clients=2) as (url, keys, _):
        summary = ws_soak.run_probe(quick_config(url, 2), keys)
    assert summary["passed"] is False
    assert summary["accepted"] == 2
    assert summary["clients_without_pong"] == 0
    assert summary["chat_deliveries_missing"] == 4
    assert summary["chat_broadcast_ms"] is None


def test_no_chat_mode_needs_only_moves_and_pongs(monkeypatch):
    with running_server(monkeypatch, clients=2) as (url, keys, _):
        summary = ws_soak.run_probe(quick_config(url, 2, chat=False), keys)
    assert summary["passed"] is True
    assert summary["chat_lines_sent"] == 0
    assert summary["chat_deliveries"] == 0
    assert summary["chat_broadcast_ms"] is None
    assert summary["application_ping_rtt_ms"] is not None


def test_later_missing_move_and_pong_fail_after_a_successful_first_round(monkeypatch):
    from server.rooms import Player

    broadcast, send = websocket.broadcast, Player.send
    move_counts, pong_counts = {}, {}

    def drop_later_move(room, message, **kwargs):
        if message.get("type") == "player_move":
            session = message["session_id"]
            move_counts[session] = move_counts.get(session, 0) + 1
            if move_counts[session] > 1:
                return
        broadcast(room, message, **kwargs)

    def drop_later_pong(player, message, **kwargs):
        if message.get("type") == "pong":
            session = player.session_id
            pong_counts[session] = pong_counts.get(session, 0) + 1
            if pong_counts[session] > 1:
                return
        return send(player, message, **kwargs)

    monkeypatch.setattr(websocket, "broadcast", drop_later_move)
    monkeypatch.setattr(Player, "send", drop_later_pong)
    with running_server(monkeypatch, clients=2) as (url, keys, _):
        summary = ws_soak.run_probe(ws_soak.Config(
            url, clients=2, duration=2.2, interval=2, timeout=3, chat=False), keys)
    assert summary["passed"] is False
    assert summary["move_pairs_missing"] == 0
    assert summary["clients_without_pong"] == 0
    assert summary["move_deliveries_missing"] == 2
    assert summary["application_pongs_missing"] == 2


def test_duplicate_first_move_cannot_hide_a_lost_second_move(monkeypatch):
    broadcast = websocket.broadcast
    counts = {}

    def duplicate_then_drop(room, message, **kwargs):
        if message.get("type") == "player_move":
            session = message["session_id"]
            counts[session] = counts.get(session, 0) + 1
            if counts[session] == 1:
                broadcast(room, message, **kwargs)
            else:
                return
        broadcast(room, message, **kwargs)

    monkeypatch.setattr(websocket, "broadcast", duplicate_then_drop)
    with running_server(monkeypatch, clients=2) as (url, keys, _):
        summary = ws_soak.run_probe(ws_soak.Config(
            url, clients=2, duration=2.2, interval=2, timeout=3, chat=False), keys)
    assert summary["passed"] is False
    assert summary["moves_sent"] == summary["move_deliveries"] == 4
    assert summary["move_deliveries_missing"] == 0
    assert summary["move_pairs_missing"] == 0
    assert summary["move_order_errors"] == 2


def test_discovery_failure_and_cli_output_never_include_the_key(monkeypatch, capsys):
    secret = "nw_" + "f" * 32
    monkeypatch.setenv("ENFOLDED_SOAK_KEYS", secret)
    with running_server(monkeypatch, clients=1) as (url, _, _):
        code = ws_soak.main(["--url", url, "--clients", "1", "--duration", "0.1"])
    captured = capsys.readouterr()
    assert code == 1
    assert secret not in captured.out + captured.err
    assert json.loads(captured.out) == {
        "passed": False,
        "error": "World discovery: HTTP 403: an invite key was refused",
    }


@pytest.mark.parametrize("status, phrase", [(428, "participation notice"), (503, "participation configuration")])
def test_participation_refusals_are_diagnosed_without_accepting(monkeypatch, status, phrase):
    class Refused(_Handler):
        def do_GET(self):
            self._send_json({"error": "private upstream content"}, status=status)

    server = _ThreadedServer(("127.0.0.1", 0), Refused)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with pytest.raises(ws_soak.ProbeError, match=phrase) as caught:
            ws_soak.run_probe(quick_config(f"http://127.0.0.1:{server.server_port}", 1), ["secret"])
        assert "secret" not in str(caught.value)
        assert "private upstream content" not in str(caught.value)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)


def test_origin_and_key_validation_happens_before_any_remote_request(tmp_path):
    for url in ("http://example.com", "https://u:secret@example.com", "https://example.com?key=secret"):
        with pytest.raises(ws_soak.ProbeError) as caught:
            ws_soak.run_probe(quick_config(url, 1), ["secret"])
        assert "secret" not in str(caught.value)
    with pytest.raises(ws_soak.ProbeError, match="Hosted soaks require"):
        ws_soak.run_probe(quick_config("https://example.com", 1), [])
    with pytest.raises(ws_soak.ProbeError, match="distinct"):
        ws_soak.run_probe(quick_config("http://localhost", 2), ["same", "same"])
    path = tmp_path / "keys.txt"
    path.write_text('[' + json.dumps("first") + ',"second"]')
    assert ws_soak.load_keys(path) == ["first", "second"]
    assert ws_soak.load_keys(None, {"ENFOLDED_SOAK_KEYS": "first\nsecond\n"}) == ["first", "second"]
    with pytest.raises(ws_soak.ProbeError, match="header characters"):
        ws_soak.load_keys(None, {"ENFOLDED_SOAK_KEYS": '["bad\\r\\nheader"]'})


def test_discovery_does_not_forward_keys_to_redirect_destinations():
    requests = []

    class Redirect(_Handler):
        def do_GET(self):
            requests.append(self.path)
            self.send_response(302)
            self.send_header("Location", "/collect?private=destination")
            self.send_header("Content-Length", "0")
            self.end_headers()

    server = _ThreadedServer(("127.0.0.1", 0), Redirect)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with pytest.raises(ws_soak.ProbeError, match="HTTP 302") as caught:
            ws_soak.discover_world(f"http://127.0.0.1:{server.server_port}", "secret", 2)
        assert requests == ["/world?depth=2"]
        assert "secret" not in str(caught.value)
        assert "destination" not in str(caught.value)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)


@pytest.fixture(scope="module")
def certificate(tmp_path_factory):
    if not shutil.which("openssl"):
        pytest.skip("openssl is unavailable for the loopback TLS fixture")
    directory = tmp_path_factory.mktemp("soak-tls")
    cert, key = directory / "cert.pem", directory / "key.pem"
    subprocess.run([
        "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
        "-keyout", str(key), "-out", str(cert), "-subj", "/CN=localhost",
        "-addext", "subjectAltName=IP:127.0.0.1,DNS:localhost",
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return cert, key


def test_https_world_discovery_and_wss_use_verified_tls(monkeypatch, certificate):
    cert, key = certificate
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.load_cert_chain(cert, key)
    monkeypatch.setenv("SSL_CERT_FILE", str(cert))
    with running_server(monkeypatch, clients=2, tls=tls) as (url, keys, requests):
        summary = ws_soak.run_probe(quick_config(url, 2), keys)
    assert summary["passed"] is True
    assert summary["chat_deliveries"] == 4
    assert all(authenticated for _, authenticated in requests)


def test_an_untrusted_tls_certificate_is_refused(monkeypatch, certificate):
    cert, key = certificate
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.load_cert_chain(cert, key)
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    with running_server(monkeypatch, clients=1, tls=tls) as (url, keys, _):
        with pytest.raises(ws_soak.ProbeError, match="TLS trust"):
            ws_soak.run_probe(quick_config(url, 1), keys)


def test_local_rss_sampling_is_optional():
    result = ws_soak.Measurements()
    thread = threading.Thread(target=ws_soak._sample_rss, args=(os.getpid(), result))
    thread.start()
    time.sleep(0.03)
    result.stop.set()
    thread.join(1)
    assert result.rss_kib and result.rss_kib[0] > 0
