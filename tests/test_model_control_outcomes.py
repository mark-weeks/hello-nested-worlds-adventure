"""A control incident stays quiet for players and visible to the operator."""
from __future__ import annotations

import json
import logging
import os
from types import SimpleNamespace

import pytest

import persistence
from consciousness import model_dispatch as dispatch, model_policy as policy, runtime
from consciousness.openai_compat_provider import (
    API_KEY_ENV, BASE_URL_ENV, REASONING_EFFORT_ENV, SEND_STORE_FALSE_ENV,
    STRUCTURED_OUTPUTS_ENV, TIMEOUT_ENV, OpenAICompatibleProvider,
)
from consciousness.runtime import SystemBlock
from main import main
from multiverse import store
from persistence import model_spend
from server import guard, intervention_api, moderation, observability


_MODEL = "synthetic-model"
_SECRET = "sk-private-control-fixture"


def _policy_file(tmp_path, *enabled):
    routes = {task: {"enabled": False} for task in (*runtime.TASKS, "images")}
    for task in enabled:
        routes[task] = {
            "enabled": True, "adapter": "openai_compatible",
            "endpoint": "https://synthetic.example/v1/chat/completions",
            "model": _MODEL, "resolved_models": [_MODEL],
            "max_input_tokens": 1000, "input_bound_kind": "provider_context_maximum",
            "input_bound_evidence": "Synthetic stub bound; no external calls.",
            "max_output_tokens": 500, "timeout_seconds": "12",
            "options": {"max_tokens_param": "max_completion_tokens", "structured_outputs": True,
                        "send_store_false": True, "reasoning_effort": "none"},
            "prices": {"input_per_million_usd": "1", "output_per_million_usd": "2",
                       "cache_read_per_million_usd": "0.1", "cache_write_per_million_usd": "2"},
            "data_use_note": "Authored fake transport only.",
            "approval_reference": "Synthetic test fixture; no live approval.",
        }
    data = {"schema_version": 1, "policy_id": "outcomes-fixture", "currency": "USD",
            "reset": "UTC", "routes": routes}
    if enabled:
        data.update(limits={"global_daily_usd": "1", "participant_daily_usd": "0.5"},
                    ledger_retention_days=2)
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(data))
    return path


@pytest.fixture
def controlled(tmp_path, monkeypatch, accounts):
    monkeypatch.setenv(policy.POLICY_ENV, str(_policy_file(tmp_path, *runtime.TASKS)))
    monkeypatch.setenv(runtime.PROVIDER_ENV, "openai_compatible")
    for name in (runtime.NODE_MODEL_ENV, runtime.INHABITANT_MODEL_ENV,
                 runtime.INTENT_MODEL_ENV, runtime.MODERATION_MODEL_ENV):
        monkeypatch.setenv(name, _MODEL)
    monkeypatch.setenv(BASE_URL_ENV, "https://synthetic.example/v1")
    monkeypatch.setenv(API_KEY_ENV, _SECRET)
    monkeypatch.setenv(STRUCTURED_OUTPUTS_ENV, "1")
    monkeypatch.setenv(SEND_STORE_FALSE_ENV, "1")
    monkeypatch.setenv(REASONING_EFFORT_ENV, "none")
    monkeypatch.setenv(TIMEOUT_ENV, "12")
    monkeypatch.delenv(guard.DISABLE_AI_ENV, raising=False)
    monkeypatch.delenv(moderation.DISABLE_MODERATION_ENV, raising=False)
    state = SimpleNamespace(model=_MODEL, requests=[], key=accounts[0])

    def transport(request):
        state.requests.append(request)
        return 200, (), json.dumps({
            "model": state.model,
            "choices": [{"finish_reason": "stop", "message": {"content": "A bell sounds."}}],
            "usage": {"prompt_tokens": 10, "total_tokens": 12,
                      "completion_tokens": 2, "prompt_tokens_details": {"cached_tokens": 0}},
        }).encode()

    state.adapter = OpenAICompatibleProvider(transport=transport)
    monkeypatch.setattr(runtime, "provider_for", lambda task: state.adapter)
    return state


