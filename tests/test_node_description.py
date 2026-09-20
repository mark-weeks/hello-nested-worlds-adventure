"""Descriptions derive from the current snapshot, never from a separate live read."""
from copy import deepcopy

from multiverse.generator import generate_node_hierarchy
from multiverse.interventions_v2 import simulate, vocabulary
from multiverse.senses import describe


def test_descriptions_follow_all_supported_material_changes_without_mutating_nodes():
    root = generate_node_hierarchy(seed=382, max_depth=11)
    node = root
    levels = 0
    while node:
        original = deepcopy(node.properties)
        before = describe(node)['description']
        assert before and node.properties == original
        for op in vocabulary(node.level):
            try:
                plan = simulate(original, [{'op': op}], node.level, node.name)
            except ValueError:  # A bounded action may already be exhausted here.
                continue
            node.properties = {**original, **plan['changed']}
            assert describe(node)['description'] != before, (node.level, op)
            assert node.properties['aspect'] == original['aspect']
        node.properties = original
        levels += 1
        node = node.children[0] if node.children else None
    assert levels == 11


def test_incomplete_descriptions_do_not_invent_state_or_future_outcomes():
    from multiverse.node import SpatialNode
    node = SpatialNode('Unspecified-1', 'Object', properties={'aspect': 'it waits.'})
    assert describe(node)['description'] == 'It waits.'
    node.properties.update({'condition': 'damaged', 'surface': '<b>engraved</b>'})
    description = describe(node)['description']
    assert 'damaged' in description and '<b>engraved</b>' in description
    # Rendering owns text escaping. The shared value is literal, with no inferred actor.
    assert 'repaired' not in description and 'will' not in description
