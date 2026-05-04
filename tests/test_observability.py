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


class TestAccessLogE2E:
    def test_real_request_emits_one_line(self, srv, caplog):
        with caplog.at_level(logging.INFO, logger="nested_worlds.access"):
            with urllib.request.urlopen(f"{srv}/health") as resp:
                resp.read()
        access_lines = [r for r in caplog.records
                        if r.name == "nested_worlds.access"]
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
        line = next(r for r in caplog.records
                    if r.name == "nested_worlds.access")
        payload = json.loads(line.message)
        assert payload["path"] == "/worlds"
        assert "secret" not in line.message
        assert "seed=1" not in line.message


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
