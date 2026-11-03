"""Player-reachable agent walks store nothing (2026-11-03 evaluation, R2).

`GET /agent` and `GET /observe` used to run world-writing FSM walks: every
request wrote permanent chronicle rows, ripple, property deltas, agent runs,
agent memory and first-use puzzle pins. #139 made the walker's name
server-owned (agents/identities.py); these tests pin the rest: `/agent` is a
simulation, `/observe` is a live walk streamed to its watcher, neither writes
anything, `/observe` never broadcasts its unapplied events as world events,
and walks take turns on the one Observer presence.
"""
from __future__ import annotations

import json
import threading
import urllib.parse
import urllib.request

import pytest

import persistence
from multiverse import store
from server import _Handler, _ThreadedServer
from server import handlers
from server.rooms import get_room

SEED = 382


@pytest.fixture
def base(monkeypatch):
    monkeypatch.setenv("NESTED_WORLDS_CANONICAL_SEED", str(SEED))
    server = _ThreadedServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)


def _nodes():
    root = store.world_tree(SEED)
    child = root.children[0]
    return root, child


class TestObserveIsLiveOnly:
    def test_a_requested_name_cannot_walk_the_room(self, base):
        root, _ = _nodes()
        query = urllib.parse.urlencode({"node_name": root.name, "name": "Tessera"})
        events = []
        with urllib.request.urlopen(f"{base}/observe?{query}", timeout=20) as resp:
            for raw in resp:
                if raw.startswith(b"data: "):
                    event = json.loads(raw[6:])
                    events.append(event)
                    if event.get("done"):
                        break
        assert events[-1]["nodes_visited"] > 0
        assert {e["agent"] for e in events if "agent" in e} == {"Observer"}
        assert persistence.get_mutations(SEED, limit=20) == []
        assert persistence.load_ripple_scores(SEED) == {}
        # Puzzles were resolved, never pinned: no question was opened.
        with persistence._connect() as conn:
            assert conn.execute("SELECT COUNT(*) FROM puzzle_instances").fetchone()[0] == 0
        # The live presence left with the walk.
        assert "Observer" not in get_room(SEED).active_agents

    def test_the_walk_is_streamed_to_the_watcher_not_broadcast_as_world_events(
            self, base, monkeypatch):
        # Nothing the walk fires is applied, so it must not reach the room as
        # a causal_event (clients render those as world events). Presence is
        # live fact and still goes out.
        sent = []
        real = handlers.broadcast
        monkeypatch.setattr(handlers, "broadcast",
                            lambda room, msg: sent.append(msg["type"]) or real(room, msg))
        root, _ = _nodes()
        with urllib.request.urlopen(
                f"{base}/observe?node_name={urllib.parse.quote(root.name)}",
                timeout=20) as resp:
            for raw in resp:
                if raw.startswith(b"data: ") and json.loads(raw[6:]).get("done"):
                    break
        assert "causal_event" not in sent
        assert "agent_done" in sent


class TestObservePinsNoPuzzle:
    def test_an_observe_walk_that_attempts_puzzles_opens_no_question(self, base):
        # Review of #141 (mutant M5): a walk must reach a puzzle for this to
        # mean anything, so pick a place where the observer attempts one.
        from agents.agent import Agent
        from causality import CausalityBus

        def walk(node):
            yield node
            for child in node.children:
                yield from walk(child)

        def attempts_puzzle(node):
            probe = Agent(name="Observer", danger_threshold=7, bus=CausalityBus())
            probe.traverse(node, max_nodes=40)
            return any("puzzle" in entry.action for entry in probe.log)

        target = next(n for n in walk(store.world_tree(SEED)) if attempts_puzzle(n))
        query = urllib.parse.urlencode({"node_name": target.name, "depth": 11})
        kinds = []
        with urllib.request.urlopen(f"{base}/observe?{query}", timeout=20) as resp:
            for raw in resp:
                if raw.startswith(b"data: "):
                    event = json.loads(raw[6:])
                    kinds.append(event.get("kind"))
                    if event.get("done"):
                        break
        assert any(k and k.startswith("PUZZLE") for k in kinds)
        with persistence._connect() as conn:
            assert conn.execute("SELECT COUNT(*) FROM puzzle_instances").fetchone()[0] == 0
        assert persistence.get_mutations(SEED, limit=5) == []


class TestSimulationPinsNoPuzzle:
    def test_agent_simulation_opens_no_question(self, base):
        with urllib.request.urlopen(
                f"{base}/agent?threshold=10&max_nodes=200", timeout=30) as resp:
            data = json.load(resp)
        assert any("puzzle" in e["action"] for e in data["events"])
        with persistence._connect() as conn:
            assert conn.execute("SELECT COUNT(*) FROM puzzle_instances").fetchone()[0] == 0


class TestObserverWalksTakeTurns:
    """Every walk is the one reserved Observer presence (review of #141)."""

    def test_overlapping_walks_never_share_the_presence(self, base, monkeypatch):
        import threading
        import time
        from server import rooms

        presence = []
        real_broadcast = rooms.broadcast

        def record(room, msg):
            if msg.get("type") in ("agent_enter", "agent_leave") and msg.get("name") == "Observer":
                presence.append(msg["type"])
            return real_broadcast(room, msg)
        monkeypatch.setattr(rooms, "broadcast", record)

        real_traverse = handlers.Agent.traverse

        def slow_traverse(self, *args, **kwargs):
            time.sleep(0.3)  # long enough for the two walks to overlap
            return real_traverse(self, *args, **kwargs)
        monkeypatch.setattr(handlers.Agent, "traverse", slow_traverse)

        root, _ = _nodes()
        done = []

        def watch():
            with urllib.request.urlopen(
                    f"{base}/observe?node_name={urllib.parse.quote(root.name)}",
                    timeout=20) as resp:
                for raw in resp:
                    if raw.startswith(b"data: "):
                        event = json.loads(raw[6:])
                        if event.get("done"):
                            done.append(event)
                            break

        walkers = [threading.Thread(target=watch) for _ in range(2)]
        for w in walkers:
            w.start()
        for w in walkers:
            w.join(30)
        assert len(done) == 2 and all(e["nodes_visited"] > 0 for e in done)
        assert presence == ["agent_enter", "agent_leave", "agent_enter", "agent_leave"]

    def test_a_watcher_who_cannot_get_a_turn_is_told_so(self, base, monkeypatch):
        monkeypatch.setattr(handlers, "_OBSERVE_WAIT_SEC", 0.05)
        room = get_room(SEED)
        assert room.observer_lock.acquire(timeout=1)
        try:
            root, _ = _nodes()
            with urllib.request.urlopen(
                    f"{base}/observe?node_name={urllib.parse.quote(root.name)}",
                    timeout=20) as resp:
                events = [json.loads(raw[6:]) for raw in resp if raw.startswith(b"data: ")]
        finally:
            room.observer_lock.release()
        assert events == [{"done": True, "nodes_visited": 0, "busy": True}]
        assert "Observer" not in room.active_agents
