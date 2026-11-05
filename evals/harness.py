"""Repeatable task trials through production prompts and validators.

Run in a dedicated process: patching task routing is deliberately scoped to this
developer tool. No HTTP server, production database, or world writes are used.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import random
import subprocess
import sys
import time
from unittest.mock import patch

from consciousness import runtime
from consciousness.runtime import Completion, TokenUsage

ROOT = Path(__file__).resolve().parents[1]
TASKS = ("node_voice", "inhabitant_voice", "intention", "moderation")
SOURCE_FILES = ("consciousness/__init__.py", "consciousness/interventions.py",
                "consciousness/runtime.py", "consciousness/anthropic_provider.py",
                "consciousness/openai_compat_provider.py",
                "multiverse/interventions_v2.py", "multiverse/interventions_v3.py",
                "multiverse/senses.py", "multiverse/history.py", "server/moderation.py",
                "content_screen.py", "evals/harness.py", "evals/reporting.py",
                "scripts/model_eval.py", "requirements.lock", "requirements-dev.lock")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode("utf-8")).hexdigest()


def read_json(path):
    def bad_constant(value):
        raise ValueError(f"non-finite JSON number: {value}")
    return json.loads(Path(path).read_text(encoding="utf-8"), parse_constant=bad_constant)


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False,
                                   allow_nan=False) + "\n", encoding="utf-8")


def load_corpus(path):
    from agents.personas import by_name
    from multiverse.generator import LEVELS
    from multiverse.interventions_v3 import normalize_steps
    corpus = read_json(path)
    if corpus.get("schema_version") != 1 or corpus.get("data_class") != "synthetic":
        raise ValueError("v1 accepts only explicitly synthetic corpora")
    validate_corpus_version(corpus)
    cases = corpus.get("cases", [])
    ids = set()
    groups = {}
    if not cases:
        raise ValueError("empty corpus")
    for case in cases:
        key = case.get("id")
        if not isinstance(key, str) or not key or key in ids:
            raise ValueError("case IDs must be nonempty and unique")
        ids.add(key)
        if case.get("task") not in TASKS or case.get("split") not in ("development", "holdout"):
            raise ValueError(f"invalid task/split: {key}")
        group = case.get("group")
        if not isinstance(group, str) or not group:
            raise ValueError(f"missing scenario group: {key}")
        if group in groups and groups[group] != case["split"]:
            raise ValueError(f"scenario group leaks across splits: {group}")
        groups[group] = case["split"]
        if not case.get("category") or type(case.get("critical")) is not bool:
            raise ValueError(f"missing category/critical flag: {key}")
        if not case.get("messages") or not all(isinstance(x, str) and x.strip() for x in case["messages"]):
            raise ValueError(f"missing messages: {key}")
        if len(case.get("fixture", [])) != len(case["messages"]):
            raise ValueError(f"one fixture response required per turn: {key}")
        if case["task"] != "moderation" and case.get("node", {}).get("level") not in LEVELS:
            raise ValueError(f"invalid scale: {key}")
        if case["task"] == "inhabitant_voice" and not by_name(case.get("persona")):
            raise ValueError(f"invalid persona: {key}")
        expected = case.get("expected", {})
        if case["task"] == "intention":
            if (len(case["messages"]) != 1 or not isinstance(expected, dict) or
                    set(expected) != {"status", "ambiguity", "steps"}):
                raise ValueError(f"invalid intention expectation shape: {key}")
            status, ambiguity, steps = (expected[k] for k in ("status", "ambiguity", "steps"))
            if status == "ready" and ambiguity == "none":
                if normalize_steps(steps, case["node"]["level"]) != steps:
                    raise ValueError(f"intention expectation must use normalized steps: {key}")
            elif not (steps == [] and (status == "unsupported" and ambiguity == "none" or
                      status == "clarify" and ambiguity in ("action", "target", "scope", "order"))):
                raise ValueError(f"unreachable intention expectation: {key}")
        elif case["task"] == "moderation":
            if len(case["messages"]) != 1 or type(expected.get("allowed")) is not bool:
                raise ValueError(f"invalid moderation expectation: {key}")
        elif not case.get("rubric_notes"):
            raise ValueError(f"voice needs case-specific grading notes: {key}")
    return corpus


def validate_corpus_version(corpus):
    if not isinstance(corpus.get("version"), str) or not corpus["version"].strip():
        raise ValueError("corpus version must be a nonempty string")


class FixtureProvider:
    """Plumbing exercise with authored answers, never model-quality evidence."""
    name = "fixture"

    def __init__(self, replies):
        self.replies = iter(replies)

    def generate(self, **kwargs):
        return Completion(next(self.replies), True, TokenUsage(0, 0, 0, 0),
                          "complete", "fixture-v1")

    def configured(self):
        return True

    def cache_reference_tokens(self, model):
        return None


def positive(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a finite positive number")


def nonnegative(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be zero or a finite positive number, or null")


def validate_brief(brief, tasks):
    if not brief or not all(brief.get(k) for k in ("purpose", "owner", "frozen_on")):
        raise ValueError("live comparison requires a frozen selection brief")
    if type(brief.get("minimum_repeats")) is not int or brief["minimum_repeats"] < 3:
        raise ValueError("selection brief requires at least three repeats for decision evidence")
    for task in tasks:
        gates = brief.get("tasks", {}).get(task, {})
        for name in ("min_success_rate", "max_p95_ms", "max_cost_per_success_usd", "minimum_gain"):
            positive(gates.get(name), name)
        if gates["min_success_rate"] > 1:
            raise ValueError("success rate must not exceed one")
        if type(gates.get("min_cases")) is not int or gates["min_cases"] < 1:
            raise ValueError("name a minimum case count per task")
        tolerance = gates.get("max_success_rate_drop")
        if type(tolerance) not in (int, float) or not math.isfinite(tolerance) or not 0 <= tolerance <= 1:
            raise ValueError("name the maximum tolerable success-rate drop")
        if gates.get("switch_metric") not in ("success_rate", "quality", "cost", "latency"):
            raise ValueError("choose a primary switching metric")
        if task.endswith("voice"):
            quality_drop = gates.get("max_quality_drop")
            if type(quality_drop) not in (int, float) or not math.isfinite(quality_drop) or not 0 <= quality_drop <= 4:
                raise ValueError("name the maximum tolerable voice-quality drop")


def provider_key(config):
    """Candidate provider name, stripped and lowercased. Never a default."""
    raw = config.get("provider")
    if not isinstance(raw, str):
        return ""
    return raw.strip().lower()


def validate_candidate(config, live=False):
    key = provider_key(config)
    # fixture is harness-only. Every other name must already be registered.
    # An unknown name is a refusal: nothing here substitutes another adapter.
    if key != "fixture" and key not in runtime.provider_names():
        raise ValueError("provider has no evaluated adapter; no implicit fallback")
    if not config.get("id") or set(config.get("models", {})) != set(TASKS):
        raise ValueError("name a candidate and an explicit model for every task")
    if not all(isinstance(x, str) and x.strip() for x in config["models"].values()):
        raise ValueError("empty model identifier")
    if live != (key != "fixture"):
        raise ValueError("live provider requires --live; fixtures cannot be live evidence")
    if not live:
        return
    if config.get("data_authorization") != "synthetic-only" or not config.get("terms_review"):
        raise ValueError("record synthetic-only authorization and a data-terms review")
    positive(config.get("timeout_seconds"), "timeout_seconds")
    if config.get("max_retries") != 0:
        raise ValueError("v1 disables SDK retries so every billable attempt is visible")
    for model in set(config["models"].values()):
        price = config.get("pricing", {}).get(model, {})
        for rate in ("input_per_million", "output_per_million", "cache_read_per_million"):
            positive(price.get(rate), rate)
        # Explicit zero is a provider with no cache-write charge. Null means
        # the rate is not priced. A missing or null rate is not billed as
        # zero when the server reports writes. The dated source still applies.
        write = price.get("cache_write_per_million", None)
        if write is not None:
            nonnegative(write, "cache_write_per_million")
        if type(price.get("max_input_tokens")) is not int or price["max_input_tokens"] < 1:
            raise ValueError("max_input_tokens must be a positive integer")
        if not price.get("source") or not price.get("verified_on"):
            raise ValueError("pricing and maximum input bound need dated official evidence")


STOP_REASONS = {"spend_limit_reached", "call_limit_reached", "pricing_bound_exceeded", "routing_mismatch"}
OPERATIONAL_OUTCOMES = {"not_run", "interrupted", "transport_error", "harness_error"}


class BudgetExceeded(RuntimeError):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


class RoutingMismatch(RuntimeError):
    """The production entry point did not request the selected candidate model."""


# TokenUsage fields and the price-map rates that bill them. A null rate is
# not a zero rate: the count stays unpriced.
_USAGE_RATES = (
    ("input_tokens", "input_per_million"),
    ("output_tokens", "output_per_million"),
    ("cache_read_tokens", "cache_read_per_million"),
    ("cache_write_tokens", "cache_write_per_million"),
)


def _finite_rate(value):
    """Zero or a positive finite rate. Anything else, including null, is unpriced."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value) or value < 0:
        return None
    return value


