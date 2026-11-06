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


def test_a_negative_cap_clamps_and_disagreement_does_not_raise_it(monkeypatch):
    monkeypatch.setenv(guard.VOICE_CAP_ENV, "-3")
    monkeypatch.setenv(guard.ANTHROPIC_CAP_ENV, "20")
    cap, problems = guard.resolve_budget_cap(
        guard.VOICE_CAP_ENV, guard.ANTHROPIC_CAP_ENV, 500)
    assert cap == 0
    assert problems != ()
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


def test_disagreement_uses_the_lower_cap_and_fails_startup(monkeypatch, capsys):
    _usable_provider(monkeypatch)
    monkeypatch.setenv(guard.VOICE_CAP_ENV, "10")
    monkeypatch.setenv(guard.ANTHROPIC_CAP_ENV, "4")
    cap, problems = guard.resolve_budget_cap(
        guard.VOICE_CAP_ENV, guard.ANTHROPIC_CAP_ENV, 500)
    assert cap == 4
    assert "disagree" in problems[0]
    assert "10" in problems[0] and "4" in problems[0]
    line = guard.budget_configuration_line()
    assert line is not None and "lower cap 4" in line
    results = [guard.consume_anthropic() for _ in range(6)]
    assert results == [True, True, True, True, False, False]
    # Both refusals still increment, then the combined count is over the cap.
    assert persistence.get_cost_calls(guard.VOICE_BUCKET, _day()) == 6
    assert persistence.get_cost_calls(guard.ANTHROPIC_BUCKET, _day()) == 0

    with pytest.raises(SystemExit) as caught:
        main(["models"])
    assert "lower cap 4" in str(caught.value)
    assert "Budget configuration:" in capsys.readouterr().out


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
    assert persistence.get_cost_calls(guard.IMAGE_BUCKET, _day()) == 2
    assert persistence.get_cost_calls(guard.FAL_BUCKET, _day()) == 0


def test_legacy_rows_still_count_and_are_not_copied(monkeypatch):
    monkeypatch.setenv(guard.ANTHROPIC_CAP_ENV, "2")
    monkeypatch.delenv(guard.VOICE_CAP_ENV, raising=False)
    day = _day()
    persistence.increment_cost_calls(guard.ANTHROPIC_BUCKET, day)
    assert guard.effective_calls(guard.VOICE_BUCKET, day) == 1
    assert guard.consume_anthropic() is True
    assert guard.consume_anthropic() is False
    assert persistence.get_cost_calls(guard.ANTHROPIC_BUCKET, day) == 1
    assert persistence.get_cost_calls(guard.VOICE_BUCKET, day) == 2
    assert guard.effective_calls(guard.VOICE_BUCKET, day) == 3


def test_legacy_per_user_rows_still_count_before_the_global_charge(monkeypatch):
    monkeypatch.setenv(guard.ANTHROPIC_CAP_ENV, "10")
    monkeypatch.setenv(guard.ANTHROPIC_PER_USER_CAP_ENV, "2")
    day = _day()
    user = guard._user_bucket(guard.ANTHROPIC_BUCKET, "nw_alice")
    persistence.increment_cost_calls(user, day)
    persistence.increment_cost_calls(user, day)
    assert guard.consume_anthropic(user_key="nw_alice") is False
    assert persistence.get_cost_calls(guard.VOICE_BUCKET, day) == 0
    assert persistence.get_cost_calls(user, day) == 2
    voice_user = guard._user_bucket(guard.VOICE_BUCKET, "nw_alice")
    # The refused attempt incremented the new per-user key, then added the
    # legacy count. It did not touch the shared counter.
    assert persistence.get_cost_calls(voice_user, day) == 1
    assert guard.consume_anthropic(user_key="nw_bob") is True
    assert persistence.get_cost_calls(guard.VOICE_BUCKET, day) == 1


def test_legacy_image_rows_still_count(monkeypatch):
    monkeypatch.setenv(guard.FAL_CAP_ENV, "2")
    day = _day()
    persistence.increment_cost_calls(guard.FAL_BUCKET, day)
    persistence.increment_cost_calls(guard.FAL_BUCKET, day)
    assert guard.consume_fal() is False
    assert persistence.get_cost_calls(guard.FAL_BUCKET, day) == 2
    assert persistence.get_cost_calls(guard.IMAGE_BUCKET, day) == 1
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
    assert persistence.get_cost_calls(guard.VOICE_BUCKET, day) == 1


def test_serve_refuses_a_disagreeing_cap_before_listen(monkeypatch, capsys):
    import server

    _usable_provider(monkeypatch)
    monkeypatch.setenv(guard.IMAGE_CAP_ENV, "3")
    monkeypatch.setenv(guard.FAL_CAP_ENV, "9")
    monkeypatch.setattr(server.observability, "setup", lambda: None)
    monkeypatch.setattr(server.guard, "canonical_seed", lambda: None)

    def opened(*_args, **_kwargs):
        raise AssertionError("listener opened")

    monkeypatch.setattr(server, "_ThreadedServer", opened)
    with pytest.raises(SystemExit) as caught:
        server.run(host="127.0.0.1", port=0)
    assert "lower cap 3" in str(caught.value)
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
