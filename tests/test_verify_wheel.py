"""The wheel gate rejects a migration the source tree no longer has.

No wheel is built here. The check compares names and bytes, and it
refuses a stale ``build/lib`` copy before packaging.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import verify_wheel  # noqa: E402


def test_source_migrations_are_exactly_0001_through_0031_with_blocks_and_consent():
    source = verify_wheel.source_migrations(verify_wheel.ROOT)
    verify_wheel.assert_source_schema_inventory(source)
    assert "persistence/migrations/0030_participant_blocks.sql" in source
    assert "persistence/migrations/0031_participation_consents.sql" in source
    assert not any(name.endswith("0030_cost_budget_names.sql") for name in source)


@pytest.mark.parametrize("replace_blocks", [False, True])
def test_source_rejects_deleted_cost_rename_even_when_it_replaces_blocks(replace_blocks):
    source = verify_wheel.source_migrations(verify_wheel.ROOT)
    if replace_blocks:
        source.pop("persistence/migrations/0030_participant_blocks.sql")
    source["persistence/migrations/0030_cost_budget_names.sql"] = b"stale\n"
    with pytest.raises(RuntimeError, match="0030_cost_budget_names.sql"):
        verify_wheel.assert_source_schema_inventory(source)


def test_a_stale_0030_and_modified_bytes_are_rejected(tmp_path):
    migrations = tmp_path / "persistence" / "migrations"
    migrations.mkdir(parents=True)
    original = b"-- sanctions\n"
    (migrations / "0029_sanctions.sql").write_bytes(original)
    staged = tmp_path / "build" / "lib" / "persistence" / "migrations"
    staged.mkdir(parents=True)
    (staged / "0029_sanctions.sql").write_bytes(b"-- rewritten\n")
    (staged / "0030_cost_budget_names.sql").write_bytes(b"UPDATE cost_budget SET bucket = 'voice';\n")

    with pytest.raises(RuntimeError) as caught:
        verify_wheel.assert_build_tree_migrations(tmp_path)
    message = str(caught.value)
    assert "0030_cost_budget_names.sql" in message
    assert "0029_sanctions.sql" in message

    source = verify_wheel.source_migrations(tmp_path)
    packaged = dict(source)
    packaged["persistence/migrations/0030_cost_budget_names.sql"] = b"stale\n"
    packaged["persistence/migrations/0029_sanctions.sql"] = b"changed\n"
    with pytest.raises(RuntimeError) as caught:
        verify_wheel.assert_migration_inventory(packaged, source)
    message = str(caught.value)
    assert "0030_cost_budget_names.sql" in message
    assert "0029_sanctions.sql" in message

    verify_wheel.assert_migration_inventory(dict(source), source)
    (staged / "0030_cost_budget_names.sql").unlink()
    (staged / "0029_sanctions.sql").write_bytes(original)
    verify_wheel.assert_build_tree_migrations(tmp_path)
