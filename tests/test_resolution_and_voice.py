"""Server-side node resolution, the authored failure voice, and node memory.

Covers: O(depth) name→node resolution (including forged-name rejection),
/speak's server-derived identity + in-fiction fallback when the AI layer is
unavailable, the reply being persisted into node memory, and the
per-(node, player) transcript reaching the prompt as real multi-turn
messages.
"""
from __future__ import annotations

import json
import threading
import urllib.error
import urllib.parse
import urllib.request

import pytest

import consciousness
import persistence
from multiverse.generator import generate_node_hierarchy, resolve_node_by_name
from server import _Handler, _ThreadedServer


@pytest.fixture()
def srv():
    server = _ThreadedServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


def _post(url: str, data: dict):
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read()), resp.status


def _some_deep_node(seed=42):
    root = generate_node_hierarchy(seed=seed, max_depth=6)
    node = root
    while node.children:
        node = node.children[-1]
    return node


class TestResolveNodeByName:
    def test_resolves_root(self):
        root = generate_node_hierarchy(seed=42, max_depth=1)
        node = resolve_node_by_name(42, root.name)
        assert node is not None
        assert node.level == "Multiverse"
        assert node.properties == root.properties

    def test_resolves_deep_node_with_ancestry(self):
        target = _some_deep_node()
        node = resolve_node_by_name(42, target.name)
        assert node is not None
        assert node.level == target.level
        assert node.properties == target.properties
        # Ancestor chain is attached, up to the root.
        depth = 0
        cursor = node
        while cursor.parent is not None:
            cursor = cursor.parent
            depth += 1
        assert cursor.level == "Multiverse"
        assert depth == 5

    def test_rejects_forged_base_name(self):
        assert resolve_node_by_name(42, "TotallyFake-11") is None

    def test_rejects_out_of_range_path(self):
        # Path digit 9 exceeds any breadth the generator rolls (1–3).
        root = generate_node_hierarchy(seed=42, max_depth=1)
        base = root.name.rsplit("-", 1)[0]
        assert resolve_node_by_name(42, f"{base}-19") is None

    def test_rejects_garbage(self):
        assert resolve_node_by_name(42, "") is None
        assert resolve_node_by_name(42, "no-suffix-here") is None
        assert resolve_node_by_name(42, "Vault-10") is None  # 0 step forged


class TestSpeakResolution:
    def test_unknown_node_404s(self, srv):
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            _post(f"{srv}/speak",
                  {"node_name": "Forged-11", "message": "hi", "seed": 42})
        assert exc_info.value.code == 404

    def test_missing_key_returns_in_fiction_fallback(self, srv, monkeypatch):
        # No ANTHROPIC_API_KEY in the test environment: the world must go
        # quiet in character — HTTP 200, an authored line in the node's
        # register, never an SDK error or a 503.
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        real = generate_node_hierarchy(seed=42, max_depth=1)
        data, status = _post(
            f"{srv}/speak",
            {"node_name": real.name, "message": "hello?", "seed": 42})
        assert status == 200
        assert data["ai"] is False
        assert data["response"] == consciousness.LEVEL_FALLBACKS["Multiverse"]
        assert "Service unavailable" not in data["response"]

    def test_speak_persists_both_sides_and_builds_transcript(self, srv, monkeypatch):
        real = generate_node_hierarchy(seed=42, max_depth=1)
        seen = {}

        def fake_speak(node, message, history=None, transcript=None,
                       ripple_score=0.0, speaker=None):
            seen["transcript"] = list(transcript or [])
            seen["speaker"] = speaker
            return f"I heard: {message}"

        monkeypatch.setattr(consciousness, "speak", fake_speak)

        _post(f"{srv}/speak", {"node_name": real.name, "seed": 42,
                               "message": "first words", "player_name": "Ada"})
        # Both sides of the exchange land in node memory.
        history = persistence.get_node_history(42, real.name)
        speak_rows = [h for h in history if h["type"] == "PLAYER_SPEAK"]
        assert speak_rows
        assert speak_rows[0]["data"]["message"] == "first words"
        assert speak_rows[0]["data"]["reply"] == "I heard: first words"
        # The handler threads the visitor's display name through to speak(),
        # so the node can recognize a returning "Ada" in its own memory.
        assert seen["speaker"] == "Ada"

        # The second conversation knows the first happened.
        _post(f"{srv}/speak", {"node_name": real.name, "seed": 42,
                               "message": "second words", "player_name": "Ada"})
        assert seen["transcript"] == [
            {"user": "first words", "assistant": "I heard: first words"},
        ]

    def test_speak_stores_full_message_and_reply_untruncated(self, srv, monkeypatch):
        # ADR-004: the permanent record keeps the full message and reply — the
        # old [:128]/[:200] storage truncation silently lost the tail forever.
        real = generate_node_hierarchy(seed=42, max_depth=1)
        long_msg = "the vault keeps a very long secret and wants it recorded " * 4

        def fake_speak(node, message, history=None, transcript=None,
                       ripple_score=0.0, speaker=None):
            return "a reply comfortably longer than the old two-hundred-char cap " * 4

        monkeypatch.setattr(consciousness, "speak", fake_speak)
        _post(f"{srv}/speak", {"node_name": real.name, "seed": 42,
                               "message": long_msg, "player_name": "Ada"})
        rows = [h for h in persistence.get_node_history(42, real.name)
                if h["type"] == "PLAYER_SPEAK"]
        assert rows
        stored = rows[0]["data"]
        assert stored["message"] == long_msg and len(stored["message"]) > 128
        assert len(stored["reply"]) > 200


