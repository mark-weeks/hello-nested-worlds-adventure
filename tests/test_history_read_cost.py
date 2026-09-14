"""Permanent history can grow without making sparse material reads scan chatter."""
import pytest

import persistence as db
from persistence import participants
from multiverse import store


@pytest.fixture
def busy_place():
    key = 'nw_' + 'b' * 32
    db.mint_invite_key(key, 'History reader')
    owner = participants.identify(key)['id']
    node = store.root_name(382)
    participants.save_note(owner, 382, node, 'Private observation', 'history-note-1')
    db.record_substance_change(382, node, 'SCALE_ACT', 'History reader',
                               {'flavor': 'A material change'}, {'audit': {'kept': True}})
    db.record_mutation(382, node, 'PUZZLE_REARM', None, {})
    expected = {
        'recap': participants.recap(owner, 382),
        'overlays': db.load_node_property_overrides(382),
        'epochs': db.count_rearms_by_node(382),
    }
    with db.transaction() as conn:
        conn.executemany('''INSERT INTO world_mutations
            (world_seed,node_name,mutation_type,player_name,data)
            VALUES (382,?,'PLAYER_CHAT','History reader','{}')''', [(node,)] * 100_000)
    return owner, node, expected


@pytest.mark.parametrize('surface', ['recap', 'overlays', 'scoped_overlays', 'epochs'])
def test_sparse_reads_ignore_chatter_at_the_same_place(busy_place, surface):
    owner, node, expected = busy_place
    # SQL operation counts are stable across machines; wall time is not a gate.
    with db.agent_work_budget(5_000):
        if surface == 'recap':
            assert participants.recap(owner, 382) == expected['recap']
        elif surface == 'overlays':
            assert db.load_node_property_overrides(382) == expected['overlays']
        elif surface == 'scoped_overlays':
            assert db.load_node_property_overrides(382, [node]) == expected['overlays']
        else:
            assert db.count_rearms_by_node(382) == expected['epochs']


def test_node_epoch_lookup_ignores_other_places_renewals(busy_place):
    _, node, _ = busy_place
    with db.transaction() as conn:
        conn.executemany('''INSERT INTO world_mutations
            (world_seed,node_name,mutation_type,data) VALUES (382,?,'PUZZLE_REARM','{}')''',
            [('Another place',)] * 10_000)
    with db.agent_work_budget(5_000):
        assert db.count_rearms_by_node(382, node) == {node: 1}
        assert db.count_rearms_by_node(382, 'Unvisited') == {}
        assert db.count_rearms_by_node(999, node) == {}


def test_index_upgrade_preserves_populated_world_and_is_idempotent(busy_place):
    from puzzles.instances import get_puzzle
    from persistence import intents, situations

    owner, node, expected = busy_place
    get_puzzle(382, store.resolve_node_by_name(382, node))
    intents.execute(owner, 382, 'audit', 'upgrade-receipt', {}, lambda: {'accepted': True})
    situations.install(382)
    db.enqueue_causal_hop(382, node, 'SCALE_ACT', 1, 'down', {}, 0)
    db.enqueue_verb_maturation(382, node, 'kindle', {'density': 10}, None, 0)
    with db.transaction() as conn:
        conn.execute("UPDATE causal_queue SET status='completed', outcome='applied'")
        # Recreate the exact v23 schema: v24 adds only these two indexes.
        conn.execute('DROP INDEX idx_world_mutations_material_node')
        conn.execute('DROP INDEX idx_world_mutations_rearms')
        conn.execute('DELETE FROM schema_version WHERE version=24')
        names = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name!='schema_version'")]
        before = {name: conn.execute(f'SELECT * FROM "{name}" ORDER BY rowid').fetchall() for name in names}
    db._initialized.discard(db._DB_PATH)
    db.init_db()
    db.init_db()
    with db._connection() as conn:
        assert {name: conn.execute(f'SELECT * FROM "{name}" ORDER BY rowid').fetchall() for name in names} == before
        assert conn.execute('SELECT COUNT(*) FROM schema_version WHERE version=24').fetchone()[0] == 1
    with db.agent_work_budget(5_000):
        assert participants.recap(owner, 382) == expected['recap']
