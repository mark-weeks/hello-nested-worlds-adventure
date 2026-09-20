"""Scale-native action spectra, v2. Retain these semantics for accepted work.

Choices describe physical interventions by the acting player. They never assign
motives, decisions, ownership, or actions to another inhabitant.
"""
from copy import deepcopy
from types import SimpleNamespace
import re

from multiverse import interventions_v1 as legacy
from multiverse.verbs import VERBS, apply_verb

VERSION = 2
MAX_STEPS = 4
digest = legacy.digest
def read_state(properties):
    if isinstance(properties.get('resonance'), str):
        return legacy.read_state({**properties, 'resonance': properties.get('acoustic_resonance', {})})
    return legacy.read_state(properties)

# Declarative, bounded physical changes. No generator, topology or identity writes.
# Tuple: verb, scale, description, changes, outward/quieting impulse.
EXTRA = [
    ('shear', 'Multiverse', 'Slip the membranes out of phase; make reality less stable.', {'stability': ('cycle', ['stable', 'fraying', 'collapsing'])}, 2),
    ('quicken', 'Multiverse', 'Shorten the membrane hum; let its cycles turn faster.', {'hum_period_years': ('multiply', .8, .1, 2000)}, 1),
    ('linger', 'Multiverse', 'Lengthen the membrane hum; open longer intervals of stillness.', {'hum_period_years': ('multiply', 1.25, .1, 2000)}, -1),
    ('condense', 'Universe', 'Increase the dark-matter share, changing the balance of the vacuum.', {'dark_matter_ratio': ('add', .05, 0, 1)}, 1),
    ('rarefy', 'Universe', 'Reduce the dark-matter share; loosen the unseen fabric.', {'dark_matter_ratio': ('add', -.05, 0, 1)}, -1),
    ('modulate', 'Universe', 'Raise the frequency of the vacuum hum.', {'vacuum_hum_hz': ('multiply', 1.2, .1, 100)}, 1),
    ('scatter', 'Galaxy', 'Spread the stars apart; trade density for open sky.', {'star_density': ('multiply', .9, 1, 999)}, -2),
    ('spiral', 'Galaxy', 'Draw the stellar distribution into spiral arms.', {'shape': 'spiral'}, 1),
    ('accelerate', 'Galaxy', 'Increase the drift through intergalactic space.', {'drift_kmps': ('multiply', 1.1, 1, 2000)}, 2),
    ('incline', 'Planetary System', 'Tilt the orbital plane; loosen its alignment.', {'ecliptic_tilt_deg': ('add', 3, 0, 90)}, 2),
    ('gather', 'Planetary System', 'Gather drifting debris into an asteroid belt.', {'asteroid_belt': True}, 1),
    ('disperse', 'Planetary System', 'Disperse the belt; leave less debris in concentrated orbits.', {'asteroid_belt': False}, -1),
    ('rewild', 'Planet', 'Let vegetation reclaim the surface, reshaping the biome.', {'biome': 'forest'}, 1),
    ('hasten', 'Planet', 'Shorten the day by increasing the rotation rate.', {'day_length_hours': ('multiply', .9, 2, 240)}, 2),
    ('slow', 'Planet', 'Lengthen the day by easing the rotation rate.', {'day_length_hours': ('multiply', 1.1, 2, 240)}, -1),
    ('cultivate', 'Region', 'Work the land into terraces; reduce exposed danger.', {'terrain': 'terraced', 'danger_level': ('add', -1, 1, 10)}, -1),
    ('overgrow', 'Region', 'Let the growth run wild; cover the terrain and increase its danger.', {'terrain': 'overgrown', 'danger_level': ('add', 1, 1, 10)}, 2),
    ('channel', 'Region', 'Cut channels through the land; turn its terrain into waterways.', {'terrain': 'waterways', 'weather': 'ground fog'}, 1),
    ('illuminate', 'Room', 'Bring light into the room; give up its concealment.', {'lighting': 'bright'}, 1),
    ('shade', 'Room', 'Dim the room; trade visibility for shelter from light.', {'lighting': 'dim'}, -1),
    ('ventilate', 'Room', 'Clear the enclosed air, opening the room to a cool draft.', {'air': 'cool and mineral'}, -1),
    ('engrave', 'Object', 'Cut a pattern into the surface; a physical mark survives your departure.', {'surface': 'engraved'}, 1),
    ('fracture', 'Object', 'Break the structure open; expose its inside at the cost of its condition.', {'condition': ('cycle', ['pristine', 'worn', 'damaged', 'corrupted']), 'fractured': True}, 2),
    ('polish', 'Object', 'Make the surface reflective, removing its previous finish.', {'surface': 'mirror smooth'}, -1),
    ('cleave', 'Molecule', 'Break a bond; loosen the structure and make it reactive.', {'bond_count': ('add', -1, 1, 12), 'reactive': True}, 2),
    ('fold', 'Molecule', 'Fold the structure into a sheet; its bonds remain intact.', {'geometry': 'folded sheet'}, -1),
    ('branch', 'Molecule', 'Reshape the molecule into a branching chain.', {'geometry': 'branched chain', 'reactive': True}, 1),
    ('relax', 'Atom', 'Let the shell settle; shift its resonance redward.', {'ionized': False, 'resonance_nm': ('multiply', 1.05, 180, 780)}, -1),
    ('ionize', 'Atom', 'Strip an electron from the atom, leaving it ionized.', {'ionized': True}, 2),
    ('neutralize', 'Atom', 'Return an electron to the ionized shell.', {'ionized': False}, -1),
    ('superpose', 'SubatomicParticle', 'Reopen both spin possibilities, reducing coherence.', {'spin': 'superposed', 'coherence': ('multiply', .7, .001, .999)}, -1),
    ('flip', 'SubatomicParticle', 'Reverse a definite spin; a superposition stays unresolved.', {'spin': ('flip', {'up': 'down', 'down': 'up'})}, 1),
    ('dephase', 'SubatomicParticle', 'Scatter the phase relationship; loosen coherence.', {'coherence': ('multiply', .5, .001, .999)}, -2),
]
OPERATORS = {v.name: {'label': v.name.capitalize(), 'level': v.level, 'description': v.tagline} for v in VERBS.values()}
OPERATORS.update({name: {'label': name.capitalize(), 'level': level, 'description': description} for name, level, description, _, _ in EXTRA})
_RULES = {row[0]: row for row in EXTRA}


