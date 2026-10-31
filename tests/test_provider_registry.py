"""Provider selection is a registry, and the default stays anthropic.

No live model call. The fixture adapter is registered in the test and
selected with NESTED_WORLDS_PROVIDER. Handlers and moderation are not patched.
"""
from __future__ import annotations

import importlib
import subprocess
import sys
import threading
from types import SimpleNamespace

import pytest

import consciousness
from consciousness import interventions, runtime
from consciousness.model_check import check_model_configuration, format_report
from consciousness.runtime import Completion, SystemBlock
from main import main
from multiverse.node import SpatialNode


READY = (
    '{"status":"ready","ambiguity":"none","steps":[{"op":"engrave","amount":1}]}'
)


class FixtureProvider:
    name = 'fixture'

    def __init__(self):
        self.calls = []

    def configured(self):
        return True

    def cache_reference_tokens(self, model):
        return None

    def model_id_validator(self):
        def verdict(model: str) -> str:
            if isinstance(model, str) and model.startswith('fixture-'):
                return 'ok'
            return 'reject'
        return verdict

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        model = kwargs['model']
        if model == 'fixture-moderation':
            text = 'ALLOW'
        elif model == 'fixture-intent':
            text = READY
        else:
            text = 'A remembered voice.'
        return Completion(text, True, provider=self.name, resolved_model=model)


def _isolate(monkeypatch):
    monkeypatch.setattr(runtime, '_REGISTERED', {})
    monkeypatch.delenv(runtime.PROVIDER_ENV, raising=False)
    for name in (
        runtime.SHARED_MODEL_ENV, runtime.NODE_MODEL_ENV,
        runtime.INHABITANT_MODEL_ENV, runtime.INTENT_MODEL_ENV,
        runtime.MODERATION_MODEL_ENV, 'ANTHROPIC_BASE_URL',
    ):
        monkeypatch.delenv(name, raising=False)


def _block_anthropic_import(monkeypatch):
    real = importlib.import_module

    def blocked(name, package=None):
        if name == 'anthropic' or name.startswith('anthropic.'):
            raise ImportError('blocked')
        return real(name, package)

    monkeypatch.setattr(importlib, 'import_module', blocked)


def test_default_provider_and_models_are_unchanged(monkeypatch):
    _isolate(monkeypatch)
    provider = runtime.get_provider()
    assert provider.name == 'anthropic'
    assert provider is runtime.get_provider()
    assert runtime.selected_provider_name() == 'anthropic'
    report = check_model_configuration()
    assert report.provider == 'anthropic'
    assert [task.provider for task in report.tasks] == ['anthropic'] * 4
    assert [task.model for task in report.tasks] == [
        'claude-opus-4-8', 'claude-opus-4-8', 'claude-opus-4-8', 'claude-haiku-4-5',
    ]
    assert [task.source for task in report.tasks] == ['default'] * 4
    assert report.hard == ()


def test_provider_name_is_stripped_and_lowercased(monkeypatch):
    _isolate(monkeypatch)
    monkeypatch.setenv(runtime.PROVIDER_ENV, '  Anthropic ')
    assert runtime.selected_provider_name() == 'anthropic'
    assert runtime.get_provider().name == 'anthropic'


@pytest.mark.parametrize('raw', ['', '   ', '\n\t'])
def test_blank_provider_fails_with_one_line(monkeypatch, raw):
    _isolate(monkeypatch)
    monkeypatch.setenv(runtime.PROVIDER_ENV, raw)
    with pytest.raises(SystemExit) as caught:
        runtime.get_provider()
    line = str(caught.value)
    assert line == 'NESTED_WORLDS_PROVIDER is empty (valid: anthropic)'
    assert '\n' not in line


def test_unknown_provider_names_the_variable_and_the_valid_names(monkeypatch):
    _isolate(monkeypatch)
    runtime.register_provider('fixture', lambda: FixtureProvider())
    monkeypatch.setenv(runtime.PROVIDER_ENV, 'openai')
    with pytest.raises(SystemExit) as caught:
        runtime.get_provider()
    line = str(caught.value)
    assert line == (
        "NESTED_WORLDS_PROVIDER='openai' is not a known text provider "
        "(valid: anthropic, fixture)"
    )
    assert '\n' not in line


