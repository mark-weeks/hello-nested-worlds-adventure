"""Behavioral regressions from PR #97 review; every world is disposable."""
import json
import urllib.parse
import urllib.request
from unittest.mock import patch

import pytest

import persistence
from agents.agent import Agent
from causality import CausalityBus, EventKind
from interface import _ambient_mode
from multiverse import store
from multiverse.node import SpatialNode
from multiverse.verbs import verb_for_level
from puzzles import gates
from puzzles.generators import build_puzzle
from server import heartbeat
from server.rooms import get_room
from tests.test_agent_attention import NAME, SEED, Steady, aim, prepare, tick, walk
from tests.test_delayed_choices import http  # noqa: F401


def test_plain_drop_in_ignores_danger_above_its_root_but_stops_below_danger():
    leaf = SpatialNode('Leaf-111', 'SubatomicParticle')
    danger = SpatialNode('Danger-112', 'Molecule', [SpatialNode('Inside-1121', 'Atom')],
                         {'danger_level': 10})
    target = SpatialNode('Target-11', 'Room', [leaf, danger])
    SpatialNode('Outside-1', 'Region', [target], {'danger_level': 10})
    events = []
    bus = CausalityBus()
    bus.register_handler(lambda node, event: events.append((node.name, event.kind)))
    agent = Agent('Observer', danger_threshold=7, bus=bus)
    agent.traverse(target)
    assert (target.name, EventKind.AGENT_VISIT) in events
    assert leaf.name in agent.memory and danger.name in agent.memory
    assert danger.children[0].name not in agent.memory
    assert agent.inspected == 4


def dangerous_drop_in():
    root = store.world_tree(SEED)
    return next(n for n in walk(root) if n.parent and n.properties.get('danger_level', 0) <= 7
                and any(a.properties.get('danger_level', 0) > 7 for a in heartbeat._chain(n.parent)))


def test_observe_endpoint_under_dangerous_ancestor_still_visits(http):
    target = dangerous_drop_in()
    query = urllib.parse.urlencode({'node_name': target.name, 'depth': 11, 'name': 'ReviewObserver'})
    with urllib.request.urlopen(http.base_url + '/observe?' + query, timeout=10) as response:
        events = []
        for raw in response:
            if raw.startswith(b'data: '):
                event = json.loads(raw[6:])
                events.append(event)
                if event.get('done'):
                    break
    assert events[-1]['nodes_visited'] > 0
    assert any(e.get('node') == target.name and e.get('kind') == 'AGENT_VISIT' for e in events)
    assert persistence.get_node_history(SEED, target.name)


def test_cli_ambient_under_dangerous_ancestor_leaves_traces(capsys):
    target = dangerous_drop_in()
    with patch('builtins.input', return_value=''):
        _ambient_mode(target, SEED)
    assert persistence.get_node_history(SEED, target.name)
    assert 'agent visit' in capsys.readouterr().out


@pytest.mark.parametrize('blockers', ['consumed_renewals', 'ineligible_verbs'])
def test_priority_skips_dead_opportunities_before_claiming_slots(http, blockers):
    name = NAME if blockers == 'consumed_renewals' else 'Marginalia'
    root, target, _, _ = prepare(name=name)
    persistence.mark_agent_attention(name, SEED, target.name, change=0, puzzle=0)
    nodes = list(walk(root))
    valid = root.children[0].children[0] if name == NAME else root.children[0]
    http.post(valid, 'Ada')
    with persistence._connect() as conn:
        conn.execute("UPDATE verb_maturation SET due_at='2000-01-01'")
    heartbeat.drain_matured_verbs(world_seed=SEED)
    dead = [n for n in nodes if n is not valid and n not in nodes[1001:1013]
            and all(a.properties.get('danger_level', 0) <= 4 for a in heartbeat._chain(n))
            and gates.sealing_room(n) is None
            and (n.properties.get('has_puzzle') if name == NAME else n.level == 'Galaxy')][:2]
    assert len(dead) == 2
    for node in dead:
        if blockers == 'consumed_renewals':
            persistence.record_mutation(SEED, node.name, 'PUZZLE_REARM', None, {})
            persistence.mark_agent_attention(name, SEED, node.name, puzzle=1)
        else:
            persistence.record_substance_change(SEED, node.name, 'TEST_CHANGE', 'Ada', {}, {'star_density': 300})
    persistence.save_agent_scan_cursor(name, SEED, nodes[1000].name)
    with patch.object(heartbeat, 'WANDERER_ROSTER', (name,)):
        result = heartbeat.run_tick(SEED, Steady(1), max_nodes=3, pace=0)
    assert result['origin'] == valid.name
    assert result['act']
    assert persistence.load_agent_memory(name, SEED)['scan_cursor'] in [n.name for n in nodes[1001:1013]]


