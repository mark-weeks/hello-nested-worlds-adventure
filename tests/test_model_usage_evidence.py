"""Independent billing bounds survive incomplete or contradictory telemetry."""
from __future__ import annotations

from dataclasses import asdict

import pytest

from consciousness.openai_compat_provider import parse_response
from consciousness.runtime import BillingEvidence, TokenUsage


def _parse(usage):
    return parse_response({
        "model": "synthetic-model",
        "choices": [{"finish_reason": "stop", "message": {"content": "A bell."}}],
        "usage": usage,
    })


def test_prompt_aggregate_survives_missing_cache_split():
    result = _parse({"prompt_tokens": 1001, "total_tokens": 1003, "completion_tokens": 2})
    assert result.usage == TokenUsage(None, 2, None, None)
    assert result.billing_evidence == BillingEvidence(1001, 2, True, 1003)


def test_completion_lower_bound_survives_missing_total():
    result = _parse({"prompt_tokens": 10, "completion_tokens": 65})
    assert result.usage == TokenUsage(None, None, None, None)
    assert result.billing_evidence == BillingEvidence(10, 65, True)


def test_reasoning_lower_bound_survives_contradictory_total():
    result = _parse({
        "prompt_tokens": 10, "total_tokens": 19, "completion_tokens": 9,
        "prompt_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
        "completion_tokens_details": {"reasoning_tokens": 110},
    })
    assert result.usage == TokenUsage(10, None, 0, 0)
    assert result.billing_evidence == BillingEvidence(10, 110, False, 19)


def test_reasoning_without_total_is_evidence_but_not_a_priceable_total():
    result = _parse({"completion_tokens_details": {"reasoning_tokens": 65}})
    assert result.usage == TokenUsage(None, None, None, None)
    assert result.billing_evidence == BillingEvidence(None, 65, True)


@pytest.mark.parametrize("count", [None, True, -1, "2", 2.0, {}, []])
def test_invalid_reasoning_cannot_authorize_an_output_refund(count):
    result = _parse({
        "prompt_tokens": 10, "total_tokens": 12, "completion_tokens": 2,
        "prompt_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
        "completion_tokens_details": {"reasoning_tokens": count},
    })
    assert result.usage == TokenUsage(10, None, 0, 0)
    assert result.billing_evidence == BillingEvidence(10, 2, False, 12)


@pytest.mark.parametrize("count", [None, True, -1, "2", 2.0, {}, []])
def test_invalid_cache_write_does_not_disappear_into_a_missing_split(count):
    result = _parse({
        "prompt_tokens": 10, "total_tokens": 12, "completion_tokens": 2,
        "prompt_tokens_details": {"cached_tokens": 0, "cache_write_tokens": count},
    })
    assert result.usage == TokenUsage(None, 2, 0, None)
    assert result.billing_evidence == BillingEvidence(10, 2, False, 12)


def test_cache_counts_cannot_exceed_known_prompt_aggregate():
    result = _parse({
        "prompt_tokens": 10, "total_tokens": 12, "completion_tokens": 2,
        "prompt_tokens_details": {"cached_tokens": 9, "cache_write_tokens": 2},
    })
    assert result.usage == TokenUsage(None, 2, 9, 2)
    assert result.billing_evidence == BillingEvidence(10, 2, False, 12)


def test_negative_derived_output_preserves_independent_known_bounds():
    result = _parse({"prompt_tokens": 10, "total_tokens": 9, "completion_tokens": 1})
    assert result.usage == TokenUsage(None, None, None, None)
    assert result.billing_evidence == BillingEvidence(10, 1, False, 9)


def test_total_still_bounds_completion_when_prompt_count_is_missing():
    result = _parse({"total_tokens": 2, "completion_tokens": 3})
    assert result.usage == TokenUsage(None, None, None, None)
    assert result.billing_evidence == BillingEvidence(None, 3, False, 2)


def test_total_aggregate_survives_missing_prompt_and_output_split():
    result = _parse({"total_tokens": 1065})
    assert result.usage == TokenUsage()
    assert result.billing_evidence == BillingEvidence(total_tokens=1065)


@pytest.mark.parametrize("total", [None, True, -1, "12", 12.0, {}, []])
def test_invalid_total_preserves_independent_output_lower_bound(total):
    result = _parse({"prompt_tokens": 10, "total_tokens": total, "completion_tokens": 2})
    assert result.usage == TokenUsage()
    assert result.billing_evidence == BillingEvidence(10, 2, False)


@pytest.mark.parametrize("usage", [
    {"total_tokens": 2, "prompt_tokens_details": {"cached_tokens": 3}},
    {"total_tokens": 4, "prompt_tokens_details": {"cached_tokens": 3, "cache_write_tokens": 2}},
    {"total_tokens": 10, "completion_tokens": 6, "prompt_tokens_details": {"cached_tokens": 6}},
])
def test_total_bounds_known_input_and_output_parts_without_prompt_aggregate(usage):
    result = _parse(usage)
    assert result.usage.input_tokens is None and result.usage.output_tokens is None
    assert result.billing_evidence.prompt_tokens is None
    assert result.billing_evidence.consistent is False


def test_large_known_counters_are_not_erased_before_policy_bound_checks():
    large = 2**80
    result = _parse({"prompt_tokens": large, "completion_tokens": large})
    assert result.usage == TokenUsage(None, None, None, None)
    assert result.billing_evidence == BillingEvidence(large, large, True)


@pytest.mark.parametrize("usage", [None, {}])
def test_missing_counters_are_uncertain_without_inventing_a_contradiction(usage):
    result = _parse(usage)
    if usage is None:
        assert result.usage is None and result.billing_evidence is None
    else:
        assert result.usage == TokenUsage()
        assert result.billing_evidence == BillingEvidence()


@pytest.mark.parametrize("usage", [[], True, "bad telemetry"])
def test_malformed_usage_container_is_distinct_from_missing_usage(usage):
    result = _parse(usage)
    assert result.usage is None
    assert result.billing_evidence == BillingEvidence(consistent=False)


def test_only_normalized_counts_and_flags_enter_billing_metadata():
    result = _parse({
        "prompt_tokens": 10, "total_tokens": 12,
        "prompt_tokens_details": {"cached_tokens": 0},
        "private_payload": "secret provider metadata",
    })
    assert asdict(result.billing_evidence) == {
        "prompt_tokens": 10, "output_tokens_lower_bound": 2, "consistent": True, "total_tokens": 12,
    }
    assert set(asdict(result.usage)) == {
        "input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens",
    }
    assert "secret provider metadata" not in repr(result)
