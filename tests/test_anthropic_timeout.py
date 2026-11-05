"""The anthropic adapter's per-attempt timeout for calls that pass none.

Node voice, inhabitant voice and intention call ``runtime.generate`` with no
timeout. Before ``NESTED_WORLDS_ANTHROPIC_TIMEOUT_SECONDS`` the pinned SDK
used 600 s per attempt for them (anthropic 0.120.2,
``resources/messages/messages.py:1030``), retried twice, so a hung provider
held each in-flight slot for about 30 minutes. The adapter now sends the
setting (default 60) per attempt and leaves the SDK's retries as they are.
A call that passes its own timeout (the moderation classify, the startup
probe) is not touched here.

The real SDK talks to a local stub through ``ANTHROPIC_BASE_URL`` or to an
``httpx.MockTransport``. Blocking calls run on a daemon thread with a join
limit, so a regression to the 600 s timeout fails a test instead of hanging
the suite. No network and no live model call.
"""
from __future__ import annotations

import json
import logging
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import httpx
import pytest

from consciousness import anthropic_provider, runtime
from consciousness.anthropic_provider import AnthropicProvider
from consciousness.runtime import SystemBlock
from multiverse import store
from server import _Handler, _ThreadedServer, guard, moderation
from tests.test_provider_slot_wait import _bounded, _count, _free_slots

SETTING = 0.3  # NESTED_WORLDS_ANTHROPIC_TIMEOUT_SECONDS in the stub tests
ATTEMPTS = 3   # the SDK's first attempt and its default two retries
# The SDK sleeps 0.5 s, then 1 s, each scaled by 0.75 to 1.0 (jitter), before
# its two retries (anthropic 0.120.2, _base_client.py:818-840).
MAX_BACKOFF = 0.5 + 1.0
RETRY_AFTER = 0.2  # seconds; the SDK honours 0 < retry-after <= 60
SEED = 382
REPLY = {"id": "msg_fixture", "type": "message", "role": "assistant",
         "model": "fixture-model", "stop_reason": "end_turn",
         "content": [{"type": "text", "text": "A reply."}],
         "usage": {"input_tokens": 3, "output_tokens": 2}}
OVERLOADED = {"type": "error",
              "error": {"type": "overloaded_error", "message": "fixture"}}


def _generate(adapter, **kwargs):
    kwargs.setdefault("max_tokens", 256)
    return adapter.generate(model="fixture-model", system=(SystemBlock("s"),),
                            messages=[{"role": "user", "content": "hi"}], **kwargs)


class _Stub:
    """A local Messages endpoint. Each POST takes the next answer in turn.

    ``hang`` never answers within a test (freed at teardown), ``overloaded``
    is a 529 with a short retry-after, and ``ok`` is a reply. The last answer
    repeats.
    """

    def __init__(self, *answers):
        self.answers = answers
        self.release = threading.Event()
        self.attempts = []
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                self.rfile.read(int(self.headers.get("content-length", 0)))
                answer = stub.answers[min(len(stub.attempts), len(stub.answers) - 1)]
                stub.attempts.append({
                    "timeout": self.headers.get("x-stainless-timeout"),
                    "retry": self.headers.get("x-stainless-retry-count"),
                })
                if answer == "hang":
                    stub.release.wait(30)
                    return
                status, body = (529, OVERLOADED) if answer == "overloaded" else (200, REPLY)
                data = json.dumps(body).encode()
                self.send_response(status)
                if status == 529:
                    self.send_header("retry-after", str(RETRY_AFTER))
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       kwargs={"poll_interval": 0.05}, daemon=True)
        self.thread.start()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server.server_port}"

    def close(self):
        self.release.set()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(5)


@pytest.fixture
def serve(monkeypatch):
    """Start a stub; return it with a fresh adapter whose real SDK sends to it."""
    started = []

    def start(*answers):
        stub = _Stub(*answers)
        monkeypatch.setenv(anthropic_provider.TIMEOUT_ENV, str(SETTING))
        monkeypatch.setenv("ANTHROPIC_BASE_URL", stub.url)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "fixture-key")
        monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
        for name in ("HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"):
            monkeypatch.delenv(name, raising=False)
        adapter = AnthropicProvider()
        adapter._get_client()  # built before any timing starts
        started.append((stub, adapter))
        return stub, adapter

    try:
        yield start
    finally:
        for stub, adapter in started:
            adapter._client.close()
            stub.close()


