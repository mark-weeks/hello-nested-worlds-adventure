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


class TestSpeakSystemBlocks:
    def test_two_blocks_world_bible_then_dynamic(self, captured_speak_call):
        node = SpatialNode(name="The Mire", level="Region",
                           properties={"danger_level": 7})
        consciousness.speak(node, "Who passed through last?")
        system = captured_speak_call["system"]
        # Two blocks: cached world bible + dynamic per-call context.
        assert len(system) == 2
        assert system[0]["text"] == consciousness._WORLD_BIBLE

    def test_world_bible_embeds_every_level_voice(self):
        # The cached prefix must contain every level register so the model
        # has the full catalog in cache regardless of which level a given
        # call targets.
        for level, voice in LEVEL_VOICES.items():
            assert voice in consciousness._WORLD_BIBLE, (
                f"{level} voice missing from WORLD_BIBLE"
            )

    def test_world_bible_block_is_cached_with_hour_ttl(self, captured_speak_call):
        node = SpatialNode(name="Vault", level="Room", properties={})
        consciousness.speak(node, "Hi.")
        system = captured_speak_call["system"]
        # Cached prefix carries 1-hour TTL; dynamic block is not cached.
        assert system[0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
        assert "cache_control" not in system[1]

    def test_world_bible_exceeds_cache_minimum(self):
        # Opus 4.7 requires ≥1024 tokens for a cacheable prefix. At a
        # conservative 3.7 chars/token for English markdown, that's 3790
        # chars. Anything below that and `cache_control` is a no-op.
        assert len(consciousness._WORLD_BIBLE) >= 3790, (
            f"WORLD_BIBLE is {len(consciousness._WORLD_BIBLE)} chars — "
            "below the size needed to actually cache on Opus 4.7"
        )

    def test_unknown_level_still_sends_world_bible(self, captured_speak_call):
        node = SpatialNode(name="Drift", level="Hyperspace", properties={})
        consciousness.speak(node, "Where am I?")
        system = captured_speak_call["system"]
        # Unknown level no longer affects block count — the bible is always
        # sent; only the dynamic block references the level by name.
        assert len(system) == 2
        assert system[0]["text"] == consciousness._WORLD_BIBLE
        assert "Hyperspace" in system[1]["text"]

    def test_dynamic_block_carries_node_name_level_and_history(
        self, captured_speak_call,
    ):
        node = SpatialNode(name="Sanctum-7", level="Room",
                           properties={"lighting": "dim"})
        history = [{"type": "AGENT_VISIT", "player": None,
                    "data": {"agent": "Tessera"}, "at": "2026-05-03T12:00"}]
        consciousness.speak(node, "Greet me.", history=history)
        dyn = captured_speak_call["system"][1]["text"]
        assert "Sanctum-7" in dyn
        assert "Room" in dyn
        assert "Tessera" in dyn


class TestAgentBibleStructure:
    def test_agent_bible_embeds_every_archetype(self):
        for archetype in ("tender", "destabilizer", "scholar", "wanderer"):
            assert archetype.capitalize() in consciousness._AGENT_BIBLE, (
                f"{archetype} archetype missing from AGENT_BIBLE"
            )

    def test_agent_bible_exceeds_cache_minimum(self):
        assert len(consciousness._AGENT_BIBLE) >= 3790, (
            f"AGENT_BIBLE is {len(consciousness._AGENT_BIBLE)} chars — "
            "below the size needed to actually cache on Opus 4.7"
        )
