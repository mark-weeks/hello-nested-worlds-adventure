"""Per-task text providers. No live provider call.

Each task may name its own adapter. Unset stays on the process default,
which stays anthropic. A blank, unknown, or unsafe name fails closed and
does not fall through. Default model ids come only from that task's
adapter. Slots stay per provider, and a failure is not retried elsewhere.
"""
from __future__ import annotations

import threading
import time

import pytest

import consciousness
from consciousness import runtime
from consciousness.model_check import check_model_configuration, format_report
from consciousness.runtime import Completion, ProviderBusy, SystemBlock, VoiceBudgetLimited
from main import main
from server import guard


def _isolate(monkeypatch):
    monkeypatch.setattr(runtime, "_REGISTERED", {})
    monkeypatch.delenv(runtime.PROVIDER_ENV, raising=False)
    for name in (
        runtime.SHARED_MODEL_ENV, runtime.NODE_MODEL_ENV,
        runtime.INHABITANT_MODEL_ENV, runtime.INTENT_MODEL_ENV,
        runtime.MODERATION_MODEL_ENV,
    ):
        monkeypatch.delenv(name, raising=False)
    runtime.reset_provider_selection()


class _Adapter:
    def __init__(self, name, *, default=None, validator=None, configured=True):
        self.name = name
        self.calls = []
        self._default = default
        self._validator = validator
        self._configured = configured

    def configured(self):
        return self._configured

    def default_model(self, task):
        if self._default is None:
            return None
        return self._default(task)

    def model_id_validator(self):
        return self._validator

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        return Completion("heard", True, provider=self.name, resolved_model=kwargs["model"])


def _register(name, adapter):
    runtime.register_provider(name, lambda adapter=adapter: adapter)
    return adapter


def _call(task, model, *, voice_budget=False):
    return runtime.generate(
        endpoint="test", model=model, system=(SystemBlock(text="s"),),
        messages=[{"role": "user", "content": "hi"}], max_tokens=8,
        voice_budget=voice_budget, task=task,
    )


def test_unset_task_providers_share_the_process_default(monkeypatch):
    _isolate(monkeypatch)
    process = runtime.get_provider()
    assert process.name == "anthropic"
    for task in runtime.TASKS:
        assert runtime.provider_for(task) is process
        assert runtime.resolve_provider(task).source == runtime.SOURCE_PROVIDER_DEFAULT
    assert runtime.model_for(runtime.NODE_TASK) == "claude-opus-4-8"
    assert runtime.model_for(runtime.MODERATION_TASK) == "claude-haiku-4-5"


def test_task_override_uses_that_adapters_default_only(monkeypatch):
    _isolate(monkeypatch)
    node = _register("nodeprov", _Adapter(
        "nodeprov", default=lambda task: "node-default" if task != "moderation" else "node-mod",
    ))
    monkeypatch.setenv(runtime.NODE_PROVIDER_ENV, "nodeprov")
    assert runtime.provider_for(runtime.NODE_TASK) is node
    assert runtime.provider_for(runtime.INHABITANT_TASK).name == "anthropic"
    assert runtime.model_for(runtime.NODE_TASK) == "node-default"
    assert "claude" not in runtime.model_for(runtime.NODE_TASK)
    assert runtime.model_for(runtime.INHABITANT_TASK) == "claude-opus-4-8"
    report = check_model_configuration()
    by_task = {task.task: task for task in report.tasks}
    assert by_task["node"].provider == "nodeprov"
    assert by_task["node"].provider_source == "task env"
    assert by_task["inhabitant"].provider == "anthropic"
    assert "per task" == report.provider
    text = format_report(report)
    assert "text provider: per task" in text
    assert "provider_source=task env" in text


def test_an_adapter_without_default_model_does_not_inherit_anthropic_ids(monkeypatch):
    _isolate(monkeypatch)
    monkeypatch.setenv(runtime.NODE_PROVIDER_ENV, "openai_compatible")
    monkeypatch.setenv(runtime.MODERATION_PROVIDER_ENV, "openai_compatible")
    assert runtime.model_for(runtime.NODE_TASK) == ""
    assert runtime.model_for(runtime.MODERATION_TASK) == ""
    assert runtime.model_for(runtime.INHABITANT_TASK) == "claude-opus-4-8"
    report = check_model_configuration()
    line = report.failure_line()
    assert "openai_compatible" in line
    assert "has no default model" in line
    assert "claude" not in line
    node = next(task for task in report.tasks if task.task == "node")
    assert node.model == ""
    assert "claude-opus-4-8" not in format_report(report).split("inhabitant")[0]


