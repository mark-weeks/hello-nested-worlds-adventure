"""Tests for server/imageprompt.py — structured per-level prompt assembly."""
from __future__ import annotations

import pytest

from server import imageprompt
from server.imageprompt import (
    HIERARCHY_STYLES, assemble_prompt, derive_modifiers, style_signature,
)


# ── derive_modifiers ────────────────────────────────────────────────────────


class TestDeriveModifiers:
    def test_empty_history_yields_pristine(self):
        mods = derive_modifiers({}, [])
        assert any("ethereal" in m for m in mods)
        assert any("untouched" in m for m in mods)

    def test_pristine_short_circuits_other_signals(self):
        # No history → only the pristine tag, regardless of properties.
        mods = derive_modifiers({"has_puzzle": True, "condition": "corrupted"}, [])
        assert mods == ["ethereal, minimal, untouched"]

    def test_high_agent_activity_triggers_surreal(self):
        history = [{"type": "AGENT_VISIT"}] * 5
        mods = derive_modifiers({}, history)
        assert any("surreal" in m for m in mods)

    def test_below_agent_threshold_does_not_trigger_surreal(self):
        history = [{"type": "AGENT_VISIT"}] * 4
        mods = derive_modifiers({}, history)
        assert not any("surreal" in m for m in mods)

    def test_danger_alert_triggers_noir(self):
        history = [{"type": "DANGER_ALERT"}]
        mods = derive_modifiers({}, history)
        assert any("noir" in m for m in mods)

    def test_two_distinct_speakers_trigger_warmth(self):
        history = [
            {"type": "PLAYER_SPEAK", "player": "Alice"},
            {"type": "PLAYER_CHAT",  "player": "Bob"},
        ]
        mods = derive_modifiers({}, history)
        assert any("warm" in m for m in mods)

    def test_single_speaker_does_not_trigger_warmth(self):
        history = [
            {"type": "PLAYER_SPEAK", "player": "Alice"},
            {"type": "PLAYER_CHAT",  "player": "Alice"},
        ]
        mods = derive_modifiers({}, history)
        assert not any("warm" in m for m in mods)

    def test_puzzle_property_triggers_geometric(self):
        history = [{"type": "AGENT_VISIT"}]  # break out of pristine
        mods = derive_modifiers({"has_puzzle": True}, history)
        assert any("Escher" in m for m in mods)

    def test_solved_puzzle_triggers_geometric(self):
        history = [{"type": "PUZZLE_SOLVED"}]
        mods = derive_modifiers({}, history)
        assert any("Escher" in m for m in mods)

    def test_repeated_puzzle_failure_triggers_oppressive(self):
        history = [{"type": "PUZZLE_FAILED"}, {"type": "PUZZLE_FAILED"}]
        mods = derive_modifiers({}, history)
        assert any("oppressive" in m for m in mods)

    def test_corrupted_property_triggers_glitch(self):
        history = [{"type": "AGENT_VISIT"}]
        mods = derive_modifiers({"condition": "corrupted"}, history)
        assert any("glitch" in m for m in mods)

    def test_modifiers_are_stable_across_calls(self):
        history = [{"type": "AGENT_VISIT"}] * 5 + [{"type": "DANGER_ALERT"}]
        a = derive_modifiers({"has_puzzle": True}, history)
        b = derive_modifiers({"has_puzzle": True}, history)
        assert a == b


# ── assemble_prompt ─────────────────────────────────────────────────────────


class TestAssemblePrompt:
    def test_includes_node_name_and_level(self):
        out = assemble_prompt("Region", "The Mire", {}, [])
        assert "region" in out.lower()
        assert "The Mire" in out

    def test_uses_per_level_baseline(self):
        # Multiverse + Galaxy + Atom should each pull their distinct register.
        for level in ("Multiverse", "Galaxy", "Atom"):
            out = assemble_prompt(level, "X", {}, [])
            baseline = HIERARCHY_STYLES[level]
            assert baseline in out

    def test_unknown_level_falls_back_to_default(self):
        out = assemble_prompt("Hyperspace", "X", {}, [])
        # No crash, and the result is still a usable prompt.
        assert "hyperspace" in out.lower()
        assert "atmospheric" in out.lower()

    def test_pristine_node_mentions_pristine_mood(self):
        out = assemble_prompt("Room", "Vault", {}, [])
        assert "untouched" in out.lower() or "ethereal" in out.lower()

    def test_property_summary_is_included(self):
        out = assemble_prompt("Room", "Vault", {"lighting": "flickering"}, [])
        assert "lighting" in out
        assert "flickering" in out

    def test_property_summary_capped_at_six(self):
        # Use single-letter keys so the sort order is unambiguous.
        props = {k: i for i, k in enumerate("abcdefghij")}
        out = assemble_prompt("Room", "Vault", props, [])
        # Sorted: a..f are kept (6 entries); g..j are dropped.
        for k in ("a", "b", "c", "d", "e", "f"):
            assert f"{k}: " in out
        for k in ("g", "h", "i", "j"):
            assert f"{k}: " not in out

    def test_distinct_levels_produce_distinct_prompts(self):
        a = assemble_prompt("Multiverse", "X", {}, [])
        b = assemble_prompt("Atom",       "X", {}, [])
        assert a != b


# ── style_signature ─────────────────────────────────────────────────────────


class TestStyleSignature:
    def test_signature_is_deterministic(self):
        history = [{"type": "AGENT_VISIT"}] * 3
        a = style_signature("Region", {"danger_level": 4}, history)
        b = style_signature("Region", {"danger_level": 4}, history)
        assert a == b

    def test_signature_changes_when_modifiers_flip(self):
        before = style_signature("Region", {}, [{"type": "AGENT_VISIT"}] * 4)
        after  = style_signature("Region", {}, [{"type": "AGENT_VISIT"}] * 5)
        # Crossing the AGENT_VISIT >= 5 threshold should flip the signature.
        assert before != after

    def test_signature_changes_with_level(self):
        a = style_signature("Multiverse", {}, [])
        b = style_signature("Atom",       {}, [])
        assert a != b

    def test_signature_changes_with_properties(self):
        a = style_signature("Region", {"biome": "tundra"}, [])
        b = style_signature("Region", {"biome": "jungle"}, [])
        assert a != b

    def test_signature_is_short(self):
        sig = style_signature("Region", {}, [])
        assert len(sig) == 8
        # hex chars only
        int(sig, 16)
