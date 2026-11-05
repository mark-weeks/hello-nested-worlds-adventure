"""Operator-visible moderation outcomes (follow-up to #144, finding 2).

A busy or failed screen on chat, Ideas, a published profile or puzzle text
used to leave one INFO `moderation_call` line and no count, so
`python main.py voice-health` could not see it. Each logged line is now
counted once per surface and outcome under `moderation_outcome:` in
`cost_budget`, and voice-health exits 1 on a screen failure.

Everything here runs the real `moderation.screen`, the real classify call
through `runtime.generate`, and the real per-provider semaphore, with the
fixture provider from tests/test_provider_slot_wait.py. Blocking calls run
on a daemon thread with a join limit. No live model call.
"""
from __future__ import annotations

import datetime
import json
import logging
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

import persistence
from multiverse import store
from server import _Handler, _ThreadedServer, guard, moderation, observability
from tests.test_day_one_recording import _ws_connect, _ws_send_json
from tests.test_moderation import _SLUR, _read_ws_json_until
from tests.test_provider_slot_wait import (  # noqa: F401 - shared fixtures
    AMBIGUOUS, LIMIT, _bounded, _free_slots, _saturated, provider, quick_screen,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import beta_metrics  # noqa: E402

SEED = 382
KEY = "nw_" + "e" * 32


def _today():
    return guard._utc_day()


def _counts():
    """Every moderation-outcome count today, as {surface: {outcome: n}}."""
    return observability.moderation_outcome_summary().get(_today(), {})


def _all_buckets():
    """Every cost_budget bucket name, any day (an empty prefix matches all)."""
    return [bucket for bucket, _day, _calls in persistence.cost_rows("", "")]


def _private(caplog, *secrets):
    """No secret in any log line or any cost_budget bucket name."""
    lines = [record.getMessage() for record in caplog.records]
    buckets = _all_buckets()
    for secret in secrets:
        assert not any(secret in line for line in lines), secret
        assert not any(secret in bucket for bucket in buckets), secret


# ── Every outcome path through the real screen ─────────────────────────────

class TestEachScreenOutcomeCountsOnce:
    def test_a_local_block(self, provider):
        verdict = moderation.screen(f"you {_SLUR}", surface="chat")
        assert verdict == moderation.Verdict(False, "blocklist", "block")
        assert _counts() == {"chat": {"block": 1}}
        assert provider.calls == []

    def test_the_disable_switch(self, provider, monkeypatch):
        monkeypatch.setenv(moderation.DISABLE_MODERATION_ENV, "1")
        assert moderation.screen("hello", surface="ideas").outcome == "disabled"
        assert _counts() == {"ideas": {"disabled": 1}}

    def test_the_moderation_action_cap(self, provider, monkeypatch):
        monkeypatch.setenv(guard.MODERATION_ACTIONS_PER_USER_ENV, "0")
        assert moderation.screen("hello", user_key=KEY, surface="profile").outcome == "user_cap"
        assert _counts() == {"profile": {"user_cap": 1}}

    def test_the_model_action_cap(self, provider, monkeypatch):
        monkeypatch.setenv(guard.MODEL_ACTIONS_PER_USER_ENV, "0")
        verdict = moderation.screen(AMBIGUOUS, user_key=KEY, surface="puzzle")
        assert verdict.outcome == "user_cap"
        assert _counts() == {"puzzle": {"user_cap": 1}}
        assert provider.calls == []

    def test_the_per_user_classify_cap(self, provider, monkeypatch):
        monkeypatch.setenv(guard.MODERATION_PER_USER_CAP_ENV, "0")
        assert moderation.screen(AMBIGUOUS, user_key=KEY, surface="agent").outcome == "user_cap"
        assert _counts() == {"agent": {"user_cap": 1}}

    def test_the_moderation_budget(self, provider, monkeypatch):
        monkeypatch.setenv(guard.MODERATION_CAP_ENV, "0")
        assert moderation.screen(AMBIGUOUS, surface="speak").outcome == "budget"
        assert _counts() == {"speak": {"budget": 1}}
        assert provider.calls == []

    def test_a_missing_moderation_model_id(self, provider, monkeypatch):
        monkeypatch.setattr(provider, "default_model", lambda task: "")
        assert moderation.screen(AMBIGUOUS, surface="chat").outcome == "error"
        assert _counts() == {"chat": {"error": 1}}

    def test_a_provider_error(self, provider, caplog):
        provider.fail = RuntimeError(f"upstream echoed {AMBIGUOUS} {KEY}")
        caplog.set_level(logging.INFO)
        assert moderation.screen(AMBIGUOUS, user_key=KEY, surface="chat").outcome == "error"
        assert _counts() == {"chat": {"error": 1}}
        assert len(provider.calls) == 1
        assert caplog.text.count("moderation_call outcome=error surface=chat ms=") == 1
        _private(caplog, AMBIGUOUS, KEY)

    def test_no_provider_slot(self, provider, quick_screen):
        with _saturated():
            box = _bounded(lambda: moderation.screen(AMBIGUOUS, surface="chat"), 5)
        assert box["value"] == moderation.Verdict(False, "busy", "busy")
        assert _counts() == {"chat": {"busy": 1}}
        assert provider.calls == []
        assert _free_slots() == LIMIT

    @pytest.mark.parametrize("reply,outcome", [
        ("ALLOW", "allow"), ("BLOCK", "block"), ("hmm, unsure", "undecided"),
    ])
    def test_a_finished_classify(self, provider, caplog, reply, outcome):
        provider.reply = reply
        caplog.set_level(logging.INFO)
        verdict = moderation.screen(AMBIGUOUS, surface="ideas")
        assert verdict.outcome == outcome
        assert _counts() == {"ideas": {outcome: 1}}
        # One logged line, one count: classify_content logs and counts the
        # verdict, and screen() does not log it again.
        assert caplog.text.count("moderation_call ") == 1
        _private(caplog, AMBIGUOUS)

    def test_a_locally_clean_line_and_empty_text_count_nothing(self, provider):
        assert moderation.screen("the lantern hums", user_key=KEY, surface="chat").allowed
        assert moderation.screen("   ", surface="chat").allowed
        assert _counts() == {}
        assert not any(b.startswith("moderation_outcome:") for b in _all_buckets())

    def test_names_count_their_logged_refusals(self, provider, monkeypatch):
        assert moderation.name_refusal("Priya") is None
        assert moderation.name_refusal(_SLUR) == moderation.NAME_BLOCK
        monkeypatch.setenv(moderation.DISABLE_MODERATION_ENV, "1")
        assert moderation.name_refusal("Priya") == moderation.NAME_UNAVAILABLE
        assert _counts() == {"name": {"block": 1, "disabled": 1}}

    def test_puzzle_excerpts_count_under_the_puzzle_surface(self, provider):
        provider.reply = "BLOCK"
        assert moderation.public_excerpt(AMBIGUOUS, user_key=KEY) is None
        assert _counts() == {"puzzle": {"block": 1}}

    def test_a_direct_classify_counts_the_verdict_it_logs(self, provider):
        # classify_content counts its finished verdict itself, whoever calls
        # it, under its default surface `classify`; it is not screen() that
        # counts it. A raising call counts nothing here: its caller logs and
        # counts that outcome=error line.
        import consciousness
        provider.reply = "BLOCK"
        assert consciousness.classify_content(AMBIGUOUS) == "block"
        assert _counts() == {"classify": {"block": 1}}
        provider.fail = RuntimeError("upstream")
        with pytest.raises(RuntimeError):
            consciousness.classify_content(AMBIGUOUS)
        assert _counts() == {"classify": {"block": 1}}


# ── The real endpoints, with a player key ───────────────────────────────────

@pytest.fixture
def site(accounts, monkeypatch):
    monkeypatch.setenv("NESTED_WORLDS_CANONICAL_SEED", str(SEED))
    server = _ThreadedServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)