def test_shared_model_is_an_id_on_every_voice_provider_except_moderation(monkeypatch):
    _isolate(monkeypatch)
    _register("homeprov", _Adapter("homeprov", default=lambda task: "home-default"))
    _register("voiceprov", _Adapter("voiceprov", default=lambda task: "voice-default"))
    monkeypatch.setenv(runtime.PROVIDER_ENV, "homeprov")
    monkeypatch.setenv(runtime.NODE_PROVIDER_ENV, "voiceprov")
    monkeypatch.setenv(runtime.SHARED_MODEL_ENV, "shared-id")
    assert runtime.model_for(runtime.NODE_TASK) == "shared-id"
    assert runtime.model_for(runtime.INHABITANT_TASK) == "shared-id"
    assert runtime.model_for(runtime.INTENT_TASK) == "shared-id"
    assert runtime.model_for(runtime.MODERATION_TASK) == "home-default"
    report = check_model_configuration()
    node = next(task for task in report.tasks if task.task == "node")
    assert any(problem.severity == "soft" and "shared onto provider voiceprov" in problem.text
               for problem in node.problems)
    inhabitant = next(task for task in report.tasks if task.task == "inhabitant")
    assert inhabitant.problems == ()
    assert report.hard == ()


def test_a_validator_reject_of_the_shared_id_is_hard(monkeypatch):
    _isolate(monkeypatch)

    def verdict(model):
        return "ok" if model.startswith("ok-") else "reject"

    _register("strictprov", _Adapter("strictprov", validator=verdict,
                                     default=lambda task: "ok-default"))
    monkeypatch.setenv(runtime.NODE_PROVIDER_ENV, "strictprov")
    monkeypatch.setenv(runtime.SHARED_MODEL_ENV, "claude-opus-4-8")
    report = check_model_configuration()
    node = next(task for task in report.tasks if task.task == "node")
    assert node.problems[0].severity == "hard"
    assert report.hard != ()


@pytest.mark.parametrize("raw", ["", "   ", "\n\t"])
def test_blank_task_provider_does_not_fall_through(monkeypatch, raw):
    _isolate(monkeypatch)
    monkeypatch.setenv(runtime.NODE_PROVIDER_ENV, raw)
    with pytest.raises(SystemExit) as caught:
        runtime.provider_for(runtime.NODE_TASK)
    line = str(caught.value)
    assert line == (
        "NESTED_WORLDS_NODE_PROVIDER is empty "
        "(valid: anthropic, openai_compatible)"
    )
    assert "\n" not in line
    # A failed selection is not cached, so a correction is read next.
    monkeypatch.setenv(runtime.NODE_PROVIDER_ENV, "openai_compatible")
    assert runtime.provider_for(runtime.NODE_TASK).name == "openai_compatible"


def test_unknown_and_unsafe_task_providers_fail_closed(monkeypatch, capsys):
    _isolate(monkeypatch)
    monkeypatch.setenv(runtime.INTENT_PROVIDER_ENV, "openai")
    with pytest.raises(SystemExit) as caught:
        main(["models"])
    assert str(caught.value) == (
        "NESTED_WORLDS_INTENT_PROVIDER='openai' is not a known text provider "
        "(valid: anthropic, openai_compatible)"
    )
    assert capsys.readouterr().out == ""

    secret = "sk-live-supersecret-value"
    monkeypatch.setenv(runtime.INTENT_PROVIDER_ENV, secret)
    with pytest.raises(SystemExit) as caught:
        runtime.provider_for(runtime.INTENT_TASK)
    line = str(caught.value)
    assert secret not in line
    assert "sk-" not in line
    assert line.startswith("NESTED_WORLDS_INTENT_PROVIDER is not a known text provider")


def test_a_replaced_get_provider_supplies_tasks_that_do_not_override(monkeypatch):
    _isolate(monkeypatch)
    patched = _Adapter(
        "patched",
        default=lambda task: "patched-mod" if task == "moderation" else "patched-voice",
    )
    monkeypatch.setattr(runtime, "get_provider", lambda: patched)
    assert runtime.provider_for(runtime.NODE_TASK) is patched
    assert runtime.model_for(runtime.NODE_TASK) == "patched-voice"
    assert runtime.model_for(runtime.MODERATION_TASK) == "patched-mod"
    _call(runtime.INHABITANT_TASK, "patched-voice")
    assert patched.calls[0]["model"] == "patched-voice"

    runtime.reset_provider_selection()
    other = _register("otherprov", _Adapter("otherprov", default=lambda task: "other-id"))
    monkeypatch.setenv(runtime.NODE_PROVIDER_ENV, "otherprov")
    assert runtime.provider_for(runtime.NODE_TASK) is other
    assert runtime.model_for(runtime.NODE_TASK) == "other-id"
    assert runtime.provider_for(runtime.INTENT_TASK) is patched


