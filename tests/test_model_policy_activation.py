"""Controlled startup, offline preflight and the image/Sentry boundaries."""
from __future__ import annotations

import json
import secrets
import threading
from types import SimpleNamespace

import pytest

import persistence
import server
from main import main
from server import guard, observability


def _forbidden(*_args, **_kwargs):
    raise AssertionError("a forbidden side effect was reached")


def _off_file(tmp_path):
    path = tmp_path / "policy.json"
    path.write_text(json.dumps({
        "schema_version": 1, "policy_id": "offline-fixture",
        "currency": "USD", "reset": "UTC",
        "routes": {task: {"enabled": False}
                   for task in ("node", "inhabitant", "intent", "moderation", "images")},
    }))
    return path


def test_bad_policy_refuses_before_migrations_listener_and_observability(monkeypatch, capsys):
    from consciousness import model_policy

    def refuse():
        error = model_policy.ModelPolicyError()
        error.args = ("private-key-in-an-untrusted-error",)
        raise error

    monkeypatch.setattr(model_policy, "initialize", refuse)
    monkeypatch.setattr(persistence, "init_db", _forbidden)
    monkeypatch.setattr(server, "_ThreadedServer", _forbidden)
    monkeypatch.setattr(observability, "setup", _forbidden)
    with pytest.raises(SystemExit) as caught:
        server.run(port=0)
    assert caught.value.code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "error: model policy configuration is invalid\n"
    assert not persistence._DB_PATH.exists()


def test_controlled_off_startup_needs_no_disabled_provider_or_legacy_banner(tmp_path, monkeypatch, capsys):
    from consciousness import model_check, model_policy, runtime
    from server import heartbeat, websocket
    import consciousness

    events = []
    monkeypatch.setenv(model_policy.POLICY_ENV, str(_off_file(tmp_path)))
    monkeypatch.setenv(runtime.NODE_PROVIDER_ENV, "not_a_registered_adapter")
    monkeypatch.setenv(runtime.NODE_MODEL_ENV, "")
    monkeypatch.setattr(model_check, "enforce_model_configuration", _forbidden)
    monkeypatch.setattr(consciousness, "warn_if_cache_ineffective", _forbidden)
    monkeypatch.setattr(server, "model_banner", _forbidden)
    monkeypatch.setattr(observability, "setup", lambda: None)
    monkeypatch.setattr(guard, "canonical_seed", lambda: None)
    monkeypatch.setattr(guard, "budget_configuration_warning_line", lambda: None)
    monkeypatch.setattr(guard, "budget_configuration_line", lambda: None)
    monkeypatch.setattr(persistence, "init_db", lambda: events.append("migrate"))
    monkeypatch.setattr(persistence, "checkpoint", lambda: None)
    monkeypatch.setattr(heartbeat, "enabled", lambda: False)
    monkeypatch.setattr(heartbeat, "pump_enabled", lambda: False)
    monkeypatch.setattr(websocket, "stop_credential_sweep", lambda: None)
    monkeypatch.setattr(server.signal, "signal", lambda *_args: None)

    def retention():
        events.append("retention.start")
        return (SimpleNamespace(set=lambda: events.append("retention.stop")),
                SimpleNamespace(join=lambda **_kwargs: events.append("retention.join"),
                                is_alive=lambda: False))

    monkeypatch.setattr(server, "_start_model_spend_retention", retention)

    class Listener:
        def __init__(self, *_args):
            events.append("bind")

        def serve_forever(self):
            events.append("serve")

        def server_close(self):
            events.append("close")

    monkeypatch.setattr(server, "_ThreadedServer", Listener)
    server.run(port=0)
    assert events == ["migrate", "bind", "retention.start", "serve",
                      "retention.stop", "retention.join", "close"]
    assert "all external routes disabled" in capsys.readouterr().out


