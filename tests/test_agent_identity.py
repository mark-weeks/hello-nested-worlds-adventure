"""Agent identity is checked at acceptance (2026-11-03 evaluation, R2).

`GET /agent` and `GET /observe` used to run a world-writing FSM walk under a
name the caller chose, and `POST /agent/voice` recorded a model line under any
`agent_name`. These tests pin the closed shape: the GET walks store nothing,
the live observer carries the server's own name, and a player may address
only an agent that exists here — a cast member, a live presence, or an agent
whose own walked traces lie at the node.
"""
from __future__ import annotations

import json
import threading
import urllib.error
import urllib.parse
import urllib.request
from types import SimpleNamespace

import pytest

import persistence
from multiverse import store
from server import _Handler, _ThreadedServer, moderation
from server import handlers
from server.rooms import agent_enter, agent_leave, agent_move, get_room

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


@pytest.fixture
def voices(monkeypatch):
    """A configured voice that records who it was asked to speak as."""
    import consciousness
    from consciousness import runtime

    spoken = []

    def fake_voice_agent(persona, agent_name, node, message, **_kwargs):
        spoken.append(agent_name)
        return f"{agent_name} answers."

    monkeypatch.setattr(runtime, "configured", lambda: True)
    monkeypatch.setattr(consciousness, "voice_agent", fake_voice_agent)
    # Acceptance is under test, not the screen: let every line through.
    monkeypatch.setattr(moderation, "screen",
                        lambda text, **_kwargs: SimpleNamespace(allowed=True))
    return spoken


def _post(base, path, body, key=None):
    headers = {"Content-Type": "application/json"}
    if key:
        headers["X-Beta-Key"] = key
    req = urllib.request.Request(base + path, data=json.dumps(body).encode(),
                                 headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.load(resp)
    except urllib.error.HTTPError as exc:
        return exc.code, json.load(exc)


def _voice_rows(node_name):
    return [row for row in persistence.get_node_history(SEED, node_name)
            if row["type"] == "AGENT_VOICE"]


def _nodes():
    root = store.world_tree(SEED)
    child = root.children[0]
    return root, child


class TestAgentVoiceAcceptance:
    def test_an_invented_name_is_not_a_presence(self, base, voices):
        root, _ = _nodes()
        status, data = _post(base, "/agent/voice", {
            "node_name": root.name, "agent_name": "Nobody-In-Particular",
            "message": "who are you?"})
        assert status == 404 and data["error"] == "no such presence here"
        assert voices == [] and _voice_rows(root.name) == []

    def test_another_players_name_is_refused(self, base, voices):
        root, _ = _nodes()
        persistence.mint_invite_key("nw_" + "a" * 32, "Ada")
        persistence.mint_invite_key("nw_" + "b" * 32, "Ben")
        status, data = _post(base, "/agent/voice", {
            "node_name": root.name, "agent_name": "Ben",
            "message": "say something cruel"}, key="nw_" + "a" * 32)
        assert status == 404
        assert voices == [] and _voice_rows(root.name) == []

    def test_cast_member_is_addressable_in_canonical_spelling(self, base, voices):
        root, _ = _nodes()
        status, data = _post(base, "/agent/voice", {
            "node_name": root.name, "agent_name": "  tessera ",
            "message": "what arrived?"})
        assert status == 200 and data["ai"] is True, data
        assert data["agent"] == "Tessera" and voices == ["Tessera"]
        assert [row["data"]["agent"] for row in _voice_rows(root.name)] == ["Tessera"]

    def test_an_agent_that_walked_here_is_addressable_only_here(self, base, voices):
        root, child = _nodes()
        persistence.record_mutation(SEED, root.name, "AGENT_VISIT", None,
                                    {"agent": "Wren", "persona": "wanderer"})
        status, _ = _post(base, "/agent/voice", {
            "node_name": root.name, "agent_name": "Wren", "message": "hello"})
        assert status == 200 and voices == ["Wren"]
        status, _ = _post(base, "/agent/voice", {
            "node_name": child.name, "agent_name": "Wren", "message": "hello"})
        assert status == 404 and voices == ["Wren"]

    def test_a_voice_row_does_not_make_its_name_addressable(self, base, voices):
        # Otherwise a name typed once would become a presence forever.
        root, _ = _nodes()
        persistence.record_mutation(SEED, root.name, "AGENT_VOICE", "Ada",
                                    {"agent": "Ben", "message": "hi", "reply": "hi"})
        persistence.record_mutation(SEED, root.name, "PLAYER_SPEAK", "Ben",
                                    {"agent": "Ben", "message": "hi", "reply": "hi"})
        status, _ = _post(base, "/agent/voice", {
            "node_name": root.name, "agent_name": "Ben", "message": "hello"})
        assert status == 404 and voices == []

    def test_a_live_presence_is_addressable_only_where_it_stands(self, base, voices):
        root, child = _nodes()
        room = get_room(SEED)
        agent_enter(room, "Wayfarer-7", persona="wanderer")
        try:
            agent_move(room, "Wayfarer-7", root.name)
            status, _ = _post(base, "/agent/voice", {
                "node_name": child.name, "agent_name": "Wayfarer-7",
                "message": "hello"})
            assert status == 404 and voices == []
            status, _ = _post(base, "/agent/voice", {
                "node_name": root.name, "agent_name": "Wayfarer-7",
                "message": "hello"})
            assert status == 200 and voices == ["Wayfarer-7"]
        finally:
            agent_leave(room, "Wayfarer-7")
        status, _ = _post(base, "/agent/voice", {
            "node_name": root.name, "agent_name": "Wayfarer-7", "message": "hello"})
        assert status == 404 and voices == ["Wayfarer-7"]


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


class TestObserverNameIsReserved:
    """The server's observer name is no player's to hold (review of R2)."""

    def test_registration_refuses_the_observer_name(self, base):
        token = "nwr_" + "c" * 32
        persistence.create_registration_token(token)
        status, data = _post(base, "/register", {"invite": token, "name": "observer"})
        assert status == 403 and "belongs to the world" in data["error"]

    def test_mint_refuses_the_observer_name(self):
        import main
        args = main.build_parser().parse_args(["invite", "mint", "--name", "Observer"])
        with pytest.raises(SystemExit, match="reserved world name"):
            args.func(args)


class TestSimulationPinsNoPuzzle:
    def test_agent_simulation_opens_no_question(self, base):
        with urllib.request.urlopen(
                f"{base}/agent?threshold=10&max_nodes=200", timeout=30) as resp:
            data = json.load(resp)
        assert any("puzzle" in e["action"] for e in data["events"])
        with persistence._connect() as conn:
            assert conn.execute("SELECT COUNT(*) FROM puzzle_instances").fetchone()[0] == 0