def _post(port, path, body, key):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "X-Beta-Key": key})
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.status, json.load(resp), time.monotonic() - started
    except urllib.error.HTTPError as exc:
        return exc.code, json.load(exc), time.monotonic() - started


def _rows(kind):
    root = store.world_tree(SEED).name
    return [row for row in persistence.get_node_history(SEED, root, 50)
            if row["type"] == kind]


def _busy_chat(port, key):
    sender, status = _ws_connect(port, SEED, "Ada", invite_key=key)
    try:
        assert b"101" in status
        _read_ws_json_until(sender, "welcome")
        _ws_send_json(sender, {"type": "chat", "text": AMBIGUOUS})
        declined = _read_ws_json_until(sender, "chat_declined", timeout=5)
        # The reader is free again after the hold.
        _ws_send_json(sender, {"type": "ping"})
        assert _read_ws_json_until(sender, "pong") == {"type": "pong"}
    finally:
        sender.close()
    return declined


def _busy_surface(port, key, surface):
    """Send AMBIGUOUS to one shared surface; return what the player saw."""
    if surface == "chat":
        return _busy_chat(port, key)
    if surface == "ideas":
        return _post(port, "/ideas/submit", {
            "title": AMBIGUOUS, "description": "A traveler could not find the crossing.",
            "request_id": "idea-count-0001", "public_credit": False}, key)
    if surface == "profile":
        return _post(port, "/profile/save", {
            "bio": AMBIGUOUS, "goals": "", "published": True}, key)
    return _post(port, "/puzzle/attempt", {
        "seed": SEED, "node_name": store.world_tree(SEED).name,
        "answer": AMBIGUOUS, "player_name": "Ada"}, key)


