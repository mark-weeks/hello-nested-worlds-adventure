"""M4: bounded real heartbeats on disposable born worlds, never live history."""
import multiprocessing
import json
import os
from pathlib import Path
import random
import signal
import sqlite3
from unittest.mock import patch

import pytest

import persistence
from agents.agent import Agent
from causality.staging import drain_due_hops
from multiverse import store, wrap
from puzzles.generators import build_puzzle
from server import heartbeat
from tests.test_delayed_choices import http, walk  # noqa: F401 — shared real HTTP fixture
from tests.test_delivery_recovery import join, snapshot, start_worker

SEED = 382
NAME = 'Tessera'


class Steady(random.Random):
    def choice(self, seq):
        return seq[0]

    def random(self):
        return 0.5


def prepare(name=NAME, partial=False):
    root = store.world_tree(SEED)
    nodes = list(walk(root))
    target = root.children[0].children[0]
    known = [n.name for n in (walk(target) if partial else nodes)]
    context = [{'node': target.name, 'level': target.level, 'state': 'EXPLORE',
                'action': 'explored', 'persona': 'tender'}]
    persistence.save_agent_memory(name, SEED, known, context)
    # Construct a quiet explored world, with ONE unconsumed opportunity.
    # These are attention fixtures, not observations of production frequency.
    with persistence.transaction() as conn:
        conn.executemany('INSERT INTO agent_attention VALUES (?, ?, ?, 0, 0)',
                         [(SEED, name, n.name) for n in nodes if n.name != target.name])
    return root, target, known, context


def aim(target, name=NAME):
    nodes = list(walk(store.world_tree(SEED)))
    index = next(i for i, n in enumerate(nodes) if n.name == target.name)
    persistence.save_agent_scan_cursor(name, SEED, nodes[index - 1].name)


def tick(target, name=NAME, **kwargs):
    # Force reinspection of the same familiar place to stress the fence.
    # Fair unforced scanning is tested separately below.
    aim(target, name)
    with patch.object(heartbeat, 'WANDERER_ROSTER', (name,)), \
            patch.object(heartbeat, '_drop_in', return_value=target):
        return heartbeat.run_tick(SEED, Steady(1), pace=0, max_nodes=kwargs.pop('max_nodes', 1), **kwargs)


def origins(target, kind='SCALE_ACT'):
    return [m for m in persistence.get_node_history(SEED, target.name, limit=200)
            if m['type'] == kind and m['data'].get('agent') and not m['data'].get('_origin')]


@pytest.mark.parametrize('partial', [False, True])
def test_known_place_acts_once_then_retains_context_without_fake_activity(partial):
    _, target, known, old_context = prepare(partial=partial)
    first = tick(target)
    assert first['fresh'] == 0 and first['act']
    after = persistence.load_agent_memory(NAME, SEED)
    assert after['visited_ids'] == known
    assert after['log_entries'][:1] == old_context
    assert any(e['action'] == 'revisited' for e in after['log_entries'])
    assert after['log_entries'][-1]['node'] == target.name
    for _ in range(4):
        quiet = tick(target)
        assert quiet['fresh'] == quiet['work']['visited'] == 0
        assert quiet['act'] is None
        assert quiet['work']['origin_effects'] == 0
    assert persistence.load_agent_memory(NAME, SEED)['log_entries'] == after['log_entries']
    assert len(origins(target)) == 1