def _reserve_rate(price):
    """Highest priced input or cache rate. A null cache-write rate is omitted."""
    rates = [_finite_rate(price.get("input_per_million")),
             _finite_rate(price.get("cache_read_per_million")),
             _finite_rate(price.get("cache_write_per_million"))]
    known = [rate for rate in rates if rate is not None]
    if not known:
        raise ValueError("pricing has no finite input rate")
    return max(known)


class Meter:
    """Reserve worst-case cost BEFORE dispatch.

    Bounds and all-inclusive rates must be verified by the run operator. Each
    request reserves the entire model input limit at the highest priced
    input or cache rate plus the requested output limit. This is conservative,
    not a billing API. A complete usage replaces that reserve with the price.
    When any count is unknown, the known counts still produce a lower bound.
    That floor is compared with the reserve before the cost is left unknown.
    If the floor exceeds the reserve, it is counted and dispatch stops.
    Otherwise the reserve stays, which is already at least the floor. A
    missing price is not invented, and a null rate is not billed as zero.
    """
    def __init__(self, config, max_usd, max_calls):
        positive(max_usd, "max_usd")
        if type(max_calls) is not int or max_calls < 1:
            raise ValueError("max_calls must be a positive integer")
        self.config, self.limit, self.max_calls = config, max_usd, max_calls
        self.accounted, self.calls = 0.0, 0
        self.halted = False

    def reserve(self, request):
        p = self.config["pricing"][request["model"]]
        maximum = (p["max_input_tokens"] * _reserve_rate(p)
                   + request["max_tokens"] * p["output_per_million"]) / 1_000_000
        if self.halted:
            raise BudgetExceeded("pricing_bound_exceeded")
        if self.calls >= self.max_calls:
            raise BudgetExceeded("call_limit_reached")
        if self.accounted + maximum > self.limit:
            raise BudgetExceeded("spend_limit_reached")
        self.calls += 1
        self.accounted += maximum
        return maximum

    def settle(self, reservation, request, completion):
        usage = completion.usage
        values = asdict(usage) if usage is not None else {}
        prices = self.config.get("pricing")
        price = prices.get(request["model"]) if isinstance(prices, dict) else None
        # A model with no price entry cannot be billed. Keep the reserve and
        # do not substitute another model's rates or a zero.
        if not isinstance(price, dict):
            return None
        product = 0.0
        known = 0
        priced = 0
        for field, rate_name in _USAGE_RATES:
            count = values.get(field)
            if type(count) is not int or count < 0:
                continue
            known += 1
            rate = _finite_rate(price.get(rate_name))
            if rate is None:
                # Zero tokens cost nothing at an unpriced rate. A positive
                # count cannot be priced, so the usage stays incomplete.
                if count == 0:
                    priced += 1
                continue
            product += count * rate
            priced += 1
        floor = product / 1_000_000
        complete = (usage is not None and known == len(_USAGE_RATES)
                    and priced == len(_USAGE_RATES))
        # The overrun check runs before an incomplete usage returns None.
        if floor > reservation + 1e-12:
            self.halted = True  # known tokens already exceed the bound
        if complete or floor > reservation + 1e-12:
            self.accounted += floor - reservation
        return floor if complete else None


