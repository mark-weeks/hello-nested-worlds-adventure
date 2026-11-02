"""OpenAI-compatible adapter contract. Fake transport, or loopback HTTP only.

No live model call and no request to a provider host. A loopback bind that
the sandbox refuses skips only the urllib tests; the fake-transport cases
still run.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ast
import inspect
import json
import logging
import socket
import threading
import time
import traceback
import urllib.request

import pytest

import persistence
from consciousness import runtime
import consciousness.openai_compat_provider as compat_module
from consciousness.openai_compat_provider import (
    API_KEY_ENV,
    BASE_URL_ENV,
    MAX_RESPONSE_BYTES,
    MAX_OUTPUT_PARAM_ENV,
    REASONING_EFFORT_ENV,
    SEND_STORE_FALSE_ENV,
    STRUCTURED_OUTPUTS_ENV,
    TIMEOUT_ENV,
    MalformedProviderResponse,
    OpenAICompatibleProvider,
    ProviderConfigError,
    ProviderConnectionError,
    ProviderHTTPError,
    ProviderNotConfigured,
    ProviderTimeout,
    TransportRequest,
    UnsupportedCapability,
    build_request,
    chat_completions_url,
    parse_base_url,
    parse_response,
    provider as compat_provider,
)
from consciousness.runtime import Completion, SystemBlock, TokenUsage, failure_summary
from multiverse import store
from server import guard


_SECRET = "sk-test-provider-SECRET"
_PLAYER = "brass-lantern-player-line"
_HOST = "secret-host.example"
_URL = f"https://{_HOST}/v1"


def _forbid(text: str) -> None:
    assert _SECRET not in text
    assert _HOST not in text
    assert _PLAYER not in text
    assert "OPENAI_API_KEY" not in text or "does not read" in text


def _traceback(exc: BaseException) -> str:
    return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))


def _chat_body(*, content="ALLOW", finish="stop", refusal=None, model="echo-model",
               usage=None, include_refusal=True) -> bytes:
    message = {"role": "assistant", "content": content}
    if include_refusal:
        message["refusal"] = refusal
    body = {
        "model": model,
        "choices": [{"index": 0, "finish_reason": finish, "message": message}],
    }
    if usage is not None:
        body["usage"] = usage
    return json.dumps(body).encode()


def _ok(content="ALLOW", **kwargs):
    def transport(request: TransportRequest):
        return (200, (), _chat_body(content=content, **kwargs))
    return transport


def _arm(monkeypatch, *, url=_URL, key=_SECRET, models=True):
    monkeypatch.setenv(runtime.PROVIDER_ENV, "openai_compatible")
    monkeypatch.setenv(BASE_URL_ENV, url)
    if key is None:
        monkeypatch.delenv(API_KEY_ENV, raising=False)
    else:
        monkeypatch.setenv(API_KEY_ENV, key)
    if models:
        monkeypatch.setenv(runtime.NODE_MODEL_ENV, "compat-node")
        monkeypatch.setenv(runtime.INHABITANT_MODEL_ENV, "compat-inhabitant")
        monkeypatch.setenv(runtime.INTENT_MODEL_ENV, "compat-intent")
        monkeypatch.setenv(runtime.MODERATION_MODEL_ENV, "compat-moderation")
    for name in (MAX_OUTPUT_PARAM_ENV, STRUCTURED_OUTPUTS_ENV, SEND_STORE_FALSE_ENV,
                 REASONING_EFFORT_ENV, TIMEOUT_ENV, "OPENAI_API_KEY", "OPENAI_BASE_URL",
                 "XAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)


def _generate(adapter, **overrides):
    kwargs = dict(
        model="compat-node",
        system=(SystemBlock("bible", True), SystemBlock("state")),
        messages=[
            {"role": "user", "content": "one"},
            {"role": "assistant", "content": "two"},
            {"role": "user", "content": _PLAYER, "extra": "drop-me"},
        ],
        max_tokens=256,
    )
    kwargs.update(overrides)
    return adapter.generate(**kwargs)


class TestConfiguration:
    def test_vendor_environments_are_not_credentials(self, monkeypatch):
        _arm(monkeypatch, url="", key=None)
        monkeypatch.delenv(BASE_URL_ENV, raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", _SECRET)
        monkeypatch.setenv("XAI_API_KEY", _SECRET)
        monkeypatch.setenv("OPENAI_BASE_URL", _URL)
        adapter = OpenAICompatibleProvider(transport=_ok())
        assert adapter.configured() is False
        with pytest.raises(ProviderNotConfigured) as caught:
            _generate(adapter)
        _forbid(str(caught.value))
        _forbid(_traceback(caught.value))

    @pytest.mark.parametrize("url,key,ok", [
        ("https://api.example/v1", _SECRET, True),
        ("https://api.example/v1/", _SECRET, True),
        ("HTTPS://API.Example/v1", _SECRET, True),
        ("http://127.0.0.1:9/v1", None, True),
        ("http://localhost:11434/v1", None, True),
        ("http://[::1]/v1", None, True),
        ("https://127.0.0.1/v1", None, True),
        ("https://api.example/v1", None, False),
        ("http://api.example/v1", _SECRET, False),
        ("http://127.0.0.1.example/v1", _SECRET, False),
        ("https://user:pass@api.example/v1", _SECRET, False),
        (f"https://{_SECRET}@api.example/v1", _SECRET, False),
        ("https://api.example/v1?q=1", _SECRET, False),
        ("https://api.example/v1#frag", _SECRET, False),
        ("https://api.example/v1/../admin", _SECRET, False),
        ("file:///tmp/v1", _SECRET, False),
        ("", _SECRET, False),
        ("   ", _SECRET, False),
    ])
    def test_base_url_policy(self, monkeypatch, url, key, ok):
        _arm(monkeypatch, url=url, key=key)
        adapter = OpenAICompatibleProvider(transport=_ok())
        assert adapter.configured() is ok
        if url:
            parsed = parse_base_url(url)
            if parsed is not None:
                assert _SECRET not in parsed.url
                assert "@" not in parsed.url

    def test_paths_join_without_dropping_the_last_segment(self):
        assert chat_completions_url("https://api.x.ai/v1") == (
            "https://api.x.ai/v1/chat/completions")
        assert chat_completions_url("https://api.x.ai/v1/") == (
            "https://api.x.ai/v1/chat/completions")
        gemini = "https://generativelanguage.googleapis.com/v1beta/openai"
        assert chat_completions_url(gemini) == gemini + "/chat/completions"
        assert chat_completions_url(gemini + "/") == gemini + "/chat/completions"

    def test_illegal_optional_settings_are_unconfigured(self, monkeypatch):
        _arm(monkeypatch)
        monkeypatch.setenv(MAX_OUTPUT_PARAM_ENV, "max_tokens;no")
        adapter = OpenAICompatibleProvider(transport=_ok())
        assert adapter.configured() is False
        with pytest.raises(ProviderConfigError) as caught:
            _generate(adapter)
        assert "max_tokens;no" not in str(caught.value)
        _forbid(str(caught.value))
        monkeypatch.setenv(MAX_OUTPUT_PARAM_ENV, "max_tokens")
        monkeypatch.setenv(REASONING_EFFORT_ENV, _SECRET)
        assert adapter.configured() is False
        with pytest.raises(ProviderConfigError) as caught:
            _generate(adapter)
        _forbid(str(caught.value))
        _forbid(_traceback(caught.value))

    def test_no_default_model_and_no_id_judgment(self, monkeypatch):
        _arm(monkeypatch, models=False)
        for name in (
            runtime.SHARED_MODEL_ENV, runtime.NODE_MODEL_ENV,
            runtime.INHABITANT_MODEL_ENV, runtime.INTENT_MODEL_ENV,
            runtime.MODERATION_MODEL_ENV,
        ):
            monkeypatch.delenv(name, raising=False)
        adapter = OpenAICompatibleProvider()
        assert not callable(getattr(adapter, "default_model", None))
        assert adapter.model_id_validator() is None
        assert adapter.cache_reference_tokens("anything") is None
        from consciousness.model_check import _SECRET_NAME
        assert _SECRET_NAME.search(MAX_OUTPUT_PARAM_ENV) is None
        assert _SECRET_NAME.search(BASE_URL_ENV) is None
        assert _SECRET_NAME.search("NESTED_WORLDS_OPENAI_COMPATIBLE_MAX_TOKENS_PARAM")
        monkeypatch.setattr(runtime, "get_provider", lambda: adapter)
        assert runtime.model_for(runtime.NODE_TASK) == ""
        assert runtime.model_for(runtime.MODERATION_TASK) == ""


class TestRequestShape:
    def _sent(self, monkeypatch, **env_and_call):
        captured = []

        def transport(request: TransportRequest):
            captured.append(request)
            return (200, (), _chat_body())

        _arm(monkeypatch)
        for name, value in env_and_call.get("env", {}).items():
            if value is None:
                monkeypatch.delenv(name, raising=False)
            else:
                monkeypatch.setenv(name, value)
        adapter = OpenAICompatibleProvider(transport=transport)
        _generate(adapter, **env_and_call.get("call", {}))
        assert len(captured) == 1
        request = captured[0]
        assert isinstance(request, TransportRequest)
        body = json.loads(request.body)
        return request, body

    def test_one_system_message_keeps_block_order_and_roles(self, monkeypatch):
        request, body = self._sent(monkeypatch)
        assert request.url == f"{_URL}/chat/completions"
        assert request.timeout == 60.0
        assert request.headers == (
            ("Content-Type", "application/json"),
            ("Accept", "application/json"),
            ("Authorization", f"Bearer {_SECRET}"),
        )
        assert set(body) == {"model", "messages", "max_completion_tokens"}
        assert body["model"] == "compat-node"
        assert body["max_completion_tokens"] == 256
        assert body["messages"] == [
            {"role": "system", "content": "bible\n\nstate"},
            {"role": "user", "content": "one"},
            {"role": "assistant", "content": "two"},
            {"role": "user", "content": _PLAYER},
        ]
        assert "temperature" not in body
        assert "n" not in body
        assert "stream" not in body
        assert "user" not in body
        assert "safety_identifier" not in body
        assert "prompt_cache_key" not in body
        assert "store" not in body
        dumped = json.dumps(body)
        assert "drop-me" not in dumped
        assert _SECRET not in dumped
        assert _HOST not in dumped
        assert "TransportRequest" in repr(request)
        assert _SECRET not in repr(request)
        assert _HOST not in repr(request)
        assert _PLAYER not in repr(request)

    def test_caller_order_is_not_sorted_by_cacheable(self, monkeypatch):
        _request, body = self._sent(monkeypatch, call={
            "system": (SystemBlock("second", True), SystemBlock("first")),
        })
        assert body["messages"][0]["content"] == "second\n\nfirst"

    def test_max_tokens_parameter_follows_the_setting(self, monkeypatch):
        _request, body = self._sent(monkeypatch, env={MAX_OUTPUT_PARAM_ENV: "max_tokens"})
        assert set(body) == {"model", "messages", "max_tokens"}
        assert body["max_tokens"] == 256

    def test_timeout_default_override_and_env(self, monkeypatch):
        request, _body = self._sent(monkeypatch, call={"timeout": 3.0})
        assert request.timeout == 3.0
        request, _body = self._sent(monkeypatch, env={TIMEOUT_ENV: "12"})
        assert request.timeout == 12.0
        request, _body = self._sent(
            monkeypatch, env={TIMEOUT_ENV: "nope"}, call={"timeout": None})
        assert request.timeout == 60.0

    def test_schema_is_strict_only_when_declared(self, monkeypatch):
        schema = {
            "type": "object",
            "properties": {"op": {"type": "string", "enum": ["engrave", "mend"]}},
        }
        calls = []

        def transport(request):
            calls.append(request)
            return (200, (), _chat_body(content="{}"))

        _arm(monkeypatch)
        adapter = OpenAICompatibleProvider(transport=transport)
        with pytest.raises(UnsupportedCapability) as caught:
            _generate(adapter, json_schema=schema, max_tokens=500)
        assert calls == []
        _forbid(str(caught.value))
        monkeypatch.setenv(STRUCTURED_OUTPUTS_ENV, "1")
        _generate(adapter, json_schema=schema, max_tokens=500)
        body = json.loads(calls[0].body)
        assert set(body) == {
            "model", "messages", "max_completion_tokens", "response_format",
        }
        assert body["response_format"] == {
            "type": "json_schema",
            "json_schema": {
                "name": "enfolded_output",
                "schema": schema,
                "strict": True,
            },
        }
        assert body["response_format"]["json_schema"]["schema"]["properties"]["op"]["enum"] == [
            "engrave", "mend",
        ]

    def test_store_and_reasoning_are_opt_in(self, monkeypatch):
        _request, body = self._sent(monkeypatch, env={
            SEND_STORE_FALSE_ENV: "1",
            REASONING_EFFORT_ENV: " none ",
        })
        assert body["store"] is False
        assert body["reasoning_effort"] == "none"
        assert "user" not in body

    def test_loopback_omits_the_authorization_header(self, monkeypatch):
        captured = []

        def transport(request):
            captured.append(request)
            return (200, (), _chat_body())

        _arm(monkeypatch, url="http://127.0.0.1:9/v1", key=None)
        adapter = OpenAICompatibleProvider(transport=transport)
        assert adapter.configured() is True
        _generate(adapter)
        names = [name for name, _value in captured[0].headers]
        assert "Authorization" not in names
        assert captured[0].url == "http://127.0.0.1:9/v1/chat/completions"


class TestResponseMapping:
    @pytest.mark.parametrize("finish,content,refusal,complete,mapped,text", [
        ("stop", "ALLOW", None, True, "complete", "ALLOW"),
        ("stop", "", None, False, "unknown", None),
        ("stop", "  \n", None, False, "unknown", None),
        ("length", "ALLOW", None, False, "length", "ALLOW"),
        ("length", "  ", None, False, "length", None),
        ("length", None, None, False, "length", None),
        ("content_filter", "hidden", None, False, "filtered", None),
        ("stop", "ALLOW", "no", False, "refusal", None),
        ("length", "ALLOW", "", False, "refusal", None),
        ("tool_calls", "ALLOW", None, False, "tool", None),
        ("function_call", "ALLOW", None, False, "tool", None),
        ("end_turn", "ALLOW", None, False, "unknown", None),
        (None, "ALLOW", None, False, "unknown", None),
        ("other", "ALLOW", None, False, "unknown", None),
    ])
    def test_finish_reasons(self, finish, content, refusal, complete, mapped, text):
        body = json.loads(_chat_body(content=content, finish=finish, refusal=refusal))
        result = parse_response(body)
        assert result == Completion(
            text, complete, None, mapped, "echo-model", "openai_compatible",
        )

    def test_non_string_content_and_extra_choices_are_malformed(self):
        body = json.loads(_chat_body(content=["not", "a string"], finish="stop"))
        with pytest.raises(MalformedProviderResponse) as caught:
            parse_response(body)
        _forbid(str(caught.value))
        assert caught.value.__cause__ is None
        doubled = json.loads(_chat_body(content="ALLOW", finish="stop"))
        doubled["choices"].append(doubled["choices"][0])
        with pytest.raises(MalformedProviderResponse):
            parse_response(doubled)

    def test_missing_refusal_is_null_and_blank_text_does_not_authorize(self):
        import consciousness
        body = {
            "model": "echo-model",
            "choices": [{"finish_reason": "stop", "message": {"content": "ALLOW"}}],
        }
        result = parse_response(body)
        assert result.complete is True and result.text == "ALLOW"
        assert result.finish_reason == "complete"
        blank = parse_response({
            "model": "echo-model",
            "choices": [{"finish_reason": "stop", "message": {"content": "   "}}],
        })
        assert blank.complete is False and blank.text is None
        assert consciousness.moderation_outcome(blank) == "undecided"

    def test_missing_choices_and_error_objects(self):
        empty = parse_response({"model": "echo-model", "choices": []})
        assert empty.text is None and empty.complete is False
        assert empty.finish_reason == "unknown"
        assert empty.resolved_model == "echo-model"
        with pytest.raises(MalformedProviderResponse):
            parse_response({"error": {"message": _SECRET}, "choices": [{
                "finish_reason": "stop",
                "message": {"content": "ALLOW", "refusal": None},
            }]})
        with pytest.raises(MalformedProviderResponse) as caught:
            parse_response(["not", "an object"])
        _forbid(str(caught.value))

    def test_usage_normalises_openai_and_xai_shapes(self):
        openai = {
            "model": "served-openai",
            "choices": [{"finish_reason": "stop", "message": {
                "content": "ok", "refusal": None}}],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "total_tokens": 120,
                "prompt_tokens_details": {
                    "cached_tokens": 40,
                    "cache_write_tokens": 10,
                },
                "completion_tokens_details": {"reasoning_tokens": 15},
            },
        }
        parsed = parse_response(openai)
        assert parsed.usage == TokenUsage(
            input_tokens=50, output_tokens=20,
            cache_read_tokens=40, cache_write_tokens=10,
        )
        xai = {
            "model": "latest",
            "choices": [{"finish_reason": "stop", "message": {
                "content": "ok", "refusal": None}}],
            "usage": {
                "prompt_tokens": 32,
                "completion_tokens": 9,
                "total_tokens": 151,
                "prompt_tokens_details": {"cached_tokens": 8, "text_tokens": 32},
                "completion_tokens_details": {"reasoning_tokens": 110},
            },
        }
        parsed = parse_response(xai)
        assert parsed.resolved_model == "latest"
        assert parsed.usage == TokenUsage(
            input_tokens=24, output_tokens=119,
            cache_read_tokens=8, cache_write_tokens=None,
        )

    def test_missing_and_negative_usage_stay_unknown(self):
        missing = parse_response({
            "model": "echo-model",
            "choices": [{"finish_reason": "stop", "message": {
                "content": "ok", "refusal": None}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
        })
        assert missing.usage == TokenUsage(
            input_tokens=None, output_tokens=2,
            cache_read_tokens=None, cache_write_tokens=None,
        )
        negative = parse_response({
            "choices": [{"finish_reason": "stop", "message": {
                "content": "ok", "refusal": None}}],
            "usage": {
                "prompt_tokens": 5,
                "completion_tokens": 1,
                "total_tokens": 3,
                "prompt_tokens_details": {"cached_tokens": 9},
            },
        })
        assert negative.usage.input_tokens is None
        assert negative.usage.output_tokens is None
        assert negative.usage.cache_read_tokens == 9
        assert negative.resolved_model is None
        no_usage = parse_response({
            "choices": [{"finish_reason": "stop", "message": {
                "content": "ok", "refusal": None}}],
        })
        assert no_usage.usage is None
        completion_only = parse_response({
            "model": "echo-model",
            "choices": [{"finish_reason": "stop", "message": {
                "content": "ok", "refusal": None}}],
            "usage": {"completion_tokens": 9, "prompt_tokens": 32},
        })
        assert completion_only.usage.output_tokens is None
        assert completion_only.usage.input_tokens is None


class TestErrorsAndSecrecy:
    def _raise(self, monkeypatch, transport):
        _arm(monkeypatch)
        adapter = OpenAICompatibleProvider(transport=transport)
        with pytest.raises(Exception) as caught:
            _generate(adapter)
        _forbid(str(caught.value))
        _forbid(_traceback(caught.value))
        assert failure_summary(caught.value) == type(caught.value).__name__
        assert _PLAYER not in failure_summary(caught.value)
        return caught.value

    @pytest.mark.parametrize("status", [401, 429, 500, 302])
    def test_http_status_carries_no_body(self, monkeypatch, status):
        def transport(request):
            raw = json.dumps({"error": {"message": _SECRET + _PLAYER + _HOST}}).encode()
            return (status, (("x-url", _URL),), raw)

        exc = self._raise(monkeypatch, transport)
        assert isinstance(exc, ProviderHTTPError)
        assert exc.status == status
        assert str(exc) == f"HTTP {status}"

    def test_error_object_non_json_timeout_and_reset(self, monkeypatch):
        def error_object(request):
            return (200, (), json.dumps({"error": {"message": _SECRET}}).encode())

        assert isinstance(self._raise(monkeypatch, error_object), MalformedProviderResponse)

        def non_json(request):
            return (200, (), f"not-json {_SECRET} {_PLAYER}".encode())

        assert isinstance(self._raise(monkeypatch, non_json), MalformedProviderResponse)

        def timed_out(request):
            raise TimeoutError(f"{_SECRET} {_HOST} {_PLAYER}")

        assert isinstance(self._raise(monkeypatch, timed_out), ProviderTimeout)

        def reset(request):
            raise ConnectionResetError(f"reset {_SECRET} {_HOST} {_PLAYER}")

        exc = self._raise(monkeypatch, reset)
        assert isinstance(exc, ProviderConnectionError)
        assert exc.__cause__ is None

    def test_oversized_body_is_malformed(self, monkeypatch):
        def transport(request):
            return (200, (), b"x" * (MAX_RESPONSE_BYTES + 1))

        assert isinstance(self._raise(monkeypatch, transport), MalformedProviderResponse)

    def test_runtime_generate_logs_usage_without_the_prompt(self, monkeypatch, caplog):
        def transport(request):
            usage = {
                "prompt_tokens": 32,
                "completion_tokens": 9,
                "total_tokens": 151,
                "prompt_tokens_details": {"cached_tokens": 8},
            }
            return (200, (), _chat_body(content="spoken", usage=usage, model="echo-node"))

        _arm(monkeypatch)
        monkeypatch.setenv("OPENAI_API_KEY", _SECRET)
        monkeypatch.setenv("XAI_API_KEY", _SECRET)
        adapter = OpenAICompatibleProvider(transport=transport)
        monkeypatch.setattr(runtime, "get_provider", lambda: adapter)
        with caplog.at_level(logging.INFO, logger="nested_worlds.consciousness"):
            result = runtime.generate(
                endpoint="speak", model="compat-node", max_tokens=256,
                system=(SystemBlock("bible", True), SystemBlock("state")),
                messages=[{"role": "user", "content": _PLAYER}],
                voice_budget=False,
            )
        assert result.text == "spoken" and result.complete is True
        assert result.provider == "openai_compatible"
        assert result.resolved_model == "echo-node"
        assert result.usage == TokenUsage(24, 119, 8, None)
        assert "provider=openai_compatible" in caplog.text
        assert "input=24" in caplog.text
        assert "output=119" in caplog.text
        assert "cache_read=8" in caplog.text
        assert "cache_create=None" in caplog.text
        _forbid(caplog.text)

    def test_blank_model_id_never_calls_the_transport(self, monkeypatch):
        def transport(request):
            raise AssertionError("transport called")

        _arm(monkeypatch)
        adapter = OpenAICompatibleProvider(transport=transport)
        monkeypatch.setattr(runtime, "get_provider", lambda: adapter)
        charged = []
        monkeypatch.setattr(guard, "consume_anthropic", lambda **kwargs: charged.append("voice") or True)
        monkeypatch.setattr(guard, "consume_model_action", lambda **kwargs: charged.append("model") or True)
        for model in ("", "   ", None, 5):
            with pytest.raises(runtime.UnusableModelId):
                runtime.generate(
                    endpoint="speak", model=model, max_tokens=16,
                    system=(SystemBlock("bible"),),
                    messages=[{"role": "user", "content": _PLAYER}],
                    voice_budget=True,
                )
        assert charged == []


class TestVoiceBudget:
    def test_speak_charges_the_anthropic_bucket_once_and_an_unconfigured_call_charges_nothing(
            self, http, accounts, monkeypatch, caplog):
        import consciousness
        calls = []

        def transport(request):
            calls.append(json.loads(request.body))
            usage = {"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6}
            return (200, (), _chat_body(content="A remembered voice.", usage=usage,
                                         model="echo-node-20261101"))

        _arm(monkeypatch, url="", key=None, models=True)
        monkeypatch.delenv(BASE_URL_ENV, raising=False)
        monkeypatch.setattr(compat_provider, "_transport", transport)
        node = store.world_tree(382)
        day = guard._utc_day()
        user_voice = guard._user_bucket(guard.ANTHROPIC_BUCKET, accounts[0])
        user_actions = guard._user_bucket(guard.MODEL_ACTIONS_BUCKET, accounts[0])
        with caplog.at_level(logging.INFO):
            status, body, _headers = http("/speak", body={
                "node_name": node.name, "message": "Hello."})
            assert status == 200 and body["ai"] is False
            assert body["response"] == consciousness.fallback_voice(node)
            assert calls == []
            assert persistence.get_cost_calls(guard.ANTHROPIC_BUCKET, day) == 0
            assert persistence.get_cost_calls(user_voice, day) == 0
            assert persistence.get_cost_calls(user_actions, day) == 0

            monkeypatch.setenv(BASE_URL_ENV, _URL)
            monkeypatch.setenv(API_KEY_ENV, _SECRET)
            status, body, _headers = http("/speak", body={
                "node_name": node.name, "message": "Hello."})
            assert status == 200 and body["ai"] is True, body
            assert body["response"] == "A remembered voice."
            assert len(calls) == 1
            assert calls[0]["max_completion_tokens"] == 256
            assert calls[0]["model"] == "compat-node"
            assert persistence.get_cost_calls(guard.ANTHROPIC_BUCKET, day) == 1
            assert persistence.get_cost_calls(user_voice, day) == 1
            assert persistence.get_cost_calls(user_actions, day) == 1
            rows = [row for row in persistence.get_node_history(382, node.name)
                    if row["type"] == "PLAYER_SPEAK"]
            assert len(rows) == 1
            assert persistence.provenance_of(rows[0]["id"]) == {
                "provider": "openai_compatible",
                "resolved_model": "echo-node-20261101",
            }
            _forbid(caplog.text)
            assert _SECRET not in json.dumps(body)
            assert _HOST not in json.dumps(body)


class _Loopback(ThreadingHTTPServer):
    daemon_threads = True

    def serve_forever(self, poll_interval=0.5):
        # listen() already ran in server_activate. This event means the
        # accept thread has entered the loop, so a connect is queued
        # rather than racing the thread start.
        self._accepting.set()
        super().serve_forever(poll_interval=poll_interval)


def _start_loopback(*, mode="ok"):
    """Bind 127.0.0.1:0, accept on that socket, and wait until it does."""
    try:
        server = _Loopback(("127.0.0.1", 0), _Handler)
    except OSError as exc:
        pytest.skip(f"loopback bind unavailable ({type(exc).__name__})")
    server.mode = mode
    server.seen = []
    server.redirect_code = 302
    server.redirect_to = None
    server._accepting = threading.Event()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    server._thread = thread
    thread.start()
    if not server._accepting.wait(2):
        _stop_loopback(server)
        pytest.fail("loopback accept thread did not start")
    deadline = time.monotonic() + 2
    while True:
        try:
            probe = socket.create_connection(server.server_address, timeout=0.2)
        except OSError:
            if time.monotonic() >= deadline:
                _stop_loopback(server)
                pytest.fail("loopback port did not accept")
            time.sleep(0.01)
            continue
        probe.close()
        return server


def _stop_loopback(server):
    accepting = getattr(server, "_accepting", None)
    if accepting is not None and accepting.is_set():
        server.shutdown()
    server.server_close()
    thread = getattr(server, "_thread", None)
    if thread is not None:
        thread.join(2)


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        return

    def do_GET(self):
        self.do_POST()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length) if length else b""
        self.server.seen.append({
            "path": self.path,
            "method": self.command,
            "authorization": self.headers.get("Authorization"),
            "body": body,
        })
        mode = self.server.mode
        try:
            if mode == "ok":
                payload = _chat_body(content="loopback-ok", model="echo-loopback")
                self._send(200, payload)
            elif mode == "redirect":
                target = self.server.redirect_to
                if not isinstance(target, str) or not target:
                    raise RuntimeError("redirect target was not set")
                self.send_response(self.server.redirect_code)
                self.send_header("Location", target)
                self.send_header("Content-Length", "0")
                self.end_headers()
            elif mode == "split":
                # Headers are flushed here. The body follows only after a
                # gap, which is the race urllib's do_open loses if it
                # closes the socket before this write.
                payload = _chat_body(content="loopback-ok", model="echo-loopback")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                time.sleep(0.2)
                self.wfile.write(payload)
                self.wfile.flush()
            elif mode == "drip":
                raw = (
                    b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                    b"Content-Length: 2\r\nConnection: close\r\n\r\n{}"
                )
                for index in range(len(raw)):
                    time.sleep(0.05)
                    self.wfile.write(raw[index:index + 1])
                    self.wfile.flush()
            elif mode == "slow":
                time.sleep(2)
                self._send(200, _chat_body())
            elif mode == "huge":
                blob = b"{" + b" " * MAX_RESPONSE_BYTES + b"}"
                self._send(200, blob)
            elif mode == "bad":
                self._send(200, f"not-json {_SECRET}".encode())
            elif mode == "denied":
                self._send(401, json.dumps({"error": {"message": _SECRET}}).encode())
            else:
                self._send(500, b"{}")
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

    def _send(self, status, payload: bytes):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


@pytest.fixture
def loopback():
    # The 2026-10-04 evaluation saw a sandbox refuse loopback bind. Skip
    # only this urllib path; fake-transport tests do not need the socket.
    server = _start_loopback()
    try:
        yield server
    finally:
        _stop_loopback(server)


class TestUrllibLoopback:
    def _adapter(self, server, monkeypatch, timeout=None):
        port = server.server_address[1]
        _arm(monkeypatch, url=f"http://127.0.0.1:{port}/v1", key=_SECRET)
        return OpenAICompatibleProvider(), timeout

    def test_post_reads_a_completion_and_does_not_follow_redirects(self, loopback, monkeypatch):
        adapter, _timeout = self._adapter(loopback, monkeypatch)
        result = adapter.generate(
            model="compat-node", system=(SystemBlock("bible"),),
            messages=[{"role": "user", "content": "Hello."}], max_tokens=16,
        )
        assert result.text == "loopback-ok" and result.complete is True
        assert result.resolved_model == "echo-loopback"
        assert loopback.seen[0]["path"] == "/v1/chat/completions"
        assert loopback.seen[0]["authorization"] == f"Bearer {_SECRET}"
        sent = json.loads(loopback.seen[0]["body"])
        assert sent["messages"][0] == {"role": "system", "content": "bible"}
        stolen = _start_loopback()
        try:
            loopback.mode = "redirect"
            loopback.redirect_to = (
                f"http://127.0.0.1:{stolen.server_address[1]}/stolen"
            )
            before = len(loopback.seen)
            with pytest.raises(ProviderHTTPError) as caught:
                adapter.generate(
                    model="compat-node", system=(SystemBlock("bible"),),
                    messages=[{"role": "user", "content": _PLAYER}], max_tokens=16,
                )
            assert caught.value.status == 302
            assert len(loopback.seen) == before + 1
            assert stolen.seen == []
            _forbid(str(caught.value))
            _forbid(_traceback(caught.value))
            assert "stolen" not in str(caught.value)
        finally:
            _stop_loopback(stolen)

    @pytest.mark.parametrize("code", [301, 302, 303, 307, 308])
    def test_redirect_status_does_not_carry_the_key_to_another_host(
            self, loopback, monkeypatch, code):
        stolen = _start_loopback()
        try:
            stolen_port = stolen.server_address[1]
            loopback.mode = "redirect"
            loopback.redirect_code = code
            loopback.redirect_to = f"http://127.0.0.1:{stolen_port}/stolen"
            adapter, _timeout = self._adapter(loopback, monkeypatch)
            before = len(loopback.seen)
            with pytest.raises(ProviderHTTPError) as caught:
                adapter.generate(
                    model="compat-node", system=(SystemBlock("bible"),),
                    messages=[{"role": "user", "content": _PLAYER}], max_tokens=16,
                )
            assert caught.value.status == code
            assert str(caught.value) == f"HTTP {code}"
            assert caught.value.__cause__ is None
            _forbid(str(caught.value))
            _forbid(_traceback(caught.value))
            assert "stolen" not in str(caught.value)
            assert len(loopback.seen) == before + 1
            assert stolen.seen == []
        finally:
            _stop_loopback(stolen)

    @pytest.mark.parametrize("code", [301, 302, 303, 307, 308])
    def test_opener_redirect_with_proxy_env_is_status_only(
            self, loopback, monkeypatch, code):
        stolen = _start_loopback()
        try:
            proxy = _start_loopback(mode="denied")
            try:
                self._assert_status_only_redirect(loopback, monkeypatch, stolen, proxy, code)
            finally:
                _stop_loopback(proxy)
        finally:
            _stop_loopback(stolen)

    def _assert_status_only_redirect(self, loopback, monkeypatch, stolen, proxy, code):
        loopback.mode = "redirect"
        loopback.redirect_code = code
        loopback.redirect_to = (
            f"http://127.0.0.1:{stolen.server_address[1]}/stolen"
        )
        proxy_url = f"http://127.0.0.1:{proxy.server_address[1]}"
        for name in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
            monkeypatch.setenv(name, proxy_url)

        def _refuse_global_opener(*_args, **_kwargs):
            raise AssertionError("urlopen or install_opener was called")

        monkeypatch.setattr(urllib.request, "urlopen", _refuse_global_opener)
        monkeypatch.setattr(urllib.request, "install_opener", _refuse_global_opener)
        adapter, _timeout = self._adapter(loopback, monkeypatch)
        before = len(loopback.seen)
        with pytest.raises(ProviderHTTPError) as caught:
            adapter.generate(
                model="compat-node", system=(SystemBlock("bible"),),
                messages=[{"role": "user", "content": _PLAYER}], max_tokens=16,
            )
        assert caught.value.status == code
        assert str(caught.value) == f"HTTP {code}"
        assert caught.value.__cause__ is None
        _forbid(str(caught.value))
        _forbid(_traceback(caught.value))
        assert "stolen" not in str(caught.value)
        assert proxy_url not in str(caught.value)
        assert proxy_url not in _traceback(caught.value)
        assert len(loopback.seen) == before + 1
        assert loopback.seen[-1]["method"] == "POST"
        assert loopback.seen[-1]["path"] == "/v1/chat/completions"
        assert loopback.seen[-1]["authorization"] == f"Bearer {_SECRET}"
        assert stolen.seen == []
        assert proxy.seen == []

    def test_proxy_environment_is_ignored(self, loopback, monkeypatch):
        proxy = _start_loopback(mode="denied")
        try:
            proxy_url = f"http://127.0.0.1:{proxy.server_address[1]}"
            for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy"):
                monkeypatch.setenv(name, proxy_url)
            adapter, _timeout = self._adapter(loopback, monkeypatch)
            result = adapter.generate(
                model="compat-node", system=(SystemBlock("bible"),),
                messages=[{"role": "user", "content": "Hello."}], max_tokens=16,
            )
            assert result.text == "loopback-ok"
            assert proxy.seen == []
            assert loopback.seen[0]["authorization"] == f"Bearer {_SECRET}"
        finally:
            _stop_loopback(proxy)

    def test_body_written_after_the_headers_is_still_a_completion(
            self, loopback, monkeypatch):
        adapter, _timeout = self._adapter(loopback, monkeypatch)
        loopback.mode = "split"
        result = adapter.generate(
            model="compat-node", system=(SystemBlock("bible"),),
            messages=[{"role": "user", "content": "Hello."}], max_tokens=16,
        )
        assert result.text == "loopback-ok" and result.complete is True
        assert result.resolved_model == "echo-loopback"
        assert loopback.seen[0]["authorization"] == f"Bearer {_SECRET}"

    def test_wall_clock_budget_stops_a_dribbled_header(self, loopback, monkeypatch):
        adapter, _timeout = self._adapter(loopback, monkeypatch)
        loopback.mode = "drip"
        started = time.monotonic()
        with pytest.raises(ProviderTimeout) as caught:
            adapter.generate(
                model="compat-node", system=(SystemBlock("bible"),),
                messages=[{"role": "user", "content": _PLAYER}], max_tokens=8,
                timeout=0.3,
            )
        elapsed = time.monotonic() - started
        assert elapsed < 1.0
        assert str(caught.value) == "timed out"
        assert caught.value.__cause__ is None
        _forbid(_traceback(caught.value))

    def test_timeout_malformed_denied_and_oversized(self, loopback, monkeypatch):
        adapter, _timeout = self._adapter(loopback, monkeypatch)
        loopback.mode = "slow"
        started = time.monotonic()
        with pytest.raises(ProviderTimeout) as caught:
            adapter.generate(
                model="compat-node", system=(SystemBlock("bible"),),
                messages=[{"role": "user", "content": _PLAYER}], max_tokens=8,
                timeout=0.3,
            )
        assert time.monotonic() - started < 2
        _forbid(_traceback(caught.value))
        loopback.mode = "bad"
        with pytest.raises(MalformedProviderResponse) as caught:
            adapter.generate(
                model="compat-node", system=(SystemBlock("bible"),),
                messages=[{"role": "user", "content": "Hello."}], max_tokens=8,
            )
        _forbid(str(caught.value))
        loopback.mode = "denied"
        with pytest.raises(ProviderHTTPError) as caught:
            adapter.generate(
                model="compat-node", system=(SystemBlock("bible"),),
                messages=[{"role": "user", "content": _PLAYER}], max_tokens=8,
            )
        assert caught.value.status == 401
        _forbid(str(caught.value))
        _forbid(_traceback(caught.value))
        loopback.mode = "huge"
        with pytest.raises(MalformedProviderResponse):
            adapter.generate(
                model="compat-node", system=(SystemBlock("bible"),),
                messages=[{"role": "user", "content": "Hello."}], max_tokens=8,
            )


def test_adapter_source_never_calls_urlopen_or_install_opener():
    tree = ast.parse(inspect.getsource(compat_module))
    banned = {"urlopen", "install_opener"}
    hits = [
        node.id if isinstance(node, ast.Name) else node.attr
        for node in ast.walk(tree)
        if (isinstance(node, ast.Name) and node.id in banned)
        or (isinstance(node, ast.Attribute) and node.attr in banned)
    ]
    assert hits == []


def test_build_request_is_pure_and_has_no_transport():
    schema = {"type": "object", "properties": {"op": {"enum": ["engrave"]}}}
    body = build_request(
        model="compat-node",
        system=(SystemBlock("bible", True), SystemBlock("now")),
        messages=[{"role": "user", "content": "hello"}],
        max_tokens=32,
        json_schema=schema,
        max_tokens_param="max_completion_tokens",
        structured_outputs=True,
        send_store_false=False,
        reasoning_effort=None,
    )
    assert body["messages"][0]["content"] == "bible\n\nnow"
    assert body["response_format"]["json_schema"]["strict"] is True
    with pytest.raises(UnsupportedCapability):
        build_request(
            model="compat-node", system=(SystemBlock("bible"),),
            messages=[], max_tokens=32, json_schema=schema,
            max_tokens_param="max_tokens", structured_outputs=False,
            send_store_false=False, reasoning_effort=None,
        )


def test_socket_timeout_from_the_transport_is_adapter_timeout(monkeypatch):
    def transport(request):
        raise socket.timeout("timed out talking to " + _HOST)

    _arm(monkeypatch)
    adapter = OpenAICompatibleProvider(transport=transport)
    with pytest.raises(ProviderTimeout) as caught:
        _generate(adapter)
    assert caught.value.__cause__ is None
    _forbid(_traceback(caught.value))
