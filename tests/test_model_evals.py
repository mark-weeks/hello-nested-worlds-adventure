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
    assert grade(c, output, calls, None)['task_correct'] is None
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
    assert result['status'] == 'call_limit_reached'
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


def single_case(corpus, id):
    result = deepcopy(corpus)
    result['cases'] = [case(result, id)]
    return result


@pytest.mark.parametrize('tokens', [1.5, True, None, 0, -1])
def test_input_reservation_bound_requires_positive_integer(candidate, tokens):
    config = live_config(candidate)
    config['pricing']['fixture-v1']['max_input_tokens'] = tokens
    with pytest.raises(ValueError, match='max_input_tokens.*integer'):
        validate_candidate(config, live=True)


@pytest.mark.parametrize('mode', ['not_run', 'interrupted', 'transport_error'])
def test_operational_outcomes_preserve_answers_without_semantic_failure(corpus, candidate, tmp_path, mode):
    class Partial(FixtureProvider):
        def generate(self, **kwargs):
            if len(kwargs['messages']) > 1:
                raise TimeoutError('private provider body')
            return super().generate(**kwargs)
    selected = single_case(corpus, 'voice-room')
    selected['cases'][0]['critical'] = True
    provider = Partial(['First answer.']) if mode == 'transport_error' else FixtureProvider(['First answer.'])
    result = run(selected, live_config(candidate), tmp_path / mode, live=True, provider=provider,
                 max_usd=.00001 if mode == 'not_run' else 1,
                 max_calls=1 if mode == 'interrupted' else 10, brief=selection_brief())
    trial = result['trials'][0]
    assert trial['grade']['outcome'] == mode
    assert trial['grade']['task_correct'] is None
    assert trial['outputs'] == ([] if mode == 'not_run' else [{'status': 'spoken', 'text': 'First answer.'}])
    summary = summarize(result)['tasks']['node_voice']
    assert summary['passed'] == summary['failed'] == summary['critical_failures'] == 0
    assert summary['unknown'] == summary['operational_outcomes'][mode] == 1
    assert summary['cost_per_success_usd'] is None
    assert result['status'] == {'not_run': 'spend_limit_reached', 'interrupted': 'call_limit_reached',
                                'transport_error': 'completed'}[mode]
    assert checked_run(tmp_path / mode / 'run.json') == result
    assert 'private provider body' not in json.dumps(result)
    assert read_json(tmp_path / mode / 'trials.jsonl')['outputs'] == trial['outputs']
    packet = review_packet(result, selected, tmp_path / 'review')
    assert packet['items'][0]['outputs'] == trial['outputs']
    assert packet['items'][0]['grading_required'] is False
    report(result)  # no-dispatch latency is n/a, never a zero-latency win
    if mode == 'transport_error':
        paired = compare(result, result)
        assert paired['tasks']['node_voice']['unknown_pairs'] == 1
        assert paired['selection_checks']['tasks']['node_voice']['status'] != 'supports human review'


def test_moderation_transport_evidence_does_not_invent_classifier_miss(corpus, candidate, tmp_path):
    class Timeout(FixtureProvider):
        def generate(self, **kwargs):
            raise TimeoutError()
    result = run(single_case(corpus, 'moderation-phone-disclosure'), live_config(candidate), tmp_path / 'run',
                 live=True, max_usd=1, max_calls=10, provider=Timeout([]), brief=selection_brief())
    summary = summarize(result)['tasks']['moderation']
    assert summary['transport_errors'] == summary['screen_fail_open'] == summary['unknown'] == 1
    assert summary['screen_failures'] == summary['classifier_misses'] == summary['critical_failures'] == 0
    assert result['trials'][0]['grade']['screen_correct'] is None


@pytest.mark.parametrize('reply,complete', [(None, False), ('refused', False), ('truncated', False)])
def test_invalid_voice_needs_no_fabricated_human_grade(corpus, candidate, tmp_path, reply, complete):
    class Mixed(FixtureProvider):
        def generate(self, **kwargs):
            if self.first:
                self.first = False
                return Completion(reply, complete, TokenUsage(0, 0, 0, 0))
            return super().generate(**kwargs)
    selected = single_case(corpus, 'voice-room')
    provider = Mixed(['Good voice.'] * 4)
    provider.first = True
    result = run(selected, live_config(candidate), tmp_path / 'run', repeats=2, live=True,
                 max_usd=1, max_calls=10, provider=provider, brief=selection_brief())
    folder, packet = scored_packet(tmp_path, result, selected)
    for item in packet['items']:
        if not item['grading_required']:
            item.update(scores=dict.fromkeys(item['scores']), critical_violation=None, notes='')
    write_json(folder / 'review.json', packet)
    summary = summarize(result, load_review(result, folder / 'review.json', folder / 'key.json'))['tasks']['node_voice']
    assert summary['failed'] == summary['passed'] == summary['invalid_completions'] == 1
    assert summary['unknown'] == 0
    assert summary['quality_eligible_trials'] == summary['quality_graded_trials'] == 1
    assert summary['quality_mean'] == 3


