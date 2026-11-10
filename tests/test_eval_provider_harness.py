"""Provider-neutral eval harness. Fixtures and loopback only; no live spend."""
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import socket
import subprocess
import sys
import threading
import time

import pytest

from consciousness import runtime
from consciousness.openai_compat_provider import (
    API_KEY_ENV, BASE_URL_ENV, MAX_OUTPUT_PARAM_ENV, REASONING_EFFORT_ENV,
    SEND_STORE_FALSE_ENV, STRUCTURED_OUTPUTS_ENV,
)
from consciousness.runtime import Completion, SystemBlock, TokenUsage
from evals.harness import (
    ROOT, Meter, RecordingProvider, adapter_settings, approve_destination,
    load_corpus, open_live_provider, provider_key, read_json, run,
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
    destination_host = "eval-probe.invalid"

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
        allow_destination="eval-probe.invalid",
    )
    assert result["status"] == "completed"
    assert result["destination_host"] == "eval-probe.invalid"
    assert result["provenance"]["destination_host"] == "eval-probe.invalid"
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
    # was not the adapter that ran. A task with no provider override still
    # asks get_provider, which this test replaces, so the process name stays
    # unset.
    assert runtime._process_name is None
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
        allow_destination="eval-probe.invalid",
    )
    call = result["trials"][0]["calls"][0]
    assert call["usage"]["input_tokens"] == 10
    assert call["usage"]["output_tokens"] == 3
    assert call["usage"]["cache_read_tokens"] is None
    assert call["usage"]["cache_write_tokens"] is None
    assert call["cost_usd"] is None
    assert call["reserved_usd"] > 0
    # The known floor is below the reserve, so the unknown counts keep the
    # whole reserve. Nothing is priced as zero.
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


class _Leaky:
    name = "leaky_override"

    def __init__(self):
        self.calls = []

    def configured(self):
        return True

    def default_model(self, task):
        return "leaky-model"

    def generate(self, **kwargs):
        self.calls.append(kwargs.get("model"))
        raise AssertionError("task provider escaped the harness")


def _precache_task_overrides(monkeypatch):
    leaky = _Leaky()
    _register(monkeypatch, leaky.name, lambda: leaky)
    for env in runtime.TASK_PROVIDER_ENVS:
        monkeypatch.setenv(env, leaky.name)
    runtime.reset_provider_selection()
    for task in runtime.TASKS:
        assert runtime.provider_for(task) is leaky
    return leaky


def test_fixture_run_ignores_task_provider_overrides_even_when_cached(
        corpus, candidate, tmp_path, monkeypatch):
    leaky = _precache_task_overrides(monkeypatch)
    result = run(one_case(corpus, "intent-multiverse"), candidate, tmp_path / "run")
    trial = result["trials"][0]
    assert result["status"] == "completed"
    assert result["evidence"] == "fixture"
    assert trial["error"] is None
    assert trial["calls"]
    assert trial["calls"][0]["provider"] == "fixture"
    assert result["budget"]["dispatched_calls"] >= 1
    assert result["budget"]["accounted_usd"] == 0
    assert leaky.calls == []
    assert os.environ[runtime.INTENT_PROVIDER_ENV] == leaky.name
    assert runtime.provider_for(runtime.INTENT_TASK) is leaky
    assert runtime._process_name is None


