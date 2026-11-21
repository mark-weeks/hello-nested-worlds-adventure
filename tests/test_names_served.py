"""ADR-041 on the server: a name is a label, the address and the identity
key travel as their own fields, and no keyed draw moved with the names.

- /world, /node and /wayback carry `address` (digits form) and `key`.
- GET /position, /world's entry and wrap landings, presence frames, the
  journal, the interventions list and the investigation carry the address
  beside each name a client may go to.
- A world born under generator version 2 keeps its stored names; its key is
  the stored name alone.
- The cast's attempt roll, the banter key and the verb token take the key,
  which is the string a version-2 name was.
"""
from __future__ import annotations

import json
import threading
import urllib.parse
import urllib.request

import pytest

import persistence
from agents.agent import Agent
from agents.banter import compose_exchange
from multiverse import naming, store
from multiverse.node import SpatialNode
from multiverse.situation import NODES
from server import _Handler, _ThreadedServer, rooms
from server.world_mechanics import entangled_twin, node_addresses

SEED = 5150
V2_SEED = 5151


@pytest.fixture()
def srv():
    server = _ThreadedServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def _get(url):
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read())


def _post(url, body):
    request = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read())


def _walk(node, parent=None):
    yield node, parent
    for child in node.get("children", []):
        yield from _walk(child, node)


def _tree_nodes(root):
    yield root
    for child in root.children:
        yield from _tree_nodes(child)


def _v2_twin(node):
    """The node as generator version 2 named it: a hand-built place whose
    name ends in its path digits and that carries no key or address."""
    return SpatialNode(f"{node.name}-{node.address}", node.level,
                       properties=dict(node.properties))


def _v2_tree(node):
    """The whole subtree as generator version 2 named it."""
    twin = _v2_twin(node)
    for child in node.children:
        twin.add_child(_v2_tree(child))
    return twin


class TestNodePayloads:
    def test_world_carries_the_address_and_the_key_of_every_node(self, srv):
        data = _get(f"{srv}/world?seed={SEED}&depth=6")
        nodes = list(_walk(data["world"]))
        assert len(nodes) == data["node_count"] > 100
        assert data["world"]["address"] == "1"
        for node, parent in nodes:
            assert node["address"].isdigit()
            assert not any(ch.isdigit() or ch == "-" for ch in node["name"])
            # The key is the name generator version 2 stored (ADR-041 D4).
            assert node["key"] == f'{node["name"]}-{node["address"]}'
            if parent is not None:
                ordinal = parent["children"].index(node) + 1
                assert node["address"] == parent["address"] + str(ordinal)
        assert len({node["name"] for node, _ in nodes}) == len(nodes)
        assert len({node["address"] for node, _ in nodes}) == len(nodes)

    def test_world_carries_the_address_of_each_wrap_landing(self, srv):
        wrap = _get(f"{srv}/world?seed={SEED}&depth=2")["wrap"]
        assert wrap["root_address"] == "1"
        # The hinge is a leaf of the full world, far below this view.
        assert len(wrap["hinge_address"]) == 11
        assert store.node_at(SEED, wrap["hinge_address"]).name == wrap["hinge"]

    def test_node_and_wayback_carry_them_for_a_place_outside_any_view(self, srv):
        deep = next(node for node in _tree_nodes(store.world_tree(seed=SEED, max_depth=9))
                    if len(node.address) == 9)
        quoted = urllib.parse.quote(deep.name)
        served = _get(f"{srv}/node?seed={SEED}&node_name={quoted}")["node"]
        assert (served["address"], served["key"]) == (
            deep.address, f"{deep.name}-{deep.address}")
        past = _get(f"{srv}/wayback?seed={SEED}&node_name={quoted}")["node"]
        assert (past["name"], past["address"], past["key"]) == (
            deep.name, deep.address, served["key"])

    def test_a_world_born_under_version_two_keys_on_its_stored_name(self, srv):
        from multiverse.generator import generate_node_hierarchy
        born = list(_tree_nodes(generate_node_hierarchy(seed=V2_SEED, max_depth=11)))
        rows = [(naming.dotted_of(n.address), f"{n.name}-{n.address}", n.level,
                 json.dumps(n.properties, ensure_ascii=False), len(n.children))
                for n in born]
        assert persistence.save_world_nodes(V2_SEED, rows, 2) == len(rows)
        data = _get(f"{srv}/world?seed={V2_SEED}&depth=4")
        served = [node for node, _ in _walk(data["world"])]
        assert len(served) > 10
        for node in served:
            # Appending the address again would move every keyed draw.
            assert node["key"] == node["name"]
            assert node["name"].endswith("-" + node["address"])
        assert data["wrap"]["hinge"].endswith("-" + data["wrap"]["hinge_address"])
        deep = next(n for n in born if len(n.address) == 8)
        stored = f"{deep.name}-{deep.address}"
        got = _get(f"{srv}/node?seed={V2_SEED}&node_name="
                   + urllib.parse.quote(stored))["node"]
        assert (got["name"], got["address"], got["key"]) == (stored, deep.address, stored)


