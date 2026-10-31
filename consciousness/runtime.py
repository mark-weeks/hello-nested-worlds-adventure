"""Small text-provider boundary; world prompts and validators stay with their tasks.

``NESTED_WORLDS_PROVIDER`` selects a registered adapter. Unset means
``anthropic``, the only built-in adapter. An unknown name fails startup.
The first successful selection is cached for the process. Per-task
settings choose a model id on that provider. When no setting names an id,
the selected adapter's own ``default_model`` supplies it. An adapter that
omits that method does not inherit another adapter's ids. An id never
selects or replaces the provider, and a failed call is never retried on
another id or another provider. Adding a provider still requires an
adapter, a registry entry, and contract evaluation (ADR-034). This module
does not import a provider SDK.
"""
from __future__ import annotations

from dataclasses import dataclass
import importlib
import logging
import os
import re
import threading
from typing import Callable, Protocol


# The anthropic adapter's defaults. Another adapter does not inherit them.
# ``model_for`` asks the selected adapter. These constants keep one spelling
# for that adapter and for the import-time ``VOICE_MODEL`` snapshot.
DEFAULT_VOICE_MODEL = "claude-opus-4-8"
DEFAULT_MODERATION_MODEL = "claude-haiku-4-5"

SHARED_MODEL_ENV = "NESTED_WORLDS_MODEL"
NODE_MODEL_ENV = "NESTED_WORLDS_NODE_MODEL"
INHABITANT_MODEL_ENV = "NESTED_WORLDS_INHABITANT_MODEL"
INTENT_MODEL_ENV = "NESTED_WORLDS_INTENT_MODEL"
MODERATION_MODEL_ENV = "NESTED_WORLDS_MODERATION_MODEL"

