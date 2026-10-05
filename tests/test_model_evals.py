"""Evaluation integrity through real prompts and validators; no network."""
from copy import deepcopy
import json
import subprocess
import sys
from types import SimpleNamespace

import pytest

from consciousness import runtime
from consciousness.runtime import Completion, TokenUsage
from evals.harness import (ROOT, BudgetExceeded, FixtureProvider, Meter, RecordingProvider,
                           digest, execute, grade, load_corpus, read_json, run,
                           task_routing, validate_candidate, write_json)
from evals.reporting import (calibration, checked_run, compare, load_review, report,
                             review_packet, summarize)


@pytest.fixture
def corpus():
    return load_corpus(ROOT / 'evals/corpus.json')


@pytest.fixture
def candidate():
    return read_json(ROOT / 'evals/candidates/fixture.json')


def live_config(candidate):
    config = deepcopy(candidate)
    config.update(provider='anthropic', data_authorization='synthetic-only',
                  terms_review='Synthetic test configuration; not real prices',
                  timeout_seconds=10, max_retries=0,
                  pricing={'fixture-v1': {'input_per_million': 1, 'output_per_million': 2,
                           'cache_read_per_million': .1, 'cache_write_per_million': 1.25,
                           'max_input_tokens': 1000, 'source': 'test-only', 'verified_on': '2026-10-05'}})
    return config


def case(corpus, id):
    return next(c for c in corpus['cases'] if c['id'] == id)


def selection_brief():
    return {'purpose': 'test only', 'owner': 'test', 'frozen_on': '2026-10-05',
            'minimum_repeats': 3, 'calibration_record': None,
            'tasks': {task: {'min_cases': 1, 'min_success_rate': .9, 'max_success_rate_drop': 0,
                            'max_p95_ms': 1000, 'max_cost_per_success_usd': 1,
                            'switch_metric': 'cost', 'minimum_gain': .1, 'max_quality_drop': 0}
                      for task in ('node_voice', 'inhabitant_voice', 'intention', 'moderation')}}


def test_corpus_coverage_and_production_reference_paths(corpus, candidate, tmp_path):
    from agents.personas import CATALOG
    from multiverse.generator import LEVELS
    assert {c['node']['level'] for c in corpus['cases'] if c['task'] == 'node_voice'} == set(LEVELS)
    assert {c['persona'] for c in corpus['cases'] if c['task'] == 'inhabitant_voice'} == {p.name for p in CATALOG}
    for split in ('development', 'holdout'):
        result = run(corpus, candidate, tmp_path / split, split=split, repeats=2)
        assert result['status'] == 'completed'
        assert all(t['error'] is None for t in result['trials'])
        assert all(t['grade']['task_correct'] is not False for t in result['trials'])
        assert all(t['grade']['task_correct'] is None for t in result['trials'] if t['grade']['human_required'])
        assert checked_run(tmp_path / split / 'run.json') == result
        assert len((tmp_path / split / 'trials.jsonl').read_text().splitlines()) == result['planned_trials']
        text, summary = report(result)
        assert summary['evidence'] == 'fixture'
        assert 'No provider/model is selected' in text


def test_multiturn_uses_candidate_reply_and_routing_is_restored(corpus):
    original = runtime.get_provider
    calls = []
    recorder = RecordingProvider(FixtureProvider(['A unique first answer.', 'A second answer.']), calls)
    with task_routing(recorder, 'candidate-snapshot'):
        execute(case(corpus, 'voice-room'))
    assert runtime.get_provider is original
    assert calls[1]['request']['messages'][1] == {'role': 'assistant', 'content': 'A unique first answer.'}
    assert all(c['request']['model'] == 'candidate-snapshot' for c in calls)
    assert calls[0]['request']['system'][0]['cacheable'] is True


def test_inhabitant_turns_use_witnessed_speech_history(corpus):
    calls = []
    with task_routing(RecordingProvider(FixtureProvider(['Remember this specific reply.', 'Second']), calls), 'test'):
        execute(case(corpus, 'inhabitant-tender'))
    context = calls[1]['request']['system'][1]['text']
    assert 'Remember this specific reply.' in context
    assert 'Eval Tender answered' in context