class TestAddressesBesideNames:
    def test_node_addresses_reads_stored_names_and_births_nothing(self):
        assert node_addresses(SEED, ["Nowhere At All"]) == {}
        assert persistence.world_generator_version(SEED) is None  # still unborn
        root = store.world_tree(seed=SEED, max_depth=3)
        child = root.children[0]
        assert node_addresses(SEED, [root.name, child.name, None, "", "Forged-11",
                                     child.name]) == {root.name: "1", child.name: "11"}
        assert node_addresses(None, [root.name]) == {}

    def test_presence_frames_carry_the_address(self):
        root = store.world_tree(seed=SEED, max_depth=3)
        galaxy = root.children[0].children[0]
        room = rooms.get_room(SEED)
        frames = []
        player = rooms.Player(name="Ada", seed=SEED, current_node=root.name,
                              session_id="s1", sock=None)
        player.send = lambda message, **_: frames.append(message) or True
        with room.lock:
            room.players["s1"] = player
        rooms.agent_enter(room, "Tessera")
        rooms.agent_move(room, "Tessera", galaxy.name)
        moved = frames[-1]
        assert (moved["type"], moved["name"], moved["node"], moved["address"]) == (
            "agent_move", "Tessera", galaxy.name, "111")
        assert rooms.snapshot(room) == [
            {"name": "Ada", "node": root.name, "address": "1", "session_id": "s1"}]
        (agent,) = rooms.agents_snapshot(room)
        assert (agent["node"], agent["address"]) == (galaxy.name, "111")
        # A name this world does not hold has no address to send.
        rooms.agent_move(room, "Tessera", "Nowhere At All")
        assert frames[-1]["address"] is None

    def test_the_journal_the_investigation_and_the_recent_list_carry_them(self, http):
        from persistence import situations
        situations.install(382)
        status, data, _ = http("/situation?seed=382")
        assert status == 200
        names = [data["situation"]["entry"], *data["situation"]["nodes"].values()]
        assert set(data["addresses"]) == set(names)
        for name in names:
            assert store.node_at(382, data["addresses"][name]).name == name

        place = NODES["instrument"]
        address = store.address_of(382, place)
        assert http("/position", body={"node": place, "seed": 382, "depth": 9})[0] == 200
        status, position, _ = http("/position")
        assert position["position"]["node"] == place
        assert position["position"]["address"] == address

        assert http("/journal/note", body={
            "seed": 382, "node": place, "text": "a note", "id": "note-0001"})[0] == 200
        assert http("/profile/home", body={"seed": 382, "node": place})[0] == 200
        status, journal, _ = http("/journal/data?seed=382")
        assert status == 200
        assert journal["notes"][0]["node"] == journal["profile"]["home"]["node"] == place
        assert journal["addresses"] == {place: address}

        status, recent, _ = http("/interventions?node=" + urllib.parse.quote(place))
        assert status == 200
        assert recent["addresses"][place] == address


