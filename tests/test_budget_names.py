"""Neutral voice and image budget names. No live provider call.

Legacy NESTED_WORLDS_ANTHROPIC_* and NESTED_WORLDS_FAL_* names still set
the same allowance. A rename does not replenish calls already stored
under the old bucket keys, and two providers do not open two allowances.
"""
from __future__ import annotations

import pytest

import persistence
from consciousness.model_check import _SECRET_NAME
from consciousness import runtime
from main import main
from server import guard


def _day():
    return guard._utc_day()


def test_new_names_are_not_treated_as_secrets():
    names = (
        guard.VOICE_CAP_ENV, guard.VOICE_PER_USER_CAP_ENV,
        guard.IMAGE_CAP_ENV, guard.IMAGE_PER_USER_CAP_ENV,
        runtime.NODE_PROVIDER_ENV, runtime.INHABITANT_PROVIDER_ENV,
        runtime.INTENT_PROVIDER_ENV, runtime.MODERATION_PROVIDER_ENV,
        runtime.PROVIDER_ENV,
    )
    for name in names:
        assert _SECRET_NAME.search(name) is None, name


def test_unset_caps_keep_the_historical_defaults(monkeypatch):
    for name in (
        guard.VOICE_CAP_ENV, guard.ANTHROPIC_CAP_ENV,
        guard.VOICE_PER_USER_CAP_ENV, guard.ANTHROPIC_PER_USER_CAP_ENV,
        guard.IMAGE_CAP_ENV, guard.FAL_CAP_ENV,
        guard.IMAGE_PER_USER_CAP_ENV, guard.FAL_PER_USER_CAP_ENV,
    ):
        monkeypatch.delenv(name, raising=False)
    assert guard.resolve_budget_cap(
        guard.VOICE_CAP_ENV, guard.ANTHROPIC_CAP_ENV, guard._DEFAULT_ANTHROPIC_DAILY,
    ) == (500, ())
    assert guard.resolve_budget_cap(
        guard.IMAGE_CAP_ENV, guard.FAL_CAP_ENV, guard._DEFAULT_FAL_DAILY,
    ) == (200, ())
    assert guard.budget_configuration_line() is None


@pytest.mark.parametrize("neutral,legacy,expected", [
    ("11", None, 11),
    (None, "9", 9),
    ("8", "8", 8),
    ("  ", "6", 6),
    ("6", "   ", 6),
    ("  ", "  ", 500),
    ("0", None, 0),
])
def test_cap_precedence(monkeypatch, neutral, legacy, expected):
    if neutral is None:
        monkeypatch.delenv(guard.VOICE_CAP_ENV, raising=False)
    else:
        monkeypatch.setenv(guard.VOICE_CAP_ENV, neutral)
    if legacy is None:
        monkeypatch.delenv(guard.ANTHROPIC_CAP_ENV, raising=False)
    else:
        monkeypatch.setenv(guard.ANTHROPIC_CAP_ENV, legacy)
    cap, problems = guard.resolve_budget_cap(
        guard.VOICE_CAP_ENV, guard.ANTHROPIC_CAP_ENV, 500)
    assert cap == expected
    assert problems == ()


def test_a_negative_cap_is_a_startup_error(monkeypatch):
    monkeypatch.setenv(guard.VOICE_CAP_ENV, "-3")
    monkeypatch.setenv(guard.ANTHROPIC_CAP_ENV, "20")
    cap, problems = guard.resolve_budget_cap(
        guard.VOICE_CAP_ENV, guard.ANTHROPIC_CAP_ENV, 500)
    assert cap == 0
    assert problems == (f"{guard.VOICE_CAP_ENV} is negative",)
    assert "-3" not in problems[0]
    assert "20" not in problems[0]
    assert guard.budget_configuration_line() is not None
    assert guard.consume_anthropic() is False
    assert persistence.get_cost_calls(guard.VOICE_BUCKET, _day()) == 0


