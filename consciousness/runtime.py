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
from typing import Callable, Protocol


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


SOURCE_TASK_ENV = "task env"
SOURCE_SHARED = SHARED_MODEL_ENV
SOURCE_DEFAULT = "default"

# Stable task order for operator reports. Dict order matches this tuple.
TASKS = (NODE_TASK, INHABITANT_TASK, INTENT_TASK, MODERATION_TASK)


@dataclass(frozen=True)
class ModelResolution:
    """One task's model id and where it came from. No credentials.

    ``source`` is ``task env``, ``NESTED_WORLDS_MODEL``, or ``default``.
    ``ignored_blank`` lists variables that were set to empty or whitespace
    and therefore did not supply the id. ``model_for`` still falls back;
    the startup check treats those blanks as misconfiguration.
    """

    task: str
    model: str
    source: str
    env_var: str
    raw: str | None
    ignored_blank: tuple[tuple[str, str], ...] = ()


def _blank_kind(value: str) -> str:
    return "empty" if value == "" else "whitespace"


def resolve_model(task: str) -> ModelResolution:
    """Same rules as ``model_for``, plus the setting that supplied the id."""
    try:
        env_name = _TASK_ENV[task]
    except KeyError:
        raise ValueError(f"unknown model task {task!r}") from None
    blanks: list[tuple[str, str]] = []
    task_raw = os.environ.get(env_name)
    if task_raw is not None and _nonblank(task_raw) is None:
        blanks.append((env_name, _blank_kind(task_raw)))
    chosen = _nonblank(task_raw)
    if chosen is not None:
        return ModelResolution(
            task, chosen, SOURCE_TASK_ENV, env_name, task_raw, tuple(blanks),
        )
    if task != MODERATION_TASK:
        shared_raw = os.environ.get(SHARED_MODEL_ENV)
        if shared_raw is not None and _nonblank(shared_raw) is None:
            blanks.append((SHARED_MODEL_ENV, _blank_kind(shared_raw)))
        shared = _nonblank(shared_raw)
        if shared is not None:
            return ModelResolution(
                task, shared, SOURCE_SHARED, SHARED_MODEL_ENV, shared_raw, tuple(blanks),
            )
        return ModelResolution(
            task, DEFAULT_VOICE_MODEL, SOURCE_DEFAULT, env_name, None, tuple(blanks),
        )
    return ModelResolution(
        task, DEFAULT_MODERATION_MODEL, SOURCE_DEFAULT, env_name, None, tuple(blanks),
    )


def model_for(task: str) -> str:
    """Model id for one text task. An id never selects a provider.

    Node voice, inhabitant voice, and intention use their own settings, then
    the shared model, then the voice default. Moderation keeps its own default
    and does not inherit the shared model. Empty and whitespace-only values
    are unset here and fall back. The startup check reports those blanks
    separately and refuses to serve. This function does not retry or
    substitute another id when a call fails.
    """
    return resolve_model(task).model


def configured_models() -> dict[str, str]:
    """Resolved model id for every text task. Ids only; no credentials."""
    return {task: model_for(task) for task in TASKS}


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


class ModelActionLimited(Exception):
    """The per-user model-action cap refused this call.

    The provider was not contacted. An empty credential is not a refusal:
    ``reserve_model_action`` normalizes it to open.
    """


class VoiceBudgetLimited(Exception):
    """The voice budget refused this call. The provider was not contacted."""


class ModelReservation:
    """Proof that ``reserve_model_action`` already charged this credential.

    ``generate`` charges when a caller does not pass one, so a new
    model-calling surface cannot skip ``NESTED_WORLDS_MODEL_ACTIONS_PER_USER``.
    The screen reserves first, then spends the moderation budget, and passes
    the reservation through so that one classify is one charge.
    """

    __slots__ = ("key",)

    def __init__(self, key: str | None) -> None:
        self.key = key


def reserve_model_action(user_key: str | None = None) -> ModelReservation:
    """Charge one model-calling action, or raise ``ModelActionLimited``.

    This is the only ``user_key or None`` normalization. An empty string and
    ``None`` both stay open, matching a credential-less local call. The
    ``anthropic`` bucket and ``NESTED_WORLDS_ANTHROPIC_*`` are not touched.
    """
    key = user_key or None
    from server import guard
    if not guard.consume_model_action(user_key=key):
        raise ModelActionLimited()
    return ModelReservation(key)


class TextProvider(Protocol):
    """Text adapter. Id judgment is not part of this protocol.

    Adapters that know which ids they serve also match
    ``ModelIdJudgingProvider``. The startup check uses getattr, so an
    adapter that omits ``model_id_validator`` is not asked and still
    satisfies this protocol for type checkers.
    """

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


class ModelIdJudgingProvider(TextProvider, Protocol):
    """Optional. Implement this only when the adapter can judge model ids.

    The callable returns ``ok``, ``warn``, or ``reject``, or None to skip.
    ``reject`` means the id is not usable on this adapter. ``warn`` means it
    is plausible but not a known release. Omitting the method is the default.
    """

    def model_id_validator(self) -> Callable[[str], str] | None: ...


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
             timeout: float | None = None,
             user_key: str | None = None,
             reservation: ModelReservation | None = None,
             voice_budget: bool = False) -> Completion:
    """One text completion. The model-action cap runs before the provider.

    ``voice_budget`` reserves an ``anthropic`` call after that cap and before
    the provider, so a refused cap does not spend the voice budget. A
    ``ModelReservation`` from ``reserve_model_action`` is not charged again.
    """
    if not isinstance(reservation, ModelReservation):
        reservation = reserve_model_action(user_key)
    if voice_budget:
        from server import guard
        if not guard.consume_anthropic(user_key=reservation.key):
            raise VoiceBudgetLimited()
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