@pytest.mark.parametrize('reply,complete', [
    ('{"status":"ready","ambiguity":"none","steps":[{"op":"fracture","amount":1}]}', True),
    ('{"status":"ready","ambiguity":"none","steps":[{"op":"remote","amount":1}]}', True),
    ('not json', True),
    ('{"status":"unsupported","ambiguity":"none","steps":[]}', False),
    (None, False),
])
def test_invalid_or_wrong_intention_cannot_pass(corpus, reply, complete):
    class Bad(FixtureProvider):
        def generate(self, **kwargs):
            return Completion(reply, complete)
    c = case(corpus, 'intent-negated-destruction')
    calls, output, error = [], [], None
    try:
        with task_routing(RecordingProvider(Bad([]), calls), 'test'):
            output = execute(c)
    except ValueError as exc:
        error = type(exc).__name__
    assert grade(c, output, calls, error)['task_correct'] is False


def test_moderation_fail_open_is_not_a_classifier_pass(corpus):
    class Timeout(FixtureProvider):
        def generate(self, **kwargs):
            raise TimeoutError('secret must never appear in the record')
    c = case(corpus, 'moderation-phone-disclosure')
    calls = []
    with task_routing(RecordingProvider(Timeout([]), calls), 'test'):
        output = execute(c)
    assert output[0]['screen']['allowed'] is True
    assert output[0]['screen']['tier'] == 'fail_open'
    assert grade(c, output, calls, None)['task_correct'] is False
    assert 'secret' not in json.dumps(calls)


def test_model_pass_does_not_hide_local_screen_bypass(corpus):
    c = case(corpus, 'moderation-real-threat')
    calls = []
    with task_routing(RecordingProvider(FixtureProvider(['BLOCK']), calls), 'test'):
        output = execute(c)
    result = grade(c, output, calls, None)
    assert result['task_correct'] is True
    assert result['screen_correct'] is False
    assert output[0]['screen']['tier'] == 'clean'


def test_nonverdict_moderation_reply_fails_even_when_application_allows(corpus):
    c = case(corpus, 'moderation-fantasy-menace')
    calls = []
    with task_routing(RecordingProvider(FixtureProvider(['Probably fine.']), calls), 'test'):
        output = execute(c)
    assert output[0]['allowed'] is True
    assert grade(c, output, calls, None)['task_correct'] is False


@pytest.mark.parametrize('amount', [0, -1, float('nan'), float('inf'), True, None])
def test_budget_rejects_invalid_limits(candidate, amount):
    with pytest.raises(ValueError):
        Meter(live_config(candidate), amount, 10)


def test_budget_reserves_before_dispatch_and_keeps_unknown_usage(candidate):
    meter = Meter(live_config(candidate), .002, 2)
    request = {'model': 'fixture-v1', 'max_tokens': 100}
    reserve = meter.reserve(request)
    assert reserve == pytest.approx(.00145)
    assert meter.settle(reserve, request, Completion('hello', True)) is None
    with pytest.raises(BudgetExceeded):
        meter.reserve(request)
    assert meter.calls == 1


def test_budget_reconciles_usage_and_counts_every_token_class(candidate):
    meter = Meter(live_config(candidate), 1, 1)
    request = {'model': 'fixture-v1', 'max_tokens': 100}
    reserve = meter.reserve(request)
    cost = meter.settle(reserve, request, Completion('hi', True, TokenUsage(10, 3, 20, 30)))
    assert cost == pytest.approx((10 + 6 + 2 + 37.5) / 1_000_000)
    assert meter.accounted == pytest.approx(cost)
    with pytest.raises(BudgetExceeded):
        meter.reserve(request)


def test_invalid_bound_halts_further_dispatch(candidate):
    meter = Meter(live_config(candidate), 10, 20)
    request = {'model': 'fixture-v1', 'max_tokens': 10}
    reserve = meter.reserve(request)
    meter.settle(reserve, request, Completion('hi', True, TokenUsage(100000, 10, 0, 0)))
    assert meter.halted
    with pytest.raises(BudgetExceeded):
        meter.reserve(request)


def test_partial_run_preserves_calls_and_is_not_comparable(corpus, candidate, tmp_path):
    result = run(corpus, live_config(candidate), tmp_path / 'partial', tasks=['node_voice'],
                 live=True, max_usd=.003, max_calls=1, provider=FixtureProvider(['first']), brief=selection_brief())
    assert result['status'] == 'budget_stopped'
    assert result['budget']['dispatched_calls'] == 1
    assert len(result['trials'][0]['calls']) == 1
    assert result['trials'][0]['error'] == 'BudgetExceeded'
    with pytest.raises(ValueError, match='partial'):
        compare(result, result)


