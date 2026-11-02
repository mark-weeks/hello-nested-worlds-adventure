"""The owner can suspend or ban a player, with a reason, an expiry and a lift.

Beta checklist G5. Before this suite, `invite revoke` was the only sanction:
permanent, name-burning, and with no recorded reason. A sanction is keyed
to the participant, refuses every credential of that participant while it
is active (the same 403 as a revoked key, no reason disclosed), closes an
open socket at its next frame, never reopens the invite gate, and ends by
expiry or lift with the same credential and the same participant (journal
intact). Every test drives the real store, server, socket or CLI.
"""
from __future__ import annotations

import datetime
import json
import logging
from contextlib import contextmanager
import sqlite3
import threading
import time
import urllib.error
import urllib.request

import pytest

import main
import persistence
from persistence import participants, sanctions
from server import guard
from tests.test_day_one_recording import _ws_connect, _ws_send_json
from tests.test_ws_credential_lifetime import (
    _join,
    _rows,
    _until_close,
    _until_eof,
    _until_type,
    _wait_rows,
)

KEY_A = "nw_" + "a" * 32
KEY_B = "nw_" + "b" * 32
KEY_C = "nw_" + "c" * 32
HOUR = datetime.timedelta(hours=1)


@pytest.fixture()
def srv():
    from server import _Handler, _ThreadedServer
    server = _ThreadedServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_address[1]
    server.shutdown()
    server.server_close()
    thread.join(5)


def _get(port, path, key=None):
    """(status, content type, parsed JSON body) for one real HTTP request."""
    headers = {"X-Beta-Key": key} if key is not None else {}
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", headers=headers)
    try:
        response = urllib.request.urlopen(req, timeout=10)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        return (response.status, response.headers.get_content_type(),
                json.loads(response.read()))


@contextmanager
def _db():
    persistence.init_db()
    conn = sqlite3.connect(persistence._DB_PATH)
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def _table(name):
    with _db() as conn:
        return conn.execute(f"SELECT * FROM {name} ORDER BY 1").fetchall()


def _count(table):
    with _db() as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def _insert_suspension(participant_id, created, expires, reason="test window"):
    """A suspension at stated SQLite-relative times (e.g. '-2 hours')."""
    with _db() as conn:
        cur = conn.execute(
            """INSERT INTO sanctions (participant_id, kind, reason, created_at, expires_at)
               VALUES (?, 'suspension', ?, datetime('now', ?), datetime('now', ?))""",
            (participant_id, reason, created, expires))
        return cur.lastrowid


def _seconds_between(a, b):
    fmt = "%Y-%m-%d %H:%M:%S"
    return (datetime.datetime.strptime(b, fmt)
            - datetime.datetime.strptime(a, fmt)).total_seconds()


def _mint_two():
    persistence.mint_invite_key(KEY_A, "Ada")
    persistence.mint_invite_key(KEY_B, "Bea")


# ── Schema: the CHECK constraints are the backstop ──────────────────────────