def test_same_provider_name_is_one_instance_and_a_later_bad_value_does_not_exit(monkeypatch):
    _isolate(monkeypatch)
    monkeypatch.setenv(runtime.NODE_PROVIDER_ENV, "openai_compatible")
    monkeypatch.setenv(runtime.INTENT_PROVIDER_ENV, " OpenAI_Compatible ")
    first = runtime.provider_for(runtime.NODE_TASK)
    assert runtime.provider_for(runtime.INTENT_TASK) is first
    monkeypatch.setenv(runtime.NODE_PROVIDER_ENV, "not-a-provider")
    assert runtime.provider_for(runtime.NODE_TASK) is first


def test_generate_routes_each_task_and_does_not_retry_another_provider(monkeypatch):
    _isolate(monkeypatch)
    boom = _register("boomprov", _Adapter("boomprov"))
    fast = _register("fastprov", _Adapter("fastprov"))

    def explode(**kwargs):
        boom.calls.append(kwargs)
        raise RuntimeError("down")

    boom.generate = explode
    monkeypatch.setenv(runtime.NODE_PROVIDER_ENV, "boomprov")
    monkeypatch.setenv(runtime.INHABITANT_PROVIDER_ENV, "fastprov")
    with pytest.raises(RuntimeError, match="down"):
        _call(runtime.NODE_TASK, "boom-model")
    assert len(boom.calls) == 1
    assert fast.calls == []
    heard = _call(runtime.INHABITANT_TASK, "fast-model")
    assert heard.provider == "fastprov"
    assert len(boom.calls) == 1
    assert len(fast.calls) == 1


def test_a_full_provider_does_not_block_another_providers_task(monkeypatch):
    _isolate(monkeypatch)
    slow = _register("slowprov", _Adapter("slowprov"))
    fast = _register("fastprov", _Adapter("fastprov"))
    entered = threading.Event()
    release = threading.Event()

    def hold(**kwargs):
        slow.calls.append(kwargs)
        entered.set()
        assert release.wait(5)
        return Completion("slow", True, provider="slowprov", resolved_model=kwargs["model"])

    slow.generate = hold
    monkeypatch.setenv(runtime.NODE_PROVIDER_ENV, "slowprov")
    monkeypatch.setenv(runtime.INHABITANT_PROVIDER_ENV, "fastprov")
    monkeypatch.setenv("NESTED_WORLDS_SLOWPROV_CONCURRENCY", "1")
    errors = []

    def run_slow():
        try:
            _call(runtime.NODE_TASK, "slow-model")
        except Exception as exc:  # noqa: BLE001 — the thread must report every failure
            errors.append(exc)

    threading.Thread(target=run_slow, daemon=True).start()
    assert entered.wait(2)
    started = time.monotonic()
    heard = _call(runtime.INHABITANT_TASK, "fast-model")
    elapsed = time.monotonic() - started
    release.set()
    assert heard.text == "heard"
    assert elapsed < 0.5
    assert errors == []
    assert len(fast.calls) == 1

    # A saturated slot on the slow provider is that provider's wait only.
    monkeypatch.setenv("NESTED_WORLDS_SLOWPROV_SLOT_WAIT_SECONDS", "0")
    runtime._semaphores.clear()
    gate = runtime._semaphore_for("slowprov")
    assert gate.acquire(blocking=False)
    with pytest.raises(ProviderBusy):
        _call(runtime.NODE_TASK, "slow-model")
    assert _call(runtime.INHABITANT_TASK, "fast-model").provider == "fastprov"
    gate.release()


def test_voice_allowance_is_shared_across_providers(monkeypatch):
    _isolate(monkeypatch)
    _register("oneprov", _Adapter("oneprov"))
    _register("twoprov", _Adapter("twoprov"))
    monkeypatch.setenv(runtime.NODE_PROVIDER_ENV, "oneprov")
    monkeypatch.setenv(runtime.INHABITANT_PROVIDER_ENV, "twoprov")
    monkeypatch.setenv(guard.VOICE_CAP_ENV, "2")
    day = guard._utc_day()
    _call(runtime.NODE_TASK, "one-model", voice_budget=True)
    _call(runtime.INHABITANT_TASK, "two-model", voice_budget=True)
    with pytest.raises(VoiceBudgetLimited):
        _call(runtime.INTENT_TASK, "one-model", voice_budget=True)
    assert persistence_calls(guard.ANTHROPIC_BUCKET, day) == 3
    assert persistence_calls(guard.VOICE_BUCKET, day) == 0
    assert persistence_calls(guard.MODERATION_BUCKET, day) == 0


