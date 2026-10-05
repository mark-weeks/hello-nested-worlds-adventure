"""Anthropic-specific transport and wire format; no world or player rules."""
from __future__ import annotations

import os
import threading
from typing import Any

from consciousness.runtime import Completion, SystemBlock, TokenUsage


class AnthropicProvider:
    name = "anthropic"

    def __init__(self) -> None:
        self._client: Any = None
        self._client_lock = threading.Lock()

    def configured(self) -> bool:
        return bool(os.environ.get("ANTHROPIC_API_KEY"))

    def cache_reference_tokens(self, model: str) -> int | None:
        # Retain the existing integration's reference guard, not a claim that
        # this ID is currently available. Other IDs need verified cache metadata.
        return 4096 if model == "claude-opus-4-8" else None

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
        return Completion(text=text, complete=getattr(response, "stop_reason", None) == "end_turn",
                          usage=usage)


provider = AnthropicProvider()
