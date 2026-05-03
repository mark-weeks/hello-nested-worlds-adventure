"""Shared pytest fixtures.

Redirects the persistence layer to a per-test temporary database so server
tests (which now record mutations on more code paths) don't pollute the
developer's real `~/.nested-worlds/worlds.db`.

`test_persistence.py` defines its own fixture with the same intent; that one
runs after this one and wins, so its assertions about row counts remain
deterministic.
"""
from __future__ import annotations

import pytest

import persistence


@pytest.fixture(autouse=True)
def _isolate_persistence_db(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "_DB_PATH", tmp_path / "worlds.db")
    persistence._initialized.discard(tmp_path / "worlds.db")
    yield