def _usable_provider(monkeypatch):
    from consciousness.runtime import Completion

    class Ok:
        name = "okprov"

        def configured(self):
            return True

        def default_model(self, task):
            return f"ok-{task}"

        def cache_reference_tokens(self, model):
            return None

        def generate(self, **kwargs):
            return Completion("ok", True, provider=self.name, resolved_model=kwargs["model"])

    monkeypatch.setattr(runtime, "_REGISTERED", {})
    runtime.reset_provider_selection()
    runtime.register_provider("okprov", lambda: Ok())
    monkeypatch.setenv(runtime.PROVIDER_ENV, "okprov")
    for name in (
        runtime.SHARED_MODEL_ENV, runtime.NODE_MODEL_ENV,
        runtime.INHABITANT_MODEL_ENV, runtime.INTENT_MODEL_ENV,
        runtime.MODERATION_MODEL_ENV,
    ):
        monkeypatch.delenv(name, raising=False)


def test_disagreement_uses_the_lower_cap_and_warns(monkeypatch, capsys):
    _usable_provider(monkeypatch)
    monkeypatch.setenv(guard.VOICE_CAP_ENV, "10")
    monkeypatch.setenv(guard.ANTHROPIC_CAP_ENV, "4")
    resolved = guard.resolve_budget_cap(
        guard.VOICE_CAP_ENV, guard.ANTHROPIC_CAP_ENV, 500)
    cap, problems = resolved
    assert cap == 4
    assert problems == ()
    assert "disagree" in resolved.warnings[0]
    assert "10" in resolved.warnings[0] and "4" in resolved.warnings[0]
    assert guard.budget_configuration_line() is None
    warning = guard.budget_configuration_warning_line()
    assert warning is not None and "lower cap 4" in warning
    results = [guard.consume_anthropic() for _ in range(6)]
    assert results == [True, True, True, True, False, False]
    # Both refusals still increment, then the combined count is over the cap.
    assert persistence.get_cost_calls(guard.ANTHROPIC_BUCKET, _day()) == 6
    assert persistence.get_cost_calls(guard.VOICE_BUCKET, _day()) == 0

    main(["models"])
    out = capsys.readouterr().out
    assert "Budget warning:" in out
    assert "lower cap 4" in out
    assert "Budget configuration:" not in out


def test_invalid_cap_refuses_without_echoing_the_value(monkeypatch):
    pasted = "sk-live-not-an-integer"
    monkeypatch.setenv(guard.VOICE_CAP_ENV, pasted)
    monkeypatch.setenv(guard.ANTHROPIC_CAP_ENV, "50")
    cap, problems = guard.resolve_budget_cap(
        guard.VOICE_CAP_ENV, guard.ANTHROPIC_CAP_ENV, 500)
    assert cap == 0
    assert problems == (f"{guard.VOICE_CAP_ENV} is not an integer",)
    assert pasted not in problems[0]
    assert guard.consume_anthropic() is False
    assert persistence.get_cost_calls(guard.VOICE_BUCKET, _day()) == 0
    line = guard.budget_configuration_line()
    assert pasted not in line
    assert "50" not in line


def test_zero_is_a_valid_refusal(monkeypatch):
    monkeypatch.setenv(guard.IMAGE_CAP_ENV, "0")
    cap, problems = guard.resolve_budget_cap(
        guard.IMAGE_CAP_ENV, guard.FAL_CAP_ENV, 200)
    assert (cap, problems) == (0, ())
    assert guard.budget_configuration_line() is None
    assert guard.consume_fal() is False
    assert persistence.get_cost_calls(guard.IMAGE_BUCKET, _day()) == 0


def test_image_legacy_name_still_sets_the_cap(monkeypatch):
    monkeypatch.setenv(guard.FAL_CAP_ENV, "1")
    monkeypatch.delenv(guard.IMAGE_CAP_ENV, raising=False)
    assert [guard.consume_fal() for _ in range(2)] == [True, False]
    assert persistence.get_cost_calls(guard.FAL_BUCKET, _day()) == 2
    assert persistence.get_cost_calls(guard.IMAGE_BUCKET, _day()) == 0


def test_charges_stay_on_the_canonical_key_and_are_not_copied(monkeypatch):
    monkeypatch.setenv(guard.ANTHROPIC_CAP_ENV, "2")
    monkeypatch.delenv(guard.VOICE_CAP_ENV, raising=False)
    day = _day()
    persistence.increment_cost_calls(guard.ANTHROPIC_BUCKET, day)
    assert guard.effective_calls(guard.VOICE_BUCKET, day) == 1
    assert guard.consume_anthropic() is True
    assert guard.consume_anthropic() is False
    assert persistence.get_cost_calls(guard.ANTHROPIC_BUCKET, day) == 3
    assert persistence.get_cost_calls(guard.VOICE_BUCKET, day) == 0
    assert guard.effective_calls(guard.VOICE_BUCKET, day) == 3