class TestKeyedDrawsDidNotMove:
    """Each derivation gives a version-3 place what it gave the same place
    under its version-2 name."""

    def _places(self):
        root = store.world_tree(seed=SEED, max_depth=6)
        return [node for node in _tree_nodes(root)]

    def test_the_cast_attempt_roll(self):
        root = store.world_tree(seed=SEED, max_depth=6)
        pairs = list(zip(_tree_nodes(root), _tree_nodes(_v2_tree(root))))
        outcomes = set()
        for name in ("Tessera", "Halden", "The Locksmith"):
            for node, twin in pairs[:120]:
                for epoch in (0, 2):
                    now = Agent(name=name)._attempt_puzzle(node, epoch=epoch)
                    assert now == Agent(name=name)._attempt_puzzle(
                        twin, epoch=epoch), (name, node.name, epoch)
                    outcomes.add(now[0])
        assert outcomes == {True, False}  # the roll is exercised both ways

    def test_the_banter_exchange(self):
        seen = set()
        for node in self._places()[:80]:
            for ordinal in (0, 1):
                now = compose_exchange(SEED, node, "Tessera", "tender",
                                       "Vex", "destabilizer", ordinal)
                assert now == compose_exchange(
                    SEED, _v2_twin(node), "Tessera", "tender",
                    "Vex", "destabilizer", ordinal), node.name
                seen.add(json.dumps(now))
        assert len(seen) > 20  # exchanges do vary with the place

    def test_the_verb_token_of_a_player_act(self, srv, monkeypatch):
        from server import handlers
        tokens = []
        real = handlers.accept_verb

        def recording(seed, node, verb, token, *args, **kwargs):
            tokens.append(token)
            return real(seed, node, verb, token, *args, **kwargs)

        monkeypatch.setattr(handlers, "accept_verb", recording)
        root = store.world_tree(seed=SEED, max_depth=3)
        target = root.children[0]
        result = _post(f"{srv}/act", {"seed": SEED, "depth": 3,
                                      "node_name": target.name, "player_name": "Ada"})
        assert result["action_status"] == "accepted"
        assert tokens == [f"Ada:{target.name}-{target.address}"]

    def test_the_verb_token_of_a_cast_act(self, monkeypatch):
        from server import heartbeat
        tokens = []
        real = heartbeat.accept_verb

        def recording(seed, node, verb, token, *args, **kwargs):
            tokens.append((node.name, token))
            return real(seed, node, verb, token, *args, **kwargs)

        monkeypatch.setattr(heartbeat, "accept_verb", recording)
        monkeypatch.setenv("NESTED_WORLDS_HOP_DELAY", "0")
        import random
        root = store.world_tree(seed=SEED, max_depth=4)
        visited = [node.name for node in _tree_nodes(root)][:12]
        heartbeat._persona_act(SEED, rooms.get_room(SEED), root, "Tessera", "tender",
                               visited, random.Random(3), chance=False)
        assert tokens
        for name, token in tokens:
            agent, _, key = token.partition(":")
            assert agent == "Tessera"
            assert key == f"{name}-{store.address_of(SEED, name)}"


class TestEntanglementReadsTheAddress:
    def test_twins_pair_by_position_in_both_generations(self):
        root = store.world_tree(seed=SEED, max_depth=11)
        particles = [node for node in _tree_nodes(root)
                     if node.level == "SubatomicParticle"]
        paired = [(node, entangled_twin(node)) for node in particles]
        paired = [(node, twin) for node, twin in paired if twin is not None]
        assert paired
        for node, twin in paired:
            last = int(node.address[-1])
            wanted = node.address[:-1] + str(last + 1 if last % 2 else last - 1)
            assert twin.address == wanted and twin.parent is node.parent
        # The same ring as version 2 named it pairs the same way.
        node, twin = paired[0]
        ring = SpatialNode("Old Ring-1", node.parent.level)
        old = {child.address: _v2_twin(child) for child in node.parent.children}
        for child in old.values():
            ring.add_child(child)
        found = entangled_twin(old[node.address])
        assert found is not None
        assert naming.node_address(found) == twin.address