def test_live_loopback_ignores_task_provider_overrides_even_when_cached(
        corpus, candidate, tmp_path, monkeypatch, loopback):
    _arm_loopback(monkeypatch, loopback)
    leaky = _precache_task_overrides(monkeypatch)
    selected = one_case(corpus, "voice-multiverse")
    selected["cases"][0]["messages"] = selected["cases"][0]["messages"][:1]
    selected["cases"][0]["fixture"] = selected["cases"][0]["fixture"][:1]
    result = run(
        selected, live_config(candidate, "openai_compatible"), tmp_path / "run",
        live=True, max_usd=1, max_calls=4, brief=selection_brief(),
        allow_destination="127.0.0.1",
    )
    trial = result["trials"][0]
    assert result["status"] == "completed"
    assert trial["error"] is None
    assert len(loopback.seen) == 1
    assert loopback.seen[0]["reserves"] == 1
    assert result["destination_host"] == "127.0.0.1"
    assert result["budget"]["dispatched_calls"] >= 1
    assert leaky.calls == []
    assert os.environ[runtime.NODE_PROVIDER_ENV] == leaky.name
    assert runtime.provider_for(runtime.NODE_TASK) is leaky


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
    with pytest.raises(ValueError, match="must be api.anthropic.com"):
        open_live_provider(config, "evil.com")
    for flag in ("API.ANTHROPIC.COM", "api.anthropic.com.evil.com", "xapi.anthropic.com"):
        with pytest.raises(ValueError, match="must be api.anthropic.com"):
            open_live_provider(config, flag)
    monkeypatch.setattr(AnthropicProvider, "configured", lambda self: True)
    provider, host = open_live_provider(config, "api.anthropic.com")
    assert host == "api.anthropic.com"
    assert provider.name == "anthropic"
    recorded = adapter_settings(provider, config)
    assert recorded["timeout_seconds"] == 10
    assert recorded["max_output_param"] == "max_tokens"
    assert recorded["structured_outputs"] is True
    assert "api.anthropic.com/" not in json.dumps(recorded)


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
        delay = getattr(self.server, "delay", 0) or 0
        if delay:
            time.sleep(delay)
        status = getattr(self.server, "status_code", 200)
        if status == 200:
            payload = _chat_body(self.server.reply, self.server.usage, self.server.echo)
        else:
            payload = getattr(self.server, "error_body", b"")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return


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
    server.delay = 0
    server.status_code = 200
    server.error_body = b""
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
    monkeypatch.delenv(SEND_STORE_FALSE_ENV, raising=False)
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
        allow_destination="127.0.0.1",
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
    port = loopback.server_address[1]
    blob = json.dumps(result)
    assert result["destination_host"] == "127.0.0.1"
    assert result["provenance"]["destination_host"] == "127.0.0.1"
    assert f"127.0.0.1:{port}" not in blob
    assert "http://127.0.0.1" not in blob
    assert _KEY not in blob
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
    # The ephemeral port is covered by the host approval and is not recorded.
    settings = result["adapter_settings"]
    assert settings["timeout_seconds"] == 10
    assert settings["max_output_param"] == "max_completion_tokens"
    assert settings["structured_outputs"] is False
    assert settings["reasoning_effort"] is None
    assert settings["send_store_false"] is False
    assert settings == result["provenance"]["adapter_settings"]
    assert call["adapter_settings"]["timeout_seconds"] == 10
    assert call["adapter_settings"]["send_store_false"] is False
    assert result["budget"]["cache_writes_bounded"] is True
    assert result["provenance"]["cache_writes_bounded"] is True
    assert _KEY not in json.dumps(settings)
    assert "http://" not in json.dumps(settings)


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
        allow_destination="127.0.0.1",
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
        allow_destination="127.0.0.1",
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


def _voice(corpus):
    selected = one_case(corpus, "voice-multiverse")
    selected["cases"][0]["messages"] = selected["cases"][0]["messages"][:1]
    selected["cases"][0]["fixture"] = selected["cases"][0]["fixture"][:1]
    return selected


def _output_text(path):
    return "\n".join(
        item.read_text(encoding="utf-8", errors="replace")
        for item in path.rglob("*") if item.is_file()
    )


def test_settle_counts_a_known_floor_before_leaving_the_cost_unknown(candidate):
    config = live_config(candidate, "anthropic")
    meter = Meter(config, max_usd=1, max_calls=4)
    request = {"model": "fixture-v1", "max_tokens": 256}
    reservation = meter.reserve(request)
    completion = Completion("x", True, TokenUsage(100, 50000, 0, None), "stop", "m", "anthropic")
    cost = meter.settle(reservation, request, completion)
    floor = (100 * 1 + 50000 * 2) / 1_000_000
    assert cost is None
    assert meter.halted is True
    assert floor > reservation
    assert meter.accounted == pytest.approx(floor)