def _mock_adapter(requests, client_timeout=None):
    """A fresh adapter whose real SDK client answers through MockTransport."""
    import anthropic

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json=REPLY)

    client = anthropic.Anthropic(
        api_key="fixture-key", base_url="http://anthropic.invalid",
        http_client=httpx.Client(transport=httpx.MockTransport(handle)))
    if client_timeout is not None:
        client = client.with_options(timeout=client_timeout)
    adapter = AnthropicProvider()
    adapter._client = client
    return adapter


def _capturing_adapter(calls):
    adapter = AnthropicProvider()

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text="ok")],
                               stop_reason="end_turn")

    adapter._client = SimpleNamespace(messages=SimpleNamespace(create=create))
    return adapter


class TestTheSetting:
    @pytest.mark.parametrize("raw", [None, "", "   ", "soon", "inf", "-inf", "nan",
                                     "0", "0.0", "-5"])
    def test_unusable_values_send_the_60_second_default(self, monkeypatch, raw):
        if raw is None:
            monkeypatch.delenv(anthropic_provider.TIMEOUT_ENV, raising=False)
        else:
            monkeypatch.setenv(anthropic_provider.TIMEOUT_ENV, raw)
        calls = []
        _generate(_capturing_adapter(calls))
        assert [call["timeout"] for call in calls] == [httpx.Timeout(60.0, connect=5.0)]

    @pytest.mark.parametrize("raw,seconds,connect", [
        ("90", 90.0, 5.0), (" 12.5 ", 12.5, 5.0), ("2", 2.0, 2.0), ("0.3", 0.3, 0.3)])
    def test_a_usable_value_is_sent_and_connect_stays_at_most_5_seconds(
            self, monkeypatch, raw, seconds, connect):
        monkeypatch.setenv(anthropic_provider.TIMEOUT_ENV, raw)
        calls = []
        _generate(_capturing_adapter(calls))
        sent = calls[0]["timeout"]
        assert (sent.connect, sent.read, sent.write, sent.pool) == (
            connect, seconds, seconds, seconds)

    def test_the_setting_is_read_on_every_call(self, monkeypatch):
        calls = []
        adapter = _capturing_adapter(calls)
        monkeypatch.setenv(anthropic_provider.TIMEOUT_ENV, "20")
        _generate(adapter)
        monkeypatch.setenv(anthropic_provider.TIMEOUT_ENV, "40")
        _generate(adapter)
        assert [call["timeout"].read for call in calls] == [20.0, 40.0]

    def test_an_intention_shaped_call_gets_the_default_and_keeps_its_schema(
            self, monkeypatch):
        # Intention asks 500 tokens with a JSON schema, the largest budget.
        monkeypatch.delenv(anthropic_provider.TIMEOUT_ENV, raising=False)
        calls = []
        schema = {"type": "object"}
        _generate(_capturing_adapter(calls), max_tokens=500, json_schema=schema)
        assert calls[0]["timeout"] == httpx.Timeout(60.0, connect=5.0)
        assert calls[0]["output_config"] == {
            "format": {"type": "json_schema", "schema": schema}}


class TestTheRequestTheSdkSends:
    def test_the_sdk_applies_the_default_to_the_request(self, monkeypatch):
        monkeypatch.delenv(anthropic_provider.TIMEOUT_ENV, raising=False)
        requests = []
        result = _generate(_mock_adapter(requests))
        assert result.text == "A reply."
        assert [r.extensions["timeout"] for r in requests] == [
            {"connect": 5.0, "read": 60.0, "write": 60.0, "pool": 60.0}]
        assert requests[0].headers["x-stainless-timeout"] == "60.0"

    def test_a_callers_timeout_reaches_the_request_and_the_setting_does_not(
            self, monkeypatch):
        monkeypatch.setenv(anthropic_provider.TIMEOUT_ENV, "45")
        requests = []
        _generate(_mock_adapter(requests), timeout=3.0)
        assert requests and all(r.extensions["timeout"] == {
            "connect": 3.0, "read": 3.0, "write": 3.0, "pool": 3.0} for r in requests)

    def test_a_client_configured_with_its_own_timeout_keeps_it(self, monkeypatch):
        # The evaluation harness builds its client with the candidate's
        # timeout_seconds; a per-request value would silently override it.
        monkeypatch.setenv(anthropic_provider.TIMEOUT_ENV, "45")
        requests = []
        _generate(_mock_adapter(requests, client_timeout=7))
        assert [r.extensions["timeout"] for r in requests] == [
            {"connect": 7, "read": 7, "write": 7, "pool": 7}]


