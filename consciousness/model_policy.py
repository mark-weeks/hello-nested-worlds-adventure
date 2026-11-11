"""Offline declarations and immutable permissions for controlled model calls.

No destinations, dollar amounts or retention periods are approved by this module.
Configuration validity is not a remote availability, pricing or data-use check.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal, InvalidOperation, ROUND_CEILING, localcontext
import json
import math
import os
from pathlib import Path
import re
import threading
from types import MappingProxyType
from typing import Mapping
from urllib.parse import urlsplit

from consciousness import runtime

POLICY_ENV = "NESTED_WORLDS_MODEL_POLICY"
REQUIRED_ENV = "NESTED_WORLDS_REQUIRE_MODEL_POLICY"
_TASKS = (*runtime.TASKS, "images")
_MAX_INTEGER = 2**63 - 1
_MAX_FILE_BYTES = 131_072
_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,159}")
_PRICE_KEYS = frozenset({"input_per_million_usd", "output_per_million_usd",
                         "cache_read_per_million_usd", "cache_write_per_million_usd"})
_OPTION_KEYS = frozenset({"max_tokens_param", "structured_outputs",
                          "send_store_false", "reasoning_effort"})


class ModelPolicyError(ValueError):
    def __init__(self) -> None:
        super().__init__("Model policy configuration is invalid or missing.")


class ModelPolicyDenied(runtime.VoiceBudgetLimited):
    def __init__(self) -> None:
        super().__init__("Controlled model call was refused.")


@dataclass(frozen=True)
class Route:
    task: str
    adapter: str
    endpoint: str = field(repr=False)
    model: str
    resolved_models: tuple[str, ...]
    max_input_tokens: int
    max_output_tokens: int
    timeout_seconds: Decimal
    options: Mapping[str, object]
    prices: Mapping[str, Decimal]


@dataclass(frozen=True)
class Policy:
    policy_id: str
    routes: Mapping[str, Route]
    global_limit_microusd: int = 0
    participant_limit_microusd: int = 0
    retention_days: int = 0
    snapshot_json: str = field(default="", repr=False)

    @property
    def enabled_routes(self) -> tuple[str, ...]:
        return tuple(task for task in runtime.TASKS if task in self.routes)


_snapshot: Policy | None = None
_lock = threading.RLock()


def reset_for_tests() -> None:
    """Test isolation only; serving code never reloads permission from env."""
    global _snapshot
    with _lock:
        _snapshot = None


def active() -> bool:
    return (_snapshot is not None
            or os.getenv(REQUIRED_ENV, "").strip() == "1"
            or POLICY_ENV in os.environ
            or os.getenv("NESTED_WORLDS_TEST_WORLD", "").strip().casefold()
            not in {"", "0", "false", "off", "no"})


def _keys(value: object, expected: set | frozenset) -> dict:
    if not isinstance(value, dict) or set(value) != expected:
        raise ModelPolicyError()
    return value


def _identifier(value: object) -> str:
    if not isinstance(value, str) or not _SAFE_ID.fullmatch(value):
        raise ModelPolicyError()
    return value


def _reference(value: object) -> str:
    if (not isinstance(value, str) or not 1 <= len(value) <= 1000
            or value != value.strip() or any(ord(x) < 32 for x in value)):
        raise ModelPolicyError()
    return value


def _integer(value: object, *, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= _MAX_INTEGER:
        raise ModelPolicyError()
    return value


def _decimal(value: object, *, positive: bool = False) -> Decimal:
    # Strings avoid binary floats and prevent a misspelled/unknown price
    # from becoming zero. Bound length/exponent before arithmetic.
    if not isinstance(value, str) or not re.fullmatch(r"(?:0|[1-9][0-9]{0,12})(?:\.[0-9]{1,12})?", value):
        raise ModelPolicyError()
    try:
        result = Decimal(value)
    except InvalidOperation:
        raise ModelPolicyError() from None
    if not result.is_finite() or result < 0 or (positive and result == 0):
        raise ModelPolicyError()
    return result


def _dollars(value: object) -> int:
    scaled = _decimal(value) * 1_000_000
    if scaled != scaled.to_integral_value() or scaled > _MAX_INTEGER:
        raise ModelPolicyError()
    return int(scaled)


def _endpoint(value: object) -> str:
    if (not isinstance(value, str) or not value.isascii() or len(value) > 2000
            or any(ord(c) <= 32 or ord(c) == 127 for c in value) or "\\" in value):
        raise ModelPolicyError()
    try:
        parsed = urlsplit(value)
        port = parsed.port
        if (parsed.scheme != "https" or not parsed.hostname
                or parsed.username is not None or parsed.password is not None
                or parsed.query or parsed.fragment or "?" in value or "#" in value
                or port == 0 or not parsed.path.endswith("/chat/completions")
                or not re.fullmatch(r"/[A-Za-z0-9/._~-]+", parsed.path)
                or any(part in {".", ".."} for part in parsed.path.split("/"))):
            raise ModelPolicyError()
    except ValueError:
        raise ModelPolicyError() from None
    return value


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ModelPolicyError()
        result[key] = value
    return result


def _route(task: str, data: object) -> Route | None:
    if isinstance(data, dict) and set(data) == {"enabled"} and data["enabled"] is False:
        return None
    data = _keys(data, {"enabled", "adapter", "endpoint", "model", "resolved_models",
                        "max_input_tokens", "input_bound_kind", "input_bound_evidence", "max_output_tokens",
                        "timeout_seconds", "options", "prices", "data_use_note",
                        "approval_reference"})
    if (data["enabled"] is not True or task == "images" or data["adapter"] != "openai_compatible"
            or data["input_bound_kind"] != "provider_context_maximum"):
        raise ModelPolicyError()
    model = _identifier(data["model"])
    resolved = data["resolved_models"]
    if not isinstance(resolved, list) or not resolved or len(resolved) > 32:
        raise ModelPolicyError()
    resolved = tuple(_identifier(x) for x in resolved)
    if len(resolved) != len(set(resolved)):
        raise ModelPolicyError()
    for key in ("input_bound_evidence", "data_use_note", "approval_reference"):
        _reference(data[key])
    options = _keys(data["options"], _OPTION_KEYS)
    if (options["max_tokens_param"] not in {"max_tokens", "max_completion_tokens"}
            or type(options["structured_outputs"]) is not bool
            or options["send_store_false"] is not True
            or options["reasoning_effort"] not in {None, "none", "minimal", "low", "medium", "high"}):
        raise ModelPolicyError()
    # Both tasks require a strict schema in their ordinary call paths.
    if task in {runtime.INTENT_TASK, runtime.MODERATION_TASK} and not options["structured_outputs"]:
        raise ModelPolicyError()
    raw_prices = _keys(data["prices"], _PRICE_KEYS)
    prices = MappingProxyType({key: _decimal(raw_prices[key]) for key in _PRICE_KEYS})
    route = Route(task, "openai_compatible", _endpoint(data["endpoint"]), model, resolved,
                  _integer(data["max_input_tokens"]), _integer(data["max_output_tokens"]),
                  _decimal(data["timeout_seconds"], positive=True),
                  MappingProxyType(dict(options)), prices)
    if route.timeout_seconds > Decimal("3600"):
        raise ModelPolicyError()
    reserve_microusd(route, route.max_output_tokens)
    return route


def check_file(path: str | Path) -> Policy:
    """Strict offline parse; no key access, DB, network or global permission."""
    try:
        with Path(path).open("rb") as stream:
            raw = stream.read(_MAX_FILE_BYTES + 1)
        if len(raw) > _MAX_FILE_BYTES:
            raise ModelPolicyError()
        data = json.loads(raw, object_pairs_hook=_unique_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ModelPolicyError()))
        if not isinstance(data, dict):
            raise ModelPolicyError()
        common = {"schema_version", "policy_id", "currency", "reset", "routes"}
        if data.keys() not in (common, common | {"limits", "ledger_retention_days"}):
            raise ModelPolicyError()
        if type(data["schema_version"]) is not int or data["schema_version"] != 1:
            raise ModelPolicyError()
        if data["currency"] != "USD" or data["reset"] != "UTC":
            raise ModelPolicyError()
        route_data = _keys(data["routes"], set(_TASKS))
        routes = {}
        for task in _TASKS:
            route = _route(task, route_data[task])
            if route is not None:
                routes[task] = route
        limits = (0, 0)
        retention = 0
        if routes or "limits" in data:
            values = _keys(data.get("limits"), {"global_daily_usd", "participant_daily_usd"})
            limits = (_dollars(values["global_daily_usd"]), _dollars(values["participant_daily_usd"]))
            retention = _integer(data.get("ledger_retention_days"), minimum=2)
            if retention > 36500:
                raise ModelPolicyError()
        return Policy(_identifier(data["policy_id"]), MappingProxyType(routes), *limits,
                      retention, json.dumps(data, sort_keys=True, separators=(",", ":")))
    except ModelPolicyError:
        raise
    except (OSError, UnicodeError, ValueError, TypeError, RecursionError, OverflowError):
        raise ModelPolicyError() from None


def validate_configuration(policy: Policy) -> None:
    """Match all enabled tasks against effective adapter/model/options offline."""
    if not policy.enabled_routes:
        return
    from consciousness.openai_compat_provider import (
        OpenAICompatibleProvider, _call_timeout, _settings, chat_completions_url,
    )
    try:
        settings = _settings()
        if settings.base is None or settings.max_tokens_param is None or settings.reasoning_invalid:
            raise ModelPolicyError()
        options = {"max_tokens_param": settings.max_tokens_param,
                   "structured_outputs": settings.structured_outputs,
                   "send_store_false": settings.send_store_false,
                   "reasoning_effort": settings.reasoning_effort}
        for task in policy.enabled_routes:
            route = policy.routes[task]
            provider = runtime.provider_for(task)
            model = runtime.resolve_model(task, provider)
            if (type(provider) is not OpenAICompatibleProvider or model.ignored_blank
                    or model.source == runtime.SOURCE_DEFAULT or model.model != route.model
                    or route.endpoint != chat_completions_url(settings.base.url)
                    or dict(route.options) != options
                    or Decimal(str(_call_timeout(3.0 if task == runtime.MODERATION_TASK else None)))
                    > route.timeout_seconds):
                raise ModelPolicyError()
    except ModelPolicyError:
        raise
    except (Exception, SystemExit):
        raise ModelPolicyError() from None


def initialize() -> Policy | None:
    """Freeze startup permission. Runtime env changes may only deny further."""
    global _snapshot
    with _lock:
        if _snapshot is not None:
            return _snapshot
        if not active():
            return None
        path = os.getenv(POLICY_ENV, "").strip()
        if path:
            policy = check_file(path)
        elif (os.getenv("NESTED_WORLDS_DISABLE_AI", "").strip() == "1"
              and os.getenv("NESTED_WORLDS_DISABLE_IMAGES", "").strip() == "1"):
            policy = Policy("external-calls-disabled", MappingProxyType({}))
        else:
            raise ModelPolicyError()
        validate_configuration(policy)
        _snapshot = policy
        return policy


def current() -> Policy | None:
    return initialize()


def route_for(task: str, model: str, max_output_tokens: int) -> Route:
    try:
        policy = current()
        if policy is None or os.getenv("NESTED_WORLDS_DISABLE_AI", "").strip() == "1":
            raise ModelPolicyDenied()
        route = policy.routes.get(task)
        if (route is None or route.model != model
                or isinstance(max_output_tokens, bool) or not isinstance(max_output_tokens, int)
                or not 1 <= max_output_tokens <= route.max_output_tokens):
            raise ModelPolicyDenied()
        return route
    except ModelPolicyError:
        raise ModelPolicyDenied() from None


def validate_prepared(route: Route, *, adapter: str, endpoint: str, model: str,
                      max_output_tokens: int, timeout_seconds: float,
                      options: dict) -> None:
    if (not isinstance(options, dict) or set(options) != _OPTION_KEYS
            or type(options.get("structured_outputs")) is not bool
            or options.get("send_store_false") is not True
            or route_for(route.task, model, max_output_tokens) is not route
            or adapter != route.adapter or endpoint != route.endpoint
            or dict(route.options) != options
            or isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(timeout_seconds) or timeout_seconds <= 0
            or Decimal(str(timeout_seconds)) > route.timeout_seconds):
        raise ModelPolicyDenied()


def _microusd(value: Decimal) -> int:
    result = int(value.to_integral_value(rounding=ROUND_CEILING))
    if not 0 <= result <= _MAX_INTEGER:
        raise ModelPolicyError()
    return result


def reserve_microusd(route: Route, max_output_tokens: int) -> int:
    worst_input = max(route.prices[k] for k in _PRICE_KEYS if k != "output_per_million_usd")
    # USD per million tokens equals microUSD per token.
    with localcontext() as context:
        context.prec = 64
        return _microusd(route.max_input_tokens * worst_input
                         + max_output_tokens * route.prices["output_per_million_usd"])


def settlement(route: Route, result: runtime.Completion,
               max_output_tokens: int) -> tuple[int | None, bool, str | None]:
    anomaly = result.resolved_model not in route.resolved_models or result.provider != route.adapter
    usage = result.usage
    if usage is None:
        return None, anomaly, None
    counts = asdict(usage)
    encoded = json.dumps(counts, sort_keys=True, separators=(",", ":"))
    for value in counts.values():
        if value is not None and (type(value) is not int or value < 0 or value > _MAX_INTEGER):
            return None, True, None
    known_inputs = sum(v for k, v in counts.items() if k != "output_tokens" and v is not None)
    if known_inputs > route.max_input_tokens or (usage.output_tokens or 0) > max_output_tokens:
        anomaly = True
    if any(counts[k] is None for k in ("input_tokens", "output_tokens", "cache_read_tokens")):
        return None, anomaly, encoded
    with localcontext() as context:
        context.prec = 64
        if usage.cache_write_tokens is None:
            # A missing write split can be included in ordinary prompt tokens by
            # this dialect. Charge every reported input at its highest rate.
            worst = max(route.prices[k] for k in _PRICE_KEYS if k != "output_per_million_usd")
            cost = known_inputs * worst + usage.output_tokens * route.prices["output_per_million_usd"]
        else:
            cost = (usage.input_tokens * route.prices["input_per_million_usd"]
                    + usage.cache_read_tokens * route.prices["cache_read_per_million_usd"]
                    + usage.cache_write_tokens * route.prices["cache_write_per_million_usd"]
                    + usage.output_tokens * route.prices["output_per_million_usd"])
    try:
        return _microusd(cost), anomaly, encoded
    except ModelPolicyError:
        return None, True, encoded


def summary(policy: Policy) -> dict:
    """Safe CLI summary: no paths, endpoints, model strings or approval text."""
    return {"policy_id": policy.policy_id, "enabled_routes": list(policy.enabled_routes),
            "currency": "USD", "reset": "UTC",
            "global_limit_microusd": policy.global_limit_microusd,
            "participant_limit_microusd": policy.participant_limit_microusd,
            "ledger_retention_days": policy.retention_days,
            "verification": "Configuration valid; remote availability and terms not verified."}