def test_openai_compatible_loopback_halts_when_the_known_floor_exceeds_the_ceiling(
        corpus, candidate, tmp_path, monkeypatch, loopback):
    # OpenAI/xAI shape: cache_write_tokens is absent. prompt 100, total
    # 50100, cached 0. At the test rates the known floor is $0.1001. Five
    # reserves of the 256-token voice bound are $0.00881, which fits under
    # --max-usd 0.01, and five true calls would be about $0.5005.
    loopback.usage = {
        "prompt_tokens": 100,
        "total_tokens": 50100,
        "prompt_tokens_details": {"cached_tokens": 0},
    }
    _arm_loopback(monkeypatch, loopback)
    result = run(
        _voice(corpus), live_config(candidate, "openai_compatible"), tmp_path / "run",
        repeats=5, live=True, max_usd=0.01, max_calls=10, brief=selection_brief(),
        allow_destination="127.0.0.1",
    )
    floor = (100 * 1 + 50000 * 2) / 1_000_000
    assert result["status"] == "pricing_bound_exceeded"
    assert result["planned_trials"] == 5
    assert len(result["trials"]) == 1
    assert len(loopback.seen) == 1
    assert result["budget"]["dispatched_calls"] == 1
    call = result["trials"][0]["calls"][0]
    assert call["usage"]["cache_write_tokens"] is None
    assert call["usage"]["output_tokens"] == 50000
    assert call["cost_usd"] is None
    assert call["reserved_usd"] < 0.01
    assert result["budget"]["accounted_usd"] == pytest.approx(floor)
    assert result["budget"]["accounted_usd"] > result["budget"]["max_usd"]


@pytest.mark.parametrize("flag", [None, "", "   "])
def test_non_anthropic_live_refuses_without_allow_destination(
        corpus, candidate, tmp_path, monkeypatch, loopback, flag):
    _arm_loopback(monkeypatch, loopback)
    monkeypatch.setenv("NESTED_WORLDS_EVAL_ALLOW_DESTINATION", "127.0.0.1")
    kwargs = {} if flag is None else {"allow_destination": flag}
    with pytest.raises(ValueError, match="allow-destination"):
        run(
            _voice(corpus), live_config(candidate, "openai_compatible"), tmp_path / "run",
            live=True, max_usd=1, max_calls=4, brief=selection_brief(), **kwargs,
        )
    assert loopback.seen == []
    assert not (tmp_path / "run").exists()


@pytest.mark.parametrize("host", [
    "localhost", "*", "http://127.0.0.1", "127.0.0.1:9", "0.0.1", "127.0.0.",
    "127.0.0.1.",
])
def test_non_anthropic_live_refuses_a_destination_that_does_not_match(
        corpus, candidate, tmp_path, monkeypatch, loopback, host):
    _arm_loopback(monkeypatch, loopback)
    with pytest.raises(ValueError, match="allow-destination") as caught:
        run(
            _voice(corpus), live_config(candidate, "openai_compatible"), tmp_path / "run",
            live=True, max_usd=1, max_calls=4, brief=selection_brief(),
            allow_destination=host,
        )
    assert "http://127.0.0.1" not in str(caught.value)
    assert _KEY not in str(caught.value)
    assert loopback.seen == []
    assert not (tmp_path / "run").exists()


def test_non_anthropic_live_without_a_resolved_host_is_refused(
        corpus, candidate, tmp_path, monkeypatch):
    class Bare:
        name = "eval_probe"

        def configured(self):
            return True

        def cache_reference_tokens(self, model):
            return None

        def generate(self, **kwargs):
            raise AssertionError("sent")

    _register(monkeypatch, "eval_probe", lambda: Bare())
    with pytest.raises(ValueError, match="no resolved destination host"):
        run(
            _voice(corpus), live_config(candidate, "eval_probe"), tmp_path / "run",
            live=True, max_usd=1, max_calls=4, brief=selection_brief(),
            allow_destination="eval-probe.invalid",
        )
    assert not (tmp_path / "run").exists()