def vocabulary(level):
    return {k: v for k, v in OPERATORS.items() if v['level'] == level}


def normalize_steps(steps, level=None):
    if not isinstance(steps, list) or not 1 <= len(steps) <= MAX_STEPS:
        raise ValueError('Choose between one and four actions.')
    result = []
    for step in steps:
        if not isinstance(step, dict) or set(step) - {'op', 'amount'}:
            raise ValueError('Choose an action this place supports.')
        op = step.get('op')
        if not isinstance(op, str) or op not in OPERATORS:
            raise ValueError('That action has no dependable consequence here yet.')
        if level and OPERATORS[op]['level'] != level:
            raise ValueError(f'{op.capitalize()} does not belong at {level} scale.')
        amount = step.get('amount', 1)
        if type(amount) is not int or amount != 1:
            raise ValueError('Each step performs one action.')
        result.append({'op': op, 'amount': 1})
    return result


def parse_score(text, level):
    if not isinstance(text, str) or not 1 <= len(text.strip()) <= 600:
        raise ValueError('Describe your intention in at most 600 characters.')
    parts = re.split(r'\s*(?:,|;|→|\bthen\b)\s*', text.strip().lower().rstrip('.'))
    if any(part not in vocabulary(level) for part in parts):
        return None  # Never infer a negated or ambiguous instruction.
    return normalize_steps([{'op': part} for part in parts], level)


def _effect(properties, rule):
    delta = {}
    for key, spec in rule.items():
        old = properties.get(key)
        if not isinstance(spec, tuple):
            new = spec
        elif spec[0] == 'cycle':
            states = spec[1]
            if old not in states:
                continue
            new = states[min(states.index(old) + 1, len(states) - 1)]
        elif spec[0] == 'flip':
            new = spec[1].get(old, old)
        elif type(old) in (int, float):
            new = old + spec[1] if spec[0] == 'add' else old * spec[1]
            new = min(spec[3], max(spec[2], new))
            new = round(new) if type(old) is int else round(new, 3)
        else:
            continue
        if new != old:
            delta[key] = new
    return delta


def simulate(properties, steps, level, token=''):
    steps = normalize_steps(steps, level)
    props = deepcopy(properties)
    notes, wave = [], 0
    for step in steps:
        op = step['op']
        if op in _RULES:
            _, _, description, rules, impulse = _RULES[op]
            delta = _effect(props, rules)
            note = description
        else:
            node = SimpleNamespace(level=level, properties=deepcopy(props))
            delta, note = apply_verb(node, VERBS[level], token)
            impulse = -1 if op in ('attune', 'calibrate', 'align', 'ward', 'mend', 'observe') else 1
        if not delta:
            raise ValueError(f'{op.capitalize()} would leave this place as it is. Try a different action or order.')
        props.update(delta)
        notes.append(note)
        wave += impulse
    changed = {k: v for k, v in props.items() if properties.get(k) != v}
    if not changed:
        raise ValueError('These actions cancel one another. Choose a consequence you want to leave.')
    # Do not overwrite a planetary system's born orbital resonance (a string).
    # Material property changes are enough to direct its scene and sound.
    return {'steps': steps, 'changed': changed, 'notes': notes,
            'signal': {'strength': wave, 'coherent': True, 'motif': digest([level, steps])},
            'summary': ' → '.join(OPERATORS[s['op']]['label'] for s in steps),
            'level': level, 'token': token}


def receive(properties, signal, hop):
    orbital = isinstance(properties.get('resonance'), str)
    received = {**properties, 'resonance': read_state(properties)} if orbital else properties
    delta, flavor = legacy.receive(received, signal, hop)
    if orbital:
        delta['acoustic_resonance'] = delta.pop('resonance')  # The orbital ratio keeps its distinct meaning.
    return delta, flavor


def choices(properties, level, token=''):
    result = []
    for op, info in vocabulary(level).items():
        try:
            simulate(properties, [{'op': op}], level, token)
            reason = None
        except ValueError as exc:
            reason = str(exc)
        result.append({'op': op, **info, 'available': reason is None, 'reason': reason})
    return result
