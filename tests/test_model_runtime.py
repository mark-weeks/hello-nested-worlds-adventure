"""Provider replacement mechanics without paid calls or another vendor's SDK."""
from types import SimpleNamespace

import pytest

import consciousness
from consciousness import interventions, runtime
from consciousness.anthropic_provider import AnthropicProvider
from consciousness.runtime import Completion, SystemBlock, TokenUsage
from multiverse.node import SpatialNode
from server import guard, intervention_api


READY = '{"status":"ready","ambiguity":"none","steps":[{"op":"engrave","amount":1}]}'


class FixtureProvider:
    name = 'fixture'

    def __init__(self):
        self.calls = []
        self.available = True
        self.result = Completion('A remembered voice.', True, TokenUsage(10, 3, 4, 0))

    def configured(self):
        return self.available

    def cache_reference_tokens(self, model):
        return None

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


@pytest.fixture
def alternate(monkeypatch):
    provider = FixtureProvider()
    monkeypatch.setattr(runtime, 'get_provider', lambda: provider)
    monkeypatch.setattr(runtime, 'VOICE_MODEL', 'fixture-voice-v1')
    monkeypatch.setenv('NESTED_WORLDS_MODERATION_MODEL', 'fixture-classifier-v2')
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    return provider


def test_all_four_tasks_use_provider_boundary(alternate, caplog):
    node = SpatialNode(name='Vault', level='Object', properties={'surface': 'smooth'})
    with caplog.at_level('INFO', logger='nested_worlds.consciousness'):
        assert consciousness.speak(node, 'Now?', transcript=[{'user': 'Before?', 'assistant': 'Before.'}]) == 'A remembered voice.'
        assert consciousness.voice_agent(SimpleNamespace(name='tender'), 'Tessera', node, 'Hello') == 'A remembered voice.'
        alternate.result = Completion('BLOCK', True)
        assert consciousness.classify_content('fixture input') is False
        alternate.result = Completion(READY, True)
        assert interventions.propose('cut a pattern', {'level': 'Object'}) == [{'op': 'engrave', 'amount': 1}]
    voice, agent, moderation, intention = alternate.calls
    assert voice['model'] == agent['model'] == intention['model'] == 'fixture-voice-v1'
    assert moderation['model'] == 'fixture-classifier-v2'
    assert voice['messages'] == [
        {'role': 'user', 'content': 'Before?'}, {'role': 'assistant', 'content': 'Before.'},
        {'role': 'user', 'content': 'Now?'},
    ]
    assert voice['system'][0].cacheable and agent['system'][0].cacheable
    assert not moderation['system'][0].cacheable
    assert moderation['timeout'] == 3.0
    assert intention['json_schema']['additionalProperties'] is False
    assert 'engrave' in intention['json_schema']['properties']['steps']['items']['properties']['op']['enum']
    assert 'provider=fixture model=fixture-voice-v1 endpoint=speak' in caplog.text
    assert 'Before?' not in caplog.text


@pytest.mark.parametrize('text,complete', [(READY, False), ('not json', True), (None, True),
    ('{"status":"ready","ambiguity":"none","steps":[{"op":"invent_canon","amount":1}]}', True)])
def test_alternate_cannot_bypass_intention_validation(alternate, text, complete):
    alternate.result = Completion(text, complete)
    with pytest.raises(ValueError):
        interventions.propose('change it', {'level': 'Object'})


def test_intention_credential_check_belongs_to_selected_adapter(alternate, monkeypatch):
    monkeypatch.delenv('NESTED_WORLDS_DISABLE_AI', raising=False)
    charged = []
    monkeypatch.setattr(guard, 'consume_anthropic', lambda **kwargs: charged.append(kwargs) or True)
    node = SpatialNode(name='Vault', level='Object', properties={})
    alternate.result = Completion(READY, True)
    steps, quiet = intervention_api._propose('engrave', 'visitor', node.name, node, {})
    assert steps == [{'op': 'engrave', 'amount': 1}] and quiet is None
    assert charged == [{'user_key': 'visitor'}]
    alternate.available = False
    steps, quiet = intervention_api._propose('engrave', 'visitor', node.name, node, {})
    assert steps is None and quiet['ai'] is False and quiet['steps'] == []
    assert len(alternate.calls) == len(charged) == 1