def test_fixture_run_never_constructs_an_sdk_client(corpus, candidate, tmp_path, monkeypatch):
    from consciousness.anthropic_provider import AnthropicProvider
    monkeypatch.setattr(AnthropicProvider, '_get_client', lambda *a: pytest.fail('paid provider touched'))
    run(corpus, candidate, tmp_path / 'offline', tasks=['intention'])


def test_live_requires_explicit_candidate_terms_prices_and_flag(candidate):
    config = live_config(candidate)
    with pytest.raises(ValueError, match='--live'):
        validate_candidate(config)
    config['terms_review'] = None
    with pytest.raises(ValueError, match='terms'):
        validate_candidate(config, live=True)
    config = live_config(candidate)
    config['max_retries'] = 2
    with pytest.raises(ValueError, match='retries'):
        validate_candidate(config, live=True)
    config['provider'] = 'unsupported'
    with pytest.raises(ValueError, match='no evaluated adapter'):
        validate_candidate(config, live=True)


def test_repeated_cases_do_not_inflate_confidence_denominator(corpus, candidate, tmp_path):
    result = run(corpus, candidate, tmp_path / 'repeated', tasks=['intention'], repeats=3)
    summary = summarize(result)['tasks']['intention']
    assert summary['trials'] == summary['cases_complete'] * 3
    assert summary['cases_passing_every_repeat'] == summary['cases_complete']
    assert summary['case_consistency_wilson_95'][0] < .9


def test_unknown_cost_is_never_zero_or_success_cost(corpus, candidate, tmp_path):
    result = run(corpus, candidate, tmp_path / 'cost', tasks=['intention'])
    result['trials'][0]['calls'][0]['cost_usd'] = None
    summary = summarize(result)['tasks']['intention']
    assert summary['cost_usd'] is None
    assert summary['cost_per_success_usd'] is None
    assert summary['unknown_cost_calls'] == 1


def scored_packet(tmp_path, result, corpus):
    folder = tmp_path / 'review'
    packet = review_packet(result, corpus, folder)
    packet['reviewer'] = 'Test reviewer (synthetic harness test)'
    for item in packet['items']:
        item['scores'] = dict.fromkeys(item['scores'], 3)
        item['critical_violation'] = False
        item['notes'] = 'Synthetic test grades, not human calibration evidence.'
    write_json(folder / 'review.json', packet)
    return folder, packet


def test_blind_packet_human_grading_and_calibration(corpus, candidate, tmp_path):
    result = run(corpus, candidate, tmp_path / 'run', tasks=['node_voice'])
    folder, packet = scored_packet(tmp_path, result, corpus)
    assert candidate['id'] not in json.dumps(packet)
    assert 'fixture-v1' not in json.dumps(packet)
    human = load_review(result, folder / 'review.json', folder / 'key.json')
    assert summarize(result, human)['tasks']['node_voice']['unknown'] == 0
    judge = deepcopy(human)
    next(iter(judge.values()))['success'] = False
    agreement = calibration(human, judge)
    assert agreement['pass_fail_agreements'] == agreement['paired_items'] - 1
    packet['kind'] = 'model'
    write_json(folder / 'review.json', packet)
    with pytest.raises(ValueError, match='human reviewer'):
        load_review(result, folder / 'review.json', folder / 'key.json')


@pytest.mark.parametrize('mutation', ['duplicate', 'missing', 'unknown', 'wrong-run', 'rubric', 'bool-score', 'output'])
def test_review_cannot_drop_or_duplicate_hard_cases(corpus, candidate, tmp_path, mutation):
    result = run(corpus, candidate, tmp_path / 'run', tasks=['node_voice'])
    folder, packet = scored_packet(tmp_path, result, corpus)
    if mutation == 'duplicate':
        packet['items'].append(packet['items'][0])
    elif mutation == 'missing':
        packet['items'].pop()
    elif mutation == 'unknown':
        packet['items'][0]['id'] = 'invented'
    elif mutation == 'wrong-run':
        result['run_sha256'] = 'not the reviewed run'
    elif mutation == 'rubric':
        packet['rubric']['version'] = 'changed'
    elif mutation == 'output':
        packet['items'][0]['outputs'] = [{'text': 'a replacement answer'}]
    else:
        packet['items'][0]['scores']['grounding'] = True
    write_json(folder / 'review.json', packet)
    with pytest.raises(ValueError):
        load_review(result, folder / 'review.json', folder / 'key.json')