def test_legacy_per_user_rows_still_count_before_the_global_charge(monkeypatch):
    monkeypatch.setenv(guard.ANTHROPIC_CAP_ENV, "10")
    monkeypatch.setenv(guard.ANTHROPIC_PER_USER_CAP_ENV, "2")
    day = _day()
    user = guard._user_bucket(guard.ANTHROPIC_BUCKET, "nw_alice")
    persistence.increment_cost_calls(user, day)
    persistence.increment_cost_calls(user, day)
    assert guard.consume_anthropic(user_key="nw_alice") is False
    assert persistence.get_cost_calls(guard.ANTHROPIC_BUCKET, day) == 0
    assert persistence.get_cost_calls(user, day) == 3
    voice_user = guard._user_bucket(guard.VOICE_BUCKET, "nw_alice")
    # The refused attempt incremented the canonical per-user key. It did
    # not open a voice key and it did not touch the shared counter.
    assert persistence.get_cost_calls(voice_user, day) == 0
    assert guard.consume_anthropic(user_key="nw_bob") is True
    assert persistence.get_cost_calls(guard.ANTHROPIC_BUCKET, day) == 1


def test_legacy_image_rows_still_count(monkeypatch):
    monkeypatch.setenv(guard.FAL_CAP_ENV, "2")
    day = _day()
    persistence.increment_cost_calls(guard.FAL_BUCKET, day)
    persistence.increment_cost_calls(guard.FAL_BUCKET, day)
    assert guard.consume_fal() is False
    assert persistence.get_cost_calls(guard.FAL_BUCKET, day) == 3
    assert persistence.get_cost_calls(guard.IMAGE_BUCKET, day) == 0
    assert guard.effective_calls(guard.IMAGE_BUCKET, day) == 3


def test_moderation_budget_stays_separate(monkeypatch):
    monkeypatch.setenv(guard.MODERATION_CAP_ENV, "1")
    assert guard.ANTHROPIC_BUCKET == "anthropic"
    assert guard.VOICE_BUCKET == "voice"
    assert guard.FAL_BUCKET == "fal_ai"
    assert guard.IMAGE_BUCKET == "image"
    assert guard.consume_voice is guard.consume_anthropic
    assert guard.consume_image is guard.consume_fal
    day = _day()
    guard.consume_anthropic()
    assert persistence.get_cost_calls(guard.MODERATION_BUCKET, day) == 0
    from server import moderation
    # A moderation reserve writes its own bucket, never the voice key.
    assert hasattr(moderation, "moderation_disabled")
    assert persistence.get_cost_calls(guard.ANTHROPIC_BUCKET, day) == 1
    assert persistence.get_cost_calls(guard.VOICE_BUCKET, day) == 0


def test_serve_warns_on_a_disagreeing_cap_and_still_listens(monkeypatch, caplog):
    import logging
    import server

    _usable_provider(monkeypatch)
    monkeypatch.setenv(guard.IMAGE_CAP_ENV, "3")
    monkeypatch.setenv(guard.FAL_CAP_ENV, "9")
    monkeypatch.setenv("NESTED_WORLDS_HEARTBEAT", "0")
    monkeypatch.setenv("NESTED_WORLDS_CAUSAL_PUMP", "0")
    monkeypatch.setattr(server.observability, "setup", lambda: None)
    monkeypatch.setattr(server.guard, "canonical_seed", lambda: None)
    opened = []

    class Listener:
        def __init__(self, address, handler):
            opened.append(address)

        def serve_forever(self):
            return

        def server_close(self):
            return

    monkeypatch.setattr(server, "_ThreadedServer", Listener)
    with caplog.at_level(logging.WARNING, logger="nested_worlds.guard"):
        server.run(host="127.0.0.1", port=0)
    assert opened
    assert "lower cap 3" in caplog.text


