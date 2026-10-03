"""Validate a downloaded snapshot without modifying it; failed copies need quarantine."""
import argparse
from contextlib import closing
from pathlib import Path
import sqlite3


def validate(path):
    with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as db:
        if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
            raise ValueError('SQLite integrity check failed.')
        if db.execute('PRAGMA journal_mode').fetchone() != ('delete',):
            raise ValueError('Snapshot is not in self-contained DELETE journal mode.')
        for table in ('world_nodes', 'world_mutations', 'invite_keys', 'intervention_work'):
            db.execute('SELECT 1 FROM ' + table + ' LIMIT 1').fetchall()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', type=Path)
    args = parser.parse_args()
    try:
        validate(args.snapshot)
    except (OSError, ValueError, sqlite3.Error) as exc:
        parser.exit(1, f'Snapshot validation failed; retain as unvalidated: {exc}\n')
    print('Self-contained snapshot passed integrity and schema checks; restore rehearsal still required.')


if __name__ == '__main__':
    main()
