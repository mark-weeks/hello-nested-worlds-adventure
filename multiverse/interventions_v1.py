"""Retained v1 semantics for accepted promises. Pure planning; no model can write world state."""
from copy import deepcopy
import hashlib
import json
import math
import re

VERSION = 1
MAX_STEPS = 4
OPERATORS = {
    'weave': {'label': 'Weave', 'description': 'Spend one stored pulse to build a resonator. Future releases carry a coherent memory.'},
    'charge': {'label': 'Charge', 'description': 'Gather ambient energy into this place. A resonator holds twice as much.'},
    'invert': {'label': 'Invert', 'description': 'Reverse the polarity. A returning wave quiets and darkens; an outward wave brightens and unsettles.'},
    'release': {'label': 'Release', 'description': 'Send stored energy through the enclosing scales. A woven source leaves a lasting harmonic memory.'},
    'dampen': {'label': 'Dampen', 'description': 'Spend stored energy to quiet this place. Less energy remains for reaching others.'},
    'unweave': {'label': 'Unweave', 'description': 'Dismantle a resonator, freeing its stored pulse into an untamed wave. The resonator is lost.'},
}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()[:24]


def _number(value, default=0):
    return float(value) if type(value) in (int, float) and math.isfinite(value) else default


def read_state(properties):
    value = properties.get('resonance', {})
    value = value if isinstance(value, dict) else {}
    return {
        'woven': value.get('woven') is True,
        'energy': max(0, min(12, _number(value.get('energy'), 1))),
        'polarity': -1 if value.get('polarity') == -1 else 1,
        'echo': max(-12, min(12, _number(value.get('echo')))),
        'memory': value.get('memory', '') if isinstance(value.get('memory', ''), str) else '',
        'last_wave': max(-12, min(12, _number(value.get('last_wave')))),
        'scar': max(0, min(8, _number(value.get('scar')))),
    }


def normalize_steps(steps):
    if not isinstance(steps, list) or not 1 <= len(steps) <= MAX_STEPS:
        raise ValueError('Compose between one and four interventions.')
    result = []
    for step in steps:
        if not isinstance(step, dict) or set(step) - {'op', 'amount'}:
            raise ValueError('Use an intervention from the shared vocabulary.')
        op = step.get('op')
        if not isinstance(op, str) or op not in OPERATORS:
            raise ValueError('That intervention has no dependable consequence yet.')
        amount = step.get('amount', 1)
        if type(amount) is not int or not 1 <= amount <= 3:
            raise ValueError('Gather one, two or three pulses at a time.')
        if op != 'charge' and amount != 1:
            raise ValueError('Only charging takes a pulse count.')
        result.append({'op': op, 'amount': amount})
    return result


def parse_score(text):
    """An explicit notation works offline. Never infer a negated intention."""
    if not isinstance(text, str) or not 1 <= len(text.strip()) <= 600:
        raise ValueError('Describe your intention in at most 600 characters.')
    parts = re.split(r'\s*(?:,|;|→|\bthen\b)\s*', text.strip().lower().rstrip('.'))
    steps = []
    for part in parts:
        match = re.fullmatch(r'(weave|charge|invert|release|dampen|unweave)(?:\s+([1-3]))?', part)
        if not match:
            return None
        steps.append({'op': match[1], 'amount': int(match[2] or 1)})
    return normalize_steps(steps)