def _assert_held(surface, seen):
    if surface == "chat":
        assert seen["text"] == moderation.HOLD_LINE
        assert _rows("PLAYER_CHAT") == []
    elif surface in ("ideas", "profile"):
        status, body, _ = seen
        hold = moderation.IDEAS_HOLD if surface == "ideas" else moderation.PROFILE_HOLD
        assert status == 422 and body == {"error": hold, "held": True}
    else:
        status, body, _ = seen
        assert status == 200 and body["correct"] is False
        attempts = _rows("PUZZLE_ATTEMPT")
        assert len(attempts) == 1 and "guess" not in attempts[0]["data"]


SURFACES = ["chat", "ideas", "profile", "puzzle"]


class TestBusyScreensOnSharedSurfaces:
    @pytest.mark.parametrize("surface", SURFACES)
    def test_a_busy_screen_is_counted_under_its_surface(
            self, site, accounts, provider, quick_screen, caplog, surface):
        provider.reply = "ALLOW"
        caplog.set_level(logging.INFO)
        with _saturated():
            seen = _busy_surface(site, accounts[0], surface)
        _assert_held(surface, seen)
        assert _counts() == {surface: {"busy": 1}}
        # Not a voice surface: no voice outcome is recorded for it.
        assert observability.voice_outcome_summary() == {}
        assert provider.calls == []
        assert f"moderation_call outcome=busy surface={surface} ms=" in caplog.text
        _private(caplog, AMBIGUOUS, accounts[0])
        assert _free_slots() == LIMIT


# ── A broken or locked counter store changes nothing a player sees ─────────

@pytest.fixture
def broken_counter(monkeypatch):
    """increment_cost_calls fails for moderation counters only.

    Budget and cap charges use the same function and keep working, so the
    screen reaches every outcome as it would with a healthy store.
    """
    real = persistence.increment_cost_calls
    attempts = []

    def increment(bucket, day, **kwargs):
        if bucket.startswith(observability.MODERATION_OUTCOME_PREFIX + ":"):
            attempts.append(bucket)
            raise sqlite3.OperationalError("disk I/O error")
        return real(bucket, day, **kwargs)
    monkeypatch.setattr(persistence, "increment_cost_calls", increment)
    return attempts


def _counter_warnings(caplog):
    return [record.getMessage() for record in caplog.records
            if record.name == "nested_worlds.moderation"
            and record.levelno == logging.WARNING]