def test_unsafe_provider_value_is_not_echoed(monkeypatch):
    _isolate(monkeypatch)
    secret = 'sk-ant-api03-secret-value'
    monkeypatch.setenv(runtime.PROVIDER_ENV, secret)
    with pytest.raises(SystemExit) as caught:
        runtime.get_provider()
    line = str(caught.value)
    assert secret not in line
    assert line == (
        'NESTED_WORLDS_PROVIDER is not a known text provider (valid: anthropic)'
    )


def test_builtin_provider_cannot_be_replaced():
    with pytest.raises(ValueError, match='built-in'):
        runtime.register_provider('Anthropic', lambda: FixtureProvider())


def test_serve_rejects_an_unknown_provider_before_the_listener(monkeypatch):
    import server

    _isolate(monkeypatch)
    monkeypatch.setenv(runtime.PROVIDER_ENV, 'openai')
    monkeypatch.setattr(server.observability, 'setup', lambda: None)
    monkeypatch.setattr(server.guard, 'canonical_seed', lambda: None)

    def opened(*args, **kwargs):
        raise AssertionError('listener opened')

    monkeypatch.setattr(server, '_ThreadedServer', opened)
    with pytest.raises(SystemExit) as caught:
        server.run(host='127.0.0.1', port=0)
    line = str(caught.value)
    assert line == (
        "NESTED_WORLDS_PROVIDER='openai' is not a known text provider "
        "(valid: anthropic)"
    )


def test_models_command_rejects_an_unknown_provider(monkeypatch, capsys):
    _isolate(monkeypatch)
    monkeypatch.setenv(runtime.PROVIDER_ENV, 'openai')
    with pytest.raises(SystemExit) as caught:
        main(['models'])
    assert "NESTED_WORLDS_PROVIDER='openai'" in str(caught.value)
    assert 'anthropic' in str(caught.value)
    assert capsys.readouterr().out == ''


def test_missing_sdk_names_the_extra_and_does_not_listen(monkeypatch, capsys):
    import server

    _isolate(monkeypatch)
    _block_anthropic_import(monkeypatch)
    with pytest.raises(SystemExit) as caught:
        main(['models'])
    line = str(caught.value)
    assert line == (
        "NESTED_WORLDS_PROVIDER=anthropic requires the optional extra "
        "enfolded[anthropic] (package 'anthropic' is not installed)"
    )
    assert capsys.readouterr().out == ''
    monkeypatch.setattr(server.observability, 'setup', lambda: None)
    monkeypatch.setattr(server.guard, 'canonical_seed', lambda: None)

    def opened(*args, **kwargs):
        raise AssertionError('listener opened')

    monkeypatch.setattr(server, '_ThreadedServer', opened)
    with pytest.raises(SystemExit) as caught:
        server.run(host='127.0.0.1', port=0)
    assert str(caught.value) == line


