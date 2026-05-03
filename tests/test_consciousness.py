"""Tests for the consciousness module: thread-safety, level voicing, etc."""
from __future__ import annotations

import sys
import threading
import types
from unittest.mock import MagicMock

import pytest

import consciousness
from consciousness import LEVEL_VOICES, _level_voice
from multiverse.generator import LEVELS
from multiverse.node import SpatialNode


def test_get_client_thread_safety():
    """Anthropic() must be called exactly once even with concurrent initialisation."""
    mock_instance = MagicMock()
    call_count = [0]
    count_lock = threading.Lock()

    def counting_anthropic():
        with count_lock:
            call_count[0] += 1
        return mock_instance

    # Inject a fake `anthropic` module so that `from anthropic import Anthropic`
    # inside _get_client resolves to our counting stub — works whether or not
    # the real package is installed.
    fake_anthropic = types.ModuleType("anthropic")
    fake_anthropic.Anthropic = counting_anthropic  # type: ignore[attr-defined]

    import consciousness

    original_module = sys.modules.get("anthropic")
    sys.modules["anthropic"] = fake_anthropic
    consciousness._client = None

    try:
        n_threads = 10
        barrier = threading.Barrier(n_threads)
        results: list = []
        errors: list = []

        def worker():
            try:
                barrier.wait()
                client = consciousness._get_client()
                results.append(client)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    finally:
        if original_module is None:
            sys.modules.pop("anthropic", None)
        else:
            sys.modules["anthropic"] = original_module
        consciousness._client = None

    assert not errors, f"Unexpected errors: {errors}"
    assert call_count[0] == 1, (
        f"Anthropic() called {call_count[0]} times; expected exactly 1"
    )
    assert len(results) == n_threads
    assert all(r is mock_instance for r in results)


# ── Per-level voicing ───────────────────────────────────────────────────────


class TestLevelVoices:
    def test_all_eleven_levels_covered(self):
        # Every level in the canonical generator hierarchy must have a voice.
        for level in LEVELS:
            assert level in LEVEL_VOICES, f"missing voice for {level!r}"

    def test_voices_are_non_empty(self):
        for level, voice in LEVEL_VOICES.items():
            assert voice.strip(), f"{level} voice is empty"

    def test_voices_are_distinct(self):
        # Two scales sharing the exact same voice would defeat the point.
        unique = set(LEVEL_VOICES.values())
        assert len(unique) == len(LEVEL_VOICES)

    def test_lookup_returns_empty_for_unknown_level(self):
        assert _level_voice("Hyperspace") == ""

    def test_lookup_returns_voice_for_known_level(self):
        assert _level_voice("Multiverse") == LEVEL_VOICES["Multiverse"]


# ── speak() integration ─────────────────────────────────────────────────────


@pytest.fixture
def captured_speak_call():
    """Replace consciousness._get_client with a stub that captures the kwargs
    of the most recent .messages.create() call. Restores afterwards."""
    captured: dict = {}

    class _FakeMessages:
        def create(self, **kwargs):
            captured.update(kwargs)
            response = MagicMock()
            response.content = [MagicMock(type="text", text="ok")]
            return response

    fake_client = MagicMock()
    fake_client.messages = _FakeMessages()
    original = consciousness._client
    consciousness._client = fake_client
    try:
        yield captured
    finally:
        consciousness._client = original


class TestSpeakUsesLevelVoice:
    def test_system_includes_level_voice_block(self, captured_speak_call):
        node = SpatialNode(name="The Mire", level="Region",
                           properties={"danger_level": 7})
        consciousness.speak(node, "Who passed through last?")
        system = captured_speak_call["system"]
        # Three blocks: preamble, level voice, node context.
        assert len(system) == 3
        assert system[1]["text"] == LEVEL_VOICES["Region"]

    def test_level_voice_block_is_cached(self, captured_speak_call):
        node = SpatialNode(name="Vault", level="Room", properties={})
        consciousness.speak(node, "Hi.")
        system = captured_speak_call["system"]
        # Both preamble (block 0) and level voice (block 1) carry cache marks
        # so same-level calls hit the longer cached prefix.
        assert "cache_control" in system[0]
        assert "cache_control" in system[1]
        # Node context (block 2) is dynamic, not cached.
        assert "cache_control" not in system[2]

    def test_unknown_level_omits_voice_block(self, captured_speak_call):
        node = SpatialNode(name="Drift", level="Hyperspace", properties={})
        consciousness.speak(node, "Where am I?")
        system = captured_speak_call["system"]
        # No level voice → only preamble + node context.
        assert len(system) == 2
        assert system[0]["text"] == consciousness._SYSTEM_PREAMBLE

    def test_distinct_levels_get_distinct_voices(self, captured_speak_call):
        atom = SpatialNode(name="Hydrogen-A", level="Atom", properties={})
        consciousness.speak(atom, "What are you?")
        atom_voice = captured_speak_call["system"][1]["text"]

        galaxy = SpatialNode(name="Vela-G", level="Galaxy", properties={})
        consciousness.speak(galaxy, "What are you?")
        galaxy_voice = captured_speak_call["system"][1]["text"]

        assert atom_voice != galaxy_voice

    def test_node_context_still_carries_node_name_and_history(
        self, captured_speak_call,
    ):
        node = SpatialNode(name="Sanctum-7", level="Room",
                           properties={"lighting": "dim"})
        history = [{"type": "AGENT_VISIT", "player": None,
                    "data": {"agent": "Tessera"}, "at": "2026-05-03T12:00"}]
        consciousness.speak(node, "Greet me.", history=history)
        node_block = captured_speak_call["system"][2]["text"]
        # Block still embeds node name and history line as before.
        assert "Sanctum-7" in node_block
        assert "Tessera" in node_block