class TestSchema:
    VALID = "VALUES ('p1', 'suspension', 'spam', datetime('now'), datetime('now', '+1 hour'))"

    @pytest.mark.parametrize("values", [
        "('p1', 'suspension', '', datetime('now'), datetime('now', '+1 hour'))",
        "('p1', 'suspension', ' ' || char(9, 10, 13), datetime('now'), datetime('now', '+1 hour'))",
        "('p1', 'suspension', NULL, datetime('now'), datetime('now', '+1 hour'))",
        "('p1', 'warning', 'spam', datetime('now'), datetime('now', '+1 hour'))",
        "('p1', 'suspension', 'spam', datetime('now'), NULL)",
        "('p1', 'ban', 'spam', datetime('now'), datetime('now', '+1 hour'))",
        "('p1', 'suspension', 'spam', datetime('now'), datetime('now'))",
        "('p1', 'suspension', 'spam', datetime('now'), datetime('now', '-1 hour'))",
        "('p1', 'suspension', 'spam', datetime('now'), '2999-01-01T00:00:00')",
        "('p1', 'suspension', 'spam', datetime('now'), 'never')",
        "('p1', 'ban', 'spam', 'yesterday', NULL)",
        "(NULL, 'ban', 'spam', datetime('now'), NULL)",
    ], ids=["empty-reason", "blank-reason", "null-reason", "unknown-kind",
            "suspension-without-expiry", "ban-with-expiry", "zero-length",
            "ends-before-it-begins", "non-canonical-time", "garbage-time",
            "garbage-created", "no-participant"])
    def test_malformed_sanctions_are_refused(self, values):
        with _db() as conn:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO sanctions (participant_id, kind, reason, created_at, "
                    f"expires_at) VALUES {values}")
        assert _count("sanctions") == 0

    def test_well_formed_rows_insert_and_lifts_are_once_with_a_reason(self):
        with _db() as conn:
            conn.execute("INSERT INTO sanctions (participant_id, kind, reason, created_at, "
                         f"expires_at) {self.VALID}")
            conn.execute("INSERT INTO sanctions (participant_id, kind, reason) "
                         "VALUES ('p1', 'ban', 'threats')")
            for bad in ("''", "'  '", "NULL"):
                with pytest.raises(sqlite3.IntegrityError):
                    conn.execute(f"INSERT INTO sanction_lifts (sanction_id, reason) VALUES (1, {bad})")
            conn.execute("INSERT INTO sanction_lifts (sanction_id, reason) VALUES (1, 'appeal')")
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute("INSERT INTO sanction_lifts (sanction_id, reason) VALUES (1, 'again')")
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute("INSERT INTO sanction_lifts (sanction_id, reason, lifted_at) "
                             "VALUES (2, 'x', 'soon')")
        assert [r[2] for r in _table("sanctions")] == ["suspension", "ban"]
        assert [(r[0], r[1]) for r in _table("sanction_lifts")] == [(1, "appeal")]

    def test_upgrade_from_0028_keeps_every_existing_row_and_key(self, monkeypatch):
        migrations = persistence._list_migrations()
        assert migrations[-1][1].name == "0029_sanctions.sql"
        monkeypatch.setattr(persistence, "_list_migrations",
                            lambda: [m for m in migrations if m[0] <= 28])
        persistence.mint_invite_key(KEY_A, "Ada")
        # Enrol the participant as identify() does; identify() itself reads
        # the sanction tables, which a 0028 database does not have yet.
        with persistence.transaction() as conn:
            owner = participants._ensure(conn, persistence._credential_digest(KEY_A))
        participants.save_note(owner, 382, "Room-1", "kept", "note-0001")
        persistence.record_mutation(382, "Room-1", "PLAYER_CHAT", "Ada", {"text": "hi"})
        before = {t: _table(t) for t in ("invite_keys", "participants",
                                         "participant_credentials", "journal_notes",
                                         "world_mutations")}
        with _db() as conn:
            assert conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0] == 28
            assert not conn.execute("SELECT 1 FROM sqlite_master WHERE name='sanctions'").fetchone()

        monkeypatch.setattr(persistence, "_list_migrations", lambda: migrations)
        persistence._initialized.discard(persistence._DB_PATH)
        persistence.init_db()
        with _db() as conn:
            assert conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0] == 29
        assert {t: _table(t) for t in before} == before
        assert participants.identify(KEY_A)["id"] == owner
        assert persistence.lookup_invite_key(KEY_A)["name"] == "Ada"


# ── Persistence: suspend, ban, lift, expiry, list ───────────────────────────


