"""Provider-neutral eval harness. Fixtures and loopback only; no live spend."""
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import socket
import subprocess
import sys
import threading

import pytest

from consciousness import runtime
from consciousness.openai_compat_provider import API_KEY_ENV, BASE_URL_ENV, STRUCTURED_OUTPUTS_ENV
from consciousness.runtime import Completion, TokenUsage
from evals.harness import (
    ROOT, load_corpus, open_live_provider, provider_key, read_json, run,
    validate_candidate, write_json,
)
from server import guard


_KEY = "sk-eval-loopback-secret"


@pytest.fixture
def corpus():
    return load_corpus(ROOT / "evals/corpus.json")


@pytest.fixture
def candidate():
    return read_json(ROOT / "evals/candidates/fixture.json")


def live_config(candidate, provider):
    config = deepcopy(candidate)
    config.update(
        provider=provider, id=f"{provider}-harness-test",
        data_authorization="synthetic-only",
        terms_review="Synthetic test configuration; not real prices",
        timeout_seconds=10, max_retries=0,
        pricing={"fixture-v1": {
            "input_per_million": 1, "output_per_million": 2,
            "cache_read_per_million": .1, "cache_write_per_million": 1.25,
            "max_input_tokens": 1000, "source": "test-only", "verified_on": "2026-10-05",
        }},
    )
    return config


def selection_brief():
    return {
        "purpose": "test only", "owner": "test", "frozen_on": "2026-10-05",
        "minimum_repeats": 3, "calibration_record": None,
        "tasks": {task: {
            "min_cases": 1, "min_success_rate": .9, "max_success_rate_drop": 0,
            "max_p95_ms": 1000, "max_cost_per_success_usd": 1,
            "switch_metric": "cost", "minimum_gain": .1, "max_quality_drop": 0,
        } for task in ("node_voice", "inhabitant_voice", "intention", "moderation")},
    }


def one_case(corpus, case_id):
    selected = deepcopy(corpus)
    selected["cases"] = [next(c for c in corpus["cases"] if c["id"] == case_id)]
    return selected


def _register(monkeypatch, name, factory):
    registered = dict(runtime._REGISTERED)
    monkeypatch.setattr(runtime, "_REGISTERED", registered)
    runtime.register_provider(name, factory)


class _Probe:
    name = "eval_probe"

    def __init__(self, text, usage):
        self.text, self.usage, self.calls = text, usage, []

    def configured(self):
        return True

    def cache_reference_tokens(self, model):
        return None

    def generate(self, **kwargs):
        self.calls.append(kwargs["model"])
        return Completion(
            self.text, True, self.usage, "complete", "probe-echo", self.name,
        )


def test_registered_provider_is_selected_and_records_reported_usage(
        corpus, candidate, tmp_path, monkeypatch):
    from consciousness.anthropic_provider import AnthropicProvider
    usage = TokenUsage(10, 3, 20, 30)
    probe = _Probe(
        '{"status": "ready", "ambiguity": "none", "steps": [{"op": "attune", "amount": 1}]}',
        usage,
    )
    _register(monkeypatch, "eval_probe", lambda: probe)
    monkeypatch.setenv(runtime.PROVIDER_ENV, "anthropic")
    monkeypatch.setattr(AnthropicProvider, "_get_client", lambda *args: pytest.fail("anthropic client"))
    runtime.reset_provider_selection()
    selected = one_case(corpus, "intent-multiverse")
    result = run(
        selected, live_config(candidate, "eval_probe"), tmp_path / "run",
        live=True, max_usd=1, max_calls=4, brief=selection_brief(),
    )
    assert result["status"] == "completed"
    assert probe.calls == ["fixture-v1"]
    call = result["trials"][0]["calls"][0]
    assert call["provider"] == "eval_probe"
    assert call["model"] == "fixture-v1"
    assert call["resolved_model"] == "probe-echo"
    assert call["usage"] == {
        "input_tokens": 10, "output_tokens": 3,
        "cache_read_tokens": 20, "cache_write_tokens": 30,
    }
    assert call["response"]["provider"] == "eval_probe"
    assert call["cost_usd"] == pytest.approx((10 + 6 + 2 + 37.5) / 1_000_000)
    assert call["reserved_usd"] > call["cost_usd"]
    assert result["trials"][0]["grade"]["task_correct"] is True
    # The lookup does not become the process selection, and the env default
    # was not the adapter that ran.
    assert runtime._selected_provider is None
    assert provider_key(result["candidate"]) == "eval_probe"