def test_unknown_human_grades_and_critical_failure_stay_visible(corpus, candidate, tmp_path):
    result = run(corpus, candidate, tmp_path / 'run', tasks=['node_voice'])
    folder, packet = scored_packet(tmp_path, result, corpus)
    packet['items'][0]['scores']['fiction'] = None
    packet['items'][1]['critical_violation'] = True
    write_json(folder / 'review.json', packet)
    summary = summarize(result, load_review(result, folder / 'review.json', folder / 'key.json'))['tasks']['node_voice']
    assert summary['unknown'] == 1
    assert summary['critical_failures'] == 1
    assert summary['cost_per_success_usd'] is None


def test_comparison_rejects_different_inputs_and_shows_fixture_limit(corpus, candidate, tmp_path):
    first = run(corpus, candidate, tmp_path / 'first', tasks=['intention'])
    second = run(corpus, candidate, tmp_path / 'second', tasks=['intention'])
    paired = compare(first, second)
    assert paired['evidence'] == 'fixture-involved'
    assert paired['tasks']['intention']['ties'] == first['planned_trials']
    second['corpus_sha256'] = 'different'
    with pytest.raises(ValueError, match='corpus'):
        compare(first, second)


def test_altered_run_is_detected(corpus, candidate, tmp_path):
    result = run(corpus, candidate, tmp_path / 'run', tasks=['intention'])
    result['trials'][0]['outputs'] = []
    write_json(tmp_path / 'run/run.json', result)
    with pytest.raises(ValueError, match='changed'):
        checked_run(tmp_path / 'run/run.json')


def test_group_leak_and_duplicate_ids_rejected(corpus, tmp_path):
    path = tmp_path / 'corpus.json'
    duplicate = deepcopy(corpus)
    duplicate['cases'].append(duplicate['cases'][0])
    write_json(path, duplicate)
    with pytest.raises(ValueError, match='unique'):
        load_corpus(path)
    corpus['cases'][1]['group'] = corpus['cases'][0]['group']
    corpus['cases'][1]['split'] = 'holdout'
    write_json(path, corpus)
    with pytest.raises(ValueError, match='leaks'):
        load_corpus(path)


def test_cli_run_and_report_from_another_directory(tmp_path):
    target = tmp_path / 'cli-run'
    args = [sys.executable, str(ROOT / 'scripts/model_eval.py'), 'run', '--output', str(target)]
    completed = subprocess.run(args + ['--task', 'intention', '--repeats', '1'],
                               cwd=tmp_path, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert (target / 'report.md').exists()
    assert read_json(target / 'summary.json')['evidence'] == 'fixture'
    repeated = subprocess.run(args, cwd=tmp_path, capture_output=True, text=True)
    assert repeated.returncode == 2


def test_adapter_records_returned_model_version():
    from consciousness.anthropic_provider import AnthropicProvider
    provider = AnthropicProvider()
    provider._client = SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs:
        SimpleNamespace(content=[SimpleNamespace(type='text', text='hi')], usage=None,
                        stop_reason='end_turn', model='resolved-snapshot')))
    result = provider.generate(model='requested-alias', system=(), messages=[], max_tokens=4)
    assert result.resolved_model == 'resolved-snapshot'


def test_digest_changes_with_configuration():
    assert digest({'model': 'a'}) != digest({'model': 'b'})


def test_fixtures_cannot_earn_selection_even_with_favorable_thresholds(corpus, candidate, tmp_path):
    brief = selection_brief()
    first = run(corpus, candidate, tmp_path / 'first', tasks=['intention'],
                split='holdout', repeats=3, brief=brief)
    second = run(corpus, candidate, tmp_path / 'second', tasks=['intention'],
                 split='holdout', repeats=3, brief=brief)
    checks = compare(first, second)['selection_checks']
    assert 'fixture evidence cannot qualify a candidate' in checks['reasons']
    assert 'independent label/rubric calibration record is missing' in checks['reasons']
    assert checks['tasks']['intention']['status'] != 'supports human review'


def test_live_requires_brief_before_provider_dispatch(corpus, candidate, tmp_path):
    with pytest.raises(ValueError, match='frozen selection brief'):
        run(corpus, live_config(candidate), tmp_path / 'unplanned', live=True,
            max_usd=1, max_calls=1, provider=FixtureProvider([]))
