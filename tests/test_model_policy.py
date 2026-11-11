"""Offline policy adversaries; every destination, price and limit is synthetic.

These fixtures do not approve a provider or exercise a remote model. The policy
must bind exact routes before dispatch and keep uncertain usage conservative.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
import json
import socket
import urllib.request

import pytest

from consciousness import model_policy as policy, runtime
from consciousness import openai_compat_provider as compat


_ENDPOINT = "https://model-policy-fixture.invalid/v1/chat/completions"
_OPTIONS = {"max_tokens_param": "max_completion_tokens", "structured_outputs": True,
            "send_store_false": True, "reasoning_effort": "none"}
_PRICES = {"input_per_million_usd": "0.2", "output_per_million_usd": "0.3",
           "cache_read_per_million_usd": "0.1", "cache_write_per_million_usd": "0.4"}
_MODEL_ENVS = (runtime.NODE_MODEL_ENV, runtime.INHABITANT_MODEL_ENV,
               runtime.INTENT_MODEL_ENV, runtime.MODERATION_MODEL_ENV)


def _forbidden(*_args, **_kwargs):
    pytest.fail("offline policy validation attempted network I/O")


@pytest.fixture(autouse=True)
def _isolated_policy(monkeypatch):
    network = {"connect": socket.create_connection, "resolve": socket.getaddrinfo,
               "open": urllib.request.urlopen}
    policy.reset_for_tests()
    runtime.reset_provider_selection()
    for name in (policy.POLICY_ENV, policy.REQUIRED_ENV, "NESTED_WORLDS_TEST_WORLD",
                 "NESTED_WORLDS_DISABLE_AI", "NESTED_WORLDS_DISABLE_IMAGES",
                 runtime.PROVIDER_ENV, runtime.SHARED_MODEL_ENV,
                 *runtime.TASK_PROVIDER_ENVS, *_MODEL_ENVS,
                 compat.BASE_URL_ENV, compat.API_KEY_ENV, compat.MAX_OUTPUT_PARAM_ENV,
                 compat.STRUCTURED_OUTPUTS_ENV, compat.SEND_STORE_FALSE_ENV,
                 compat.REASONING_EFFORT_ENV, compat.TIMEOUT_ENV,
                 "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(socket, "create_connection", _forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", _forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", _forbidden)
    monkeypatch.setattr(compat.OpenAICompatibleProvider, "generate", _forbidden)
    yield network
    policy.reset_for_tests()
    runtime.reset_provider_selection()


def _document(*tasks):
    routes = {task: {"enabled": False} for task in (*runtime.TASKS, "images")}
    for task in tasks:
        routes[task] = {
            "enabled": True, "adapter": "openai_compatible", "endpoint": _ENDPOINT,
            "model": f"fixture-{task}", "resolved_models": [f"fixture-{task}-v1"],
            "max_input_tokens": 10, "max_output_tokens": 5,
            "input_bound_kind": "provider_context_maximum",
            "input_bound_evidence": "Synthetic bound for an offline test only.",
            "timeout_seconds": "12.5", "options": deepcopy(_OPTIONS),
            "prices": deepcopy(_PRICES), "data_use_note": "Synthetic fixture terms.",
            "approval_reference": "Test fixture, not an approval.",
        }
    result = {"schema_version": 1, "policy_id": "offline-fixture", "currency": "USD",
              "reset": "UTC", "routes": routes}
    if tasks:
        result.update(limits={"global_daily_usd": "0.000010",
                              "participant_daily_usd": "0.000005"},
                      ledger_retention_days=2)
    return result


def _write(tmp_path, document, name="policy.json"):
    path = tmp_path / name
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def _set(document, path, value):
    target = document
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value


def _configuration(monkeypatch, tasks=runtime.TASKS):
    monkeypatch.setenv(runtime.PROVIDER_ENV, "anthropic")
    monkeypatch.setenv(compat.BASE_URL_ENV, _ENDPOINT.removesuffix("/chat/completions"))
    monkeypatch.setenv(compat.STRUCTURED_OUTPUTS_ENV, "1")
    monkeypatch.setenv(compat.SEND_STORE_FALSE_ENV, "1")
    monkeypatch.setenv(compat.REASONING_EFFORT_ENV, "none")
    monkeypatch.setenv(compat.TIMEOUT_ENV, "12")
    for task in tasks:
        index = runtime.TASKS.index(task)
        monkeypatch.setenv(runtime.TASK_PROVIDER_ENVS[index], "openai_compatible")
        monkeypatch.setenv(_MODEL_ENVS[index], f"fixture-{task}")


def _activate(tmp_path, monkeypatch, *tasks):
    _configuration(monkeypatch, tasks)
    monkeypatch.setenv(policy.POLICY_ENV, str(_write(tmp_path, _document(*tasks))))
    return policy.initialize()


def _completion(usage=None, *, model="fixture-node-v1", provider="openai_compatible"):
    return runtime.Completion("fixture response", True, usage=usage,
                              resolved_model=model, provider=provider)


def _off_with_unusable_provider(tmp_path, monkeypatch):
    monkeypatch.setenv(policy.POLICY_ENV, str(_write(tmp_path, _document())))
    monkeypatch.setenv(runtime.PROVIDER_ENV, "unregistered_fixture")
    for provider_env, model_env in zip(runtime.TASK_PROVIDER_ENVS, _MODEL_ENVS):
        monkeypatch.setenv(provider_env, "unregistered_fixture")
        monkeypatch.setenv(model_env, " ")
    monkeypatch.setattr(runtime, "provider_for", _forbidden)
    monkeypatch.setattr(runtime, "get_provider", _forbidden)
    return policy.initialize()


def test_minimal_all_off_needs_no_destination_price_limit_or_retention(tmp_path, monkeypatch):
    path = _write(tmp_path, _document())
    checked = policy.check_file(path)
    assert checked.enabled_routes == () and dict(checked.routes) == {}
    assert checked.global_limit_microusd == checked.participant_limit_microusd == 0
    assert checked.retention_days == 0
    assert not policy.active()
    assert json.loads(checked.snapshot_json) == _document()
    monkeypatch.setenv(policy.POLICY_ENV, str(path))
    monkeypatch.setenv(runtime.PROVIDER_ENV, "not-a-provider")
    assert policy.initialize().enabled_routes == ()


@pytest.mark.parametrize("path,value", [
    (("extra",), "unreviewed"),
    (("schema_version",), True), (("schema_version",), 1.0),
    (("currency",), "EUR"), (("reset",), "local"),
    (("routes", "extra"), {"enabled": False}),
    (("routes", "images"), {"enabled": False, "model": "hidden"}),
    (("routes", "node", "enabled"), 1),
    (("routes", "node", "adapter"), "anthropic"),
    (("routes", "node", "unreviewed"), "value"),
    (("routes", "node", "options", "extra"), True),
    (("routes", "node", "options", "structured_outputs"), 1),
    (("routes", "node", "options", "send_store_false"), False),
    (("routes", "node", "options", "max_tokens_param"), "tokens"),
    (("routes", "node", "options", "reasoning_effort"), "maximum"),
    (("routes", "node", "prices", "extra"), "0"),
    (("routes", "node", "model"), "model with spaces"),
    (("routes", "node", "resolved_models"), []),
    (("routes", "node", "resolved_models"), ["same", "same"]),
    (("routes", "node", "resolved_models"), "fixture-node-v1"),
    (("routes", "node", "approval_reference"), ""),
    (("routes", "node", "input_bound_evidence"), " padded "),
    (("routes", "node", "input_bound_kind"), "estimated_average"),
    (("routes", "node", "data_use_note"), "line\nbreak"),
    (("limits", "extra"), "0"),
])
def test_strict_schema_rejects_unknown_or_mistyped_fields(tmp_path, path, value):
    document = _document("node")
    _set(document, path, value)
    with pytest.raises(policy.ModelPolicyError):
        policy.check_file(_write(tmp_path, document))


@pytest.mark.parametrize("path", [
    ("routes", "images"), ("routes", "node", "prices", "cache_read_per_million_usd"),
    ("routes", "node", "approval_reference"), ("limits",), ("ledger_retention_days",),
    ("routes", "node", "input_bound_kind"),
])
def test_strict_schema_rejects_missing_fields(tmp_path, path):
    document = _document("node")
    target = document
    for key in path[:-1]:
        target = target[key]
    del target[path[-1]]
    with pytest.raises(policy.ModelPolicyError):
        policy.check_file(_write(tmp_path, document))


@pytest.mark.parametrize("needle,replacement", [
    ('"policy_id": "offline-fixture"', '"policy_id":"first","policy_id":"second"'),
    ('"images": {"enabled": false}', '"images":{"enabled":false},"images":{"enabled":false}'),
    ('"max_input_tokens": 10', '"max_input_tokens":10,"max_input_tokens":20'),
    ('"send_store_false": true', '"send_store_false":true,"send_store_false":false'),
    ('"output_per_million_usd": "0.3"', '"output_per_million_usd":"0.3","output_per_million_usd":"0"'),
])
def test_duplicate_json_fields_are_not_last_value_wins(tmp_path, needle, replacement):
    raw = json.dumps(_document("node"))
    assert raw.count(needle) == 1
    path = tmp_path / "duplicate.json"
    path.write_text(raw.replace(needle, replacement), encoding="utf-8")
    with pytest.raises(policy.ModelPolicyError):
        policy.check_file(path)


@pytest.mark.parametrize("raw", ["NaN", "Infinity", "-Infinity", "null", "[]", "{}", "{", '"text"'])
def test_invalid_json_and_nonfinite_constants_fail_closed(tmp_path, raw):
    path = tmp_path / "invalid.json"
    path.write_text(raw, encoding="utf-8")
    with pytest.raises(policy.ModelPolicyError):
        policy.check_file(path)


@pytest.mark.parametrize("field,value", [
    ("max_input_tokens", True), ("max_input_tokens", 0), ("max_input_tokens", -1),
    ("max_input_tokens", 2**63), ("max_input_tokens", 1.0), ("max_input_tokens", "10"),
    ("max_output_tokens", False), ("max_output_tokens", 0), ("max_output_tokens", 2**63),
    ("timeout_seconds", "0"), ("timeout_seconds", "3600.1"),
    ("timeout_seconds", "NaN"), ("timeout_seconds", "1e1"), ("timeout_seconds", 12.5),
])
def test_route_bounds_require_bounded_positive_numbers(tmp_path, field, value):
    document = _document("node")
    document["routes"]["node"][field] = value
    with pytest.raises(policy.ModelPolicyError):
        policy.check_file(_write(tmp_path, document))


@pytest.mark.parametrize("value", [True, 1.5, "NaN", "Infinity", "-1", "+1", "01", "1e2",
                                   " 1", "1 ", "0.0000000000001", "10000000000000"])
def test_prices_are_explicit_finite_decimal_strings(tmp_path, value):
    document = _document("node")
    document["routes"]["node"]["prices"]["input_per_million_usd"] = value
    with pytest.raises(policy.ModelPolicyError):
        policy.check_file(_write(tmp_path, document))


@pytest.mark.parametrize("field,value", [
    ("global_daily_usd", True), ("global_daily_usd", "0.0000001"),
    ("global_daily_usd", "9223372036854.775808"),
    ("participant_daily_usd", "-1"),
])
def test_limits_are_exact_integer_microdollars(tmp_path, field, value):
    document = _document("node")
    document["limits"][field] = value
    with pytest.raises(policy.ModelPolicyError):
        policy.check_file(_write(tmp_path, document))


def test_zero_prices_and_zero_limits_are_explicit_declarations_not_missing_values(tmp_path):
    document = _document("node")
    document["routes"]["node"]["prices"] = {key: "0" for key in _PRICES}
    document["limits"] = {key: "0" for key in document["limits"]}
    checked = policy.check_file(_write(tmp_path, document))
    assert checked.global_limit_microusd == checked.participant_limit_microusd == 0
    assert policy.reserve_microusd(checked.routes["node"], 5) == 0


@pytest.mark.parametrize("value", [True, 0, 1, 2.0, 36501, 2**63])
def test_ledger_retention_is_bounded_and_covers_the_spending_day(tmp_path, value):
    document = _document("node")
    document["ledger_retention_days"] = value
    with pytest.raises(policy.ModelPolicyError):
        policy.check_file(_write(tmp_path, document))


@pytest.mark.parametrize("endpoint", [
    "http://localhost/v1/chat/completions", "https:///v1/chat/completions",
    "https://user:secret@example.invalid/v1/chat/completions",
    _ENDPOINT + "?key=private", _ENDPOINT + "?", _ENDPOINT + "#fragment", _ENDPOINT + "#",
    "https://example.invalid:0/v1/chat/completions",
    "https://example.invalid:65536/v1/chat/completions",
    "https://example.invalid/../v1/chat/completions",
    "https://example.invalid/./v1/chat/completions",
    "https://example.invalid/%2e%2e/v1/chat/completions",
    "https://example.invalid\\other/v1/chat/completions",
    "https://example.invalid/v1/chat/completions\n",
    "https://example\x7f.invalid/v1/chat/completions",
    "https://examplé.invalid/v1/chat/completions", "https://example.invalid/v1/responses",
])
def test_destination_is_exact_https_without_credentials_or_redirecting_parts(tmp_path, endpoint):
    document = _document("node")
    document["routes"]["node"]["endpoint"] = endpoint
    with pytest.raises(policy.ModelPolicyError) as caught:
        policy.check_file(_write(tmp_path, document))
    assert "secret" not in str(caught.value) and "example.invalid" not in str(caught.value)


def test_images_cannot_be_enabled_by_a_text_route_declaration(tmp_path):
    document = _document("node")
    document["routes"]["images"] = deepcopy(document["routes"]["node"])
    with pytest.raises(policy.ModelPolicyError):
        policy.check_file(_write(tmp_path, document))


@pytest.mark.parametrize("task", [runtime.INTENT_TASK, runtime.MODERATION_TASK])
def test_schema_dependent_tasks_require_structured_outputs(tmp_path, task):
    document = _document(task)
    document["routes"][task]["options"]["structured_outputs"] = False
    with pytest.raises(policy.ModelPolicyError):
        policy.check_file(_write(tmp_path, document))


def test_unreadable_oversized_and_invalid_utf8_files_have_safe_errors(tmp_path):
    invalid = tmp_path / "bytes.json"
    invalid.write_bytes(b"\xff")
    huge = tmp_path / "huge.json"
    huge.write_bytes(b" " * 131073)
    for path in (tmp_path / "missing-private-path.json", invalid, huge):
        with pytest.raises(policy.ModelPolicyError) as caught:
            policy.check_file(path)
        assert str(caught.value) == "Model policy configuration is invalid or missing."


def test_policy_snapshots_and_nested_route_values_are_immutable(tmp_path, monkeypatch):
    document = _document("node")
    frozen = _activate(tmp_path, monkeypatch, "node")
    route = frozen.routes["node"]
    with pytest.raises(FrozenInstanceError):
        frozen.policy_id = "replacement"
    for mapping, key, value in ((frozen.routes, "node", None),
                                (route.options, "send_store_false", False),
                                (route.prices, "input_per_million_usd", Decimal("0"))):
        with pytest.raises(TypeError):
            mapping[key] = value
    assert json.loads(frozen.snapshot_json) == document
    assert route.resolved_models == ("fixture-node-v1",)


def test_appearing_policy_keys_and_removed_environment_cannot_enable_frozen_off_routes(tmp_path, monkeypatch):
    monkeypatch.setenv("NESTED_WORLDS_TEST_WORLD", "temporary-fixture")
    monkeypatch.setenv("NESTED_WORLDS_DISABLE_AI", "1")
    monkeypatch.setenv("NESTED_WORLDS_DISABLE_IMAGES", "1")
    off = policy.initialize()
    assert off.enabled_routes == ()
    _configuration(monkeypatch)
    monkeypatch.setenv(policy.POLICY_ENV, str(_write(tmp_path, _document(*runtime.TASKS))))
    monkeypatch.setenv(compat.API_KEY_ENV, "fixture-key-appeared-later")
    for name in (policy.REQUIRED_ENV, "NESTED_WORLDS_TEST_WORLD",
                 "NESTED_WORLDS_DISABLE_AI", "NESTED_WORLDS_DISABLE_IMAGES"):
        monkeypatch.delenv(name, raising=False)
    assert policy.active() and policy.initialize() is off
    for task in (*runtime.TASKS, "images"):
        with pytest.raises(policy.ModelPolicyDenied):
            policy.route_for(task, f"fixture-{task}", 1)


def test_live_snapshot_does_not_reload_a_changed_file_or_environment(tmp_path, monkeypatch):
    original = _activate(tmp_path, monkeypatch, "node")
    path = _write(tmp_path, _document(), "replacement.json")
    monkeypatch.setenv(policy.POLICY_ENV, str(path))
    assert policy.current() is original
    monkeypatch.delenv(policy.POLICY_ENV)
    assert policy.active() and policy.current() is original
    monkeypatch.setenv("NESTED_WORLDS_DISABLE_AI", "1")
    with pytest.raises(policy.ModelPolicyDenied):
        policy.route_for("node", "fixture-node", 1)


@pytest.mark.parametrize("task", runtime.TASKS)
def test_disabled_tasks_refuse_before_provider_model_or_call_cap_lookup(tmp_path, monkeypatch, task):
    frozen = _off_with_unusable_provider(tmp_path, monkeypatch)
    monkeypatch.setattr(runtime, "reserve_model_action", _forbidden)
    for appeared_key in (False, True):
        if appeared_key:
            monkeypatch.setenv(compat.API_KEY_ENV, "fixture-key-appeared-later")
            monkeypatch.setenv("ANTHROPIC_API_KEY", "fixture-sdk-key-appeared-later")
            monkeypatch.setenv(compat.BASE_URL_ENV, _ENDPOINT.removesuffix("/chat/completions"))
        assert policy.current() is frozen
        with pytest.raises(policy.ModelPolicyDenied):
            runtime.model_for(task)
        assert runtime.configured(task) is False
        assert runtime.configured() is False
        with pytest.raises(policy.ModelPolicyDenied):
            runtime.generate(endpoint="offline-fixture", task=task, model=" ",
                             system=(), messages=[], max_tokens=1,
                             user_key="nw_" + "a" * 32)


def test_disabled_moderation_holds_as_budget_without_provider_or_classifier_lookup(
        tmp_path, monkeypatch, accounts, caplog):
    import consciousness
    from server import moderation

    _off_with_unusable_provider(tmp_path, monkeypatch)
    monkeypatch.delenv(moderation.DISABLE_MODERATION_ENV, raising=False)
    monkeypatch.setenv(moderation.EXTRA_WATCH_ENV, "fixturewatch")
    monkeypatch.setattr(consciousness, "classify_content", _forbidden)
    monkeypatch.setattr(runtime, "reserve_model_action", _forbidden)
    verdict = moderation.screen("fixturewatch", user_key=accounts[0], surface="speak")
    assert (verdict.allowed, verdict.tier, verdict.outcome) == (False, "budget", "budget")
    assert "model id unavailable" not in caplog.text


def test_all_off_speak_returns_authored_http_200_after_keys_appear(
        tmp_path, monkeypatch, http, _isolated_policy):
    import consciousness
    import persistence
    from multiverse import store
    from server import guard

    _off_with_unusable_provider(tmp_path, monkeypatch)
    monkeypatch.setattr(guard, "consume_anthropic", _forbidden)
    # Only this test restores the loopback HTTP fixture's networking. A
    # provider URL or non-loopback address still fails before any socket.
    def connect(address, *args, **kwargs):
        assert address[0] == "127.0.0.1"
        return _isolated_policy["connect"](address, *args, **kwargs)

    def resolve(host, *args, **kwargs):
        assert host == "127.0.0.1"
        return _isolated_policy["resolve"](host, *args, **kwargs)

    def local_open(request, *args, **kwargs):
        assert request.full_url.startswith("http://127.0.0.1:")
        return _isolated_policy["open"](request, *args, **kwargs)

    monkeypatch.setattr(socket, "create_connection", connect)
    monkeypatch.setattr(socket, "getaddrinfo", resolve)
    monkeypatch.setattr(urllib.request, "urlopen", local_open)
    node = store.world_tree(382)
    for appeared_key in (False, True):
        if appeared_key:
            monkeypatch.setenv(compat.API_KEY_ENV, "fixture-key-appeared-later")
            monkeypatch.setenv("ANTHROPIC_API_KEY", "fixture-sdk-key-appeared-later")
        status, result, _headers = http("/speak", body={"node_name": node.name, "message": "hello"})
        assert status == 200
        assert result == {"response": consciousness.fallback_voice(node), "ai": False}
    assert persistence.get_mutations(382) == []


@pytest.mark.parametrize("activation", [policy.REQUIRED_ENV, policy.POLICY_ENV, "NESTED_WORLDS_TEST_WORLD"])
def test_controlled_mode_without_policy_or_both_switches_fails_closed(monkeypatch, activation):
    monkeypatch.setenv(activation, "1" if activation != policy.POLICY_ENV else "")
    monkeypatch.setenv("NESTED_WORLDS_DISABLE_AI", "1")
    with pytest.raises(policy.ModelPolicyError):
        policy.initialize()


def test_all_task_overrides_match_explicit_routes_without_contacting_a_provider(tmp_path, monkeypatch):
    checked = _activate(tmp_path, monkeypatch, *runtime.TASKS)
    assert checked.enabled_routes == runtime.TASKS
    for task in runtime.TASKS:
        assert policy.route_for(task, f"fixture-{task}", 5) is checked.routes[task]


@pytest.mark.parametrize("task", runtime.TASKS)
@pytest.mark.parametrize("setting", ["provider", "unknown_provider", "model", "blank_model"])
def test_every_task_override_must_match_its_declaration(tmp_path, monkeypatch, task, setting):
    _configuration(monkeypatch)
    index = runtime.TASKS.index(task)
    provider_setting = setting in {"provider", "unknown_provider"}
    value = ("anthropic" if setting == "provider" else "unregistered_fixture"
             if setting == "unknown_provider" else " " if setting == "blank_model" else "other-model")
    monkeypatch.setenv(runtime.TASK_PROVIDER_ENVS[index] if provider_setting else _MODEL_ENVS[index], value)
    checked = policy.check_file(_write(tmp_path, _document(*runtime.TASKS)))
    with pytest.raises(policy.ModelPolicyError):
        policy.validate_configuration(checked)


@pytest.mark.parametrize("setting,value", [
    (compat.BASE_URL_ENV, "https://different-fixture.invalid/v1"),
    (compat.MAX_OUTPUT_PARAM_ENV, "max_tokens"),
    (compat.STRUCTURED_OUTPUTS_ENV, "0"),
    (compat.SEND_STORE_FALSE_ENV, "0"),
    (compat.REASONING_EFFORT_ENV, "high"),
])
def test_effective_endpoint_and_options_must_match_policy(tmp_path, monkeypatch, setting, value):
    _configuration(monkeypatch, ("node",))
    monkeypatch.setenv(setting, value)
    checked = policy.check_file(_write(tmp_path, _document("node")))
    with pytest.raises(policy.ModelPolicyError):
        policy.validate_configuration(checked)


@pytest.mark.parametrize("task", [runtime.NODE_TASK, runtime.INHABITANT_TASK, runtime.INTENT_TASK])
def test_standard_task_timeout_must_fit_policy_before_dispatch(tmp_path, monkeypatch, task):
    _configuration(monkeypatch, (task,))
    checked = policy.check_file(_write(tmp_path, _document(task)))
    # The transport's unset default is 60 seconds, beyond this synthetic
    # route's 12.5-second approval. No remote call is needed to detect it.
    monkeypatch.delenv(compat.TIMEOUT_ENV)
    with pytest.raises(policy.ModelPolicyError):
        policy.validate_configuration(checked)
    monkeypatch.setenv(compat.TIMEOUT_ENV, "12")
    policy.validate_configuration(checked)


def test_moderation_caller_timeout_cannot_exceed_its_policy_bound(tmp_path, monkeypatch):
    _configuration(monkeypatch, (runtime.MODERATION_TASK,))
    # Moderation passes its own three-second budget, so lowering the
    # environment timeout does not shorten that prepared call.
    monkeypatch.setenv(compat.TIMEOUT_ENV, "1")
    document = _document(runtime.MODERATION_TASK)
    document["routes"][runtime.MODERATION_TASK]["timeout_seconds"] = "2.999999"
    with pytest.raises(policy.ModelPolicyError):
        policy.validate_configuration(policy.check_file(_write(tmp_path, document)))
    document["routes"][runtime.MODERATION_TASK]["timeout_seconds"] = "3"
    policy.validate_configuration(policy.check_file(_write(tmp_path, document)))


def test_prepared_request_accepts_only_captured_route_and_bounded_output_timeout(tmp_path, monkeypatch):
    route = _activate(tmp_path, monkeypatch, "node").routes["node"]
    values = {"adapter": route.adapter, "endpoint": _ENDPOINT, "model": route.model,
              "max_output_tokens": 5, "timeout_seconds": 12.5, "options": deepcopy(_OPTIONS)}
    policy.validate_prepared(route, **values)
    policy.validate_prepared(route, **{**values, "timeout_seconds": 1, "max_output_tokens": 1})
    with pytest.raises(policy.ModelPolicyDenied):
        policy.validate_prepared(replace(route), **values)
    for field, bad in (("adapter", "anthropic"), ("endpoint", _ENDPOINT + "/"),
                       ("model", "other-model"), ("max_output_tokens", True),
                       ("max_output_tokens", 0), ("max_output_tokens", 6),
                       ("timeout_seconds", True), ("timeout_seconds", float("nan")),
                       ("timeout_seconds", float("inf")), ("timeout_seconds", 0),
                       ("timeout_seconds", 12.500001), ("options", {}),
                       ("options", {**_OPTIONS, "structured_outputs": 1}),
                       ("options", {**_OPTIONS, "send_store_false": 1})):
        with pytest.raises(policy.ModelPolicyDenied):
            policy.validate_prepared(route, **{**values, field: bad})


def test_summary_omits_destination_model_and_approval_text(tmp_path):
    checked = policy.check_file(_write(tmp_path, _document("node")))
    report = policy.summary(checked)
    assert report["global_limit_microusd"] == 10
    assert report["participant_limit_microusd"] == 5
    assert report["enabled_routes"] == ["node"]
    encoded = json.dumps(report)
    for private in (_ENDPOINT, "fixture-node", "Synthetic fixture terms", "not an approval"):
        assert private not in encoded


def test_reservation_uses_highest_input_price_and_rounds_up_once(tmp_path):
    document = _document("node")
    document["routes"]["node"]["max_input_tokens"] = 1
    document["routes"]["node"]["max_output_tokens"] = 1
    route = policy.check_file(_write(tmp_path, document)).routes["node"]
    assert policy.reserve_microusd(route, 1) == 1  # 0.4 + 0.3 microUSD
    assert policy.reserve_microusd(replace(route, max_input_tokens=10), 5) == 6  # 4 + 1.5


def test_declared_reservation_overflow_is_rejected_offline(tmp_path):
    document = _document("node")
    document["routes"]["node"]["max_input_tokens"] = 2**63 - 1
    document["routes"]["node"]["prices"]["cache_write_per_million_usd"] = "2"
    with pytest.raises(policy.ModelPolicyError):
        policy.check_file(_write(tmp_path, document))


def test_large_decimal_reservations_and_settlements_never_round_below_exact_cost(tmp_path):
    # A valid 18-digit count and a permitted 12-decimal price make an exact
    # fraction smaller than Decimal's default 28-digit arithmetic can keep.
    # Ceil must retain that fraction rather than under-reserve one microUSD.
    document = _document("node")
    document["routes"]["node"]["max_input_tokens"] = 999_999_999_999_999_999
    document["routes"]["node"]["prices"] = {
        key: "0.999999999999" if key == "input_per_million_usd" else "0"
        for key in _PRICES}
    route = policy.check_file(_write(tmp_path, document)).routes["node"]
    expected = 999_999_999_999_000_000  # ceil(999999999998999999.000000000001)
    assert policy.reserve_microusd(route, 1) == expected
    cost, anomaly, _encoded = policy.settlement(
        route, _completion(runtime.TokenUsage(route.max_input_tokens, 0, 0, 0)), 1)
    assert (cost, anomaly) == (expected, False)


@pytest.mark.parametrize("usage,cost", [
    (runtime.TokenUsage(2, 1, 3, 4), 3),  # .4 + .3 + .3 + 1.6 = 2.6, ceil once
    (runtime.TokenUsage(2, 1, 3, None), 3),  # unknown cache-write split: (2+3)*.4+.3
    (runtime.TokenUsage(0, 0, 0, 0), 0),
])
def test_complete_usage_prices_explicit_splits_or_conservative_cache_bound(tmp_path, usage, cost):
    route = policy.check_file(_write(tmp_path, _document("node"))).routes["node"]
    actual, anomaly, encoded = policy.settlement(route, _completion(usage), 5)
    assert (actual, anomaly) == (cost, False)
    assert json.loads(encoded) == {"input_tokens": usage.input_tokens,
                                   "output_tokens": usage.output_tokens,
                                   "cache_read_tokens": usage.cache_read_tokens,
                                   "cache_write_tokens": usage.cache_write_tokens}


@pytest.mark.parametrize("usage", [None, runtime.TokenUsage(None, 1, 0, 0),
                                   runtime.TokenUsage(1, None, 0, 0),
                                   runtime.TokenUsage(1, 1, None, 0)])
def test_unknown_usage_never_claims_a_zero_cost_refund(tmp_path, usage):
    route = policy.check_file(_write(tmp_path, _document("node"))).routes["node"]
    cost, anomaly, _encoded = policy.settlement(route, _completion(usage), 5)
    assert cost is None and anomaly is False


def test_missing_usage_fields_do_not_hide_known_bound_violations(tmp_path):
    route = policy.check_file(_write(tmp_path, _document("node"))).routes["node"]
    cost, anomaly, _encoded = policy.settlement(
        route, _completion(runtime.TokenUsage(11, None, None, None)), 5)
    assert cost is None and anomaly is True


@pytest.mark.parametrize("usage", [runtime.TokenUsage(True, 1, 0, 0),
                                   runtime.TokenUsage(-1, 1, 0, 0),
                                   runtime.TokenUsage(1.5, 1, 0, 0),
                                   runtime.TokenUsage(float("nan"), 1, 0, 0),
                                   runtime.TokenUsage(float("inf"), 1, 0, 0),
                                   runtime.TokenUsage(2**63, 1, 0, 0)])
def test_invalid_usage_latches_an_anomaly_without_a_refund(tmp_path, usage):
    route = policy.check_file(_write(tmp_path, _document("node"))).routes["node"]
    cost, anomaly, _encoded = policy.settlement(route, _completion(usage), 5)
    assert cost is None and anomaly is True


@pytest.mark.parametrize("result", [
    _completion(runtime.TokenUsage(11, 0, 0, 0)),
    _completion(runtime.TokenUsage(0, 6, 0, 0)),
    _completion(runtime.TokenUsage(6, 0, 5, 0)),
    _completion(runtime.TokenUsage(0, 0, 0, 0), model="unapproved-model"),
    _completion(runtime.TokenUsage(0, 0, 0, 0), provider="anthropic"),
    _completion(None, model=None),
])
def test_out_of_bound_usage_or_model_drift_is_never_treated_as_ordinary(tmp_path, result):
    route = policy.check_file(_write(tmp_path, _document("node"))).routes["node"]
    _cost, anomaly, _encoded = policy.settlement(route, result, 5)
    assert anomaly is True