def test_http_change_reopens_familiar_opportunity_but_own_landing_does_not(http):
    _, target, _, _ = prepare()
    assert tick(target)['act']
    with persistence._connect() as conn:
        conn.execute("UPDATE verb_maturation SET due_at='2000-01-01'")
    heartbeat.drain_matured_verbs(world_seed=SEED)
    assert persistence.agent_attention_signals(SEED, [target.name])[target.name]['change'] == 0
    assert tick(target)['act'] is None
    accepted = http.post(target, 'Ada')
    with persistence._connect() as conn:
        conn.execute("UPDATE verb_maturation SET due_at='2000-01-01' WHERE status='pending'")
    heartbeat.drain_matured_verbs(world_seed=SEED)
    assert tick(target)['act']
    assert len(origins(target)) == 2
    # Acceptance, pending v2, landing, live M3 projection and historical reload.
    notices = []
    with patch.object(heartbeat, 'broadcast', side_effect=lambda room, msg: notices.append(msg)):
        with persistence._connect() as conn:
            conn.execute("UPDATE verb_maturation SET due_at='2000-01-01' WHERE status='pending'")
            conn.execute("UPDATE causal_queue SET due_at='2000-01-01' WHERE status='pending'")
        heartbeat.drain_matured_verbs(world_seed=SEED)
        drain_due_hops(world_seed=SEED, broadcaster_batch=heartbeat._pump_broadcast_batch)
    outcome = next(n for n in notices if n.get('matured') and n.get('actor') == NAME)
    historic = next(m for m in persistence.get_node_history(SEED, target.name)
                    if m['id'] == outcome['event_id'])
    assert historic['narration'] == outcome['narration']
    assert outcome['narration']['actor_label'] == NAME
    assert outcome['narration']['source_event_id'] != accepted['event_id']
    assert any(n.get('narration', {}).get('phase') == 'arrival' and
               n['narration'].get('actor_label') == NAME for n in notices)
    assert tick(target)['act'] is None
    assert http.bounded_read(target)['pending_actions'] == []


def test_saturation_and_shared_admission_consume_opportunity_without_origin(http):
    _, target, _, _ = prepare()
    persistence.record_substance_change(SEED, target.name, 'TEST_CHANGE', None, {},
                                        {'star_density': 999, 'kindled': False})
    human = http.post(target)
    shared = tick(target)
    assert shared['act'] is None and not origins(target)
    assert persistence.pending_verb_maturations(SEED) == 1
    assert tick(target)['work']['persona_attempts'] == 0
    with persistence._connect() as conn:
        conn.execute("UPDATE verb_maturation SET due_at='2000-01-01'")
    heartbeat.drain_matured_verbs(world_seed=SEED)
    noop = tick(target)
    assert noop['work']['persona_attempts'] == 1 and noop['act'] is None
    assert tick(target)['work']['persona_attempts'] == 0
    assert not origins(target)
    assert persistence.inspect_work('verb_maturation', human['work']['id'])['status'] == 'completed'


def test_other_cast_effects_do_not_create_tending_decay_loop():
    root, target, _, _ = prepare()
    assert tick(target)['act']
    for _ in range(5):
        heartbeat._persona_act(SEED, heartbeat.get_room(SEED), root, 'Vex', 'destabilizer',
                               [target.name], Steady(1))
        assert tick(target)['act'] is None
    assert len(origins(target)) == 1


def puzzle_place():
    root = store.world_tree(SEED)
    return next(n for n in walk(root) if n.properties.get('has_puzzle')
                and not any(a.properties.get('locked') or
                a.properties.get('danger_level', 0) > 4 for a in heartbeat._chain(n)))


def test_puzzle_uses_current_epoch_once_and_never_claims_human_progress(monkeypatch):
    root, _, known, _ = prepare()
    node = puzzle_place()
    persistence.record_mutation(SEED, node.name, 'PUZZLE_REARM', None, {})
    calls = []
    actual = Agent._attempt_puzzle
    def attempt(self, target, epoch=None):
        result = actual(self, target, epoch)
        calls.append((epoch, result))
        return result
    monkeypatch.setattr(Agent, '_attempt_puzzle', attempt)
    assert tick(node)['work']['puzzle_attempts'] == 1
    assert calls[0][0] == 1 and calls[0][1][1] == build_puzzle(node, 1).name
    for _ in range(3):
        assert tick(node)['work']['puzzle_attempts'] == 0
    persistence.record_mutation(SEED, node.name, 'PUZZLE_REARM', None, {})
    assert tick(node)['work']['puzzle_attempts'] == 1
    assert calls[-1][0] == 2
    assert calls[0][1][2] == calls[1][1][2] == build_puzzle(node).difficulty
    assert persistence.get_puzzle_solve(SEED, node.name, build_puzzle(node, 2).name) is None
    assert not [m for m in persistence.get_mutations(SEED, limit=200)
                if m['type'] in ('PUZZLE_ATTEMPT', 'CONSTELLATION_COMPLETE')]
    assert persistence.load_agent_memory(NAME, SEED)['visited_ids'] == known


