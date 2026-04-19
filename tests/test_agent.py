import pytest
from multiverse.generator import generate_node_hierarchy
from multiverse.node import SpatialNode
from agents.agent import Agent
from agents.behaviors import State, transition, should_preserve, should_interact


def make_node(level="Room", **props):
    return SpatialNode(name=f"Test-{level}", level=level, properties=props)


class TestBehaviors:
    def test_should_preserve_from_high_danger(self):
        node = make_node(danger_level=8)
        assert should_preserve(node, danger_threshold=6)

    def test_should_not_preserve_from_low_danger(self):
        node = make_node(danger_level=3)
        assert not should_preserve(node, danger_threshold=6)

    def test_should_interact_with_puzzle(self):
        node = make_node(has_puzzle=True)
        assert should_interact(node)

    def test_should_interact_with_interactive(self):
        node = make_node(interactive=True)
        assert should_interact(node)

    def test_idle_transitions_to_explore(self):
        node = make_node()
        assert transition(State.IDLE, node) == State.EXPLORE

    def test_explore_to_interact_on_puzzle(self):
        node = make_node(has_puzzle=True, danger_level=1)
        assert transition(State.EXPLORE, node) == State.INTERACT

    def test_explore_to_exit_on_high_danger(self):
        node = make_node(danger_level=9)
        assert transition(State.EXPLORE, node) == State.EXIT

    def test_interact_returns_to_explore(self):
        node = make_node()
        assert transition(State.INTERACT, node) == State.EXPLORE

    def test_exit_stays_exit(self):
        node = make_node()
        assert transition(State.EXIT, node) == State.EXIT


class TestAgent:
    def test_agent_traverses_world(self):
        root = generate_node_hierarchy(seed=42, max_depth=4, min_breadth=1, max_breadth=2)
        agent = Agent(name="TestScout")
        agent.traverse(root, max_nodes=20)
        assert len(agent.visited) > 0
        assert len(agent.log) > 0

    def test_agent_respects_max_nodes(self):
        root = generate_node_hierarchy(seed=1, max_depth=6, min_breadth=2, max_breadth=2)
        agent = Agent(name="Bounded")
        agent.traverse(root, max_nodes=10)
        assert len(agent.visited) <= 10

    def test_agent_withdraws_from_dangerous_nodes(self):
        dangerous = SpatialNode(name="Danger-Zone", level="Region", properties={"danger_level": 9})
        safe = SpatialNode(name="Safe-Zone", level="Region", properties={"danger_level": 2})
        root = SpatialNode(name="Root", level="Planet", properties={"gravity": 1.0})
        root.add_child(dangerous)
        root.add_child(safe)

        agent = Agent(name="Cautious", danger_threshold=6)
        agent.traverse(root, max_nodes=20)

        withdrew = [e for e in agent.log if "withdrew" in e.action]
        assert len(withdrew) >= 1

    def test_agent_report_contains_name(self):
        root = generate_node_hierarchy(seed=5, max_depth=3, min_breadth=1, max_breadth=1)
        agent = Agent(name="Recon")
        agent.traverse(root)
        report = agent.report()
        assert "Recon" in report

    def test_no_duplicate_visits(self):
        root = generate_node_hierarchy(seed=3, max_depth=4, min_breadth=1, max_breadth=2)
        agent = Agent(name="UniqueVisitor")
        agent.traverse(root, max_nodes=30)
        assert len(agent.visited) == len(set(agent.visited))