class TestAgainstALocalStub:
    def test_a_hung_provider_fails_after_three_attempts_of_the_setting_each(self, serve):
        import anthropic
        stub, adapter = serve("hang")
        box = _bounded(lambda: _generate(adapter), limit=10)
        assert isinstance(box.get("error"), anthropic.APITimeoutError)
        assert [a["retry"] for a in stub.attempts] == ["0", "1", "2"]
        assert {a["timeout"] for a in stub.attempts} == {str(SETTING)}
        # Each attempt waits out the setting; the SDK backs off between them.
        assert ATTEMPTS * SETTING <= box["elapsed"] < ATTEMPTS * SETTING + MAX_BACKOFF + 1.5

    def test_a_transient_overload_is_still_retried(self, serve):
        # SDK retries stay at its default for calls with no timeout of their
        # own, so a 529 on a node voice is retried after the retry-after.
        stub, adapter = serve("overloaded", "ok")
        box = _bounded(lambda: _generate(adapter), limit=10)
        assert "error" not in box, box.get("error")
        assert box["value"].text == "A reply." and box["value"].complete
        assert [a["retry"] for a in stub.attempts] == ["0", "1"]
        assert box["elapsed"] >= RETRY_AFTER

    def test_a_working_provider_is_answered_once(self, serve):
        stub, adapter = serve("ok")
        box = _bounded(lambda: _generate(adapter), limit=10)
        assert box["value"].text == "A reply." and box["value"].complete
        assert stub.attempts == [{"timeout": str(SETTING), "retry": "0"}]


def _post(port, path, body):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.load(resp), time.monotonic() - started
    except urllib.error.HTTPError as exc:
        return exc.code, json.load(exc), time.monotonic() - started


@pytest.fixture
def game(monkeypatch):
    monkeypatch.setenv("NESTED_WORLDS_CANONICAL_SEED", str(SEED))
    server = _ThreadedServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever,
                              kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)


class TestSpeakAgainstAHungProvider:
    def test_the_player_gets_the_nodes_silence_and_the_slot_comes_back(
            self, serve, game, monkeypatch, caplog):
        import consciousness
        stub, adapter = serve("hang")
        monkeypatch.setattr(runtime, "get_provider", lambda: adapter)
        monkeypatch.setattr(runtime, "_semaphores", {})
        monkeypatch.setattr(runtime, "_semaphore_limits", {})
        monkeypatch.setenv("NESTED_WORLDS_ANTHROPIC_CONCURRENCY", "2")
        for name in (runtime.SHARED_MODEL_ENV, runtime.NODE_MODEL_ENV):
            monkeypatch.delenv(name, raising=False)
        monkeypatch.delenv(guard.DISABLE_AI_ENV, raising=False)
        monkeypatch.delenv(moderation.DISABLE_MODERATION_ENV, raising=False)
        caplog.set_level(logging.WARNING, logger="nested_worlds")
        root = store.world_tree(SEED)
        box = _bounded(lambda: _post(game, "/speak", {
            "node_name": root.name, "message": "hello"}), limit=12)
        assert "error" not in box, box.get("error")
        status, data, elapsed = box["value"]
        assert status == 200 and data == {
            "response": consciousness.fallback_voice(root), "ai": False}
        assert elapsed < ATTEMPTS * SETTING + MAX_BACKOFF + 3
        assert len(stub.attempts) == ATTEMPTS
        assert _count("speak", "provider") == 1
        assert _count("speak", "busy") == 0 and _count("speak", "ok") == 0
        assert [r.getMessage() for r in caplog.records if r.name == "nested_worlds.voice"] == [
            "voice_fallback surface=speak reason=provider exception=APITimeoutError"]
        assert _free_slots(runtime._semaphore_for("anthropic")) == 2
