"""Anthropic-specific transport and wire format; no world or player rules."""
from __future__ import annotations

import os
import re
import threading
from typing import Any

from consciousness.runtime import Completion, SystemBlock, TokenUsage


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

    def generate(self, *, model: str, system: tuple[SystemBlock, ...],
                 messages: list[dict[str, str]], max_tokens: int,
                 json_schema: dict | None = None,
                 timeout: float | None = None) -> Completion:
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
        if json_schema is not None:
            kwargs["output_config"] = {"format": {"type": "json_schema", "schema": json_schema}}
        if timeout is not None:
            kwargs["timeout"] = timeout
        response = self._get_client().messages.create(**kwargs)
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
