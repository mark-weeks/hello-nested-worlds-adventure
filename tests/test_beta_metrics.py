"""Pilot measurement: what the pilot depends on, and the read of it.

The first half drives a scratch copy of the canonical world through the real
HTTP and WebSocket paths with minted per-user keys and pins the multi-player
behaviours the beta checklist gates on:

  * C6: two keyed travelers find each other in the welcome roster, chat,
    and co-solve one puzzle with credit under their registered names;
  * C4: one traveler's solve and Act reach the other live, as broadcast
    frames, and again after a reload, over HTTP;
  * C2a: a solve answers the solver with a visible effect (credit and the
    changed properties).

Publication is proven by the frames another socket receives and by HTTP
responses, never by reading a PLAYER_CHAT row back.

The second half reads the worlds those paths leave with
``scripts/beta_metrics.py`` (checklist B2): an Act-only tester acted, the
move every client sends on connect is not an action, a failed puzzle counts
once where it first failed however many wrong guesses follow, a rotated key
is one visitor, ``--exclude-identity`` drops the facilitator under every
key, ``--since``/``--until`` read an archive without changing it, and
``--timeline`` names nobody.

Sockets that stand for a browser announce their node right after the
welcome, as both shipped clients do on every (re)connect.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import socket
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

import persistence
from multiverse import store
from multiverse.situation import NODES
from persistence import participants
from puzzles.engine import PuzzleEngine
from server import observability
from tests.test_server_protocol import _client_frame

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import beta_metrics  # noqa: E402

SEED = 382


# ── A real server, real sockets ──────────────────────────────────────────────


class _Socket:
    """A keyed WebSocket client that keeps every frame it has read."""

    def __init__(self, sock: socket.socket, status: bytes) -> None:
        self.sock = sock
        self.status = status
        self.buf = b""
        self.frames: list[dict] = []

    def send(self, message: dict) -> None:
        self.sock.sendall(_client_frame(json.dumps(message).encode()))

    def _parse(self) -> None:
        while len(self.buf) >= 2:
            opcode, length, head = self.buf[0] & 0x0F, self.buf[1] & 0x7F, 2
            if length == 126:
                if len(self.buf) < 4:
                    return
                length, head = int.from_bytes(self.buf[2:4], "big"), 4
            elif length == 127:
                if len(self.buf) < 10:
                    return
                length, head = int.from_bytes(self.buf[2:10], "big"), 10
            if len(self.buf) < head + length:
                return
            payload = self.buf[head:head + length]
            self.buf = self.buf[head + length:]
            if opcode == 0x1:
                self.frames.append(json.loads(payload))

    def wait_for(self, predicate, timeout: float = 5.0) -> dict:
        deadline = time.monotonic() + timeout
        while True:
            for frame in self.frames:
                if predicate(frame):
                    return frame
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AssertionError(
                    f"no matching frame among {[f.get('type') for f in self.frames]}")
            self.sock.settimeout(min(remaining, 0.25))
            try:
                chunk = self.sock.recv(65536)
            except (socket.timeout, TimeoutError):
                continue
            if not chunk:
                raise AssertionError("the server closed the socket")
            self.buf += chunk
            self._parse()

    def close(self) -> None:
        self.sock.close()


class _World:
    def __init__(self, port: int) -> None:
        self.port = port
        self.sockets: list[_Socket] = []

    def mint(self, name: str) -> str:
        """A per-user key as `main.py invite mint` makes one."""
        key = "nw_" + secrets.token_hex(16)
        persistence.mint_invite_key(key, name)
        return key

    def request(self, path: str, key: str, body: dict | None = None):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=json.dumps(body).encode() if body is not None else None,
            headers={"X-Beta-Key": key, "Content-Type": "application/json"})
        try:
            response = urllib.request.urlopen(req, timeout=10)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            return response.status, json.load(response)

    def connect(self, key: str, name: str = "Mallory") -> _Socket:
        """Upgrade with ?key=; the client-sent name is a decoy the server
        must ignore for a keyed socket."""
        sock = socket.create_connection(("127.0.0.1", self.port), timeout=5)
        query = urllib.parse.urlencode({"seed": SEED, "name": name, "key": key})
        sock.sendall((
            f"GET /ws?{query} HTTP/1.1\r\nHost: t\r\n"
            "Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {base64.b64encode(os.urandom(16)).decode()}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n").encode())
        # Byte by byte to the blank line: the welcome frame may share the
        # segment and must stay for the frame reader.
        head = b""
        while not head.endswith(b"\r\n\r\n"):
            chunk = sock.recv(1)
            if not chunk:
                break
            head += chunk
        client = _Socket(sock, head.split(b"\r\n", 1)[0])
        self.sockets.append(client)
        return client

    def arrive(self, key: str) -> tuple[_Socket, dict]:
        """Connect as a browser does: on open, both shipped clients send a
        move for the node they show (static/explorer.js ws.onopen,
        frontend/src/App.jsx once connected), with no player input."""
        client = self.connect(key)
        welcome = client.wait_for(lambda f: f["type"] == "welcome")
        self.announce(client, key, _own_node(welcome))
        return client, welcome

    def announce(self, client: _Socket, key: str, node: str) -> None:
        """Send a connect-time move and wait for its row, so its join is
        recorded before the next arrival and arrival order is fixed."""
        before = _recorded(_identity(key), "PLAYER_MOVE")
        client.send({"type": "move", "node": node})
        deadline = time.monotonic() + 5
        while _recorded(_identity(key), "PLAYER_MOVE") == before:
            assert time.monotonic() < deadline, "the move was not recorded"
            time.sleep(0.02)

    def open_puzzle(self, key: str, node: str) -> dict:
        status, opened = self.request(
            "/puzzle?node_name=" + urllib.parse.quote(node), key)
        assert status == 200 and opened["found"], opened
        return opened

    def attempt(self, key: str, node: str, puzzle: str, answer: str) -> dict:
        status, result = self.request("/puzzle/attempt", key, {
            "node_name": node, "puzzle_name": puzzle, "answer": answer,
            "player_name": "Mallory"})
        assert status == 200, result
        return result

    def act(self, key: str, node: str, request_id: str) -> dict:
        status, _ = self.request(
            "/position", key, {"node": node, "seed": SEED, "depth": 9})
        assert status == 200
        status, receipt = self.request("/interventions/commit", key, {
            "node": node, "steps": [{"op": "engrave"}], "version": 3,
            "request_id": request_id})
        assert status == 200 and receipt["accepted"], receipt
        return receipt


def _own_node(welcome: dict) -> str:
    """The node the server placed this socket on, from its welcome roster."""
    return next(p["node"] for p in welcome["players"]
                if p["session_id"] == welcome["session_id"])


def _answer(node_name: str) -> str:
    """The server's current answer, read server-side as the handler reads
    it. Tests only: no client path returns it before a failure."""
    target = store.resolve_node_by_name(SEED, node_name)
    engine = PuzzleEngine(seed=SEED)
    engine.attach_puzzles(target, persistence.count_rearms_by_node(SEED),
                          persist=True, recursive=False)
    return engine.collect_puzzles(target)[0].answer


def _departures() -> int:
    """PLAYER_LEAVE rows written by this run's sockets (a row a test wrote
    with an earlier time is not one)."""
    with sqlite3.connect(f"file:{persistence._DB_PATH}?mode=ro", uri=True) as conn:
        return conn.execute(
            """SELECT COUNT(*) FROM world_mutations
               WHERE mutation_type = 'PLAYER_LEAVE'
                 AND recorded_at >= datetime('now', '-1 hour')""").fetchone()[0]


def _recorded(identity: str, kind: str) -> int:
    with sqlite3.connect(f"file:{persistence._DB_PATH}?mode=ro", uri=True) as conn:
        return conn.execute(
            """SELECT COUNT(*) FROM world_mutations
               WHERE actor_identity = ? AND mutation_type = ?""",
            (identity, kind)).fetchone()[0]


def _settle(world: _World) -> None:
    """Close every socket and wait until each departure is recorded."""
    for client in world.sockets:
        client.close()
    upgraded = sum(1 for client in world.sockets
                   if client.status.split()[1:2] == [b"101"])
    deadline = time.monotonic() + 5
    while _departures() < upgraded:
        assert time.monotonic() < deadline, "a departure was not recorded"
        time.sleep(0.02)


def _identity(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()[:16]


@pytest.fixture
def world(monkeypatch):
    monkeypatch.setenv("NESTED_WORLDS_CANONICAL_SEED", str(SEED))
    monkeypatch.setenv("NESTED_WORLDS_DISABLE_AI", "1")
    monkeypatch.setenv("NESTED_WORLDS_DISABLE_IMAGES", "1")
    monkeypatch.setenv("NESTED_WORLDS_HOP_DELAY", "0")
    # One test makes more puzzle and Act requests than a player's minute.
    monkeypatch.setenv("NESTED_WORLDS_RATE_LIMIT_PER_MIN", "1000")
    from server import _Handler, _ThreadedServer
    server = _ThreadedServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    w = _World(server.server_address[1])
    try:
        yield w
    finally:
        for client in w.sockets:
            client.close()
        server.shutdown()
        server.server_close()


def _metrics(**kwargs) -> dict:
    return beta_metrics.compute_metrics(persistence._DB_PATH, **kwargs)


def _cli(capsys, *argv: str) -> str:
    beta_metrics.main(["--db", str(persistence._DB_PATH), *argv])
    return capsys.readouterr().out


# The universe under the root: a three-attempt navigation puzzle, so one
# wrong guess leaves the pool open for the co-solve.
COSOLVE_NODE = "Ashen Ember Sphere-11"
# A galaxy beneath it, three attempts, for the failure pool.
FAILING_NODE = "Mossbound Bell Disc-111"
CHAT = "marker-chat-lantern by the reeds"
REPLY = "marker-chat-reply on my way"
GUESS = "marker-guess-nowhere"
JOURNAL = "marker-journal-private wondering"


def _meet_and_cosolve(world: _World) -> dict:
    """Two keyed travelers meet, talk, co-solve, and one of them acts.

    Returns the keys, the frames and responses each step produced, for the
    behaviour assertions and the metrics read alike.
    """
    ada_key, bea_key = world.mint("Quorra"), world.mint("Zephyrine")
    ada, ada_welcome = world.arrive(ada_key)
    bea, bea_welcome = world.arrive(bea_key)
    bea_arrives = ada.wait_for(lambda f: f["type"] == "player_join")

    ada.send({"type": "chat", "text": CHAT})
    heard_by_bea = bea.wait_for(
        lambda f: f["type"] == "chat" and f["text"] == CHAT)
    bea.send({"type": "chat", "text": REPLY})
    heard_by_ada = ada.wait_for(
        lambda f: f["type"] == "chat" and f["text"] == REPLY)

    status, _ = world.request("/journal/note", ada_key, {
        "id": "pilot-note", "node": COSOLVE_NODE, "text": JOURNAL})
    assert status == 200

    opened = world.open_puzzle(ada_key, COSOLVE_NODE)
    first = world.attempt(ada_key, COSOLVE_NODE, opened["name"], GUESS)
    bea.send({"type": "move", "node": COSOLVE_NODE})
    bea_moves = ada.wait_for(
        lambda f: f["type"] == "player_move" and f["node"] == COSOLVE_NODE)
    answer = _answer(COSOLVE_NODE)
    solved = world.attempt(bea_key, COSOLVE_NODE, opened["name"], answer)
    solve_seen = ada.wait_for(
        lambda f: f["type"] == "puzzle_solved" and f["node"] == COSOLVE_NODE)
    ripple_seen = ada.wait_for(
        lambda f: f["type"] == "causal_event" and f["kind"] == "PUZZLE_SOLVED")

    receipt = world.act(bea_key, NODES["instrument"], "pilot-act-bea")
    act_seen = ada.wait_for(
        lambda f: f["type"] == "intervention_changed"
        and f["id"] == receipt["id"])
    return {
        "ada_key": ada_key, "bea_key": bea_key, "answer": answer,
        "ada_welcome": ada_welcome, "bea_welcome": bea_welcome,
        "bea_arrives": bea_arrives, "heard_by_bea": heard_by_bea,
        "heard_by_ada": heard_by_ada, "opened": opened, "first": first,
        "bea_moves": bea_moves, "solved": solved, "solve_seen": solve_seen,
        "ripple_seen": ripple_seen, "receipt": receipt, "act_seen": act_seen,
    }


# ── C6, C4, C2a: what the pilot depends on ───────────────────────────────────


class TestTwoTravelers:
    def test_keyed_travelers_find_each_other_and_chat(self, world):
        s = _meet_and_cosolve(world)
        # Registered names, never the client's decoy, in the roster.
        assert [p["name"] for p in s["ada_welcome"]["players"]] == ["Quorra"]
        assert sorted(p["name"] for p in s["bea_welcome"]["players"]) == [
            "Quorra", "Zephyrine"]
        assert s["bea_arrives"]["name"] == "Zephyrine"
        # Each line reached the other socket, under its sender's name.
        assert s["heard_by_bea"]["name"] == "Quorra"
        assert s["heard_by_ada"]["name"] == "Zephyrine"
        assert s["bea_moves"] == {"type": "player_move", "name": "Zephyrine",
                                  "node": COSOLVE_NODE,
                                  "session_id": s["bea_moves"]["session_id"]}

    def test_a_cosolve_credits_both_registered_names(self, world):
        s = _meet_and_cosolve(world)
        assert s["opened"]["max_attempts"] >= 2 and not s["opened"]["solved"]
        assert s["first"]["result"] == "UNSOLVED"
        assert s["first"]["contributors"] == ["Quorra"]
        assert s["solved"]["result"] == "SOLVED"
        assert s["solved"]["solver"] == "Zephyrine"
        assert s["solved"]["contributors"] == ["Quorra", "Zephyrine"]
        assert "Mallory" not in json.dumps([s["first"], s["solved"]])

    def test_the_solve_answers_the_solver_with_a_visible_effect(self, world):
        solved = _meet_and_cosolve(world)["solved"]
        # Credit, and the material change committed with the solve.
        assert solved["solver"] == "Zephyrine"
        assert solved["changed"]["stabilized"] is True
        assert solved["correct_answer"] is None

    def test_one_travelers_solve_and_act_reach_the_other_live(self, world):
        s = _meet_and_cosolve(world)
        assert s["solve_seen"]["solver"] == "Zephyrine"
        assert s["solve_seen"]["contributors"] == ["Quorra", "Zephyrine"]
        assert s["ripple_seen"]["origin"] == COSOLVE_NODE
        seen = s["act_seen"]
        assert seen["node"] == NODES["instrument"] and seen["accepted"]
        assert seen["flavor"].startswith("Zephyrine attempts")

    def test_and_again_after_a_reload(self, world):
        s = _meet_and_cosolve(world)
        _settle(world)  # Quorra's page closes; a fresh one reads over HTTP
        status, page = world.request("/chronicle?limit=200", s["ada_key"])
        assert status == 200
        solve = next(e for e in page["entries"]
                     if e["type"] == "PUZZLE_SOLVED" and e["node"] == COSOLVE_NODE)
        assert solve["player"] == "Zephyrine"
        assert solve["data"]["contributors"] == ["Quorra", "Zephyrine"]
        act = next(e for e in page["entries"]
                   if e["type"] == "INTERVENTION_COMMITTED"
                   and e["node"] == NODES["instrument"])
        assert act["player"] == "Zephyrine"
        reopened = world.open_puzzle(s["ada_key"], COSOLVE_NODE)
        assert reopened["solved"] and reopened["solver"] == "Zephyrine"
        assert reopened["contributors"] == ["Quorra", "Zephyrine"]
        status, history = world.request(
            "/history?node_name=" + urllib.parse.quote(NODES["instrument"]),
            s["ada_key"])
        assert status == 200
        assert any(row["type"] == "INTERVENTION_COMMITTED"
                   and row["player"] == "Zephyrine"
                   for row in history["mutations"])


# ── B2: the read ─────────────────────────────────────────────────────────────


class TestBetaMetrics:
    def test_the_pilot_world_reads_as_two_acting_visitors(self, world):
        _meet_and_cosolve(world)
        _settle(world)
        m = _metrics(days=1)
        assert m["visitors"] == m["visitor_identities"] == 2
        assert m["acting_visitors"] == 2
        assert m["chat_lines"] == 2
        assert m["act_commits"] == 1
        assert (m["puzzle_attempts"], m["puzzle_solves"]) == (2, 1)
        assert (m["puzzle_failures"], m["puzzle_failed_rows"]) == (0, 0)

    def test_an_act_only_tester_is_one_visitor_who_acted(self, world):
        tester_key, lurker_key = world.mint("Oonagh"), world.mint("Thessaly")
        world.arrive(tester_key)
        lurker, _ = world.arrive(lurker_key)
        receipt = world.act(tester_key, NODES["instrument"], "act-only-1")
        lurker.wait_for(lambda f: f["type"] == "intervention_changed"
                        and f["id"] == receipt["id"])
        _settle(world)

        m = _metrics(days=1)
        # Both connected and announced; only the tester did anything, and
        # it was Act.
        assert m["visitors"] == 2
        assert m["events_by_type"]["PLAYER_MOVE"] == 2
        assert m["acting_visitors"] == 1
        assert m["act_commits"] == 1
        assert m["events_by_type"]["INTERVENTION_COMMITTED"] == 1
        assert m["actions_per_visitor"] == 0.5
        assert "act commits:         1" in beta_metrics.render(m)

    def test_a_move_that_goes_nowhere_is_not_an_action(self, world):
        # Opens the page and does nothing: the connect announcement, then
        # the same node again (the explorer reloading its view).
        lurker, welcome = world.arrive(world.mint("Thessaly"))
        lurker.send({"type": "move", "node": _own_node(welcome)})
        # A first visit whose socket opened before its saved position
        # landed: it joins at the root and announces the node it shows.
        early_key = world.mint("Isaura")
        early = world.connect(early_key)
        assert _own_node(early.wait_for(
            lambda f: f["type"] == "welcome")) == store.root_name(SEED)
        world.announce(early, early_key, COSOLVE_NODE)
        # Announces, walks one step, then reselects where it stands.
        walker, _ = world.arrive(world.mint("Quorra"))
        walker.send({"type": "move", "node": COSOLVE_NODE})
        walker.send({"type": "move", "node": COSOLVE_NODE})
        _settle(world)

        m = _metrics(days=1, timeline=True)
        assert m["visitors"] == 3
        assert m["events_by_type"]["PLAYER_MOVE"] == 6
        assert m["acting_visitors"] == 1
        assert m["actions_per_visitor"] == round(1 / 3, 1)
        # Numbered by arrival: only the walker has a first move.
        assert [(row["participant"], row["measured_from"]) for row in m["timeline"]] == [
            ("P1", "join"), ("P2", "join"), ("P3", "join")]
        assert [row["first_move"] is None for row in m["timeline"]] == [
            True, True, False]
        assert m["timeline"][2]["first_move"] >= 0

    def test_a_failed_pool_counts_once_however_many_wrong_guesses_follow(self, world):
        ada_key, bea_key = world.mint("Quorra"), world.mint("Zephyrine")
        opened = world.open_puzzle(ada_key, FAILING_NODE)
        results = [world.attempt(ada_key, FAILING_NODE, opened["name"], f"wrong-{i}")
                   for i in range(opened["max_attempts"])]
        assert [r["result"] for r in results] == (
            ["UNSOLVED"] * (opened["max_attempts"] - 1) + ["FAILED"])
        # Every wrong guess after the pool failed writes another failure.
        late = [world.attempt(bea_key, FAILING_NODE, opened["name"], "late-one"),
                world.attempt(ada_key, FAILING_NODE, opened["name"], "late-two")]
        assert [r["result"] for r in late] == ["FAILED", "FAILED"]

        m = _metrics(days=1)
        assert m["puzzle_failed_rows"] == 3
        assert m["puzzle_failures"] == 1
        assert m["puzzle_attempts"] == opened["max_attempts"] + 2
        assert "failed 1)" in beta_metrics.render(m)

        # A renewal is a new question at the same node: failing it is a
        # second failed puzzle.
        persistence.record_mutation(SEED, FAILING_NODE, "PUZZLE_REARM", None,
                                    {"trigger": "DANGER_ALERT", "agent": None})
        renewed = world.open_puzzle(ada_key, FAILING_NODE)
        assert renewed["epoch"] == 1 and renewed["name"] != opened["name"]
        for i in range(renewed["max_attempts"]):
            last = world.attempt(bea_key, FAILING_NODE, renewed["name"], f"again-{i}")
        assert last["result"] == "FAILED"
        m = _metrics(days=1)
        assert (m["puzzle_failures"], m["puzzle_failed_rows"]) == (2, 4)

    def test_a_failed_pool_counts_where_and_by_whom_it_first_failed(self, world):
        facilitator, tester = world.mint("Oonagh"), world.mint("Quorra")
        opened = world.open_puzzle(facilitator, FAILING_NODE)
        for i in range(opened["max_attempts"]):
            last = world.attempt(facilitator, FAILING_NODE, opened["name"], f"demo-{i}")
        assert last["result"] == "FAILED"
        assert world.attempt(tester, FAILING_NODE, opened["name"],
                             "late-one")["result"] == "FAILED"

        # The facilitator exhausted the pool; the tester only guessed late.
        assert _metrics(days=1)["puzzle_failures"] == 1
        m = _metrics(days=1, exclude=["Oonagh"])
        assert (m["puzzle_failures"], m["puzzle_failed_rows"]) == (0, 1)

        # Three days on, the pool still answers FAILED to a late guess.
        with persistence._connect() as conn:
            conn.execute(
                """UPDATE world_mutations
                   SET recorded_at = datetime('now', '-3 days')
                   WHERE node_name = ?
                     AND mutation_type IN ('PUZZLE_ATTEMPT', 'PUZZLE_FAILED')""",
                (FAILING_NODE,))
        assert world.attempt(tester, FAILING_NODE, opened["name"],
                             "late-two")["result"] == "FAILED"
        today = _metrics(days=1)
        assert (today["puzzle_failures"], today["puzzle_failed_rows"]) == (0, 1)
        week = _metrics(days=7)
        assert (week["puzzle_failures"], week["puzzle_failed_rows"]) == (1, 3)
        week = _metrics(days=7, exclude=["Oonagh"])
        assert (week["puzzle_failures"], week["puzzle_failed_rows"]) == (0, 2)

    def test_a_rotated_key_is_one_visitor(self, world):
        old = world.mint("Quorra")
        first = world.connect(old)
        first.wait_for(lambda f: f["type"] == "welcome")
        first.send({"type": "chat", "text": "before the rotation"})
        first.wait_for(lambda f: f["type"] == "chat")
        _settle(world)

        new = "nw_" + secrets.token_hex(16)
        participants.rotate(old, new)  # what `main.py invite rotate` runs
        assert world.connect(old).status.split()[1] == b"403"
        second = world.connect(new)
        welcome = second.wait_for(lambda f: f["type"] == "welcome")
        assert [p["name"] for p in welcome["players"]] == ["Quorra"]
        second.send({"type": "chat", "text": "after the rotation"})
        second.wait_for(lambda f: f["type"] == "chat")
        _settle(world)

        m = _metrics(days=1)
        assert m["visitor_identities"] == 2  # two credential hashes...
        assert m["visitors"] == 1            # ...one person
        assert m["acting_visitors"] == 1
        assert m["chat_lines"] == 2
        assert "2 credential identities fold" in beta_metrics.render(m)

    def test_a_rotated_key_returning_the_next_day_is_one_returning_visitor(self, world):
        old = world.mint("Quorra")
        # Yesterday's visit under the first key (the clock cannot be moved,
        # so the row is written with yesterday's time).
        with persistence._connect() as conn:
            conn.execute(
                """INSERT INTO world_mutations
                   (world_seed, node_name, mutation_type, player_name, data,
                    actor_identity, recorded_at)
                   VALUES (?, ?, 'PLAYER_JOIN', 'Quorra', '{}', ?,
                           datetime('now', '-1 day'))""",
                (SEED, store.root_name(SEED), _identity(old)))
        new = "nw_" + secrets.token_hex(16)
        participants.rotate(old, new)
        today = world.connect(new)
        today.wait_for(lambda f: f["type"] == "welcome")
        today.send({"type": "chat", "text": "back again"})
        today.wait_for(lambda f: f["type"] == "chat")
        _settle(world)

        m = _metrics(days=7)
        assert m["visitor_identities"] == 2
        assert (m["visitors"], m["returning_visitors"]) == (1, 1)
        assert m["return_rate"] == 1.0

    def test_exclude_identity_drops_the_facilitator_under_every_key(self, world, capsys):
        facilitator = world.mint("Oonagh")
        second_traveler = world.mint("Thessaly")
        tester = world.mint("Quorra")
        for key in (facilitator, second_traveler, tester):
            client = world.connect(key)
            client.wait_for(lambda f: f["type"] == "welcome")
            client.send({"type": "chat", "text": "hello"})
            client.wait_for(lambda f: f["type"] == "chat")
        world.act(facilitator, NODES["instrument"], "facilitator-demo")
        # A model-written row under the facilitator's key (as a parsed Act
        # or a voice line stores one), and one under the tester's.
        for key, name in ((facilitator, "Oonagh"), (tester, "Quorra")):
            persistence.record_mutation(
                SEED, NODES["instrument"], "AGENT_VOICE", name, {},
                actor_identity=_identity(key),
                model_provider="fixture", resolved_model=f"model-{name}")
        _settle(world)
        rotated = "nw_" + secrets.token_hex(16)
        participants.rotate(facilitator, rotated)
        again = world.connect(rotated)
        again.wait_for(lambda f: f["type"] == "welcome")
        again.send({"type": "chat", "text": "one more"})
        again.wait_for(lambda f: f["type"] == "chat")
        _settle(world)

        everyone = _metrics(days=1)
        assert everyone["visitors"] == 3 and everyone["visitor_identities"] == 4
        assert sorted(row["resolved_model"] for row in everyone["model_provenance"]) == [
            "model-Oonagh", "model-Quorra"]
        m = _metrics(days=1, exclude=["Oonagh", "Thessaly"])
        assert m["excluded_identities"] == 3  # two keys, plus one
        assert m["visitors"] == m["visitor_identities"] == 1
        assert m["chat_lines"] == 1 and m["act_commits"] == 0
        assert m["model_provenance"] == [
            {"provider": "fixture", "resolved_model": "model-Quorra", "rows": 1}]
        # Names compare as registration compares them.
        # The window's start is read from the clock on each call, so it is
        # left out: two reads a second apart would differ there alone.
        assert ({**_metrics(days=1, exclude=["  oonagh ", "THESSALY"]), "window": None}
                == {**m, "window": None})

        out = json.loads(_cli(capsys, "--days", "1", "--json",
                              "--exclude-identity", "Oonagh",
                              "--exclude-identity", "Thessaly"))
        assert out["visitors"] == 1 and out["excluded_identities"] == 3
        # A typo excludes nobody silently.
        with pytest.raises(ValueError, match="no registered player"):
            _metrics(days=1, exclude=["Oonah"])
        with pytest.raises(SystemExit, match="no registered player"):
            _cli(capsys, "--exclude-identity", "Oonah")

    def test_since_and_until_read_an_archive_without_changing_it(self, world, capsys, tmp_path):
        # A watch session long past, as the chronicle stored it, and its
        # voice counter on the same UTC day.
        watched = world.mint("Isaura")
        rows = [("PLAYER_JOIN", "2026-01-05 10:00:00"),
                ("PLAYER_MOVE", "2026-01-05 10:01:30"),
                ("INTERVENTION_COMMITTED", "2026-01-05 10:04:00"),
                ("PLAYER_LEAVE", "2026-01-05 10:20:00")]
        with persistence._connect() as conn:
            conn.executemany(
                """INSERT INTO world_mutations
                   (world_seed, node_name, mutation_type, player_name, data,
                    actor_identity, recorded_at)
                   VALUES (?, ?, ?, 'Isaura', '{}', ?, ?)""",
                [(SEED, store.root_name(SEED), kind, _identity(watched), at)
                 for kind, at in rows])
        for day in ("2026-01-05", "2026-01-06"):
            persistence.increment_cost_calls(
                observability.voice_bucket("speak", "ok"), day)
        # Today's traveler, through the real socket.
        today = world.connect(world.mint("Quorra"))
        today.wait_for(lambda f: f["type"] == "welcome")
        _settle(world)
        archive = tmp_path / "watch-archive.db"
        persistence.backup_to(archive)
        archive.chmod(0o400)
        before = hashlib.sha256(archive.read_bytes()).hexdigest()

        def read(*argv):
            beta_metrics.main(["--db", str(archive), "--json", *argv])
            return json.loads(capsys.readouterr().out)

        assert read("--days", "7")["visitors"] == 1  # only today's
        day = read("--since", "2026-01-05", "--until", "2026-01-05")
        assert day["window"] == {"since": "2026-01-05 00:00:00",
                                 "until": "2026-01-06 00:00:00"}
        assert day["window_days"] is None
        assert (day["visitors"], day["acting_visitors"], day["act_commits"]) == (1, 1, 1)
        # The next day's counter stays out: --until 2026-01-05 ends there.
        assert day["voice_outcomes"] == {"speak": {"ok": 1}}
        assert read("--since", "2026-01-04", "--until",
                    "2026-01-05")["voice_outcomes"] == {"speak": {"ok": 1}}
        next_day = read("--since", "2026-01-06", "--until", "2026-01-06")
        assert next_day["visitors"] == 0
        assert next_day["voice_outcomes"] == {"speak": {"ok": 1}}
        # Date-times bound to the second; --until is exclusive there.
        assert read("--since", "2026-01-05T10:00:00",
                    "--until", "2026-01-05T10:04:00")["act_commits"] == 0
        assert read("--since", "2026-01-05T10:00:00+00:00",
                    "--until", "2026-01-05T10:04:01Z")["act_commits"] == 1
        beta_metrics.main(["--db", str(archive), "--since", "2026-01-05",
                           "--until", "2026-01-05"])
        assert capsys.readouterr().out.startswith(
            "Beta health — 2026-01-05 00:00:00 to 2026-01-06 00:00:00 UTC")
        with pytest.raises(SystemExit, match="not both"):
            beta_metrics.main(["--db", str(archive), "--days", "7",
                               "--since", "2026-01-05"])
        with pytest.raises(SystemExit, match="earlier than"):
            beta_metrics.main(["--db", str(archive), "--since", "2026-01-06",
                               "--until", "2026-01-05"])
        with pytest.raises(SystemExit, match="not an ISO date"):
            beta_metrics.main(["--db", str(archive), "--since", "last tuesday"])
        assert hashlib.sha256(archive.read_bytes()).hexdigest() == before
        assert not Path(str(archive) + "-wal").exists()

    def test_the_timeline_names_nobody(self, world, capsys):
        s = _meet_and_cosolve(world)
        _settle(world)
        text = _cli(capsys, "--days", "1", "--timeline")
        as_json = json.loads(_cli(capsys, "--days", "1", "--timeline", "--json"))

        timeline = as_json["timeline"]
        assert [row["participant"] for row in timeline] == ["P1", "P2"]
        quorra, zephyrine = timeline  # numbered by arrival
        assert quorra["measured_from"] == "join"
        assert quorra["first_puzzle_attempt"] >= 0
        assert (quorra["first_move"], quorra["first_act"], quorra["first_solve"]) == (
            None, None, None)
        assert all(zephyrine[field] >= 0 for field in (
            "first_move", "first_act", "first_puzzle_attempt", "first_solve"))
        assert set(quorra) == {"participant", "measured_from", "first_move",
                               "first_act", "first_puzzle_attempt", "first_solve"}

        section = text.split("first steps", 1)[1]
        assert "\n  P1 " in section and "\n  P2 " in section
        with sqlite3.connect(persistence._DB_PATH) as conn:
            participant_ids = [r[0] for r in conn.execute(
                "SELECT participant_id FROM participant_credentials")]
        assert participant_ids  # the journal and Act resolved participants
        forbidden = ["Quorra", "Zephyrine", "Mallory", CHAT, REPLY, GUESS,
                     JOURNAL, *participant_ids]
        for key in (s["ada_key"], s["bea_key"]):
            forbidden += [key, hashlib.sha256(key.encode()).hexdigest(),
                          _identity(key)]
        for output in (text, json.dumps(as_json)):
            for secret in forbidden:
                assert secret not in output
        # The answer is checked where only the timeline speaks: an answer
        # word may also be part of a place name the report lists.
        assert s["answer"] not in section
        assert s["answer"] not in json.dumps(timeline)


def _fixture_event(kind, *, actor="tester", seed=SEED, node=FAILING_NODE,
                   data=None, ago="0 days"):
    """Append a scratch-history event, including historical ambient traces."""
    persistence.record_mutation(seed, node, kind, None, data or {},
                                actor_identity=actor)
    with persistence._connect() as conn:
        event_id = conn.execute("SELECT MAX(id) FROM world_mutations").fetchone()[0]
        conn.execute(
            "UPDATE world_mutations SET recorded_at = datetime('now', ?) WHERE id = ?",
            (f"-{ago}", event_id))


class TestAmbientMetricsSafeguards:
    def test_all_server_identities_and_agent_actions_stay_out_of_human_counts(self):
        from agents.identities import SERVER_IDENTITIES
        for actor in SERVER_IDENTITIES:
            for kind in ("INTERVENTION_COMMITTED", "SCALE_ACT", "PUZZLE_SOLVED",
                         "PUZZLE_FAILED", "PLAYER_JOIN"):
                _fixture_event(kind, actor=actor)
        # Older custom walkers can have identities outside today's roster.
        # Their payload still tells us that these are ambient actions.
        for kind in ("INTERVENTION_COMMITTED", "SCALE_ACT", "PUZZLE_ATTEMPT",
                     "PUZZLE_SOLVED", "PUZZLE_FAILED"):
            _fixture_event(kind, actor="historical-agent",
                           data={"agent": "historical-agent"})
        _fixture_event("INTERVENTION_COMMITTED", actor=None)
        _fixture_event("INTERVENTION_ARRIVED")  # delivery is not another action
        _fixture_event("INTERVENTION_COMMITTED")
        _fixture_event("SCALE_ACT")
        # A player asking an inhabitant is still a human conversation.
        _fixture_event("AGENT_VOICE", data={"agent": "Tessera", "reply": "Welcome."})

        metrics = _metrics(days=1, timeline=True)
        assert metrics["visitors"] == metrics["acting_visitors"] == 1
        assert metrics["events_per_visitor"] == metrics["actions_per_visitor"] == 3
        assert metrics["act_commits"] == metrics["scale_acts"] == 1
        assert metrics["conversations"] == 1
        assert metrics["puzzle_attempts"] == metrics["puzzle_solves"] == 0
        assert metrics["puzzle_failures"] == metrics["puzzle_failed_rows"] == 0
        assert metrics["events_by_type"] == {
            "INTERVENTION_COMMITTED": 1, "SCALE_ACT": 1, "AGENT_VOICE": 1}
        assert len(metrics["timeline"]) == 1
        assert metrics["timeline"][0]["first_solve"] is None

    def test_ambient_failure_cannot_claim_the_first_human_failed_pool(self):
        puzzle = {"puzzle": "The Sealed Room"}
        for actor in ("Tessera", "Scout", "Observer", None):
            _fixture_event("PUZZLE_FAILED", actor=actor, data=puzzle, ago="2 days")
        _fixture_event("PUZZLE_FAILED", actor="historical-agent", ago="2 days",
                       data={**puzzle, "agent": "historical-agent"})
        _fixture_event("PUZZLE_FAILED", data=puzzle)
        _fixture_event("PUZZLE_FAILED", actor="second-tester", data=puzzle)
        _fixture_event("PUZZLE_SOLVED", actor="second-tester", data=puzzle)

        metrics = _metrics(days=1)
        assert metrics["puzzle_failures"] == 1
        assert metrics["puzzle_failed_rows"] == 2
        assert metrics["puzzle_solves"] == 1
        assert _metrics(days=7)["puzzle_failures"] == 1
        # Even though the first ambient failures cannot claim the pool,
        # excluding the first human must not pass it to a late tester.
        excluded = _metrics(days=1, exclude=["tester"])
        assert excluded["puzzle_failures"] == 0
        assert excluded["puzzle_failed_rows"] == excluded["puzzle_solves"] == 1

    def test_first_human_failure_keeps_its_window_until_the_pool_renews(self):
        puzzle = {"puzzle": "The Sealed Room"}
        _fixture_event("PUZZLE_FAILED", actor="Tessera", data=puzzle, ago="3 days")
        _fixture_event("PUZZLE_FAILED", data=puzzle, ago="2 days")
        _fixture_event("PUZZLE_FAILED", actor="second-tester", data=puzzle)
        assert _metrics(days=1)["puzzle_failures"] == 0
        assert _metrics(days=7)["puzzle_failures"] == 1
        _fixture_event("PUZZLE_REARM", actor=None)
        _fixture_event("PUZZLE_FAILED", actor="Observer", data=puzzle)
        _fixture_event("PUZZLE_FAILED", data=puzzle)
        assert _metrics(days=1)["puzzle_failures"] == 1
        assert _metrics(days=7)["puzzle_failures"] == 2

    def test_failed_pools_preserve_node_world_and_epoch_lineage(self):
        puzzle = {"puzzle": "The Sealed Room"}
        _fixture_event("PUZZLE_FAILED", data=puzzle)
        _fixture_event("PUZZLE_REARM", seed=7, actor=None)
        _fixture_event("PUZZLE_REARM", node="Elsewhere", actor=None)
        _fixture_event("PUZZLE_FAILED", data=puzzle)
        # Unrelated rearms did not split the original pool.
        assert _metrics(seed=SEED)["puzzle_failures"] == 1
        _fixture_event("PUZZLE_REARM", actor=None)
        _fixture_event("PUZZLE_FAILED", data=puzzle)
        _fixture_event("PUZZLE_FAILED", node="Elsewhere", data=puzzle)
        _fixture_event("PUZZLE_FAILED", seed=7, data=puzzle)
        assert _metrics(seed=SEED)["puzzle_failures"] == 3
        assert _metrics(seed=7)["puzzle_failures"] == 1
        assert _metrics()["puzzle_failures"] == 4
