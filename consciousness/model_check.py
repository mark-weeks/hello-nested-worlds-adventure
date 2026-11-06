"""Provider-neutral model-id check. Adapters own which ids they serve.

The check resolves every text task through the active adapter and asks it,
if it offers ``model_id_validator``, whether it serves that id. A task that
would use ``source=default`` without an id from that adapter's
``default_model`` is a hard problem. The check does not substitute another
adapter's id.
The active adapter is the registry's unless the caller passes one. It does
not name a provider, and it does not call the provider unless
``probe_distinct_models`` is invoked. An adapter that declares an SDK which
is not installed exits before the report. Server startup and tests do not probe.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import logging
import os
import re

from consciousness import runtime
from consciousness.runtime import SystemBlock


_log = logging.getLogger("nested_worlds.consciousness")

# Operator-facing text must stay one line. Model ids are not secrets, but a
# value pasted into a model setting might be one. Redact those values.
_SECRET_NAME = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)", re.IGNORECASE)
_SECRET_MIN = 8
_MAX_MODEL_ID_LENGTH = 256
_PROBE_SKIPPED = "skipped: provider not configured"

PROBE_MAX_TOKENS = 1
PROBE_TIMEOUT_SECONDS = 30.0
_PROBE_SYSTEM = "Reply with ok."
_PROBE_USER = "ok"

_UNJUDGED = object()


@dataclass(frozen=True)
class ModelProblem:
    severity: str
    kind: str
    env_var: str
    text: str
    task: str


@dataclass(frozen=True)
class TaskModelStatus:
    task: str
    provider: str
    model: str
    source: str
    env_var: str
    problems: tuple[ModelProblem, ...]
    # Where the provider name came from: task env, NESTED_WORLDS_PROVIDER, or default.
    provider_source: str = ""

    @property
    def display_model(self) -> str:
        return _display_model(self.model, _secret_values())


@dataclass(frozen=True)
class ModelReport:
    provider: str
    tasks: tuple[TaskModelStatus, ...]

    def problems(self, severity: str) -> tuple[ModelProblem, ...]:
        return tuple(
            problem for task in self.tasks for problem in task.problems
            if problem.severity == severity
        )

    @property
    def hard(self) -> tuple[ModelProblem, ...]:
        return self.problems("hard")

    def failure_line(self) -> str:
        return _one_line("Model configuration: ", self._grouped("hard"))

    def warning_line(self) -> str:
        return _one_line("model configuration: ", self._grouped("soft"))

    def _grouped(self, severity: str) -> list[tuple[str, list[str]]]:
        order: list[str] = []
        groups: dict[str, list[str]] = {}
        for task in self.tasks:
            for problem in task.problems:
                if problem.severity != severity:
                    continue
                bucket = groups.get(problem.text)
                if bucket is None:
                    groups[problem.text] = [problem.task]
                    order.append(problem.text)
                elif problem.task not in bucket:
                    bucket.append(problem.task)
        return [(text, groups[text]) for text in order]


@dataclass(frozen=True)
class ProbeResult:
    model: str
    accepted: bool
    detail: str

    def line(self, secrets: tuple[str, ...] | None = None) -> str:
        if self.detail == _PROBE_SKIPPED:
            return self.detail
        shown = _display_model(self.model, secrets if secrets is not None else _secret_values())
        if self.accepted:
            return f"probe {shown}: accepted"
        return f"probe {shown}: refused ({self.detail})"


def _secret_values() -> tuple[str, ...]:
    found: list[str] = []
    for name, value in os.environ.items():
        if not _SECRET_NAME.search(name):
            continue
        text = value.strip()
        if len(text) >= _SECRET_MIN:
            found.append(text)
    return tuple(sorted(set(found), key=len, reverse=True))


def _redact(text: str, secrets: tuple[str, ...]) -> str:
    for secret in secrets:
        if secret and secret in text:
            text = text.replace(secret, "[redacted]")
    return text


def _display_model(model: str | None, secrets: tuple[str, ...]) -> str:
    # None, empty, and whitespace-only are the absence of an id, not a secret.
    if model is None or (isinstance(model, str) and not model.strip()):
        return "(none)"
    if not model or _embeds_secret(model, secrets):
        return "[redacted]"
    if any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in model):
        return "[redacted]"
    if len(model) > 256:
        return "[redacted]"
    return model


def _embeds_secret(text: str, secrets: tuple[str, ...]) -> bool:
    return any(secret and secret in text for secret in secrets)


def _public_provider(name: str, secrets: tuple[str, ...]) -> str:
    text = " ".join(_redact(str(name), secrets).split())
    return text or "provider"


def _quote(model: str, secrets: tuple[str, ...]) -> str | None:
    shown = _display_model(model, secrets)
    if shown == "[redacted]" or not shown:
        return None
    if "'" in shown or '"' in shown:
        return None
    return f"'{shown}'"


def _validator_of(provider):
    method = getattr(provider, "model_id_validator", None)
    if not callable(method):
        return None
    try:
        validator = method()
    except Exception:
        return _UNJUDGED
    if validator is None:
        return None
    if not callable(validator):
        return _UNJUDGED
    return validator


def _configured_blank(name: str) -> str | None:
    """``empty`` or ``whitespace`` when the variable is set but blank."""
    if name not in os.environ:
        return None
    raw = os.environ[name]
    if raw.strip():
        return None
    return "empty" if raw == "" else "whitespace"


def _structural(model: str) -> str | None:
    """Problems every adapter shares. Character sets belong to the adapter.

    Empty, whitespace, control characters, and an absurd length cannot be a
    model id. ``@``, ``+``, ``~``, and other token characters are left for
    ``model_id_validator``.
    """
    if model == "":
        return "empty"
    if model.strip() == "" or any(ch.isspace() for ch in model):
        return "whitespace"
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in model):
        return "malformed"
    if len(model) > _MAX_MODEL_ID_LENGTH:
        return "malformed"
    return None


def _labeled(env_var: str, model: str, secrets: tuple[str, ...], rest: str) -> str:
    quoted = _quote(model, secrets)
    if quoted is None:
        return f"{env_var} {rest}"
    return f"{env_var}={quoted} {rest}"


def _problems_for(choice: runtime.ModelResolution, provider_name: str,
                  validator, secrets: tuple[str, ...]) -> list[ModelProblem]:
    problems: list[ModelProblem] = []

    def add(severity: str, kind: str, env_var: str, text: str) -> None:
        problems.append(ModelProblem(severity, kind, env_var, _redact(text, secrets), choice.task))

    for env_var, kind in choice.ignored_blank:
        if kind == "empty":
            add("hard", "empty", env_var, f"{env_var} is empty")
        else:
            add("hard", "whitespace", env_var, f"{env_var} is whitespace")

    # An empty fallback id must not also be reported as an empty setting.
    # The adapter did not supply a default, so startup stops on that fact.
    if choice.source == runtime.SOURCE_DEFAULT and not choice.adapter_default:
        # Voice tasks can also be set with the shared model. Moderation
        # cannot, so its line names only its own variable.
        if choice.task == runtime.MODERATION_TASK:
            named = choice.env_var
        else:
            named = f"{choice.env_var} or {runtime.SHARED_MODEL_ENV}"
        add(
            "hard", "default", choice.env_var,
            f"{named} is unset and provider {provider_name} "
            "has no default model",
        )
        return problems

    model = choice.model
    if _embeds_secret(model, secrets):
        add("hard", "malformed", choice.env_var, f"{choice.env_var} is not a usable model id")
        return problems

    kind = _structural(model)
    if kind == "empty":
        add("hard", "empty", choice.env_var, f"{choice.env_var} is empty")
        return problems
    if kind == "whitespace":
        add("hard", "whitespace", choice.env_var,
            _labeled(choice.env_var, model, secrets, "contains whitespace"))
        return problems
    if kind == "malformed":
        add("hard", "malformed", choice.env_var,
            _labeled(choice.env_var, model, secrets, "is not a usable model id"))
        return problems

    if (choice.raw is not None and choice.raw != model and choice.raw.strip() == model):
        add("soft", "whitespace", choice.env_var,
            f"{choice.env_var} has surrounding whitespace")

    if validator is None:
        return problems
    if validator is _UNJUDGED:
        add("soft", "unknown", choice.env_var,
            f"{choice.env_var} could not be judged for provider {provider_name}")
        return problems
    try:
        verdict = validator(model)
    except Exception as exc:
        add("soft", "unknown", choice.env_var,
            f"{choice.env_var} could not be judged for provider {provider_name} "
            f"({type(exc).__name__})")
        return problems
    if verdict == "ok":
        return problems
    if verdict == "reject":
        add("hard", "rejected", choice.env_var,
            _labeled(choice.env_var, model, secrets,
                     f"is not served by provider {provider_name}"))
        return problems
    if verdict == "warn":
        add("soft", "unknown", choice.env_var,
            _labeled(choice.env_var, model, secrets,
                     f"is not a known model id for provider {provider_name}"))
        return problems
    add("soft", "unknown", choice.env_var,
        f"{choice.env_var} could not be judged for provider {provider_name}")
    return problems


def _note_blank_shared(tasks: list[TaskModelStatus], secrets: tuple[str, ...]) -> None:
    """A blank shared setting is a mistake even when every voice task overrides it."""
    shared_kind = _configured_blank(runtime.SHARED_MODEL_ENV)
    if shared_kind is None:
        return
    shared_text = _redact(
        f"{runtime.SHARED_MODEL_ENV} is empty" if shared_kind == "empty"
        else f"{runtime.SHARED_MODEL_ENV} is whitespace",
        secrets,
    )
    for index, status in enumerate(tasks):
        if status.task == runtime.MODERATION_TASK:
            continue
        if any(problem.text == shared_text for problem in status.problems):
            continue
        extra = ModelProblem(
            "hard", shared_kind, runtime.SHARED_MODEL_ENV, shared_text, status.task,
        )
        tasks[index] = replace(status, problems=status.problems + (extra,))


def _status_for(choice: runtime.ModelResolution, provider_name: str,
                provider_source: str, validator, secrets: tuple[str, ...],
                crossed_shared: bool) -> TaskModelStatus:
    problems = _problems_for(choice, provider_name, validator, secrets)
    if crossed_shared and choice.source == runtime.SOURCE_SHARED:
        problems.append(ModelProblem(
            "soft", "shared", runtime.SHARED_MODEL_ENV,
            _redact(
                f"{runtime.SHARED_MODEL_ENV} is a model id shared onto "
                f"provider {provider_name} for task {choice.task}",
                secrets,
            ),
            choice.task,
        ))
    return TaskModelStatus(
        task=choice.task,
        provider=provider_name,
        model=choice.model,
        source=choice.source,
        env_var=choice.env_var,
        problems=tuple(problems),
        provider_source=provider_source,
    )


def _check_one_provider(provider) -> ModelReport:
    """Every task through one adapter. Callers pass it; startup does not."""
    missing = runtime.installation_error(provider)
    if missing:
        raise SystemExit(missing)
    secrets = _secret_values()
    provider_name = _public_provider(getattr(provider, "name", ""), secrets)
    validator = _validator_of(provider)
    tasks = []
    for task in runtime.TASKS:
        choice = runtime.resolve_model(task, provider)
        tasks.append(_status_for(
            choice, provider_name, "", validator, secrets, crossed_shared=False,
        ))
    _note_blank_shared(tasks, secrets)
    return ModelReport(provider=provider_name, tasks=tuple(tasks))


def _selector_env(resolution: runtime.ProviderResolution) -> str:
    if resolution.source == runtime.SOURCE_PROVIDER_TASK:
        return resolution.env_var
    return runtime.PROVIDER_ENV


def check_model_configuration(provider=None) -> ModelReport:
    """Resolve every task through its own adapter.

    Does not generate text or read a credential. Pass an adapter to judge
    every task against that one adapter (tests).     Otherwise each task uses
    its own provider: the task variable, then ``NESTED_WORLDS_PROVIDER``,
    then the process default. A blank, unknown, or unsafe name raises
    ``SystemExit`` with one line before the report. When an adapter names
    an SDK that is not installed, this raises ``SystemExit`` with one line
    naming the variable that selected it and the optional extra. A shared
    model id used on a provider other than the process default is a soft
    problem: the id is explicit, and it is not that provider's default.
    """
    if provider is not None:
        return _check_one_provider(provider)
    secrets = _secret_values()
    resolutions = []
    for task in runtime.TASKS:
        resolution = runtime.resolve_provider(task)
        line = runtime.provider_failure_line(resolution)
        if line:
            raise SystemExit(line)
        resolutions.append(resolution)
    loaded = []
    seen_sdk: set[str] = set()
    for resolution in resolutions:
        prov = runtime.provider_for(resolution.task)
        loaded.append(prov)
        if prov.name in seen_sdk:
            continue
        seen_sdk.add(prov.name)
        missing = runtime.installation_error(prov, _selector_env(resolution))
        if missing:
            raise SystemExit(missing)
    try:
        process_provider = runtime.get_provider()
    except SystemExit:
        # Every task named its own adapter and the process value is unusable.
        # The task lines still report. A shared model id cannot be assumed
        # to belong to those adapters.
        process_provider = None
    tasks = []
    for resolution, prov in zip(resolutions, loaded):
        provider_name = _public_provider(getattr(prov, "name", ""), secrets)
        choice = runtime.resolve_model(resolution.task, prov)
        same = (
            process_provider is not None
            and (prov is process_provider or provider_name == _public_provider(
                getattr(process_provider, "name", ""), secrets))
        )
        tasks.append(_status_for(
            choice, provider_name, resolution.source, _validator_of(prov), secrets,
            crossed_shared=not same,
        ))
    _note_blank_shared(tasks, secrets)
    names = {task.provider for task in tasks}
    header = next(iter(names)) if len(names) == 1 else "per task"
    return ModelReport(provider=header, tasks=tuple(tasks))


def enforce_model_configuration(provider=None) -> ModelReport:
    """Log one warning for soft problems. Hard problems raise SystemExit.

    The message is one line and names the environment variable. It does not
    include credential values. This does not probe.
    """
    report = check_model_configuration(provider)
    if report.problems("soft"):
        _log.warning("%s", report.warning_line())
    if report.hard:
        raise SystemExit(report.failure_line())
    return report


def format_report(report: ModelReport) -> str:
    """Operator text: provider, model, source, and problems. No credentials."""
    secrets = _secret_values()
    lines = [f"text provider: {report.provider}"]
    for task in report.tasks:
        via = f" provider_source={task.provider_source}" if task.provider_source else ""
        lines.append(
            f"{task.task:<12} provider={task.provider}{via} "
            f"model={task.display_model} source={task.source} env={task.env_var}"
        )
        for problem in task.problems:
            lines.append(f"  {problem.severity}: {problem.text}")
    text = "\n".join(lines)
    return _redact(text, secrets)


def _one_line(prefix: str, groups: list[tuple[str, list[str]]]) -> str:
    parts = []
    for text, tasks in groups:
        label = "task" if len(tasks) == 1 else "tasks"
        parts.append(f"{text} ({label} {', '.join(tasks)})")
    return " ".join(f"{prefix}{'; '.join(parts)}".split())


def _provider_ready(provider) -> bool:
    configured = getattr(provider, "configured", None)
    if not callable(configured):
        return True
    try:
        return bool(configured())
    except Exception:
        return False


def _probe_models(report: ModelReport, provider, secrets: tuple[str, ...]) -> list[ProbeResult]:
    results: list[ProbeResult] = []
    seen: set[str] = set()
    for task in report.tasks:
        model = task.model
        if model in seen:
            continue
        seen.add(model)
        if not model or _embeds_secret(model, secrets) or _structural(model) is not None:
            results.append(ProbeResult(model, False, "skipped"))
            continue
        try:
            provider.generate(
                model=model,
                system=(SystemBlock(text=_PROBE_SYSTEM),),
                messages=[{"role": "user", "content": _PROBE_USER}],
                max_tokens=PROBE_MAX_TOKENS,
                timeout=PROBE_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            # Class name only. SDK messages can carry the key or the prompt.
            results.append(ProbeResult(model, False, type(exc).__name__))
        else:
            results.append(ProbeResult(model, True, "accepted"))
    return results


def probe_distinct_models(report: ModelReport, provider=None) -> tuple[ProbeResult, ...]:
    """One tiny call per distinct resolved id. Opt-in. Never used at startup.

    Calls the adapter directly. It does not charge the model-action cap or
    the persisted voice allowance, and it does not write a chronicle row.
    An id that embeds a credential is not sent. Pass an adapter to probe
    that one adapter. Otherwise each task is probed on its own provider,
    and one unconfigured provider does not skip a configured provider's id.
    An unconfigured provider adds ``skipped: provider not configured`` and
    is not called.
    """
    secrets = _secret_values()
    if provider is not None:
        if not _provider_ready(provider):
            return (ProbeResult("", False, _PROBE_SKIPPED),)
        return tuple(_probe_models(report, provider, secrets))
    results: list[ProbeResult] = []
    seen: set[tuple[str, str]] = set()
    saw_unconfigured = False
    for task in report.tasks:
        prov = runtime.provider_for(task.task)
        if not _provider_ready(prov):
            saw_unconfigured = True
            continue
        key = (getattr(prov, "name", ""), task.model)
        if key in seen:
            continue
        seen.add(key)
        if not task.model or _embeds_secret(task.model, secrets) or _structural(task.model) is not None:
            results.append(ProbeResult(task.model, False, "skipped"))
            continue
        try:
            prov.generate(
                model=task.model,
                system=(SystemBlock(text=_PROBE_SYSTEM),),
                messages=[{"role": "user", "content": _PROBE_USER}],
                max_tokens=PROBE_MAX_TOKENS,
                timeout=PROBE_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            results.append(ProbeResult(task.model, False, type(exc).__name__))
        else:
            results.append(ProbeResult(task.model, True, "accepted"))
    if saw_unconfigured:
        results.append(ProbeResult("", False, _PROBE_SKIPPED))
    if not results:
        return (ProbeResult("", False, _PROBE_SKIPPED),)
    return tuple(results)
