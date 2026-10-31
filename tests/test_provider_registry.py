"""Provider selection is a registry, and the default stays anthropic.

No live model call. The fixture adapter is registered in the test and
selected with NESTED_WORLDS_PROVIDER. Handlers and moderation are not patched.
"""
from __future__ import annotations

import importlib
import subprocess
import sys
import threading
import time
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
        if name == 'anthropic' or (isinstance(name, str) and name.startswith('anthropic.')):
            raise ModuleNotFoundError("No module named 'anthropic'", name='anthropic')
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
    def default_model(self, task):
        if task == 'moderation':
            return 'fixture-moderation'
        return 'fixture-voice'
    def generate(self, **kwargs):
        raise AssertionError('generate')

runtime.register_provider('fixture', lambda: Fixture())
os.environ['NESTED_WORLDS_PROVIDER'] = 'fixture'
assert runtime.get_provider().name == 'fixture'
from consciousness.model_check import check_model_configuration
report = check_model_configuration()
assert report.provider == 'fixture'
assert all(task.provider == 'fixture' for task in report.tasks)
assert report.hard == ()

os.environ['NESTED_WORLDS_PROVIDER'] = 'anthropic'
runtime.reset_provider_selection()
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


class _OwnDefaults(FixtureProvider):
    def default_model(self, task):
        if task == runtime.MODERATION_TASK:
            return 'fixture-moderation'
        return 'fixture-voice'


def test_fixture_with_its_own_defaults_does_not_inherit_claude_ids(monkeypatch):
    _isolate(monkeypatch)
    fixture = _OwnDefaults()
    runtime.register_provider('fixture', lambda: fixture)
    monkeypatch.setenv(runtime.PROVIDER_ENV, 'fixture')
    assert runtime.model_for(runtime.NODE_TASK) == 'fixture-voice'
    assert runtime.model_for(runtime.INHABITANT_TASK) == 'fixture-voice'
    assert runtime.model_for(runtime.INTENT_TASK) == 'fixture-voice'
    assert runtime.model_for(runtime.MODERATION_TASK) == 'fixture-moderation'
    report = check_model_configuration()
    assert report.provider == 'fixture'
    assert report.hard == ()
    assert [task.source for task in report.tasks] == ['default'] * 4
    assert [task.model for task in report.tasks] == [
        'fixture-voice', 'fixture-voice', 'fixture-voice', 'fixture-moderation',
    ]
    assert all('claude' not in task.model for task in report.tasks)
    monkeypatch.setenv(runtime.SHARED_MODEL_ENV, 'fixture-shared')
    assert runtime.model_for(runtime.NODE_TASK) == 'fixture-shared'
    assert runtime.model_for(runtime.MODERATION_TASK) == 'fixture-moderation'
    monkeypatch.setenv(runtime.NODE_MODEL_ENV, 'fixture-node')
    assert runtime.model_for(runtime.NODE_TASK) == 'fixture-node'


def test_fixture_without_defaults_fails_startup_and_does_not_send_claude_ids(
    monkeypatch, capsys,
):
    import server

    _isolate(monkeypatch)
    fixture = FixtureProvider()
    runtime.register_provider('fixture', lambda: fixture)
    monkeypatch.setenv(runtime.PROVIDER_ENV, 'fixture')
    assert runtime.model_for(runtime.NODE_TASK) == ''
    assert runtime.model_for(runtime.MODERATION_TASK) == ''
    report = check_model_configuration()
    assert report.provider == 'fixture'
    assert [task.source for task in report.tasks] == ['default'] * 4
    assert all(task.model == '' for task in report.tasks)
    assert all(problem.kind == 'default' for problem in report.hard)
    line = report.failure_line()
    assert 'has no default model' in line
    assert 'provider fixture' in line
    assert runtime.NODE_MODEL_ENV in line
    assert runtime.MODERATION_MODEL_ENV in line
    assert 'claude' not in line
    assert '\n' not in line
    with pytest.raises(SystemExit) as caught:
        main(['models'])
    assert 'has no default model' in str(caught.value)
    printed = capsys.readouterr().out
    assert 'text provider: fixture' in printed
    assert 'source=default' in printed
    assert 'claude-opus-4-8' not in printed
    assert 'claude-haiku-4-5' not in printed
    monkeypatch.setattr(server.observability, 'setup', lambda: None)
    monkeypatch.setattr(server.guard, 'canonical_seed', lambda: None)

    def opened(*args, **kwargs):
        raise AssertionError('listener opened')

    monkeypatch.setattr(server, '_ThreadedServer', opened)
    with pytest.raises(SystemExit) as caught:
        server.run(host='127.0.0.1', port=0)
    assert 'has no default model' in str(caught.value)
    assert 'claude' not in str(caught.value)