def test_missing_required_policy_refuses_before_database_or_listener(monkeypatch, capsys):
    from consciousness import model_policy

    monkeypatch.setenv(model_policy.REQUIRED_ENV, "1")
    monkeypatch.delenv(model_policy.POLICY_ENV, raising=False)
    monkeypatch.setenv("NESTED_WORLDS_DISABLE_AI", "0")
    monkeypatch.setenv("NESTED_WORLDS_DISABLE_IMAGES", "1")
    monkeypatch.setattr(persistence, "init_db", _forbidden)
    monkeypatch.setattr(server, "_ThreadedServer", _forbidden)
    with pytest.raises(SystemExit) as caught:
        server.run(port=0)
    assert caught.value.code == 1
    assert not persistence._DB_PATH.exists()
    assert capsys.readouterr().err == "error: model policy configuration is invalid\n"


def test_preflight_checks_without_activating_or_touching_the_database(monkeypatch, capsys):
    from consciousness import model_policy

    policy = object()
    seen = []
    monkeypatch.setattr(model_policy, "check_file", lambda path: seen.append(path) or policy)
    monkeypatch.setattr(model_policy, "validate_configuration", lambda value: seen.append(value))
    monkeypatch.setattr(model_policy, "summary", lambda value: {"enabled_tasks": []})
    monkeypatch.setattr(model_policy, "initialize", _forbidden)
    monkeypatch.setattr(persistence, "init_db", _forbidden)
    main(["model-policy", "--check", "--policy", "/operator/policy.json"])
    assert seen == ["/operator/policy.json", policy]
    report = json.loads(capsys.readouterr().out)
    assert report == {"configuration": {"enabled_tasks": []},
                      "remote_verified": False, "live_calls": False}
    assert not persistence._DB_PATH.exists()


def test_all_off_preflight_uses_real_loader_without_provider_or_activation(tmp_path, monkeypatch, capsys):
    from consciousness import model_policy, runtime

    monkeypatch.setattr(runtime, "provider_for", _forbidden)
    monkeypatch.setenv(runtime.NODE_MODEL_ENV, "")
    main(["model-policy", "--check", "--policy", str(_off_file(tmp_path))])
    report = json.loads(capsys.readouterr().out)
    assert report["configuration"]["enabled_routes"] == []
    assert report["remote_verified"] is False
    assert not model_policy.active()
    assert not persistence._DB_PATH.exists()


@pytest.mark.parametrize("stage", ["file", "configuration"])
def test_preflight_does_not_echo_untrusted_failure_details(monkeypatch, capsys, stage):
    from consciousness import model_policy

    def fail(*_args):
        error = model_policy.ModelPolicyError()
        error.args = ("secret-model-key https://private.example/?key=secret",)
        raise error

    monkeypatch.setattr(model_policy, "check_file", fail if stage == "file" else lambda _path: object())
    monkeypatch.setattr(model_policy, "validate_configuration", fail)
    with pytest.raises(SystemExit) as caught:
        main(["model-policy", "--check", "--policy", "/operator/private.json"])
    assert caught.value.code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "error: model policy configuration is invalid\n"


def test_preflight_requires_an_explicit_check_and_policy_path(capsys):
    for argv in (["model-policy"], ["model-policy", "--check"],
                 ["model-policy", "--policy", "somewhere.json"]):
        with pytest.raises(SystemExit) as caught:
            main(argv)
        assert caught.value.code == 2
    capsys.readouterr()


