"""Emit reproducible design-study samples without touching an existing world.

Each after-state is an isolated v3 settlement of an explicit action, not a player
forecast. The browser study is review evidence, never exposed in the play UI.
"""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def samples():
    import persistence
    from multiverse import store, senses, interventions_v3
    original = persistence._DB_PATH
    result = []
    try:
        with tempfile.TemporaryDirectory(prefix='enfolded-visual-study-') as directory:
            persistence._DB_PATH = Path(directory) / 'worlds.db'
            for name, operation in [
                ('Emberlit Orchard Terraces-111111', 'channel'),
                ('Broken Ember Gallery-1111111', 'illuminate'),
                ('Elder River Instrument-11111111', 'fracture'),
                ('Amber Ember Mechanism-11111112', 'engrave'),
                ('Distant River Chain-111111111', 'branch'),
            ]:
                node = store.resolve_node_by_name(382, name)
                def snapshot():
                    return {'name': node.name, 'level': node.level,
                            'properties': deepcopy(node.properties), 'senses': senses.describe(node)}
                before = snapshot()
                delta, _, _ = interventions_v3.settle(node.properties,
                    interventions_v3.attempt([{'op': operation}], node.level, node.name))
                node.properties.update(delta)
                result.append({'operation': operation, 'before': before, 'after': snapshot()})
    finally:
        persistence._DB_PATH = original
    return result


if __name__ == '__main__':
    print(json.dumps(samples(), indent=2))