def simulate(properties, steps):
    steps = normalize_steps(steps)
    state = read_state(properties)
    initial = deepcopy(state)
    wave = 0.0
    coherent = False
    notes = []
    for step in steps:
        op, amount = step['op'], step['amount']
        if op == 'weave':
            if state['woven']:
                raise ValueError('A resonator already holds here. Use it or unweave it first.')
            if state['energy'] < 1:
                raise ValueError('Gather a pulse before weaving a resonator.')
            state['energy'] -= 1
            state['woven'] = True
            notes.append('A resonator will be woven here; one pulse becomes its structure.')
        elif op == 'charge':
            cap = 12 if state['woven'] else 6
            if state['energy'] + amount > cap:
                raise ValueError(f'This place can hold {cap} pulses. Release or dampen before gathering more.')
            state['energy'] += amount
            notes.append(f'{amount} ambient pulses will gather here.')
        elif op == 'invert':
            state['polarity'] *= -1
            notes.append('The next release will ' + ('return inward, quieting and darkening.' if state['polarity'] < 0 else 'open outward, brightening and unsettling.'))
        elif op == 'release':
            if state['energy'] <= 0:
                raise ValueError('There is no stored pulse to release. Gather energy first.')
            wave += state['energy'] * state['polarity']
            coherent = coherent or state['woven']
            state['energy'] = 0
            notes.append('The stored pulse will travel into the enclosing places' + (', carrying the resonator’s memory.' if state['woven'] else ' as an untamed wave.'))
        elif op == 'dampen':
            if state['energy'] <= 0 and state['echo'] == 0:
                raise ValueError('This place is already quiet.')
            state['energy'] = max(0, state['energy'] - 2)
            state['echo'] = round(state['echo'] * .5, 3)
            notes.append('The pulse will soften; some energy will become silence.')
        else:
            if not state['woven']:
                raise ValueError('There is no resonator here to dismantle.')
            wave += (state['energy'] + 1) * state['polarity']
            state['energy'] = 0
            state['woven'] = False
            state['scar'] = min(8, state['scar'] + 1)
            notes.append('The resonator will come apart. Its energy will travel, leaving a visible seam.')
    wave = round(max(-12, min(12, wave)), 3)
    if wave:
        state['last_wave'] = wave
        state['echo'] = round(max(-12, min(12, state['echo'] + wave * .25)), 3)
        if coherent:
            state['memory'] = digest(steps)
    if state == initial:
        raise ValueError('This sequence leaves the place unchanged. Give it a consequence.')
    return {'steps': steps, 'state': state, 'notes': notes,
            'signal': {'strength': wave, 'coherent': coherent, 'motif': digest(steps)},
            'summary': ' → '.join(OPERATORS[s['op']]['label'] + (f" {s['amount']}" if s['op'] == 'charge' else '') for s in steps)}


def receive(properties, signal, hop):
    """A received wave encounters CURRENT conditions; its source is immutable."""
    state = read_state(properties)
    amplitude = round(signal['strength'] * (.65 ** hop), 3)
    # A built resonator catches some energy, an actual compositional interaction.
    caught = min(abs(amplitude) * .5, max(0, 12 - state['energy'])) if state['woven'] else 0
    state['energy'] = round(state['energy'] + caught, 3)
    amplitude = round(math.copysign(max(0, abs(amplitude) - caught), amplitude), 3)
    state['echo'] = round(max(-12, min(12, state['echo'] + amplitude)), 3)
    state['last_wave'] = amplitude
    if signal['coherent']:
        state['memory'] = signal['motif']
    delta = {'resonance': state}
    danger = properties.get('danger_level')
    if type(danger) is int and abs(amplitude) >= .5:
        delta['danger_level'] = max(1, min(10, danger + (1 if amplitude > 0 else -1)))
    direction = 'opens outward' if amplitude > 0 else 'turns inward'
    text = 'The arriving wave ' + direction + ('. A woven resonator catches part of its energy.' if caught else '.')
    if signal['coherent']:
        text += ' Its source’s harmonic memory remains here.'
    return delta, text


def suggestions(properties):
    state = read_state(properties)
    candidates = [
        ('A memory that can travel', [{'op': 'charge'}, {'op': 'weave'}, {'op': 'charge', 'amount': 2}, {'op': 'release'}]),
        ('Let the uncontained pulse travel', [{'op': 'charge', 'amount': 2}, {'op': 'release'}]),
        ('Send a quieter answer', [{'op': 'charge'}, {'op': 'invert'}, {'op': 'release'}]),
    ]
    if state['woven']:
        candidates[0] = ('Pass on the resonator’s memory', [{'op': 'charge'}, {'op': 'release'}])
        candidates.append(('Free the bound energy', [{'op': 'unweave'}]))
    results = []
    for title, steps in candidates:
        try:
            simulate(properties, steps)
        except ValueError:
            continue
        results.append({'title': title, 'steps': normalize_steps(steps)})
    if not results:
        results.append({'title': 'Make room for a different future', 'steps': [{'op': 'dampen', 'amount': 1}]})
    return results