class PromptStore:
    """Content-address cacheable blocks, including before a live journal write."""
    def __init__(self, directory, *, durable=False):
        self.directory, self.durable = Path(directory), durable
        self.blocks = {}

    def compact(self, request):
        system = []
        for block in request["system"]:
            if not block["cacheable"]:
                system.append(block)
                continue
            key = digest(block["text"])
            if key not in self.blocks:
                self.directory.mkdir(exist_ok=True)
                with (self.directory / f"{key}.json").open("x", encoding="utf-8") as handle:
                    handle.write(json.dumps(block["text"], ensure_ascii=False) + "\n")
                    if self.durable:
                        handle.flush()
                        os.fsync(handle.fileno())
                self.blocks[key] = block["text"]
            system.append({"text_sha256": key, "cacheable": True})
        return {**request, "system": system}


def expand_request(request, blocks):
    system = []
    for block in request["system"]:
        if "text_sha256" not in block:
            system.append(block)
            continue
        key = block["text_sha256"]
        if key not in blocks or digest(blocks[key]) != key:
            raise ValueError("missing or changed system prompt block")
        system.append({"text": blocks[key], "cacheable": block["cacheable"]})
    return {**request, "system": system}


class RecordingProvider:
    def __init__(self, provider, records, meter=None, *, expected_model=None, prompts=None):
        self.provider, self.records, self.meter = provider, records, meter
        self.name = provider.name
        self.expected_model, self.prompts = expected_model, prompts

    def configured(self):
        return self.provider.configured()

    def cache_reference_tokens(self, model):
        return self.provider.cache_reference_tokens(model)

    def supports_json_schema(self):
        # runtime.generate checks this on the object get_provider returns,
        # which is this wrapper. Forward it so a schema-off adapter is
        # refused before any budget charge. An adapter that omits the
        # method still accepts a schema.
        method = getattr(self.provider, "supports_json_schema", None)
        if not callable(method):
            return True
        return method()

    def generate(self, **kwargs):
        if self.expected_model is not None and kwargs["model"] != self.expected_model:
            raise RoutingMismatch("production request differs from selected candidate model")
        # A live call with no explicit timeout uses the candidate bound.
        # Moderation passes its own three-second timeout and keeps it.
        if self.meter is not None and kwargs.get("timeout") is None:
            kwargs = {**kwargs, "timeout": self.meter.config["timeout_seconds"]}
        request = {**kwargs, "system": [asdict(x) for x in kwargs["system"]]}
        stored = self.prompts.compact(request) if self.prompts else request
        # Eval ceiling before the adapter call. Fixture runs have no meter;
        # their zero cost is authored evidence, not a price.
        reservation = self.meter.reserve(kwargs) if self.meter else 0
        record = {"request": stored, "request_sha256": digest(request), "response": None,
                  "error": None, "cost_usd": None, "reserved_usd": reservation,
                  "provider": self.name, "model": kwargs.get("model"),
                  "resolved_model": None, "usage": None}
        self.records.append(record)
        start = time.perf_counter()
        try:
            result = self.provider.generate(**kwargs)
            record["response"] = asdict(result)
            record["resolved_model"] = result.resolved_model
            # Counts as the adapter reported them, including unknown (None).
            # Do not coerce a missing count to zero.
            record["usage"] = asdict(result.usage) if result.usage is not None else None
            if self.meter:
                # None when the usage is incomplete. The reserve stays unless
                # the known counts already exceed it. No price is invented.
                record["cost_usd"] = self.meter.settle(reservation, kwargs, result)
            else:
                record["cost_usd"] = 0.0
            return result
        except Exception as exc:
            record["error"] = type(exc).__name__  # no raw SDK bodies/credentials
            raise
        finally:
            record["latency_ms"] = (time.perf_counter() - start) * 1000


