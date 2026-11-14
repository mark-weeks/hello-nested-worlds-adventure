"""The final controlled text-dispatch boundary.

Only safe request metadata reaches policy and accounting. Credentials and the
serialized request stay in the adapter's memory and never enter the ledger.
Local calls keep their existing behavior while controls are inactive.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
import threading
from typing import TYPE_CHECKING, Callable, Iterator, Mapping

from consciousness.model_policy import ModelPolicyDenied

if TYPE_CHECKING:
    from consciousness.runtime import Completion


class _Permit:
    """One attempt, including across copied contexts and concurrent threads."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active = True
        self._used = False

    def consume(self) -> None:
        with self._lock:
            if not self._active or self._used:
                raise ModelPolicyDenied()
            self._used = True

    def close(self) -> None:
        with self._lock:
            self._active = False


@dataclass(frozen=True)
class _CallScope:
    task: str | None
    user_key: str | None = field(repr=False)
    policy: object = field(repr=False)
    permit: _Permit = field(default_factory=_Permit, repr=False)


_scope: ContextVar[_CallScope | None] = ContextVar("model_dispatch_scope", default=None)
_settlement_fault = threading.Event()
_accounting_lock = threading.RLock()
_initialized_databases: set[str] = set()
_reported_stops: set[str] = set()
_STOP_REASONS = frozenset({"billing_anomaly", "accounting_fault", "unsettled_startup",
                           "accounting_unavailable", "policy_invalid"})


class ModelControlStopped(ModelPolicyDenied):
    """An accounting/control incident needs operator attention, not more budget."""

    def __init__(self) -> None:
        super().__init__()
        self.args = ("Controlled model dispatch is stopped.",)


def _signal_stop(reason: str) -> None:
    reason = reason if reason in _STOP_REASONS else "accounting_fault"
    with _accounting_lock:
        if reason in _reported_stops:
            return
        _reported_stops.add(reason)
    from server import observability
    observability.model_control_stop(reason)


def _ledger_status() -> dict:
    from persistence import model_spend
    try:
        return model_spend.status()
    except Exception:
        return {"latched": None, "stop_reason": None,
                "unresolved_reservations": None, "storage_error": True,
                "ledger_state": "unavailable"}


def initialize_accounting() -> None:
    """Once per controlled process/database, latch unfinished earlier requests.

    All-off hosting can still start and prune expired metadata while stopped.
    Every live preflight checks the resulting stop before charging a call.
    """
    from consciousness import model_policy
    import persistence
    from persistence import model_spend

    if not model_policy.active():
        return
    path = str(persistence._DB_PATH)
    with _accounting_lock:
        if path in _initialized_databases:
            return
        try:
            stopped = model_spend.check_unsettled_on_startup()
        except Exception:
            _settlement_fault.set()
            _signal_stop("accounting_unavailable")
            return
        _initialized_databases.add(path)
    if stopped:
        state = _ledger_status()
        _signal_stop(state.get("stop_reason") or "accounting_fault")


def _ensure_not_stopped() -> None:
    if _settlement_fault.is_set():
        raise ModelControlStopped()
    initialize_accounting()
    if _settlement_fault.is_set():
        raise ModelControlStopped()
    state = _ledger_status()
    if state.get("storage_error"):
        _signal_stop("accounting_unavailable")
        raise ModelControlStopped()
    if state.get("latched"):
        _signal_stop(state.get("stop_reason") or "accounting_fault")
        raise ModelControlStopped()


def task_disabled(task: str) -> bool:
    """An immutable disabled route or its own switch is an intentional limit."""
    from consciousness import model_policy, runtime
    import os

    if not model_policy.active():
        return False
    try:
        policy = model_policy.current()
    except model_policy.ModelPolicyError:
        return False
    if policy is None or task not in policy.routes:
        return True
    switch = ("NESTED_WORLDS_DISABLE_MODERATION" if task == runtime.MODERATION_TASK
              else "NESTED_WORLDS_DISABLE_AI")
    return os.getenv(switch, "").strip() == "1"


