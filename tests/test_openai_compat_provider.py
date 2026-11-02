"""OpenAI-compatible adapter contract. Fake transport, or loopback HTTP only.

No live model call and no request to a provider host. A loopback bind that
the sandbox refuses skips only the urllib tests; the fake-transport cases
still run.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ast
import http.client
import inspect
import json
import logging
import socket
import ssl
import subprocess
import sys
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
    MalformedProviderResponse,
    REASONING_EFFORT_ENV,
    SEND_STORE_FALSE_ENV,
    STRUCTURED_OUTPUTS_ENV,
    TIMEOUT_ENV,
    OpenAICompatibleProvider,
    ProviderConfigError,
    ProviderConnectionError,
    ProviderHTTPError,
    ProviderNotConfigured,
    ProviderTimeout,
    decode_response,
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

    def test_key_must_be_ascii_and_printable(self, monkeypatch):
        for key in ("sk-test\r\nX: y", "sk-test-\u20ac", "sk-test-\u0007", "sk-a b"):
            _arm(monkeypatch, key=key)
            adapter = OpenAICompatibleProvider(transport=_ok())
            assert adapter.configured() is False
            rendered = repr(compat_module._settings())
            assert key not in rendered
            assert "api_key" not in rendered
            with pytest.raises(ProviderNotConfigured) as caught:
                _generate(adapter)
            assert key not in str(caught.value)
            assert key not in _traceback(caught.value)
        _arm(monkeypatch)
        rendered = repr(compat_module._settings())
        assert _SECRET not in rendered
        assert "api_key" not in rendered

    def test_invalid_key_is_unconfigured_on_loopback(self, monkeypatch):
        calls = []

        def transport(request):
            calls.append(request)
            return (200, (), _chat_body())

        for key in ("sk-test\r\nX: y", "sk-test-\u20ac", "sk-a b"):
            _arm(monkeypatch, url="http://127.0.0.1:9/v1", key=key)
            adapter = OpenAICompatibleProvider(transport=transport)
            assert adapter.configured() is False
            rendered = repr(compat_module._settings())
            assert key not in rendered
            with pytest.raises(ProviderNotConfigured) as caught:
                _generate(adapter)
            assert key not in str(caught.value)
            assert key not in _traceback(caught.value)
        assert calls == []

    @pytest.mark.parametrize("url", [
        "https://example..com/v1",
        "https://.example.com/v1",
        "https://\u0080.example/v1",
    ])
    def test_bad_idna_host_is_rejected(self, url):
        assert parse_base_url(url) is None

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
        boolean = parse_response({
            "choices": [{
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": "ok", "refusal": None},
            }],
            "usage": {
                "prompt_tokens": True,
                "completion_tokens": True,
                "total_tokens": True,
                "prompt_tokens_details": {
                    "cached_tokens": True,
                    "cache_write_tokens": True,
                },
            },
        })
        assert boolean.usage == TokenUsage(None, None, None, None)

    def test_deeply_nested_json_is_malformed(self):
        raw = b"[" * 2000 + b"]" * 2000
        assert len(raw) < MAX_RESPONSE_BYTES
        with pytest.raises(MalformedProviderResponse) as caught:
            decode_response(200, raw)
        assert str(caught.value) == "malformed response"
        assert caught.value.__cause__ is None
        assert caught.value.__suppress_context__ is True


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
                # gap. The deadline socket must keep the descriptor open
                # for that read.
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
            elif mode in ("conn_close", "http10", "no_length"):
                self._delayed_completion(mode)
            elif mode == "truncated":
                self._truncated()
            elif mode == "chunked_huge":
                self._chunked_over_cap()
            elif mode == "stream_huge":
                self._stream_over_cap()
            elif mode == "huge_500":
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(MAX_RESPONSE_BYTES + 8))
                self.end_headers()
            else:
                self._send(500, b"{}")
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

    def _delayed_completion(self, mode: str) -> None:
        payload = _chat_body(content="loopback-ok", model="echo-loopback")
        if mode == "http10":
            status = b"HTTP/1.0 200 OK\r\n"
            length = b"Content-Length: " + str(len(payload)).encode() + b"\r\n"
            extra = b""
        elif mode == "no_length":
            status = b"HTTP/1.1 200 OK\r\n"
            length = b""
            extra = b""
        else:
            status = b"HTTP/1.1 200 OK\r\n"
            length = b"Content-Length: " + str(len(payload)).encode() + b"\r\n"
            extra = b"Connection: close\r\n"
        self.wfile.write(
            status + b"Content-Type: application/json\r\n" + length + extra + b"\r\n"
        )
        self.wfile.flush()
        time.sleep(0.2)
        self.wfile.write(payload)
        self.wfile.flush()
        self.close_connection = True

    def _truncated(self) -> None:
        payload = _chat_body(content="loopback-ok", model="echo-loopback")
        announced = len(payload) + 32
        self.wfile.write(
            b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
            b"Content-Length: " + str(announced).encode() + b"\r\n"
            b"Connection: close\r\n\r\n"
        )
        self.wfile.write(payload)
        self.wfile.flush()
        self.close_connection = True

    def _chunked_over_cap(self) -> None:
        self.wfile.write(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n")
        remaining = MAX_RESPONSE_BYTES + 64
        piece = b"x" * 65536
        while remaining:
            block = piece[:min(len(piece), remaining)]
            self.wfile.write(f"{len(block):x}\r\n".encode() + block + b"\r\n")
            remaining -= len(block)
        self.wfile.write(b"0\r\n\r\n")
        self.wfile.flush()

    def _stream_over_cap(self) -> None:
        self.wfile.write(b"HTTP/1.1 200 OK\r\nConnection: close\r\n\r\n")
        self.wfile.write(b"x" * (MAX_RESPONSE_BYTES + 64))
        self.wfile.flush()
        self.close_connection = True

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
        monkeypatch.delenv("NO_PROXY", raising=False)
        monkeypatch.delenv("no_proxy", raising=False)

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
            monkeypatch.delenv("NO_PROXY", raising=False)
            monkeypatch.delenv("no_proxy", raising=False)
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
        loopback.mode = "denied"
        with pytest.raises(ProviderHTTPError) as caught:
            adapter.generate(
                model="compat-node", system=(SystemBlock("bible"),),
                messages=[{"role": "user", "content": _PLAYER}], max_tokens=8,
            )
        assert caught.value.status == 401
        assert str(caught.value) == "HTTP 401"
        assert caught.value.__cause__ is None
        assert caught.value.__suppress_context__ is True
        _forbid(str(caught.value))
        _forbid(_traceback(caught.value))
        loopback.mode = "bad"
        with pytest.raises(MalformedProviderResponse) as caught:
            adapter.generate(
                model="compat-node", system=(SystemBlock("bible"),),
                messages=[{"role": "user", "content": "Hello."}], max_tokens=8,
            )
        assert str(caught.value) == "malformed response"
        assert caught.value.__cause__ is None
        assert caught.value.__suppress_context__ is True
        _forbid(str(caught.value))
        _forbid(_traceback(caught.value))
        loopback.mode = "huge"
        with pytest.raises(MalformedProviderResponse):
            adapter.generate(
                model="compat-node", system=(SystemBlock("bible"),),
                messages=[{"role": "user", "content": "Hello."}], max_tokens=8,
            )

    @pytest.mark.parametrize("mode", ["conn_close", "http10", "no_length"])
    def test_delayed_body_is_a_completion_when_the_connection_closes(
            self, loopback, monkeypatch, mode):
        adapter, _timeout = self._adapter(loopback, monkeypatch)
        loopback.mode = mode
        result = adapter.generate(
            model="compat-node", system=(SystemBlock("bible"),),
            messages=[{"role": "user", "content": "Hello."}], max_tokens=16,
        )
        assert result.text == "loopback-ok" and result.complete is True
        assert result.resolved_model == "echo-loopback"
        assert loopback.seen[-1]["authorization"] == f"Bearer {_SECRET}"

    @pytest.mark.parametrize("mode", ["chunked_huge", "stream_huge", "truncated"])
    def test_stream_over_the_cap_or_a_short_body_is_malformed(
            self, loopback, monkeypatch, mode):
        adapter, _timeout = self._adapter(loopback, monkeypatch)
        loopback.mode = mode
        with pytest.raises(MalformedProviderResponse) as caught:
            adapter.generate(
                model="compat-node", system=(SystemBlock("bible"),),
                messages=[{"role": "user", "content": "Hello."}], max_tokens=8,
            )
        assert str(caught.value) == "malformed response"
        assert caught.value.__cause__ is None
        assert not isinstance(caught.value, ProviderConnectionError)

    def test_oversized_error_status_is_the_status(self, loopback, monkeypatch):
        adapter, _timeout = self._adapter(loopback, monkeypatch)
        loopback.mode = "huge_500"
        with pytest.raises(ProviderHTTPError) as caught:
            adapter.generate(
                model="compat-node", system=(SystemBlock("bible"),),
                messages=[{"role": "user", "content": _PLAYER}], max_tokens=8,
            )
        assert caught.value.status == 500
        assert str(caught.value) == "HTTP 500"
        assert caught.value.__cause__ is None
        _forbid(str(caught.value))
        _forbid(_traceback(caught.value))

    def test_https_loopback_sends_the_key(self, monkeypatch, tmp_path):
        cert = tmp_path / "cert.pem"
        key = tmp_path / "key.pem"
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
            pytest.skip("openssl could not write a loopback certificate")
        server = _start_tls_loopback(cert, key)
        try:
            monkeypatch.setenv("SSL_CERT_FILE", str(cert))
            port = server.server_address[1]
            _arm(monkeypatch, url=f"https://127.0.0.1:{port}/v1", key=_SECRET)
            result = OpenAICompatibleProvider().generate(
                model="compat-node", system=(SystemBlock("bible"),),
                messages=[{"role": "user", "content": "Hello."}], max_tokens=16,
            )
            assert result.text == "loopback-ok" and result.complete is True
            assert server.seen[-1]["authorization"] == f"Bearer {_SECRET}"
            assert server.seen[-1]["path"] == "/v1/chat/completions"
        finally:
            _stop_loopback(server)

    def test_https_loopback_survives_a_py312_connection(self, monkeypatch, tmp_path):
        """A 3.12 connection rejects ``check_hostname`` and has no such attribute."""
        cert = tmp_path / "cert.pem"
        key = tmp_path / "key.pem"
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
            pytest.skip("openssl could not write a loopback certificate")

        class Py312(http.client.HTTPConnection):
            default_port = http.client.HTTPS_PORT

            def __init__(self, host, port=None, *,
                         timeout=socket._GLOBAL_DEFAULT_TIMEOUT,
                         source_address=None, context=None, blocksize=8192):
                self._enfolded_context = context
                super().__init__(host, port, timeout, source_address, blocksize)

            def connect(self):
                super().connect()
                context = self._enfolded_context or ssl.create_default_context()
                host = self._tunnel_host or self.host
                self.sock = context.wrap_socket(self.sock, server_hostname=host)

        monkeypatch.setattr(http.client, "HTTPSConnection", Py312)
        real_init = compat_module._HTTPSHandler.__init__

        def init(self, deadline):
            real_init(self, deadline)
            if hasattr(self, "_check_hostname"):
                delattr(self, "_check_hostname")

        monkeypatch.setattr(compat_module._HTTPSHandler, "__init__", init)
        server = _start_tls_loopback(cert, key)
        try:
            monkeypatch.setenv("SSL_CERT_FILE", str(cert))
            port = server.server_address[1]
            _arm(monkeypatch, url=f"https://127.0.0.1:{port}/v1", key=_SECRET)
            result = OpenAICompatibleProvider().generate(
                model="compat-node", system=(SystemBlock("bible"),),
                messages=[{"role": "user", "content": "Hello."}], max_tokens=16,
            )
            assert result.text == "loopback-ok" and result.complete is True
            assert server.seen[-1]["authorization"] == f"Bearer {_SECRET}"
        finally:
            _stop_loopback(server)


def _start_tls_loopback(certfile, keyfile):
    try:
        server = _Loopback(("127.0.0.1", 0), _Handler)
    except OSError as exc:
        pytest.skip(f"loopback bind unavailable ({type(exc).__name__})")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile, keyfile)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    server.mode = "ok"
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
    client = ssl.create_default_context(cafile=str(certfile))
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


def test_connection_refused_is_connection_failed(monkeypatch):
    held = socket.socket()
    try:
        held.bind(("127.0.0.1", 0))
        port = held.getsockname()[1]
        _arm(monkeypatch, url=f"http://127.0.0.1:{port}/v1")
        with pytest.raises(ProviderConnectionError) as caught:
            _generate(OpenAICompatibleProvider())
        assert str(caught.value) == "connection failed"
        assert caught.value.__cause__ is None
        assert caught.value.__suppress_context__ is True
        rendered = str(caught.value) + _traceback(caught.value)
        assert "Connection refused" not in rendered
        assert "Errno" not in rendered
        _forbid(rendered)
    finally:
        held.close()


def test_unicode_error_from_the_opener_is_connection_failed(monkeypatch):
    def boom(self, fullurl, data=None, timeout=socket._GLOBAL_DEFAULT_TIMEOUT):
        raise UnicodeEncodeError(
            "latin-1", "Bearer " + _SECRET + "-\u20ac", 0, 1, "not latin-1",
        )

    monkeypatch.setattr(urllib.request.OpenerDirector, "open", boom)
    _arm(monkeypatch)
    with pytest.raises(ProviderConnectionError) as caught:
        _generate(OpenAICompatibleProvider())
    assert str(caught.value) == "connection failed"
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__ is True
    rendered = str(caught.value) + _traceback(caught.value)
    assert "\u20ac" not in rendered
    _forbid(rendered)


def test_deadline_socket_waits_for_its_reader():
    left, right = socket.socketpair()
    try:
        wrapped = compat_module._DeadlineSocket(left, time.monotonic() + 5)
        reader = wrapped.makefile("rb")
        wrapped.close()
        right.sendall(b"still-open")
        assert reader.read(10) == b"still-open"
        reader.close()
        assert left.fileno() == -1
    finally:
        right.close()
        left.close()


def test_read_capped_stops_a_finite_stream_near_the_cap():
    class Source:
        def __init__(self, payload: bytes) -> None:
            self.payload = payload
            self.pos = 0

        def read(self, amt: int) -> bytes:
            if self.pos >= len(self.payload):
                return b""
            chunk = self.payload[self.pos:self.pos + amt]
            self.pos += len(chunk)
            return chunk

    source = Source(b"x" * (4 * 1024 * 1024))
    with pytest.raises(MalformedProviderResponse):
        compat_module._read_capped(source, None)
    assert MAX_RESPONSE_BYTES < source.pos <= MAX_RESPONSE_BYTES + 65536


def test_provider_semaphore_is_released(monkeypatch):
    monkeypatch.setenv("NESTED_WORLDS_OPENAI_COMPATIBLE_CONCURRENCY", "1")
    _arm(monkeypatch)

    def fail(request):
        raise ProviderConnectionError()

    failing = OpenAICompatibleProvider(transport=fail)
    monkeypatch.setattr(runtime, "get_provider", lambda: failing)
    gate = runtime._semaphore_for("openai_compatible")
    assert gate.acquire(blocking=False)
    gate.release()
    with pytest.raises(ProviderConnectionError):
        runtime.generate(
            endpoint="speak", model="compat-node", max_tokens=8,
            system=(SystemBlock("bible"),),
            messages=[{"role": "user", "content": "hi"}],
        )
    assert gate.acquire(blocking=False)
    gate.release()

    def succeed(request):
        return (200, (), _chat_body(content="released"))

    monkeypatch.setattr(
        runtime, "get_provider",
        lambda: OpenAICompatibleProvider(transport=succeed),
    )
    box = []

    def second():
        try:
            box.append(runtime.generate(
                endpoint="speak", model="compat-node", max_tokens=8,
                system=(SystemBlock("bible"),),
                messages=[{"role": "user", "content": "hi"}],
            ).text)
        except Exception as exc:
            box.append(exc)

    worker = threading.Thread(target=second, daemon=True)
    worker.start()
    worker.join(1)
    assert not worker.is_alive()
    assert box == ["released"]
    assert gate.acquire(blocking=False)
    gate.release()


def test_bearer_list_is_not_a_live_local(monkeypatch):
    provider_file = compat_module.__file__

    def transport(request):
        frame = sys._getframe()
        while frame is not None:
            if frame.f_code.co_filename == provider_file:
                for name, value in frame.f_locals.items():
                    assert name != "headers"
                    rendered = repr(value)
                    assert _SECRET not in rendered
                    assert "Bearer" not in rendered
            frame = frame.f_back
        assert ("Authorization", f"Bearer {_SECRET}") in request.headers
        return (200, (), _chat_body(content="sent"))

    _arm(monkeypatch)
    result = _generate(OpenAICompatibleProvider(transport=transport))
    assert result.text == "sent"


def test_status_and_no_redirect_raise_on_their_own():
    status = compat_module._Status()

    class Response:
        def __init__(self, code):
            self.code = code
            self.msg = "Found"

        def info(self):
            return {}

    with pytest.raises(ProviderHTTPError) as caught:
        status.http_response(None, Response(302))
    assert caught.value.status == 302
    assert str(caught.value) == "HTTP 302"
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__ is True
    ok = Response(200)
    assert status.http_response(None, ok) is ok
    with pytest.raises(ProviderHTTPError) as caught:
        status.https_response(None, Response(308))
    assert caught.value.status == 308
    redirect = compat_module._NoRedirect()
    for name, code in (
        ("http_error_301", 301),
        ("http_error_302", 302),
        ("http_error_303", 303),
        ("http_error_307", 307),
        ("http_error_308", 308),
    ):
        with pytest.raises(ProviderHTTPError) as caught:
            getattr(redirect, name)(None, None, code, "Moved", {})
        assert caught.value.status == code
        assert caught.value.__cause__ is None
        assert "Moved" not in str(caught.value)
    with pytest.raises(ProviderHTTPError) as caught:
        redirect.redirect_request(None, None, 301, "Moved", {}, "http://evil.example/next")
    assert caught.value.status == 301
    assert str(caught.value) == "HTTP 301"
    assert "evil" not in str(caught.value)


def test_models_names_an_unconfigured_provider_without_the_value(monkeypatch, capsys):
    from main import main

    secret_url = "https://user:pass@secret-host.example/v1?token=abc"
    _arm(monkeypatch, url=secret_url, key="sk-test-\u20ac")
    main(["models"])
    out = capsys.readouterr().out
    assert "provider not configured" in out
    assert "secret-host" not in out
    assert "user:pass" not in out
    assert "token=abc" not in out
    assert "\u20ac" not in out
    _arm(monkeypatch)
    main(["models"])
    configured = capsys.readouterr().out
    assert "text provider: openai_compatible" in configured
    assert "provider not configured" not in configured


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