@pytest.mark.parametrize('field', ['reviewer', 'notes'])
def test_null_review_text_is_operator_error(corpus, candidate, tmp_path, field):
    result = run(corpus, candidate, tmp_path / 'run', tasks=['node_voice'])
    folder, packet = scored_packet(tmp_path, result, corpus)
    if field == 'reviewer':
        packet[field] = None
    else:
        packet['items'][0][field] = None
    write_json(folder / 'review.json', packet)
    with pytest.raises(ValueError, match='reviewer|notes'):
        load_review(result, folder / 'review.json', folder / 'key.json')


@pytest.mark.parametrize('fault', ['missing-version', 'no-git'])
def test_run_validation_precedes_output_creation(corpus, candidate, tmp_path, monkeypatch, fault):
    if fault == 'missing-version':
        corpus.pop('version')
        write_json(tmp_path / 'corpus.json', corpus)
        with pytest.raises(ValueError, match='corpus version'):
            load_corpus(tmp_path / 'corpus.json')
    else:
        def no_git(*args, **kwargs):
            raise subprocess.CalledProcessError(128, ['git'], stderr='private path')
        monkeypatch.setattr(subprocess, 'check_output', no_git)
    with pytest.raises(ValueError, match='corpus version|readable Git worktree'):
        run(corpus, candidate, tmp_path / 'run')
    assert not (tmp_path / 'run').exists()


def test_review_uses_run_snapshot_and_failure_is_retryable(corpus, candidate, tmp_path, monkeypatch):
    from evals import harness
    result = run(corpus, candidate, tmp_path / 'run', tasks=['node_voice'])
    changed = deepcopy(result['rubric'])
    changed['version'] = 'new-rubric'
    with pytest.raises(ValueError, match='rubric differs'):
        review_packet(result, corpus, tmp_path / 'review', rubric=changed)
    assert not (tmp_path / 'review').exists()
    monkeypatch.setattr(harness, 'ROOT', tmp_path)  # no current rubric is available
    packet = review_packet(result, corpus, tmp_path / 'review')
    assert packet['rubric'] == read_json(tmp_path / 'run/rubric.json')
    legacy = deepcopy(result)
    legacy.pop('rubric')
    review_packet(legacy, corpus, tmp_path / 'legacy', rubric=read_json(tmp_path / 'run/rubric.json'))


@pytest.mark.parametrize('status,signature,message', [
    ('running', None, 'incomplete'), ('completed', None, 'missing.*hash'),
    ('completed', 'bogus', 'contents have changed')])
def test_checked_run_diagnoses_status_and_hash_separately(tmp_path, status, signature, message):
    record = {'status': status}
    if signature:
        record['run_sha256'] = signature
    write_json(tmp_path / 'run.json', record)
    with pytest.raises(ValueError, match=message):
        checked_run(tmp_path / 'run.json')


@pytest.mark.parametrize('expected', [
    {'status': 'ready', 'ambiguity': 'target', 'steps': []},
    {'status': 'unsupported', 'ambiguity': 'action', 'steps': []},
    {'status': 'unsupported', 'ambiguity': 'none', 'steps': [{'op': 'fracture', 'amount': 1}]},
    {'status': 'clarify', 'ambiguity': 'none', 'steps': []},
    {'status': 'clarify', 'ambiguity': 'target'},
    {'status': 'clarify', 'ambiguity': 'target', 'steps': [], 'extra': True},
])
def test_unreachable_intention_labels_rejected(corpus, tmp_path, expected):
    case(corpus, 'intent-negated-destruction')['expected'] = expected
    write_json(tmp_path / 'corpus.json', corpus)
    with pytest.raises(ValueError, match='intention expectation'):
        load_corpus(tmp_path / 'corpus.json')


@pytest.mark.parametrize('live', [False, True])
def test_journal_sync_is_limited_to_live_evidence(corpus, candidate, tmp_path, monkeypatch, live):
    from evals import harness
    syncs = []
    monkeypatch.setattr(harness.os, 'fsync', lambda fd: syncs.append(fd))
    selected = single_case(corpus, 'voice-room')
    kwargs = dict(live=True, max_usd=1, max_calls=10, provider=FixtureProvider(['one', 'two']),
                  brief=selection_brief()) if live else {}
    run(selected, live_config(candidate) if live else candidate, tmp_path / 'run', **kwargs)
    assert bool(syncs) is live


