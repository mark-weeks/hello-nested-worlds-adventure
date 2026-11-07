"""Small text-provider boundary; world prompts and validators stay with their tasks.

``NESTED_WORLDS_PROVIDER`` selects the process default adapter. Unset
means ``anthropic``. Each text task may override that choice with
``NESTED_WORLDS_NODE_PROVIDER``, ``NESTED_WORLDS_INHABITANT_PROVIDER``,
``NESTED_WORLDS_INTENT_PROVIDER``, or ``NESTED_WORLDS_MODERATION_PROVIDER``.
An unset task variable uses the process default. A blank, unknown, or
otherwise unusable name fails startup and does not fall through to
another adapter. Built-in adapters are ``anthropic`` and
``openai_compatible``. The second speaks OpenAI-compatible Chat
Completions to an operator-supplied base URL. It is registered for
evaluation. No destination is approved for production, and no provider
other than the current default has been evaluated or approved (ADR-034;
ADR-035 is Proposed and does not enable a destination). The first
successful selection of each provider is cached for the process.
Per-task settings choose a model id on that task's provider. When no
setting names an id, that provider's own ``default_model`` supplies it.
An adapter that omits that method does not inherit another adapter's ids.
``NESTED_WORLDS_MODEL`` is a shared model id for node voice, inhabitant
voice, and intention, including when those tasks use different providers.
It is not a provider selector and moderation never inherits it. An id
never selects or replaces the provider, and a failed call is never
retried on another id or another provider. Adding a provider still
requires an adapter, a registry entry, and contract evaluation (ADR-034).
This module does not import a provider SDK.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import importlib
import logging
import math
import os
import re
import threading
from typing import Callable, Protocol


SHARED_MODEL_ENV = "NESTED_WORLDS_MODEL"
NODE_MODEL_ENV = "NESTED_WORLDS_NODE_MODEL"
INHABITANT_MODEL_ENV = "NESTED_WORLDS_INHABITANT_MODEL"
INTENT_MODEL_ENV = "NESTED_WORLDS_INTENT_MODEL"
MODERATION_MODEL_ENV = "NESTED_WORLDS_MODERATION_MODEL"

# Process default. Unset keeps the current adapter. A task variable overrides
# it for that task only. A blank or unknown task value does not fall through.
PROVIDER_ENV = "NESTED_WORLDS_PROVIDER"
DEFAULT_PROVIDER = "anthropic"
NODE_PROVIDER_ENV = "NESTED_WORLDS_NODE_PROVIDER"
INHABITANT_PROVIDER_ENV = "NESTED_WORLDS_INHABITANT_PROVIDER"
INTENT_PROVIDER_ENV = "NESTED_WORLDS_INTENT_PROVIDER"
MODERATION_PROVIDER_ENV = "NESTED_WORLDS_MODERATION_PROVIDER"
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

_TASK_PROVIDER_ENV = {
    NODE_TASK: NODE_PROVIDER_ENV,
    INHABITANT_TASK: INHABITANT_PROVIDER_ENV,
    INTENT_TASK: INTENT_PROVIDER_ENV,
    MODERATION_TASK: MODERATION_PROVIDER_ENV,
}


def _nonblank(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


SOURCE_TASK_ENV = "task env"
SOURCE_SHARED = SHARED_MODEL_ENV
SOURCE_DEFAULT = "default"
SOURCE_PROVIDER_TASK = "task env"
SOURCE_PROVIDER_PROCESS = PROVIDER_ENV
SOURCE_PROVIDER_DEFAULT = "default"

# Stable task order for operator reports. Dict order matches this tuple.
TASKS = (NODE_TASK, INHABITANT_TASK, INTENT_TASK, MODERATION_TASK)
TASK_PROVIDER_ENVS = tuple(_TASK_PROVIDER_ENV[task] for task in TASKS)


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


def _provider_for_defaults(provider: TextProvider | None, task: str) -> TextProvider:
    """Adapter that owns this task's default id. This is not a model call.

    Omitted, it is ``provider_for(task)``, the same adapter ``generate``
    sends that task's call through, so a default id always comes from the
    adapter that will receive it. A task with no provider override shares
    ``get_provider()``. Replacing ``get_provider`` replaces both for those
    tasks. Looking up the adapter does not contact it; the voice budget
    gates ``provider.generate``, not this lookup. A later environment
    change does not switch a cached adapter.
    """
    if provider is not None:
        return provider
    return provider_for(task)


def _default_resolution(task: str, env_name: str, blanks: list[tuple[str, str]],
                        provider: TextProvider | None) -> ModelResolution:
    chosen = _supplied_default(_provider_for_defaults(provider, task), task)
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
    use that task's provider. A task setting, then the shared model for
    every task except moderation, still wins over that default. The shared
    model is an id, so it applies even when the task's provider is not the
    process default. It never supplies moderation's id, and it never
    supplies another adapter's ``default_model``.
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
    the shared model, then that task's provider's default. Moderation uses
    its own setting, then that task's provider's moderation default, and
    does not inherit the shared model. An adapter with no default leaves
    the id empty and does not inherit another adapter's ids, including when
    other tasks still use those ids. Empty and whitespace-only settings are
    unset here and fall back. The startup check reports those blanks, and a
    default the task's provider did not supply, and refuses to serve. This
    function does not retry or substitute another id when a call fails.
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


class ProviderBusy(Exception):
    """No in-flight slot for the selected provider opened within the wait.

    ``generate`` raises this after the model-action cap and the voice budget
    when every slot under ``NESTED_WORLDS_<NAME>_CONCURRENCY`` stayed taken
    for the whole wait (``_slot_wait``). The provider was not contacted and
    no slot is held. Charges already taken stand, as they do for every
    failure after the charge: the cost ledger has no refund.
    """


class UnusableModelId(Exception):
    """The model id is missing or blank.

    ``generate`` raises this before the model-action cap and before any
    voice or provider budget. The provider is not called. The message does
    not include the id: a value pasted into a model setting might be a
    credential. Moderation holds shared text when this escapes a classify.
    """


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


def require_model_id(model: object) -> str:
    """Return ``model`` when it is a non-blank string.

    Otherwise raise ``UnusableModelId``. This does not charge a budget and
    does not call a provider. The id itself is not included in the error.
    """
    if not isinstance(model, str) or not model.strip():
        raise UnusableModelId("model id is empty")
    return model


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

    Built-in adapters share this protocol. The method set and the
    ``Completion`` fields do not change when another adapter is registered.
    Adapters that know which ids they serve also match
    ``ModelIdJudgingProvider``. The startup check uses getattr, so an
    adapter that omits ``model_id_validator`` is not asked and still
    satisfies this protocol for type checkers. ``default_model(task)`` is
    also optional. It returns the id to use when no setting names one.
    Omitting it does not borrow another adapter's ids.
    ``supports_json_schema()`` is optional too. When it is present and
    false, ``generate`` raises before any charge if a schema was
    requested. Omitting it means the adapter accepts a schema.
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

        A ``timeout`` from the caller, in seconds, allows one attempt under
        that timeout: the adapter must not retry, and must not wait out a
        provider's retry-after. It is not a total deadline: an adapter may
        apply it per network phase (connect, send, each read), and its module
        says which. A failure raises, and the caller decides what that means (the moderation screen
        holds the text). Without a ``timeout`` the adapter applies its own
        limits and retry policy. Retrying is the adapter's concern; nothing
        shared retries a call, and nothing retries on another model or
        provider.
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


def _load_openai_compatible() -> TextProvider:
    # Stdlib HTTP only. The module does not import a provider SDK.
    from consciousness.openai_compat_provider import provider
    return provider


_BUILTINS: dict[str, Callable[[], TextProvider]] = {
    DEFAULT_PROVIDER: _load_anthropic,
    "openai_compatible": _load_openai_compatible,
}
_REGISTERED: dict[str, Callable[[], TextProvider]] = {}
_registry_lock = threading.Lock()
# First successful selection of each provider name, plus the process default
# name and each task's resolved name. A failed selection is not stored.
# Tests clear these with reset_provider_selection.
_providers: dict[str, TextProvider] = {}
_process_name: str | None = None
_task_provider_names: dict[str, str] = {}
_task_provider_sources: dict[str, str] = {}
# While set, get_provider and provider_for return this adapter and do not
# read a task variable or a cached task selection. The eval harness owns it.
# It is not a process selection and is not cleared by reset_provider_selection.
_provider_override: TextProvider | None = None
# Re-entrant so a factory that calls back into selection can be refused
# instead of deadlocking on a non-reentrant lock. The build itself stays
# inside the lock, so concurrent first calls do not each construct one.
_selection_lock = threading.RLock()
_selection_owner: int | None = None


def provider_names() -> tuple[str, ...]:
    """Registered adapter names, built-ins included. No credentials."""
    with _registry_lock:
        names = set(_BUILTINS) | set(_REGISTERED)
    return tuple(sorted(names))


def build_provider(name: str) -> TextProvider:
    """Instantiate one registered adapter by the name the caller passed.

    This does not read ``NESTED_WORLDS_PROVIDER``, does not apply
    ``DEFAULT_PROVIDER``, and does not cache the instance as the process
    selection. ``get_provider`` remains the seam for a running server.
    The evaluation harness uses this so a candidate names its adapter and
    no other adapter is substituted. A blank, unsafe, or unknown name
    raises ``ValueError``. An unsafe value is not included in the message.
    """
    if not isinstance(name, str) or _PROVIDER_NAME.fullmatch(name.strip().lower()) is None:
        raise ValueError("provider has no evaluated adapter; no implicit fallback")
    text = name.strip().lower()
    with _registry_lock:
        factory = _BUILTINS.get(text)
        if factory is None:
            factory = _REGISTERED.get(text)
    if factory is None:
        raise ValueError("provider has no evaluated adapter; no implicit fallback")
    return factory()


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


@dataclass(frozen=True)
class ProviderResolution:
    """One task's provider name and where it came from. No credentials.

    ``source`` is ``task env``, ``NESTED_WORLDS_PROVIDER``, or ``default``.
    ``failure`` is ``empty``, ``unsafe``, or ``unknown`` when the name that
    applies cannot be used. A failed name does not fall through to another
    adapter. ``name`` is safe to echo only when ``failure`` is ``unknown``
    (a short token that is not registered) or there is no failure.
    """

    task: str
    name: str
    source: str
    env_var: str
    failure: str | None = None
    failure_env: str | None = None


def _classify_provider_value(raw: str) -> tuple[str, str | None]:
    """``(token, failure)``. ``failure`` is empty, unsafe, unknown, or None.

    An unsafe value is not returned. An unknown value is a short token and
    is safe to put in an operator line.
    """
    text = raw.strip().lower()
    if not text:
        return "", "empty"
    if _PROVIDER_NAME.fullmatch(text) is None:
        return "", "unsafe"
    if text not in provider_names():
        return text, "unknown"
    return text, None


def _provider_failure_line(env_name: str, name: str, failure: str) -> str:
    suffix = _valid_suffix()
    if failure == "empty":
        return f"{env_name} is empty ({suffix})"
    if failure == "unknown":
        return (
            f"{env_name}={name!r} is not a known text provider ({suffix})"
        )
    # Unsafe, or any other refusal: do not echo the value.
    return f"{env_name} is not a known text provider ({suffix})"


def resolve_provider(task: str) -> ProviderResolution:
    """Which adapter serves one task. Does not build it or call it.

    A set task variable wins, including when it names the same adapter as
    the process default. Unset falls back to ``NESTED_WORLDS_PROVIDER``,
    then ``anthropic``. A blank, unsafe, or unknown value is a failure on
    the variable that supplied it and does not fall through. This reads
    the environment every time; ``provider_for`` caches a successful result.
    """
    try:
        env_name = _TASK_PROVIDER_ENV[task]
    except KeyError:
        raise ValueError(f"unknown model task {task!r}") from None
    if env_name in os.environ:
        name, failure = _classify_provider_value(os.environ[env_name])
        return ProviderResolution(
            task, name, SOURCE_PROVIDER_TASK, env_name, failure, env_name,
        )
    if PROVIDER_ENV in os.environ:
        name, failure = _classify_provider_value(os.environ[PROVIDER_ENV])
        return ProviderResolution(
            task, name, SOURCE_PROVIDER_PROCESS, PROVIDER_ENV, failure, PROVIDER_ENV,
        )
    return ProviderResolution(
        task, DEFAULT_PROVIDER, SOURCE_PROVIDER_DEFAULT, env_name,
    )


def provider_failure_line(resolution: ProviderResolution) -> str | None:
    """One line for a bad provider name, or None when the name is usable."""
    if not resolution.failure:
        return None
    return _provider_failure_line(
        resolution.failure_env or resolution.env_var,
        resolution.name,
        resolution.failure,
    )


def selected_provider_name() -> str:
    """Registry key for this process. Unset means ``anthropic``.

    The value is stripped and lowercased. Empty, whitespace-only, unsafe,
    or unknown is a misconfiguration. This does not import a provider SDK.
    """
    if PROVIDER_ENV not in os.environ:
        return DEFAULT_PROVIDER
    name, failure = _classify_provider_value(os.environ[PROVIDER_ENV])
    if failure:
        raise SystemExit(_provider_failure_line(PROVIDER_ENV, name, failure))
    return name


def reset_provider_selection() -> None:
    """Forget every adapter chosen for this process.

    ``get_provider`` and ``provider_for`` validate a name once and keep
    that adapter. Tests call this so a later case can select again. A
    failed selection is not cached, so a corrected value can be read on
    the next call without this reset.
    """
    global _process_name
    with _selection_lock:
        _providers.clear()
        _process_name = None
        _task_provider_names.clear()
        _task_provider_sources.clear()


def _load_named(name: str, *, selector_env: str = PROVIDER_ENV) -> TextProvider:
    """Build and cache one registered adapter. Does not import an SDK.

    The factory runs under the selection lock, so two first calls for the
    same name build one adapter. A factory that calls back into selection
    raises ``RuntimeError`` instead of waiting on the lock it already
    holds. A failed selection is not cached. ``selector_env`` is named only
    when the name is not registered.
    """
    global _selection_owner
    with _selection_lock:
        cached = _providers.get(name)
        if cached is not None:
            return cached
        owner = threading.get_ident()
        if _selection_owner == owner:
            raise RuntimeError("text provider factory re-entered selection")
        _selection_owner = owner
        try:
            with _registry_lock:
                factory = _BUILTINS.get(name)
                if factory is None:
                    factory = _REGISTERED.get(name)
            if factory is None:
                raise SystemExit(_provider_failure_line(selector_env, name, "unknown"))
            provider = factory()
            existing = _providers.get(name)
            if existing is None:
                _providers[name] = provider
                existing = provider
            return existing
        finally:
            _selection_owner = None


@contextmanager
def override_provider(provider: TextProvider):
    """Return ``provider`` from every provider lookup until the context ends.

    ``get_provider`` and ``provider_for`` both take this path, including a
    task whose selection is already cached and a task whose environment
    variable names another adapter. The cache and those variables are left
    as they were. Exiting restores the previous override, including none.
    """
    global _provider_override
    with _selection_lock:
        previous = _provider_override
        _provider_override = provider
    try:
        yield
    finally:
        with _selection_lock:
            _provider_override = previous


def _active_override() -> TextProvider | None:
    with _selection_lock:
        return _provider_override


def get_provider() -> TextProvider:
    """The adapter named by ``NESTED_WORLDS_PROVIDER``, chosen once.

    The first successful call validates the name and builds the adapter.
    Later calls return that adapter and do not read the environment again,
    so a bad value set during a request cannot raise ``SystemExit`` on a
    request thread. An unknown name on the first call still raises
    ``SystemExit`` with one line naming that variable and the valid names.
    The same line is what ``python main.py serve`` exits with, before it
    opens a port, when a task has not named a different provider.
    ``override_provider`` returns that adapter instead, without caching it
    as the process selection.
    A failed selection is not cached. ``reset_provider_selection`` clears
    a successful one. This does not import a provider SDK. A task with no
    provider override asks this adapter for default ids, and ``generate``
    sends that task's call to it. The lookup is not a model call:
    ``generate`` reaches ``provider.generate`` only after the voice budget.
    """
    global _process_name
    routed = _active_override()
    if routed is not None:
        return routed
    with _selection_lock:
        cached = _process_name
    if cached is not None:
        return _load_named(cached)
    name = selected_provider_name()
    provider = _load_named(name)
    with _selection_lock:
        if _process_name is None:
            _process_name = name
    return provider


def _read_task_choice(task: str) -> tuple[str, str | None] | None:
    """The cached task choice, or None. Source and name are read together."""
    with _selection_lock:
        source = _task_provider_sources.get(task)
        if source is None:
            return None
        if source == SOURCE_PROVIDER_TASK:
            return source, _task_provider_names[task]
        return source, None


def _publish_task_choice(task: str, source: str, name: str | None) -> tuple[str, str | None]:
    """Store one task choice. A name is written before its task source.

    The lock is held for both writes and for a read of an existing choice,
    so another thread cannot observe a task source with no name. The first
    publisher wins. This does not build or call an adapter.
    """
    with _selection_lock:
        current = _task_provider_sources.get(task)
        if current is None:
            if source == SOURCE_PROVIDER_TASK:
                _task_provider_names[task] = name
            _task_provider_sources[task] = source
            return source, name
        if current == SOURCE_PROVIDER_TASK:
            return current, _task_provider_names[task]
        return current, None


def _adapter_for_choice(task: str, source: str, name: str | None) -> TextProvider:
    """The adapter for one published choice.

    A task-environment choice loads the published name. A process or
    default choice calls ``get_provider`` and does not use a name the
    losing publisher resolved. A task choice with no name is a broken
    cache. It is not passed to ``_load_named``.
    """
    if source != SOURCE_PROVIDER_TASK:
        return get_provider()
    if not isinstance(name, str) or not name.strip():
        raise RuntimeError(f"task provider selection for {task} has no name")
    return _load_named(name, selector_env=_TASK_PROVIDER_ENV[task])


def provider_for(task: str) -> TextProvider:
    """The adapter for one text task, chosen once.

    A task variable that names a registered adapter is cached under that
    name and does not use ``get_provider``. Any other successful resolution
    returns ``get_provider``, so a replaced process provider still supplies
    the default ids and the call. A blank, unsafe, or unknown name raises
    ``SystemExit`` with one line and is not cached. A later change to a
    variable that already resolved does not reselect and does not raise
    from a request. ``override_provider`` is consulted before that cache
    and before the environment, and a task that follows the process
    default does not store a name of its own: ``get_provider`` is the
    seam, and a stored name would go stale when that seam is replaced.
    The cached source and name are published and read under one lock.
    Building the adapter happens outside that publication. When two threads
    resolve one cold task, the first publication wins. The loser returns
    that winner: a process or default winner is ``get_provider``, and a
    task winner is the published name. This does not import a provider SDK
    and does not call the adapter.
    """
    if task not in _TASK_PROVIDER_ENV:
        raise ValueError(f"unknown model task {task!r}")
    routed = _active_override()
    if routed is not None:
        return routed
    cached = _read_task_choice(task)
    if cached is not None:
        return _adapter_for_choice(task, *cached)
    resolution = resolve_provider(task)
    line = provider_failure_line(resolution)
    if line:
        raise SystemExit(line)
    if resolution.source != SOURCE_PROVIDER_TASK:
        get_provider()
        source, name = _publish_task_choice(task, resolution.source, None)
        return _adapter_for_choice(task, source, name)
    _load_named(resolution.name, selector_env=resolution.env_var)
    source, name = _publish_task_choice(task, SOURCE_PROVIDER_TASK, resolution.name)
    return _adapter_for_choice(task, source, name)


def installation_error(provider: TextProvider, selector_env: str | None = None) -> str | None:
    """One-line failure when the selected adapter's own SDK is not installed.

    Adapters that do not set ``sdk_module`` need no SDK. Only a
    ``ModuleNotFoundError`` whose ``name`` is that module, or the root
    package when the module name is dotted, becomes the one-line failure.
    A missing dependency of the SDK, or any other ``ImportError``,
    propagates with its own message. The line names the variable that
    selected the adapter (``NESTED_WORLDS_PROVIDER`` when omitted) and the
    optional extra. It does not include a credential or make a model call.
    """
    module_name = getattr(provider, "sdk_module", None)
    if not isinstance(module_name, str) or not module_name.strip():
        return None
    module_name = module_name.strip()
    try:
        importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        root = module_name.split(".", 1)[0]
        if exc.name not in (module_name, root):
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
        env_name = selector_env.strip() if isinstance(selector_env, str) and selector_env.strip() else PROVIDER_ENV
        return (
            f"{env_name}={shown} requires the optional extra "
            f"enfolded[{extra}] (package '{module_name}' is not installed)"
        )
    return None


def configured(task: str | None = None) -> bool:
    """Whether the process provider, or one task's provider, can be called.

    Callers that patch this with a zero-argument function still match the
    historical no-task check. A task argument asks that task's adapter.
    """
    provider = provider_for(task) if task else get_provider()
    return provider.configured()


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


# A voice reply of at most a few hundred tokens takes seconds, so ten seconds
# lets one to two full turnovers of the default eight slots clear a burst.
# A backlog deeper than that will not clear in a time a player waits for,
# and each waiter holds a request thread or a WebSocket reader meanwhile.
DEFAULT_SLOT_WAIT_SECONDS = 10.0


def _slot_wait_env(provider_name: str) -> str:
    # Same per-provider pattern as the concurrency setting beside it, and the
    # same name `_semaphore_for` keys the slots by: a blank adapter name
    # shares the default provider's slots, so it reads that provider's wait.
    name = provider_name.strip().upper() or DEFAULT_PROVIDER.upper()
    return f"NESTED_WORLDS_{name}_SLOT_WAIT_SECONDS"


def _slot_wait(provider_name: str, timeout: float | None = None) -> float:
    """Longest wait, in seconds, for an in-flight slot before ``ProviderBusy``.

    The call's own timeout when it is a positive finite number: moderation
    passes 3 s, so a held screen answers in about that. Otherwise
    ``NESTED_WORLDS_<NAME>_SLOT_WAIT_SECONDS``: unset, empty, non-numeric or
    non-finite means 10; zero or negative means 0, which takes a free slot
    or answers busy at once. Never above ``threading.TIMEOUT_MAX``, the
    largest wait a lock accepts.
    """
    try:
        own = float(timeout) if timeout is not None else None
    except (TypeError, ValueError):
        own = None
    if own is not None and math.isfinite(own) and own > 0:
        return min(own, threading.TIMEOUT_MAX)
    raw = os.environ.get(_slot_wait_env(provider_name), "").strip()
    try:
        value = float(raw) if raw else DEFAULT_SLOT_WAIT_SECONDS
    except ValueError:
        value = DEFAULT_SLOT_WAIT_SECONDS
    if not math.isfinite(value):
        value = DEFAULT_SLOT_WAIT_SECONDS
    return min(max(0.0, value), threading.TIMEOUT_MAX)


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
             voice_budget: bool = False,
             task: str | None = None) -> Completion:
    """One text completion. An unsupported schema charges nothing.

    ``task`` selects that task's provider. Omit it to use the process
    provider. A missing or blank model id raises ``UnusableModelId`` before
    any cap and before the provider is called. When a schema is requested
    and that adapter's ``supports_json_schema`` is false, this raises
    ``UnsupportedCapability`` before the model-action cap and before the
    voice budget, and the provider is not called. An adapter that omits
    that method still accepts a schema. The model-action cap then runs,
    and ``voice_budget`` reserves one voice call in the shared voice
    allowance, whichever provider serves the task, after that cap and
    before the provider, so a refused cap does not spend the voice budget.
    Every text provider shares that one allowance. A failure is not
    retried on another provider. A ``ModelReservation`` from
    ``reserve_model_action`` is not charged again. The schema check still
    runs when a reservation is already held, and it does not charge again.

    The call then waits for one of that provider's in-flight slots, at
    most ``_slot_wait`` seconds: its own ``timeout`` when given, else
    ``NESTED_WORLDS_<NAME>_SLOT_WAIT_SECONDS`` (default 10). Slots are
    per provider, so a provider that is slow or full does not hold a slot
    of another provider. When none opens, this raises ``ProviderBusy``
    without calling the provider. The charges above are not refunded. A
    slot taken is released on every path out of the provider call.

    A ``timeout`` is then handed to the adapter in full, for one provider
    attempt with no retries (``TextProvider.generate``); the slot wait does
    not count against it. So a call that passes one waits at most that long
    for a slot, then makes one attempt under the same timeout. An adapter may
    enforce it per network phase (connect, send, each read) rather than as
    one wall-clock deadline; its module says which. Nothing here retries.
    """
    require_model_id(model)
    provider = provider_for(task) if task else get_provider()
    if json_schema is not None:
        supports = getattr(provider, "supports_json_schema", None)
        if callable(supports) and not supports():
            from consciousness.openai_compat_provider import UnsupportedCapability
            raise UnsupportedCapability() from None
    if not isinstance(reservation, ModelReservation):
        reservation = reserve_model_action(user_key)
    if voice_budget:
        from server import guard
        if not guard.consume_anthropic(user_key=reservation.key):
            raise VoiceBudgetLimited()
    # Release the gate that was acquired, not a fresh lookup: a changed
    # concurrency setting replaces the semaphore for later callers.
    gate = _semaphore_for(provider.name)
    if not gate.acquire(timeout=_slot_wait(provider.name, timeout)):
        raise ProviderBusy()
    try:
        result = provider.generate(model=model, system=system, messages=messages,
                                   max_tokens=max_tokens, json_schema=json_schema,
                                   timeout=timeout)
    finally:
        gate.release()
    usage = result.usage
    if usage is not None:
        _log.info(
            "model_call provider=%s model=%s endpoint=%s input=%s "
            "cache_read=%s cache_create=%s output=%s",
            provider.name, model, endpoint, usage.input_tokens,
            usage.cache_read_tokens, usage.cache_write_tokens, usage.output_tokens,
        )
    return result