def test_controlled_image_refuses_before_cache_charge_and_dispatch(http, monkeypatch):
    from consciousness import model_policy
    import urllib.request

    monkeypatch.setenv(model_policy.REQUIRED_ENV, "1")
    monkeypatch.delenv(model_policy.POLICY_ENV, raising=False)
    monkeypatch.setenv("NESTED_WORLDS_DISABLE_AI", "1")
    monkeypatch.setenv("NESTED_WORLDS_DISABLE_IMAGES", "1")
    model_policy.initialize()
    monkeypatch.delenv(model_policy.REQUIRED_ENV)
    monkeypatch.setattr(persistence, "get_cached_image", _forbidden)
    monkeypatch.setattr(guard, "consume_fal", _forbidden)
    # The HTTP fixture uses urlopen too; retain it for loopback only.
    original = urllib.request.urlopen

    def local_only(request, *args, **kwargs):
        if not request.full_url.startswith("http://127.0.0.1:"):
            raise AssertionError("the image provider was contacted")
        return original(request, *args, **kwargs)

    monkeypatch.setattr(urllib.request, "urlopen", local_only)
    for flag in ("1", "0"):
        monkeypatch.setenv("NESTED_WORLDS_DISABLE_IMAGES", flag)
        monkeypatch.setenv("FAL_KEY", "a-key-added-after-activation")
        status, body, _headers = http("/image", body={"node_name": "anywhere"})
        assert status == 200
        assert body == {"url": None, "images": False, "error": server.handlers._IMAGE_QUIET_LINE}


def test_sentry_captured_exception_does_not_include_frame_locals(monkeypatch):
    import sentry_sdk
    from sentry_sdk.integrations import logging as sentry_logging
    from sentry_sdk.transport import Transport

    events = []

    class Capture(Transport):
        def capture_envelope(self, envelope):
            for item in envelope.items:
                event = item.get_event()
                if event is not None:
                    events.append(event)

    for name in ("_IGNORED_LOGGERS", "_IGNORED_LOGGERS_SENTRY_LOGS"):
        if hasattr(sentry_logging, name):
            monkeypatch.setattr(sentry_logging, name, getattr(sentry_logging, name).copy())
    global_scope = sentry_sdk.get_global_scope()
    previous_client = global_scope.client
    clients = []

    def capture_init(**kwargs):
        client = sentry_sdk.Client(**kwargs, transport=Capture, default_integrations=False)
        clients.append(client)
        global_scope.set_client(client)

    monkeypatch.setattr(sentry_sdk, "init", capture_init)
    monkeypatch.setattr(observability, "_sentry_ready", False)
    monkeypatch.setenv("SENTRY_DSN", "https://fixture@example.invalid/1")
    try:
        observability.setup()
        private_value = secrets.token_hex(32)

        def private_frame():
            provider_key = private_value
            assert provider_key
            raise ValueError("fixture error")

        try:
            private_frame()
        except ValueError as exc:
            observability.capture_exception(exc)
        assert len(events) == 1
        frames = events[0]["exception"]["values"][0]["stacktrace"]["frames"]
        assert frames
        assert all("vars" not in frame for frame in frames)
        assert private_value not in json.dumps(events)
    finally:
        global_scope.set_client(previous_client)
        for client in clients:
            client.close()


def test_idle_retention_runs_immediately_and_stops_without_waiting_a_tick():
    called = threading.Event()
    calls = []

    def prune():
        calls.append(threading.current_thread().name)
        called.set()
        return 0

    stopped, worker = server._start_model_spend_retention(interval_seconds=3600, prune=prune)
    try:
        assert called.wait(1)
    finally:
        stopped.set()
        worker.join(timeout=1)
    assert not worker.is_alive()
    assert calls == ["model-spend-retention"]


def test_retention_retries_after_failure_without_logging_private_details(caplog):
    retried, release = threading.Event(), threading.Event()
    calls = []

    def prune():
        calls.append(1)
        if len(calls) == 1:
            raise ValueError("private model accounting metadata")
        retried.set()
        assert release.wait(1)
        return 0

    stopped, worker = server._start_model_spend_retention(interval_seconds=0, prune=prune)
    try:
        assert retried.wait(1)
    finally:
        stopped.set()
        release.set()
        worker.join(timeout=1)
    assert not worker.is_alive()
    assert len(calls) == 2
    assert "model accounting retention unavailable (ValueError)" in caplog.text
    assert "private model accounting metadata" not in caplog.text