def test_live_timeout_fills_only_when_the_caller_omits_one(candidate):
    class Probe:
        name = "eval_probe"

        def __init__(self):
            self.timeouts = []

        def configured(self):
            return True

        def cache_reference_tokens(self, model):
            return None

        def generate(self, **kwargs):
            self.timeouts.append(kwargs.get("timeout"))
            return Completion("ok", True, TokenUsage(1, 1, 0, 0), "stop", "m", self.name)

    probe = Probe()
    config = live_config(candidate, "eval_probe")
    config["timeout_seconds"] = 1
    meter = Meter(config, 1, 4)
    recording = RecordingProvider(probe, [], meter)
    common = dict(model="fixture-v1", system=(SystemBlock("s"),), messages=[], max_tokens=16)
    recording.generate(**common, timeout=3.0)
    recording.generate(**common)
    assert probe.timeouts == [3.0, 1]


def test_openai_compatible_loopback_honors_timeout_seconds(
        corpus, candidate, tmp_path, monkeypatch, loopback):
    loopback.delay = 3
    _arm_loopback(monkeypatch, loopback)
    monkeypatch.setenv("NESTED_WORLDS_OPENAI_COMPATIBLE_TIMEOUT_SECONDS", "30")
    config = live_config(candidate, "openai_compatible")
    config["timeout_seconds"] = 1
    result = run(
        _voice(corpus), config, tmp_path / "run",
        live=True, max_usd=1, max_calls=4, brief=selection_brief(),
        allow_destination="127.0.0.1",
    )
    assert len(loopback.seen) == 1
    trial = result["trials"][0]
    call = trial["calls"][0]
    assert trial["error"] == "ProviderTimeout"
    assert call["error"] == "ProviderTimeout"
    assert call["request"]["timeout"] == 1
    # The server waits 3s. The candidate bound is 1s, so the trial ends
    # before that wait. The adapter's own 30s setting must not win.
    assert trial["latency_ms"] < 2500


def test_provider_error_keeps_the_reserve(
        corpus, candidate, tmp_path, monkeypatch, loopback):
    loopback.status_code = 500
    loopback.error_body = b"upstream failed"
    _arm_loopback(monkeypatch, loopback)
    result = run(
        _voice(corpus), live_config(candidate, "openai_compatible"), tmp_path / "run",
        live=True, max_usd=1, max_calls=4, brief=selection_brief(),
        allow_destination="127.0.0.1",
    )
    assert len(loopback.seen) == 1
    call = result["trials"][0]["calls"][0]
    assert call["error"] == "ProviderHTTPError"
    assert call["cost_usd"] is None
    assert call["reserved_usd"] > 0
    assert result["budget"]["accounted_usd"] == pytest.approx(call["reserved_usd"])
    assert result["budget"]["dispatched_calls"] == 1


def test_provider_error_body_does_not_enter_the_result(
        corpus, candidate, tmp_path, monkeypatch, loopback):
    loopback.status_code = 500
    loopback.error_body = f"upstream leaked {_KEY}".encode()
    _arm_loopback(monkeypatch, loopback)
    result = run(
        _voice(corpus), live_config(candidate, "openai_compatible"), tmp_path / "run",
        live=True, max_usd=1, max_calls=4, brief=selection_brief(),
        allow_destination="127.0.0.1",
    )
    call = result["trials"][0]["calls"][0]
    assert call["error"] == "ProviderHTTPError"
    assert _KEY not in call["error"]
    blob = json.dumps(result)
    assert _KEY not in blob
    assert _KEY not in _output_text(tmp_path / "run")


def test_build_provider_does_not_echo_an_unknown_name():
    for name in ("not-a-name", "sk-secret-value-not-a-name", " Fixture "):
        with pytest.raises(ValueError) as caught:
            runtime.build_provider(name)
        assert str(caught.value) == "provider has no evaluated adapter; no implicit fallback"
        assert name not in str(caught.value)


def test_validate_candidate_uses_the_normalized_provider_name(candidate):
    offline = deepcopy(candidate)
    offline["provider"] = " Fixture "
    validate_candidate(offline, live=False)
    validate_candidate(live_config(candidate, " Anthropic "), live=True)


def test_price_map_miss_does_not_invent_a_cost(candidate):
    config = live_config(candidate, "anthropic")
    meter = Meter(config, max_usd=1, max_calls=4)
    reservation = 0.01
    meter.accounted = reservation
    meter.calls = 1
    completion = Completion("x", True, TokenUsage(10, 4, 0, 0), "stop", "m", "anthropic")
    cost = meter.settle(reservation, {"model": "not-priced", "max_tokens": 16}, completion)
    assert cost is None
    assert meter.accounted == reservation
    assert meter.halted is False


