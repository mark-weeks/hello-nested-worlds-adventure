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

# Authored clauses are selected by the actual delta, not the whole operation.
# A compound action can change only one field when another is already at its cap.
_OBSERVED = {
    'shear': {'stability': 'The membranes slip out of phase; reality frays a little further.'},
    'quicken': {'hum_period_years': 'The membrane hum quickens; its cycles turn faster.'},
    'linger': {'hum_period_years': 'The membrane hum lengthens; longer intervals of stillness open.'},
    'condense': {'dark_matter_ratio': 'Dark matter thickens; the balance of the vacuum shifts.'},
    'rarefy': {'dark_matter_ratio': 'Dark matter thins; the unseen fabric loosens.'},
    'modulate': {'vacuum_hum_hz': 'The vacuum hum rises in pitch.'},
    'scatter': {'star_density': 'The stars drift apart; open sky widens between them.'},
    'spiral': {'shape': 'The stars gather into spiral arms.'},
    'accelerate': {'drift_kmps': 'The drift through intergalactic space quickens.'},
    'incline': {'ecliptic_tilt_deg': 'The orbital plane tilts; its alignment loosens.'},
    'gather': {'asteroid_belt': 'Drifting debris gathers into an asteroid belt.'},
    'disperse': {'asteroid_belt': 'The belt disperses; its debris thins along the orbits.'},
    'rewild': {'biome': 'Vegetation reclaims the surface; the biome turns to forest.'},
    'hasten': {'day_length_hours': 'The world turns faster; the day shortens.'},
    'slow': {'day_length_hours': 'The world turns slower; the day lengthens.'},
    'cultivate': {'terrain': 'The land settles into terraces.', 'danger_level': 'Less danger lies exposed.'},
    'overgrow': {'terrain': 'Growth runs wild over the terrain.', 'danger_level': 'The danger rises.'},
    'channel': {'terrain': 'Channels cut through the land.', 'weather': 'A ground fog settles.'},
    'illuminate': {'lighting': 'Light fills the room; its concealment is gone.'},
    'shade': {'lighting': 'The room dims; shelter from the light returns.'},
    'ventilate': {'air': 'The enclosed air clears to a cool, mineral draft.'},
    'engrave': {'surface': 'A pattern is cut into the surface.'},
    'fracture': {'condition': 'The material deteriorates.', 'fractured': 'The structure breaks open; its inside shows.'},
    'polish': {'surface': 'The surface turns mirror smooth; its previous finish is gone.'},
    'cleave': {'bond_count': 'A bond breaks.', 'reactive': 'The loosened structure turns reactive.'},
    'fold': {'geometry': 'The structure folds into a sheet.'},
    'branch': {'geometry': 'The molecule reshapes into a branching chain.', 'reactive': 'The structure turns reactive.'},
    'relax': {'ionized': 'An electron returns; the shell is neutral again.', 'resonance_nm': 'Its resonance shifts redward.'},
    'ionize': {'ionized': 'An electron is stripped away; the atom is ionized.'},
    'neutralize': {'ionized': 'An electron returns; the shell is neutral again.'},
    'superpose': {'spin': 'Both spin possibilities reopen.', 'coherence': 'Coherence loosens.'},
    'flip': {'spin': 'The definite spin reverses.'},
    'dephase': {'coherence': 'The phase relationship scatters; coherence loosens.'},
}

# These retained verbs also have compound effects. Their original notes can
# claim a numeric change when only a flag changed. Correct v3's voice only;
# the retained v1/v2 physics and their accepted commitments stay unchanged.
_VERB_OBSERVED = {
    'kindle': {'star_density': 'New stars catch along the dust lanes.', 'kindled': 'Kindling takes hold here.'},
    'align': {'ecliptic_tilt_deg': 'The ecliptic flattens.', 'aligned': 'The orbits hold their alignment.'},
    'ward': {'danger_level': 'The danger recedes.', 'warded': 'Ward lines settle along the boundary.'},
    'catalyze': {'bond_count': 'A new bond snaps into place.', 'catalyzed': 'The lattice carries the reaction.'},
    'excite': {'ionized': 'An electron is stripped away.', 'resonance_nm': 'The atom brightens; its resonance shifts blueward.'},
}


def _observed_note(op, changed, original, properties):
    clauses = _OBSERVED.get(op, _VERB_OBSERVED.get(op))
    if clauses is None:
        return original
    note = ' '.join(line for key, line in clauses.items() if key in changed)
    if op in _VERB_OBSERVED:
        aspect = properties.get('aspect')
        if isinstance(aspect, str) and ';' in aspect:
            clause = aspect.split(';')[0].strip().rstrip('.')
            if clause:
                note += f' {clause[0].upper()}{clause[1:]}.'
    return note


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
                             'note': _observed_note(step['op'], result['changed'], result['notes'][0], props)})
    changed = {k: v for k, v in props.items() if properties.get(k) != v}
    signal = {'strength': strength if changed else 0, 'coherent': True,
              'motif': v2.digest([plan['level'], plan['steps']])}
    return changed, signal, outcomes


def describe(outcome):
    """The world's voice for one settled step. Property literals never reach a reader."""
    if outcome.get('outcome') != 'materialized' or not outcome.get('changed'):
        return _NOTHING
    return outcome.get('note') or 'A material change settles here.'


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