def _call(controlled):
    return runtime.generate(
        endpoint="fixture", task="node", model=_MODEL, user_key=controlled.key,
        system=(SystemBlock("synthetic context"),),
        messages=[{"role": "user", "content": "private fixture words"}], max_tokens=32,
    )


def test_new_anomaly_is_one_safe_error_and_a_durable_health_failure(controlled, caplog, capsys):
    controlled.model = "unexpected-safe-model"
    for _ in range(2):
        with pytest.raises(dispatch.ModelControlStopped):
            _call(controlled)
    assert len(controlled.requests) == 1
    errors = [r for r in caplog.records if r.name == "nested_worlds.model_control"]
    assert [(r.levelno, r.getMessage()) for r in errors] == [
        (logging.ERROR, "model_control_stopped reason=billing_anomaly")]
    assert _SECRET not in caplog.text and "private fixture words" not in caplog.text
    with persistence._connection() as conn:
        assert conn.execute("SELECT resolved_model FROM model_spend_reservations").fetchone() == (
            "unexpected-safe-model",)
    with pytest.raises(SystemExit, match="controlled model dispatch is stopped"):
        main(["voice-health"])
    output = capsys.readouterr().out
    assert "STOPPED (billing_anomaly)" in output
    assert "images: disabled (intentional)" in output


def test_failed_settlement_cannot_resume_after_process_state_is_reset(controlled, monkeypatch):
    def unavailable(*_args, **_kwargs):
        raise RuntimeError("private storage payload")

    monkeypatch.setattr(model_spend, "settle", unavailable)
    monkeypatch.setattr(model_spend, "mark_settlement_fault", unavailable)
    with pytest.raises(dispatch.ModelControlStopped):
        _call(controlled)
    dispatch.reset_for_tests()
    policy.reset_for_tests()
    monkeypatch.setattr(runtime, "reserve_model_action",
                        lambda *_args: pytest.fail("a stopped call charged a legacy cap"))
    with pytest.raises(dispatch.ModelControlStopped):
        _call(controlled)
    assert len(controlled.requests) == 1
    status = model_spend.status()
    assert status["latched"] is True and status["stop_reason"] == "unsettled_startup"
    assert status["unresolved_reservations"] == 1


@pytest.mark.parametrize("command", ["models", "voice-health"])
def test_all_off_operator_commands_do_not_resolve_disabled_adapters(
        tmp_path, monkeypatch, capsys, command):
    monkeypatch.setenv(policy.POLICY_ENV, str(_policy_file(tmp_path)))
    monkeypatch.setenv(runtime.NODE_PROVIDER_ENV, "disabled-provider-with-no-sdk")
    monkeypatch.setenv(runtime.NODE_MODEL_ENV, "")
    monkeypatch.setattr(runtime, "provider_for",
                        lambda *_args: pytest.fail("resolved a disabled adapter"))
    main([command])
    output = capsys.readouterr().out
    for task in (*runtime.TASKS, "images"):
        assert f"{task}: disabled (intentional)" in output
    assert "NOT configured" not in output
    if command == "models":
        assert not persistence._DB_PATH.exists()


@pytest.mark.parametrize("command", ["models", "voice-health"])
def test_controlled_commands_refuse_direct_probes_without_calling_an_adapter(
        tmp_path, monkeypatch, capsys, command):
    monkeypatch.setenv(policy.POLICY_ENV, str(_policy_file(tmp_path)))
    from consciousness import model_check
    monkeypatch.setattr(model_check, "probe_distinct_models",
                        lambda *_args: pytest.fail("made a direct live probe"))
    with pytest.raises(SystemExit, match="controlled direct probes are unavailable"):
        main([command, "--probe"])
    capsys.readouterr()


