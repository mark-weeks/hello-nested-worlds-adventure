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

3. World hosting — explicitly enables the local multi-world mode used by the
   historical behavior suite. Canonical-world boundary tests override it.
"""
from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

import pytest

import persistence
from server import _Handler, _ThreadedServer, rooms as _rooms_module


@pytest.fixture(autouse=True)
def _local_multiworld_mode(monkeypatch):
    # The runtime default is fail-closed to the launch world. Most unit tests
    # intentionally exercise isolated worlds with distinct seeds, which is a
    # supported CLI/local-development capability rather than a public-server
    # capability.
    monkeypatch.setenv("NESTED_WORLDS_CANONICAL_SEED", "")


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
def _reset_text_provider(monkeypatch):
    """Selection is cached for the process. Each test starts unset.

    Task provider overrides and the neutral budget names are cleared so a
    developer environment cannot leak into the suite. Legacy budget names
    are left for the test that sets them.
    """
    from consciousness import model_dispatch, model_policy, runtime
    from server import guard
    for name in runtime.TASK_PROVIDER_ENVS:
        monkeypatch.delenv(name, raising=False)
    for name in (
        guard.VOICE_CAP_ENV, guard.VOICE_PER_USER_CAP_ENV,
        guard.IMAGE_CAP_ENV, guard.IMAGE_PER_USER_CAP_ENV,
        model_policy.POLICY_ENV, model_policy.REQUIRED_ENV,
    ):
        monkeypatch.delenv(name, raising=False)
    runtime.reset_provider_selection()
    model_policy.reset_for_tests()
    model_dispatch.reset_for_tests()
    yield
    runtime.reset_provider_selection()
    model_policy.reset_for_tests()
    model_dispatch.reset_for_tests()


@pytest.fixture(autouse=True)
def _isolate_rate_limits(monkeypatch):
    """The per-IP rate limiter, WS connection limiter and per-credential WS
    message buckets are module-level singletons; one test file's requests
    must not 429 the next file's."""
    from server import guard
    guard.RATE_LIMITER.reset()
    guard.READ_RATE_LIMITER.reset()
    guard.IDEAS_AUTH_FAILURE_RATE_LIMITER.reset()
    guard.WS_LIMITER.reset()
    guard.WS_MOVE_BUCKETS.reset()
    guard.WS_CHAT_BUCKETS.reset()
    # Open sockets re-check authorization on every frame in tests, so a
    # suite can revoke and send one frame without waiting out the
    # production throttle. The throttle itself is pinned in
    # tests/test_ws_credential_lifetime.py::TestReauthorizationThrottle.
    monkeypatch.setattr(guard, "WS_REAUTH_INTERVAL_SEC", 0.0)
    # The credential sweep re-checks quiet sockets on the server's own
    # schedule. An hour here keeps it out of other suites' lookup counts
    # and frame-driven closes; tests/test_ws_credential_sweep.py shortens it.
    monkeypatch.setattr(guard, "WS_SWEEP_INTERVAL_SEC", 3600.0)
    yield
    guard.RATE_LIMITER.reset()
    guard.READ_RATE_LIMITER.reset()
    guard.IDEAS_AUTH_FAILURE_RATE_LIMITER.reset()
    guard.WS_LIMITER.reset()
    guard.WS_MOVE_BUCKETS.reset()
    guard.WS_CHAT_BUCKETS.reset()


@pytest.fixture
def accounts():
    persistence.mint_invite_key('nw_' + 'a' * 32, 'Ada')
    persistence.mint_invite_key('nw_' + 'b' * 32, 'Bea')
    return 'nw_' + 'a' * 32, 'nw_' + 'b' * 32


@pytest.fixture
def http(accounts, monkeypatch):
    monkeypatch.setenv('NESTED_WORLDS_CANONICAL_SEED', '382')
    server = _ThreadedServer(('127.0.0.1', 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    def request(path, key=accounts[0], body=None):
        req = urllib.request.Request(f'http://127.0.0.1:{server.server_port}{path}',
            data=json.dumps(body).encode() if body is not None else None,
            headers={'X-Beta-Key': key, 'Content-Type': 'application/json'})
        try:
            response = urllib.request.urlopen(req, timeout=10)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            data = json.load(response) if response.headers.get_content_type() == 'application/json' else response.read().decode()
            return response.status, data, dict(response.headers)
    try:
        yield request
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)
