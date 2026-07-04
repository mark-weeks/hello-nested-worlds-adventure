"""The world heartbeat: ambient agent life that persists and broadcasts."""
from __future__ import annotations

import json
import random

import pytest

import persistence
from server import heartbeat
from server.rooms import Player, get_room


class _FakeSock:
    """Collects ws_send frames so a test can read what was broadcast."""

    def __init__(self):
        self.raw = b""

    def sendall(self, data):
        self.raw += data


def _decode_frames(raw: bytes) -> list[dict]:
    """Parse unmasked server frames (FIN + text, len ≤ 65535)."""
    out, i = [], 0
    while i + 2 <= len(raw):
        length = raw[i + 1] & 0x7F
        offset = i + 2
        if length == 126:
            length = int.from_bytes(raw[i + 2:i + 4], "big")
            offset = i + 4
        payload = raw[offset:offset + length]
        try:
            out.append(json.loads(payload))
        except json.JSONDecodeError:
            pass
        i = offset + length
    return out


class TestHeartbeatTick:
    def test_tick_leaves_persistent_traces(self):
        summary = heartbeat.run_tick(seed=42, rng=random.Random(1), pace=0.0)
        assert summary["seed"] == 42
        assert summary["fresh"] > 0

        # The run persisted: agent run row, agent memory, and node mutations.
        runs = persistence.get_agent_runs(42)
        assert any(r["agent_name"] == summary["agent"] for r in runs)
        memory = persistence.load_agent_memory(summary["agent"], 42)
        assert memory and len(memory["visited_ids"]) >= summary["fresh"]
        mutations = persistence.get_mutations(42)
        assert any(m["data"].get("agent") == summary["agent"] for m in mutations)

    def test_tick_broadcasts_to_live_players(self):
        room = get_room(42)
        sock = _FakeSock()
        with room.lock:
            room.players["watcher"] = Player(
                name="Watcher", seed=42, current_node="", session_id="watcher",
                sock=sock)
        heartbeat.run_tick(seed=42, rng=random.Random(2), pace=0.0)
        frames = _decode_frames(sock.raw)
        kinds = {f.get("type") for f in frames}
        assert "causal_event" in kinds, "live players must see the agent move"
        assert "agent_done" in kinds
        causal = [f for f in frames if f.get("type") == "causal_event"]
        # Strengths are the events' real propagated strengths in (0, 1].
        assert all(0 < f["strength"] <= 1.0 for f in causal)
        assert all(f.get("agent") for f in causal)

    def test_agent_leaves_room_registry_after_tick(self):
        room = get_room(42)
        summary = heartbeat.run_tick(seed=42, rng=random.Random(3), pace=0.0)
        with room.lock:
            assert summary["agent"] not in room.active_agents

    def test_memory_accretes_across_ticks(self):
        # The same roster name returning to the same world continues into
        # fresh ground instead of re-walking (or bricking on) known nodes.
        rng = random.Random(4)
        first = heartbeat.run_tick(seed=7, rng=rng, pace=0.0)
        known_after_first = len(
            persistence.load_agent_memory(first["agent"], 7)["visited_ids"])
        # Force the same agent by monkey-free trick: run ticks until the same
        # name comes up again (roster is small, rng deterministic here).
        for _ in range(20):
            nxt = heartbeat.run_tick(seed=7, rng=rng, pace=0.0)
            if nxt["agent"] == first["agent"]:
                known_now = len(
                    persistence.load_agent_memory(first["agent"], 7)["visited_ids"])
                assert known_now >= known_after_first
                return
        pytest.skip("same roster agent did not recur within 20 ticks")

    def test_interval_env_parsing(self, monkeypatch):
        monkeypatch.setenv(heartbeat.INTERVAL_ENV, "45")
        assert heartbeat.interval_seconds() == 45.0
        monkeypatch.setenv(heartbeat.INTERVAL_ENV, "bogus")
        assert heartbeat.interval_seconds() == heartbeat._DEFAULT_INTERVAL
        monkeypatch.setenv(heartbeat.DISABLE_ENV, "0")
        assert heartbeat.enabled() is False