def test_deterministic_failed_puzzle_waits_for_renewal_even_after_external_change(monkeypatch):
    prepare()
    node = puzzle_place()
    persistence.record_mutation(SEED, node.name, 'PUZZLE_REARM', None, {})
    monkeypatch.setattr(Agent, '_attempt_puzzle', lambda self, node, epoch=None:
                        (False, build_puzzle(node, epoch).name, build_puzzle(node).difficulty))
    assert tick(node)['work']['puzzle_attempts'] == 1
    persistence.record_substance_change(SEED, node.name, 'TEST_CHANGE', 'Ada', {}, {'stabilized': False})
    assert tick(node)['work']['puzzle_attempts'] == 0
    assert len(origins(node, 'PUZZLE_FAILED')) == 1


def test_seal_blocks_entry_agent_success_does_not_open_it_and_human_solve_does():
    prepare()
    root = store.world_tree(SEED)
    node = next(n for n in walk(root) if n.level == 'Room' and n.properties.get('locked')
                and all(a.properties.get('danger_level', 0) <= 4 for a in heartbeat._chain(n)))
    persistence.record_mutation(SEED, node.name, 'PUZZLE_SOLVED', None,
                                {'agent': NAME, 'puzzle': build_puzzle(node).name})
    assert tick(node)['origin'] == node.name
    assert not any(e['node'] == node.name and e['action'] == 'revisited'
                   for e in persistence.load_agent_memory(NAME, SEED)['log_entries'])
    # Same authoritative human solve-state consumed by the existing seal rule.
    persistence.record_mutation(SEED, node.name, 'PUZZLE_SOLVED', 'Ada',
                                {'puzzle': build_puzzle(node).name})
    persistence.record_substance_change(SEED, node.name, 'TEST_CHANGE', 'Ada', {}, {'inscriptions': 2})
    assert tick(node)['work']['visited'] >= 1


def test_danger_withdraws_once_and_never_enters_descendants():
    _, target, _, _ = prepare()
    persistence.record_substance_change(SEED, target.name, 'TEST_CHANGE', 'Ada', {}, {'danger_level': 10})
    first = tick(target)
    assert first['work']['visited'] == 1 and first['work']['origin_effects'] == 0
    assert not origins(target)
    assert 'withdrew' in persistence.load_agent_memory(NAME, SEED)['log_entries'][-1]['action']
    assert tick(target)['work']['visited'] == 0
    persistence.record_substance_change(SEED, target.name, 'TEST_CHANGE', 'Ada', {}, {'danger_level': 1})
    assert tick(target)['act']


def test_fair_scan_cursor_survives_fresh_agents_and_quiet_ticks():
    root, target, _, _ = prepare()
    # Consume the last outstanding opportunity. Every candidate is now quiet.
    persistence.mark_agent_attention(NAME, SEED, target.name, change=0, puzzle=0)
    aim(root)
    names = [n.name for n in walk(root)]
    with patch.object(heartbeat, 'WANDERER_ROSTER', (NAME,)):
        for i in range(8):
            result = heartbeat.run_tick(SEED, Steady(1), max_nodes=1, pace=0)
            assert result['work']['inspected'] == 4
            assert result['work']['visited'] == 0
            assert persistence.load_agent_memory(NAME, SEED)['scan_cursor'] == names[(i + 1) * 4 - 1]