def unavailable_reason(task: str) -> str:
    if task_disabled(task):
        return "disabled"
    try:
        if _policy() is not None:
            _ensure_not_stopped()
    except ModelControlStopped:
        return "control_stop"
    except ModelPolicyDenied:
        return "control_stop"
    return "unconfigured"


def operator_status() -> dict:
    """Safe readback, without probes, enrollment, reservations, or recovery."""
    from consciousness import model_policy, runtime

    if not model_policy.active():
        return {"controlled": False}
    try:
        policy = model_policy.current()
    except model_policy.ModelPolicyError:
        return {"controlled": True, "policy_valid": False, "stopped": True,
                "stop_reason": "policy_invalid", "routes": {}, "ledger": None}
    routes = {task: ("disabled" if task_disabled(task) else "enabled")
              for task in (*runtime.TASKS, "images")}
    ledger = _ledger_status()
    reason = ledger.get("stop_reason")
    if _settlement_fault.is_set() and not reason:
        reason = "accounting_fault"
    elif ledger.get("storage_error") or (
            policy is not None and policy.enabled_routes
            and ledger.get("ledger_state") in {"absent", "uninitialized"}):
        reason = "accounting_unavailable"
    return {"controlled": True, "policy_valid": policy is not None,
            "policy_id": policy.policy_id if policy is not None else None,
            "process_fault": _settlement_fault.is_set(),
            "stopped": bool(reason or ledger.get("latched")),
            "stop_reason": reason, "routes": routes, "ledger": ledger}


def preflight(task: str | None, user_key: str | None,
              max_tokens: int | None = None, model: str | None = None) -> None:
    """Check policy, switches, identity shape and faults without a cap or call."""
    policy = _policy()
    if policy is None:
        return
    if task_disabled(task):
        raise ModelPolicyDenied()
    if not isinstance(user_key, str) or not user_key:
        raise ModelPolicyDenied()
    from consciousness import runtime
    provider = runtime.provider_for(task)
    if not _supported(provider):
        raise ModelPolicyDenied()
    route = policy.routes.get(task)
    if route is None:
        raise ModelPolicyDenied()
    _route(task, runtime.resolve_model(task, provider).model if model is None else model,
           route.max_output_tokens if max_tokens is None else max_tokens)
    _ensure_not_stopped()


def reset_for_tests() -> None:
    """Test isolation only; an operational accounting fault needs review."""
    _settlement_fault.clear()
    with _accounting_lock:
        _initialized_databases.clear()
        _reported_stops.clear()


def _policy():
    from consciousness import model_policy
    try:
        if not model_policy.active():
            return None
        policy = model_policy.current()
        if policy is None:
            raise ModelPolicyDenied()
        if _settlement_fault.is_set():
            raise ModelControlStopped()
        return policy
    except model_policy.ModelPolicyError:
        _signal_stop("policy_invalid")
        raise ModelControlStopped() from None


def _supported(adapter: object) -> bool:
    # Exact type is intentional: a registered wrapper or subclass may implement
    # its own generate and never pass through the protected send boundary.
    from consciousness.openai_compat_provider import OpenAICompatibleProvider
    return type(adapter) is OpenAICompatibleProvider


def _route(task, model, max_output_tokens):
    from consciousness import model_policy
    try:
        return model_policy.route_for(task, model, max_output_tokens)
    except model_policy.ModelPolicyError:
        raise ModelPolicyDenied() from None


def validate_runtime_call(provider: object, task: str | None, model: str,
                          user_key: str | None, max_tokens: int) -> None:
    """Refuse unsupported/unauthenticated live routes before legacy call caps."""
    if _policy() is None:
        return
    if not _supported(provider) or not isinstance(user_key, str) or not user_key:
        raise ModelPolicyDenied()
    _route(task, model, max_tokens)
    preflight(task, user_key, max_tokens=max_tokens, model=model)


