"""Anthropic-specific transport and wire format; no world or player rules."""
from __future__ import annotations

import math
import os
import re
import threading
from typing import Any

from consciousness.runtime import (
    Completion,
    MODERATION_TASK,
    SystemBlock,
    TokenUsage,
)


# This adapter's ids. They stay here so shared code does not name them.
# Another adapter does not inherit them. ``model_for`` asks ``default_model``.
DEFAULT_VOICE_MODEL = "claude-opus-4-8"
DEFAULT_MODERATION_MODEL = "claude-haiku-4-5"


# Claude API cache minima, verified 2026-10-05:
# https://platform.claude.com/docs/en/build-with-claude/prompt-caching#cache-limitations
# Match known versions only, not an entire family or future versions.
_CACHE_REFERENCES = {
    "claude-opus-4-5": 4096,
    "claude-opus-4-6": 4096,
    "claude-opus-4-7": 2048,
    "claude-opus-4-8": 1024,
    "claude-sonnet-4-5": 1024,
    "claude-sonnet-4-6": 1024,
    "claude-haiku-4-5": 4096,
}
_FINISH_REASONS = {
    "end_turn": "complete", "stop_sequence": "stop", "max_tokens": "length",
    "refusal": "refusal", "tool_use": "tool", "pause_turn": "pause",
}
# Known releases only. A dated snapshot of one of these is the same release.
# Anything else that still names Claude, or any id behind a base-URL gateway,
# warns. A hard reject is reserved for an id this API cannot be asked to serve
# and for text that is not an id at all. A gateway alias must not take the
# process down.
_KNOWN_MODEL_IDS = frozenset(_CACHE_REFERENCES)
_DATED_SNAPSHOT = re.compile(r"-\d{8}$")
_BASE_URL_ENV = "ANTHROPIC_BASE_URL"
_MAX_MODEL_ID_LENGTH = 256

# Per-attempt timeout for a call whose caller passes none (node voice,
# inhabitant voice, intention). Without it the pinned SDK computes 600 s
# read, 5 s connect for a non-streaming call (anthropic 0.120.2,
# resources/messages/messages.py:1030 and _base_client.py:769), and retries
# twice. The SDK's retries stay on: each of up to three attempts gets this.
# 60 is a judgement, not a measurement: no live latency for these tasks is
# on record (docs/development/agent-runtime.md gives the reasoning).
TIMEOUT_ENV = "NESTED_WORLDS_ANTHROPIC_TIMEOUT_SECONDS"
DEFAULT_TIMEOUT_SECONDS = 60.0
# The pinned SDK's own connect timeout (anthropic/_constants.py:9).
_CONNECT_TIMEOUT_SECONDS = 5.0


def _default_timeout_seconds() -> float:
    """``NESTED_WORLDS_ANTHROPIC_TIMEOUT_SECONDS``, read on every call.

    Unset, blank, non-numeric, non-finite, zero or negative means 60, the
    same parsing as ``NESTED_WORLDS_OPENAI_COMPATIBLE_TIMEOUT_SECONDS``.
    A larger value than ``threading.TIMEOUT_MAX`` is capped there, as the
    slot wait is: past it a socket wait overflows, and every call failed
    with a connection error before sending anything.
    """
    raw = os.environ.get(TIMEOUT_ENV)
    if raw is None or not raw.strip():
        return DEFAULT_TIMEOUT_SECONDS
    try:
        value = float(raw.strip())
    except ValueError:
        return DEFAULT_TIMEOUT_SECONDS
    if not math.isfinite(value) or value <= 0:
        return DEFAULT_TIMEOUT_SECONDS
    return min(value, threading.TIMEOUT_MAX)


def _default_request_timeout(client: Any) -> Any:
    """The timeout to send when the caller passed none, or None to send none.

    The SDK hands it to httpx on every attempt: read, write and pool are the
    setting, and connect stays the SDK's 5 s (less when the setting is
    smaller). Read is the longest wait for the next bytes, not a deadline
    for the whole response.

    A client whose own timeout is not the SDK default keeps it, the rule the
    SDK itself uses before computing its 600 s (messages.py:1030): the
    evaluation harness sets the candidate's ``timeout_seconds`` that way
    (``evals/harness.py``), and a per-request value would override it.
    Sending a timeout also skips that computation's refusal of a large
    non-streaming ``max_tokens`` (above about 21,000, lower for a few older
    models); these tasks ask 500 at most.
    """
    import httpx
    from anthropic import DEFAULT_TIMEOUT
    if getattr(client, "timeout", DEFAULT_TIMEOUT) != DEFAULT_TIMEOUT:
        return None
    seconds = _default_timeout_seconds()
    return httpx.Timeout(seconds, connect=min(_CONNECT_TIMEOUT_SECONDS, seconds))


def _unusable_model_id(model: object) -> bool:
    if not isinstance(model, str) or model == "":
        return True
    if any(ch.isspace() for ch in model):
        return True
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in model):
        return True
    return len(model) > _MAX_MODEL_ID_LENGTH


def _base_url_override() -> bool:
    # Same variable the pinned SDK reads before its default API host.
    # A blank value is unset. The value itself is never logged.
    raw = os.environ.get(_BASE_URL_ENV)
    return bool(raw and raw.strip())


def _anthropic_model_verdict(model: str) -> str:
    """ok, warn, or reject.

    Exact known ids are ok. A Claude name in another shape (mixed case,
    ``anthropic/claude-…``, ``….anthropic.claude-…-v1:0``, a ``:beta`` suffix)
    warns. With ``ANTHROPIC_BASE_URL`` set, every other usable id warns too,
    because a gateway alias is not a Claude id. Reject only unusable text,
    or an id that neither names Claude nor sits behind that override.
    """
    if _unusable_model_id(model):
        return "reject"
    base = _DATED_SNAPSHOT.sub("", model)
    if model in _KNOWN_MODEL_IDS or base in _KNOWN_MODEL_IDS:
        return "ok"
    if "claude" in model.lower() or _base_url_override():
        return "warn"
    return "reject"


