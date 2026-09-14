"""Permanent history can grow without making sparse material reads scan chatter."""
from contextlib import closing
import sqlite3

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


@pytest.mark.parametrize('surface', ['recap', 'overlays', 'scoped_overlays', 'epochs'])
def test_reads_survive_v23_restore_without_restart(busy_place, surface, tmp_path, monkeypatch):
    owner, node, expected = busy_place
    backup = tmp_path / 'v23.db'
    db.backup_to(backup)
    with closing(sqlite3.connect(backup)) as conn:
        conn.executescript('DROP INDEX idx_world_mutations_material_node; '
                           'DROP INDEX idx_world_mutations_rearms; '
                           'DELETE FROM schema_version WHERE version=24;')
    assert db._DB_PATH in db._initialized
    def forbidden(*args):
        raise AssertionError('Restored schemas must remain readable without migration')
    monkeypatch.setattr(db, '_run_migrations', forbidden)
    db.restore_from(backup)
    if surface == 'recap':
        assert participants.recap(owner, 382) == expected['recap']
    elif surface == 'overlays':
        assert db.load_node_property_overrides(382) == expected['overlays']
    elif surface == 'scoped_overlays':
        assert db.load_node_property_overrides(382, [node]) == expected['overlays']
    else:
        assert db.count_rearms_by_node(382) == expected['epochs']
        assert db.count_rearms_by_node(382, node) == {node: 1}
    with db._connection() as conn:
        assert conn.execute('SELECT MAX(version) FROM schema_version').fetchone()[0] == 23
        assert not conn.execute("SELECT 1 FROM sqlite_master WHERE name IN "
                                "('idx_world_mutations_rearms','idx_world_mutations_material_node')").fetchall()


@pytest.mark.parametrize('solved', [False, True])
def test_puzzle_attempt_epoch_check_ignores_other_places(solved, monkeypatch):
    from server.rooms import get_room, puzzle_attempt, PuzzleRenewed

    node, puzzle = 'Place-1', 'The Lock'
    db.record_mutation(382, node, 'PUZZLE_REARM', None, {})
    if solved:
        db.record_mutation(382, node, 'PUZZLE_SOLVED', 'Ada',
                           {'puzzle': puzzle, 'contributors': ['Ada']})
    with db.transaction() as conn:
        conn.executemany("INSERT INTO world_mutations (world_seed,node_name,mutation_type,data) "
                         "VALUES (382,'Elsewhere-1','PUZZLE_REARM','{}')", [()] * 10_000)
    # Budget only epoch reads; co-op hydration has separate query contracts.
    original = db._connect
    epoch_reads = []
    def connect():
        conn = original()
        steps, charge = 0, False
        def trace(statement):
            nonlocal steps, charge
            steps = 0
            charge = "mutation_type = 'PUZZLE_REARM'" in statement
            if charge:
                epoch_reads.append(statement)
        def progress():
            nonlocal steps
            steps += 100
            return charge and steps >= 5_000
        conn.set_trace_callback(trace)
        conn.set_progress_handler(progress, 100)
        return conn
    monkeypatch.setattr(db, '_connect', connect)
    room = get_room(382)
    with puzzle_attempt(room, node, puzzle, 'Bob', False, expected_epoch=1) as (session, just_solved):
        assert not just_solved
        assert session.solver == ('Ada' if solved else None)
        assert 'Bob' in session.contributors
    with pytest.raises(PuzzleRenewed):
        with puzzle_attempt(room, node, puzzle, 'Bob', False, expected_epoch=0):
            pytest.fail('An old epoch must never be accepted')
    assert len(epoch_reads) == 2