@pytest.mark.parametrize('requested', [0, 1, 4, 10, 100000])
def test_total_work_is_bounded_independently_of_fresh_discovery(requested):
    root, target, _, _ = prepare()
    aim(target)
    selects, hydrations = [], []
    original_connect, original_tree = persistence._connect, store.world_tree
    def connect():
        conn = original_connect()
        conn.set_trace_callback(lambda sql: selects.append(sql) if sql.lstrip().upper().startswith(('SELECT', 'WITH')) else None)
        return conn
    def tree(*args, **kwargs):
        hydrations.append(1)
        return original_tree(*args, **kwargs)
    with patch.object(persistence, '_connect', connect), patch.object(store, 'world_tree', tree), \
            patch.object(heartbeat, 'WANDERER_ROSTER', (NAME,)):
        result = heartbeat.run_tick(SEED, Steady(1), max_nodes=requested, pace=0)
    work = result['work']
    assert work['inspected'] <= min(40, max(0, requested) * 4)
    assert work['visited'] <= min(10, max(0, requested))
    assert work['puzzle_attempts'] <= 2
    assert work['puzzle_attempts'] + work['persona_attempts'] <= 4
    assert work['origin_effects'] <= work['visited'] + 4
    assert work['initial_hops'] <= 4 * max(len(n.children) + bool(n.parent) for n in walk(root))
    assert hydrations == [1]
    assert len(selects) < 150, len(selects)


def test_history_projection_limit_fails_quiet_preserves_memory_and_advances(monkeypatch):
    _, target, known, context = prepare()
    with persistence.transaction() as conn:
        conn.executemany("INSERT INTO world_mutations(world_seed,node_name,mutation_type,data) VALUES (382,?,'PUZZLE_REARM','{}')",
                         [(target.name,)] * 500)
    monkeypatch.setattr(persistence, 'ATTENTION_SQL_STEPS', 1000)
    result = tick(target)
    assert result['work']['projection_limited']
    assert result['fresh'] == result['work']['origin_effects'] == 0
    memory = persistence.load_agent_memory(NAME, SEED)
    assert memory['visited_ids'] == known and memory['log_entries'] == context
    assert memory['scan_cursor'] != target.name
    assert not origins(target)


