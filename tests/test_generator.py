import pytest
from multiverse.generator import generate_node_hierarchy, LEVELS
from multiverse.node import SpatialNode


def test_deterministic():
    a = generate_node_hierarchy(seed=1, max_depth=4)
    b = generate_node_hierarchy(seed=1, max_depth=4)
    assert repr(a) == repr(b)


def test_root_has_no_parent():
    root = generate_node_hierarchy(seed=1, max_depth=3)
    assert root.parent is None


def test_children_link_back_to_parent():
    root = generate_node_hierarchy(seed=1, max_depth=4, min_breadth=2, max_breadth=2)

    def check(node):
        for child in node.children:
            assert child.parent is node, (
                f"{child.name} should point back at {node.name}"
            )
            check(child)

    check(root)


def test_constructor_children_get_parent_set():
    # Children passed to SpatialNode.__init__ should have their parent set,
    # not just children added later via add_child.
    leaf = SpatialNode(name="Leaf", level="Atom", properties={})
    parent = SpatialNode(name="P", level="Molecule", properties={}, children=[leaf])
    assert leaf.parent is parent


def test_different_seeds_differ():
    a = generate_node_hierarchy(seed=1, max_depth=4)
    b = generate_node_hierarchy(seed=99, max_depth=4)
    assert repr(a) != repr(b)


def test_root_is_multiverse():
    root = generate_node_hierarchy(max_depth=3)
    assert root.level == "Multiverse"


def test_all_nodes_have_properties():
    root = generate_node_hierarchy(seed=42, max_depth=4, min_breadth=1, max_breadth=2)

    def check(node):
        assert isinstance(node.properties, dict)
        assert len(node.properties) > 0, f"{node.level} has empty properties"
        for child in node.children:
            check(child)

    check(root)


def test_breadth_respected():
    root = generate_node_hierarchy(seed=7, max_depth=3, min_breadth=2, max_breadth=2)
    assert len(root.children) == 2
    for child in root.children:
        assert len(child.children) == 2


def test_depth_respected():
    root = generate_node_hierarchy(seed=1, max_depth=3, min_breadth=1, max_breadth=1)
    level1 = root.children[0]
    level2 = level1.children[0]
    assert len(level2.children) == 0


def test_node_levels_follow_hierarchy():
    root = generate_node_hierarchy(seed=5, max_depth=5, min_breadth=1, max_breadth=1)
    node = root
    for expected_level in LEVELS[:5]:
        assert node.level == expected_level
        if node.children:
            node = node.children[0]


def test_planetary_system_in_hierarchy():
    root = generate_node_hierarchy(seed=1, max_depth=4, min_breadth=1, max_breadth=1)
    # With max_depth=4: Multiverse → Universe → Galaxy → Planetary System
    node = root
    for _ in range(3):
        assert node.children, f"{node.level} should have a child"
        node = node.children[0]
    assert node.level == "Planetary System"
    assert "star_type" in node.properties
    assert "planet_count" in node.properties
    assert "habitable_zone" in node.properties


def test_planet_properties():
    # max_depth=6 reaches Planet (index 4) with Planetary System (index 3) now in between
    root = generate_node_hierarchy(seed=42, max_depth=6, min_breadth=2, max_breadth=2)

    def find_planets(node):
        results = []
        if node.level == "Planet":
            results.append(node)
        for child in node.children:
            results.extend(find_planets(child))
        return results

    planets = find_planets(root)
    assert planets, "No planets generated"
    for planet in planets:
        assert "gravity" in planet.properties
        assert "biome" in planet.properties
        assert "inhabited" in planet.properties
        assert "moons" in planet.properties
        assert 0.1 <= planet.properties["gravity"] <= 3.5


def _collect(node, out=None):
    if out is None:
        out = {}
    out[node.name] = node
    for child in node.children:
        _collect(child, out)
    return out


