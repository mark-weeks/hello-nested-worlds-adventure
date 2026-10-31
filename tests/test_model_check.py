"""Startup model-id check is provider-neutral and never logs a credential."""
from pathlib import Path
import logging

import pytest

from consciousness import runtime
from consciousness.anthropic_provider import AnthropicProvider, DEFAULT_VOICE_MODEL
from consciousness.model_check import (
    check_model_configuration, enforce_model_configuration, format_report,
    probe_distinct_models,
)
from consciousness.runtime import Completion, SystemBlock
from main import main
from server import model_banner


_TASK_ENVS = (
    runtime.NODE_MODEL_ENV, runtime.INHABITANT_MODEL_ENV,
    runtime.INTENT_MODEL_ENV, runtime.MODERATION_MODEL_ENV, runtime.SHARED_MODEL_ENV,
)
_SECRET = 'sk-ant-test-secret-value'
_BEARER = 'bearer-token-secret-value'
_FAL = 'fal-key-secret-value'


def _clear(monkeypatch):
    monkeypatch.delenv(runtime.PROVIDER_ENV, raising=False)
    for name in _TASK_ENVS:
        monkeypatch.delenv(name, raising=False)
    # A leftover gateway host would turn a foreign id into a warning.
    monkeypatch.delenv('ANTHROPIC_BASE_URL', raising=False)


def _status(report, task):
    return next(item for item in report.tasks if item.task == task)


class LabProvider:
    """Non-Anthropic adapter. Its id rules are not Claude's."""

    name = 'lab'

    def __init__(self, result=None):
        self.calls = []
        self.result = result
        self.raise_on = None

    def model_id_validator(self):
        def verdict(model: str) -> str:
            if model == 'lab-known':
                return 'ok'
            if isinstance(model, str) and model.startswith('lab-'):
                return 'warn'
            return 'reject'
        return verdict

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        if self.raise_on is not None:
            raise self.raise_on
        if isinstance(self.result, Exception):
            raise self.result
        return self.result or Completion('ok', True)


class SilentProvider:
    """No id opinion. Structural problems still apply."""

    name = 'silent'


def test_defaults_are_served_and_name_their_source(monkeypatch):
    _clear(monkeypatch)
    report = check_model_configuration()
    assert report.provider == 'anthropic'
    assert report.hard == ()
    assert report.problems('soft') == ()
    node = _status(report, 'node')
    moderation = _status(report, 'moderation')
    assert node.model == 'claude-opus-4-8'
    assert node.source == 'default'
    assert node.env_var == runtime.NODE_MODEL_ENV
    assert node.provider == 'anthropic'
    assert moderation.model == 'claude-haiku-4-5'
    assert moderation.source == 'default'
    text = format_report(report)
    assert 'provider=anthropic' in text
    assert 'source=default' in text
    assert 'model=claude-opus-4-8' in text
    assert 'model=claude-haiku-4-5' in text


