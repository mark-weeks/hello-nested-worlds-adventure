"""Commit an attempt; discover material results under version 3 rules.

The v2 vocabulary/rules are retained dependencies, never current model output.
No state is simulated until settlement. Each step meets the state left by the
previous step; a moot step does not cancel independent, executable steps.
"""
from copy import deepcopy

from multiverse import interventions_v2 as v2

VERSION = 3
normalize_steps = v2.normalize_steps
parse_score = v2.parse_score
read_state = v2.read_state


# Describe only the attempted physical operation. Rules and present conditions
# remain learnable; these invitations make no promise about a particular result.
_ATTEMPTS = {
    'attune': 'Bring the membranes into phase', 'shear': 'Slip the membranes out of phase',
    'quicken': 'Quicken the membrane hum', 'linger': 'Slow the membrane hum',
    'calibrate': 'Balance the physical constants', 'condense': 'Concentrate dark matter',
    'rarefy': 'Thin the dark-matter fabric', 'modulate': 'Raise the vacuum hum',
    'kindle': 'Ignite stars along the dust lanes', 'scatter': 'Spread the stellar distribution',
    'spiral': 'Draw stars into spiral arms', 'accelerate': 'Accelerate the galactic drift',
    'align': 'Align the orbital plane', 'incline': 'Tilt the orbital plane',
    'gather': 'Gather orbital debris into a belt', 'disperse': 'Disperse the asteroid belt',
    'seed': 'Nurture life on this planet', 'rewild': 'Rewild the surface',
    'hasten': 'Speed up the planetary rotation', 'slow': 'Ease the planetary rotation',
    'ward': 'Ward this region against danger', 'cultivate': 'Work the land into terraces',
    'overgrow': 'Encourage wild growth across the terrain', 'channel': 'Cut waterways through the land',
    'inscribe': 'Inscribe a mark in this room', 'illuminate': 'Light this room',
    'shade': 'Shade this room', 'ventilate': 'Ventilate the enclosed air',
    'mend': 'Repair this object', 'engrave': 'Cut a pattern into this surface',
    'fracture': 'Break the structure open', 'polish': 'Polish this surface',
    'catalyze': 'Coax a new bond into the lattice', 'cleave': 'Break a molecular bond',
    'fold': 'Fold the molecular structure into a sheet', 'branch': 'Reshape the molecule into a branching chain',
    'excite': 'Excite the electron shell', 'relax': 'Relax the electron shell',
    'ionize': 'Strip an electron from the atom', 'neutralize': 'Return an electron to the ionized shell',
    'observe': 'Observe the particle spin', 'superpose': 'Reopen both spin possibilities',
    'flip': 'Reverse a definite spin', 'dephase': 'Scatter the phase relationship',
}

_NOTHING = 'No new material change remains.'

# What a settled step leaves behind, in the world's voice. Verb operators carry
# their own authored result line from apply_verb (with the node's aspect
# clause); the declarative operators are voiced here. Never a property literal.
_OBSERVED = {
    'shear': 'The membranes slip out of phase; reality frays a little further.',
    'quicken': 'The membrane hum quickens; its cycles turn faster.',
    'linger': 'The membrane hum lengthens; longer intervals of stillness open.',
    'condense': 'Dark matter thickens; the balance of the vacuum shifts.',
    'rarefy': 'Dark matter thins; the unseen fabric loosens.',
    'modulate': 'The vacuum hum rises in pitch.',
    'scatter': 'The stars drift apart; open sky widens between them.',
    'spiral': 'The stars gather into spiral arms.',
    'accelerate': 'The drift through intergalactic space quickens.',
    'incline': 'The orbital plane tilts; its alignment loosens.',
    'gather': 'Drifting debris gathers into an asteroid belt.',
    'disperse': 'The belt disperses; its debris thins along the orbits.',
    'rewild': 'Vegetation reclaims the surface; the biome turns to forest.',
    'hasten': 'The world turns faster; the day shortens.',
    'slow': 'The world turns slower; the day lengthens.',
    'cultivate': 'The land settles into terraces; less danger lies exposed.',
    'overgrow': 'Growth runs wild over the terrain; the danger rises.',
    'channel': 'Channels cut through the land; waterways carry a ground fog.',
    'illuminate': 'Light fills the room; its concealment is gone.',
    'shade': 'The room dims; shelter from the light returns.',
    'ventilate': 'The enclosed air clears to a cool, mineral draft.',
    'engrave': 'A pattern is cut into the surface; the mark will outlast whoever made it.',
    'fracture': 'The structure breaks open; its inside shows at the cost of its condition.',
    'polish': 'The surface turns mirror smooth; its previous finish is gone.',
    'cleave': 'A bond breaks; the loosened structure turns reactive.',
    'fold': 'The structure folds into a sheet; its bonds hold.',
    'branch': 'The molecule reshapes into a branching chain.',
    'relax': 'The shell settles; its resonance shifts redward.',
    'ionize': 'An electron is stripped away; the atom is ionized.',
    'neutralize': 'An electron returns; the shell is neutral again.',
    'superpose': 'Both spin possibilities reopen; coherence loosens.',
    'flip': 'The definite spin reverses.',
    'dephase': 'The phase relationship scatters; coherence loosens.',
}


def vocabulary(level):
    return {op: {**info, 'description': 'Attempt to ' + _ATTEMPTS[op][0].lower() + _ATTEMPTS[op][1:] + '.'}
            for op, info in v2.vocabulary(level).items()}


def attempt(steps, level, token):
    steps = normalize_steps(steps, level)
    return {'steps': steps, 'level': level, 'token': token,
            'summary': ' → '.join(v2.OPERATORS[s['op']]['label'] for s in steps)}


def settle(properties, plan):
    props = deepcopy(properties)
    outcomes, strength = [], 0
    for step in normalize_steps(plan['steps'], plan['level']):
        try:
            result = v2.simulate(props, [step], plan['level'], plan['token'])
        except ValueError:
            outcomes.append({'op': step['op'], 'changed': {}, 'outcome': 'no_material_change', 'note': _NOTHING})
        else:
            props.update(result['changed'])
            strength += result['signal']['strength']
            outcomes.append({'op': step['op'], 'changed': result['changed'], 'outcome': 'materialized',
                             'note': _OBSERVED.get(step['op'], result['notes'][0])})
    changed = {k: v for k, v in props.items() if properties.get(k) != v}
    signal = {'strength': strength if changed else 0, 'coherent': True,
              'motif': v2.digest([plan['level'], plan['steps']])}
    return changed, signal, outcomes


def describe(outcome):
    """The world's voice for one settled step. Property literals never reach a reader."""
    if outcome.get('outcome') != 'materialized' or not outcome.get('changed'):
        return _NOTHING
    return outcome.get('note') or _OBSERVED.get(outcome.get('op')) or 'A material change settles here.'


def receive(properties, signal):
    # One step from the preceding OBSERVED wave. A receiver's resonator can
    # absorb energy before the remainder continues; never reuse a forecast.
    # The remainder feeds the next hop whether or not this receiver's own
    # state moved (ADR-028): a saturated echo records no material change
    # here, yet the wave that reached it still travels on.
    received, flavor = v2.receive(properties, signal, 1)
    state = received.get('acoustic_resonance', received.get('resonance', {}))
    changed = {key: value for key, value in received.items() if properties.get(key) != value}
    outgoing = {**signal, 'strength': state.get('last_wave', 0)}
    if not changed:
        flavor = ('The arriving disturbance leaves no new material change here; what remains of it travels on.'
                  if outgoing['strength'] else 'The arriving disturbance leaves no new material change.')
    return changed, outgoing, flavor
