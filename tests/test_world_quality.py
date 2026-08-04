"""The launch world must pass an experiential quality gate before birth."""

from multiverse.quality import LAUNCH_THRESHOLDS, audit_world


def test_provisional_canonical_seed_passes_launch_quality_gate():
    result = audit_world(42)
    assert result["passed"], result["failures"]
    assert result["level_counts"]["SubatomicParticle"] > 0


def test_quality_gate_reports_all_public_metrics():
    result = audit_world(42)
    assert set(result["metrics"]) == set(LAUNCH_THRESHOLDS)
    assert len(result["sample_names"]) == 11
