"""Read-only descriptions of current substance, including retained material traces.

The born aspect stays intact. No model call, history write, actor inference or
forecast is needed to describe the state already served to every visitor.
"""
import math


def describe_place(level, properties, resonance):
    p = properties

    def text(key):
        value = p.get(key)
        return value.strip() if isinstance(value, str) else ''

    def number(key):
        value = p.get(key)
        return value if type(value) in (int, float) and math.isfinite(value) else None

    def sentence(value):
        value = value.strip()
        return value[:1].upper() + value[1:].rstrip('.; ') + '.' if value else ''

    current = []
    if level == 'Multiverse':
        if text('stability'):
            current.append(f"the membranes are {text('stability')}")
        if number('hum_period_years') is not None:
            current.append(f"their hum cycles every {number('hum_period_years'):g} years")
    elif level == 'Universe':
        if text('light_temper'):
            current.append(f"the light is {text('light_temper')}")
        if number('vacuum_hum_hz') is not None:
            current.append(f"the vacuum hums at {number('vacuum_hum_hz'):g} Hz")
        if number('dark_matter_ratio') is not None:
            current.append(f"dark matter holds {number('dark_matter_ratio') * 100:g}% of its balance")
    elif level == 'Galaxy':
        if text('shape'):
            current.append(f"the stars hold a {text('shape')} form")
        if text('dust'):
            current.append(f"{text('dust')} dust lies between them")
        if number('star_density') is not None:
            current.append(f"its stellar density is {number('star_density'):g}")
        if number('drift_kmps') is not None:
            current.append(f"it drifts at {number('drift_kmps'):g} km/s")
    elif level == 'Planetary System':
        if number('ecliptic_tilt_deg') is not None:
            current.append(f"the orbital plane tilts by {number('ecliptic_tilt_deg'):g} degrees")
        if type(p.get('asteroid_belt')) is bool:
            current.append('an asteroid belt circles here' if p['asteroid_belt'] else 'there is no concentrated asteroid belt')
    elif level == 'Planet':
        if text('biome'):
            current.append(f"the surface carries a {text('biome')} biome")
        if number('day_length_hours') is not None:
            current.append(f"a day lasts {number('day_length_hours'):g} hours")
        if number('population') is not None:
            current.append(f"{number('population'):,.0f} inhabitants live here")
    elif level == 'Region':
        if text('terrain'):
            current.append(f"the terrain is {text('terrain')}")
        if text('weather'):
            current.append(f"the weather brings {text('weather')}")
        if number('danger_level') is not None:
            degree = max(1, min(10, round(number('danger_level'))))
            danger = ('barely perceptible', 'faint', 'low', 'noticeable', 'unsettling',
                      'substantial', 'pronounced', 'severe', 'pervasive', 'overwhelming')[degree - 1]
            current.append(f'danger is {danger}')
    elif level == 'Room':
        if text('lighting'):
            current.append('the room is dark' if text('lighting') == 'dark' else f"the light is {text('lighting')}")
        if text('air'):
            current.append(f"the air is {text('air')}")
    elif level == 'Object':
        if text('condition'):
            current.append(f"its {text('material') or 'substance'} is {text('condition')}")
        if text('surface'):
            current.append(f"the surface is {text('surface')}")
    elif level == 'Molecule':
        if text('geometry'):
            current.append(f"its geometry is {text('geometry')}")
        if number('bond_count') is not None:
            count = number('bond_count')
            current.append(f"{count:g} {'bond holds' if count == 1 else 'bonds hold'} it together")
        if type(p.get('reactive')) is bool:
            current.append('it is reactive' if p['reactive'] else 'it is unreactive')
    elif level == 'Atom':
        if type(p.get('ionized')) is bool:
            current.append('the atom is ionized' if p['ionized'] else 'the atom is neutral')
        if number('resonance_nm') is not None:
            current.append(f"its resonance lies at {number('resonance_nm'):g} nm")
    elif level == 'SubatomicParticle':
        spin = text('spin')
        if spin:
            current.append('its spin remains superposed' if spin == 'superposed' else f'its spin is {spin}')
        if number('coherence') is not None:
            current.append(f"its coherence is {number('coherence'):g}")

    # These are durable material traces, not guesses about who acted or why.
    traces = []
    for key, line in (('attuned', 'the membranes have been attuned'),
                      ('calibrated', 'the vacuum has been calibrated'),
                      ('kindled', 'a kindling remains in its history'),
                      ('aligned', 'its orbits have been aligned'),
                      ('seeded', 'life has been seeded here'),
                      ('catalyzed', 'a catalyzed reaction remains in its history'),
                      ('observed', 'its spin has been observed')):
        if p.get(key) is True:
            traces.append(line)
    if p.get('warded') is True:
        traces.append('a ward marks the boundary')
    if number('inscriptions') and number('inscriptions') > 0:
        count = number('inscriptions')
        traces.append('an inscription remains' if count == 1 else f'{count:g} inscriptions remain')
    if p.get('fractured') is True:
        traces.append('a fracture remains')
    if resonance['woven']:
        traces.append('a woven resonator holds here')
    if resonance['memory']:
        traces.append('a harmonic memory remains')
    if resonance['scar']:
        traces.append('seams from a dismantled resonator remain')
    if resonance['echo']:
        traces.append('an outward resonance lingers' if resonance['echo'] > 0 else 'an inward resonance lingers')

    return ' '.join(filter(None, (sentence(text('aspect')), sentence('; '.join(current)), sentence('; '.join(traces)))))