def test_fixture_is_selected_for_every_task_with_its_own_model(monkeypatch, capsys):
    _isolate(monkeypatch)
    fixture = FixtureProvider()
    runtime.register_provider('fixture', lambda: fixture)
    monkeypatch.setenv(runtime.PROVIDER_ENV, 'fixture')
    monkeypatch.setenv(runtime.SHARED_MODEL_ENV, 'fixture-shared')
    monkeypatch.setenv(runtime.NODE_MODEL_ENV, 'fixture-node')
    monkeypatch.setenv(runtime.INTENT_MODEL_ENV, 'fixture-intent')
    monkeypatch.setenv(runtime.MODERATION_MODEL_ENV, 'fixture-moderation')
    assert runtime.get_provider() is fixture

    node = SpatialNode(name='Vault', level='Object', properties={'surface': 'smooth'})
    assert consciousness.speak(node, 'Now?') == 'A remembered voice.'
    assert consciousness.voice_agent(
        SimpleNamespace(name='tender'), 'Tessera', node, 'Hello',
    ) == 'A remembered voice.'
    assert consciousness.classify_content('fixture input') == 'allow'
    assert interventions.propose('cut a pattern', {'level': 'Object'}) == [
        {'op': 'engrave', 'amount': 1},
    ]
    assert [call['model'] for call in fixture.calls] == [
        'fixture-node', 'fixture-shared', 'fixture-moderation', 'fixture-intent',
    ]

    report = check_model_configuration()
    assert report.provider == 'fixture'
    assert report.hard == ()
    by_task = {task.task: task for task in report.tasks}
    assert by_task['node'].model == 'fixture-node'
    assert by_task['node'].source == 'task env'
    assert by_task['node'].provider == 'fixture'
    assert by_task['inhabitant'].model == 'fixture-shared'
    assert by_task['inhabitant'].source == 'NESTED_WORLDS_MODEL'
    assert by_task['intent'].model == 'fixture-intent'
    assert by_task['intent'].source == 'task env'
    assert by_task['moderation'].model == 'fixture-moderation'
    assert by_task['moderation'].source == 'task env'
    assert all(task.problems == () for task in report.tasks)
    text = format_report(report)
    assert 'text provider: fixture' in text
    assert 'provider=fixture' in text
    assert 'model=fixture-node' in text
    assert 'model=fixture-moderation' in text

    before = len(fixture.calls)
    main(['models'])
    assert len(fixture.calls) == before
    printed = capsys.readouterr().out
    assert 'text provider: fixture' in printed
    assert 'probe ' not in printed
    main(['models', '--probe'])
    probed = capsys.readouterr().out
    assert 'probe fixture-node: accepted' in probed
    assert 'probe fixture-shared: accepted' in probed
    assert 'probe fixture-intent: accepted' in probed
    assert 'probe fixture-moderation: accepted' in probed
    assert len(fixture.calls) == before + 4


def test_fixture_validator_is_the_one_that_judges(monkeypatch):
    _isolate(monkeypatch)
    runtime.register_provider('fixture', lambda: FixtureProvider())
    monkeypatch.setenv(runtime.PROVIDER_ENV, 'fixture')
    monkeypatch.setenv(runtime.NODE_MODEL_ENV, 'fixture-node')
    monkeypatch.setenv(runtime.INHABITANT_MODEL_ENV, 'fixture-inhabitant')
    monkeypatch.setenv(runtime.INTENT_MODEL_ENV, 'claude-opus-4-8')
    monkeypatch.setenv(runtime.MODERATION_MODEL_ENV, 'fixture-moderation')
    report = check_model_configuration()
    assert report.hard != ()
    problem = next(task for task in report.tasks if task.task == 'intent').problems[0]
    assert problem.severity == 'hard'
    assert 'fixture' in problem.text
    assert next(task for task in report.tasks if task.task == 'node').problems == ()


def test_fixture_selection_does_not_need_the_anthropic_sdk(monkeypatch):
    _isolate(monkeypatch)
    _block_anthropic_import(monkeypatch)
    fixture = FixtureProvider()
    runtime.register_provider('fixture', lambda: fixture)
    monkeypatch.setenv(runtime.PROVIDER_ENV, 'fixture')
    monkeypatch.setenv(runtime.NODE_MODEL_ENV, 'fixture-node')
    monkeypatch.setenv(runtime.INHABITANT_MODEL_ENV, 'fixture-inhabitant')
    monkeypatch.setenv(runtime.INTENT_MODEL_ENV, 'fixture-intent')
    monkeypatch.setenv(runtime.MODERATION_MODEL_ENV, 'fixture-moderation')
    report = check_model_configuration()
    assert report.provider == 'fixture'
    assert report.hard == ()
    assert runtime.get_provider() is fixture