def quiet_page():
    root, target, _, context = prepare()
    persistence.mark_agent_attention(NAME, SEED, target.name, change=0, puzzle=0)
    aim(root)
    signals = persistence.agent_attention_signals(SEED, [n.name for n in list(walk(root))[:40]], seals=True)
    page = [n for n in list(walk(root))[:40] if heartbeat._accessible(n, signals, 4)
            and n.properties.get('danger_level', 0) <= 4]
    assert len(page) > 4
    return page, context


@pytest.mark.parametrize('with_persona', [False, True])
def test_puzzle_capacity_is_checked_before_revisit_movement_and_context(with_persona):
    page, context = quiet_page()
    for node in page:
        persistence.record_substance_change(SEED, node.name, 'TEST_CHANGE', None,
            {} if with_persona else {'agent': 'Fixture'}, {'has_puzzle': True})
        persistence.record_mutation(SEED, node.name, 'PUZZLE_REARM', None, {})
    moves = []
    with patch.object(heartbeat, 'WANDERER_ROSTER', (NAME,)), \
            patch.object(Agent, '_attempt_puzzle', return_value=(False, 'Fixture puzzle', 1)), \
            patch.object(heartbeat, 'agent_move', side_effect=lambda room, name, node: moves.append(node) or []):
        result = heartbeat.run_tick(SEED, Steady(1), max_nodes=10, pace=0)
    assert result['work']['puzzle_attempts'] == 2
    assert result['work']['visited'] == 2
    assert len(moves) == 2 + result['work']['persona_moves']
    assert result['work']['puzzle_attempts'] + result['work']['persona_attempts'] <= 4
    recent = persistence.load_agent_memory(NAME, SEED)['log_entries']
    assert recent[:len(context)] == context
    assert sum(e['action'] == 'revisited' for e in recent) == 2


def test_deferred_persona_candidates_reserve_the_shared_attempt_capacity():
    page, _ = quiet_page()
    for node in page:
        persistence.record_substance_change(SEED, node.name, 'TEST_CHANGE', 'Ada', {}, {'inscriptions': 1})
    with patch.object(heartbeat, 'WANDERER_ROSTER', (NAME,)):
        result = heartbeat.run_tick(SEED, Steady(1), max_nodes=10, pace=0)
    assert result['fresh'] == 0
    assert 0 < result['work']['visited'] <= 4
    assert result['work']['puzzle_attempts'] + result['work']['persona_attempts'] <= 4


def test_home_drop_in_only_seeds_the_first_fair_cursor():
    _, target, _, _ = prepare()
    with patch.object(heartbeat, 'WANDERER_ROSTER', (NAME,)), \
            patch.object(heartbeat, '_drop_in', return_value=target) as drop:
        cursors = []
        for _ in range(3):
            heartbeat.run_tick(SEED, Steady(1), max_nodes=1, pace=0)
            cursors.append(persistence.load_agent_memory(NAME, SEED)['scan_cursor'])
    assert drop.call_count == 1
    assert len(set(cursors)) == 3


