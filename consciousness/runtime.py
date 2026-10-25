"""Small text-provider boundary; world prompts and validators stay with their tasks.

Only Anthropic is implemented today. Adding a provider requires an adapter and
explicit selection wiring here, plus contract and live-task evaluation (ADR-034).
Per-task settings choose a model id on that provider. An id never selects or
replaces the provider, and a failed call is never retried on another id.
"""
from __future__ import annotations

from dataclasses import dataclass
import logging
import os
import threading
from typing import Protocol


DEFAULT_VOICE_MODEL = "claude-opus-4-8"
DEFAULT_MODERATION_MODEL = "claude-haiku-4-5"

SHARED_MODEL_ENV = "NESTED_WORLDS_MODEL"
NODE_MODEL_ENV = "NESTED_WORLDS_NODE_MODEL"
INHABITANT_MODEL_ENV = "NESTED_WORLDS_INHABITANT_MODEL"
INTENT_MODEL_ENV = "NESTED_WORLDS_INTENT_MODEL"
MODERATION_MODEL_ENV = "NESTED_WORLDS_MODERATION_MODEL"

NODE_TASK = "node"
INHABITANT_TASK = "inhabitant"
INTENT_TASK = "intent"
MODERATION_TASK = "moderation"

_TASK_ENV = {
    NODE_TASK: NODE_MODEL_ENV,
    INHABITANT_TASK: INHABITANT_MODEL_ENV,
    INTENT_TASK: INTENT_MODEL_ENV,
    MODERATION_TASK: MODERATION_MODEL_ENV,
}


def _nonblank(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


# Import-time shared id. Calls use model_for(), which reads the environment
# on each call. Blank or whitespace-only values are unset.
VOICE_MODEL = _nonblank(os.environ.get(SHARED_MODEL_ENV)) or DEFAULT_VOICE_MODEL


def model_for(task: str) -> str:
    """Model id for one text task. An id never selects a provider.

    Node voice, inhabitant voice, and intention use their own settings, then
    the shared model, then the voice default. Moderation keeps its own default
    and does not inherit the shared model. This function does not retry or
    substitute another id when a call fails.
    """
    try:
        env_name = _TASK_ENV[task]
    except KeyError:
        raise ValueError(f"unknown model task {task!r}") from None
    chosen = _nonblank(os.environ.get(env_name))
    if chosen is not None:
        return chosen
    if task == MODERATION_TASK:
        return DEFAULT_MODERATION_MODEL
    return _nonblank(os.environ.get(SHARED_MODEL_ENV)) or DEFAULT_VOICE_MODEL


def configured_models() -> dict[str, str]:
    """Resolved model id for every text task. Ids only; no credentials."""
    return {task: model_for(task) for task in _TASK_ENV}


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
    resolved_model: str | None = None
    provider: str | None = None

    def require_text(self) -> str:
        # Preserve voice behavior for partial text; only a missing block fails.
        if self.text is None:
            raise NoTextError(f"No text in model response (complete={self.complete}, finish={self.finish_reason})")
        return self.text


class Voiced(str):
    """Model text that still compares and serializes as that text.

    `provider` and `resolved_model` are copied from the Completion that
    produced the text. A plain str is authored fallback text and has neither
    attribute. Slicing returns a plain str, so read the attributes first.
    """

    def __new__(cls, text: str, provider: str | None, resolved_model: str | None):
        obj = str.__new__(cls, text)
        obj.provider = provider
        obj.resolved_model = resolved_model
        return obj

    def __reduce_ex__(self, protocol):
        # str's reducer rebuilds through __new__ with only the characters.
        # Eval snapshots deepcopy the spoken line, so the call result must travel.
        return (type(self), (str(self), self.provider, self.resolved_model))


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