def test_serve_refuses_an_invalid_cap_before_listen(monkeypatch, capsys):
    import server

    _usable_provider(monkeypatch)
    monkeypatch.setenv(guard.IMAGE_CAP_ENV, "nope")
    monkeypatch.setattr(server.observability, "setup", lambda: None)
    monkeypatch.setattr(server.guard, "canonical_seed", lambda: None)

    def opened(*_args, **_kwargs):
        raise AssertionError("listener opened")

    monkeypatch.setattr(server, "_ThreadedServer", opened)
    with pytest.raises(SystemExit) as caught:
        server.run(host="127.0.0.1", port=0)
    assert "is not an integer" in str(caught.value)
    assert "nope" not in str(caught.value)
    assert capsys.readouterr().out == ""


def test_voice_health_shows_legacy_spend_and_fails_on_a_bad_cap(monkeypatch, capsys):
    import main as cli
    from consciousness import model_check

    day = _day()
    persistence.increment_cost_calls(guard.ANTHROPIC_BUCKET, day)
    persistence.increment_cost_calls(guard.ANTHROPIC_BUCKET, day)
    monkeypatch.setattr(runtime, "configured", lambda *args, **kwargs: True)
    report = model_check.ModelReport(provider="fixture", tasks=())
    monkeypatch.setattr(model_check, "check_model_configuration", lambda *_a: report)
    args = cli.build_parser().parse_args(["voice-health"])
    args.func(args)
    out = capsys.readouterr().out
    assert "voice budget today: 2/500 calls" in out
    assert out.rstrip().endswith("voice-health: ok")

    monkeypatch.setenv(guard.VOICE_CAP_ENV, "nope")
    with pytest.raises(SystemExit, match="budget configuration"):
        args.func(args)
    assert "nope" not in capsys.readouterr().out


def test_voice_health_fails_an_unconfigured_moderation_provider(monkeypatch, capsys):
    import main as cli
    from consciousness import model_check

    def configured(task=None):
        return task != runtime.MODERATION_TASK

    monkeypatch.setattr(runtime, "configured", configured)
    report = model_check.ModelReport(provider="fixture", tasks=())
    monkeypatch.setattr(model_check, "check_model_configuration", lambda *_a: report)
    args = cli.build_parser().parse_args(["voice-health"])
    with pytest.raises(SystemExit, match="no usable moderation provider"):
        args.func(args)
    out = capsys.readouterr().out
    assert "voice provider: configured" in out
    assert "moderation provider: NOT configured" in out


def test_voice_health_fails_an_invalid_image_cap_while_ai_is_off(monkeypatch, capsys):
    import main as cli
    from consciousness import model_check

    monkeypatch.setenv(guard.DISABLE_AI_ENV, "1")
    monkeypatch.setenv(guard.IMAGE_CAP_ENV, "nope")
    monkeypatch.setattr(runtime, "configured", lambda *args, **kwargs: True)
    report = model_check.ModelReport(provider="fixture", tasks=())
    monkeypatch.setattr(model_check, "check_model_configuration", lambda *_a: report)
    args = cli.build_parser().parse_args(["voice-health"])
    with pytest.raises(SystemExit, match="budget configuration"):
        args.func(args)
    out = capsys.readouterr().out
    assert "nope" not in out
    assert "kill switch:" in out


def test_voice_health_prints_a_cap_disagreement_and_stays_ok(monkeypatch, capsys):
    import main as cli
    from consciousness import model_check

    monkeypatch.setenv(guard.VOICE_CAP_ENV, "1000")
    monkeypatch.setenv(guard.ANTHROPIC_CAP_ENV, "500")
    monkeypatch.setattr(runtime, "configured", lambda *args, **kwargs: True)
    report = model_check.ModelReport(provider="fixture", tasks=())
    monkeypatch.setattr(model_check, "check_model_configuration", lambda *_a: report)
    args = cli.build_parser().parse_args(["voice-health"])
    args.func(args)
    out = capsys.readouterr().out
    assert "Budget warning:" in out
    assert "lower cap 500" in out
    assert "moderation provider: configured" in out
    assert out.rstrip().endswith("voice-health: ok")


