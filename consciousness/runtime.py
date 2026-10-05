"""Small text-provider boundary; world prompts and validators stay with their tasks.

Only Anthropic is implemented today. Adding a provider requires an adapter and
explicit selection wiring here, plus contract and live-task evaluation (ADR-034).
"""
from __future__ import annotations

from dataclasses import dataclass
import logging
import os
import threading
from typing import Protocol


DEFAULT_VOICE_MODEL = "claude-opus-4-8"
VOICE_MODEL = os.environ.get("NESTED_WORLDS_MODEL", DEFAULT_VOICE_MODEL)
DEFAULT_MODERATION_MODEL = "claude-haiku-4-5"


@dataclass(frozen=True)
class SystemBlock:
    text: str
    cacheable: bool = False


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_write_tokens: int | None = None


class NoTextError(ValueError):
    """Safe diagnostic containing only normalized completion metadata."""


@dataclass(frozen=True)
class Completion:
    text: str | None
    complete: bool
    usage: TokenUsage | None = None
    finish_reason: str = "unknown"

    def require_text(self) -> str:
        # Preserve voice behavior for partial text; only a missing block fails.
        if self.text is None:
            raise NoTextError(f"No text in model response (complete={self.complete}, finish={self.finish_reason})")
        return self.text


def failure_summary(exc: Exception) -> str:
    # SDK error bodies can contain submitted text or credentials. Keep operator
    # diagnostics to an error class or our own normalized completion metadata.
    return str(exc) if isinstance(exc, NoTextError) else type(exc).__name__


class TextProvider(Protocol):
    name: str

    def configured(self) -> bool: ...

    def cache_reference_tokens(self, model: str) -> int | None:
        """Advisory threshold for a known model; None means not established."""
        ...

    def generate(self, *, model: str, system: tuple[SystemBlock, ...],
                 messages: list[dict[str, str]], max_tokens: int,
                 json_schema: dict | None = None,
                 timeout: float | None = None) -> Completion:
        """Honor a requested schema or raise; never silently drop it.

        `complete` is true only for normal completion, never refusal or
        truncation. Missing usage stays unknown. Cacheable blocks are an
        optional optimization; messages and their ordering must be preserved.
        """
        ...


def get_provider() -> TextProvider:
    from consciousness.anthropic_provider import provider
    return provider


def configured() -> bool:
    return get_provider().configured()


def _concurrency_limit() -> int:
    # Keep the existing operator setting and shared limit across all text tasks.
    raw = os.environ.get("NESTED_WORLDS_ANTHROPIC_CONCURRENCY", "").strip()
    try:
        return max(1, int(raw)) if raw else 8
    except ValueError:
        return 8


_call_semaphore = threading.BoundedSemaphore(_concurrency_limit())
_log = logging.getLogger("nested_worlds.consciousness")


def generate(*, endpoint: str, model: str, system: tuple[SystemBlock, ...],
             messages: list[dict[str, str]], max_tokens: int,
             json_schema: dict | None = None,
             timeout: float | None = None) -> Completion:
    provider = get_provider()
    with _call_semaphore:
        result = provider.generate(model=model, system=system, messages=messages,
                                   max_tokens=max_tokens, json_schema=json_schema,
                                   timeout=timeout)
    usage = result.usage
    if usage is not None:
        _log.info(
            "model_call provider=%s model=%s endpoint=%s input=%s "
            "cache_read=%s cache_create=%s output=%s",
            provider.name, model, endpoint, usage.input_tokens,
            usage.cache_read_tokens, usage.cache_write_tokens, usage.output_tokens,
        )
    return result
