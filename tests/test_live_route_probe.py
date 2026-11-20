"""The live-route probe against a local controlled server.

The Chat Completions peer is a TLS loopback. Nothing in this module contacts
a provider or a Fly app. Ledger assertions read the temporary database
themselves, so a probe that returns without checking the rows cannot pass.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler
import json
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import threading
import time
import urllib.request
from urllib.parse import urlparse

import pytest

import persistence
from consciousness import honesty, model_dispatch, model_policy, runtime
from consciousness import openai_compat_provider as compat
from server import _Handler, _ThreadedServer, guard, moderation
from tests.test_openai_compat_provider import _Loopback, _chat_body, _stop_loopback

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import live_route_probe as probe  # noqa: E402

_KEY = "nw_" + "c" * 32
_PROVIDER_KEY = "sk-live-route-probe-fixture"
_OPTIONS = {
    "max_tokens_param": "max_completion_tokens",
    "structured_outputs": True,
    "send_store_false": True,
    "reasoning_effort": "none",
}
_PRICES = {
    "input_per_million_usd": "0.2",
    "output_per_million_usd": "0.3",
    "cache_read_per_million_usd": "0.1",
    "cache_write_per_million_usd": "0.4",
}
_USAGE = {
    "prompt_tokens": 10,
    "completion_tokens": 2,
    "total_tokens": 12,
    "prompt_tokens_details": {"cached_tokens": 1, "cache_write_tokens": 0},
}
_INTENT = json.dumps({
    "status": "ready",
    "ambiguity": "none",
    "steps": [{"op": "shear", "amount": 1}],
})
_RESOLVED = {f"fixture-{task}": f"fixture-{task}-v1" for task in runtime.TASKS}


class _Chat(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        return

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b""
        try:
            document = json.loads(raw.decode("utf-8"))
            model = document["model"]
        except (UnicodeError, ValueError, KeyError, TypeError):
            self.send_error(400)
            return
        if type(model) is not str or model not in _RESOLVED:
            self.send_error(404)
            return
        self.server.seen.append({
            "model": model,
            "authorized": str(self.headers.get("Authorization", "")).startswith("Bearer "),
        })
        if self.server.mode == "down":
            self.send_error(500)
            return
        usage = dict(_USAGE)
        if self.server.mode == "uncertain":
            del usage["total_tokens"]
        if model == "fixture-moderation":
            content = "ALLOW"
        elif model == "fixture-intent":
            content = _INTENT
        else:
            content = "The lights answer."
        payload = _chat_body(content=content, model=_RESOLVED[model], usage=usage)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class _Recording(_Handler):
    def _send_json(self, data, status=200):
        path = urlparse(self.path).path
        body = data if isinstance(data, dict) else {}
        self.server.calls.append({
            "path": path,
            "status": status,
            "keyed": bool(self.headers.get("X-Beta-Key")),
            "ai": body.get("ai"),
            "held": body.get("held"),
            "accepted": body.get("accepted"),
            "has_ai": "ai" in body,
            "response": body.get("response"),
            "error": body.get("error"),
            "persona": body.get("persona"),
            "id": body.get("id"),
        })
        return super()._send_json(data, status)


def _certificate(directory: Path) -> Path:
    cert = directory / "cert.pem"
    key = directory / "key.pem"
    issued = subprocess.run(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
            "-keyout", str(key), "-out", str(cert), "-days", "1",
            "-subj", "/CN=127.0.0.1",
            "-addext", "subjectAltName=IP:127.0.0.1",
        ],
        check=False, capture_output=True,
    )
    if issued.returncode != 0:
        pytest.fail("openssl could not write a loopback certificate")
    return cert


def _start_tls(cert: Path):
    try:
        server = _Loopback(("127.0.0.1", 0), _Chat)
    except OSError as exc:
        pytest.fail(f"loopback bind unavailable ({type(exc).__name__})")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, cert.with_name("key.pem"))
    server.socket = context.wrap_socket(server.socket, server_side=True)
    server.mode = "ok"
    server.seen = []
    server._accepting = threading.Event()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    server._thread = thread
    thread.start()
    if not server._accepting.wait(2):
        _stop_loopback(server)
        pytest.fail("loopback accept thread did not start")
    client = ssl.create_default_context(cafile=str(cert))
    deadline = time.monotonic() + 2
    while True:
        raw = None
        try:
            raw = socket.create_connection(server.server_address, timeout=0.2)
            tls = client.wrap_socket(raw, server_hostname="127.0.0.1")
        except OSError:
            if raw is not None:
                raw.close()
            if time.monotonic() >= deadline:
                _stop_loopback(server)
                pytest.fail("tls loopback port did not accept")
            time.sleep(0.01)
            continue
        tls.close()
        return server


def _policy(path: Path, endpoint: str, limits: tuple[str, str]) -> None:
    routes = {
        task: {
            "enabled": True,
            "adapter": "openai_compatible",
            "endpoint": endpoint,
            "model": f"fixture-{task}",
            "resolved_models": [f"fixture-{task}-v1"],
            "max_input_tokens": 8000,
            "max_output_tokens": 500,
            "input_bound_kind": "provider_context_maximum",
            "input_bound_evidence": "Synthetic bound for an offline test only.",
            "timeout_seconds": "12",
            "options": _OPTIONS,
            "prices": _PRICES,
            "data_use_note": "Synthetic fixture terms. No remote model is contacted.",
            "approval_reference": "Synthetic fixture, not an approval.",
        }
        for task in runtime.TASKS
    }
    routes["images"] = {"enabled": False}
    document = {
        "schema_version": 1,
        "policy_id": "live-route-probe-fixture",
        "currency": "USD",
        "reset": "UTC",
        "limits": {"global_daily_usd": limits[0], "participant_daily_usd": limits[1]},
        "ledger_retention_days": 2,
        "routes": routes,
    }
    path.write_text(json.dumps(document), encoding="utf-8")


def _wait(port: int) -> None:
    deadline = time.monotonic() + 5
    while True:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/participation", timeout=0.5) as response:
                response.read()
            return
        except Exception:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.02)


def _stop_game(server, thread) -> None:
    server.shutdown()
    server.server_close()
    thread.join(5)


@pytest.fixture
def stage(tmp_path, monkeypatch):
    started = []

    def start(*, mode="ok", test_world="1", limits=("1", "1"), extra=None):
        cert = _certificate(tmp_path)
        fake = _start_tls(cert)
        port = fake.server_address[1]
        fake.mode = mode
        policy_path = tmp_path / "model-policy.json"
        _policy(policy_path, f"https://127.0.0.1:{port}/v1/chat/completions", limits)
        monkeypatch.setenv("NESTED_WORLDS_TEST_WORLD", test_world)
        monkeypatch.setenv(model_policy.POLICY_ENV, str(policy_path))
        monkeypatch.setenv(runtime.PROVIDER_ENV, "openai_compatible")
        monkeypatch.setenv(compat.BASE_URL_ENV, f"https://127.0.0.1:{port}/v1")
        monkeypatch.setenv(compat.API_KEY_ENV, _PROVIDER_KEY)
        monkeypatch.setenv(compat.MAX_OUTPUT_PARAM_ENV, "max_completion_tokens")
        monkeypatch.setenv(compat.STRUCTURED_OUTPUTS_ENV, "1")
        monkeypatch.setenv(compat.SEND_STORE_FALSE_ENV, "1")
        monkeypatch.setenv(compat.REASONING_EFFORT_ENV, "none")
        monkeypatch.setenv(compat.TIMEOUT_ENV, "12")
        monkeypatch.setenv("SSL_CERT_FILE", str(cert))
        model_envs = (
            runtime.NODE_MODEL_ENV, runtime.INHABITANT_MODEL_ENV,
            runtime.INTENT_MODEL_ENV, runtime.MODERATION_MODEL_ENV,
        )
        for provider_env, model_env, task in zip(runtime.TASK_PROVIDER_ENVS, model_envs, runtime.TASKS):
            monkeypatch.setenv(provider_env, "openai_compatible")
            monkeypatch.setenv(model_env, f"fixture-{task}")
        for name in (
            guard.ANTHROPIC_CAP_ENV, guard.ANTHROPIC_PER_USER_CAP_ENV,
            guard.MODERATION_ACTIONS_PER_USER_ENV, guard.MODERATION_CAP_ENV,
            guard.MODERATION_PER_USER_CAP_ENV, guard.MODEL_ACTIONS_PER_USER_ENV,
            guard.DISABLE_AI_ENV, "ENFOLDED_LIVE_ROUTE_KEY",
        ):
            monkeypatch.delenv(name, raising=False)
        for name, value in (extra or {}).items():
            monkeypatch.setenv(name, value)
        persistence.init_db()
        persistence.mint_invite_key(_KEY, "Check")
        model_policy.reset_for_tests()
        model_dispatch.reset_for_tests()
        runtime.reset_provider_selection()
        model_policy.initialize()
        game = _ThreadedServer(("127.0.0.1", 0), _Recording)
        game.calls = []
        thread = threading.Thread(target=game.serve_forever, daemon=True)
        thread.start()
        _wait(game.server_port)
        game.calls.clear()
        fake.seen.clear()
        started.append((fake, game, thread))
        return fake, game, f"http://127.0.0.1:{game.server_port}"

    try:
        yield start
    finally:
        for fake, game, thread in started:
            _stop_game(game, thread)
            _stop_loopback(fake)
        model_policy.reset_for_tests()
        model_dispatch.reset_for_tests()


def _rows():
    with persistence._connection() as conn:
        return conn.execute(
            """SELECT task, status, reserved_microusd, accounted_microusd, usage_json, resolved_model
               FROM model_spend_reservations ORDER BY rowid"""
        ).fetchall()


def _argv(url, case, db=True):
    argv = ["--url", url, "--case", case, "--key", _KEY, "--timeout", "30"]
    if db:
        argv.extend(["--db", str(persistence._DB_PATH)])
    return argv


def _quiet_output(capsys, key=_KEY):
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert key not in combined
    assert _PROVIDER_KEY not in combined
    assert probe.SHARED_LINE not in combined
    assert "1234567" not in combined
    return captured


def test_success_settles_each_task(stage, capsys):
    fake, _game, url = stage()
    probe.main(_argv(url, "success"))
    captured = _quiet_output(capsys)
    assert '"intent": 1' in captured.out
    seen = [item["model"] for item in fake.seen]
    assert seen.count("fixture-moderation") == 2
    assert seen.count("fixture-node") == 1
    assert seen.count("fixture-inhabitant") == 1
    assert seen.count("fixture-intent") == 1
    assert all(item["authorized"] for item in fake.seen)
    rows = _rows()
    assert [row[0] for row in rows] == [
        "moderation", "node", "moderation", "inhabitant", "intent",
    ]
    assert {row[1] for row in rows} == {"settled"}
    assert all(row[3] <= row[2] for row in rows)
    for task, _status, _reserved, _accounted, usage_json, resolved in rows:
        usage = json.loads(usage_json)
        assert all(type(usage[field]) is int and usage[field] >= 0
                   for field in ("input_tokens", "output_tokens", "cache_read_tokens"))
        assert resolved == f"fixture-{task}-v1"
    blob = persistence._DB_PATH.read_bytes()
    assert _KEY.encode() not in blob
    assert _PROVIDER_KEY.encode() not in blob


def test_uncertain_usage_fails_requirement_4(stage, capsys):
    _fake, game, url = stage(mode="uncertain")
    with pytest.raises(SystemExit) as caught:
        probe.main(_argv(url, "success"))
    assert caught.value.code == 1
    captured = _quiet_output(capsys)
    assert "failed ADR-035 requirement 4" in captured.err
    assert "uncertain" in captured.err
    speak = next(item for item in game.calls if item["path"] == "/speak")
    assert speak["status"] == 200 and speak["ai"] is True
    assert any(row[1] == "uncertain" for row in _rows())


def test_hold_when_the_moderation_action_cap_is_spent(stage, capsys):
    fake, game, url = stage(extra={guard.MODERATION_ACTIONS_PER_USER_ENV: "0"})
    probe.main(_argv(url, "hold"))
    _quiet_output(capsys)
    assert fake.seen == []
    held = [item for item in game.calls if item["path"] in {"/speak", "/agent/voice"}]
    assert len(held) == 2
    assert all(item["status"] == 200 and item["response"] == moderation.HOLD_LINE
               and item["held"] is True and item["ai"] is False for item in held)
    ideas = next(item for item in game.calls if item["path"] == "/ideas/submit")
    profile = next(item for item in game.calls if item["path"] == "/profile/save")
    assert ideas["status"] == 422 and ideas["error"] == moderation.IDEAS_HOLD and ideas["held"] is True
    assert profile["status"] == 422 and profile["error"] == moderation.PROFILE_HOLD and profile["held"] is True
    with persistence._connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM community_ideas").fetchone()[0] == 0
        assert conn.execute(
            "SELECT COUNT(*) FROM model_spend_reservations WHERE task IN ('node', 'inhabitant', 'intent')"
        ).fetchone()[0] == 0


def test_hold_when_the_classifier_is_unreachable(stage, capsys):
    fake, game, url = stage(mode="down")
    probe.main(_argv(url, "hold"))
    _quiet_output(capsys)
    assert {item["model"] for item in fake.seen} == {"fixture-moderation"}
    assert all(item["path"] != "/speak" or item["response"] == moderation.HOLD_LINE for item in game.calls)
    rows = _rows()
    assert rows and {row[0] for row in rows} == {"moderation"}
    assert all(row[1] == "reserved" for row in rows)


def test_hold_when_the_dollar_ceiling_is_spent(stage, capsys):
    fake, game, url = stage(limits=("0.000001", "0.000001"))
    probe.main(_argv(url, "hold"))
    _quiet_output(capsys)
    assert fake.seen == []
    assert any(item["path"] == "/speak" and item["response"] == moderation.HOLD_LINE for item in game.calls)
    assert _rows() == []


def test_quiet_when_only_the_voice_cap_is_spent(stage, capsys):
    fake, game, url = stage(extra={guard.VOICE_CAP_ENV: "0"})
    probe.main(_argv(url, "quiet"))
    _quiet_output(capsys)
    voices = [item for item in game.calls if item["path"] in {"/speak", "/agent/voice"}]
    assert len(voices) == 2
    assert all(item["status"] == 200 and item["response"] == guard.QUIET_RESPONSE
               and item["ai"] is False and item["held"] is None for item in voices)
    assert {item["model"] for item in fake.seen} == {"fixture-moderation"}
    rows = _rows()
    assert [row[0] for row in rows] == ["moderation", "moderation"]
    assert {row[1] for row in rows} == {"settled"}
    assert all(row[3] <= row[2] for row in rows)


def test_identity_under_the_kill_switch(stage, capsys):
    fake, game, url = stage(extra={guard.DISABLE_AI_ENV: "1"})
    probe.main(_argv(url, "identity"))
    _quiet_output(capsys)
    assert fake.seen == []
    speak = next(item for item in game.calls if item["path"] == "/speak")
    agent = next(item for item in game.calls if item["path"] == "/agent/voice")
    assert speak["status"] == 200 and speak["ai"] is False
    assert speak["response"] == honesty.ROOT_PLACE_ANSWER
    assert agent["status"] == 200 and agent["ai"] is False
    assert agent["response"] == honesty.agent_answer(agent["persona"])
    assert _rows() == []


def test_non_temporary_world_is_refused_before_discovery(stage, capsys):
    _fake, game, url = stage(test_world="0")
    with pytest.raises(SystemExit) as caught:
        probe.main(_argv(url, "success"))
    assert caught.value.code == 1
    captured = _quiet_output(capsys)
    assert "not declared temporary" in captured.err
    assert {item["path"] for item in game.calls} == {"/participation"}
    assert all(item["keyed"] is False for item in game.calls)
    with persistence._connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM world_nodes").fetchone()[0] == 0


def test_controlled_direct_probe_stays_refused(tmp_path, monkeypatch, capsys):
    path = tmp_path / "policy.json"
    path.write_text(json.dumps({
        "schema_version": 1, "policy_id": "live-route-probe-fixture", "currency": "USD",
        "reset": "UTC",
        "routes": {task: {"enabled": False} for task in (*runtime.TASKS, "images")},
    }), encoding="utf-8")
    monkeypatch.setenv(model_policy.POLICY_ENV, str(path))
    from consciousness import model_check
    from main import main
    monkeypatch.setattr(model_check, "probe_distinct_models",
                        lambda *_args: pytest.fail("made a direct live probe"))
    for command in ("models", "voice-health"):
        with pytest.raises(SystemExit, match="controlled direct probes are unavailable"):
            main([command, "--probe"])
    capsys.readouterr()


def test_ledger_checks_reject_an_unsettled_or_incomplete_row():
    approved = json.dumps({"routes": {"node": {"resolved_models": ["fixture-node-v1"]}}})

    def row(**overrides):
        body = {
            "task": "node", "status": "settled", "reserved_microusd": 10,
            "accounted_microusd": 4, "resolved_model": "fixture-node-v1",
            "policy_json": approved,
            "usage_json": json.dumps({
                "input_tokens": 9, "output_tokens": 2, "cache_read_tokens": 1,
            }),
        }
        body.update(overrides)
        return body

    probe._assert_settled(row())
    with pytest.raises(probe.ProbeError, match="failed ADR-035 requirement 4"):
        probe._assert_settled(row(status="uncertain"))
    with pytest.raises(probe.ProbeError, match="accounted microUSD"):
        probe._assert_settled(row(accounted_microusd=11))
    with pytest.raises(probe.ProbeError, match="cached-token"):
        probe._assert_settled(row(usage_json=json.dumps({"input_tokens": 9, "output_tokens": 2})))
    with pytest.raises(probe.ProbeError, match="resolved_models"):
        probe._assert_settled(row(resolved_model="unapproved-model"))


def test_success_and_quiet_require_the_ledger(stage, capsys):
    _fake, _game, url = stage()
    with pytest.raises(SystemExit) as caught:
        probe.main(_argv(url, "success", db=False))
    assert caught.value.code == 1
    captured = _quiet_output(capsys)
    assert "needs --db" in captured.err
    with persistence._connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM world_nodes").fetchone()[0] == 0
