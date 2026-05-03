"""Tests for the agent persona archetype system."""
from __future__ import annotations

from agents.agent import Agent
from agents.personas import (
    CATALOG, DESTABILIZER, SCHOLAR, TENDER, WANDERER,
    by_name, for_name,
)
from causality import CausalityBus, EventKind
from multiverse.node import SpatialNode


class TestForName:
    def test_returns_a_persona_from_catalog(self):
        p = for_name("Scout")
        assert p in CATALOG

    def test_is_deterministic(self):
        # Same name → same persona, across calls and (implicitly) processes.
        # Uses sha1 internally rather than Python's randomized hash().
        first  = for_name("Pilgrim")
        second = for_name("Pilgrim")
        assert first is second

    def test_different_names_can_pick_different_personas(self):
        # We don't assert exhaustive distribution — just that the function is
        # not collapsed to a single archetype.
        names = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]
        picked = {for_name(n).name for n in names}
        assert len(picked) >= 2

    def test_empty_name_still_returns_a_persona(self):
        # sha1("") is well-defined; we just want a non-crash + something
        # from the catalog.
        assert for_name("") in CATALOG


class TestByName:
    def test_known_archetype_resolves(self):
        assert by_name("tender") is TENDER
        assert by_name("destabilizer") is DESTABILIZER
        assert by_name("scholar") is SCHOLAR
        assert by_name("wanderer") is WANDERER

    def test_case_insensitive(self):
        assert by_name("TENDER") is TENDER
        assert by_name("Destabilizer") is DESTABILIZER

    def test_unknown_returns_none(self):
        assert by_name("warlord") is None

    def test_empty_returns_none(self):
        assert by_name("") is None


class TestAgentPersona:
    def test_default_persona_is_assigned_from_name(self):
        agent = Agent(name="Tessera")
        assert agent.persona is for_name("Tessera")

    def test_explicit_persona_overrides_default(self):
        agent = Agent(name="Tessera", persona=DESTABILIZER)
        assert agent.persona is DESTABILIZER

    def test_persona_appears_in_log_entries(self):
        agent = Agent(name="Mark", persona=SCHOLAR)
        node = SpatialNode(name="Vault", level="Room", properties={})
        agent.traverse(node, max_nodes=5)
        # Every recorded log entry carries the persona tag.
        assert all(entry.persona == "scholar" for entry in agent.log)

    def test_persona_appears_in_report(self):
        agent = Agent(name="Echo", persona=WANDERER)
        node = SpatialNode(name="Antechamber", level="Room", properties={})
        agent.traverse(node, max_nodes=3)
        report = agent.report()
        assert "wanderer" in report

    def test_persona_in_causal_event_payload(self):
        captured: list[dict] = []
        bus = CausalityBus()
        bus.register_handler(lambda n, e: captured.append(e.payload))
        agent = Agent(name="Whorl", persona=TENDER, bus=bus)
        node = SpatialNode(name="Sanctum", level="Room",
                           properties={"interactive": False})
        agent.traverse(node, max_nodes=5)
        assert captured, "agent should have emitted at least one causal event"
        assert all(p.get("persona") == "tender" for p in captured)
        assert all(p.get("agent")   == "Whorl"  for p in captured)

    def test_existing_action_strings_unchanged(self):
        # Persona is purely additive — log.action remains a stable contract
        # (the "withdrew" substring is asserted by test_agent.py).
        dangerous = SpatialNode(name="Danger", level="Region",
                                properties={"danger_level": 9})
        root = SpatialNode(name="Root", level="Planet", properties={})
        root.add_child(dangerous)
        agent = Agent(name="Cautious", danger_threshold=6, persona=TENDER)
        agent.traverse(root, max_nodes=5)
        assert any("withdrew" in e.action for e in agent.log)
