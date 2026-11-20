"""The released signal: a bounded authored situation, not a generic quest engine."""
from multiverse import store
from puzzles.gates import sealing_room

SLUG = 'the-released-signal'
VERSION = 1
WINDOW_SECONDS = 60
STEP_SECONDS = 20
KEEPER = 'Tessera'
# The authored places, by the name world 382 is born with under the current
# generator. `ADDRESSES` is where each one stands; `definition` resolves by
# address, so a world 382 born under an earlier generator version, whose
# stored names differ, serves its own stored names (ADR-041).
NODES = {
    'region': 'Emberlit Orchard Terraces',
    'gallery': 'Broken Ember Gallery',
    'instrument': 'Elder River Instrument',
    'chain': 'Distant River Chain',
    'fold': 'Elder Lantern Fold',
    'regulator': 'Amber Ember Mechanism',
    'structure': 'Emberlit Crown Structure',
    'alcove': 'Mossbound Orchard Alcove',
}
ADDRESSES = {
    'region': '111111',
    'gallery': '1111111',
    'instrument': '11111111',
    'chain': '111111111',
    'fold': '111111112',
    'regulator': '11111112',
    'structure': '111111121',
    'alcove': '1111112',
}
CLUES = {
    'region': 'The orchard hums whenever the gallery brightens. Holding the signal inside the gallery would calm these terraces; releasing it would carry it farther, and make the ground less settled.',
    'gallery': 'Tessera tends the gallery. “The instrument keeps a signal under my care. I can hold it here, or let the orchard hear it. Either choice will change what I can protect.”',
    'instrument': 'Under the instrument is an unsigned inscription: “A signal held is a signal kept from someone.” Its maker is unknown.',
    'chain': 'The chain carries the pulse from the instrument toward the gallery. A held signal repeats locally; a released signal continues toward the terraces.',
    'fold': 'A folded echo waits here. Tessera promises to mark what the signal becomes, whichever route you choose. The mark will survive your departure.',
    'regulator': 'The regulator gives the keeper control over the signal. Preserving its setting keeps the gallery quiet. Releasing its hold gives up that control; the orchard receives the pulse.',
    'structure': 'At this scale, the regulator is a set of bonds. The choice concerns the arrangement they sustain, not whether every bond is good or bad.',
    'alcove': 'The sealed alcove carries the same pulse. Its ordinary seal remains in force; opening it is optional and never required to decide the signal’s route.',
}
BRANCHES = {
    'preserve': {'label': 'Keep the signal under Tessera’s care',
        'benefit': 'The gallery steadies and the orchard becomes calmer.',
        'cost': 'The signal stays enclosed. Those beyond the gallery still cannot hear it.'},
    'release': {'label': 'Release the signal into the orchard',
        'benefit': 'The signal travels beyond the keeper’s control.',
        'cost': 'The gallery loses its steady light and the terraces become more dangerous.'},
}


def definition(seed):
    if seed != 382:
        raise ValueError('This authored situation belongs to world 382.')
    nodes = {}
    for role, address in ADDRESSES.items():
        node = store.node_at(seed, address)
        if node is None:
            raise ValueError(f'The authored place for {role} is unavailable.')
        if role != 'alcove' and sealing_room(node) is not None:
            raise ValueError('A required clue would be behind a seal.')
        nodes[role] = node.name
    return {'version': VERSION, 'title': 'The signal in the gallery', 'nodes': nodes,
            'clues': CLUES, 'branches': BRANCHES, 'keeper': KEEPER,
            'window_seconds': WINDOW_SECONDS, 'step_seconds': STEP_SECONDS,
            'entry': nodes['region'], 'required_clues': ['instrument', 'regulator'],
            'promise': 'Tessera will leave a lasting mark in the Elder Lantern Fold after the signal reaches the terraces.'}