class TestCounterFailuresAreInvisibleToPlayers:
    @pytest.mark.parametrize("text,reply,expected", [
        (f"you {_SLUR}", None, moderation.Verdict(False, "blocklist", "block")),
        (AMBIGUOUS, "ALLOW", moderation.Verdict(True, "classify", "allow")),
        (AMBIGUOUS, "BLOCK", moderation.Verdict(False, "classify", "block")),
    ])
    def test_a_failing_store_keeps_the_verdict(
            self, provider, broken_counter, caplog, text, reply, expected):
        provider.reply = reply or "ALLOW"
        caplog.set_level(logging.INFO)
        box = _bounded(lambda: moderation.screen(text, user_key=KEY, surface="chat"), 5)
        assert box.get("error") is None and box["value"] == expected
        assert len(broken_counter) == 1
        assert _counter_warnings(caplog) == [
            f"moderation_outcome counter unavailable surface=chat "
            f"outcome={expected.outcome} exception=OperationalError"]
        assert caplog.text.count("moderation_call ") == 1
        _private(caplog, text, KEY)

    def test_a_failing_store_keeps_a_busy_hold(self, provider, quick_screen, broken_counter):
        with _saturated():
            box = _bounded(lambda: moderation.screen(AMBIGUOUS, surface="chat"), 5)
        assert box["value"] == moderation.Verdict(False, "busy", "busy")
        assert len(broken_counter) == 1

    def test_a_failing_store_keeps_the_players_response(
            self, site, accounts, provider, quick_screen, broken_counter):
        with _saturated():
            seen = _busy_surface(site, accounts[0], "chat")
            ideas = _busy_surface(site, accounts[0], "ideas")
        _assert_held("chat", seen)
        _assert_held("ideas", ideas)
        assert len(broken_counter) == 2

    def test_a_locked_store_holds_the_screen_at_most_briefly(self, provider, caplog):
        # Another writer holds the write lock (a long transaction, a redact).
        persistence.get_cost_calls("warm", _today())  # create the DB
        holder = sqlite3.connect(persistence._DB_PATH)
        holder.execute("BEGIN IMMEDIATE")
        caplog.set_level(logging.WARNING, logger="nested_worlds")
        try:
            box = _bounded(lambda: moderation.screen(f"you {_SLUR}", surface="chat"), 5)
        finally:
            holder.rollback()
            holder.close()
        assert box["value"].outcome == "block"
        assert box["elapsed"] < 1.0  # the 50 ms counter wait, not the 5 s default
        assert _counter_warnings(caplog) == [
            "moderation_outcome counter unavailable surface=chat outcome=block "
            "exception=OperationalError"]
        assert _counts() == {}

    def test_a_screen_inside_an_open_transaction_does_not_wait_on_it(
            self, provider, monkeypatch, caplog):
        # No caller screens inside persistence.transaction() today. If one
        # did, the counter's own connection would wait on the caller's write
        # lock; it skips the write without touching the store instead.
        writes = []
        real = persistence.increment_cost_calls
        monkeypatch.setattr(persistence, "increment_cost_calls",
                            lambda *a, **k: writes.append(a[0]) or real(*a, **k))
        caplog.set_level(logging.WARNING, logger="nested_worlds")
        with persistence.transaction() as conn:
            assert persistence.in_transaction()
            verdict = moderation.screen(f"you {_SLUR}", surface="chat")
            conn.execute("INSERT INTO cost_budget (bucket, day, calls) VALUES (?, ?, 1)",
                         ("outer-write", _today()))
        assert not persistence.in_transaction()
        assert verdict.outcome == "block"
        assert writes == []
        assert _counter_warnings(caplog) == [
            "moderation_outcome counter skipped surface=chat outcome=block "
            "reason=open-transaction"]
        assert persistence.get_cost_calls("outer-write", _today()) == 1  # committed
        moderation.screen(f"you {_SLUR}", surface="chat")
        assert _counts() == {"chat": {"block": 1}}


# ── The closed sets ─────────────────────────────────────────────────────────