def test_partial_usage_is_recorded_and_does_not_invent_a_cost(
        corpus, candidate, tmp_path, monkeypatch):
    probe = _Probe("The lantern holds.", TokenUsage(10, 3, None, None))
    _register(monkeypatch, "eval_probe", lambda: probe)
    selected = one_case(corpus, "voice-multiverse")
    selected["cases"][0]["messages"] = selected["cases"][0]["messages"][:1]
    selected["cases"][0]["fixture"] = selected["cases"][0]["fixture"][:1]
    result = run(
        selected, live_config(candidate, "eval_probe"), tmp_path / "run",
        live=True, max_usd=1, max_calls=4, brief=selection_brief(),
    )
    call = result["trials"][0]["calls"][0]
    assert call["usage"]["input_tokens"] == 10
    assert call["usage"]["output_tokens"] == 3
    assert call["usage"]["cache_read_tokens"] is None
    assert call["usage"]["cache_write_tokens"] is None
    assert call["cost_usd"] is None
    assert call["reserved_usd"] > 0
    # The unknown counts keep the whole reserve. Nothing is priced as zero.
    assert result["budget"]["accounted_usd"] == pytest.approx(call["reserved_usd"])
    assert result["trials"][0]["grade"]["outcome"] == "awaiting_human"


def test_unknown_provider_is_refused_before_any_output(corpus, candidate, tmp_path):
    config = live_config(candidate, "unsupported")
    with pytest.raises(ValueError, match="no evaluated adapter"):
        validate_candidate(config, live=True)
    secret = "sk-secret-value-not-a-name"
    config["provider"] = secret
    with pytest.raises(ValueError, match="no evaluated adapter") as caught:
        run(one_case(corpus, "intent-multiverse"), config, tmp_path / "run",
            live=True, max_usd=1, max_calls=1, brief=selection_brief())
    assert secret not in str(caught.value)
    assert not (tmp_path / "run").exists()


@pytest.mark.parametrize("max_usd,max_calls", [(None, 10), (1, None), (None, None)])
def test_live_run_refuses_a_missing_spend_ceiling(
        corpus, candidate, tmp_path, monkeypatch, max_usd, max_calls):
    built = []

    def refuse_build(name):
        built.append(name)
        raise AssertionError(name)

    class RefuseAnthropic:
        def __init__(self):
            built.append("anthropic")
            raise AssertionError("anthropic")

    monkeypatch.setattr(runtime, "build_provider", refuse_build)
    from consciousness import anthropic_provider
    monkeypatch.setattr(anthropic_provider, "AnthropicProvider", RefuseAnthropic)
    config = live_config(candidate, "openai_compatible")
    with pytest.raises(ValueError, match="explicit spend ceiling"):
        run(one_case(corpus, "intent-multiverse"), config, tmp_path / "run",
            live=True, max_usd=max_usd, max_calls=max_calls, brief=selection_brief())
    assert built == []
    assert not (tmp_path / "run").exists()


def test_cli_live_without_a_ceiling_exits_before_dispatch(candidate, tmp_path):
    config_path = tmp_path / "candidate.json"
    write_json(config_path, live_config(candidate, "openai_compatible"))
    target = tmp_path / "live"
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts/model_eval.py"), "run", "--live",
         "--candidate", str(config_path), "--output", str(target),
         "--task", "intention", "--repeats", "1"],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert completed.returncode == 2, completed.stderr
    assert "explicit spend ceiling" in completed.stderr
    assert not target.exists()


def test_fixture_run_does_not_build_a_registered_adapter(corpus, candidate, tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, "build_provider", lambda name: pytest.fail(name))
    result = run(one_case(corpus, "intent-multiverse"), candidate, tmp_path / "run")
    assert result["status"] == "completed"
    assert result["evidence"] == "fixture"
    call = result["trials"][0]["calls"][0]
    assert call["provider"] == "fixture"
    assert call["cost_usd"] == 0.0
    assert call["model"] == "fixture-v1"


