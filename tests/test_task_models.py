"""Per-task model ids fall back to the shared setting and never select a provider."""
from types import SimpleNamespace

import pytest

import consciousness
from consciousness import interventions, runtime
from multiverse.node import SpatialNode
from server import model_banner


READY = '{"status":"ready","ambiguity":"none","steps":[{"op":"engrave","amount":1}]}'
_TASK_ENVS = (
    runtime.NODE_MODEL_ENV, runtime.INHABITANT_MODEL_ENV,
    runtime.INTENT_MODEL_ENV, runtime.MODERATION_MODEL_ENV,
)


class _Provider:
    name = 'fixture'

    def __init__(self, result):
        self.calls = []
        self.result = result

    def configured(self):
        return True

    def cache_reference_tokens(self, model):
        return {'known-small': 1, 'known-large': 10**9}.get(model)

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _clear(monkeypatch):
    monkeypatch.delenv(runtime.SHARED_MODEL_ENV, raising=False)
    for name in _TASK_ENVS:
        monkeypatch.delenv(name, raising=False)


def test_defaults_match_the_existing_voice_and_moderation_ids(monkeypatch):
    _clear(monkeypatch)
    assert runtime.model_for(runtime.NODE_TASK) == 'claude-opus-4-8'
    assert runtime.model_for(runtime.INHABITANT_TASK) == runtime.DEFAULT_VOICE_MODEL
    assert runtime.model_for(runtime.INTENT_TASK) == runtime.DEFAULT_VOICE_MODEL
    assert runtime.model_for(runtime.MODERATION_TASK) == 'claude-haiku-4-5'
    assert runtime.model_for(runtime.MODERATION_TASK) == runtime.DEFAULT_MODERATION_MODEL