class TestClosedSets:
    def test_every_surface_the_code_passes_is_known(self):
        # The surfaces screen(), public_excerpt(), classify_content() and
        # name_refusal() are called with today, and their defaults.
        for surface in ("speak", "agent", "chat", "ideas", "profile", "puzzle",
                        "name", "cli", "shared", "classify"):
            observability.moderation_outcome(surface, "block")
        assert set(_counts()) == {"speak", "agent", "chat", "ideas", "profile",
                                  "puzzle", "name", "cli", "shared", "classify"}

    def test_an_unknown_surface_is_counted_as_other(self, caplog):
        caplog.set_level(logging.INFO)
        observability.moderation_outcome(AMBIGUOUS, "busy")
        observability.moderation_outcome(None, "error")
        assert _counts() == {"other": {"busy": 1, "error": 1}}
        _private(caplog, AMBIGUOUS)

    def test_an_unknown_outcome_raises_nothing_and_writes_nothing(self, caplog):
        caplog.set_level(logging.INFO)
        observability.moderation_outcome("chat", AMBIGUOUS)
        observability.moderation_outcome("chat", None)
        observability.moderation_outcome("chat", "ok")
        assert _counts() == {}
        assert _counter_warnings(caplog) == [
            "moderation_outcome dropped surface=chat reason=unknown-outcome"] * 3
        _private(caplog, AMBIGUOUS)

    def test_the_groups_partition_the_outcomes(self):
        groups = (observability.MODERATION_VERDICTS, observability.MODERATION_FAILURES,
                  observability.MODERATION_LIMITS)
        assert sorted(o for g in groups for o in g) == sorted(observability.MODERATION_OUTCOMES)
        assert set(observability.MODERATION_FAILURES) == {"error", "busy", "undecided"}
        assert set(observability.MODERATION_LIMITS) == {"budget", "user_cap", "disabled"}

    def test_the_new_rows_inflate_no_spend_or_voice_figure(self, capsys, monkeypatch):
        from consciousness import runtime
        monkeypatch.setattr(runtime, "configured", lambda: True)
        for outcome in observability.MODERATION_OUTCOMES:
            observability.moderation_outcome("chat", outcome)
        day = _today()
        for bucket in (guard.ANTHROPIC_BUCKET, guard.MODERATION_BUCKET,
                       guard.MODERATION_ACTIONS_BUCKET, guard.MODEL_ACTIONS_BUCKET,
                       guard.FAL_BUCKET):
            assert persistence.get_cost_calls(bucket, day) == 0
        assert observability.voice_outcome_summary() == {}
        assert persistence.cost_rows(observability.VOICE_OUTCOME_PREFIX + ":", day) == []
        metrics = beta_metrics.compute_metrics(persistence._DB_PATH, days=1)
        assert metrics["voice_outcomes"] == {}
        with pytest.raises(SystemExit):
            _voice_health()
        out = capsys.readouterr().out
        assert "voice budget today: 0/" in out
        assert "moderation budget today: 0/" in out


# ── voice-health ────────────────────────────────────────────────────────────

def _voice_health(*argv):
    import main
    args = main.build_parser().parse_args(["voice-health", *argv])
    args.func(args)