def _schema29_consume(bucket, env, default, user_key=None, user_env=None, user_default=None):
    """Spend one call the way ``server/guard.py`` did at ``18e5bbd``.

    That binary increments ``anthropic`` or ``fal_ai`` only, including the
    ``:u:<hash>`` per-user key, and it reads only the legacy cap variables.
    Invalid text falls through to the default. It does not read a ``voice``
    or ``image`` row.
    """
    if user_key:
        user_cap = guard._cap_for(user_env, user_default)
        user_bucket = guard._user_bucket(bucket, user_key)
        if user_cap <= 0:
            return False
        spent = persistence.increment_cost_calls(user_bucket, _day())
        if spent > user_cap:
            return False
    cap = guard._cap_for(env, default)
    if cap <= 0:
        return False
    spent = persistence.increment_cost_calls(bucket, _day())
    return spent <= cap


def _rows():
    import sqlite3
    conn = sqlite3.connect(persistence._DB_PATH)
    try:
        return dict(conn.execute(
            "SELECT bucket, calls FROM cost_budget WHERE day = ?", (_day(),)
        ).fetchall())
    finally:
        conn.close()


def test_schema29_and_this_binary_share_one_spent_allowance(monkeypatch):
    """Upgrade and rollback on one database do not replenish or double-count.

    Both writers use the schema-29 keys. Spend recorded before the switch
    is still spent after it, and spend recorded after the switch is still
    spent when the schema-29 writer runs again.
    """
    monkeypatch.setenv(guard.ANTHROPIC_CAP_ENV, "3")
    monkeypatch.setenv(guard.ANTHROPIC_PER_USER_CAP_ENV, "2")
    monkeypatch.setenv(guard.FAL_CAP_ENV, "2")
    monkeypatch.setenv(guard.FAL_PER_USER_CAP_ENV, "1")
    monkeypatch.delenv(guard.VOICE_CAP_ENV, raising=False)
    monkeypatch.delenv(guard.VOICE_PER_USER_CAP_ENV, raising=False)
    monkeypatch.delenv(guard.IMAGE_CAP_ENV, raising=False)
    monkeypatch.delenv(guard.IMAGE_PER_USER_CAP_ENV, raising=False)
    assert persistence.schema_versions()[-1] == 29
    day = _day()
    alice_voice = guard._user_bucket(guard.ANTHROPIC_BUCKET, "nw_alice")
    bob_voice = guard._user_bucket(guard.ANTHROPIC_BUCKET, "nw_bob")
    alice_image = guard._user_bucket(guard.FAL_BUCKET, "nw_alice")

    assert _schema29_consume(
        guard.ANTHROPIC_BUCKET, guard.ANTHROPIC_CAP_ENV, 500,
        "nw_alice", guard.ANTHROPIC_PER_USER_CAP_ENV, 150,
    ) is True
    assert _schema29_consume(
        guard.ANTHROPIC_BUCKET, guard.ANTHROPIC_CAP_ENV, 500,
        "nw_alice", guard.ANTHROPIC_PER_USER_CAP_ENV, 150,
    ) is True
    assert _schema29_consume(
        guard.FAL_BUCKET, guard.FAL_CAP_ENV, 200,
        "nw_alice", guard.FAL_PER_USER_CAP_ENV, 60,
    ) is True
    assert persistence.get_cost_calls(guard.ANTHROPIC_BUCKET, day) == 2
    assert persistence.get_cost_calls(alice_voice, day) == 2
    assert persistence.get_cost_calls(guard.FAL_BUCKET, day) == 1
    assert persistence.get_cost_calls(alice_image, day) == 1

    # This binary sees the schema-29 spend. Alice is already at her cap.
    assert guard.consume_anthropic(user_key="nw_alice") is False
    assert persistence.get_cost_calls(guard.ANTHROPIC_BUCKET, day) == 2
    assert persistence.get_cost_calls(alice_voice, day) == 3
    assert guard.consume_fal(user_key="nw_alice") is False
    assert persistence.get_cost_calls(guard.FAL_BUCKET, day) == 1
    assert persistence.get_cost_calls(alice_image, day) == 2
    assert guard.consume_anthropic(user_key="nw_bob") is True
    assert persistence.get_cost_calls(guard.ANTHROPIC_BUCKET, day) == 3
    assert persistence.get_cost_calls(bob_voice, day) == 1
    assert guard.consume_anthropic(user_key="nw_bob") is False
    assert persistence.get_cost_calls(guard.ANTHROPIC_BUCKET, day) == 4
    assert persistence.get_cost_calls(guard.VOICE_BUCKET, day) == 0
    assert persistence.get_cost_calls(guard.IMAGE_BUCKET, day) == 0

    # Rolled back. Bob's per-user row is already at its cap, so the
    # schema-29 writer refuses before the global counter. A fresh user
    # still has per-user room and is refused on the global spend this
    # binary already recorded. Neither call finds a new allowance.
    assert persistence.get_cost_calls(bob_voice, day) == 2
    assert _schema29_consume(
        guard.ANTHROPIC_BUCKET, guard.ANTHROPIC_CAP_ENV, 500,
        "nw_bob", guard.ANTHROPIC_PER_USER_CAP_ENV, 150,
    ) is False
    assert persistence.get_cost_calls(guard.ANTHROPIC_BUCKET, day) == 4
    assert persistence.get_cost_calls(bob_voice, day) == 3
    assert _schema29_consume(
        guard.ANTHROPIC_BUCKET, guard.ANTHROPIC_CAP_ENV, 500,
        "nw_dave", guard.ANTHROPIC_PER_USER_CAP_ENV, 150,
    ) is False
    assert persistence.get_cost_calls(guard.ANTHROPIC_BUCKET, day) == 5
    assert _schema29_consume(
        guard.FAL_BUCKET, guard.FAL_CAP_ENV, 200,
        "nw_bob", guard.FAL_PER_USER_CAP_ENV, 60,
    ) is True
    assert persistence.get_cost_calls(guard.FAL_BUCKET, day) == 2
    assert guard.consume_fal(user_key="nw_carol") is False
    assert persistence.get_cost_calls(guard.FAL_BUCKET, day) == 3