def test_moderation_preflight_ignores_the_voice_kill_switch(controlled, monkeypatch):
    monkeypatch.setenv(guard.DISABLE_AI_ENV, "1")
    dispatch.preflight("moderation", controlled.key, max_tokens=32, model=_MODEL)
    with pytest.raises(policy.ModelPolicyDenied):
        dispatch.preflight("node", controlled.key, max_tokens=32, model=_MODEL)
    assert controlled.requests == []


def test_partial_policy_is_healthy_without_resolving_disabled_routes(controlled, monkeypatch, capsys):
    from pathlib import Path
    from consciousness import model_check

    path = Path(os.environ[policy.POLICY_ENV])
    document = json.loads(path.read_text())
    for task in runtime.TASKS:
        if task != "node":
            document["routes"][task] = {"enabled": False}
    path.write_text(json.dumps(document))

    def only_enabled(task):
        assert task == "node", "a disabled adapter was resolved"
        return controlled.adapter

    monkeypatch.setattr(runtime, "provider_for", only_enabled)
    monkeypatch.setattr(model_check, "check_model_configuration",
                        lambda: pytest.fail("used the legacy model defaults"))
    main(["models"])
    main(["voice-health"])
    output = capsys.readouterr().out
    assert "node: enabled" in output
    assert "moderation: disabled (intentional)" in output
    assert output.rstrip().endswith("voice-health: ok")
    assert controlled.requests == []


@pytest.mark.parametrize("remote_model", ["sk-untrusted-remote-value", "untrusted payload\nwith text"])
def test_untrusted_remote_model_value_is_not_persisted_or_logged(controlled, caplog, remote_model):
    controlled.model = remote_model
    with pytest.raises(dispatch.ModelControlStopped):
        _call(controlled)
    with persistence._connection() as conn:
        assert conn.execute("SELECT resolved_model FROM model_spend_reservations").fetchone() == (None,)
    assert remote_model not in caplog.text


def test_an_intentionally_disabled_route_uses_disabled_voice_outcome(http, tmp_path, monkeypatch):
    monkeypatch.setenv(policy.POLICY_ENV, str(_policy_file(tmp_path)))
    monkeypatch.delenv(guard.DISABLE_AI_ENV, raising=False)
    monkeypatch.setattr(moderation, "screen", lambda *_args, **_kwargs: SimpleNamespace(allowed=True))
    root = store.world_tree(382)
    status, body, _headers = http("/speak", body={"node_name": root.name, "message": "hello"})
    assert status == 200 and body["ai"] is False
    counts = observability.voice_outcome_summary()
    assert counts[guard._utc_day()]["speak"]["disabled"] == 1
    assert "unconfigured" not in counts[guard._utc_day()]["speak"]


def test_control_stop_is_a_failure_on_voice_and_intention_surfaces(http, controlled, monkeypatch):
    monkeypatch.setattr(moderation, "screen", lambda *_args, **_kwargs: SimpleNamespace(allowed=True))

    def stopped(*_args, **_kwargs):
        raise dispatch.ModelControlStopped()

    import consciousness
    from consciousness import interventions
    monkeypatch.setattr(consciousness, "speak", stopped)
    monkeypatch.setattr(consciousness, "voice_agent", stopped)
    monkeypatch.setattr(interventions, "propose", stopped)
    root = store.world_tree(382)
    for path, body in (("/speak", {"node_name": root.name, "message": "hello"}),
                       ("/agent/voice", {"agent_name": "Tessera", "node_name": root.name,
                                         "message": "hello"})):
        status, result, _headers = http(path, body=body)
        assert status == 200 and result["ai"] is False
    _, quiet = intervention_api._propose("settle", controlled.key, root.name, root, {})
    assert quiet["ai"] is False
    counts = observability.voice_outcome_summary()[guard._utc_day()]
    for surface in observability.VOICE_SURFACES:
        assert counts[surface]["control_stop"] == 1
        assert "budget" not in counts[surface]