class TestFallbackVoices:
    def test_every_level_has_an_authored_silence(self):
        from multiverse.generator import LEVELS
        for level in LEVELS:
            assert level in consciousness.LEVEL_FALLBACKS
            assert consciousness.LEVEL_FALLBACKS[level].strip()

    def test_fallback_lines_are_distinct(self):
        lines = set(consciousness.LEVEL_FALLBACKS.values())
        assert len(lines) == len(consciousness.LEVEL_FALLBACKS)


class TestNodeMemoryContent:
    def test_history_block_renders_what_was_said(self):
        history = [{
            "type": "PLAYER_SPEAK", "player": "Ada",
            "data": {"message": "what do you guard?",
                     "reply": "Only the dark."},
            "at": "2026-07-01T10:00",
        }]
        block = consciousness._history_block(history)
        assert 'they said: "what do you guard?"' in block
        assert 'you answered: "Only the dark."' in block

    def test_history_block_clips_long_content_for_the_prompt_only(self):
        # ADR-004: the chronicle stores full content; the PROMPT clips it to a
        # render budget so a long message can't blow a voice call's context.
        long_msg = "m" * 500
        long_reply = "r" * 500
        history = [{
            "type": "PLAYER_SPEAK", "player": "Ada",
            "data": {"message": long_msg, "reply": long_reply},
            "at": "2026-07-12T10:00",
        }]
        block = consciousness._history_block(history)
        # Clipped to exactly the render budget — not one char more, and the
        # full stored strings never reach the prompt.
        assert long_msg not in block
        assert long_reply not in block
        assert "m" * consciousness._MEM_MSG_CHARS in block
        assert "m" * (consciousness._MEM_MSG_CHARS + 1) not in block
        assert "r" * consciousness._MEM_REPLY_CHARS in block
        assert "r" * (consciousness._MEM_REPLY_CHARS + 1) not in block

    def test_player_exchanges_round_trip(self):
        persistence.record_mutation(
            5, "Vault-11", "PLAYER_SPEAK", "Ada",
            {"message": "hello", "reply": "hush", "identity": "Ada"})
        persistence.record_mutation(
            5, "Vault-11", "PLAYER_SPEAK", "Bob",
            {"message": "other player", "identity": "Bob"})
        exchanges = persistence.get_player_exchanges(5, "Vault-11", "Ada")
        assert exchanges == [{"user": "hello", "assistant": "hush"}]

    def test_transcripts_key_on_credential_not_display_name(self):
        # Two players who both call themselves "Ada" must not share a
        # memory: the conversation identity is the hashed invite key when
        # one was presented, so same-name strangers stay strangers and a
        # rename doesn't orphan a transcript.
        persistence.record_mutation(
            5, "Vault-11", "PLAYER_SPEAK", "Ada",
            {"message": "first ada", "identity": "cred-aaaa"})
        persistence.record_mutation(
            5, "Vault-11", "PLAYER_SPEAK", "Ada",
            {"message": "second ada", "identity": "cred-bbbb"})
        a = persistence.get_player_exchanges(5, "Vault-11", "cred-aaaa")
        b = persistence.get_player_exchanges(5, "Vault-11", "cred-bbbb")
        assert [e["user"] for e in a] == ["first ada"]
        assert [e["user"] for e in b] == ["second ada"]

    def test_transcript_becomes_multi_turn_messages(self):
        captured = {}

        class _FakeMessages:
            def create(self, **kwargs):
                captured.update(kwargs)
                from unittest.mock import MagicMock
                response = MagicMock()
                response.content = [MagicMock(type="text", text="ok")]
                return response

        from unittest.mock import MagicMock
        fake_client = MagicMock()
        fake_client.messages = _FakeMessages()
        original = consciousness._client
        consciousness._client = fake_client
        try:
            from multiverse.node import SpatialNode
            node = SpatialNode("Vault-11", "Room", properties={})
            consciousness.speak(
                node, "and now?",
                transcript=[{"user": "hello", "assistant": "hush"}],
            )
        finally:
            consciousness._client = original

        assert captured["messages"] == [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hush"},
            {"role": "user", "content": "and now?"},
        ]

    def test_ripple_pressure_reaches_the_prompt(self):
        captured = {}

        class _FakeMessages:
            def create(self, **kwargs):
                captured.update(kwargs)
                from unittest.mock import MagicMock
                response = MagicMock()
                response.content = [MagicMock(type="text", text="ok")]
                return response

        from unittest.mock import MagicMock
        fake_client = MagicMock()
        fake_client.messages = _FakeMessages()
        original = consciousness._client
        consciousness._client = fake_client
        try:
            from multiverse.node import SpatialNode
            node = SpatialNode("Vault-11", "Room", properties={})
            consciousness.speak(node, "how do you feel?", ripple_score=0.72)
        finally:
            consciousness._client = original

        dynamic = captured["system"][1]["text"]
        assert "0.72" in dynamic
        assert "pressure" in dynamic.lower()


