"""PR172 regressions use fictitious declarations and authored transports only."""
from __future__ import annotations

import json

import pytest

from consciousness import model_policy as policy, runtime
from consciousness import openai_compat_provider as compat
from persistence import model_spend
import persistence
from tests.test_model_policy import _configuration, _document, _write
from tests.test_model_dispatch import real_controlled as real_controlled, _runtime_call, _reply


@pytest.fixture(autouse=True)
def _environment(monkeypatch):
    for name in ("NESTED_WORLDS_DISABLE_AI", "NESTED_WORLDS_DISABLE_MODERATION",
                 "NESTED_WORLDS_TEST_WORLD"):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize("field", ["model", "resolved_models"])
def test_policy_accepts_adapter_model_alphabet_without_weakening_policy_id(tmp_path, monkeypatch, field):
    document = _document("node")
    value = "vendor/model@v1+preview~latest"
    document["routes"]["node"][field] = [value] if field == "resolved_models" else value
    checked = policy.check_file(_write(tmp_path, document))
    if field == "model":
        _configuration(monkeypatch, ("node",))
        monkeypatch.setenv(runtime.NODE_MODEL_ENV, value)
        policy.validate_configuration(checked)
    else:
        assert checked.routes["node"].resolved_models == (value,)
    document["policy_id"] = value
    with pytest.raises(policy.ModelPolicyError):
        policy.check_file(_write(tmp_path, document))


@pytest.mark.parametrize("model", ["", "bad model", "bad\nmodel", "bad\x7fmodel", "x" * 257])
def test_model_alphabet_still_rejects_structurally_invalid_ids(tmp_path, model):
    document = _document("node")
    document["routes"]["node"]["model"] = model
    with pytest.raises(policy.ModelPolicyError):
        policy.check_file(_write(tmp_path, document))


@pytest.mark.parametrize("field", ["input_per_million_usd", "output_per_million_usd"])
def test_an_enabled_route_cannot_accidentally_declare_unbilled_tokens(tmp_path, field):
    document = _document("node")
    document["routes"]["node"]["prices"][field] = "0"
    with pytest.raises(policy.ModelPolicyError):
        policy.check_file(_write(tmp_path, document))


def test_zero_cache_rates_are_explicit_but_still_reserve_positive_money(tmp_path):
    document = _document("node")
    for field in ("cache_read_per_million_usd", "cache_write_per_million_usd"):
        document["routes"]["node"]["prices"][field] = "0"
    checked = policy.check_file(_write(tmp_path, document))
    assert policy.reserve_microusd(checked.routes["node"], 5) > 0


def test_unicode_policy_preflight_and_ledger_share_the_same_snapshot_contract(tmp_path, accounts):
    document = _document(*runtime.TASKS)
    document["limits"] = {"global_daily_usd": "1", "participant_daily_usd": "1"}
    for route in document["routes"].values():
        if route["enabled"]:
            for field in ("input_bound_evidence", "data_use_note", "approval_reference"):
                route[field] = "界" * 1000
    path = tmp_path / "unicode.json"
    path.write_text(json.dumps(document, ensure_ascii=False))
    checked = policy.check_file(path)
    assert len(json.dumps(document, sort_keys=True, separators=(",", ":"))) > 65536
    assert len(checked.snapshot_json) <= model_spend.MAX_POLICY_JSON_CHARS
    reservation = model_spend.reserve(
        user_key=accounts[0], reserved_microusd=10, global_limit_microusd=1_000_000,
        participant_limit_microusd=1_000_000, policy_snapshot=checked.snapshot_json,
        task="node", adapter="openai_compatible", endpoint=checked.routes["node"].endpoint,
        model=checked.routes["node"].model, retention_days=2,
    )
    assert reservation


def test_snapshot_over_ledger_limit_is_rejected_during_offline_check(tmp_path, monkeypatch):
    monkeypatch.setattr(model_spend, "MAX_POLICY_JSON_CHARS", 100)
    with pytest.raises(policy.ModelPolicyError):
        policy.check_file(_write(tmp_path, _document("node")))
    assert not persistence._DB_PATH.exists()


def test_unpaired_unicode_surrogate_is_rejected_before_ledger_admission(tmp_path):
    document = _document("node")
    document["routes"]["node"]["data_use_note"] = "\ud800"
    with pytest.raises(policy.ModelPolicyError):
        policy.check_file(_write(tmp_path, document))
    assert not persistence._DB_PATH.exists()


@pytest.mark.parametrize("value,expected", [
    ("unlisted/model-v2", "unlisted/model-v2"),
    ("private words pasted here", None), ("x" * 257, None),
    ("sk-private-credential", None), ("nw_" + "a" * 32, None), (None, None),
])
def test_unexpected_model_metadata_is_bounded_and_credentials_are_omitted(value, expected):
    assert policy.safe_reported_model(value) == expected


def test_known_credentials_cannot_be_saved_as_a_returned_model_id(monkeypatch):
    monkeypatch.setenv(compat.API_KEY_ENV, "fixture-private-credential")
    assert policy.safe_reported_model("fixture-private-credential") is None


@pytest.mark.parametrize("usage", [
    {"prompt_tokens": 1001, "completion_tokens": 2, "total_tokens": 1003},
    {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12,
     "prompt_tokens_details": {"cached_tokens": 0},
     "completion_tokens_details": {"reasoning_tokens": 100}},
    {"prompt_tokens": 10, "completion_tokens": 5000},
    {"prompt_tokens": 10, "completion_tokens": 5000, "total_tokens": 12},
    {"total_tokens": 50_000},
])
def test_known_usage_violation_retains_reservation_and_stops_the_next_send(real_controlled, usage):
    def transport(request):
        real_controlled.requests.append(request)
        status, headers, raw = _reply()
        body = json.loads(raw)
        body["usage"] = usage
        return status, headers, json.dumps(body).encode()

    real_controlled.adapter._transport = transport
    for _ in range(2):
        with pytest.raises(policy.ModelPolicyDenied):
            _runtime_call(real_controlled)
    with persistence._connection() as connection:
        assert connection.execute("""SELECT status,reserved_microusd,accounted_microusd
            FROM model_spend_reservations""").fetchall() == [("anomaly", 2064, 2064)]
        assert connection.execute("SELECT reason FROM model_spend_latch").fetchall() == [("billing_anomaly",)]
    assert len(real_controlled.requests) == 1