@contextmanager
def task_routing(provider, model):
    # Install the candidate id on the shared setting and clear per-task
    # overrides. An operator shell must not redirect the candidate's call.
    # Blank values are unset, so the three voice/intention tasks use `model`.
    # model_for asks get_provider for a default. The candidate id is the
    # environment below, so this patched provider is not asked for one.
    with patch.object(runtime, "get_provider", return_value=provider), \
         patch.dict(os.environ, {runtime.SHARED_MODEL_ENV: model,
                                 runtime.NODE_MODEL_ENV: "",
                                 runtime.INHABITANT_MODEL_ENV: "",
                                 runtime.INTENT_MODEL_ENV: "",
                                 runtime.MODERATION_MODEL_ENV: model,
                                 "NESTED_WORLDS_DISABLE_MODERATION": "0",
                                 "NESTED_WORLDS_MODERATION_BLOCK_EXTRA": "",
                                 "NESTED_WORLDS_MODERATION_WATCH_EXTRA": ""}):
        yield


def execute(case, outputs=None):
    import consciousness
    from consciousness import interventions
    from agents.personas import by_name
    from multiverse.node import SpatialNode
    outputs = [] if outputs is None else outputs
    transcript = []
    history = list(case.get("history", []))
    node = SpatialNode(**case["node"]) if "node" in case else None
    if node:
        node.id = case["id"]  # stable evaluation identity, never a stored node
        node.ripple_score = case.get("ripple_score", 0)
    for message in case["messages"]:
        if case["task"] == "node_voice":
            reply = consciousness.speak(node, message, history=history, transcript=transcript,
                                        ripple_score=node.ripple_score,
                                        speaker=case.get("speaker"), hinge=case.get("hinge", False))
            transcript.append({"user": message, "assistant": reply})
            outputs.append({"status": "spoken", "text": reply})
        elif case["task"] == "inhabitant_voice":
            reply = consciousness.voice_agent(by_name(case["persona"]), case["agent_name"],
                node, message, history=history, agent_memory=case.get("agent_memory"))
            outputs.append({"status": "spoken", "text": reply})
            history.append({"type": "AGENT_VOICE", "player": "Eval visitor",
                            "data": {"agent": case["agent_name"], "message": message, "reply": reply}})
        elif case["task"] == "intention":
            try:
                steps = interventions.propose(message, case["node"])
                outputs.append({"status": "ready", "steps": steps})
            except interventions.Clarification as exc:
                outputs.append({"status": "clarify", "text": str(exc)})
            except interventions.Unsupported:
                outputs.append({"status": "unsupported"})
        else:
            from server import moderation
            # Classifier trial even for clean/local-block inputs; end-to-end
            # screen is also observed using the SAME reply (never a second call).
            # A transport failure is not an allow: shared text holds.
            try:
                outcome = consciousness.classify_content(message)
                error = None
            except (BudgetExceeded, RoutingMismatch):
                raise
            except Exception as exc:
                outcome, error = "error", type(exc).__name__
            allowed = outcome == "allow"
            with patch.object(consciousness, "classify_content", return_value=outcome,
                              side_effect=RuntimeError("eval transport failure") if error else None), \
                 patch.object(moderation.guard, "moderation_reserve", return_value="ok"), \
                 patch.object(moderation.guard, "consume_model_action", return_value=True), \
                 patch.object(moderation.guard, "consume_moderation_action", return_value=True):
                screen = moderation.screen(message)
            outputs.append({"status": "classified", "allowed": allowed, "outcome": outcome,
                            "error": error, "local_tier": moderation._local_tier(message),
                            "screen": asdict(screen)})
    return outputs