def test_unset_tasks_use_the_shared_model_and_moderation_does_not(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv(runtime.SHARED_MODEL_ENV, 'shared-model-id')
    assert runtime.model_for(runtime.NODE_TASK) == 'shared-model-id'
    assert runtime.model_for(runtime.INHABITANT_TASK) == 'shared-model-id'
    assert runtime.model_for(runtime.INTENT_TASK) == 'shared-model-id'
    assert runtime.model_for(runtime.MODERATION_TASK) == runtime.DEFAULT_MODERATION_MODEL


@pytest.mark.parametrize('task,env_name', [
    (runtime.NODE_TASK, runtime.NODE_MODEL_ENV),
    (runtime.INHABITANT_TASK, runtime.INHABITANT_MODEL_ENV),
    (runtime.INTENT_TASK, runtime.INTENT_MODEL_ENV),
])
def test_one_override_does_not_change_the_other_tasks(monkeypatch, task, env_name):
    _clear(monkeypatch)
    monkeypatch.setenv(runtime.SHARED_MODEL_ENV, 'shared-model-id')
    monkeypatch.setenv(env_name, 'only-this-task')
    resolved = {name: runtime.model_for(name) for name in (
        runtime.NODE_TASK, runtime.INHABITANT_TASK, runtime.INTENT_TASK)}
    assert resolved[task] == 'only-this-task'
    assert all(model == 'shared-model-id' for name, model in resolved.items() if name != task)
    assert runtime.model_for(runtime.MODERATION_TASK) == runtime.DEFAULT_MODERATION_MODEL


def test_moderation_override_does_not_change_voice_or_intention(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv(runtime.SHARED_MODEL_ENV, 'shared-model-id')
    monkeypatch.setenv(runtime.MODERATION_MODEL_ENV, 'classifier-id')
    assert runtime.model_for(runtime.MODERATION_TASK) == 'classifier-id'
    assert runtime.model_for(runtime.NODE_TASK) == 'shared-model-id'
    assert runtime.model_for(runtime.INHABITANT_TASK) == 'shared-model-id'
    assert runtime.model_for(runtime.INTENT_TASK) == 'shared-model-id'


@pytest.mark.parametrize('blank', ['', '   ', '\n\t'])
def test_blank_task_and_shared_values_are_unset(monkeypatch, blank):
    _clear(monkeypatch)
    monkeypatch.setenv(runtime.SHARED_MODEL_ENV, 'shared-model-id')
    monkeypatch.setenv(runtime.NODE_MODEL_ENV, blank)
    monkeypatch.setenv(runtime.MODERATION_MODEL_ENV, blank)
    assert runtime.model_for(runtime.NODE_TASK) == 'shared-model-id'
    assert runtime.model_for(runtime.MODERATION_TASK) == runtime.DEFAULT_MODERATION_MODEL
    monkeypatch.setenv(runtime.SHARED_MODEL_ENV, blank)
    monkeypatch.delenv(runtime.NODE_MODEL_ENV, raising=False)
    assert runtime.model_for(runtime.NODE_TASK) == runtime.DEFAULT_VOICE_MODEL
    assert runtime.model_for(runtime.INTENT_TASK) == runtime.DEFAULT_VOICE_MODEL


def test_override_stands_alone_when_the_shared_setting_is_absent(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv(runtime.INTENT_MODEL_ENV, 'intent-only')
    assert runtime.model_for(runtime.INTENT_TASK) == 'intent-only'
    assert runtime.model_for(runtime.NODE_TASK) == runtime.DEFAULT_VOICE_MODEL
    assert runtime.model_for(runtime.INHABITANT_TASK) == runtime.DEFAULT_VOICE_MODEL


def test_surrounding_whitespace_is_stripped_from_a_model_id(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv(runtime.SHARED_MODEL_ENV, '  shared-id  ')
    monkeypatch.setenv(runtime.NODE_MODEL_ENV, '\n node-id \t')
    assert runtime.model_for(runtime.NODE_TASK) == 'node-id'
    assert runtime.model_for(runtime.INHABITANT_TASK) == 'shared-id'


def test_unknown_task_is_rejected(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv(runtime.SHARED_MODEL_ENV, 'shared-model-id')
    with pytest.raises(ValueError, match='unknown model task'):
        runtime.model_for('intention')


def test_call_sites_send_only_their_resolved_model(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv(runtime.SHARED_MODEL_ENV, 'shared-model-id')
    monkeypatch.setenv(runtime.NODE_MODEL_ENV, 'node-id')
    monkeypatch.setenv(runtime.INHABITANT_MODEL_ENV, 'inhabitant-id')
    monkeypatch.setenv(runtime.INTENT_MODEL_ENV, 'intent-id')
    monkeypatch.setenv(runtime.MODERATION_MODEL_ENV, 'moderation-id')
    provider = _Provider(runtime.Completion('ALLOW', True))
    monkeypatch.setattr(runtime, 'get_provider', lambda: provider)
    node = SpatialNode(name='Vault', level='Object', properties={})
    assert consciousness.speak(node, 'Hello') == 'ALLOW'
    assert consciousness.voice_agent(
        SimpleNamespace(name='tender'), 'Tessera', node, 'Hello') == 'ALLOW'
    assert consciousness.classify_content('fixture input') is True
    provider.result = runtime.Completion(READY, True)
    assert interventions.propose('cut a pattern', {'level': 'Object'}) == [
        {'op': 'engrave', 'amount': 1}]
    assert [call['model'] for call in provider.calls] == [
        'node-id', 'inhabitant-id', 'moderation-id', 'intent-id']


def test_failed_call_is_not_retried_on_another_model(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv(runtime.NODE_MODEL_ENV, 'node-only')
    monkeypatch.setenv(runtime.SHARED_MODEL_ENV, 'shared-backup')
    provider = _Provider(RuntimeError('upstream'))
    monkeypatch.setattr(runtime, 'get_provider', lambda: provider)
    node = SpatialNode(name='Vault', level='Room', properties={})
    with pytest.raises(RuntimeError, match='upstream'):
        consciousness.speak(node, 'Hello')
    assert [call['model'] for call in provider.calls] == ['node-only']


def test_model_id_does_not_switch_provider(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv(runtime.NODE_MODEL_ENV, 'gpt-4o')
    monkeypatch.setenv(runtime.INHABITANT_MODEL_ENV, 'grok-2')
    monkeypatch.setenv(runtime.INTENT_MODEL_ENV, 'gemini-2.5-pro')
    assert runtime.model_for(runtime.NODE_TASK) == 'gpt-4o'
    assert runtime.get_provider().name == 'anthropic'
    assert runtime.get_provider() is runtime.get_provider()


def test_configured_models_and_banner_report_ids_without_secrets(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'sk-test-secret')
    monkeypatch.setenv('ANTHROPIC_AUTH_TOKEN', 'bearer-test-secret')
    monkeypatch.setenv(runtime.SHARED_MODEL_ENV, 'shared-id')
    monkeypatch.setenv(runtime.NODE_MODEL_ENV, 'node-id')
    reported = runtime.configured_models()
    assert reported == {
        runtime.NODE_TASK: 'node-id',
        runtime.INHABITANT_TASK: 'shared-id',
        runtime.INTENT_TASK: 'shared-id',
        runtime.MODERATION_TASK: runtime.DEFAULT_MODERATION_MODEL,
    }
    text = '\n'.join(model_banner())
    assert 'node-id' in text and 'shared-id' in text
    assert runtime.DEFAULT_MODERATION_MODEL in text
    assert 'sk-test-secret' not in text and 'bearer-test-secret' not in text
    assert 'ANTHROPIC' not in text


def test_split_voice_models_warn_separately(monkeypatch, caplog):
    _clear(monkeypatch)
    monkeypatch.setenv(runtime.NODE_MODEL_ENV, 'known-large')
    monkeypatch.setenv(runtime.INHABITANT_MODEL_ENV, 'known-small')
    monkeypatch.setattr(runtime, 'get_provider', lambda: _Provider(runtime.Completion('x', True)))
    monkeypatch.setattr(consciousness, '_cache_warned', False)
    with caplog.at_level('WARNING', logger='nested_worlds.consciousness'):
        assert consciousness.cached_prefix_meets_minimum() is False
        consciousness.warn_if_cache_ineffective()
        consciousness.warn_if_cache_ineffective()
    assert len(caplog.records) == 1
    assert 'known-large' in caplog.text and 'node voice' in caplog.text
    assert 'known-small' not in caplog.text