@contextmanager
def call_scope(*, task: str | None, user_key: str | None) -> Iterator[None]:
    """Bind one runtime invocation; reset identity and revoke it on every exit."""
    scope = _CallScope(task=task, user_key=user_key, policy=_policy())
    token = _scope.set(scope)
    try:
        yield
    finally:
        scope.permit.close()
        _scope.reset(token)


def validate_adapter_call(adapter: object) -> None:
    """Deny unsupported adapters and unscoped direct calls before preparation."""
    scope = _scope.get()
    policy = scope.policy if scope is not None and scope.policy is not None else _policy()
    if policy is None:
        return
    if _settlement_fault.is_set():
        raise ModelControlStopped()
    if (not _supported(adapter) or scope is None
            or not isinstance(scope.user_key, str) or not scope.user_key):
        raise ModelPolicyDenied()


def execute_prepared(*, adapter: object, endpoint: str, model: str,
                     max_output_tokens: int, timeout_seconds: float,
                     options: Mapping[str, object], send_once: Callable[[], Completion],
                     retries: int = 0, redirects: bool = False) -> Completion:
    """Validate the captured request, reserve once, then send and settle once.

    ``send_once`` must capture the exact immutable settings and bytes described
    here. A provider exception leaves the full durable reservation in place.
    """
    from consciousness import model_policy

    scope = _scope.get()
    policy = scope.policy if scope is not None and scope.policy is not None else _policy()
    if policy is None:
        return send_once()
    validate_adapter_call(adapter)
    if scope is None or type(retries) is not int or retries != 0 or redirects is not False:
        raise ModelPolicyDenied()
    route = _route(scope.task, model, max_output_tokens)
    try:
        model_policy.validate_prepared(
            route, adapter=adapter.name, endpoint=endpoint, model=model,
            max_output_tokens=max_output_tokens, timeout_seconds=timeout_seconds,
            options=dict(options),
        )
        reserved = model_policy.reserve_microusd(route, max_output_tokens)
    except model_policy.ModelPolicyError:
        raise ModelPolicyDenied() from None
    if _settlement_fault.is_set():
        raise ModelControlStopped()
    scope.permit.consume()
    from persistence import model_spend
    try:
        reservation_id = model_spend.reserve(
            user_key=scope.user_key, reserved_microusd=reserved,
            global_limit_microusd=policy.global_limit_microusd,
            participant_limit_microusd=policy.participant_limit_microusd,
            policy_snapshot=policy.snapshot_json,
            task=route.task, adapter=adapter.name, endpoint=endpoint, model=model,
            retention_days=policy.retention_days,
        )
    except model_spend.SpendLatched:
        state = _ledger_status()
        _signal_stop(state.get("stop_reason") or "accounting_fault")
        raise ModelControlStopped() from None
    except model_spend.ModelSpendDenied:
        raise ModelPolicyDenied() from None
    if _settlement_fault.is_set():
        # A concurrent accounting failure may have landed during admission.
        # Keep this reserve too, but do not start another network request.
        raise ModelControlStopped()
    result = send_once()
    try:
        actual, anomaly, usage_json = model_policy.settlement(route, result, max_output_tokens)
        model_spend.settle(
            reservation_id, actual_microusd=actual, usage_json=usage_json,
            resolved_model=model_policy.safe_reported_model(result.resolved_model),
            anomaly=anomaly,
        )
    except Exception:
        # The full pending reserve survives even when storage cannot commit
        # the result/latch. Stop this process until its operator reviews it.
        _settlement_fault.set()
        try:
            model_spend.mark_settlement_fault(reservation_id)
        except Exception:
            pass  # the durable unresolved reservation is checked after restart
        _signal_stop("accounting_fault")
        raise ModelControlStopped() from None
    if anomaly:
        _settlement_fault.set()
        _signal_stop("billing_anomaly")
        raise ModelControlStopped()
    return result