class TestSuspensionAndBan:
    def test_suspension_records_reason_and_expiry_and_refuses_the_credential(self):
        _mint_two()
        owner = participants.identify(KEY_A)["id"]
        s = sanctions.suspend("Ada", 2 * HOUR, "  spam in the commons  ")
        assert (s["kind"], s["status"], s["name"], s["participant"]) == (
            "suspension", "active", "Ada", owner)
        assert s["reason"] == "spam in the commons"
        assert _seconds_between(s["created_at"], s["expires_at"]) == 7200
        assert persistence.lookup_invite_key(KEY_A) is None
        with pytest.raises(participants.Unauthorized):
            participants.identify(KEY_A)
        assert sanctions.is_sanctioned(owner)
        assert [x["id"] for x in sanctions.active_sanctions(owner)] == [s["id"]]
        # Only Ada: Bea's credential is untouched.
        assert persistence.lookup_invite_key(KEY_B)["name"] == "Bea"
        assert participants.identify(KEY_B)["name"] == "Bea"

    def test_ban_lasts_until_lifted(self):
        _mint_two()
        b = sanctions.ban("ada", "threats")  # names match case-insensitively
        assert (b["kind"], b["expires_at"], b["status"]) == ("ban", None, "active")
        assert persistence.lookup_invite_key(KEY_A) is None
        lifted = sanctions.lift(b["id"], "reviewed; reinstated")
        assert (lifted["status"], lifted["lift_reason"]) == ("lifted", "reviewed; reinstated")
        assert persistence.lookup_invite_key(KEY_A)["name"] == "Ada"

    def test_a_player_who_never_signed_in_gets_one_participant(self):
        persistence.mint_invite_key(KEY_A, "Ada")
        assert _count("participants") == 0
        b = sanctions.ban("Ada", "pre-emptive")
        assert _count("participants") == 1
        with pytest.raises(participants.Unauthorized):
            participants.identify(KEY_A)
        sanctions.lift(b["id"], "mistake")
        assert participants.identify(KEY_A)["id"] == b["participant"]
        assert _count("participants") == 1

    def test_a_participant_id_resolves_and_an_ambiguous_target_is_refused(self):
        _mint_two()
        bea = participants.identify(KEY_B)["id"]
        assert sanctions.suspend(bea, HOUR, "by id")["name"] == "Bea"
        # A player named exactly like another player's participant id.
        persistence.mint_invite_key(KEY_C, bea)
        rows = _table("sanctions")
        with pytest.raises(ValueError, match="ambiguous|both"):
            sanctions.ban(bea, "which one?")
        assert _table("sanctions") == rows

    def test_expired_suspension_no_longer_refuses_and_cannot_be_lifted(self):
        _mint_two()
        owner = participants.identify(KEY_A)["id"]
        sid = _insert_suspension(owner, "-2 hours", "-1 hour")
        assert persistence.lookup_invite_key(KEY_A)["name"] == "Ada"
        assert participants.identify(KEY_A)["id"] == owner
        assert not sanctions.is_sanctioned(owner)
        assert sanctions.list_sanctions() == []
        assert [(r["id"], r["status"]) for r in sanctions.list_sanctions(include_all=True)] == [
            (sid, "expired")]
        with pytest.raises(ValueError, match="already ended"):
            sanctions.lift(sid, "too late")
        assert _table("sanction_lifts") == []

    def test_a_suspension_ends_on_its_own_when_it_expires(self):
        persistence.mint_invite_key(KEY_A, "Ada")
        owner = participants.identify(KEY_A)["id"]
        participants.save_note(owner, 382, "Room-1", "written before", "note-0001")
        _insert_suspension(owner, "+0 seconds", "+3 seconds")
        assert persistence.lookup_invite_key(KEY_A) is None
        with pytest.raises(participants.Unauthorized):
            participants.identify(KEY_A)
        deadline = time.monotonic() + 8
        while persistence.lookup_invite_key(KEY_A) is None:
            assert time.monotonic() < deadline, "the suspension never expired"
            time.sleep(0.1)
        # No operator action: the same key is the same participant again.
        assert participants.identify(KEY_A) == {"id": owner, "name": "Ada"}
        assert [n["text"] for n in participants.notes(owner, 382)] == ["written before"]

    def test_lift_restores_the_same_participant_with_journal_and_profile(self):
        _mint_two()
        owner = participants.identify(KEY_A)["id"]
        participants.save_note(owner, 382, "Room-1", "Where the signal hid", "note-0001")
        participants.save_profile(owner, {"bio": "Cartographer", "published": True})
        s = sanctions.suspend("Ada", 24 * HOUR, "cooling off")
        with pytest.raises(participants.Unauthorized):
            participants.identify(KEY_A)
        sanctions.lift(s["id"], "early release")
        assert participants.identify(KEY_A) == {"id": owner, "name": "Ada"}
        assert [n["text"] for n in participants.notes(owner, 382)] == ["Where the signal hid"]
        assert participants.profile(owner)["bio"] == "Cartographer"

    def test_rotating_the_key_does_not_escape_the_sanction(self):
        persistence.mint_invite_key(KEY_A, "Ada")
        owner = participants.identify(KEY_A)["id"]
        s = sanctions.suspend("Ada", HOUR, "spam")
        participants.rotate(KEY_A, KEY_C)
        assert persistence.lookup_invite_key(KEY_C) is None
        with pytest.raises(participants.Unauthorized):
            participants.identify(KEY_C)
        sanctions.lift(s["id"], "done")
        assert participants.identify(KEY_C)["id"] == owner

    def test_overlapping_sanctions_each_have_to_end(self):
        persistence.mint_invite_key(KEY_A, "Ada")
        s = sanctions.suspend("Ada", HOUR, "spam")
        b = sanctions.ban("Ada", "then threats")
        assert [x["id"] for x in sanctions.list_sanctions()] == [b["id"], s["id"]]
        sanctions.lift(b["id"], "ban overturned")
        assert persistence.lookup_invite_key(KEY_A) is None
        sanctions.lift(s["id"], "suspension served")
        assert persistence.lookup_invite_key(KEY_A)["name"] == "Ada"

    @pytest.mark.parametrize("call", [
        lambda: sanctions.suspend("Ada", HOUR, ""),
        lambda: sanctions.suspend("Ada", HOUR, " \t\n "),
        lambda: sanctions.suspend("Ada", HOUR, None),
        lambda: sanctions.suspend("Ada", HOUR, "x" * 501),
        lambda: sanctions.ban("Ada", "   "),
        lambda: sanctions.ban("Nobody", "spam"),
        lambda: sanctions.ban("", "spam"),
        lambda: sanctions.suspend("Ada", datetime.timedelta(0), "spam"),
        lambda: sanctions.suspend("Ada", datetime.timedelta(seconds=30), "spam"),
        lambda: sanctions.suspend("Ada", datetime.timedelta(days=366), "spam"),
        lambda: sanctions.suspend("Ada", -HOUR, "spam"),
        lambda: sanctions.suspend("Ada", 3600, "spam"),
    ], ids=["empty-reason", "blank-reason", "no-reason", "long-reason", "blank-ban-reason",
            "unknown-name", "empty-name", "zero", "under-a-minute", "over-a-year",
            "negative", "not-a-duration"])
    def test_refusals_write_nothing(self, call):
        persistence.mint_invite_key(KEY_A, "Ada")
        with pytest.raises(ValueError):
            call()
        assert _count("sanctions") == 0
        assert _count("participants") == 0
        assert persistence.lookup_invite_key(KEY_A)["name"] == "Ada"