def test_a_cold_task_choice_publishes_its_name_with_its_source(monkeypatch):
    _isolate(monkeypatch)
    adapter = _register("raceprov", _Adapter("raceprov"))
    monkeypatch.setenv(runtime.NODE_PROVIDER_ENV, "raceprov")
    task = runtime.NODE_TASK

    # The old order published the source, then the name. A reader in that
    # gap raises KeyError. The locked helpers do not leave the gap.
    errors = []
    started = threading.Event()
    release = threading.Event()

    def unsafe_reader():
        started.set()
        assert release.wait(2)
        try:
            runtime._task_provider_names[task]
        except KeyError as exc:
            errors.append(exc)

    reader = threading.Thread(target=unsafe_reader)
    reader.start()
    assert started.wait(2)
    runtime._task_provider_sources[task] = runtime.SOURCE_PROVIDER_TASK
    release.set()
    reader.join(2)
    assert reader.is_alive() is False
    assert len(errors) == 1 and isinstance(errors[0], KeyError)
    runtime.reset_provider_selection()

    barrier = threading.Barrier(2)
    seen = []
    failures = []

    def publish():
        barrier.wait(2)
        runtime._publish_task_choice(task, runtime.SOURCE_PROVIDER_TASK, "raceprov")

    def observe():
        barrier.wait(2)
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            choice = runtime._read_task_choice(task)
            if choice is None:
                continue
            if choice != (runtime.SOURCE_PROVIDER_TASK, "raceprov"):
                failures.append(choice)
            seen.append(choice)
            return
        failures.append("timeout")

    pair = [threading.Thread(target=publish), threading.Thread(target=observe)]
    for thread in pair:
        thread.start()
    for thread in pair:
        thread.join(3)
    assert failures == []
    assert seen == [(runtime.SOURCE_PROVIDER_TASK, "raceprov")]

    runtime.reset_provider_selection()
    results = []
    call_errors = []
    start = threading.Barrier(2)

    def call():
        start.wait(2)
        try:
            results.append(runtime.provider_for(task))
        except Exception as exc:  # noqa: BLE001 — the thread must report every failure
            call_errors.append(exc)

    callers = [threading.Thread(target=call), threading.Thread(target=call)]
    for thread in callers:
        thread.start()
    for thread in callers:
        thread.join(3)
    assert call_errors == []
    assert results == [adapter, adapter]
    assert runtime._task_provider_names[task] == "raceprov"
    assert runtime._task_provider_sources[task] == runtime.SOURCE_PROVIDER_TASK


def persistence_calls(bucket, day):
    import persistence
    return persistence.get_cost_calls(bucket, day)


def test_models_and_serve_fail_closed_on_a_task_provider(monkeypatch, capsys):
    import server

    _isolate(monkeypatch)
    _register("okprov", _Adapter("okprov", default=lambda task: f"ok-{task}"))
    monkeypatch.setenv(runtime.PROVIDER_ENV, "okprov")
    monkeypatch.setenv(runtime.MODERATION_PROVIDER_ENV, "   ")
    with pytest.raises(SystemExit) as caught:
        main(["models"])
    assert "NESTED_WORLDS_MODERATION_PROVIDER is empty" in str(caught.value)
    assert capsys.readouterr().out == ""

    monkeypatch.setattr(server.observability, "setup", lambda: None)
    monkeypatch.setattr(server.guard, "canonical_seed", lambda: None)

    def opened(*_args, **_kwargs):
        raise AssertionError("listener opened")

    monkeypatch.setattr(server, "_ThreadedServer", opened)
    with pytest.raises(SystemExit) as caught:
        server.run(host="127.0.0.1", port=0)
    assert "NESTED_WORLDS_MODERATION_PROVIDER is empty" in str(caught.value)