def test_a_replaced_get_provider_also_supplies_the_default_ids(monkeypatch):
    # model_for and generate share one seam. A replaced get_provider (the
    # eval harness and tests use it) must not pair its calls with the cached
    # adapter's Claude ids.
    _isolate(monkeypatch)
    assert runtime.get_provider().name == 'anthropic'
    substitute = _OwnDefaults()
    monkeypatch.setattr(runtime, 'get_provider', lambda: substitute)
    assert runtime.model_for(runtime.NODE_TASK) == 'fixture-voice'
    assert runtime.model_for(runtime.MODERATION_TASK) == 'fixture-moderation'
    node = SpatialNode(name='Vault', level='Object', properties={'surface': 'smooth'})
    assert consciousness.speak(node, 'Now?') == 'A remembered voice.'
    assert [call['model'] for call in substitute.calls] == ['fixture-voice']

    bare = FixtureProvider()
    monkeypatch.setattr(runtime, 'get_provider', lambda: bare)
    assert runtime.model_for(runtime.NODE_TASK) == ''
    assert runtime.model_for(runtime.MODERATION_TASK) == ''


def test_selected_provider_is_cached_and_a_later_bad_value_does_not_exit(monkeypatch):
    _isolate(monkeypatch)
    built = []

    def factory():
        provider = FixtureProvider()
        built.append(provider)
        return provider

    runtime.register_provider('fixture', factory)
    monkeypatch.setenv(runtime.PROVIDER_ENV, 'openai')
    with pytest.raises(SystemExit):
        runtime.get_provider()
    monkeypatch.setenv(runtime.PROVIDER_ENV, 'fixture')
    selected = runtime.get_provider()
    assert selected is built[0]
    assert runtime.get_provider() is selected
    assert len(built) == 1
    monkeypatch.setenv(runtime.PROVIDER_ENV, '')
    errors = []

    def run():
        try:
            assert runtime.configured() is True
            runtime.generate(
                endpoint='speak', model='fixture-node', max_tokens=8,
                system=(SystemBlock('s'),),
                messages=[{'role': 'user', 'content': 'hi'}],
            )
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=run)
    thread.start()
    thread.join(2)
    assert not thread.is_alive()
    assert errors == []
    assert len(built) == 1
    assert built[0].calls and built[0].calls[0]['model'] == 'fixture-node'
    runtime.reset_provider_selection()
    with pytest.raises(SystemExit) as caught:
        runtime.get_provider()
    assert 'empty' in str(caught.value)


class _NeedsSdk:
    name = 'fixture'
    sdk_module = 'anthropic'
    distribution_extra = 'anthropic'

    def configured(self):
        return True

    def cache_reference_tokens(self, model):
        return None

    def generate(self, **kwargs):
        raise AssertionError('generate')


def test_missing_sdk_is_only_the_adapters_own_module(monkeypatch):
    real = importlib.import_module

    def missing_self(name, package=None):
        if name == 'anthropic':
            raise ModuleNotFoundError("No module named 'anthropic'", name='anthropic')
        return real(name, package)

    monkeypatch.setattr(importlib, 'import_module', missing_self)
    assert runtime.installation_error(_NeedsSdk()) == (
        "NESTED_WORLDS_PROVIDER=fixture requires the optional extra "
        "enfolded[anthropic] (package 'anthropic' is not installed)"
    )

    def missing_dependency(name, package=None):
        if name == 'anthropic':
            raise ModuleNotFoundError("No module named 'httpx'", name='httpx')
        return real(name, package)

    monkeypatch.setattr(importlib, 'import_module', missing_dependency)
    with pytest.raises(ModuleNotFoundError) as missing:
        runtime.installation_error(_NeedsSdk())
    assert missing.value.name == 'httpx'
    assert 'enfolded[anthropic]' not in str(missing.value)

    def circular(name, package=None):
        if name == 'anthropic':
            raise ImportError('circular import inside anthropic')
        return real(name, package)

    monkeypatch.setattr(importlib, 'import_module', circular)
    with pytest.raises(ImportError) as other:
        runtime.installation_error(_NeedsSdk())
    assert type(other.value) is ImportError
    assert str(other.value) == 'circular import inside anthropic'
    assert 'enfolded[anthropic]' not in str(other.value)