@pytest.mark.parametrize('inside', [False, True])
@pytest.mark.parametrize('solved', [False, True])
def test_heartbeat_and_player_share_seal_boundary_across_renewal(inside, solved):
    root = store.world_tree(SEED)
    room = next(n for n in walk(root) if n.level == 'Room' and n.properties.get('locked')
                and all(a.properties.get('danger_level', 0) <= 4 for a in heartbeat._chain(n)))
    target = room.children[0]
    current = room.name if inside else root.name
    if solved:
        persistence.record_mutation(SEED, room.name, 'PUZZLE_SOLVED', 'Ada', {'puzzle': build_puzzle(room).name})
    for epoch in (0, 1):
        if epoch:
            persistence.record_mutation(SEED, room.name, 'PUZZLE_REARM', None, {})
        signals = persistence.agent_attention_signals(SEED, [n.name for n in heartbeat._chain(target)], seals=True)
        expected = inside or solved and not epoch
        assert (gates.seal_check(SEED, target, current) is None) == expected
        assert heartbeat._accessible(target, signals, 7, current) == expected


@pytest.mark.parametrize('verb,past', [('kindle', 'kindled'), ('inscribe', 'inscribed'), ('observe', 'observed')])
def test_persona_action_uses_the_same_correct_past_tense_in_context_and_summary(verb, past):
    root = store.world_tree(SEED)
    node = next(n for n in walk(root) if verb_for_level(n.level) is not None and verb_for_level(n.level).name == verb)
    context = []
    result = heartbeat._persona_act(SEED, get_room(SEED), root, NAME, 'tender', [node.name], Steady(1),
        chance=False, on_action=lambda node, action: context.append(action))
    assert context == [past]
    assert result.startswith(past + ' ')


def test_saturated_tick_persists_and_broadcasts_actual_visits():
    _, target, _, _ = prepare()
    notices = []
    with patch.object(heartbeat, 'broadcast', side_effect=lambda room, message: notices.append(message)):
        result = tick(target)
    assert result['fresh'] == 0 and result['work']['visited'] == 1
    assert persistence.get_agent_runs(SEED)[0]['nodes_visited'] == 1
    assert next(m for m in notices if m['type'] == 'agent_done')['nodes_visited'] == 1


def test_full_recent_pool_screening_is_measured_and_batch_bounded():
    root, target, _, _ = prepare()
    persistence.mark_agent_attention(NAME, SEED, target.name, change=0, puzzle=0)
    aim(root)
    nodes = list(walk(root))
    for node in nodes[100:164]:
        persistence.record_substance_change(SEED, node.name, 'TEST_CHANGE', 'Ada', {}, {'inscriptions': 1})
    reads, batch_sizes, hydrations = [], [], []
    original_connect, original_signals, original_tree = persistence._connect, persistence.agent_attention_signals, store.world_tree
    def connect():
        conn = original_connect()
        conn.set_trace_callback(lambda sql: reads.append(sql) if sql.lstrip().upper().startswith(('SELECT', 'WITH')) else None)
        return conn
    def signals(seed, names, **kwargs):
        batch_sizes.append(len(names))
        return original_signals(seed, names, **kwargs)
    def tree(*args, **kwargs):
        hydrations.append(1)
        return original_tree(*args, **kwargs)
    with patch.object(persistence, '_connect', connect), patch.object(persistence, 'agent_attention_signals', signals), \
            patch.object(store, 'world_tree', tree), patch.object(heartbeat, 'WANDERER_ROSTER', (NAME,)):
        result = heartbeat.run_tick(SEED, Steady(1), max_nodes=10, pace=0)
    work = result['work']
    assert work['priority_screened'] == 64
    assert work['inspected'] + work['priority_screened'] <= 104
    assert work['projected_nodes'] <= 104 * 11
    assert max(batch_sizes) <= 550
    assert len(reads) < 150
    assert hydrations == [1]
    print(json.dumps({'review_work': work, 'reads': len(reads), 'batch_sizes': batch_sizes}))
