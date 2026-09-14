"""Compare sparse history reads using disposable data under a selected checkout.

Run with Python 3.11: history_probe.py --repo /path/to/checkout
The explicit repository argument allows the same fixture to measure both versions.
"""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.repo.resolve()))
    import persistence as db
    from persistence import participants
    from multiverse import store

    with tempfile.TemporaryDirectory(prefix='enfolded-history-cost-') as directory:
        db._DB_PATH = Path(directory) / 'worlds.db'
        key = 'nw_' + 'a' * 32
        db.mint_invite_key(key, 'Audit reader')
        owner = participants.identify(key)['id']
        node = store.root_name(382)
        participants.save_note(owner, 382, node, 'Saved place', 'audit-note-1')
        db.record_substance_change(382, node, 'SCALE_ACT', 'Audit reader',
                                   {'flavor': 'An old material change'}, {'audit': True})
        original = db._connect
        steps = [0]
        def connect():
            conn = original()
            def progress():
                steps[0] += 100
                return 0
            conn.set_progress_handler(progress, 100)
            return conn
        db._connect = connect
        results = []
        for size, extra in [(0, 0), (2_000, 2_000), (100_000, 98_000)]:
            with db.transaction() as conn:
                conn.executemany('''INSERT INTO world_mutations
                    (world_seed,node_name,mutation_type,player_name,data)
                    VALUES (382,?,'PLAYER_CHAT','Audit reader','{}')''', [(node,)] * extra)
            measurements = {}
            for name, operation in [
                ('journal_recap', lambda: participants.recap(owner, 382)),
                ('puzzle_epochs', lambda: db.count_rearms_by_node(382)),
                ('property_overlays', lambda: db.load_node_property_overrides(382)),
                ('activity_counts', lambda: db.count_mutations_by_node(382)),
            ]:
                steps[0] = 0
                started = time.perf_counter()
                answer = operation()
                measurements[name] = {'sqlite_steps_approx': steps[0],
                                      'ms': round(1_000 * (time.perf_counter() - started), 2)}
                if name == 'journal_recap':
                    assert len(answer) == 1
            results.append({'same_place_chat_rows': size, **measurements})
        print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