def test_import_and_fixture_provider_need_no_sdk():
    script = r"""
import os, sys
sys.modules['anthropic'] = None
os.environ.pop('NESTED_WORLDS_PROVIDER', None)
import consciousness.runtime as runtime
import consciousness.anthropic_provider
import server.handlers
assert sys.modules.get('anthropic') is None

class Fixture:
    name = 'fixture'
    def configured(self):
        return True
    def cache_reference_tokens(self, model):
        return None
    def generate(self, **kwargs):
        raise AssertionError('generate')

runtime.register_provider('fixture', lambda: Fixture())
os.environ['NESTED_WORLDS_PROVIDER'] = 'fixture'
assert runtime.get_provider().name == 'fixture'
from consciousness.model_check import check_model_configuration
report = check_model_configuration()
assert report.provider == 'fixture'
assert all(task.provider == 'fixture' for task in report.tasks)

os.environ['NESTED_WORLDS_PROVIDER'] = 'anthropic'
try:
    check_model_configuration()
except SystemExit as exc:
    text = str(exc)
else:
    raise SystemExit('missing sdk should fail startup')
assert text == (
    "NESTED_WORLDS_PROVIDER=anthropic requires the optional extra "
    "enfolded[anthropic] (package 'anthropic' is not installed)"
)
assert '\n' not in text
"""
    completed = subprocess.run(
        [sys.executable, '-c', script],
        check=False, capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout


def test_concurrency_limits_do_not_cross_providers(monkeypatch):
    monkeypatch.setenv('NESTED_WORLDS_ANTHROPIC_CONCURRENCY', '1')
    monkeypatch.setenv('NESTED_WORLDS_FIXTURE_CONCURRENCY', '2')
    assert runtime._concurrency_limit('anthropic') == 1
    assert runtime._concurrency_limit() == 1
    assert runtime._concurrency_limit('fixture') == 2
    monkeypatch.setenv('NESTED_WORLDS_FIXTURE_CONCURRENCY', 'bad')
    assert runtime._concurrency_limit('fixture') == 8
    monkeypatch.setenv('NESTED_WORLDS_FIXTURE_CONCURRENCY', '0')
    assert runtime._concurrency_limit('fixture') == 1
    monkeypatch.setenv('NESTED_WORLDS_FIXTURE_CONCURRENCY', '2')
    anthropic_gate = runtime._semaphore_for('anthropic')
    fixture_gate = runtime._semaphore_for('fixture')
    assert anthropic_gate is not fixture_gate
    try:
        assert anthropic_gate.acquire(blocking=False)
        assert not anthropic_gate.acquire(blocking=False)
        assert fixture_gate.acquire(blocking=False)
        assert fixture_gate.acquire(blocking=False)
        assert not fixture_gate.acquire(blocking=False)
    finally:
        for gate, times in ((anthropic_gate, 1), (fixture_gate, 2)):
            for _ in range(times):
                try:
                    gate.release()
                except ValueError:
                    break


def test_generate_waits_on_the_selected_providers_limit(monkeypatch):
    _isolate(monkeypatch)
    entered = threading.Event()

    class Fixture:
        name = 'fixture'

        def configured(self):
            return True

        def cache_reference_tokens(self, model):
            return None

        def generate(self, **kwargs):
            entered.set()
            return Completion('ok', True, provider='fixture')

    class Gate:
        def __init__(self):
            self.waiting = threading.Event()
            self.opened = threading.Event()

        def __enter__(self):
            self.waiting.set()
            assert self.opened.wait(2)
            return self

        def __exit__(self, *args):
            return False

    runtime.register_provider('fixture', lambda: Fixture())
    monkeypatch.setenv(runtime.PROVIDER_ENV, 'fixture')
    monkeypatch.setenv('NESTED_WORLDS_ANTHROPIC_CONCURRENCY', '1')
    gate = Gate()
    real_semaphore = runtime._semaphore_for

    def semaphore_for(name):
        if name == 'fixture':
            return gate
        return real_semaphore(name)

    monkeypatch.setattr(runtime, '_semaphore_for', semaphore_for)

    def run():
        runtime.generate(
            endpoint='speak', model='fixture-node', max_tokens=8,
            system=(SystemBlock('s'),),
            messages=[{'role': 'user', 'content': 'hi'}],
        )

    thread = threading.Thread(target=run)
    thread.start()
    try:
        assert gate.waiting.wait(2)
        assert not entered.is_set()
        other = real_semaphore('anthropic')
        assert other.acquire(blocking=False)
        other.release()
        gate.opened.set()
        thread.join(2)
        assert not thread.is_alive()
        assert entered.is_set()
    finally:
        gate.opened.set()
        thread.join(2)