def test_cache_write_key_is_required_and_anthropic_null_is_not_a_bound(candidate):
    for name in ("anthropic", "openai_compatible"):
        missing = live_config(candidate, name)
        del missing["pricing"]["fixture-v1"]["cache_write_per_million"]
        with pytest.raises(ValueError, match="must be present"):
            validate_candidate(missing, live=True)
    anthropic = live_config(candidate, "anthropic")
    anthropic["pricing"]["fixture-v1"]["cache_write_per_million"] = None
    with pytest.raises(ValueError, match="not a bound"):
        validate_candidate(anthropic, live=True)
    for write in (0, 0.0):
        config = live_config(candidate, "anthropic")
        config["pricing"]["fixture-v1"]["cache_write_per_million"] = write
        with pytest.raises(ValueError, match="finite positive"):
            validate_candidate(config, live=True)
    validate_candidate(live_config(candidate, "anthropic"), live=True)
    compatible = live_config(candidate, "openai_compatible")
    compatible["pricing"]["fixture-v1"]["cache_write_per_million"] = None
    validate_candidate(compatible, live=True)
    missing_source = live_config(candidate, "openai_compatible")
    missing_source["pricing"]["fixture-v1"]["cache_write_per_million"] = None
    missing_source["pricing"]["fixture-v1"]["source"] = ""
    with pytest.raises(ValueError, match="dated official"):
        validate_candidate(missing_source, live=True)
    negative = live_config(candidate, "anthropic")
    negative["pricing"]["fixture-v1"]["cache_write_per_million"] = -1
    with pytest.raises(ValueError, match="cache_write_per_million"):
        validate_candidate(negative, live=True)

    priced = live_config(candidate, "openai_compatible")
    priced["pricing"]["fixture-v1"]["cache_write_per_million"] = 0
    validate_candidate(priced, live=True)
    meter = Meter(priced, 1, 4)
    request = {"model": "fixture-v1", "max_tokens": 16}
    reservation = meter.reserve(request)
    completion = Completion("x", True, TokenUsage(10, 3, 0, 10), "stop", "m", "anthropic")
    assert meter.settle(reservation, request, completion) == pytest.approx((10 + 6) / 1_000_000)

    # An unreported write count at an explicit zero is priced at zero.
    meter = Meter(priced, 1, 4)
    reservation = meter.reserve(request)
    unreported = Completion("x", True, TokenUsage(10, 3, 0, None), "stop", "m", "anthropic")
    assert meter.settle(reservation, request, unreported) == pytest.approx((10 + 6) / 1_000_000)
    assert meter.halted is False

    # Zero writes at a null rate are priced. Positive writes halt.
    unpriced = live_config(candidate, "openai_compatible")
    unpriced["pricing"]["fixture-v1"]["cache_write_per_million"] = None
    meter = Meter(unpriced, 1, 4)
    reservation = meter.reserve(request)
    zero_writes = Completion("x", True, TokenUsage(10, 3, 0, 0), "stop", "m", "openai_compatible")
    assert meter.settle(reservation, request, zero_writes) == pytest.approx((10 + 6) / 1_000_000)
    assert meter.halted is False
    meter = Meter(unpriced, 1, 4)
    reservation = meter.reserve(request)
    # 1000 input tokens at the $1 rate; the null write rate is left out. Plus 16 * $2.
    assert reservation == pytest.approx((1000 + 32) / 1_000_000)
    held = meter.accounted
    writes = Completion("x", True, TokenUsage(10, 3, 0, 1000), "stop", "m", "openai_compatible")
    assert meter.settle(reservation, request, writes) is None
    assert meter.halted is True
    assert meter.accounted == pytest.approx(held)


def test_allow_destination_match_is_exact_and_case_sensitive():
    approve_destination("127.0.0.1", "127.0.0.1")
    approve_destination("api.example.com", "api.example.com")
    for host, flag in (
        ("127.0.0.1", "0.0.1"),
        ("127.0.0.1", "127.0.0."),
        ("api.example.com", "example.com"),
        ("api.example.com", "API.EXAMPLE.COM"),
        ("api.example.com", "api.example.com."),
        ("api.example.com.", "api.example.com"),
        ("api.example.com", "api.example.com.evil"),
    ):
        with pytest.raises(ValueError, match="allow-destination"):
            approve_destination(host, flag)