class TestVerbTokensOutsideTheServer:
    """The CLI verb and the intervention interpreter hash the identity key
    too, so a place answers the same there as through POST /act and as it
    did under its version-2 name (ADR-041 D4)."""

    def test_the_verb_token_of_a_cli_act(self, monkeypatch):
        import interface
        from causality import delivery
        tokens = []
        real = delivery.accept_verb

        def recording(seed, node, verb, token, *args, **kwargs):
            tokens.append(token)
            return real(seed, node, verb, token, *args, **kwargs)

        monkeypatch.setattr(delivery, "accept_verb", recording)
        root = store.world_tree(seed=SEED, max_depth=3)
        target = root.children[0]
        interface._do_scale_verb(target, SEED, "Ada")
        assert tokens == [f"Ada:{target.name}-{target.address}"]

    def test_an_intervention_plan_keys_on_the_identity_key(self, monkeypatch):
        from multiverse import interventions_v2
        from persistence import interventions
        seen = []

        def recording(props, steps, level, token):
            seen.append(token)
            return {"state": "calm", "changed": {}}

        monkeypatch.setattr(interventions_v2, "simulate", recording)
        root = store.world_tree(seed=SEED, max_depth=3)
        node = root.children[0]
        twin = _v2_twin(node)
        interventions._plan(interventions_v2, {}, [], node)
        interventions._plan(interventions_v2, {}, [], twin)
        assert seen == [f"{node.name}-{node.address}"] * 2
        assert twin.name == f"{node.name}-{node.address}"  # the twin is a real v2 name


class TestManyAddressesInOneRead:
    """A journal can name a hundred places. Their addresses come from one
    connection, and the mapping is what one read per name gave."""

    @staticmethod
    def _one_read_per_name(seed, names):
        found = {}
        for name in dict.fromkeys(names):
            if not name or not isinstance(name, str):
                continue
            row = persistence.get_world_node_address(seed, name)
            if row is not None:
                found[name] = naming.digits_of(row[0])
        return found

    def test_the_mapping_is_unchanged_and_one_connection_is_opened(self, monkeypatch):
        root = store.world_tree(seed=SEED, max_depth=6)
        places = [node.name for node in _tree_nodes(root)]
        assert len(places) > 150
        # Out of path order, repeated, with unknown names and non-names.
        asked = [*places[140:40:-1], "Nowhere At All", None, "", 7, places[41],
                 "Forged-11", *places[41:60], "nowhere at all", places[0]]
        assert len({name for name in asked if isinstance(name, str) and name}) > 100
        expected = self._one_read_per_name(SEED, asked)
        assert len(expected) == 101 and "Nowhere At All" not in expected

        opened = []
        connect = persistence._connect

        def counting(*args, **kwargs):
            opened.append(1)
            return connect(*args, **kwargs)

        monkeypatch.setattr(persistence, "_connect", counting)
        found = node_addresses(SEED, asked)
        assert len(opened) == 1
        assert found == expected
        assert list(found) == list(expected)  # the same order: first asked first

    def test_the_helper_returns_path_and_version_for_known_names_only(self):
        root = store.world_tree(seed=SEED, max_depth=3)
        child = root.children[1]
        assert persistence.get_world_node_addresses(SEED, [child.name, "Nowhere", root.name]) == {
            child.name: persistence.get_world_node_address(SEED, child.name),
            root.name: persistence.get_world_node_address(SEED, root.name)}
        assert persistence.get_world_node_addresses(SEED, []) == {}
        # Another world's names are not this world's.
        assert persistence.get_world_node_addresses(SEED + 1, [root.name]) == {}

    def test_more_names_than_one_statement_binds(self):
        root = store.world_tree(seed=SEED, max_depth=6)
        places = [node.name for node in _tree_nodes(root)]
        asked = [*places, *(f"Unknown Place {i}" for i in range(2000))]
        assert node_addresses(SEED, asked) == self._one_read_per_name(SEED, places)

    def test_an_unborn_world_is_not_born_by_the_read(self):
        assert node_addresses(SEED + 2, ["Nowhere At All", "Elsewhere"]) == {}
        assert persistence.world_generator_version(SEED + 2) is None