class TestCanonicalWorld:
    """One seed = one world: any depth prefix is identical to the full tree."""

    def test_depth_prefix_is_identical(self):
        shallow = _collect(generate_node_hierarchy(seed=42, max_depth=6))
        deep = _collect(generate_node_hierarchy(seed=42, max_depth=11))
        assert set(shallow) <= set(deep), (
            "every node in the depth-6 world must exist in the depth-11 world"
        )
        for name, node in shallow.items():
            twin = deep[name]
            assert node.level == twin.level
            assert node.properties == twin.properties
            # Same branching for non-leaf levels of the shallow tree.
            if node.children:
                assert [c.name for c in node.children] == [c.name for c in twin.children]

    def test_names_unique_within_world(self):
        root = generate_node_hierarchy(seed=7, max_depth=11)
        names = []

        def walk(n):
            names.append(n.name)
            for c in n.children:
                walk(c)

        walk(root)
        assert len(names) == len(set(names))

    def test_node_identity_independent_of_siblings(self):
        # A node's name/properties depend only on (seed, path) — not on how
        # deep the rest of the tree goes.
        a = generate_node_hierarchy(seed=3, max_depth=4, min_breadth=2, max_breadth=2)
        b = generate_node_hierarchy(seed=3, max_depth=8, min_breadth=2, max_breadth=2)
        assert a.children[1].name == b.children[1].name
        assert a.children[1].properties == b.children[1].properties

    def test_atom_element_matches_atomic_number(self):
        root = generate_node_hierarchy(seed=11, max_depth=11, min_breadth=1, max_breadth=2)
        table = {"H": 1, "C": 6, "N": 7, "O": 8, "Si": 14,
                 "Fe": 26, "Xe": 54, "Au": 79, "Pb": 82, "U": 92}

        def walk(n):
            if n.level == "Atom":
                assert n.properties["atomic_number"] == table[n.properties["element"]]
            for c in n.children:
                walk(c)

        walk(root)

    def test_breadth_above_nine_rejected(self):
        with pytest.raises(ValueError, match="max_breadth"):
            generate_node_hierarchy(seed=1, max_depth=3, min_breadth=1, max_breadth=10)


class TestGeneratorValidation:
    def test_min_breadth_exceeds_max_raises(self):
        with pytest.raises(ValueError, match="min_breadth"):
            generate_node_hierarchy(min_breadth=5, max_breadth=2)

    def test_max_depth_zero_raises(self):
        with pytest.raises(ValueError, match="max_depth"):
            generate_node_hierarchy(max_depth=0)

    def test_max_depth_too_large_raises(self):
        with pytest.raises(ValueError, match="max_depth"):
            generate_node_hierarchy(max_depth=len(LEVELS) + 1)

    def test_valid_params_do_not_raise(self):
        root = generate_node_hierarchy(seed=1, max_depth=3, min_breadth=2, max_breadth=2)
        assert root is not None

    def test_equal_min_max_breadth_is_valid(self):
        root = generate_node_hierarchy(seed=1, max_depth=3, min_breadth=2, max_breadth=2)
        assert len(root.children) == 2


class TestNodeUniqueness:
    """Each node is one of a kind: full names unique by construction, base
    names synthesized from spaces large enough that repetition is rare, and
    every node carries an `aspect` description belonging to it alone."""

    def _walk(self, seed, depth=11):
        root = generate_node_hierarchy(seed=seed, max_depth=depth)
        out = []

        def walk(n):
            out.append(n)
            for c in n.children:
                walk(c)

        walk(root)
        return out

    def test_full_names_unique(self):
        nodes = self._walk(seed=13)
        names = [n.name for n in nodes]
        assert len(names) == len(set(names))

    def test_base_names_rarely_repeat(self):
        nodes = self._walk(seed=13)
        bases = [n.name.rsplit("-", 1)[0] for n in nodes]
        distinct = len(set(bases)) / len(bases)
        assert distinct >= 0.95, (
            f"only {distinct:.1%} of base names are distinct — the synthesis "
            "space has collapsed and nodes no longer feel unique"
        )

    def test_every_node_has_a_unique_aspect(self):
        nodes = self._walk(seed=13)
        aspects = [n.properties.get("aspect") for n in nodes]
        assert all(aspects), "every node must carry an aspect description"
        distinct = len(set(aspects)) / len(aspects)
        assert distinct >= 0.99

    def test_property_sets_never_repeat(self):
        # Continuous values + the aspect make a node's full property tuple
        # effectively unrepeatable within a world.
        nodes = self._walk(seed=13)
        fingerprints = [tuple(sorted((k, str(v)) for k, v in n.properties.items()))
                        for n in nodes]
        assert len(set(fingerprints)) == len(fingerprints)

    def test_base_names_never_contain_the_suffix_separator(self):
        # rpartition("-") is how resolve_node_by_name recovers the path; a
        # hyphen inside a base name would corrupt resolution.
        nodes = self._walk(seed=13, depth=8)
        for n in nodes:
            base = n.name.rsplit("-", 1)[0]
            assert "-" not in base, f"{n.name!r} has a hyphenated base"

    def test_synthesized_names_still_resolve(self):
        from multiverse.generator import resolve_node_by_name
        nodes = self._walk(seed=13, depth=8)
        for n in nodes[:: max(1, len(nodes) // 25)]:
            resolved = resolve_node_by_name(13, n.name)
            assert resolved is not None, f"{n.name} failed to resolve"
            assert resolved.properties == n.properties
