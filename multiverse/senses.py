"""A shared, versioned interpretation of place, independent of media providers."""
from multiverse.interventions_v2 import digest, read_state

VERSION = 2
PLATES = {
    'Emberlit Orchard Terraces-111111': ('orchard', 'a lace of pollen hangs about it; it tightens when approached, and it is patient the way stone is patient.'),
    'Broken Ember Gallery-1111111': ('gallery', 'it carries a dusting of dew; it holds itself perfectly still, and it has forgiven whatever happened here.'),
    'Elder River Instrument-11111111': ('instrument', 'ridges of frost rise along it; it exhales when the pressure drops, and it keeps one secret well.'),
    'Distant River Chain-111111111': ('chain', 'hairline traces of static map it; it drifts a hair out of true, and it tolerates the cold on principle.'),
}
# A plate may stand for a changing arrangement, but never contradict a changed
# material/silhouette. Other states get local rendering or provider enhancement.
PLATE_SHAPES = {
    'orchard': {'terrain': 'overgrown'},
    'gallery': {'ceiling_m': 38.4, 'exits': 1},
    'instrument': {'material': 'woven light', 'condition': 'damaged'},
    'chain': {'geometry': 'helical', 'bond_count': 3, 'compound_type': 'photoreactive'},
}
MATERIALS = {
    'ice': ('#05192d', '#a1e6ee', 'crystalline'),
    'frost': ('#071827', '#b1d8e3', 'crystalline'),
    'coral': ('#201321', '#efaa91', 'branching'),
    'wood': ('#111e1a', '#c8a06a', 'fibrous'),
    'woven light': ('#071b24', '#efc07b', 'filament'),
    'stone': ('#101719', '#bdac93', 'mineral'),
    'metal': ('#101922', '#c5d3dd', 'metallic'),
    'pollen': ('#102523', '#e0b973', 'organic'),
    'helical': ('#071b29', '#81c9d0', 'helical'),
    'dendritic': ('#092027', '#a5d7c0', 'branching'),
}


def describe(node):
    p = node.properties
    state = read_state(p)
    aspect = p.get('aspect', '')
    text = ' '.join(str(p.get(k, '')) for k in ('material', 'geometry', 'biome', 'aspect')).lower()
    shadow, light, texture = '#111b2b', '#ddcba5', 'mineral'
    for source in (str(p.get('material', '')).lower(), str(p.get('geometry', '')).lower(), text):
        matched = next((palette for word, palette in MATERIALS.items() if word in source), None)
        if matched:
            shadow, light, texture = matched
            break
    air = ' '.join(str(p.get(k, '')) for k in ('air', 'weather', 'sky', 'aspect')).lower()
    atmosphere = ('rain' if any(x in air for x in ('rain', 'drizzle', 'dew')) else
                  'dust' if any(x in air for x in ('dust', 'pollen', 'smoke', 'ash')) else
                  'electric' if any(x in air for x in ('lightning', 'static', 'storm')) else
                  'heat' if any(x in air for x in ('heat', 'warm', 'hot')) else 'still')
    danger = p.get('danger_level', 0)
    danger = danger if type(danger) in (int, float) else 0
    tension = max(0, min(1, danger / 10 + max(0, state['echo']) / 24))
    plate = PLATES.get(node.name)
    plate = '/media/places/' + plate[0] + '-v1.png' if (plate and aspect == plate[1] and
        all(p.get(k) == value for k, value in PLATE_SHAPES[plate[0]].items())) else None
    ancestor = node
    while ancestor.parent is not None and ancestor.level not in ('Region', 'Planet'):
        ancestor = ancestor.parent
    # Identity may choose a tonal family; literal material/atmosphere never hash.
    family = int(digest(ancestor.name)[:4], 16) % 4
    result = {'version': VERSION, 'aspect': aspect, 'material': str(p.get('material', texture)),
              'texture': texture, 'atmosphere': atmosphere, 'shadow': shadow, 'light': light,
              'tension': round(tension, 3), 'energy': state['energy'] / 12,
              'polarity': state['polarity'], 'echo': state['echo'], 'woven': state['woven'],
              'memory': state['memory'], 'scar': state['scar'], 'last_wave': state['last_wave'],
              'family': family, 'plate': plate, 'lighting': str(p.get('lighting', 'ambient')),
              'geometry': str(p.get('geometry', '')), 'condition': str(p.get('condition', ''))}
    result['revision'] = digest({'senses': result, 'properties': p})
    return result