def test_a_transient_neutral_row_counts_here_and_is_not_rewritten(monkeypatch):
    monkeypatch.setenv(guard.VOICE_CAP_ENV, "3")
    monkeypatch.setenv(guard.VOICE_PER_USER_CAP_ENV, "2")
    monkeypatch.delenv(guard.ANTHROPIC_CAP_ENV, raising=False)
    monkeypatch.delenv(guard.ANTHROPIC_PER_USER_CAP_ENV, raising=False)
    day = _day()
    persistence.increment_cost_calls(guard.ANTHROPIC_BUCKET, day)
    persistence.increment_cost_calls(guard.VOICE_BUCKET, day)
    persistence.increment_cost_calls(guard.VOICE_BUCKET, day)
    transient_user = guard._user_bucket(guard.VOICE_BUCKET, "nw_alice")
    canonical_user = guard._user_bucket(guard.ANTHROPIC_BUCKET, "nw_alice")
    persistence.increment_cost_calls(transient_user, day)
    persistence.increment_cost_calls(transient_user, day)
    persistence.increment_cost_calls(guard.MODERATION_BUCKET, day)
    persistence.increment_cost_calls("voice_outcome:speak:ok", day)
    before = _rows()

    assert guard.effective_calls(guard.VOICE_BUCKET, day) == 3
    assert guard.consume_anthropic(user_key="nw_alice") is False
    assert persistence.get_cost_calls(guard.ANTHROPIC_BUCKET, day) == 1
    assert persistence.get_cost_calls(guard.VOICE_BUCKET, day) == 2
    assert persistence.get_cost_calls(canonical_user, day) == 1
    assert persistence.get_cost_calls(transient_user, day) == 2
    assert persistence.get_cost_calls(guard.MODERATION_BUCKET, day) == 1
    assert persistence.get_cost_calls("voice_outcome:speak:ok", day) == 1
    # The refused call increments only Alice's canonical per-user key.
    # The global anthropic row and the transient voice row are unchanged:
    # nothing was copied or deleted.
    assert persistence.get_cost_calls(guard.ANTHROPIC_BUCKET, day) == before[guard.ANTHROPIC_BUCKET]
    assert guard.VOICE_BUCKET in before
    assert persistence.get_cost_calls(guard.VOICE_BUCKET, day) == before[guard.VOICE_BUCKET]
