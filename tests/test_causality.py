import pytest
import causality
from causality import CausalEvent, EventKind, emit, propagate, get_log, clear_log
from multiverse.node import SpatialNode


def make_tree() -> SpatialNode:
    """Two-level tree: root → [child1, child2], child1 → [grandchild]."""
    root = SpatialNode(name="Root", level="Universe", properties={})
    child1 = SpatialNode(name="Child1", level="Galaxy", properties={})
    child2 = SpatialNode(name="Child2", level="Galaxy", properties={})
    grandchild = SpatialNode(name="Grandchild", level="Planet", properties={})
    child1.add_child(grandchild)
    root.add_child(child1)
    root.add_child(child2)
    return root


@pytest.fixture(autouse=True)
def _reset():
    clear_log()
    causality.clear_handlers()
    yield
    clear_log()
    causality.clear_handlers()


class TestEmit:
    def test_emit_fires_at_origin_only(self):
        root = make_tree()
        emit(root, EventKind.AGENT_VISIT)
        log = get_log()
        assert len(log) == 1
        assert log[0][0] == "Root"

    def test_emit_returns_event_with_full_strength(self):
        root = make_tree()
        event = emit(root, EventKind.PUZZLE_SOLVED, {"agent": "Scout"})
        assert event.strength == 1.0
        assert event.kind == EventKind.PUZZLE_SOLVED
        assert event.payload["agent"] == "Scout"

    def test_emit_sets_origin_fields(self):
        root = make_tree()
        event = emit(root, EventKind.DANGER_ALERT)
        assert event.origin_id == root.id
        assert event.origin_level == root.level


class TestPropagate:
    def test_propagate_reaches_all_nodes(self):
        root = make_tree()
        propagate(root, EventKind.STRUCTURAL_CHANGE)
        visited = {name for name, _ in get_log()}
        assert visited == {"Root", "Child1", "Child2", "Grandchild"}

    def test_propagate_strength_decreases_with_depth(self):
        root = make_tree()
        propagate(root, EventKind.AGENT_VISIT, dampening=0.5)
        log = get_log()
        strengths = {name: ev.strength for name, ev in log}
        assert strengths["Root"] == pytest.approx(1.0)
        assert strengths["Child1"] == pytest.approx(0.5)
        assert strengths["Grandchild"] == pytest.approx(0.25)

    def test_propagate_stops_below_min_strength(self):
        # With dampening=0.1, strength reaches _MIN_STRENGTH very quickly
        root = make_tree()
        propagate(root, EventKind.AGENT_VISIT, dampening=0.04)
        # Root fires at 1.0, children at 0.04 which is < _MIN_STRENGTH (0.05)
        visited = {name for name, _ in get_log()}
        assert "Root" in visited
        assert "Child1" not in visited

    def test_propagate_returns_event(self):
        root = make_tree()
        event = propagate(root, EventKind.PUZZLE_FAILED)
        assert isinstance(event, CausalEvent)
        assert event.kind == EventKind.PUZZLE_FAILED


class TestUpPropagation:
    """README claims effects propagate 'up and down the hierarchy with
    dampening.' These tests cover the upward path."""

    def test_propagate_from_leaf_reaches_ancestors(self):
        root = make_tree()
        grandchild = root.children[0].children[0]
        propagate(grandchild, EventKind.PUZZLE_SOLVED, dampening=0.5)
        visited = {name for name, _ in get_log()}
        # Grandchild fires; cascades both up the parent chain (Child1, Root)
        # and down its own children (none here).
        assert {"Grandchild", "Child1", "Root"}.issubset(visited)

    def test_up_only_does_not_fire_siblings_or_descendants(self):
        root = make_tree()
        grandchild = root.children[0].children[0]
        propagate(grandchild, EventKind.AGENT_VISIT,
                  dampening=0.5, direction="up")
        visited = {name for name, _ in get_log()}
        # Up-only from Grandchild: Grandchild → Child1 → Root.
        # Child2 is a sibling of Child1, not an ancestor — must not fire.
        assert "Child2" not in visited
        assert visited == {"Grandchild", "Child1", "Root"}

    def test_down_only_preserves_legacy_behavior(self):
        # Existing callers that pass direction="down" get the original
        # downward-only cascade, so puzzle-solve callers can opt out of
        # up-propagation if they ever need to.
        root = make_tree()
        propagate(root, EventKind.STRUCTURAL_CHANGE, direction="down")
        visited = {name for name, _ in get_log()}
        assert visited == {"Root", "Child1", "Child2", "Grandchild"}

    def test_up_strength_decreases_with_each_ancestor(self):
        root = make_tree()
        grandchild = root.children[0].children[0]
        propagate(grandchild, EventKind.AGENT_VISIT, dampening=0.5)
        strengths = {name: ev.strength for name, ev in get_log()}
        assert strengths["Grandchild"] == pytest.approx(1.0)
        assert strengths["Child1"]     == pytest.approx(0.5)
        assert strengths["Root"]       == pytest.approx(0.25)

    def test_origin_fires_exactly_once_with_both(self):
        # Origin at a non-root non-leaf node — both directions active —
        # the origin must still fire exactly once, never twice.
        root = make_tree()
        child1 = root.children[0]
        propagate(child1, EventKind.AGENT_VISIT, dampening=0.5)
        log = get_log()
        names = [name for name, _ in log]
        assert names.count("Child1") == 1

    def test_invalid_direction_raises(self):
        root = make_tree()
        with pytest.raises(ValueError, match="direction"):
            propagate(root, EventKind.AGENT_VISIT, direction="sideways")


