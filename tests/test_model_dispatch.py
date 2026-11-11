"""Controlled dispatch uses captured requests and one durable reservation.

All transports are authored fakes. No provider host is contacted.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
import json
from types import SimpleNamespace
import threading

import pytest

import persistence
from consciousness import model_dispatch, model_policy, runtime
from consciousness.anthropic_provider import AnthropicProvider
from consciousness.openai_compat_provider import (
    API_KEY_ENV, BASE_URL_ENV, MAX_OUTPUT_PARAM_ENV, REASONING_EFFORT_ENV,
    SEND_STORE_FALSE_ENV, STRUCTURED_OUTPUTS_ENV, TIMEOUT_ENV,
    OpenAICompatibleProvider, ProviderHTTPError,
)
from consciousness.runtime import SystemBlock
from persistence import model_spend


_KEY = "nw_" + "a" * 32
_SECRET = "sk-dispatch-private-key"
_PLAYER = "private player words"
_ENDPOINT = "https://approved.example/v1/chat/completions"
_OPTIONS = {
    "max_tokens_param": "max_completion_tokens", "structured_outputs": True,
    "send_store_false": True, "reasoning_effort": "none",
}


def _reply(model="approved-model"):
    return 200, (), json.dumps({
        "model": model,
        "choices": [{"finish_reason": "stop", "message": {"content": "A quiet bell."}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12,
                  "prompt_tokens_details": {"cached_tokens": 0}},
    }).encode()


def _generate(adapter, *, messages=None, schema=None):
    return adapter.generate(
        model="approved-model", system=(SystemBlock("private bible"),),
        messages=messages if messages is not None else [{"role": "user", "content": _PLAYER}],
        max_tokens=32, json_schema=schema,
    )


@pytest.fixture
def controlled(monkeypatch):
    model_dispatch.reset_for_tests()
    monkeypatch.setenv(BASE_URL_ENV, "https://approved.example/v1")
    monkeypatch.setenv(API_KEY_ENV, _SECRET)
    monkeypatch.delenv(MAX_OUTPUT_PARAM_ENV, raising=False)
    monkeypatch.setenv(STRUCTURED_OUTPUTS_ENV, "1")
    monkeypatch.setenv(SEND_STORE_FALSE_ENV, "1")
    monkeypatch.setenv(REASONING_EFFORT_ENV, "none")
    monkeypatch.setenv(TIMEOUT_ENV, "12")
    policy = SimpleNamespace(global_limit_microusd=1000, participant_limit_microusd=500,
                             snapshot_json='{"policy":"synthetic"}', retention_days=1)
    route = SimpleNamespace(task="node", adapter="openai_compatible", endpoint=_ENDPOINT,
                            model="approved-model", resolved_models=("approved-model",))
    reservations, settlements, requests = [], [], []
    monkeypatch.setattr(model_policy, "active", lambda: True)
    monkeypatch.setattr(model_policy, "current", lambda: policy)

    def route_for(task, model, max_output_tokens):
        if task not in runtime.TASKS or model != "approved-model" or max_output_tokens > 32:
            raise model_policy.ModelPolicyError()
        return SimpleNamespace(**{**vars(route), "task": task})

    def validate_prepared(route, **values):
        if (values["adapter"] != route.adapter or values["endpoint"] != _ENDPOINT
                or values["model"] != route.model or values["max_output_tokens"] > 32
                or values["timeout_seconds"] > 12 or values["options"] != _OPTIONS):
            raise model_policy.ModelPolicyError()

    monkeypatch.setattr(model_policy, "route_for", route_for)
    monkeypatch.setattr(model_policy, "validate_prepared", validate_prepared)
    monkeypatch.setattr(model_policy, "reserve_microusd", lambda route, max_tokens: 100)
    monkeypatch.setattr(model_policy, "settlement", lambda route, result, max_tokens:
                        (12, result.resolved_model != "approved-model", None))

    def reserve(**values):
        reservations.append(values)
        return str(len(reservations))

    def settle(reservation_id, **values):
        settlements.append((reservation_id, values))

    def transport(request):
        requests.append(request)
        return _reply()

    monkeypatch.setattr(model_spend, "reserve", reserve)
    monkeypatch.setattr(model_spend, "settle", settle)
    yield SimpleNamespace(adapter=OpenAICompatibleProvider(transport=transport),
                          reservations=reservations, settlements=settlements,
                          requests=requests, policy=policy)
    model_dispatch.reset_for_tests()


def test_direct_compatible_call_cannot_borrow_authorization(controlled):
    with pytest.raises(model_dispatch.ModelPolicyDenied):
        _generate(controlled.adapter)
    assert controlled.requests == controlled.reservations == []


def test_direct_anthropic_refuses_before_constructing_a_client(controlled, monkeypatch):
    adapter = AnthropicProvider()
    monkeypatch.setattr(adapter, "_get_client", lambda: pytest.fail("constructed SDK client"))
    with pytest.raises(model_dispatch.ModelPolicyDenied):
        _generate(adapter)
    with model_dispatch.call_scope(task="node", user_key=_KEY):
        with pytest.raises(model_dispatch.ModelPolicyDenied):
            _generate(adapter)
    assert controlled.reservations == []


@pytest.mark.parametrize("task", runtime.TASKS)
def test_all_task_routes_use_one_reservation_and_settlement(controlled, task):
    model_dispatch.validate_runtime_call(controlled.adapter, task, "approved-model", _KEY, 32)
    with model_dispatch.call_scope(task=task, user_key=_KEY):
        assert _generate(controlled.adapter).text == "A quiet bell."
    assert len(controlled.requests) == len(controlled.reservations) == len(controlled.settlements) == 1
    assert controlled.reservations[0]["task"] == task
    assert controlled.reservations[0]["user_key"] == _KEY
    assert controlled.reservations[0]["reserved_microusd"] == 100
    persisted = {k: v for k, v in controlled.reservations[0].items() if k != "user_key"}
    assert _SECRET not in repr(persisted) and _PLAYER not in repr(persisted)


@pytest.mark.parametrize("user_key", [None, ""])
def test_no_keyless_live_lane(controlled, user_key):
    with pytest.raises(model_dispatch.ModelPolicyDenied):
        model_dispatch.validate_runtime_call(controlled.adapter, "node", "approved-model", user_key, 32)
    with model_dispatch.call_scope(task="node", user_key=user_key):
        with pytest.raises(model_dispatch.ModelPolicyDenied):
            _generate(controlled.adapter)
    assert controlled.requests == controlled.reservations == []


def test_wrappers_subclasses_and_custom_adapters_refuse(controlled):
    class Subclass(OpenAICompatibleProvider):
        pass

    for adapter in (Subclass(), AnthropicProvider(),
                    SimpleNamespace(name="openai_compatible", provider=controlled.adapter)):
        with pytest.raises(model_dispatch.ModelPolicyDenied):
            model_dispatch.validate_runtime_call(adapter, "node", "approved-model", _KEY, 32)
    assert controlled.requests == controlled.reservations == []


def test_runtime_refusal_happens_before_call_caps(controlled, monkeypatch):
    monkeypatch.setattr(runtime, "provider_for", lambda task: AnthropicProvider())
    monkeypatch.setattr(runtime, "reserve_model_action", lambda key: pytest.fail("charged call cap"))
    with pytest.raises(model_dispatch.ModelPolicyDenied):
        runtime.generate(endpoint="speak", task="node", model="approved-model", user_key=_KEY,
                         system=(SystemBlock("bible"),), messages=[], max_tokens=32)
    assert controlled.requests == controlled.reservations == []


def test_missing_policy_never_reaches_transport(controlled, monkeypatch):
    def missing():
        raise model_policy.ModelPolicyError()
    monkeypatch.setattr(model_policy, "current", missing)
    with pytest.raises(model_dispatch.ModelPolicyDenied):
        _generate(controlled.adapter)
    assert controlled.requests == controlled.reservations == []


def test_unapproved_endpoint_refuses_before_reserve(controlled, monkeypatch):
    monkeypatch.setenv(BASE_URL_ENV, "https://other.example/v1")
    with model_dispatch.call_scope(task="node", user_key=_KEY):
        with pytest.raises(model_dispatch.ModelPolicyDenied):
            _generate(controlled.adapter)
    assert controlled.requests == controlled.reservations == []


def test_authorized_snapshot_survives_environment_and_input_mutation(controlled, monkeypatch):
    messages = [{"role": "user", "content": _PLAYER}]
    schema = {"type": "object", "properties": {"tone": {"type": "string"}},
              "required": ["tone"], "additionalProperties": False}
    original_validate = model_policy.validate_prepared

    def mutate(route, **values):
        original_validate(route, **values)
        monkeypatch.setenv(BASE_URL_ENV, "https://other.example/v9")
        monkeypatch.setenv(API_KEY_ENV, "replacement-secret")
        monkeypatch.setenv(MAX_OUTPUT_PARAM_ENV, "max_tokens")
        monkeypatch.setenv(STRUCTURED_OUTPUTS_ENV, "0")
        monkeypatch.setenv(SEND_STORE_FALSE_ENV, "0")
        monkeypatch.setenv(REASONING_EFFORT_ENV, "high")
        monkeypatch.setenv(TIMEOUT_ENV, "999")
        messages[0]["content"] = "mutated player words"
        schema["properties"]["tone"]["type"] = "number"
        controlled.adapter._transport = lambda request: pytest.fail("transport changed after approval")

    monkeypatch.setattr(model_policy, "validate_prepared", mutate)
    with model_dispatch.call_scope(task="node", user_key=_KEY):
        _generate(controlled.adapter, messages=messages, schema=schema)
    request, = controlled.requests
    wire = json.loads(request.body)
    assert request.url == _ENDPOINT and request.timeout == 12
    assert dict(request.headers)["Authorization"] == f"Bearer {_SECRET}"
    assert wire["messages"][-1]["content"] == _PLAYER
    assert wire["max_completion_tokens"] == 32 and "max_tokens" not in wire
    assert wire["store"] is False and wire["reasoning_effort"] == "none"
    assert wire["response_format"]["json_schema"]["schema"]["properties"]["tone"]["type"] == "string"


@pytest.mark.parametrize("status", [302, 429, 503])
def test_failure_is_one_attempt_and_keeps_full_reservation(controlled, status):
    def fail(request):
        controlled.requests.append(request)
        raise ProviderHTTPError(status)
    controlled.adapter._transport = fail
    with model_dispatch.call_scope(task="node", user_key=_KEY):
        with pytest.raises(ProviderHTTPError):
            _generate(controlled.adapter)
        with pytest.raises(model_dispatch.ModelPolicyDenied):
            _generate(controlled.adapter)
    assert len(controlled.requests) == len(controlled.reservations) == 1
    assert controlled.settlements == []


def test_scope_is_single_use_after_success(controlled):
    with model_dispatch.call_scope(task="node", user_key=_KEY):
        _generate(controlled.adapter)
        with pytest.raises(model_dispatch.ModelPolicyDenied):
            _generate(controlled.adapter)
    assert len(controlled.requests) == len(controlled.reservations) == len(controlled.settlements) == 1


def test_copied_scope_is_revoked_after_exit(controlled):
    with model_dispatch.call_scope(task="node", user_key=_KEY):
        saved = copy_context()
    with pytest.raises(model_dispatch.ModelPolicyDenied):
        saved.run(_generate, controlled.adapter)
    assert controlled.requests == controlled.reservations == []


def test_concurrent_copied_scopes_cannot_send_twice(controlled):
    entered, release = threading.Event(), threading.Event()

    def transport(request):
        controlled.requests.append(request)
        entered.set()
        assert release.wait(2)
        return _reply()

    controlled.adapter._transport = transport
    with model_dispatch.call_scope(task="node", user_key=_KEY):
        first, second = copy_context(), copy_context()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(context.run, _generate, controlled.adapter)
                       for context in (first, second)]
            try:
                assert entered.wait(2)
            finally:
                release.set()
            results = []
            for future in futures:
                try:
                    results.append(future.result())
                except model_dispatch.ModelPolicyDenied:
                    results.append(None)
    assert sum(result is not None for result in results) == 1
    assert len(controlled.requests) == len(controlled.reservations) == len(controlled.settlements) == 1


def test_nested_keyless_scope_does_not_inherit_actor(controlled):
    with model_dispatch.call_scope(task="node", user_key=_KEY):
        with model_dispatch.call_scope(task="moderation", user_key=None):
            with pytest.raises(model_dispatch.ModelPolicyDenied):
                _generate(controlled.adapter)
        _generate(controlled.adapter)
    with pytest.raises(model_dispatch.ModelPolicyDenied):
        _generate(controlled.adapter)
    assert len(controlled.requests) == 1


def test_reserve_refusal_cannot_retry_inside_same_scope(controlled, monkeypatch):
    def deny(**values):
        controlled.reservations.append(values)
        raise model_spend.ModelSpendDenied()
    monkeypatch.setattr(model_spend, "reserve", deny)
    with model_dispatch.call_scope(task="node", user_key=_KEY):
        for _ in range(2):
            with pytest.raises(model_dispatch.ModelPolicyDenied):
                _generate(controlled.adapter)
    assert len(controlled.reservations) == 1 and controlled.requests == []


def test_unexpected_model_is_settled_and_refused(controlled):
    controlled.adapter._transport = lambda request: _reply("unexpected-model")
    with model_dispatch.call_scope(task="node", user_key=_KEY):
        with pytest.raises(model_dispatch.ModelPolicyDenied):
            _generate(controlled.adapter)
    assert controlled.settlements[0][1]["anomaly"] is True
    assert controlled.settlements[0][1]["resolved_model"] is None


def test_settlement_failure_stops_later_calls_without_another_reserve(controlled, monkeypatch):
    def unavailable(*args, **kwargs):
        raise RuntimeError("untrusted storage exception details")
    monkeypatch.setattr(model_spend, "settle", unavailable)
    with model_dispatch.call_scope(task="node", user_key=_KEY):
        with pytest.raises(model_dispatch.ModelPolicyDenied) as caught:
            _generate(controlled.adapter)
    assert "untrusted" not in str(caught.value)
    with pytest.raises(model_dispatch.ModelPolicyDenied):
        model_dispatch.validate_runtime_call(controlled.adapter, "node", "approved-model", _KEY, 32)
    with pytest.raises(model_dispatch.ModelPolicyDenied):
        with model_dispatch.call_scope(task="node", user_key=_KEY):
            _generate(controlled.adapter)
    assert len(controlled.requests) == len(controlled.reservations) == 1


def test_fault_during_preparation_blocks_existing_scope_before_reserve(controlled, monkeypatch):
    original = model_policy.validate_prepared

    def concurrent_fault(route, **values):
        original(route, **values)
        model_dispatch._settlement_fault.set()

    monkeypatch.setattr(model_policy, "validate_prepared", concurrent_fault)
    with model_dispatch.call_scope(task="node", user_key=_KEY):
        with pytest.raises(model_dispatch.ModelPolicyDenied):
            _generate(controlled.adapter)
    assert controlled.requests == controlled.reservations == []


def test_fault_during_reservation_blocks_network_and_keeps_reserve(controlled, monkeypatch):
    original = model_spend.reserve

    def concurrent_fault(**values):
        reservation_id = original(**values)
        model_dispatch._settlement_fault.set()
        return reservation_id

    monkeypatch.setattr(model_spend, "reserve", concurrent_fault)
    with model_dispatch.call_scope(task="node", user_key=_KEY):
        with pytest.raises(model_dispatch.ModelPolicyDenied):
            _generate(controlled.adapter)
    assert controlled.requests == [] and len(controlled.reservations) == 1
    assert controlled.settlements == []


def test_inactive_controls_preserve_direct_local_adapter_calls(controlled, monkeypatch):
    monkeypatch.setattr(model_policy, "active", lambda: False)
    assert _generate(controlled.adapter).text == "A quiet bell."
    assert len(controlled.requests) == 1
    assert controlled.reservations == controlled.settlements == []


@pytest.fixture
def real_controlled(tmp_path, monkeypatch, accounts):
    """A fictitious declaration exercises the actual loader and durable ledger."""
    monkeypatch.setenv(runtime.PROVIDER_ENV, "openai_compatible")
    for name in (runtime.NODE_MODEL_ENV, runtime.INHABITANT_MODEL_ENV,
                 runtime.INTENT_MODEL_ENV, runtime.MODERATION_MODEL_ENV):
        monkeypatch.setenv(name, "approved-model")
    monkeypatch.setenv(BASE_URL_ENV, "https://approved.example/v1")
    monkeypatch.setenv(API_KEY_ENV, _SECRET)
    monkeypatch.delenv(MAX_OUTPUT_PARAM_ENV, raising=False)
    monkeypatch.setenv(STRUCTURED_OUTPUTS_ENV, "1")
    monkeypatch.setenv(SEND_STORE_FALSE_ENV, "1")
    monkeypatch.setenv(REASONING_EFFORT_ENV, "none")
    monkeypatch.setenv(TIMEOUT_ENV, "12")
    monkeypatch.delenv("NESTED_WORLDS_DISABLE_AI", raising=False)
    declaration = {
        "schema_version": 1, "policy_id": "synthetic-dispatch-test", "currency": "USD", "reset": "UTC",
        "limits": {"global_daily_usd": "1", "participant_daily_usd": "0.5"},
        "ledger_retention_days": 2,
        "routes": {task: {
            "enabled": True, "adapter": "openai_compatible", "endpoint": _ENDPOINT,
            "model": "approved-model", "resolved_models": ["approved-model"],
            "max_input_tokens": 1000, "input_bound_kind": "provider_context_maximum",
            "input_bound_evidence": "Authored synthetic fixture bound.",
            "max_output_tokens": 500, "timeout_seconds": "12", "options": _OPTIONS,
            "prices": {"input_per_million_usd": "1", "output_per_million_usd": "2",
                       "cache_read_per_million_usd": "0.1", "cache_write_per_million_usd": "2"},
            "data_use_note": "No remote model; authored fake transport only.",
            "approval_reference": "Synthetic test declaration, not operator approval.",
        } for task in runtime.TASKS},
    }
    declaration["routes"]["images"] = {"enabled": False}
    path = tmp_path / "model-policy.json"
    path.write_text(json.dumps(declaration))
    monkeypatch.setenv(model_policy.POLICY_ENV, str(path))
    monkeypatch.setenv(model_policy.REQUIRED_ENV, "1")
    requests = []

    def transport(request):
        requests.append(request)
        return _reply()

    adapter = OpenAICompatibleProvider(transport=transport)
    monkeypatch.setattr(runtime, "provider_for", lambda task: adapter)
    model_policy.reset_for_tests()
    model_dispatch.reset_for_tests()
    yield SimpleNamespace(adapter=adapter, requests=requests, key=accounts[0])
    model_policy.reset_for_tests()
    model_dispatch.reset_for_tests()


def _runtime_call(controlled, task="node"):
    return runtime.generate(
        endpoint="synthetic", task=task, model="approved-model", user_key=controlled.key,
        system=(SystemBlock("private bible"),),
        messages=[{"role": "user", "content": _PLAYER}], max_tokens=32,
    )


def test_real_policy_all_runtime_tasks_account_to_one_stable_participant(real_controlled):
    for task in runtime.TASKS:
        assert _runtime_call(real_controlled, task).text == "A quiet bell."
    with persistence._connection() as conn:
        rows = conn.execute("""SELECT participant_id,task,status,accounted_microusd,policy_json
            FROM model_spend_reservations ORDER BY task""").fetchall()
    assert len(real_controlled.requests) == len(rows) == 4
    assert len({row[0] for row in rows}) == 1
    assert {row[1] for row in rows} == set(runtime.TASKS)
    assert all(row[2] == "settled" and row[3] == 24 for row in rows)
    assert all(_SECRET not in row[4] and _PLAYER not in row[4] for row in rows)


def test_real_policy_endpoint_drift_has_no_ledger_or_transport(real_controlled, monkeypatch):
    model_policy.current()
    monkeypatch.setenv(BASE_URL_ENV, "https://unapproved.example/v1")
    with pytest.raises(model_dispatch.ModelPolicyDenied):
        _runtime_call(real_controlled)
    with persistence._connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM model_spend_reservations").fetchone()[0] == 0
    assert real_controlled.requests == []


def test_real_provider_failure_retains_reservation(real_controlled):
    def failure(request):
        real_controlled.requests.append(request)
        raise ProviderHTTPError(503)
    real_controlled.adapter._transport = failure
    with pytest.raises(ProviderHTTPError):
        _runtime_call(real_controlled)
    with persistence._connection() as conn:
        rows = conn.execute("SELECT status,reserved_microusd,accounted_microusd FROM model_spend_reservations").fetchall()
    assert len(rows) == len(real_controlled.requests) == 1
    assert rows[0][0] == "reserved" and rows[0][1] == rows[0][2] == 2064


def test_real_missing_output_usage_keeps_full_reservation(real_controlled):
    def incomplete_usage(request):
        real_controlled.requests.append(request)
        status, headers, raw = _reply()
        body = json.loads(raw)
        del body["usage"]["total_tokens"]
        return status, headers, json.dumps(body).encode()
    real_controlled.adapter._transport = incomplete_usage
    assert _runtime_call(real_controlled).text == "A quiet bell."
    with persistence._connection() as conn:
        rows = conn.execute("SELECT status,reserved_microusd,accounted_microusd FROM model_spend_reservations").fetchall()
    assert rows == [("uncertain", 2064, 2064)]


def test_real_contradictory_output_usage_keeps_full_reservation(real_controlled):
    def contradictory_usage(request):
        real_controlled.requests.append(request)
        status, headers, raw = _reply()
        body = json.loads(raw)
        body["usage"] = {
            "prompt_tokens": 10, "completion_tokens": 32, "total_tokens": 10,
            "prompt_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
        }
        return status, headers, json.dumps(body).encode()
    real_controlled.adapter._transport = contradictory_usage
    assert _runtime_call(real_controlled).text == "A quiet bell."
    with persistence._connection() as conn:
        row, = conn.execute("""SELECT status,reserved_microusd,accounted_microusd,usage_json
            FROM model_spend_reservations""").fetchall()
    assert row[:3] == ("uncertain", 2064, 2064)
    assert json.loads(row[3])["output_tokens"] is None


def test_real_unexpected_model_persists_latch_and_blocks_next_send(real_controlled):
    def wrong_model(request):
        real_controlled.requests.append(request)
        return _reply("unexpected-model")
    real_controlled.adapter._transport = wrong_model
    for _ in range(2):
        with pytest.raises(model_dispatch.ModelPolicyDenied):
            _runtime_call(real_controlled)
    with persistence._connection() as conn:
        assert conn.execute("SELECT status FROM model_spend_reservations").fetchall() == [("anomaly",)]
        assert conn.execute("SELECT reason FROM model_spend_latch").fetchall() == [("billing_anomaly",)]
    assert len(real_controlled.requests) == 1