class TestInsertOnly:
    def test_a_lift_is_a_new_row_and_the_sanction_row_never_changes(self):
        persistence.mint_invite_key(KEY_A, "Ada")
        s = sanctions.suspend("Ada", HOUR, "spam")
        before = _table("sanctions")
        sanctions.lift(s["id"], "first lift")
        assert _table("sanctions") == before
        lifts = _table("sanction_lifts")
        assert [(r[0], r[1]) for r in lifts] == [(s["id"], "first lift")]
        with pytest.raises(ValueError, match="already lifted"):
            sanctions.lift(s["id"], "second lift")
        with pytest.raises(ValueError, match="No sanction"):
            sanctions.lift(s["id"] + 99, "unknown")
        assert _table("sanction_lifts") == lifts
        assert _table("sanctions") == before
        # A later sanction is another row; the history of earlier ones stays.
        sanctions.ban("Ada", "again")
        assert _table("sanctions")[0] == before[0]
        assert len(_table("sanctions")) == 2

    def test_the_module_offers_no_update_or_delete(self):
        public = {name for name in dir(sanctions)
                  if not name.startswith("_") and callable(getattr(sanctions, name))}
        writers = {"suspend", "ban", "lift"}
        assert writers <= public
        assert not {n for n in public
                    if any(w in n.lower() for w in ("update", "delete", "remove",
                                                    "edit", "clear", "purge"))}

    def test_sanctions_write_nothing_to_world_mutations(self):
        _mint_two()
        persistence.record_mutation(382, "Room-1", "PLAYER_CHAT", "Bea", {"text": "hi"})
        before = _table("world_mutations")
        s = sanctions.suspend("Ada", HOUR, "spam")
        b = sanctions.ban("Bea", "threats")
        sanctions.lift(s["id"], "served")
        sanctions.lift(b["id"], "overturned")
        sanctions.list_sanctions(include_all=True)
        assert _table("world_mutations") == before