class TestAgentAddressability:
    """Addressing 'the agent whose traces are here' must reach an agent that
    remembers being here — its persisted memory grounds the voice prompt."""

    def test_history_endpoint_supports_node_scope(self, srv):
        real = generate_node_hierarchy(seed=42, max_depth=1)
        persistence.record_mutation(
            42, real.name, "AGENT_VISIT", None,
            {"agent": "Tessera", "persona": "scholar"})
        persistence.record_mutation(
            42, "Elsewhere-12", "AGENT_VISIT", None, {"agent": "Vex"})
        with urllib.request.urlopen(
                f"{srv}/history?seed=42&node_name={urllib.parse.quote(real.name)}") as resp:
            data = json.loads(resp.read())
        agents = {m["data"].get("agent") for m in data["mutations"]}
        assert "Tessera" in agents
        assert "Vex" not in agents, "node-scoped history leaked other nodes"
        assert all(m["node"] == real.name for m in data["mutations"])

    def test_agent_voice_carries_the_agents_own_memory(self, srv, monkeypatch):
        real = generate_node_hierarchy(seed=42, max_depth=1)
        persistence.save_agent_memory(
            "Tessera", 42, [real.name, "Vault-11"],
            [{"node": real.name, "action": "explored"}])

        captured = {}

        def fake_voice_agent(persona, agent_name, node, message,
                             history=None, agent_memory=None):
            captured.update(agent=agent_name, memory=agent_memory,
                            history=history)
            return "…"

        monkeypatch.setattr(consciousness, "voice_agent", fake_voice_agent)
        _post(f"{srv}/agent/voice",
              {"agent_name": "Tessera", "node_name": real.name,
               "seed": 42, "message": "you were here?"})
        assert captured["agent"] == "Tessera"
        assert captured["memory"] is not None
        assert real.name in captured["memory"]["visited_ids"]

    def test_memory_block_marks_returning_presence(self):
        from multiverse.node import SpatialNode
        node = SpatialNode("Vault-11", "Room", properties={})
        block = consciousness._agent_memory_block(
            {"visited_ids": ["Vault-11", "Other-12"],
             "log_entries": [{"node": "Other-12", "action": "explored"}]},
            node)
        assert "stood at Vault-11 before" in block
        assert "Other-12 — explored" in block
        assert "2 place(s)" in block

    def test_memory_block_for_stranger(self):
        from multiverse.node import SpatialNode
        node = SpatialNode("Vault-11", "Room", properties={})
        assert "no memories" in consciousness._agent_memory_block(None, node)


class TestTranscriptIdentityOverHTTP:
    def test_same_credential_shares_transcript_across_renames(self, srv, monkeypatch):
        import server.guard as guard_mod
        monkeypatch.setenv(guard_mod.BETA_KEY_ENV, "sharedkey")
        real = generate_node_hierarchy(seed=42, max_depth=1)
        seen = {}

        def fake_speak(node, message, history=None, transcript=None,
                       ripple_score=0.0, speaker=None):
            seen["transcript"] = list(transcript or [])
            return "reply"

        monkeypatch.setattr(consciousness, "speak", fake_speak)
        _post(f"{srv}/speak?key=sharedkey",
              {"node_name": real.name, "seed": 42,
               "message": "as ada", "player_name": "Ada"})
        # Same credential, different display name → same conversation.
        _post(f"{srv}/speak?key=sharedkey",
              {"node_name": real.name, "seed": 42,
               "message": "as bob now", "player_name": "Bob"})
        assert [t["user"] for t in seen["transcript"]] == ["as ada"]