class TestRippleScore:
    """`SpatialNode.ripple_score` is documented as cumulative causal pressure.
    Until now it was never mutated; firing on the bus now bumps it."""

    def test_emit_increments_ripple_score(self):
        root = make_tree()
        assert root.ripple_score == 0.0
        emit(root, EventKind.AGENT_VISIT)
        assert root.ripple_score > 0.0

    def test_propagate_marks_each_visited_node(self):
        root = make_tree()
        grandchild = root.children[0].children[0]
        propagate(grandchild, EventKind.PUZZLE_SOLVED, dampening=0.5)
        # Origin and both ancestors should all carry some ripple now.
        assert grandchild.ripple_score > 0.0
        assert root.children[0].ripple_score > 0.0
        assert root.ripple_score > 0.0

    def test_ripple_clamped_to_one(self):
        # Many emits should not push ripple_score above 1.0.
        root = make_tree()
        for _ in range(50):
            emit(root, EventKind.AGENT_VISIT)
        assert root.ripple_score <= 1.0

    def test_dampened_events_leave_smaller_marks(self):
        root = make_tree()
        grandchild = root.children[0].children[0]
        propagate(grandchild, EventKind.AGENT_VISIT, dampening=0.5)
        # Origin gets full strength → biggest mark; root gets the most-
        # dampened strength → smallest mark.
        assert grandchild.ripple_score > root.ripple_score


class TestHandlers:
    def test_handler_called_on_emit(self):
        received = []
        causality.register_handler(lambda node, ev: received.append((node.name, ev.kind)))
        root = make_tree()
        emit(root, EventKind.AGENT_VISIT)
        assert received == [("Root", EventKind.AGENT_VISIT)]

    def test_handler_called_for_each_propagated_node(self):
        counts = []
        causality.register_handler(lambda node, ev: counts.append(node.name))
        root = make_tree()
        propagate(root, EventKind.STRUCTURAL_CHANGE)
        assert len(counts) == 4  # root + child1 + child2 + grandchild

    def test_clear_handlers(self):
        calls = []
        causality.register_handler(lambda n, e: calls.append(1))
        causality.clear_handlers()
        root = make_tree()
        emit(root, EventKind.AGENT_VISIT)
        assert calls == []


class TestDampen:
    def test_dampen_reduces_strength(self):
        ev = CausalEvent(kind=EventKind.AGENT_VISIT, origin_id="x", origin_level="Room", strength=1.0)
        dampened = ev.dampen(0.5)
        assert dampened.strength == pytest.approx(0.5)

    def test_dampen_does_not_mutate_original(self):
        ev = CausalEvent(kind=EventKind.AGENT_VISIT, origin_id="x", origin_level="Room", strength=1.0)
        ev.dampen(0.5)
        assert ev.strength == 1.0

    def test_dampen_copies_payload(self):
        ev = CausalEvent(kind=EventKind.AGENT_VISIT, origin_id="x", origin_level="Room",
                         strength=1.0, payload={"key": "val"})
        dampened = ev.dampen(0.5)
        dampened.payload["key"] = "changed"
        assert ev.payload["key"] == "val"