def test_prompt_blocks_reconstruct_identical_requests_and_survive_unfinished_manifest(corpus, candidate, tmp_path):
    from evals.harness import expand_request
    result = run(single_case(corpus, 'voice-room'), candidate, tmp_path / 'run', repeats=2)
    calls = [c for t in result['trials'] for c in t['calls']]
    assert len(result['system_blocks']) == 1
    assert all('text' not in c['request']['system'][0] for c in calls)
    for call in calls:
        assert digest(expand_request(call['request'], result['system_blocks'])) == call['request_sha256']
    # An interrupted run.json need not have the final block map: the journal uses durable blobs.
    blocks = {p.stem: read_json(p) for p in (tmp_path / 'run/prompts').glob('*.json')}
    journal = [json.loads(line) for line in (tmp_path / 'run/trials.jsonl').read_text(encoding='utf-8').splitlines()]
    for trial in journal:
        for call in trial['calls']:
            assert digest(expand_request(call['request'], blocks)) == call['request_sha256']
    blocks[next(iter(blocks))] = 'corrupted'
    with pytest.raises(ValueError, match='changed system prompt'):
        expand_request(calls[0]['request'], blocks)


@pytest.mark.parametrize('task', ['node_voice', 'inhabitant_voice', 'intention', 'moderation'])
def test_production_task_requests_selected_model_and_rejects_drift(corpus, candidate, tmp_path, monkeypatch, task):
    from contextlib import contextmanager
    from evals import harness
    result = run(corpus, candidate, tmp_path / 'correct', tasks=[task])
    assert all(c['request']['model'] == candidate['models'][task] for t in result['trials'] for c in t['calls'])
    @contextmanager
    def drifted(provider, model):
        with task_routing(provider, 'unexpected-production-default'):
            yield
    monkeypatch.setattr(harness, 'task_routing', drifted)
    result = run(corpus, live_config(candidate), tmp_path / 'drift', tasks=[task], live=True,
                 max_usd=1, max_calls=10, provider=FixtureProvider([]), brief=selection_brief())
    assert result['status'] == 'routing_mismatch'
    assert result['budget']['dispatched_calls'] == 0
    assert result['trials'][0]['grade']['outcome'] == 'harness_error'


def test_invalid_pricing_bound_has_distinct_finished_status(corpus, candidate, tmp_path):
    class OverBound(FixtureProvider):
        def generate(self, **kwargs):
            result = super().generate(**kwargs)
            return Completion(result.text, True, TokenUsage(100000, 0, 0, 0))
    selected = single_case(corpus, 'intent-negated-destruction')
    result = run(selected, live_config(candidate), tmp_path / 'run', live=True, max_usd=10,
                 max_calls=10, provider=OverBound(selected['cases'][0]['fixture']), brief=selection_brief())
    assert result['status'] == 'pricing_bound_exceeded'
    assert result['trials'][0]['grade']['task_correct'] is True
    assert checked_run(tmp_path / 'run/run.json') == result


def test_cli_artifacts_are_utf8_under_ascii_locale(tmp_path):
    import os
    target = tmp_path / 'unicode-run'
    args = [sys.executable, '-X', 'utf8=0', str(ROOT / 'scripts/model_eval.py'), 'run',
            '--task', 'node_voice', '--repeats', '1', '--output', str(target)]
    env = {**os.environ, 'LC_ALL': 'C', 'LANG': 'C', 'PYTHONCOERCECLOCALE': '0', 'PYTHONUTF8': '0'}
    completed = subprocess.run(args, cwd=tmp_path, env=env, capture_output=True)
    assert completed.returncode == 0, completed.stderr
    result = checked_run(target / 'run.json')
    assert result['corpus_sha256'] == digest(read_json(target / 'corpus.json'))
    args = [sys.executable, '-X', 'utf8=0', str(ROOT / 'scripts/model_eval.py'), 'review',
            str(target / 'run.json'), '--output', str(tmp_path / 'review')]
    reviewed = subprocess.run(args, cwd=tmp_path, env=env, capture_output=True)
    assert reviewed.returncode == 0, reviewed.stderr
    assert read_json(tmp_path / 'review/review.json')['items']


def test_harness_failure_before_dispatch_remains_unknown_in_comparison(corpus, candidate, tmp_path, monkeypatch):
    from evals import harness
    def broken(*args):
        raise TypeError('harness defect')
    monkeypatch.setattr(harness, 'execute', broken)
    result = run(single_case(corpus, 'voice-room'), candidate, tmp_path / 'run', brief=selection_brief())
    summary = summarize(result)['tasks']['node_voice']
    assert summary['operational_outcomes']['harness_error'] == summary['unknown'] == 1
    assert summary['critical_failures'] == summary['failed'] == 0
    assert summary['p95_ms'] is None
    assert compare(result, result)['selection_checks']['tasks']['node_voice']['status'] != 'supports human review'