class TestAddressReadsStayOutOfTheRoomLock:
    """A roster is built from the positions the room holds. Where an
    address must still be read, the read is made with no lock held, so a
    slow one never stops another participant's move."""

    @staticmethod
    def _slow_reads(monkeypatch, slow_names):
        """Make the stored-address read of `slow_names` wait until released.
        Returns (entered, release, names read slowly)."""
        entered, release, read = threading.Event(), threading.Event(), []
        real = persistence.get_world_node_address

        def delayed(seed, name):
            if name in slow_names:
                read.append(name)
                entered.set()
                assert release.wait(10), "the slow read was never released"
            return real(seed, name)

        monkeypatch.setattr(persistence, "get_world_node_address", delayed)
        return entered, release, read

    def test_a_slow_read_for_a_roster_does_not_hold_the_room(self, monkeypatch):
        root = store.world_tree(seed=SEED, max_depth=3)
        galaxy = root.children[0].children[0]
        room = rooms.get_room(SEED)
        # A position recorded without its address: the one case left to read.
        ada = rooms.Player(name="Ada", seed=SEED, current_node=root.name,
                           session_id="s1", sock=None)
        ada.send = lambda message, **_: True
        with room.lock:
            room.players["s1"] = ada
        rooms.agent_enter(room, "Tessera")
        entered, release, _ = self._slow_reads(monkeypatch, {root.name})

        rosters = []
        reader = threading.Thread(
            target=lambda: rosters.append((rooms.snapshot(room), rooms.agents_snapshot(room))))
        reader.start()
        assert entered.wait(5)
        moved = []
        mover = threading.Thread(
            target=lambda: moved.append(rooms.agent_move(room, "Tessera", galaxy.name)))
        mover.start()
        mover.join(2)
        try:
            assert not mover.is_alive(), "a move waited on another's address read"
            assert moved == [[]] and reader.is_alive()
            assert room.lock.acquire(timeout=1)
            room.lock.release()
        finally:
            release.set()
            reader.join(5)
            mover.join(5)
        (players, agents), = rosters
        assert players == [{"name": "Ada", "node": root.name, "address": "1",
                            "session_id": "s1"}]
        assert [(a["name"], a["node"], a["address"]) for a in agents] == [
            ("Tessera", galaxy.name, "111")]

    def test_a_join_with_a_slow_read_does_not_delay_another_players_move(
            self, srv, monkeypatch):
        from tests.test_day_one_recording import _ws_connect, _ws_send_json
        from tests.test_ws_credential_lifetime import _until_type
        port = int(srv.rsplit(":", 1)[1])
        root = store.world_tree(seed=SEED, max_depth=4)
        galaxy = root.children[0].children[0]
        system = galaxy.children[0]
        universe = root.children[0]
        sockets = []

        def join(name):
            sock, status = _ws_connect(port, SEED, name)
            assert b"101" in status
            sockets.append(sock)
            return sock, _until_type(sock, "welcome")[0]

        try:
            ada, _ = join("Ada")
            bea, _ = join("Bea")
            _until_type(ada, "player_join")
            _ws_send_json(ada, {"type": "move", "node": galaxy.name})
            assert _until_type(bea, "player_move")[0]["address"] == "111"
            # A position recorded without its address, as a test or an older
            # caller may leave one: the only read a join still has to make.
            room = rooms.get_room(SEED)
            ghost = rooms.Player(name="Ghost", seed=SEED, current_node=system.name,
                                 session_id="ghost", sock=None)
            ghost.send = lambda message, **_: True
            with room.lock:
                room.players["ghost"] = ghost
            entered, release, read = self._slow_reads(
                monkeypatch, {galaxy.name, system.name})

            welcomes = []
            joiner = threading.Thread(target=lambda: welcomes.append(join("Cleo")[1]))
            joiner.start()
            assert entered.wait(5)
            try:
                # Cleo's join is waiting on a read. Bea still moves, and Ada
                # still hears of it.
                _ws_send_json(bea, {"type": "move", "node": universe.name})
                moved = _until_type(ada, "player_move", timeout=2.0)[0]
                assert (moved["name"], moved["node"], moved["address"]) == (
                    "Bea", universe.name, "11")
                assert joiner.is_alive() and welcomes == []
            finally:
                release.set()
                joiner.join(10)
            # Ada's place was never read again: her move recorded its address.
            assert read == [system.name]
            (welcome,) = welcomes
            assert {(p["name"], p["node"], p["address"]) for p in welcome["players"]} == {
                ("Ada", galaxy.name, "111"), ("Bea", universe.name, "11"),
                ("Ghost", system.name, "1111"), ("Cleo", root.name, "1")}
        finally:
            for sock in sockets:
                sock.close()
