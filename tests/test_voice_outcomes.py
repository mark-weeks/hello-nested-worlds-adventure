"""Operator-visible voice outcomes (2026-11-03 evaluation, finding R3).

"Failure stays in fiction" governs the player's view only. These tests pin
that every player-facing voice surface still answers quietly in character AND
leaves the operator a signal: a structured `nested_worlds.voice` log line
(ERROR for failures to fix, WARNING for limits) and a daily counter that
`python main.py voice-health` and scripts/beta_metrics.py read.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import pytest

import persistence
from multiverse import store
from server import _Handler, _ThreadedServer, guard, moderation, observability

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import beta_metrics  # noqa: E402

SEED = 382
_SECRET = "sk-provider-SECRET-echo"


@pytest.fixture
def base(monkeypatch):
    monkeypatch.setenv("NESTED_WORLDS_CANONICAL_SEED", str(SEED))
    server = _ThreadedServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)


@pytest.fixture
def voiced(monkeypatch):
    """A configured voice and an open screen; each test sets the behaviour."""
    from consciousness import runtime
    monkeypatch.delenv(guard.DISABLE_AI_ENV, raising=False)
    monkeypatch.setattr(runtime, "configured", lambda: True)
    monkeypatch.setattr(moderation, "screen",
                        lambda text, **_kwargs: SimpleNamespace(allowed=True))


def _post(base, path, body):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.load(resp)
    except urllib.error.HTTPError as exc:
        return exc.code, json.load(exc)


def _count(surface, reason):
    return persistence.get_cost_calls(observability.voice_bucket(surface, reason),
                                      guard._utc_day())


def _eventually(check, timeout=3.0):
    import time
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return True
        time.sleep(0.02)
    return check()


def _voice_records(caplog):
    return [(r.levelno, r.getMessage()) for r in caplog.records
            if r.name == "nested_worlds.voice"]


def _speak(base):
    return _post(base, "/speak", {"node_name": store.world_tree(SEED).name,
                                  "message": "hello"})


class TestSpeakOutcomes:
    def test_provider_failure_is_quiet_for_the_player_and_loud_for_the_operator(
            self, base, voiced, monkeypatch, caplog):
        import consciousness

        def boom(*_a, **_k):
            raise RuntimeError(f"upstream said {_SECRET}")
        monkeypatch.setattr(consciousness, "speak", boom)
        caplog.set_level(logging.WARNING, logger="nested_worlds")
        status, data = _speak(base)
        assert status == 200 and data["ai"] is False and data["response"]
        assert _voice_records(caplog) == [(
            logging.ERROR,
            "voice_fallback surface=speak reason=provider exception=RuntimeError")]
        assert _SECRET not in caplog.text
        assert _count("speak", "provider") == 1 and _count("speak", "ok") == 0

    def test_an_answer_is_counted_and_logs_nothing(
            self, base, voiced, monkeypatch, caplog):
        import consciousness
        monkeypatch.setattr(consciousness, "speak", lambda *_a, **_k: "A reply.")
        caplog.set_level(logging.WARNING, logger="nested_worlds")
        status, data = _speak(base)
        assert status == 200 and data["ai"] is True
        # Counted after the reply is written, so the client can read first.
        assert _eventually(lambda: _count("speak", "ok") == 1)
        assert _voice_records(caplog) == []

    def test_budget_is_a_warning_not_an_alert(self, base, voiced, monkeypatch, caplog):
        import consciousness
        from consciousness import runtime

        def limited(*_a, **_k):
            raise runtime.VoiceBudgetLimited()
        monkeypatch.setattr(consciousness, "speak", limited)
        caplog.set_level(logging.WARNING, logger="nested_worlds")
        status, data = _speak(base)
        assert status == 200 and data["response"] == guard.QUIET_RESPONSE
        assert _voice_records(caplog) == [(
            logging.WARNING, "voice_fallback surface=speak reason=budget exception=-")]
        assert _count("speak", "budget") == 1

    def test_action_cap_is_its_own_reason(self, base, voiced, monkeypatch):
        import consciousness
        from consciousness import runtime

        def capped(*_a, **_k):
            raise runtime.ModelActionLimited()
        monkeypatch.setattr(consciousness, "speak", capped)
        assert _speak(base)[0] == 200
        assert _count("speak", "action_cap") == 1 and _count("speak", "budget") == 0

    def test_store_failure_is_logged_but_not_counted(
            self, base, voiced, monkeypatch, caplog):
        def locked(*_a, **_k):
            raise sqlite3.OperationalError("database is locked")
        monkeypatch.setattr(persistence, "get_node_history", locked)
        caplog.set_level(logging.WARNING, logger="nested_worlds")
        status, data = _speak(base)
        assert status == 200 and data["ai"] is False
        assert (logging.ERROR, "voice_fallback surface=speak reason=db "
                "exception=OperationalError") in _voice_records(caplog)
        assert observability.voice_outcome_summary() == {}

    def test_unconfigured_voice_is_an_alert(self, base, monkeypatch, caplog):
        from consciousness import runtime
        monkeypatch.delenv(guard.DISABLE_AI_ENV, raising=False)
        monkeypatch.setattr(runtime, "configured", lambda: False)
        monkeypatch.setattr(moderation, "screen",
                            lambda text, **_kwargs: SimpleNamespace(allowed=True))
        caplog.set_level(logging.WARNING, logger="nested_worlds")
        assert _speak(base)[1]["ai"] is False
        assert _voice_records(caplog)[0][0] == logging.ERROR
        assert _count("speak", "unconfigured") == 1

    def test_kill_switch_is_counted_as_disabled(self, base, monkeypatch):
        monkeypatch.setenv(guard.DISABLE_AI_ENV, "1")
        status, data = _speak(base)
        assert status == 200 and data["response"] == guard.QUIET_RESPONSE
        assert _count("speak", "disabled") == 1


    def test_a_player_who_hung_up_is_not_a_provider_failure(
            self, base, voiced, monkeypatch, caplog):
        # The success reply is written outside the classifying try, so a
        # socket closed before the reply arrives cannot be counted as a
        # provider failure (review of R3).
        import consciousness
        from server import handlers
        monkeypatch.setattr(consciousness, "speak", lambda *_a, **_k: "A reply.")
        real = handlers.Handler._send_json

        def hang_up(self, data, *args, **kwargs):
            if data.get("ai") is True:
                raise ConnectionResetError("peer went away")
            return real(self, data, *args, **kwargs)
        monkeypatch.setattr(handlers.Handler, "_send_json", hang_up)
        caplog.set_level(logging.WARNING, logger="nested_worlds")
        try:
            _speak(base)  # the dispatcher's own error path answers, or not
        except (urllib.error.URLError, ConnectionError):
            pass
        assert _count("speak", "provider") == 0
        assert _voice_records(caplog) == []


class TestOtherSurfaces:
    def test_agent_voice_provider_failure_is_counted(
            self, base, voiced, monkeypatch, caplog):
        import consciousness

        def boom(*_a, **_k):
            raise TimeoutError("slow")
        monkeypatch.setattr(consciousness, "voice_agent", boom)
        caplog.set_level(logging.WARNING, logger="nested_worlds")
        status, data = _post(base, "/agent/voice", {
            "node_name": store.world_tree(SEED).name, "agent_name": "Tessera",
            "message": "what arrived?"})
        assert status == 200 and data["ai"] is False
        assert _count("agent_voice", "provider") == 1
        assert (logging.ERROR, "voice_fallback surface=agent_voice reason=provider "
                "exception=TimeoutError") in _voice_records(caplog)

    def test_intention_outcomes(self, voiced, monkeypatch):
        import consciousness.interventions as interventions
        from server import intervention_api

        node = SimpleNamespace(level="Room")
        monkeypatch.setattr(interventions, "propose", lambda *a, **k: ["step"])
        assert intervention_api._propose("tidy", "", "Room-1", node, {}) == (["step"], None)
        assert _count("intention", "ok") == 1

        def boom(*_a, **_k):
            raise RuntimeError("upstream")
        monkeypatch.setattr(interventions, "propose", boom)
        proposal, quiet = intervention_api._propose("tidy", "", "Room-1", node, {})
        assert proposal is None and quiet["ai"] is False
        assert _count("intention", "provider") == 1

        monkeypatch.setenv(guard.DISABLE_AI_ENV, "1")
        intervention_api._propose("tidy", "", "Room-1", node, {})
        assert _count("intention", "disabled") == 1


class TestOutcomeRecording:
    def test_a_failing_counter_never_reaches_the_player(self, monkeypatch, caplog):
        def broken(*_a, **_k):
            raise sqlite3.OperationalError("disk full")
        monkeypatch.setattr(persistence, "increment_cost_calls", broken)
        caplog.set_level(logging.WARNING, logger="nested_worlds")
        observability.voice_outcome("speak", "provider", RuntimeError("x"))
        messages = [m for _, m in _voice_records(caplog)]
        assert messages[0].startswith("voice_fallback surface=speak reason=provider")
        assert messages[1].startswith("voice_outcome counter unavailable")

    def test_a_locked_store_cannot_hold_the_reply(self, caplog):
        # Another writer holds the write lock (a long transaction, a redact).
        # The counter waits at most ~50 ms, not the usual 5 s, then gives up.
        import time
        persistence.get_cost_calls("warm", guard._utc_day())  # create the DB
        holder = sqlite3.connect(persistence._DB_PATH)
        holder.execute("BEGIN IMMEDIATE")
        caplog.set_level(logging.WARNING, logger="nested_worlds")
        try:
            started = time.monotonic()
            observability.voice_outcome("speak", "disabled")
            elapsed = time.monotonic() - started
        finally:
            holder.rollback()
            holder.close()
        assert elapsed < 1.0
        assert any(m.startswith("voice_outcome counter unavailable")
                   for _, m in _voice_records(caplog))

    def test_unknown_outcomes_are_a_programming_error(self):
        with pytest.raises(ValueError):
            observability.voice_outcome("speak", "mystery")
        with pytest.raises(ValueError):
            observability.voice_outcome("chat", "ok")

    def test_prefix_match_is_literal(self):
        persistence.increment_cost_calls("voiceXoutcome:speak:ok", guard._utc_day())
        observability.voice_outcome("speak", "ok")
        assert observability.voice_outcome_summary() == {
            guard._utc_day(): {"speak": {"ok": 1}}}


class TestVoiceHealthCommand:
    def _run(self, *argv):
        import main
        args = main.build_parser().parse_args(["voice-health", *argv])
        args.func(args)

    def test_failures_in_the_window_exit_nonzero(self, monkeypatch, capsys):
        from consciousness import runtime
        monkeypatch.setattr(runtime, "configured", lambda: True)
        observability.voice_outcome("speak", "ok")
        observability.voice_outcome("speak", "provider", RuntimeError())
        observability.voice_outcome("speak", "budget")
        with pytest.raises(SystemExit, match="1 voice failure"):
            self._run()
        out = capsys.readouterr().out
        assert "speak        answered    1   quiet: budget 1, provider 1" in out
        assert "voice provider: configured" in out

    def test_limits_alone_pass(self, monkeypatch, capsys):
        from consciousness import runtime
        monkeypatch.setattr(runtime, "configured", lambda: True)
        observability.voice_outcome("speak", "ok")
        observability.voice_outcome("agent_voice", "budget")
        self._run()
        assert capsys.readouterr().out.rstrip().endswith("voice-health: ok")

    def test_no_usable_provider_fails_unless_switched_off(self, monkeypatch):
        from consciousness import runtime
        monkeypatch.setattr(runtime, "configured", lambda: False)
        with pytest.raises(SystemExit, match="no usable voice provider"):
            self._run()
        monkeypatch.setenv(guard.DISABLE_AI_ENV, "1")
        self._run()


class TestBetaMetrics:
    def test_report_separates_answered_from_quiet(self):
        observability.voice_outcome("speak", "ok")
        observability.voice_outcome("speak", "ok")
        observability.voice_outcome("speak", "provider", RuntimeError())
        metrics = beta_metrics.compute_metrics(persistence._DB_PATH, days=1)
        assert metrics["voice_outcomes"] == {"speak": {"ok": 2, "provider": 1}}
        rendered = beta_metrics.render(metrics)
        assert "speak            2 / 1      (provider 1)" in rendered