def test_anthropic_live_still_requires_the_reviewed_destination(
        corpus, candidate, tmp_path, monkeypatch):
    from consciousness.anthropic_provider import AnthropicProvider

    class FakeClient:
        def __init__(self, base_url):
            self.base_url = base_url
            self.api_key = None
            self.auth_token = None
            self.credentials = None
            self.options = None

        def with_options(self, **kwargs):
            self.options = kwargs
            return self

    client = FakeClient("https://example.invalid")
    monkeypatch.setattr(AnthropicProvider, "_get_client", lambda self: client)
    config = live_config(candidate, "anthropic")
    with pytest.raises(ValueError, match="reviewed direct Anthropic"):
        run(one_case(corpus, "intent-multiverse"), config, tmp_path / "other",
            live=True, max_usd=1, max_calls=1, brief=selection_brief())
    assert not (tmp_path / "other").exists()

    client.base_url = "https://api.anthropic.com/"
    with pytest.raises(ValueError, match="unconfigured"):
        open_live_provider(config)
    assert client.options == {"max_retries": 0, "timeout": 10}


def test_openai_compatible_live_refuses_without_an_operator_url(
        corpus, candidate, tmp_path, monkeypatch):
    monkeypatch.delenv(BASE_URL_ENV, raising=False)
    monkeypatch.delenv(API_KEY_ENV, raising=False)
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("OPENAI_API_KEY", _KEY)
    config = live_config(candidate, "openai_compatible")
    with pytest.raises(ValueError, match="unconfigured"):
        run(one_case(corpus, "intent-multiverse"), config, tmp_path / "run",
            live=True, max_usd=1, max_calls=1, brief=selection_brief())
    assert not (tmp_path / "run").exists()


def _chat_body(content, usage, model="echo-loopback"):
    return json.dumps({
        "model": model,
        "choices": [{
            "index": 0, "finish_reason": "stop",
            "message": {"role": "assistant", "content": content, "refusal": None},
        }],
        "usage": usage,
    }).encode()


class _Server(ThreadingHTTPServer):
    daemon_threads = True


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        return

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length) if length else b""
        self.server.seen.append({
            "path": self.path,
            "authorization": self.headers.get("Authorization"),
            "body": body,
            "reserves": len(self.server.reserves),
            "charged": list(self.server.charged),
        })
        payload = _chat_body(self.server.reply, self.server.usage, self.server.echo)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def _start_loopback():
    try:
        server = _Server(("127.0.0.1", 0), _Handler)
    except OSError as exc:
        pytest.skip(f"loopback bind unavailable ({type(exc).__name__})")
    server.seen = []
    server.reserves = []
    server.charged = []
    server.reply = "The lantern holds."
    server.echo = "echo-loopback"
    server.usage = {
        "prompt_tokens": 100,
        "total_tokens": 110,
        "prompt_tokens_details": {"cached_tokens": 40, "cache_write_tokens": 10},
    }
    server._accepting = threading.Event()
    real_serve = server.serve_forever

    def serve():
        server._accepting.set()
        real_serve()

    thread = threading.Thread(target=serve, daemon=True)
    server._thread = thread
    thread.start()
    if not server._accepting.wait(2):
        _stop_loopback(server)
        pytest.fail("loopback accept thread did not start")
    deadline = threading.Event()
    connected = False
    for _ in range(50):
        try:
            probe = socket.create_connection(server.server_address, timeout=0.2)
        except OSError:
            deadline.wait(0.02)
            continue
        probe.close()
        connected = True
        break
    if not connected:
        _stop_loopback(server)
        pytest.fail("loopback port did not accept")
    return server


def _stop_loopback(server):
    accepting = getattr(server, "_accepting", None)
    if accepting is not None and accepting.is_set():
        server.shutdown()
    server.server_close()
    thread = getattr(server, "_thread", None)
    if thread is not None:
        thread.join(2)


@pytest.fixture
def loopback():
    server = _start_loopback()
    try:
        yield server
    finally:
        _stop_loopback(server)


def _arm_loopback(monkeypatch, server):
    port = server.server_address[1]
    monkeypatch.setenv(runtime.PROVIDER_ENV, "anthropic")
    monkeypatch.setenv(BASE_URL_ENV, f"http://127.0.0.1:{port}/v1")
    monkeypatch.setenv(API_KEY_ENV, _KEY)
    monkeypatch.delenv(STRUCTURED_OUTPUTS_ENV, raising=False)
    monkeypatch.setenv("NESTED_WORLDS_OPENAI_COMPATIBLE_TIMEOUT_SECONDS", "5")
    for name in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "XAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    from evals.harness import Meter
    original = Meter.reserve

    def counting(self, request):
        amount = original(self, request)
        server.reserves.append(amount)
        return amount

    monkeypatch.setattr(Meter, "reserve", counting)
    monkeypatch.setattr(
        guard, "consume_model_action",
        lambda **kwargs: server.charged.append("model") or True,
    )
    monkeypatch.setattr(
        guard, "consume_anthropic",
        lambda **kwargs: server.charged.append("voice") or True,
    )