# ── The HTTP gate ───────────────────────────────────────────────────────────


class TestHttpGate:
    def test_a_suspended_key_gets_exactly_the_revoked_key_403(self, srv):
        _mint_two()
        persistence.mint_invite_key(KEY_C, "Cy")
        persistence.revoke_invite_key(KEY_C)
        sanctions.suspend("Ada", HOUR, "spam in the commons")

        suspended = _get(srv, "/worlds", KEY_A)
        revoked = _get(srv, "/worlds", KEY_C)
        assert suspended == revoked == (403, "application/json", {"error": "forbidden"})
        assert "spam" not in json.dumps(suspended[2])
        assert _get(srv, "/worlds", KEY_B)[0] == 200

    def test_a_lifted_key_is_admitted_again(self, srv):
        persistence.mint_invite_key(KEY_A, "Ada")
        b = sanctions.ban("Ada", "threats")
        assert _get(srv, "/worlds", KEY_A)[0] == 403
        sanctions.lift(b["id"], "appeal upheld")
        assert _get(srv, "/worlds", KEY_A)[0] == 200

    def test_an_expired_suspension_is_admitted(self, srv):
        persistence.mint_invite_key(KEY_A, "Ada")
        owner = sanctions.resolve("Ada")["id"]
        _insert_suspension(owner, "-3 hours", "-1 second")
        assert _get(srv, "/worlds", KEY_A)[0] == 200

    def test_sanctioning_every_live_player_never_reopens_the_gate(self, srv):
        _mint_two()
        sanctions.suspend("Ada", HOUR, "spam")
        sanctions.ban("Bea", "threats")
        assert persistence.list_invite_keys() != []  # both keys are still unrevoked
        assert guard.invite_gate_active() is True
        for key in (None, "", KEY_A, KEY_B):
            assert _get(srv, "/worlds", key)[0] == 403, key
        for key in (None, KEY_A, KEY_B):
            sock, status = _ws_connect(srv, 2910, "Mallory", invite_key=key)
            sock.close()
            assert b"403" in status, (key, status)

    def test_identify_surfaces_refuse_while_sanctioned_and_return_after(self, http, accounts):
        ada, bea = accounts
        owner = participants.identify(ada)["id"]
        participants.save_note(owner, 382, "Room-1", "kept through it", "note-0001")
        persistence.mint_invite_key(KEY_C, "Cy")
        persistence.revoke_invite_key(KEY_C)
        s = sanctions.suspend("Ada", HOUR, "spam")

        # Ideas authenticates through participants.identify, outside the gate.
        refused = http("/ideas/list", key=ada)
        assert refused[:2] == http("/ideas/list", key=KEY_C)[:2]
        assert refused[0] == 403 and "spam" not in json.dumps(refused[1])
        assert http("/me", key=ada)[:2] == (403, {"error": "forbidden"})
        assert http("/me", key=bea)[0] == 200

        sanctions.lift(s["id"], "early release")
        status, body, _ = http("/me", key=ada)
        assert status == 200 and body["participant"] == {"id": owner, "name": "Ada"}
        assert http("/ideas/list", key=ada)[0] == 200
        assert [n["text"] for n in participants.notes(owner, 382)] == ["kept through it"]