def test_adapter_failure_keeps_authored_intention_fallback(alternate, monkeypatch):
    monkeypatch.delenv('NESTED_WORLDS_DISABLE_AI', raising=False)
    monkeypatch.setattr(guard, 'consume_anthropic', lambda **kwargs: True)
    def unavailable(**kwargs):
        raise RuntimeError('private upstream detail')
    monkeypatch.setattr(alternate, 'generate', unavailable)
    node = SpatialNode(name='Vault', level='Object', properties={})
    steps, quiet = intervention_api._propose('engrave', None, node.name, node, {})
    assert steps is None and quiet['ai'] is False and quiet['steps'] == []
    assert quiet['response'] == intervention_api._UNSETTLED


def test_unknown_cache_metadata_warns_without_assuming_incumbent(alternate, monkeypatch, caplog):
    monkeypatch.setattr(consciousness, '_cache_warned', False)
    with caplog.at_level('WARNING', logger='nested_worlds.consciousness'):
        assert not consciousness.cached_prefix_meets_minimum()
        consciousness.warn_if_cache_ineffective()
        consciousness.warn_if_cache_ineffective()
    assert len(caplog.records) == 1
    assert 'UNKNOWN' in caplog.text and 'provider=fixture' in caplog.text
    estimate = min(consciousness._estimate_tokens(consciousness._WORLD_BIBLE),
                   consciousness._estimate_tokens(consciousness._AGENT_BIBLE))
    assert f'smaller cached prefix ~{estimate} tokens' in caplog.text
    assert consciousness.cached_prefix_meets_minimum(1)


@pytest.mark.parametrize('stop,complete,reason', [('end_turn', True, 'complete'),
    ('max_tokens', False, 'length'), ('refusal', False, 'refusal'), ('tool_use', False, 'tool'),
    ('stop_sequence', False, 'stop'), ('pause_turn', False, 'pause'), (None, False, 'unknown')])
def test_anthropic_normalizes_request_completion_and_usage(stop, complete, reason):
    adapter = AnthropicProvider()
    calls = []
    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(content=[SimpleNamespace(type='thinking'), SimpleNamespace(type='text', text='answer')],
            stop_reason=stop, usage=SimpleNamespace(input_tokens=10, output_tokens=4,
                                                   cache_read_input_tokens=7, cache_creation_input_tokens=2))
    adapter._client = SimpleNamespace(messages=SimpleNamespace(create=create))
    schema = {'type': 'object'}
    result = adapter.generate(model='fixture-model', system=(SystemBlock('bible', True), SystemBlock('state')),
        messages=[{'role': 'user', 'content': 'hello'}], max_tokens=500, json_schema=schema, timeout=3.0)
    assert result == Completion('answer', complete, TokenUsage(10, 4, 7, 2), reason)
    assert calls == [dict(model='fixture-model', max_tokens=500, timeout=3.0,
        system=[{'type': 'text', 'text': 'bible', 'cache_control': {'type': 'ephemeral', 'ttl': '1h'}},
                {'type': 'text', 'text': 'state'}],
        messages=[{'role': 'user', 'content': 'hello'}],
        output_config={'format': {'type': 'json_schema', 'schema': schema}})]


def test_anthropic_keeps_missing_text_and_usage_unknown():
    adapter = AnthropicProvider()
    calls = []
    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(content=[], stop_reason='refusal')
    adapter._client = SimpleNamespace(messages=SimpleNamespace(create=create))
    result = adapter.generate(model='other-model', system=(SystemBlock('classify'),), messages=[], max_tokens=8)
    assert result == Completion(None, False, None, 'refusal')
    assert calls == [dict(model='other-model', system='classify', messages=[], max_tokens=8)]
    assert adapter.cache_reference_tokens('other-model') is None


@pytest.mark.parametrize('raw,limit', [('', 8), ('bad', 8), ('0', 1), ('-5', 1), ('2', 2)])
def test_existing_concurrency_setting_is_preserved(monkeypatch, raw, limit):
    monkeypatch.setenv('NESTED_WORLDS_ANTHROPIC_CONCURRENCY', raw)
    assert runtime._concurrency_limit() == limit


@pytest.mark.parametrize('model,minimum', [
    ('claude-opus-4-5', 4096), ('claude-opus-4-6', 4096),
    ('claude-opus-4-7', 2048), ('claude-opus-4-8', 1024),
    ('claude-sonnet-4-5-20250929', 1024), ('claude-sonnet-4-6', 1024),
    ('claude-haiku-4-5-20251001', 4096), ('claude-opus-99-1', None),
    ('claude-opus-4-8-latest', None), ('fixture-model', None),
])
def test_cache_metadata_is_version_specific(model, minimum):
    assert AnthropicProvider().cache_reference_tokens(model) == minimum