def test_pending_initial_failure_rolls_back_attention_and_no_notice(monkeypatch):
    _, target, _, context = prepare()
    notices = []
    original = persistence.enqueue_causal_hop
    def failed(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError('initial scheduling failed')
    with patch.object(persistence, 'enqueue_causal_hop', failed), \
            patch.object(heartbeat, 'broadcast', side_effect=lambda room, msg: notices.append(msg)):
        tick(target)
    assert not origins(target)
    assert not persistence.load_agent_attention(NAME, SEED, [target.name])
    assert persistence.pending_verb_maturations(SEED) == persistence.pending_causal_hops(SEED) == 0
    assert not [m for m in notices if m['type'] == 'scale_act']
    assert tick(target)['act']
    assert len(origins(target)) == 1


def cast_worker(db, phase):
    persistence._DB_PATH = Path(db)
    os.environ['NESTED_WORLDS_CANONICAL_SEED'] = ''
    def die():
        os.kill(os.getpid(), signal.SIGKILL)
    root = store.world_tree(SEED)
    target = root.children[0].children[0]
    original = persistence.mark_agent_attention
    def marked(*args, **kwargs):
        if phase == 'before_marker':
            die()
        original(*args, **kwargs)
        if phase == 'after_marker':
            die()
    def notice(room, message):
        if phase == 'after_commit' and message['type'] == 'scale_act':
            die()
    with patch.object(persistence, 'mark_agent_attention', marked), patch.object(heartbeat, 'broadcast', notice):
        tick(target)


@pytest.mark.parametrize('phase', ['before_marker', 'after_marker', 'after_commit'])
def test_process_death_fences_autonomous_acceptance_and_recovers_delivery(phase):
    _, target, _, _ = prepare()
    worker = multiprocessing.get_context('spawn').Process(target=cast_worker, args=(str(persistence._DB_PATH), phase))
    worker.start()
    join(worker, -signal.SIGKILL)
    assert len(origins(target)) == (1 if phase == 'after_commit' else 0)
    tick(target)
    assert len(origins(target)) == 1
    assert len(persistence.load_agent_attention(NAME, SEED, [target.name])) == 1
    with persistence._connect() as conn:
        conn.execute("UPDATE verb_maturation SET due_at='2000-01-01'")
        conn.execute("UPDATE causal_queue SET due_at='2000-01-01'")
    for queue in ('verb_maturation', 'causal_queue'):
        join(start_worker(queue, 'normal'))
    outcomes = [m for m in persistence.get_node_history(SEED, target.name) if m['type'] == 'SCALE_ACT_MATURED']
    assert len(outcomes) == 1 and outcomes[0]['narration']['actor_label'] == NAME
    before = snapshot()
    assert tick(target)['act'] is None
    assert snapshot() == before


def test_v19_upgrade_preserves_memory_world_hinge_history_and_pending(tmp_path, monkeypatch):
    db = persistence._DB_PATH
    with sqlite3.connect(db) as conn:
        for migration in sorted(persistence._MIGRATIONS_DIR.glob('*.sql')):
            if int(migration.name[:4]) >= 20:
                break
            conn.executescript(migration.read_text())
        conn.execute('CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT)')
        conn.executemany('INSERT INTO schema_version(version) VALUES (?)', [(i,) for i in range(1, 20)])
        conn.execute("INSERT INTO agent_memory(agent_name,world_seed,visited_ids,log_entries) VALUES ('Tessera',382,'[\"Remembered-1\"]','[]')")
    persistence._initialized.add(db)
    root = store.world_tree(SEED)
    wrap.hinge_name(SEED)
    galaxy = root.children[0].children[0]
    persistence.record_mutation(SEED, galaxy.name, 'AGENT_VISIT', None, {'agent': NAME})
    persistence.enqueue_verb_maturation(SEED, galaxy.name, 'kindle', {'star_density': 438}, 'Legacy', 300)
    from multiverse.delayed_v2 import prepare as operation_for
    operation, _ = operation_for('kindle', galaxy.level, galaxy.properties)
    persistence.enqueue_verb_maturation(SEED, galaxy.name, 'kindle', {}, NAME, 300, operation=operation)
    with persistence._connect() as conn:
        tables = ['world_nodes', 'world_meta', 'world_mutations', 'causal_queue', 'verb_maturation']
        before = {t: conn.execute(f'SELECT * FROM {t}').fetchall() for t in tables}
    persistence._initialized.discard(db)
    persistence.init_db()
    memory = persistence.load_agent_memory(NAME, SEED)
    assert memory['visited_ids'] == ['Remembered-1'] and memory['scan_cursor'] is None
    with persistence._connect() as conn:
        assert conn.execute('SELECT MAX(version) FROM schema_version').fetchone()[0] == max(int(p.name[:4]) for p in persistence._MIGRATIONS_DIR.glob('*.sql'))
        assert conn.execute('SELECT * FROM agent_attention').fetchall() == []
        assert before == {t: conn.execute(f'SELECT * FROM {t}').fetchall() for t in tables}


def test_recent_context_is_capped_without_forgetting_discovered_names():
    _, target, known, context = prepare()
    persistence.save_agent_memory(NAME, SEED, known, context * 100)
    assert tick(target)['act']
    saved = persistence.load_agent_memory(NAME, SEED)
    assert len(saved['log_entries']) == 100
    assert saved['visited_ids'] == known
    assert saved['log_entries'][-1]['action'] == 'kindled'


def test_current_seal_does_not_imprison_inhabitant_already_inside():
    root = store.world_tree(SEED)
    room = next(n for n in walk(root) if n.level == 'Room' and n.properties.get('locked')
                and all(a.properties.get('danger_level', 0) <= 4 for a in heartbeat._chain(n)))
    nodes = {n.name: n for n in heartbeat._chain(room.children[0])}
    signals = persistence.agent_attention_signals(SEED, list(nodes), seals=True)
    assert not heartbeat._accessible(room.children[0], signals, 7)
    assert heartbeat._accessible(room.children[0], signals, 7, current_name=room.name)


def test_real_human_puzzle_endpoint_then_autonomous_decay_renews_agent_attempt(http):
    import urllib.request
    _, _, _, _ = prepare()
    node = puzzle_place()
    request = urllib.request.Request(http.base_url + '/puzzle/attempt',
        data=json.dumps({'node_name': node.name, 'player_name': 'Ada', 'depth': 11,
                                    'answer': build_puzzle(node).answer}).encode(),
        headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request) as response:
        solved = json.load(response)
    assert solved['correct']
    # Vex reacts once to the human's material settlement. Its real heartbeat
    # decay re-arms the solved puzzle through existing causal wiring.
    persistence.save_agent_memory('Vex', SEED, [n.name for n in walk(store.world_tree(SEED))], [])
    decay = tick(node, 'Vex')
    assert decay['act']
    epoch = persistence.count_node_mutations(SEED, node.name, 'PUZZLE_REARM')
    assert epoch == 1
    attempted = tick(node)
    assert attempted['work']['puzzle_attempts'] == 1
    new_puzzle = build_puzzle(node, epoch)
    rows = origins(node, 'PUZZLE_SOLVED') + origins(node, 'PUZZLE_FAILED')
    assert any(m['data']['puzzle'] == new_puzzle.name for m in rows)
    assert persistence.get_puzzle_solve(SEED, node.name, new_puzzle.name) is None
    assert tick(node)['work']['puzzle_attempts'] == 0


def test_concurrent_heartbeats_cannot_accept_same_opportunity_twice():
    from concurrent.futures import ThreadPoolExecutor
    _, target, _, _ = prepare()
    aim(target)
    with patch.object(heartbeat, 'WANDERER_ROSTER', (NAME,)), \
            patch.object(heartbeat, '_drop_in', return_value=target):
        with ThreadPoolExecutor(2) as pool:
            list(pool.map(lambda _: heartbeat.run_tick(SEED, Steady(1), max_nodes=1, pace=0), range(2)))
    assert len(origins(target)) == 1


def test_backup_restore_retains_attention_cursor_pending_and_completion_fence(tmp_path):
    _, target, known, _ = prepare()
    assert tick(target)['act']
    backup = tmp_path / 'attention-pending.db'
    saved = persistence.load_agent_memory(NAME, SEED)
    attention = persistence.load_agent_attention(NAME, SEED, [target.name])
    persistence.backup_to(backup)
    with persistence._connect() as conn:
        conn.execute("UPDATE verb_maturation SET due_at='2000-01-01'")
    heartbeat.drain_matured_verbs(world_seed=SEED)
    expected = snapshot()
    persistence.restore_from(backup)
    assert persistence.load_agent_memory(NAME, SEED) == saved
    assert persistence.load_agent_attention(NAME, SEED, [target.name]) == attention
    with persistence._connect() as conn:
        conn.execute("UPDATE verb_maturation SET due_at='2000-01-01'")
    join(start_worker('verb_maturation', 'normal'))
    assert snapshot() == expected
    assert tick(target)['act'] is None
    assert persistence.load_agent_memory(NAME, SEED)['visited_ids'] == known


def test_tick_sql_budget_also_bounds_hydration_and_other_database_reads(monkeypatch):
    _, target, known, context = prepare()
    original = persistence.agent_work_budget
    monkeypatch.setattr(persistence, 'agent_work_budget', lambda: original(1000))
    result = tick(target)
    assert result['status'] == 'work_limit'
    assert result['work']['sql_steps'] == 1000
    assert not origins(target)
    saved = persistence.load_agent_memory(NAME, SEED)
    assert saved['visited_ids'] == known and saved['log_entries'] == context


def test_recent_changed_familiar_place_is_prompt_without_resetting_fair_cursor(http):
    root, target, _, _ = prepare()
    assert tick(target)['act']
    with persistence._connect() as conn:
        conn.execute("UPDATE verb_maturation SET due_at='2000-01-01'")
    heartbeat.drain_matured_verbs(world_seed=SEED)
    http.post(target, 'Ada')
    with persistence._connect() as conn:
        conn.execute("UPDATE verb_maturation SET due_at='2000-01-01' WHERE status='pending'")
    heartbeat.drain_matured_verbs(world_seed=SEED)
    nodes = list(walk(root))
    persistence.save_agent_scan_cursor(NAME, SEED, nodes[1000].name)
    with patch.object(heartbeat, 'WANDERER_ROSTER', (NAME,)):
        result = heartbeat.run_tick(SEED, Steady(1), max_nodes=10, pace=0)
    assert result['origin'] == target.name and result['act']
    assert len(origins(target)) == 2
    cursor = persistence.load_agent_memory(NAME, SEED)['scan_cursor']
    assert cursor in [n.name for n in nodes[1001:1041]]