def test_models_names_each_task_and_a_missing_task_sdk(monkeypatch, capsys):
    import importlib

    _isolate(monkeypatch)
    _register("okprov", _Adapter("okprov", default=lambda task: f"ok-{task}"))
    for task, env in (
        (runtime.NODE_TASK, runtime.NODE_PROVIDER_ENV),
        (runtime.INHABITANT_TASK, runtime.INHABITANT_PROVIDER_ENV),
        (runtime.INTENT_TASK, runtime.INTENT_PROVIDER_ENV),
    ):
        monkeypatch.setenv(env, "okprov")
    monkeypatch.setenv(runtime.MODERATION_PROVIDER_ENV, "anthropic")
    real = importlib.import_module

    def blocked(name, package=None):
        if name == "anthropic" or (isinstance(name, str) and name.startswith("anthropic.")):
            raise ModuleNotFoundError("No module named 'anthropic'", name="anthropic")
        return real(name, package)

    monkeypatch.setattr(importlib, "import_module", blocked)
    with pytest.raises(SystemExit) as caught:
        main(["models"])
    assert str(caught.value) == (
        "NESTED_WORLDS_MODERATION_PROVIDER=anthropic requires the optional extra "
        "enfolded[anthropic] (package 'anthropic' is not installed)"
    )
    assert capsys.readouterr().out == ""


def test_mixed_unconfigured_provider_is_named_and_does_not_skip_a_probe(monkeypatch, capsys):
    _isolate(monkeypatch)
    fixture = _register("okprov", _Adapter("okprov", default=lambda task: f"ok-{task}"))
    monkeypatch.setenv(runtime.PROVIDER_ENV, "okprov")
    monkeypatch.setenv(runtime.NODE_PROVIDER_ENV, "openai_compatible")
    monkeypatch.setenv(runtime.NODE_MODEL_ENV, "gateway-node")
    main(["models"])
    printed = capsys.readouterr().out
    assert "text provider: per task" in printed
    assert "provider not configured (node)" in printed
    assert "claude" not in printed
    with pytest.raises(SystemExit):
        main(["models", "--probe"])
    probed = capsys.readouterr().out
    assert "skipped: provider not configured" in probed
    assert "probe ok-inhabitant: accepted" in probed
    assert any(call["model"] == "ok-inhabitant" for call in fixture.calls)
    assert all(call["model"] != "gateway-node" for call in fixture.calls)


def test_intent_schema_note_follows_the_intent_provider(monkeypatch, capsys):
    _isolate(monkeypatch)
    _register("okprov", _Adapter("okprov", default=lambda task: f"ok-{task}"))
    monkeypatch.setenv(runtime.PROVIDER_ENV, "okprov")
    monkeypatch.setenv(runtime.INTENT_PROVIDER_ENV, "openai_compatible")
    monkeypatch.setenv(runtime.INTENT_MODEL_ENV, "gateway-intent")
    main(["models"])
    printed = capsys.readouterr().out
    assert "structured outputs off - intent calls will be refused" in printed
    assert "provider=openai_compatible" in printed


def test_configured_follows_the_task(monkeypatch):
    _isolate(monkeypatch)
    _register("openprov", _Adapter("openprov", configured=True, default=lambda task: "open"))
    _register("quietprov", _Adapter("quietprov", configured=False, default=lambda task: "q"))
    monkeypatch.setenv(runtime.PROVIDER_ENV, "openprov")
    monkeypatch.setenv(runtime.NODE_PROVIDER_ENV, "quietprov")
    assert runtime.configured(runtime.NODE_TASK) is False
    assert runtime.configured(runtime.INHABITANT_TASK) is True
    assert runtime.configured() is True


def test_every_task_override_survives_an_unusable_process_provider(monkeypatch):
    _isolate(monkeypatch)
    _register("okprov", _Adapter("okprov", default=lambda task: f"ok-{task}"))
    monkeypatch.setenv(runtime.PROVIDER_ENV, "not-a-provider")
    for env in runtime.TASK_PROVIDER_ENVS:
        monkeypatch.setenv(env, "okprov")
    report = check_model_configuration()
    assert report.hard == ()
    assert report.provider == "okprov"
    node = next(task for task in report.tasks if task.task == "node")
    assert any("shared onto provider" in problem.text for problem in node.problems) is False
    monkeypatch.setenv(runtime.SHARED_MODEL_ENV, "shared-id")
    runtime.reset_provider_selection()
    report = check_model_configuration()
    node = next(task for task in report.tasks if task.task == "node")
    assert any(problem.severity == "soft" for problem in node.problems)


def test_speak_uses_the_node_provider(monkeypatch):
    _isolate(monkeypatch)
    node = _register("nodeprov", _Adapter("nodeprov", default=lambda task: "node-voice"))
    monkeypatch.setenv(runtime.NODE_PROVIDER_ENV, "nodeprov")
    from multiverse.node import SpatialNode
    heard = consciousness.speak(
        SpatialNode(name="Vault", level="Object", properties={"surface": "smooth"}),
        "Now?",
    )
    assert heard == "heard"
    assert node.calls and node.calls[0]["model"] == "node-voice"