@pytest.mark.parametrize('auth_env', [None, 'ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN'])
@pytest.mark.parametrize('endpoint,event_type', [('/speak', 'PLAYER_SPEAK'), ('/agent/voice', 'AGENT_VOICE')])
def test_voice_credentials_gate_budget_and_history(http, accounts, monkeypatch, auth_env, endpoint, event_type):
    import anthropic._client
    import persistence
    from multiverse import store
    from server import moderation

    for key in ('ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN'):
        monkeypatch.delenv(key, raising=False)
    # Never inspect a contributor's local SDK profile or send a request.
    monkeypatch.setattr(anthropic._client, 'default_credentials', lambda **kwargs: None)
    if auth_env:
        monkeypatch.setenv(auth_env, 'fixture-credential')
    monkeypatch.delenv(guard.DISABLE_AI_ENV, raising=False)
    monkeypatch.setenv(guard.ANTHROPIC_CAP_ENV, '100')
    monkeypatch.setenv(guard.ANTHROPIC_PER_USER_CAP_ENV, '100')
    monkeypatch.setattr(moderation, 'screen', lambda text: SimpleNamespace(allowed=True))
    adapter = AnthropicProvider()
    monkeypatch.setattr(runtime, 'get_provider', lambda: adapter)
    calls = []
    monkeypatch.setattr(adapter, 'generate', lambda **kwargs: calls.append(kwargs) or Completion('A reply.', True))
    node = store.world_tree(382)
    try:
        status, result, _ = http(endpoint, body={'node_name': node.name, 'message': 'hello'})
        assert status == 200 and result['ai'] is bool(auth_env)
        if auth_env:
            assert result['response'] == 'A reply.'
        else:
            assert result['response'] == (consciousness.fallback_voice(node) if endpoint == '/speak'
                else f"Scout does not answer. Only the traces of a {result['persona']} remain here, already cooling.")
        expected = int(bool(auth_env))
        assert len(calls) == expected
        for bucket in (guard.ANTHROPIC_BUCKET, guard._user_bucket(guard.ANTHROPIC_BUCKET, accounts[0])):
            assert persistence.get_cost_calls(bucket, guard._utc_day()) == expected
        rows = [row for row in persistence.get_node_history(382, node.name) if row['type'] == event_type]
        assert len(rows) == expected
    finally:
        if adapter._client is not None:
            adapter._client.close()


def test_configured_accepts_sdk_credentials_provider_without_fetching_token():
    adapter = AnthropicProvider()
    adapter._client = SimpleNamespace(api_key=None, auth_token=None, credentials=object())
    assert adapter.configured()


def test_client_setup_failure_is_unconfigured(monkeypatch):
    adapter = AnthropicProvider()
    def unavailable():
        raise RuntimeError('private configuration detail')
    monkeypatch.setattr(adapter, '_get_client', unavailable)
    assert not adapter.configured()


@pytest.mark.parametrize('surface', ['node', 'agent'])
@pytest.mark.parametrize('text,reason', [(None, 'refusal'), (None, 'unknown'), ('Partial answer', 'length')])
def test_voice_extraction_keeps_normalized_diagnostics_and_partial_text(alternate, surface, text, reason):
    alternate.result = Completion(text, False, finish_reason=reason)
    node = SpatialNode(name='Vault', level='Room', properties={})
    def call():
        if surface == 'node':
            return consciousness.speak(node, 'Hello')
        return consciousness.voice_agent(SimpleNamespace(name='tender'), 'Tessera', node, 'Hello')
    if text is None:
        with pytest.raises(runtime.NoTextError, match=f'complete=False, finish={reason}'):
            call()
    else:
        assert call() == text


def test_token_authenticated_intention_reaches_proposal(monkeypatch):
    monkeypatch.delenv('NESTED_WORLDS_DISABLE_AI', raising=False)
    adapter = AnthropicProvider()
    calls = []
    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(stop_reason='end_turn', content=[SimpleNamespace(type='text', text=READY)])
    adapter._client = SimpleNamespace(api_key=None, auth_token='fixture-token',
                                     messages=SimpleNamespace(create=create))
    monkeypatch.setattr(runtime, 'get_provider', lambda: adapter)
    charged = []
    monkeypatch.setattr(guard, 'consume_anthropic', lambda **kwargs: charged.append(kwargs) or True)
    node = SpatialNode(name='Vault', level='Object', properties={})
    steps, quiet = intervention_api._propose('engrave', 'visitor', node.name, node, {})
    assert steps == [{'op': 'engrave', 'amount': 1}] and quiet is None
    assert len(calls) == len(charged) == 1