def grade(case, outputs, calls, error):
    responses = [c["response"] for c in calls]
    valid = (len(responses) == len(case["messages"]) and
             all(r and r["complete"] and isinstance(r["text"], str) and r["text"].strip()
                 for r in responses))
    result = {"valid_completion": bool(valid), "task_correct": None, "screen_correct": None,
              "classifier_verdict_valid": False, "human_required": case["task"].endswith("voice"),
              "outcome": "awaiting_human" if case["task"].endswith("voice") else "completed"}
    if error == "BudgetExceeded":
        result["outcome"] = "interrupted" if calls else "not_run"
    elif any(c["error"] for c in calls):
        result["outcome"] = "transport_error"
    elif any(r and (not r["complete"] or not isinstance(r["text"], str) or not r["text"].strip())
             for r in responses):
        result.update(task_correct=False, outcome="invalid_completion")
        return result
    elif error == "RoutingMismatch" or not calls or len(calls) != len(case["messages"]):
        result["outcome"] = "harness_error"
    if result["outcome"] in OPERATIONAL_OUTCOMES:
        return result
    if not valid:
        result.update(task_correct=False, outcome="invalid_completion")
        return result
    if error:
        if case["task"] == "intention" and error == "ValueError":
            result.update(task_correct=False, outcome="model_failure")
        else:
            result["outcome"] = "harness_error"
        return result
    if case["task"] == "intention":
        try:
            raw = json.loads(responses[0]["text"])
            expected = case["expected"]
            result["task_correct"] = (raw == expected and outputs[0]["status"] == expected["status"])
            if expected["status"] == "ready":
                result["task_correct"] &= outputs[0]["steps"] == expected["steps"]
        except (ValueError, KeyError, TypeError, IndexError):
            result["task_correct"] = False
    elif case["task"] == "moderation":
        from consciousness import moderation_outcome
        response = responses[0]
        outcome = moderation_outcome(Completion(
            response.get("text"), bool(response.get("complete")),
            finish_reason=response.get("finish_reason") or "unknown"))
        result["classifier_verdict_valid"] = (outcome in ("allow", "block") and
                                               bool(outputs) and not outputs[0]["error"])
        result["task_correct"] = (result["classifier_verdict_valid"] and
                                  outputs[0]["allowed"] == (outcome == "allow") and
                                  outputs[0]["allowed"] == case["expected"]["allowed"])
        if result["classifier_verdict_valid"]:
            result["screen_correct"] = outputs[0]["screen"]["allowed"] == case["expected"]["allowed"]
    if result["task_correct"] is False:
        result["outcome"] = "model_failure"
    return result


