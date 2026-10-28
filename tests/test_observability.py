"""Coverage for observability.py + the access log + the backup CLI helper.

Sentry is exercised only at the configuration boundary — we don't import the
real SDK in tests; a no-DSN environment must produce a silent no-op, and a
DSN-set + missing-SDK environment must log a warning.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import sys
import threading
import time
import urllib.request

import pytest

import persistence
from server import _Handler, _ThreadedServer, observability


# ── Sentry init ─────────────────────────────────────────────────────────────

class TestSentryInit:
    def test_no_dsn_is_silent_noop(self, monkeypatch, caplog):
        monkeypatch.delenv("SENTRY_DSN", raising=False)
        # Force a fresh state — `_sentry_ready` may have been set by a prior
        # test in the same process.
        monkeypatch.setattr(observability, "_sentry_ready", False)
        with caplog.at_level(logging.WARNING, logger="nested_worlds"):
            observability.setup()
        assert not caplog.records  # no warning, no info, no error
        assert observability._sentry_ready is False

    def test_dsn_set_but_sdk_missing_warns(self, monkeypatch, caplog):
        monkeypatch.setenv("SENTRY_DSN", "https://fake@sentry.example/42")
        # Hide sentry_sdk from import even if it happens to be installed.
        monkeypatch.setitem(sys.modules, "sentry_sdk", None)
        monkeypatch.setattr(observability, "_sentry_ready", False)
        with caplog.at_level(logging.WARNING, logger="nested_worlds"):
            observability.setup()
        assert any("sentry_sdk is not installed" in r.message
                   for r in caplog.records)
        assert observability._sentry_ready is False


class TestCaptureExceptionFallback:
    def test_logs_traceback_when_sentry_unconfigured(self, monkeypatch, caplog):
        monkeypatch.setattr(observability, "_sentry_ready", False)
        with caplog.at_level(logging.ERROR, logger="nested_worlds"):
            try:
                raise RuntimeError("boom")
            except RuntimeError as exc:
                observability.capture_exception(exc)
        # Without Sentry configured, the helper still surfaces the exception.
        assert any("unhandled request error" in r.message
                   for r in caplog.records)


# ── Access log ──────────────────────────────────────────────────────────────

class TestAccessLog:
    def test_line_is_json_with_expected_fields(self, caplog):
        # Drive access_log directly so the test doesn't need a server fixture.
        import time
        started = time.monotonic() - 0.1  # ~100ms ago
        with caplog.at_level(logging.INFO, logger="nested_worlds.access"):
            observability.access_log(
                "POST", "/speak", 200,
                started=started, ip="9.9.9.9", length=42,
            )
        line = next(r for r in caplog.records
                    if r.name == "nested_worlds.access")
        payload = json.loads(line.message)
        assert payload["method"] == "POST"
        assert payload["path"]   == "/speak"
        assert payload["status"] == 200
        assert payload["len"]    == 42
        assert payload["ms"]     >= 50          # captured the elapsed time
        # IP must be hashed, not raw.
        assert payload["ip_h"]   != "9.9.9.9"
        assert payload["ip_h"]   == observability.hash_ip("9.9.9.9")

    def test_query_string_never_logged(self, caplog):
        # The path argument is the path component only; access_log treats it
        # as opaque, so the caller is responsible for stripping the query.
        # This test enforces that the line shape doesn't accidentally include
        # any query-shaped key.
        import time
        with caplog.at_level(logging.INFO, logger="nested_worlds.access"):
            observability.access_log(
                "GET", "/world", 200,
                started=time.monotonic(), ip="1.2.3.4",
            )
        line = next(r for r in caplog.records
                    if r.name == "nested_worlds.access")
        payload = json.loads(line.message)
        assert "?" not in payload["path"]
        assert "query" not in payload


# ── End-to-end: access log fires through real HTTP ──────────────────────────

@pytest.fixture
def srv():
    server = _ThreadedServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


def _http_responses(data: bytes) -> list[tuple[int, dict[str, str], bytes]]:
    """Split a pipelined byte stream into status, headers, and body."""
    responses = []
    rest = data
    while rest:
        head, sep, rest = rest.partition(b"\r\n\r\n")
        if not sep:
            break
        lines = head.decode("iso-8859-1").split("\r\n")
        status = int(lines[0].split(" ", 2)[1])
        headers = {}
        for line in lines[1:]:
            name, _, value = line.partition(":")
            headers[name.strip().lower()] = value.strip()
        length = int(headers.get("content-length", "0"))
        body, rest = rest[:length], rest[length:]
        responses.append((status, headers, body))
    return responses


def _access_records(caplog, timeout=2.0):
    """Collect access-log records, waiting for the handler thread.

    The access line is emitted by the request thread *after* the response
    is flushed, so the client can finish reading before the record exists —
    asserting immediately flakes on loaded CI runners.
    """
    deadline = time.monotonic() + timeout
    while True:
        recs = [r for r in caplog.records if r.name == "nested_worlds.access"]
        if recs or time.monotonic() > deadline:
            return recs
        time.sleep(0.01)


class TestAccessLogE2E:
    def test_real_request_emits_one_line(self, srv, caplog):
        with caplog.at_level(logging.INFO, logger="nested_worlds.access"):
            with urllib.request.urlopen(f"{srv}/health") as resp:
                resp.read()
            access_lines = _access_records(caplog)
        assert len(access_lines) == 1
        payload = json.loads(access_lines[0].message)
        assert payload["path"]   == "/health"
        assert payload["status"] == 200
        assert payload["method"] == "GET"

    def test_query_string_stripped_from_logged_path(self, srv, caplog):
        # `?key=...` invite secrets and any other query state must never
        # land in the access log.
        with caplog.at_level(logging.INFO, logger="nested_worlds.access"):
            with urllib.request.urlopen(f"{srv}/worlds?seed=1&secret=42") as resp:
                resp.read()
            records = _access_records(caplog)
        assert records, "no access-log line was emitted"
        line = records[0]
        payload = json.loads(line.message)
        assert payload["path"] == "/worlds"
        assert "secret" not in line.message
        assert "seed=1" not in line.message

    def test_reused_handler_logs_each_request_on_one_connection(
            self, srv, monkeypatch, caplog):
        # HTTP/1.1 reuses the handler while the socket stays open. Every
        # current response sets Connection: close, so this test leaves the
        # first response's socket open and closes on the second. Without a
        # per-request reset, the second access line is dropped.
        import socket
        from urllib.parse import urlparse
        from server.handlers import Handler

        port = urlparse(srv).port
        real = Handler._send_security_headers

        def reopen_unless_client_closes(self):
            real(self)
            if (self.headers.get("Connection") or "").lower() != "close":
                self.close_connection = False

        monkeypatch.setattr(Handler, "_send_security_headers", reopen_unless_client_closes)
        # /ideas/list sets _private_response. /health must not inherit that
        # header, the 403 status, or the 403 body length.
        request = (
            "GET /ideas/list HTTP/1.1\r\nHost: localhost\r\n\r\n"
            "GET /health HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n"
        )
        with caplog.at_level(logging.INFO, logger="nested_worlds.access"):
            sock = socket.create_connection(("127.0.0.1", port), timeout=2)
            try:
                sock.sendall(request.encode())
                sock.settimeout(2)
                data = bytearray()
                while True:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    data.extend(chunk)
            finally:
                sock.close()
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                logs = [r for r in caplog.records if r.name == "nested_worlds.access"]
                if len(logs) >= 2:
                    break
                time.sleep(0.01)
        responses = _http_responses(bytes(data))
        assert [item[0] for item in responses] == [403, 200]
        ideas_headers, health_headers = responses[0][1], responses[1][1]
        assert ideas_headers.get("cache-control") == "no-store"
        assert "cache-control" not in health_headers
        logs = [r for r in caplog.records if r.name == "nested_worlds.access"]
        assert len(logs) == 2
        payloads = [json.loads(record.message) for record in logs]
        assert [item["path"] for item in payloads] == ["/ideas/list", "/health"]
        assert [item["status"] for item in payloads] == [403, 200]
        assert payloads[0]["len"] == int(ideas_headers["content-length"])
        assert payloads[1]["len"] == int(health_headers["content-length"])
        assert payloads[0]["len"] != payloads[1]["len"]


# ── persistence.backup_to ───────────────────────────────────────────────────

class TestBackup:
    def test_backup_copies_live_data(self, tmp_path):
        # Seed a row, snapshot the DB, then verify the snapshot has the row
        # and the live DB still has it (online backup must not destroy state).
        persistence.save_world(seed=999, node_count=3, max_depth=2,
                               min_breadth=1, max_breadth=2)
        target = tmp_path / "snapshot.db"
        persistence.backup_to(target)

        assert target.exists()
        assert target.stat().st_size > 0
        with sqlite3.connect(target) as conn:
            row = conn.execute(
                "SELECT seed, node_count FROM worlds WHERE seed = 999"
            ).fetchone()
        assert row == (999, 3)

        # Live DB still readable.
        worlds = persistence.list_worlds()
        assert any(w["seed"] == 999 for w in worlds)

    def test_backup_creates_parent_dirs(self, tmp_path):
        # Operators wire `backup --to /backups/$(date).db` — the parent
        # directory may not exist yet on a fresh host.
        target = tmp_path / "nested" / "deeper" / "snap.db"
        persistence.backup_to(target)
        assert target.exists()

    def test_backup_is_owner_only(self, tmp_path):
        import stat
        target = tmp_path / "snap.db"
        persistence.backup_to(target)
        mode = target.stat().st_mode & 0o777
        # 0o600 — same posture as the live DB.
        assert mode == stat.S_IRUSR | stat.S_IWUSR