class AnthropicProvider:
    name = "anthropic"
    # Optional extra. The SDK is imported only when a client is built.
    sdk_module = "anthropic"
    distribution_extra = "anthropic"

    def __init__(self) -> None:
        self._client: Any = None
        self._client_lock = threading.Lock()
        # (base client, its copy with SDK retries off). One tuple, so a
        # reader never pairs one base with another base's copy.
        self._deadline_pair: tuple[Any, Any] | None = None

    def configured(self) -> bool:
        # SDK construction resolves local credentials without making a request.
        # Include its bearer-token and profile/federation sources, so this gate
        # agrees with the client that will actually send the call.
        try:
            client = self._get_client()
        except Exception:
            return False
        return bool(client.api_key or client.auth_token or getattr(client, "credentials", None))

    def model_id_validator(self):
        # Prefix and known-release knowledge stays on this adapter.
        return _anthropic_model_verdict

    def default_model(self, task: str) -> str:
        """Ids this adapter uses when no setting names one.

        Node voice, inhabitant voice, and intention share the voice id.
        Moderation keeps its own and does not inherit the shared model.
        Another adapter does not receive these ids.
        """
        if task == MODERATION_TASK:
            return DEFAULT_MODERATION_MODEL
        return DEFAULT_VOICE_MODEL

    def cache_reference_tokens(self, model: str) -> int | None:
        # A dated snapshot of a known version uses that version's reference.
        # This advisory metadata does not certify that an ID is available.
        version = re.sub(r"-\d{8}$", "", model)
        return _CACHE_REFERENCES.get(version)

    def _get_client(self) -> Any:
        if self._client is None:
            with self._client_lock:
                if self._client is None:
                    from anthropic import Anthropic
                    self._client = Anthropic()
        return self._client

    def _get_deadline_client(self) -> Any:
        """The client for a call whose caller gave a timeout: no SDK retries.

        ``messages.create`` takes no per-request ``max_retries``.
        ``with_options(max_retries=0)`` returns a copy that keeps the base
        client's HTTP connection pool, credentials (key, bearer token, or
        profile provider with its token cache), base URL and headers, so
        ``configured()`` still describes the client that sends the call.
        Built once per base client; a replaced ``_client`` (the eval harness
        installs its own) gets its own copy.
        """
        base = self._get_client()
        pair = self._deadline_pair
        if pair is None or pair[0] is not base:
            with self._client_lock:
                pair = self._deadline_pair
                if pair is None or pair[0] is not base:
                    pair = (base, base.with_options(max_retries=0))
                    self._deadline_pair = pair
        return pair[1]

    def _client_for(self, timeout: float | None) -> Any:
        # A caller's timeout allows one attempt and no retries
        # (runtime.TextProvider.generate): the SDK's retries, and the
        # retry-after waits between them, would spend past it. httpx applies
        # the number to connect, write, pool and each read, not as one
        # wall-clock deadline. Against a local stub at 3 s, one attempt took
        # 3.01 s when the provider never answered and 6.01 s when it sent
        # its body a chunk a second.
        if timeout is not None:
            return self._get_deadline_client()
        return self._get_client()

    def generate(self, *, model: str, system: tuple[SystemBlock, ...],
                 messages: list[dict[str, str]], max_tokens: int,
                 json_schema: dict | None = None,
                 timeout: float | None = None) -> Completion:
        # This adapter has not yet earned a controlled one-attempt,
        # no-redirect dispatch path. Keep legacy SDK behavior only locally.
        from consciousness import model_dispatch
        model_dispatch.validate_adapter_call(self)
        if len(system) == 1 and not system[0].cacheable:
            wire_system: str | list[dict] = system[0].text
        else:
            wire_system = []
            for block in system:
                item: dict = {"type": "text", "text": block.text}
                if block.cacheable:
                    item["cache_control"] = {"type": "ephemeral", "ttl": "1h"}
                wire_system.append(item)
        kwargs: dict = dict(model=model, system=wire_system, messages=messages,
                            max_tokens=max_tokens)
        if timeout is None:
            # Voice, inhabitant and intention: this adapter's per-attempt
            # default; the SDK's own retries are left as they are.
            default_timeout = _default_request_timeout(self._get_client())
            if default_timeout is not None:
                kwargs["timeout"] = default_timeout
        if json_schema is not None:
            kwargs["output_config"] = {"format": {"type": "json_schema", "schema": json_schema}}
        if timeout is not None:
            kwargs["timeout"] = timeout
        response = self._client_for(timeout).messages.create(**kwargs)
        text = next((block.text for block in response.content if block.type == "text"), None)
        raw = getattr(response, "usage", None)
        usage = None if raw is None else TokenUsage(
            input_tokens=getattr(raw, "input_tokens", None),
            output_tokens=getattr(raw, "output_tokens", None),
            cache_read_tokens=getattr(raw, "cache_read_input_tokens", None),
            cache_write_tokens=getattr(raw, "cache_creation_input_tokens", None),
        )
        stop = getattr(response, "stop_reason", None)
        return Completion(text=text, complete=stop == "end_turn", usage=usage,
                          finish_reason=_FINISH_REASONS.get(stop, "unknown"),
                          resolved_model=getattr(response, "model", None),
                          provider=self.name)


provider = AnthropicProvider()