# ── The open socket ─────────────────────────────────────────────────────────


class TestOpenSocket:
    def test_suspension_closes_the_open_socket_1008_and_a_lift_lets_it_back(self, srv):
        seed = 2901
        _mint_two()
        bea, _ = _join(srv, seed, "x", KEY_B)
        ada, ada_sid = _join(srv, seed, "x", KEY_A)
        _until_type(bea, "player_join")

        sanction = sanctions.suspend("Ada", HOUR, "spam")
        _ws_send_json(ada, {"type": "ping"})
        code, seen = _until_close(ada)
        assert code == 1008
        assert not [m for m in seen if m.get("type") == "pong"]
        _until_eof(ada)
        leave, _ = _until_type(bea, "player_leave")
        assert leave["session_id"] == ada_sid
        assert len(_wait_rows(seed, "PLAYER_LEAVE", "Ada", 1)) == 1

        # Refused at the upgrade while suspended …
        sock, status = _ws_connect(srv, seed, "x", invite_key=KEY_A)
        sock.close()
        assert b"403" in status
        # … and the same key is the same named player once lifted.
        sanctions.lift(sanction["id"], "served")
        again, _ = _join(srv, seed, "x", KEY_A)
        joined, _ = _until_type(bea, "player_join")
        assert joined["name"] == "Ada"
        again.close()
        bea.close()

    def test_a_ban_from_the_cli_closes_the_socket_before_its_chat_lands(self, srv, capsys):
        seed = 2902
        _mint_two()
        bea, _ = _join(srv, seed, "x", KEY_B)
        ada, _ = _join(srv, seed, "x", KEY_A)
        _until_type(bea, "player_join")

        main.main(["sanction", "ban", "Ada", "--reason", "threats in chat"])
        assert "Banned Ada" in capsys.readouterr().out
        _ws_send_json(ada, {"type": "chat", "text": "you cannot stop me"})
        assert _until_close(ada)[0] == 1008
        _until_eof(ada)
        _, before_leave = _until_type(bea, "player_leave")
        assert not [m for m in before_leave if m.get("type") == "chat"]
        assert _rows(seed, "PLAYER_CHAT") == []
        bea.close()


# ── The owner's CLI ─────────────────────────────────────────────────────────


def _cli(*argv):
    main.main(list(argv))