def test_task_env_shared_and_default_are_reported(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv(runtime.SHARED_MODEL_ENV, 'claude-sonnet-4-6')
    monkeypatch.setenv(runtime.NODE_MODEL_ENV, 'claude-opus-4-8')
    monkeypatch.setenv(runtime.MODERATION_MODEL_ENV, 'claude-haiku-4-5-20251001')
    report = check_model_configuration()
    assert report.hard == ()
    assert _status(report, 'node').source == 'task env'
    assert _status(report, 'node').env_var == runtime.NODE_MODEL_ENV
    assert _status(report, 'inhabitant').source == 'NESTED_WORLDS_MODEL'
    assert _status(report, 'inhabitant').model == 'claude-sonnet-4-6'
    assert _status(report, 'intent').source == 'NESTED_WORLDS_MODEL'
    assert _status(report, 'moderation').source == 'task env'
    assert _status(report, 'moderation').model == 'claude-haiku-4-5-20251001'


@pytest.mark.parametrize('model', ['gpt-4o', 'grok-2', 'gemini-2.5-pro'])
def test_anthropic_adapter_rejects_ids_it_does_not_serve(monkeypatch, model):
    _clear(monkeypatch)
    monkeypatch.setenv(runtime.INTENT_MODEL_ENV, model)
    report = check_model_configuration()
    problem = _status(report, 'intent').problems[0]
    assert problem.severity == 'hard'
    assert problem.kind == 'rejected'
    assert problem.env_var == runtime.INTENT_MODEL_ENV
    line = report.failure_line()
    assert '\n' not in line
    assert runtime.INTENT_MODEL_ENV in line
    assert model in line
    assert 'anthropic' in line
    assert _status(report, 'node').problems == ()


@pytest.mark.parametrize('model', [
    'anthropic/claude-opus-4-8',
    'us.anthropic.claude-sonnet-4-5-v1:0',
    'Claude-Opus-4-8',
    'claude-opus-4-8:beta',
    'claudeopus',
    'claude-opus-4-8;drop',
])
def test_plausible_claude_forms_warn_without_a_base_url(monkeypatch, model):
    _clear(monkeypatch)
    monkeypatch.setenv(runtime.INTENT_MODEL_ENV, model)
    report = check_model_configuration()
    assert report.hard == ()
    problem = _status(report, 'intent').problems[0]
    assert problem.severity == 'soft'
    assert problem.kind == 'unknown'
    assert model in problem.text
    assert _status(report, 'node').problems == ()


def test_base_url_override_warns_for_a_gateway_alias(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv('ANTHROPIC_BASE_URL', 'https://gateway.example/v1')
    monkeypatch.setenv(runtime.INTENT_MODEL_ENV, 'my-gateway-alias')
    report = check_model_configuration()
    assert report.hard == ()
    problem = _status(report, 'intent').problems[0]
    assert problem.severity == 'soft'
    assert problem.kind == 'unknown'
    rendered = format_report(report) + report.warning_line()
    assert 'gateway.example' not in rendered
    assert 'https://' not in rendered


def test_foreign_id_behind_a_base_url_warns(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv('ANTHROPIC_BASE_URL', 'https://gateway.example/v1')
    monkeypatch.setenv(runtime.INTENT_MODEL_ENV, 'gpt-4o')
    report = enforce_model_configuration()
    assert report.hard == ()
    problem = _status(report, 'intent').problems[0]
    assert problem.severity == 'soft'
    assert problem.kind == 'unknown'
    assert 'gpt-4o' in problem.text


def test_gateway_alias_without_a_base_url_is_rejected(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv(runtime.INTENT_MODEL_ENV, 'my-gateway-alias')
    with pytest.raises(SystemExit) as caught:
        enforce_model_configuration()
    message = str(caught.value)
    assert 'my-gateway-alias' in message
    assert 'not served' in message
    assert runtime.INTENT_MODEL_ENV in message


@pytest.mark.parametrize('base_url', ['', '   '])
def test_blank_base_url_is_not_an_override(monkeypatch, base_url):
    _clear(monkeypatch)
    monkeypatch.setenv('ANTHROPIC_BASE_URL', base_url)
    monkeypatch.setenv(runtime.INTENT_MODEL_ENV, 'gpt-4o')
    with pytest.raises(SystemExit) as caught:
        enforce_model_configuration()
    assert 'gpt-4o' in str(caught.value)
    assert 'not served' in str(caught.value)


def test_unknown_claude_id_warns_and_does_not_fail(monkeypatch, caplog):
    _clear(monkeypatch)
    monkeypatch.setenv(runtime.SHARED_MODEL_ENV, 'claude-opus-4-9')
    monkeypatch.setenv('ANTHROPIC_API_KEY', _SECRET)
    with caplog.at_level(logging.WARNING, logger='nested_worlds.consciousness'):
        report = enforce_model_configuration()
    assert report.hard == ()
    assert {item.task for item in report.tasks if item.problems} == {
        'node', 'inhabitant', 'intent'}
    warnings = [record for record in caplog.records if record.levelno >= logging.WARNING]
    assert len(warnings) == 1
    assert 'claude-opus-4-9' in warnings[0].message
    assert runtime.SHARED_MODEL_ENV in warnings[0].message
    assert 'task' in warnings[0].message
    assert _SECRET not in warnings[0].message
    assert _SECRET not in format_report(report)


def test_dated_unknown_snapshot_warns_once(monkeypatch, caplog):
    _clear(monkeypatch)
    monkeypatch.setenv(runtime.NODE_MODEL_ENV, 'claude-opus-4-9-20260101')
    with caplog.at_level(logging.WARNING, logger='nested_worlds.consciousness'):
        report = enforce_model_configuration()
    assert report.hard == ()
    assert _status(report, 'node').problems[0].severity == 'soft'
    assert len(caplog.records) == 1


@pytest.mark.parametrize('blank,kind', [('', 'empty'), ('   ', 'whitespace'), ('\n\t', 'whitespace')])
def test_blank_setting_fails_startup_and_model_for_still_falls_back(monkeypatch, blank, kind):
    _clear(monkeypatch)
    monkeypatch.setenv(runtime.NODE_MODEL_ENV, blank)
    assert runtime.model_for(runtime.NODE_TASK) == DEFAULT_VOICE_MODEL
    with pytest.raises(SystemExit) as caught:
        enforce_model_configuration()
    message = str(caught.value)
    assert '\n' not in message
    assert runtime.NODE_MODEL_ENV in message
    assert kind == 'empty' or 'whitespace' in message
    if kind == 'empty':
        assert 'is empty' in message
    else:
        assert 'is whitespace' in message


def test_blank_shared_setting_fails_even_when_every_task_overrides(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv(runtime.SHARED_MODEL_ENV, '')
    for name in (runtime.NODE_MODEL_ENV, runtime.INHABITANT_MODEL_ENV, runtime.INTENT_MODEL_ENV):
        monkeypatch.setenv(name, 'claude-opus-4-8')
    assert runtime.model_for(runtime.NODE_TASK) == 'claude-opus-4-8'
    with pytest.raises(SystemExit) as caught:
        enforce_model_configuration()
    message = str(caught.value)
    assert 'NESTED_WORLDS_MODEL is empty' in message
    assert 'tasks node, inhabitant, intent' in message


def test_shared_blank_is_one_line_for_every_voice_task(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv(runtime.SHARED_MODEL_ENV, '')
    with pytest.raises(SystemExit) as caught:
        enforce_model_configuration()
    message = str(caught.value)
    assert message.count(runtime.SHARED_MODEL_ENV) == 1
    assert 'tasks node, inhabitant, intent' in message
    assert 'moderation' not in message


def test_surrounding_whitespace_is_a_warning_and_the_id_is_stripped(monkeypatch, caplog):
    _clear(monkeypatch)
    monkeypatch.setenv(runtime.SHARED_MODEL_ENV, '  claude-opus-4-8  ')
    with caplog.at_level(logging.WARNING, logger='nested_worlds.consciousness'):
        report = enforce_model_configuration()
    assert report.hard == ()
    assert _status(report, 'node').model == 'claude-opus-4-8'
    assert _status(report, 'node').source == 'NESTED_WORLDS_MODEL'
    assert _status(report, 'node').problems[0].kind == 'whitespace'
    assert len(caplog.records) == 1
    assert 'surrounding whitespace' in caplog.records[0].message


def test_internal_whitespace_and_malformed_ids_fail(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv(runtime.INTENT_MODEL_ENV, 'claude opus')
    with pytest.raises(SystemExit) as spacing:
        enforce_model_configuration()
    assert 'contains whitespace' in str(spacing.value)
    assert 'claude opus' not in str(spacing.value)
    monkeypatch.setenv(runtime.INTENT_MODEL_ENV, 'claude\x01opus')
    with pytest.raises(SystemExit) as control:
        enforce_model_configuration()
    assert 'not a usable model id' in str(control.value)
    assert '\x01' not in str(control.value)


def test_lab_adapter_uses_its_own_rules_without_a_check_change(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv(runtime.NODE_MODEL_ENV, 'claude-opus-4-8')
    monkeypatch.setenv(runtime.INHABITANT_MODEL_ENV, 'lab-known')
    monkeypatch.setenv(runtime.INTENT_MODEL_ENV, 'lab-fresh')
    monkeypatch.setenv(runtime.MODERATION_MODEL_ENV, 'nope-1')
    lab = LabProvider()
    report = check_model_configuration(lab)
    assert report.provider == 'lab'
    assert lab.calls == []
    anthropic = AnthropicProvider().model_id_validator()
    assert anthropic('claude-opus-4-8') == 'ok'
    assert anthropic('lab-known') == 'reject'
    assert _status(report, 'node').problems[0].kind == 'rejected'
    assert _status(report, 'inhabitant').problems == ()
    assert _status(report, 'inhabitant').source == 'task env'
    assert _status(report, 'intent').problems[0].severity == 'soft'
    assert _status(report, 'intent').problems[0].kind == 'unknown'
    assert _status(report, 'moderation').problems[0].kind == 'rejected'
    text = format_report(report) + report.failure_line()
    assert 'provider=lab' in text
    assert 'is not served by provider lab' in text


class OpenProvider:
    """Accepts every structurally usable id, including another vendor's tokens."""

    name = 'open'

    def model_id_validator(self):
        return lambda model: 'ok'


@pytest.mark.parametrize('model', [
    'gemini-1.5-pro@002',
    '@cf/meta/llama-3-8b-instruct',
    'org/model+variant~1',
])
def test_shared_check_leaves_token_characters_to_the_adapter(monkeypatch, model):
    _clear(monkeypatch)
    for name in (
        runtime.NODE_MODEL_ENV, runtime.INHABITANT_MODEL_ENV,
        runtime.INTENT_MODEL_ENV, runtime.MODERATION_MODEL_ENV,
    ):
        monkeypatch.setenv(name, model)
    report = check_model_configuration(OpenProvider())
    assert report.provider == 'open'
    assert report.hard == ()
    assert report.problems('soft') == ()
    assert _status(report, 'node').model == model
    assert _status(report, 'moderation').model == model


def test_shared_check_still_rejects_length_and_controls(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv(runtime.NODE_MODEL_ENV, 'a' * 257)
    report = check_model_configuration(OpenProvider())
    problem = _status(report, 'node').problems[0]
    assert problem.severity == 'hard'
    assert problem.kind == 'malformed'
    monkeypatch.setenv(runtime.NODE_MODEL_ENV, 'ok\x01id')
    report = check_model_configuration(OpenProvider())
    problem = _status(report, 'node').problems[0]
    assert problem.severity == 'hard'
    assert problem.kind == 'malformed'
    assert '\x01' not in problem.text


def test_moderation_model_is_checked_when_moderation_is_disabled(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv('NESTED_WORLDS_DISABLE_MODERATION', '1')
    monkeypatch.setenv(runtime.MODERATION_MODEL_ENV, 'gpt-4o')
    with pytest.raises(SystemExit) as caught:
        enforce_model_configuration()
    message = str(caught.value)
    assert runtime.MODERATION_MODEL_ENV in message
    assert 'gpt-4o' in message
    assert 'moderation' in message


def test_adapter_without_a_validator_only_checks_shape(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv(runtime.NODE_MODEL_ENV, 'gpt-4o')
    monkeypatch.setenv(runtime.INHABITANT_MODEL_ENV, 'lab-known')
    report = check_model_configuration(SilentProvider())
    assert _status(report, 'node').problems == ()
    assert _status(report, 'inhabitant').problems == ()
    assert report.provider == 'silent'
    monkeypatch.setenv(runtime.NODE_MODEL_ENV, '')
    report = check_model_configuration(SilentProvider())
    assert _status(report, 'node').problems[0].kind == 'empty'


def test_a_raising_validator_warns_without_its_message(monkeypatch, caplog):
    _clear(monkeypatch)
    monkeypatch.setenv(runtime.NODE_MODEL_ENV, 'lab-known')
    monkeypatch.setenv(runtime.INHABITANT_MODEL_ENV, 'lab-known')
    monkeypatch.setenv(runtime.INTENT_MODEL_ENV, 'lab-known')
    monkeypatch.setenv(runtime.MODERATION_MODEL_ENV, 'lab-known')

    class Raising:
        name = 'lab'

        def model_id_validator(self):
            def verdict(model):
                raise RuntimeError(f'body {_SECRET} {model}')
            return verdict

    with caplog.at_level(logging.WARNING, logger='nested_worlds.consciousness'):
        report = enforce_model_configuration(Raising())
    assert report.hard == ()
    assert len(caplog.records) == 1
    assert 'RuntimeError' in caplog.records[0].message
    assert 'could not be judged' in caplog.records[0].message
    assert 'lab-known' not in caplog.records[0].message
    assert _SECRET not in caplog.records[0].message
    assert _SECRET not in format_report(report)


def test_nothing_logs_or_prints_a_key(monkeypatch, caplog, capsys):
    _clear(monkeypatch)
    monkeypatch.setenv('ANTHROPIC_API_KEY', _SECRET)
    monkeypatch.setenv('ANTHROPIC_AUTH_TOKEN', _BEARER)
    monkeypatch.setenv('FAL_KEY', _FAL)
    monkeypatch.setenv(runtime.NODE_MODEL_ENV, _SECRET)
    monkeypatch.setenv(runtime.INTENT_MODEL_ENV, 'gpt-4o')
    with caplog.at_level(logging.DEBUG, logger='nested_worlds.consciousness'):
        with pytest.raises(SystemExit) as caught:
            enforce_model_configuration()
    message = str(caught.value)
    rendered = message + caplog.text + format_report(check_model_configuration())
    rendered += '\n'.join(model_banner())
    for secret in (_SECRET, _BEARER, _FAL):
        assert secret not in rendered
    assert 'gpt-4o' in message
    assert runtime.NODE_MODEL_ENV in message
    assert runtime.INTENT_MODEL_ENV in message
    assert 'ANTHROPIC_API_KEY' not in rendered
    out = capsys.readouterr().out
    assert _SECRET not in out


def test_check_does_not_call_the_provider(monkeypatch):
    _clear(monkeypatch)

    def boom(self, **kwargs):
        raise AssertionError('live call')

    monkeypatch.setattr(AnthropicProvider, 'generate', boom)
    report = check_model_configuration()
    assert report.hard == ()
    enforce_model_configuration()


def test_server_run_refuses_before_the_listener_and_does_not_probe(monkeypatch):
    import server
    from consciousness import model_check

    _clear(monkeypatch)
    monkeypatch.setenv(runtime.SHARED_MODEL_ENV, 'gpt-4o')
    monkeypatch.setenv('ANTHROPIC_API_KEY', _SECRET)
    probes = []
    monkeypatch.setattr(model_check, 'probe_distinct_models',
                        lambda *args, **kwargs: probes.append(args) or ())
    monkeypatch.setattr(server.observability, 'setup', lambda: None)
    monkeypatch.setattr(server.guard, 'canonical_seed', lambda: None)

    def opened(*args, **kwargs):
        raise AssertionError('listener opened')

    monkeypatch.setattr(server, '_ThreadedServer', opened)
    with pytest.raises(SystemExit) as caught:
        server.run(host='127.0.0.1', port=0)
    message = str(caught.value)
    assert '\n' not in message
    assert runtime.SHARED_MODEL_ENV in message
    assert 'gpt-4o' in message
    assert 'tasks node, inhabitant, intent' in message
    assert _SECRET not in message
    assert probes == []


def test_probe_calls_each_distinct_id_once_and_not_the_budget(monkeypatch):
    import server.guard as guard

    _clear(monkeypatch)
    monkeypatch.setenv(runtime.NODE_MODEL_ENV, 'lab-known')
    monkeypatch.setenv(runtime.INHABITANT_MODEL_ENV, 'lab-known')
    monkeypatch.setenv(runtime.INTENT_MODEL_ENV, 'lab-fresh')
    monkeypatch.setenv(runtime.MODERATION_MODEL_ENV, 'lab-known')
    lab = LabProvider()

    def reject_budget(*args, **kwargs):
        raise AssertionError('budget charged')

    monkeypatch.setattr(guard, 'consume_anthropic', reject_budget)
    monkeypatch.setattr(guard, 'consume_model_action', reject_budget)
    report = check_model_configuration(lab)
    assert lab.calls == []
    assert report.hard == ()

    def generate(**kwargs):
        lab.calls.append(kwargs)
        if kwargs['model'] == 'lab-fresh':
            raise RuntimeError(f'upstream {_SECRET}')
        return Completion('ok', True)

    lab.generate = generate
    results = probe_distinct_models(report, lab)
    assert [item.model for item in results] == ['lab-known', 'lab-fresh']
    assert [item.accepted for item in results] == [True, False]
    assert results[1].detail == 'RuntimeError'
    assert len(lab.calls) == 2
    call = next(item for item in lab.calls if item['model'] == 'lab-known')
    assert call['max_tokens'] == 1
    assert call['timeout'] == 30.0
    assert call['messages'] == [{'role': 'user', 'content': 'ok'}]
    assert isinstance(call['system'][0], SystemBlock)
    assert 'json_schema' not in call
    rendered = '\n'.join(item.line() for item in results)
    assert _SECRET not in rendered
    assert 'upstream' not in rendered
    assert 'refused (RuntimeError)' in rendered


def test_models_command_prints_the_report_and_probes_only_with_the_flag(monkeypatch, capsys):
    _clear(monkeypatch)
    lab = LabProvider()
    monkeypatch.setattr(runtime, 'get_provider', lambda: lab)
    monkeypatch.setenv(runtime.NODE_MODEL_ENV, 'lab-known')
    monkeypatch.setenv(runtime.INHABITANT_MODEL_ENV, 'lab-known')
    monkeypatch.setenv(runtime.INTENT_MODEL_ENV, 'lab-fresh')
    monkeypatch.setenv(runtime.MODERATION_MODEL_ENV, 'lab-known')
    main(['models'])
    out = capsys.readouterr().out
    assert 'text provider: lab' in out
    assert 'source=task env' in out
    assert 'model=lab-known' in out
    assert 'model=lab-fresh' in out
    assert 'soft:' in out
    assert lab.calls == []
    main(['models', '--probe'])
    probed = capsys.readouterr().out
    assert 'probe lab-known: accepted' in probed
    assert 'probe lab-fresh: accepted' in probed
    assert len(lab.calls) == 2
    monkeypatch.setenv(runtime.MODERATION_MODEL_ENV, 'nope-1')
    before = len(lab.calls)
    with pytest.raises(SystemExit) as caught:
        main(['models', '--probe'])
    assert runtime.MODERATION_MODEL_ENV in str(caught.value)
    assert len(lab.calls) == before


@pytest.mark.parametrize('ready', [False, 'raise'])
def test_probe_skips_when_the_provider_is_not_configured(monkeypatch, capsys, ready):
    _clear(monkeypatch)
    calls = []

    class Unconfigured:
        name = 'lab'

        def configured(self):
            if ready == 'raise':
                raise RuntimeError('credential store unavailable')
            return False

        def default_model(self, task):
            return 'lab-voice'

        def generate(self, **kwargs):
            calls.append(kwargs)
            raise TypeError('missing key')

    monkeypatch.setattr(runtime, 'get_provider', lambda: Unconfigured())
    with pytest.raises(SystemExit) as caught:
        main(['models', '--probe'])
    assert caught.value.code == 1
    out = capsys.readouterr().out
    assert 'skipped: provider not configured' in out
    assert 'TypeError' not in out
    assert 'refused' not in out
    assert calls == []


def test_check_source_names_no_provider_and_ci_does_not_probe():
    text = (Path(__file__).resolve().parents[1] / 'consciousness/model_check.py').read_text().lower()
    for needle in ('claude', 'anthropic', 'openai', 'gpt-', 'gemini', 'grok', 'xai'):
        assert needle not in text
    root = Path(__file__).resolve().parents[1]
    assert '--probe' not in (root / 'scripts/check.sh').read_text()
    for path in (root / '.github').rglob('*.yml'):
        body = path.read_text()
        assert '--probe' not in body
        assert 'models --probe' not in body
