"""Stored first-use puzzle definitions and their public observational evidence."""
import json
import persistence as db


def read(seed, node, epoch):
    db.init_db()
    with db._connection() as conn:
        return conn.execute('''SELECT definition_version,definition,evidence FROM puzzle_instances
            WHERE world_seed=? AND node_name=? AND epoch=?''', (seed, node, epoch)).fetchone()


def pin(seed, node, epoch, version, definition, evidence):
    with db.transaction() as conn:
        conn.execute('''INSERT INTO puzzle_instances
            (world_seed,node_name,epoch,definition_version,definition,evidence)
            VALUES (?,?,?,?,?,?) ON CONFLICT(world_seed,node_name,epoch) DO NOTHING''',
            (seed, node, epoch, version, json.dumps(definition), json.dumps(evidence)))
        return read(seed, node, epoch)