def provenance():
    def git(*args):
        try:
            return subprocess.check_output(["git", "-c", "core.fsmonitor=false", *args],
                                           cwd=ROOT, text=True, stderr=subprocess.PIPE).strip()
        except (subprocess.CalledProcessError, OSError) as exc:
            raise ValueError("evaluation provenance requires a readable Git worktree") from exc
    files = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCE_FILES}
    return {"commit": git("rev-parse", "HEAD"), "dirty": bool(git("status", "--porcelain")),
            "source_sha256": files, "source_bundle_sha256": digest(files),
            "python": sys.version, "anthropic_sdk": importlib.metadata.version("anthropic")}


def require_live_ceiling(max_usd, max_calls):
    """Refuse a live run that did not name both spend limits.

    ``None`` is the CLI default when ``--max-usd`` or ``--max-calls`` is
    omitted. There is no default ceiling. A present but non-positive limit
    is still rejected by ``Meter``.
    """
    if max_usd is None or max_calls is None:
        raise ValueError(
            "live run requires an explicit spend ceiling (--max-usd and --max-calls); "
            "no default ceiling"
        )


_DESTINATION_REFUSAL = (
    "non-anthropic live run requires --allow-destination HOST "
    "exactly matching the resolved base URL host; no default destination"
)


def resolved_destination_host(provider):
    """Host the adapter will send to. Not the URL, the userinfo, or the key.

    ``openai_compatible`` uses the host of the base URL that adapter already
    parsed. Any other non-anthropic adapter must expose ``destination_host``
    as that same host string. A wildcard or a URL is not a host.
    """
    if getattr(provider, "name", None) == "openai_compatible":
        from urllib.parse import urlsplit
        from consciousness.openai_compat_provider import _settings
        base = _settings().base
        host = None if base is None else urlsplit(base.url).hostname
    else:
        host = getattr(provider, "destination_host", None)
    if (not isinstance(host, str) or not host or "*" in host or "/" in host
            or any(ch.isspace() for ch in host)):
        raise ValueError("live run has no resolved destination host")
    return host


def approve_destination(host, allow_destination):
    """One exact host for this run. No allowlist, no environment default, no wildcard."""
    if not isinstance(allow_destination, str):
        raise ValueError(_DESTINATION_REFUSAL)
    approved = allow_destination.strip()
    if not approved or approved != host or "*" in approved or "/" in approved:
        raise ValueError(_DESTINATION_REFUSAL)
    return host


def open_live_provider(config, allow_destination=None):
    """Build the candidate's adapter from the registry. No default.

    ``anthropic`` keeps a fresh instance and the reviewed-destination
    check so client options are not written onto the process singleton.
    Every other registered adapter is the registry's own instance, and a
    live run refuses unless ``allow_destination`` is the host of that
    adapter's resolved base URL. This function does not set a base URL,
    a model id, or a credential, and it does not read an allowlist from
    the environment.

    Returns ``(provider, destination_host)``. The host is the approved
    destination, never the URL.
    """
    key = provider_key(config)
    if key not in runtime.provider_names():
        raise ValueError("provider has no evaluated adapter; no implicit fallback")
    if key == "anthropic":
        from consciousness.anthropic_provider import AnthropicProvider
        provider = AnthropicProvider()
        client = provider._get_client()
        # No alternate destination inherited from an operator's shell.
        if str(client.base_url).rstrip("/") != "https://api.anthropic.com":
            raise ValueError("only the reviewed direct Anthropic destination is supported")
        provider._client = client.with_options(max_retries=0, timeout=config["timeout_seconds"])
        host = "api.anthropic.com"
    else:
        provider = runtime.build_provider(key)
        host = None
    if not provider.configured():
        raise ValueError("provider is unconfigured")
    if key != "anthropic":
        host = resolved_destination_host(provider)
        approve_destination(host, allow_destination)
    return provider, host