def test_settle_does_not_halt_when_the_floor_equals_the_reserve(candidate):
    config = live_config(candidate, "anthropic")
    meter = Meter(config, max_usd=1, max_calls=2)
    request = {"model": "fixture-v1", "max_tokens": 256}
    reservation = meter.reserve(request)
    # 1000 cache writes at $1.25 and 256 output tokens at $2 equal the reserve.
    completion = Completion("x", True, TokenUsage(0, 256, 0, 1000), "stop", "m", "anthropic")
    cost = meter.settle(reservation, request, completion)
    assert cost == reservation
    assert meter.halted is False
    assert meter.accounted == pytest.approx(cost)


def test_openai_compatible_loopback_halts_on_positive_writes_at_a_null_rate(
        corpus, candidate, tmp_path, monkeypatch, loopback):
    loopback.usage = {
        "prompt_tokens": 1000,
        "total_tokens": 1010,
        "prompt_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 1000},
    }
    _arm_loopback(monkeypatch, loopback)
    config = live_config(candidate, "openai_compatible")
    config["pricing"]["fixture-v1"]["cache_write_per_million"] = None
    result = run(
        _voice(corpus), config, tmp_path / "run",
        repeats=3, live=True, max_usd=1, max_calls=10, brief=selection_brief(),
        allow_destination="127.0.0.1",
    )
    assert result["status"] == "pricing_bound_exceeded"
    assert len(loopback.seen) == 1
    call = result["trials"][0]["calls"][0]
    assert call["usage"]["cache_write_tokens"] == 1000
    assert call["cost_usd"] is None
    # Input rate only: the null write rate was not in the reserve.
    assert call["reserved_usd"] == pytest.approx((1000 + 512) / 1_000_000)
    assert result["budget"]["cache_writes_bounded"] is False
    assert result["provenance"]["cache_writes_bounded"] is False


def test_explicit_zero_write_rate_prices_openai_shaped_usage(
        corpus, candidate, tmp_path, monkeypatch, loopback):
    loopback.usage = {
        "prompt_tokens": 100,
        "total_tokens": 110,
        "prompt_tokens_details": {"cached_tokens": 0},
    }
    _arm_loopback(monkeypatch, loopback)
    config = live_config(candidate, "openai_compatible")
    config["pricing"]["fixture-v1"]["cache_write_per_million"] = 0
    result = run(
        _voice(corpus), config, tmp_path / "run",
        live=True, max_usd=1, max_calls=4, brief=selection_brief(),
        allow_destination="127.0.0.1",
    )
    call = result["trials"][0]["calls"][0]
    assert call["usage"]["cache_write_tokens"] is None
    assert call["usage"]["input_tokens"] == 100
    assert call["usage"]["output_tokens"] == 10
    assert call["cost_usd"] == pytest.approx((100 + 20) / 1_000_000)
    assert result["status"] == "completed"
    assert result["budget"]["cache_writes_bounded"] is True
    assert result["provenance"]["cache_writes_bounded"] is True


def test_null_write_rate_with_no_write_count_is_flagged_unbounded(
        corpus, candidate, tmp_path, monkeypatch, loopback):
    loopback.usage = {
        "prompt_tokens": 100,
        "total_tokens": 110,
        "prompt_tokens_details": {"cached_tokens": 0},
    }
    _arm_loopback(monkeypatch, loopback)
    config = live_config(candidate, "openai_compatible")
    config["pricing"]["fixture-v1"]["cache_write_per_million"] = None
    result = run(
        _voice(corpus), config, tmp_path / "run",
        repeats=5, live=True, max_usd=1, max_calls=10, brief=selection_brief(),
        allow_destination="127.0.0.1",
    )
    assert result["status"] == "completed"
    assert len(loopback.seen) == 5
    assert result["budget"]["cache_writes_bounded"] is False
    assert result["provenance"]["cache_writes_bounded"] is False
    assert result["budget"]["dispatched_calls"] == 5
    for trial in result["trials"]:
        call = trial["calls"][0]
        assert call["usage"]["cache_write_tokens"] is None
        assert call["cost_usd"] is None