def test_openai_compatible_loopback_records_usage_and_priced_cost(
        corpus, candidate, tmp_path, monkeypatch, loopback):
    _arm_loopback(monkeypatch, loopback)
    selected = one_case(corpus, "voice-multiverse")
    selected["cases"][0]["messages"] = selected["cases"][0]["messages"][:1]
    selected["cases"][0]["fixture"] = selected["cases"][0]["fixture"][:1]
    result = run(
        selected, live_config(candidate, "openai_compatible"), tmp_path / "run",
        live=True, max_usd=1, max_calls=4, brief=selection_brief(),
    )
    assert result["status"] == "completed"
    assert len(loopback.seen) == 1
    seen = loopback.seen[0]
    assert seen["path"] == "/v1/chat/completions"
    assert seen["authorization"] == f"Bearer {_KEY}"
    assert seen["reserves"] == 1
    assert seen["charged"] == ["model"]
    sent = json.loads(seen["body"])
    assert sent["model"] == "fixture-v1"
    assert "127.0.0.1" not in json.dumps(result)
    assert _KEY not in json.dumps(result)
    call = result["trials"][0]["calls"][0]
    assert call["provider"] == "openai_compatible"
    assert call["model"] == "fixture-v1"
    assert call["resolved_model"] == "echo-loopback"
    assert call["usage"] == {
        "input_tokens": 50, "output_tokens": 10,
        "cache_read_tokens": 40, "cache_write_tokens": 10,
    }
    # 50*1 + 10*2 + 40*0.1 + 10*1.25, per million.
    assert call["cost_usd"] == pytest.approx(86.5 / 1_000_000)
    assert call["response"]["provider"] == "openai_compatible"
    assert "voice" not in loopback.charged


def test_openai_compatible_loopback_keeps_unknown_usage_unpriced(
        corpus, candidate, tmp_path, monkeypatch, loopback):
    loopback.usage = {"prompt_tokens": 100, "total_tokens": 110}
    _arm_loopback(monkeypatch, loopback)
    selected = one_case(corpus, "voice-multiverse")
    selected["cases"][0]["messages"] = selected["cases"][0]["messages"][:1]
    selected["cases"][0]["fixture"] = selected["cases"][0]["fixture"][:1]
    result = run(
        selected, live_config(candidate, "openai_compatible"), tmp_path / "run",
        live=True, max_usd=1, max_calls=4, brief=selection_brief(),
    )
    call = result["trials"][0]["calls"][0]
    assert call["usage"]["input_tokens"] is None
    assert call["usage"]["output_tokens"] == 10
    assert call["usage"]["cache_read_tokens"] is None
    assert call["usage"]["cache_write_tokens"] is None
    assert call["cost_usd"] is None
    assert result["budget"]["accounted_usd"] == pytest.approx(call["reserved_usd"])
    assert 0 not in (
        call["usage"]["input_tokens"], call["usage"]["cache_read_tokens"],
        call["usage"]["cache_write_tokens"],
    )


def test_schema_off_intention_sends_nothing_and_charges_nothing(
        corpus, candidate, tmp_path, monkeypatch, loopback):
    _arm_loopback(monkeypatch, loopback)
    before = len(loopback.seen)
    result = run(
        one_case(corpus, "intent-multiverse"),
        live_config(candidate, "openai_compatible"), tmp_path / "run",
        live=True, max_usd=1, max_calls=4, brief=selection_brief(),
    )
    assert len(loopback.seen) == before
    assert loopback.charged == []
    assert loopback.reserves == []
    assert result["budget"]["dispatched_calls"] == 0
    assert result["budget"]["accounted_usd"] == 0
    trial = result["trials"][0]
    assert trial["error"] == "UnsupportedCapability"
    assert trial["calls"] == []
    assert trial["grade"]["task_correct"] is None
    assert _KEY not in json.dumps(result)
