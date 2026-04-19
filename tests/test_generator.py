import pytest
from multiverse.generator import generate_node_hierarchy, LEVELS
from multiverse.node import SpatialNode


def test_deterministic():
    a = generate_node_hierarchy(seed=1)
    b = generate_node_hierarchy(seed=1)
    assert repr(a) == repr(b)


def test_different_seeds_differ():
    a = generate_node_hierarchy(seed=1)
    b = generate_node_hierarchy(seed=99)
    assert repr(a) != repr(b)


def test_root_is_multiverse():
    root = generate_node_hierarchy()
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


def test_planet_properties():
    root = generate_node_hierarchy(seed=42, max_depth=5, min_breadth=2, max_breadth=2)

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