# One adapter for every text task. Unset keeps the current adapter.
PROVIDER_ENV = "NESTED_WORLDS_PROVIDER"
DEFAULT_PROVIDER = "anthropic"
_PROVIDER_NAME = re.compile(r"[a-z][a-z0-9_]{0,32}")

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
# on each call and then the selected adapter's default. Blank or
# whitespace-only values are unset. This snapshot uses the anthropic voice
# default when the shared setting is unset at import.
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
    ``adapter_default`` is true when ``source`` is ``default`` and the
    selected adapter supplied the id. A default with no adapter id leaves
    ``model`` empty so another adapter's id is not sent.
    """

    task: str
    model: str
    source: str
    env_var: str
    raw: str | None
    ignored_blank: tuple[tuple[str, str], ...] = ()
    adapter_default: bool = False


def _blank_kind(value: str) -> str:
    return "empty" if value == "" else "whitespace"


def _supplied_default(provider: TextProvider, task: str) -> str | None:
    """Non-blank id from an optional ``default_model`` method.

    The method is not part of ``TextProvider``. An adapter that omits it,
    or returns a blank or a non-string, does not inherit another adapter's
    ids. A raising method is a bug in that adapter and propagates.
    """
    method = getattr(provider, "default_model", None)
    if not callable(method):
        return None
    value = method(task)
    if not isinstance(value, str):
        return None
    return _nonblank(value)


def _provider_for_defaults(provider: TextProvider | None) -> TextProvider:
    """Adapter that owns the default id. This is not a model call.

    Omitted, it is ``get_provider()``, the same seam ``generate`` sends the
    call through, so a default id always comes from the adapter that will
    receive it. Replacing ``get_provider`` replaces both together. Looking
    up the adapter does not contact it; the voice budget gates
    ``provider.generate``, not this lookup. A later environment change does
    not switch the cached adapter.
    """
    if provider is not None:
        return provider
    return get_provider()


def _default_resolution(task: str, env_name: str, blanks: list[tuple[str, str]],
                        provider: TextProvider | None) -> ModelResolution:
    chosen = _supplied_default(_provider_for_defaults(provider), task)
    if chosen is None:
        return ModelResolution(
            task, "", SOURCE_DEFAULT, env_name, None, tuple(blanks),
            adapter_default=False,
        )
    return ModelResolution(
        task, chosen, SOURCE_DEFAULT, env_name, None, tuple(blanks),
        adapter_default=True,
    )


def resolve_model(task: str, provider: TextProvider | None = None) -> ModelResolution:
    """Same rules as ``model_for``, plus the setting that supplied the id.

    ``provider`` is the adapter whose ``default_model`` applies. Omit it to
    use the selected adapter. A task setting, then the shared model for
    every task except moderation, still wins over that default.
    """
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
    return _default_resolution(task, env_name, blanks, provider)


def model_for(task: str) -> str:
    """Model id for one text task. An id never selects a provider.

    Node voice, inhabitant voice, and intention use their own settings, then
    the shared model, then the selected adapter's default. Moderation uses
    its own setting, then that adapter's moderation default, and does not
    inherit the shared model. An adapter with no default leaves the id
    empty. Empty and whitespace-only settings are unset here and fall back.
    The startup check reports those blanks, and a default the adapter did
    not supply, and refuses to serve. This function does not retry or
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
    """Text adapter. Id judgment and default ids are not part of this protocol.

    Adapters that know which ids they serve also match
    ``ModelIdJudgingProvider``. The startup check uses getattr, so an
    adapter that omits ``model_id_validator`` is not asked and still
    satisfies this protocol for type checkers. ``default_model(task)`` is
    also optional. It returns the id to use when no setting names one.
    Omitting it does not borrow another adapter's ids.
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


def _load_anthropic() -> TextProvider:
    # The adapter module does not import the SDK. Startup checks that.
    from consciousness.anthropic_provider import provider
    return provider


_BUILTINS: dict[str, Callable[[], TextProvider]] = {
    DEFAULT_PROVIDER: _load_anthropic,
}
_REGISTERED: dict[str, Callable[[], TextProvider]] = {}
_registry_lock = threading.Lock()
# First successful selection. A failed selection is not stored. Tests clear
# this with reset_provider_selection so a later case can select again.
_selected_provider: TextProvider | None = None
_selection_lock = threading.Lock()


def provider_names() -> tuple[str, ...]:
    """Registered adapter names, built-ins included. No credentials."""
    with _registry_lock:
        names = set(_BUILTINS) | set(_REGISTERED)
    return tuple(sorted(names))


def _valid_suffix() -> str:
    return "valid: " + ", ".join(provider_names())


def register_provider(name: str, factory: Callable[[], TextProvider]) -> None:
    """Add a named adapter. A built-in name cannot be replaced.

    The name is a short token. It is not a model id and it does not select
    a vendor by guessing. Tests register a fixture here; a future adapter
    registers the same way.
    """
    text = name.strip().lower()
    if _PROVIDER_NAME.fullmatch(text) is None:
        raise ValueError(
            f"provider name {name!r} must be a short lowercase token"
        )
    if text in _BUILTINS:
        raise ValueError(f"{text} is a built-in text provider")
    if not callable(factory):
        raise TypeError("provider factory must be callable")
    with _registry_lock:
        _REGISTERED[text] = factory


def selected_provider_name() -> str:
    """Registry key for this process. Unset means ``anthropic``.

    The value is stripped and lowercased. Empty or whitespace-only is a
    misconfiguration. This does not import a provider SDK.
    """
    if PROVIDER_ENV not in os.environ:
        return DEFAULT_PROVIDER
    text = os.environ[PROVIDER_ENV].strip().lower()
    if not text:
        raise SystemExit(f"{PROVIDER_ENV} is empty ({_valid_suffix()})")
    if _PROVIDER_NAME.fullmatch(text) is None:
        # Do not echo an unsafe value. It might be a pasted credential.
        raise SystemExit(
            f"{PROVIDER_ENV} is not a known text provider ({_valid_suffix()})"
        )
    return text


def reset_provider_selection() -> None:
    """Forget the adapter chosen for this process.

    ``get_provider`` validates ``NESTED_WORLDS_PROVIDER`` once and keeps
    that adapter. Tests call this so a later case can select again. A
    failed selection is not cached, so a corrected value can be read on
    the next call without this reset.
    """
    global _selected_provider
    with _selection_lock:
        _selected_provider = None


def _load_selected_provider() -> TextProvider:
    """Validate and cache ``NESTED_WORLDS_PROVIDER``. Does not import an SDK.

    Callers go through ``get_provider``, never here directly, so default ids
    and calls share one seam. A failed selection is not cached.
    """
    global _selected_provider
    with _selection_lock:
        if _selected_provider is not None:
            return _selected_provider
    name = selected_provider_name()
    with _registry_lock:
        factory = _BUILTINS.get(name)
        if factory is None:
            factory = _REGISTERED.get(name)
    if factory is None:
        raise SystemExit(
            f"{PROVIDER_ENV}={name!r} is not a known text provider "
            f"({_valid_suffix()})"
        )
    provider = factory()
    with _selection_lock:
        if _selected_provider is None:
            _selected_provider = provider
        return _selected_provider


def get_provider() -> TextProvider:
    """The adapter named by ``NESTED_WORLDS_PROVIDER``, chosen once.

    The first successful call validates the name and builds the adapter.
    Later calls return that adapter and do not read the environment again,
    so a bad value set during a request cannot raise ``SystemExit`` on a
    request thread. An unknown name on the first call still raises
    ``SystemExit`` with one line naming that variable and the valid names.
    The same line is what ``python main.py serve`` exits with, before it
    opens a port. ``reset_provider_selection`` clears the cache. This does
    not import a provider SDK. ``model_for`` asks this adapter for default
    ids and ``generate`` sends the call to it, so both always name the same
    adapter. The lookup is not a model call: ``generate`` reaches
    ``provider.generate`` only after the voice budget.
    """
    return _load_selected_provider()


def installation_error(provider: TextProvider) -> str | None:
    """One-line failure when the selected adapter's own SDK is not installed.

    Adapters that do not set ``sdk_module`` need no SDK. Only a
    ``ModuleNotFoundError`` whose ``name`` is that module becomes the
    one-line failure. A missing dependency of the SDK, or any other
    ``ImportError``, propagates with its own message. The line names
    ``NESTED_WORLDS_PROVIDER`` and the optional extra. It does not include
    a credential or make a model call.
    """
    module_name = getattr(provider, "sdk_module", None)
    if not isinstance(module_name, str) or not module_name.strip():
        return None
    module_name = module_name.strip()
    try:
        importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name != module_name:
            raise
        extra = getattr(provider, "distribution_extra", None)
        if not isinstance(extra, str) or not extra.strip():
            extra = module_name
        else:
            extra = extra.strip()
        raw_name = getattr(provider, "name", None)
        if not isinstance(raw_name, str) or not raw_name.strip():
            shown = DEFAULT_PROVIDER
        else:
            shown = raw_name.strip()
        return (
            f"{PROVIDER_ENV}={shown} requires the optional extra "
            f"enfolded[{extra}] (package '{module_name}' is not installed)"
        )
    return None


def configured() -> bool:
    return get_provider().configured()


def _concurrency_env(provider_name: str) -> str:
    # Anthropic keeps NESTED_WORLDS_ANTHROPIC_CONCURRENCY. The pattern is the
    # same for every provider, so one provider's cap is not another's.
    return f"NESTED_WORLDS_{provider_name.strip().upper()}_CONCURRENCY"


def _concurrency_limit(provider_name: str = DEFAULT_PROVIDER) -> int:
    """In-flight cap for one provider. Unset, empty, or non-numeric means 8.

    Zero and negative values clamp to 1. The anthropic name is the existing
    ``NESTED_WORLDS_ANTHROPIC_CONCURRENCY`` setting.
    """
    raw = os.environ.get(_concurrency_env(provider_name), "").strip()
    try:
        return max(1, int(raw)) if raw else 8
    except ValueError:
        return 8


_semaphores: dict[str, threading.BoundedSemaphore] = {}
_semaphore_limits: dict[str, int] = {}
_semaphore_lock = threading.Lock()


def _semaphore_for(provider_name: str) -> threading.BoundedSemaphore:
    name = provider_name.strip().lower() or DEFAULT_PROVIDER
    limit = _concurrency_limit(name)
    with _semaphore_lock:
        current = _semaphores.get(name)
        if current is None or _semaphore_limits.get(name) != limit:
            current = threading.BoundedSemaphore(limit)
            _semaphores[name] = current
            _semaphore_limits[name] = limit
        return current


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
    with _semaphore_for(provider.name):
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