def test_moderation_call_records_its_own_timeout(
        corpus, candidate, tmp_path, monkeypatch, loopback):
    loopback.reply = "ALLOW"
    _arm_loopback(monkeypatch, loopback)
    result = run(
        one_case(corpus, "moderation-fantasy-menace"),
        live_config(candidate, "openai_compatible"), tmp_path / "run",
        live=True, max_usd=1, max_calls=4, brief=selection_brief(),
        allow_destination="127.0.0.1",
    )
    assert len(loopback.seen) == 1
    assert result["adapter_settings"]["timeout_seconds"] == 10
    assert result["provenance"]["adapter_settings"]["timeout_seconds"] == 10
    call = result["trials"][0]["calls"][0]
    assert call["adapter_settings"]["timeout_seconds"] == 3.0
    assert result["budget"]["cache_writes_bounded"] is True


def test_loopback_records_resolved_adapter_settings(
        corpus, candidate, tmp_path, monkeypatch, loopback):
    _arm_loopback(monkeypatch, loopback)
    monkeypatch.setenv(REASONING_EFFORT_ENV, "low")
    monkeypatch.setenv(MAX_OUTPUT_PARAM_ENV, "max_tokens")
    monkeypatch.setenv(STRUCTURED_OUTPUTS_ENV, "1")
    monkeypatch.setenv(SEND_STORE_FALSE_ENV, "1")
    result = run(
        _voice(corpus), live_config(candidate, "openai_compatible"), tmp_path / "run",
        live=True, max_usd=1, max_calls=4, brief=selection_brief(),
        allow_destination="127.0.0.1",
    )
    expected = {
        "timeout_seconds": 10,
        "reasoning_effort": "low",
        "max_output_param": "max_tokens",
        "structured_outputs": True,
        "send_store_false": True,
    }
    assert result["adapter_settings"] == expected
    assert result["provenance"]["adapter_settings"] == expected
    call = result["trials"][0]["calls"][0]
    assert call["adapter_settings"] == expected
    blob = json.dumps(result)
    assert _KEY not in blob
    assert "http://127.0.0.1" not in blob
    sent = json.loads(loopback.seen[0]["body"])
    assert sent["max_tokens"] == 256
    assert sent["reasoning_effort"] == "low"


def test_cli_forwards_allow_destination(corpus, candidate, tmp_path, loopback):
    corpus_path = tmp_path / "corpus.json"
    write_json(corpus_path, _voice(corpus))
    config_path = tmp_path / "candidate.json"
    write_json(config_path, live_config(candidate, "openai_compatible"))
    brief_path = tmp_path / "brief.json"
    write_json(brief_path, selection_brief())
    port = loopback.server_address[1]
    env = os.environ.copy()
    env[BASE_URL_ENV] = f"http://127.0.0.1:{port}/v1"
    env[API_KEY_ENV] = _KEY
    env.pop(STRUCTURED_OUTPUTS_ENV, None)
    output = tmp_path / "cli-run"
    base = [
        sys.executable, str(ROOT / "scripts/model_eval.py"), "run", "--live",
        "--corpus", str(corpus_path), "--candidate", str(config_path),
        "--brief", str(brief_path), "--max-usd", "1", "--max-calls", "4",
        "--repeats", "1", "--task", "node_voice",
    ]
    missing = subprocess.run(
        [*base, "--output", str(tmp_path / "no-flag")],
        cwd=tmp_path, env=env, capture_output=True, text=True,
    )
    assert missing.returncode == 2, missing.stderr
    assert "allow-destination" in missing.stderr
    assert not (tmp_path / "no-flag").exists()
    assert loopback.seen == []
    completed = subprocess.run(
        [*base, "--allow-destination", "127.0.0.1", "--output", str(output)],
        cwd=tmp_path, env=env, capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stderr
    result = read_json(output / "run.json")
    assert result["destination_host"] == "127.0.0.1"
    assert result["status"] == "completed"
    assert len(loopback.seen) == 1
    assert f"127.0.0.1:{port}" not in json.dumps(result)
