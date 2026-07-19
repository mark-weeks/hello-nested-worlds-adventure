"""Shared pytest fixtures.

Two pieces of test isolation:

1. Persistence — redirects `persistence._DB_PATH` to a per-test temp file
   so server tests don't pollute `~/.nested-worlds/worlds.db`.
   `test_persistence.py` defines its own fixture with the same intent;
   that one runs after this one and wins, so its assertions about row
   counts remain deterministic.

2. Rooms — clears the global `server.rooms._rooms` registry between tests.
   The puzzle-session co-op state lives there, and a previous test's
   solver would otherwise short-circuit the next test's attempt flow.
"""
from __future__ import annotations

import pytest

import persistence
from server import rooms as _rooms_module


@pytest.fixture(autouse=True)
def _isolate_persistence_db(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "_DB_PATH", tmp_path / "worlds.db")
    persistence._initialized.discard(tmp_path / "worlds.db")
    yield


@pytest.fixture(autouse=True)
def _isolate_rooms():
    _rooms_module.clear_rooms()
    yield
    _rooms_module.clear_rooms()


@pytest.fixture(autouse=True)
def _isolate_rate_limits():
    """The per-IP rate limiter and WS connection limiter are module-level
    singletons; one test file's requests must not 429 the next file's."""
    from server import guard
    guard.RATE_LIMITER.reset()
    guard.READ_RATE_LIMITER.reset()
    guard.WS_LIMITER.reset()
    yield
    guard.RATE_LIMITER.reset()
    guard.READ_RATE_LIMITER.reset()
    guard.WS_LIMITER.reset()
