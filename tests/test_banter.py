"""Agent-to-agent life: co-located wanderers converse, and the conversation
persists — the world generates stories that later arrivals can find.
"""
from __future__ import annotations

import json
import random

import persistence
from agents.banter import compose_exchange
from multiverse.node import SpatialNode
from server import heartbeat
from server.rooms import Player, get_room
from tests.test_heartbeat import _decode_frames, _FakeSock


def _node(name="Vault-1121", level="Room", props=None, ripple=0.0):
    n = SpatialNode(name, level, properties=props or {})
    n.ripple_score = ripple
    return n


class TestComposeExchange:
    def test_deterministic(self):
        args = (42, _node(), "Tessera", "scholar", "Brann", "tender")
        assert compose_exchange(*args) == compose_exchange(*args)

    def test_ordinal_makes_the_next_meeting_different(self):
        node = _node()
        first = compose_exchange(42, node, "Tessera", "scholar",
                                 "Brann", "tender", ordinal=0)
        second = compose_exchange(42, node, "Tessera", "scholar",
                                  "Brann", "tender", ordinal=1)
        assert first != second

    def test_shape_speakers_and_stage_direction(self):
        lines = compose_exchange(1, _node(), "A", "wanderer", "B", "destabilizer")
        assert len(lines) == 3
        assert lines[0]["speaker"] == "A" and lines[0]["persona"] == "wanderer"
        assert lines[1]["speaker"] == "B" and lines[1]["persona"] == "destabilizer"
        assert lines[2]["speaker"] == ""  # closing stage direction
        assert all(l["line"] for l in lines)

    def test_grounded_in_the_nodes_actual_state(self):
        node = _node(props={"danger_level": 8})
        lines = compose_exchange(3, node, "A", "tender", "B", "scholar")
        text = " ".join(l["line"] for l in lines)
        assert "danger here reads 8" in text

    def test_unknown_persona_falls_back_to_wanderer_voice(self):
        lines = compose_exchange(5, _node(), "A", "glitch", "B", "???")
        assert len(lines) == 3 and all(l["line"] for l in lines)


class TestHeartbeatConversations:
    def test_hold_conversation_persists_and_broadcasts(self):
        room = get_room(555)
        sock = _FakeSock()
        with room.lock:
            room.players["w"] = Player(name="W", seed=555, current_node="",
                                       session_id="w", sock=sock)
        node = _node("Spire-11", "Region", {"danger_level": 7})

        heartbeat._hold_conversation(555, room, node,
                                     "Tessera", "scholar", "Brann", "tender")

        talks = [h for h in persistence.get_node_history(555, "Spire-11", 10)
                 if h["type"] == "AGENT_TALK"]
        assert len(talks) == 1
        assert talks[0]["data"]["a"] == "Tessera"
        assert len(talks[0]["data"]["lines"]) == 3

        frames = _decode_frames(sock.raw)
        talk_frames = [f for f in frames if f.get("type") == "agent_talk"]
        assert talk_frames and talk_frames[0]["node"] == "Spire-11"
        assert len(talk_frames[0]["lines"]) == 3

        # A second meeting at the same node advances the ordinal → new words.
        heartbeat._hold_conversation(555, room, node,
                                     "Tessera", "scholar", "Brann", "tender")
        talks = [h for h in persistence.get_node_history(555, "Spire-11", 10)
                 if h["type"] == "AGENT_TALK"]
        assert len(talks) == 2
        assert talks[0]["data"]["lines"] != talks[1]["data"]["lines"]

    def test_social_tick_produces_a_recorded_conversation(self):
        # rng seed 7 deterministically takes the companion branch on world
        # 4242 (roster pick → drop-in walk → social roll all seeded).
        heartbeat.run_tick(seed=4242, rng=random.Random(7), pace=0.0)
        talks = [h for h in persistence.get_mutations(4242, limit=200)
                 if h["type"] == "AGENT_TALK"]
        assert talks, "the social tick must leave a conversation in history"
        data = talks[0]["data"]
        assert data["a"] != data["b"]
        assert len(data["lines"]) == 3

    def test_companion_leaves_registry_after_tick(self):
        room = get_room(4243)
        heartbeat.run_tick(seed=4243, rng=random.Random(7), pace=0.0)
        with room.lock:
            assert not room.active_agents


class TestNodeVoiceOverhearsTalk:
    def test_history_block_renders_the_conversation(self):
        from consciousness import _history_block
        history = [{
            "type": "AGENT_TALK", "player": None, "at": "2026-07-05 01:00:00",
            "data": {"a": "Tessera", "b": "Brann",
                     "lines": [
                         {"speaker": "Tessera", "persona": "scholar",
                          "line": "Note the anomaly."},
                         {"speaker": "Brann", "persona": "tender",
                          "line": "Then help me steady it."},
                         {"speaker": "", "persona": "", "line": "They part."},
                     ]},
        }]
        block = _history_block(history)
        assert "overheard Tessera and Brann" in block
        assert 'Tessera: "Note the anomaly."' in block
        assert "They part." not in block  # stage directions aren't speech