class TestCli:
    def test_suspend_takes_hours_or_days(self, capsys):
        _mint_two()
        _cli("sanction", "suspend", "Ada", "--hours", "3", "--reason", "spam")
        out = capsys.readouterr().out
        _cli("sanction", "suspend", "Bea", "--days", "2", "--reason", "flooding")
        rows = {r["name"]: r for r in sanctions.list_sanctions()}
        assert f"Suspended Ada until {rows['Ada']['expires_at']} UTC (sanction {rows['Ada']['id']})" in out
        assert _seconds_between(rows["Ada"]["created_at"], rows["Ada"]["expires_at"]) == 3 * 3600
        assert _seconds_between(rows["Bea"]["created_at"], rows["Bea"]["expires_at"]) == 2 * 86400
        assert persistence.lookup_invite_key(KEY_A) is None
        assert persistence.lookup_invite_key(KEY_B) is None

    @pytest.mark.parametrize("argv", [
        ["sanction", "suspend", "Ada", "--hours", "3"],
        ["sanction", "ban", "Ada"],
        ["sanction", "lift", "1"],
        ["sanction", "suspend", "Ada", "--reason", "spam"],
        ["sanction", "suspend", "Ada", "--hours", "3", "--days", "1", "--reason", "spam"],
        ["sanction", "suspend", "Ada", "--hours", "0", "--reason", "spam"],
        ["sanction", "suspend", "Ada", "--hours", "1.5", "--reason", "spam"],
        ["sanction", "lift", "first", "--reason", "x"],
    ], ids=["suspend-no-reason", "ban-no-reason", "lift-no-reason", "no-length",
            "hours-and-days", "zero-hours", "fractional-hours", "non-numeric-id"])
    def test_usage_errors_exit_2_and_write_nothing(self, argv, capsys):
        persistence.mint_invite_key(KEY_A, "Ada")
        with pytest.raises(SystemExit) as exc:
            _cli(*argv)
        assert exc.value.code == 2
        assert _count("sanctions") == 0 and _count("sanction_lifts") == 0

    @pytest.mark.parametrize("argv, message", [
        (["sanction", "ban", "Ada", "--reason", "   "], "reason is required"),
        (["sanction", "ban", "Nobody", "--reason", "spam"], "No registered player"),
        (["sanction", "suspend", "Ada", "--days", "366", "--reason", "spam"], "365 days"),
        (["sanction", "lift", "7", "--reason", "x"], "No sanction has id 7"),
    ], ids=["blank-reason", "unknown-player", "too-long", "unknown-id"])
    def test_refusals_exit_with_a_message_and_write_nothing(self, argv, message):
        persistence.mint_invite_key(KEY_A, "Ada")
        with pytest.raises(SystemExit) as exc:
            _cli(*argv)
        assert message in str(exc.value.code)
        assert _count("sanctions") == 0 and _count("sanction_lifts") == 0
        assert persistence.lookup_invite_key(KEY_A)["name"] == "Ada"

    def test_lift_and_list(self, capsys):
        _mint_two()
        _cli("sanction", "ban", "Ada", "--reason", "threats")
        _cli("sanction", "suspend", "Bea", "--hours", "1", "--reason", "spam")
        capsys.readouterr()
        _cli("sanction", "list")
        listing = capsys.readouterr().out.splitlines()
        assert [line.split()[:4] for line in listing[2:]] == [
            ["2", "Bea", "suspension", "active"], ["1", "Ada", "ban", "active"]]
        assert listing[2].endswith("spam") and listing[3].endswith("threats")

        _cli("sanction", "lift", "1", "--reason", "appeal upheld")
        assert "Lifted sanction 1 (ban) on Ada." in capsys.readouterr().out
        assert persistence.lookup_invite_key(KEY_A)["name"] == "Ada"
        with pytest.raises(SystemExit) as exc:
            _cli("sanction", "lift", "1", "--reason", "again")
        assert "already lifted" in str(exc.value.code)

        _cli("sanction", "list")
        assert [line.split()[1] for line in capsys.readouterr().out.splitlines()[2:]] == ["Bea"]
        _cli("sanction", "list", "--all")
        everything = capsys.readouterr().out
        assert "lifted" in everything and "appeal upheld" in everything
        sanctions.lift(2, "served")
        _cli("sanction", "list")
        assert capsys.readouterr().out.strip() == "No active sanctions."

    def test_logs_carry_neither_reasons_nor_credentials(self, srv, caplog, capsys):
        caplog.set_level(logging.DEBUG)
        seed = 2903
        _mint_two()
        ada, _ = _join(srv, seed, "x", KEY_A)
        secrets_ = ["REASON-alpha harassment", "REASON-beta threats",
                    "REASON-gamma appeal", KEY_A, KEY_B]
        _cli("sanction", "suspend", "Ada", "--hours", "2", "--reason", secrets_[0])
        _ws_send_json(ada, {"type": "ping"})
        assert _until_close(ada)[0] == 1008
        assert _get(srv, "/worlds", KEY_A)[0] == 403
        _cli("sanction", "ban", "Bea", "--reason", secrets_[1])
        _cli("sanction", "lift", "1", "--reason", secrets_[2])
        _cli("sanction", "list", "--all")
        capsys.readouterr()
        logged = "\n".join(f"{r.getMessage()} {r.args!r}" for r in caplog.records)
        assert any(r.name == "nested_worlds.sanctions" for r in caplog.records)
        for secret in secrets_ + ["harassment", "threats"]:
            assert secret not in logged, secret
