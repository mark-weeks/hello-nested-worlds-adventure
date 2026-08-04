"""The launch world must pass an experiential quality gate before birth."""

import pytest

from multiverse.generator import DEFAULT_WORLD_SEED
from multiverse.quality import LAUNCH_THRESHOLDS, audit_world


@pytest.fixture(scope="module")
def launch_audit():
    return audit_world(DEFAULT_WORLD_SEED)


def test_canonical_launch_seed_passes_launch_quality_gate(launch_audit):
    result = launch_audit
    assert result["passed"], result["failures"]
    assert result["seed"] == DEFAULT_WORLD_SEED
    assert result["level_counts"]["SubatomicParticle"] > 0


def test_quality_gate_reports_all_public_metrics(launch_audit):
    result = launch_audit
    assert set(result["metrics"]) == set(LAUNCH_THRESHOLDS)
    assert len(result["sample_names"]) == 11