class TestVoiceHealth:
    @pytest.fixture(autouse=True)
    def _voice_ready(self, monkeypatch):
        from consciousness import runtime
        monkeypatch.setattr(runtime, "configured", lambda: True)

    def test_a_busy_chat_screen_alone_fails_the_check(self, provider, quick_screen, capsys):
        with _saturated():
            box = _bounded(lambda: moderation.screen(AMBIGUOUS, surface="chat"), 5)
        assert box["value"].outcome == "busy"
        with pytest.raises(SystemExit) as raised:
            _voice_health()
        assert str(raised.value) == "voice-health: 1 screen failure(s) in the window"
        out = capsys.readouterr().out
        assert "  (no voice requests recorded)" in out
        assert "Shared-text screens, last 1 UTC day(s), today included" in out
        assert f"{_today()}\n  chat         screens    1   not allowed: busy 1\n" in out

    def test_limits_and_allows_pass(self, capsys):
        observability.moderation_outcome("chat", "allow")
        observability.moderation_outcome("chat", "allow")
        observability.moderation_outcome("chat", "user_cap")
        observability.moderation_outcome("ideas", "budget")
        observability.moderation_outcome("profile", "disabled")
        observability.moderation_outcome("name", "block")
        _voice_health()
        out = capsys.readouterr().out
        assert "  chat         screens    3   not allowed: user_cap 1\n" in out
        assert "  ideas        screens    1   not allowed: budget 1\n" in out
        assert "  profile      screens    1   not allowed: disabled 1\n" in out
        assert "  name         screens    1   not allowed: block 1\n" in out
        assert out.rstrip().endswith("voice-health: ok")

    @pytest.mark.parametrize("outcome", ["error", "undecided"])
    def test_every_screen_failure_fails_the_check(self, outcome):
        observability.moderation_outcome("puzzle", outcome)
        with pytest.raises(SystemExit, match="1 screen failure"):
            _voice_health()

    def test_a_voice_surface_failure_is_reported_in_both_sections(self, capsys):
        # A busy screen on /speak is the voice reason `busy` and the screen
        # outcome `busy`. Reported separately, never merged into one count.
        observability.voice_outcome("speak", "busy")
        observability.moderation_outcome("speak", "busy")
        with pytest.raises(SystemExit) as raised:
            _voice_health()
        assert str(raised.value) == ("voice-health: 1 voice failure(s) in the window; "
                                     "1 screen failure(s) in the window")
        out = capsys.readouterr().out
        assert "  speak        answered    0   quiet: busy 1\n" in out
        assert "  speak        screens    1   not allowed: busy 1\n" in out

    def test_the_window(self, capsys):
        today = datetime.date.fromisoformat(_today())
        yesterday = (today - datetime.timedelta(days=1)).isoformat()
        persistence.increment_cost_calls(
            observability.moderation_bucket("chat", "busy"), yesterday)
        _voice_health()  # yesterday's failure is outside a one-day window
        assert "  (no screens recorded)" in capsys.readouterr().out
        with pytest.raises(SystemExit, match="1 screen failure"):
            _voice_health("--days", "2")
        assert observability.moderation_outcome_summary(days=2) == {
            yesterday: {"chat": {"busy": 1}}}

    def test_the_budget_line_reads_moderations_own_bucket_and_cap(
            self, provider, monkeypatch, capsys):
        monkeypatch.setenv(guard.MODERATION_CAP_ENV, "7")
        provider.reply = "ALLOW"
        assert moderation.screen(AMBIGUOUS, surface="chat").allowed  # one classify
        _voice_health()
        out = capsys.readouterr().out
        assert "moderation budget today: 1/7 classify calls\n" in out
        assert "voice budget today: 0/" in out

    def test_the_moderation_switch_is_reported_not_failed(self, monkeypatch, capsys):
        monkeypatch.setenv(moderation.DISABLE_MODERATION_ENV, "1")
        moderation.screen("hello", surface="chat")
        _voice_health()
        out = capsys.readouterr().out
        assert "  chat         screens    1   not allowed: disabled 1\n" in out
        assert f"moderation switch: {moderation.DISABLE_MODERATION_ENV}=1" in out


class TestBetaMetrics:
    def test_screens_are_reported_beside_the_voice(self):
        observability.moderation_outcome("chat", "allow")
        observability.moderation_outcome("chat", "busy")
        observability.moderation_outcome("ideas", "block")
        observability.voice_outcome("speak", "ok")
        metrics = beta_metrics.compute_metrics(persistence._DB_PATH, days=1)
        assert metrics["moderation_outcomes"] == {
            "chat": {"allow": 1, "busy": 1}, "ideas": {"block": 1}}
        assert metrics["voice_outcomes"] == {"speak": {"ok": 1}}
        rendered = beta_metrics.render(metrics)
        assert "shared-text screens (by UTC day; screened / not allowed):" in rendered
        assert "  chat             2 / 1      (busy 1)" in rendered
        assert "  ideas            1 / 1      (block 1)" in rendered