def _budget_spies(monkeypatch):
    from server import guard
    charged = []

    def model_action(user_key=None):
        charged.append(('model-action', user_key))
        return True

    def voice(user_key=None):
        charged.append(('anthropic', user_key))
        return True

    def moderation_budget(user_key=None):
        charged.append(('moderation', user_key))
        return 'ok'

    monkeypatch.setattr(guard, 'consume_model_action', model_action)
    monkeypatch.setattr(guard, 'consume_anthropic', voice)
    monkeypatch.setattr(guard, 'moderation_reserve', moderation_budget)
    return charged


def test_blank_model_is_refused_before_any_budget(monkeypatch):
    import consciousness
    from server import moderation

    _isolate(monkeypatch)
    fixture = FixtureProvider()
    runtime.register_provider('fixture', lambda: fixture)
    monkeypatch.setenv(runtime.PROVIDER_ENV, 'fixture')
    charged = _budget_spies(monkeypatch)
    kwargs = dict(
        endpoint='speak', model='', max_tokens=8,
        system=(SystemBlock('s'),),
        messages=[{'role': 'user', 'content': 'hi'}],
        user_key='ada', voice_budget=True,
    )
    for model in ('', '   ', None):
        with pytest.raises(runtime.UnusableModelId):
            runtime.generate(**{**kwargs, 'model': model})
    assert charged == []
    assert fixture.calls == []

    node = SpatialNode(name='Vault', level='Object', properties={})
    with pytest.raises(runtime.UnusableModelId):
        consciousness.speak(node, 'Now?', user_key='ada', voice_budget=True)
    with pytest.raises(runtime.UnusableModelId):
        consciousness.classify_content('a phrase that needs a look', user_key='ada')
    assert charged == []
    assert fixture.calls == []

    verdict = moderation.screen('go kill yourself', user_key='ada', surface='speak')
    assert verdict.allowed is False
    assert verdict.outcome == 'error'
    body = moderation.http_body(verdict)
    assert body['held'] is True
    assert body['ai'] is False
    assert charged == []
    assert fixture.calls == []


def test_concurrent_first_selection_builds_one_adapter(monkeypatch):
    _isolate(monkeypatch)
    built = []
    entered = threading.Event()
    release = threading.Event()

    def factory():
        provider = FixtureProvider()
        built.append(provider)
        entered.set()
        assert release.wait(2)
        return provider

    runtime.register_provider('fixture', factory)
    monkeypatch.setenv(runtime.PROVIDER_ENV, 'fixture')
    errors = []
    results = []

    def run():
        try:
            results.append(runtime.get_provider())
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=run) for _ in range(8)]
    for thread in threads:
        thread.start()
    assert entered.wait(2)
    deadline = time.monotonic() + 0.2
    while time.monotonic() < deadline:
        if len(built) != 1:
            break
        time.sleep(0.01)
    assert len(built) == 1
    release.set()
    for thread in threads:
        thread.join(2)
        assert not thread.is_alive()
    assert errors == []
    assert len(results) == 8
    assert all(item is built[0] for item in results)


def test_reentering_factory_does_not_deadlock(monkeypatch):
    _isolate(monkeypatch)

    def factory():
        runtime.get_provider()
        return FixtureProvider()

    runtime.register_provider('fixture', factory)
    monkeypatch.setenv(runtime.PROVIDER_ENV, 'fixture')
    box = []
    done = threading.Event()

    def run():
        try:
            runtime.get_provider()
        except BaseException as exc:
            box.append(exc)
        finally:
            done.set()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    assert done.wait(2)
    thread.join(1)
    assert not thread.is_alive()
    assert len(box) == 1
    assert isinstance(box[0], RuntimeError)
    assert 're-entered' in str(box[0])
    runtime.register_provider('fixture', lambda: FixtureProvider())
    selected = runtime.get_provider()
    assert selected.name == 'fixture'
    assert runtime.get_provider() is selected
