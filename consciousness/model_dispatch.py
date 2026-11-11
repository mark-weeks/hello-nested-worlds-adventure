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


def reset_for_tests() -> None:
    """Test isolation only; an operational accounting fault needs review."""
    _settlement_fault.clear()


def _policy():
    from consciousness import model_policy
    try:
        if not model_policy.active():
            return None
        policy = model_policy.current()
        if policy is None:
            raise ModelPolicyDenied()
        if _settlement_fault.is_set():
            raise ModelPolicyDenied()
        return policy
    except model_policy.ModelPolicyError:
        raise ModelPolicyDenied() from None


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
    if (_settlement_fault.is_set() or not _supported(adapter) or scope is None
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
        raise ModelPolicyDenied()
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
    except model_spend.ModelSpendDenied:
        raise ModelPolicyDenied() from None
    if _settlement_fault.is_set():
        # A concurrent accounting failure may have landed during admission.
        # Keep this reserve too, but do not start another network request.
        raise ModelPolicyDenied()
    result = send_once()
    try:
        actual, anomaly, usage_json = model_policy.settlement(route, result, max_output_tokens)
        model_spend.settle(
            reservation_id, actual_microusd=actual, usage_json=usage_json,
            resolved_model=(result.resolved_model
                            if result.resolved_model in route.resolved_models else None),
            anomaly=anomaly,
        )
    except Exception:
        # The full pending reserve survives even when storage cannot commit
        # the result/latch. Stop this process until its operator reviews it.
        _settlement_fault.set()
        raise ModelPolicyDenied() from None
    if anomaly:
        _settlement_fault.set()
        raise ModelPolicyDenied()
    return result
