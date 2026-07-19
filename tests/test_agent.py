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
        root = generate_node_hierarchy(seed=42, max_depth=4)
        agent = Agent(name="TestScout")
        agent.traverse(root, max_nodes=20)
        assert len(agent.visited) > 0
        assert len(agent.log) > 0

    def test_agent_respects_max_nodes(self):
        root = generate_node_hierarchy(seed=1, max_depth=6)
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
        root = generate_node_hierarchy(seed=5, max_depth=3)
        agent = Agent(name="Recon")
        agent.traverse(root)
        report = agent.report()
        assert "Recon" in report

    def test_no_duplicate_visits(self):
        root = generate_node_hierarchy(seed=3, max_depth=4)
        agent = Agent(name="UniqueVisitor")
        agent.traverse(root, max_nodes=30)
        assert len(agent.visited) == len(set(agent.visited))


class TestAgentPuzzleRules:
    """Agents face the puzzle engine like humans do — no free solves."""

    def _interact(self, agent_name, node_name):
        from causality import CausalityBus
        node = SpatialNode(node_name, "Room",
                           properties={"has_puzzle": True, "danger_level": 1})
        bus = CausalityBus()
        agent = Agent(name=agent_name, bus=bus)
        agent.state = State.INTERACT
        agent._act(node)
        return [ev.kind.name for _, ev in bus.get_log()], bus.get_log()

    def test_outcome_is_a_roll_not_a_gift(self):
        outcomes = set()
        for i in range(40):
            kinds, _ = self._interact(f"Agent{i}", f"Vault-{i}")
            outcomes.update(k for k in kinds
                            if k in ("PUZZLE_SOLVED", "PUZZLE_FAILED"))
        assert outcomes == {"PUZZLE_SOLVED", "PUZZLE_FAILED"}, (
            "agents must sometimes fail puzzles — a guaranteed solve would "
            "mint for free the event humans have to earn"
        )

    def test_outcome_is_reproducible(self):
        a, _ = self._interact("Tessera", "Vault-11")
        b, _ = self._interact("Tessera", "Vault-11")
        assert a == b

    def test_event_payload_names_the_puzzle(self):
        _, log = self._interact("Tessera", "Vault-11")
        origin_events = [ev for name, ev in log if name == "Vault-11"]
        assert origin_events
        assert origin_events[0].payload.get("puzzle")


class TestAgentMemory:
    def test_memory_accumulates_across_runs(self):
        root = generate_node_hierarchy(seed=7, max_depth=4)
        agent = Agent(name="Chronicler")
        agent.traverse(root, max_nodes=5)
        first_memory = list(agent.memory)
        assert len(first_memory) > 0

        agent.traverse(root, max_nodes=5)
        assert len(agent.memory) >= len(first_memory)

    def test_fresh_count_is_zero_when_world_fully_known(self):
        root = generate_node_hierarchy(seed=2, max_depth=3)
        agent = Agent(name="Explorer")
        agent.traverse(root)
        total = len(agent.memory)
        assert agent.fresh_count == total

        agent.traverse(root)
        assert agent.fresh_count == 0

    def test_known_nodes_skipped_in_second_run(self):
        root = generate_node_hierarchy(seed=9, max_depth=4)
        agent = Agent(name="Rover")
        agent.traverse(root, max_nodes=10)
        after_first = len(agent.memory)

        agent.traverse(root, max_nodes=10)
        # fresh_count ≤ what was left unexplored
        assert agent.fresh_count <= after_first

    def test_memory_can_be_restored_externally(self):
        root = generate_node_hierarchy(seed=5, max_depth=4)
        a1 = Agent(name="Pioneer")
        a1.traverse(root, max_nodes=8)
        saved_names = list(a1.memory)

        a2 = Agent(name="Pioneer")
        a2.memory = saved_names
        a2.traverse(root, max_nodes=8)
        # Restored memory means known nodes are skipped: nothing already in
        # memory is re-visited as fresh.
        fresh = a2.memory[len(saved_names):]
        assert not set(fresh) & set(saved_names)

    def test_memory_survives_world_rebuild(self):
        # Memory is keyed by node NAME, so it must carry across a fresh
        # regeneration of the same world (new node UUIDs) — the second run
        # continues into unexplored territory instead of going inert.
        first = generate_node_hierarchy(seed=5, max_depth=5)
        agent = Agent(name="Pioneer")
        agent.traverse(first, max_nodes=6)
        assert agent.fresh_count == 6

        rebuilt = generate_node_hierarchy(seed=5, max_depth=5)
        agent.traverse(rebuilt, max_nodes=6)
        assert agent.fresh_count > 0, (
            "restored memory must not consume the visit budget and brick the agent"
        )
        assert len(agent.memory) == len(set(agent.memory))

    def test_memory_has_no_duplicates(self):
        root = generate_node_hierarchy(seed=4, max_depth=4)
        agent = Agent(name="Careful")
        agent.traverse(root, max_nodes=10)
        agent.traverse(root, max_nodes=10)
        assert len(agent.memory) == len(set(agent.memory))

    def test_report_mentions_new_and_prior(self):
        root = generate_node_hierarchy(seed=6, max_depth=3)
        agent = Agent(name="Scribe")
        agent.traverse(root, max_nodes=5)
        agent.traverse(root, max_nodes=5)
        report = agent.report()
        assert "previously known" in report