def run(corpus, config, output, *, split="development", repeats=1, seed=0,
        tasks=TASKS, live=False, max_usd=None, max_calls=None, provider=None, brief=None,
        allow_destination=None):
    validate_candidate(config, live)
    validate_corpus_version(corpus)
    if type(repeats) is not int or repeats < 1 or split not in ("development", "holdout"):
        raise ValueError("positive repeats and one explicit split required")
    cases = [c for c in corpus["cases"] if c["split"] == split and c["task"] in tasks]
    if not cases:
        raise ValueError("no cases selected")
    if live:
        # Before the brief and before any adapter is built, so a missing
        # ceiling cannot construct a client.
        require_live_ceiling(max_usd, max_calls)
        validate_brief(brief, {c["task"] for c in cases})
    meter = Meter(config, max_usd, max_calls) if live else None
    destination_host = None
    if live and provider is None:
        # The candidate names the adapter. NESTED_WORLDS_PROVIDER is not read.
        provider, destination_host = open_live_provider(config, allow_destination)
    output = Path(output)
    schedule = [(c, repeat) for repeat in range(repeats) for c in cases]
    random.Random(seed).shuffle(schedule)
    rubric = read_json(ROOT / "evals/rubric.json")
    provenance_record = provenance()
    provenance_record["destination_host"] = destination_host
    result = {"schema_version": 2, "evidence": "live" if live else "fixture",
              "started_at": datetime.now(timezone.utc).isoformat(), "candidate": config,
              "corpus_version": corpus["version"], "corpus_sha256": digest(corpus),
              "rubric_sha256": digest(rubric), "rubric": rubric,
              "provenance": provenance_record, "destination_host": destination_host,
              "split": split, "repeats": repeats, "seed": seed,
              "selection_brief": brief,
              "case_ids": [c["id"] for c in cases], "planned_trials": len(schedule),
              "budget": {"max_usd": max_usd, "max_calls": max_calls},
              "trials": [], "status": "running"}
    output.mkdir(parents=True, exist_ok=False)
    os.chmod(output, 0o700)
    prompts = PromptStore(output / "prompts", durable=live)
    result["system_blocks"] = prompts.blocks
    write_json(output / "run.json", result)
    write_json(output / "corpus.json", corpus)
    write_json(output / "rubric.json", rubric)
    with (output / "trials.jsonl").open("x", encoding="utf-8") as journal:
        for case, repeat in schedule:
            calls, outputs, error, stop_reason = [], [], None, None
            selected = provider if live else FixtureProvider(case["fixture"])
            model = config["models"][case["task"]]
            recording = RecordingProvider(selected, calls, meter, expected_model=model, prompts=prompts)
            started = time.perf_counter()
            try:
                with task_routing(recording, model):
                    execute(case, outputs)
            except BudgetExceeded as exc:
                error, stop_reason = "BudgetExceeded", exc.reason
            except RoutingMismatch:
                error, stop_reason = "RoutingMismatch", "routing_mismatch"
            except Exception as exc:
                error = type(exc).__name__
            trial = {"id": f"{case['id']}:{repeat}", "case_id": case["id"], "repeat": repeat,
                     "task": case["task"], "category": case["category"], "critical": case["critical"],
                     "expected": case.get("expected"),
                     "outputs": outputs, "calls": calls, "error": error, "stop_reason": stop_reason,
                     "latency_ms": (time.perf_counter() - started) * 1000,
                     "grade": grade(case, outputs, calls, error)}
            result["trials"].append(trial)
            journal.write(json.dumps(trial, ensure_ascii=False, allow_nan=False) + "\n")
            journal.flush()
            if live:
                os.fsync(journal.fileno())
            if stop_reason or (meter and meter.halted):
                result["status"] = stop_reason or "pricing_bound_exceeded"
                break
    if result["status"] == "running":
        result["status"] = "completed"
    result["finished_at"] = datetime.now(timezone.utc).isoformat()
    result["budget"]["accounted_usd"] = meter.accounted if meter else 0
    result["budget"]["dispatched_calls"] = meter.calls if meter else sum(len(t["calls"]) for t in result["trials"])
    result["run_sha256"] = digest(result)
    write_json(output / "run.json", result)
    return result
