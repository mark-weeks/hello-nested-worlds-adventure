"""Agent identities are server-owned; a client-chosen name never writes history.

An agent's name lands in ``AGENT_VISIT`` / ``AGENT_VOICE`` ``data.agent``,
keys ``agent_memory``, and becomes a Speak target in both clients.
``data.agent`` is neither redactable nor screened, so these tests drive the
real endpoints over HTTP, SSE and WebSocket and read what was stored.
Stub providers only. No live model call.
"""
from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from urllib.parse import quote

import pytest

import persistence
from agents import identities
from agents.personas import CATALOG, for_name
from consciousness import WANDERER_CAST, runtime
from consciousness.runtime import Completion
from multiverse.generator import generate_node_hierarchy
from multiverse.situation import KEEPER
from server import _Handler, _ThreadedServer, guard, moderation
from tests.test_day_one_recording import _ws_connect
from tests.test_moderation import _recv_exact

ADA_KEY = "nw_" + "a" * 32
BEA_KEY = "nw_" + "b" * 32
_ARCHETYPES = {persona.name for persona in CATALOG}


@pytest.fixture()
def srv():
    # Minting closes the invite gate: every request below is a named player.
    persistence.mint_invite_key(ADA_KEY, "Ada")
    persistence.mint_invite_key(BEA_KEY, "Bea")
    server = _ThreadedServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield port
    server.shutdown()
    server.server_close()
    thread.join(5)


def _request(port, path, *, key=BEA_KEY, body=None):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers={"X-Beta-Key": key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _observe(port, seed, *, name, key=BEA_KEY):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/observe?seed={seed}&depth=4&name={quote(name)}",
        headers={"X-Beta-Key": key})
    events = []
    with urllib.request.urlopen(req, timeout=30) as resp:
        assert resp.headers.get_content_type() == "text/event-stream"
        for raw in resp:
            if raw.startswith(b"data: "):
                event = json.loads(raw[6:])
                events.append(event)
                if event.get("done"):
                    break
    return events


def _ws_frames_until(sock, msg_type, timeout=5.0):
    """Every JSON text frame up to and including the first ``msg_type``."""
    import struct
    import time
    sock.settimeout(timeout)
    deadline = time.monotonic() + timeout
    frames = []
    while time.monotonic() < deadline:
        hdr = _recv_exact(sock, 2)
        length = hdr[1] & 0x7F
        if length == 126:
            length = struct.unpack(">H", _recv_exact(sock, 2))[0]
        elif length == 127:
            length = struct.unpack(">Q", _recv_exact(sock, 8))[0]
        payload = _recv_exact(sock, length)
        if hdr[0] & 0x0F != 1:
            continue
        msg = json.loads(payload)
        frames.append(msg)
        if msg.get("type") == msg_type:
            return frames
    raise AssertionError(f"no {msg_type!r} frame within {timeout}s")


def _agent_rows(seed, kind):
    return [row for row in persistence.get_mutations(seed, limit=1000)
            if row["type"] == kind]


def _chronicled_agents(seed):
    """Every ``data.agent`` any row in this world carries, whatever its type.

    A walker's name rides on every event it fires — ``AGENT_VISIT``, and the
    ``DANGER_ALERT``, ``PUZZLE_SOLVED``/``PUZZLE_FAILED`` and
    ``PUZZLE_REARM`` rows the substance handler records from the same
    payload — so checking ``AGENT_VISIT`` alone would miss a leak there.
    """
    return {row["data"]["agent"] for row in persistence.get_mutations(seed, limit=1000)
            if row["data"].get("agent") is not None}


# ── The one identity set ────────────────────────────────────────────────────

def test_the_identity_set_is_the_cast_the_keeper_and_two_utility_walkers():
    assert set(identities.SERVER_IDENTITIES) == {
        *WANDERER_CAST, KEEPER, identities.SCOUT, identities.OBSERVER}
    assert len(identities.SERVER_IDENTITIES) == len(set(identities.SERVER_IDENTITIES))
    assert identities.canonical("  the locksmith ") == "The Locksmith"
    assert identities.canonical("OBSERVER") == "Observer"
    for stranger in ("Recorder", "Ada", "", "Tessera2", None, 5, ["Tessera"]):
        assert identities.canonical(stranger) is None


# ── GET /agent ──────────────────────────────────────────────────────────────

def test_agent_walk_is_always_scout_and_never_touches_a_named_memory(srv):
    seed = 4601
    remembered = (["remembered-id"], [{"node": "Elsewhere-1", "action": "kept"}])
    persistence.save_agent_memory("Tessera", seed, *remembered)
    before = persistence.load_agent_memory("Tessera", seed)
    long_name = "Z" * 300
    for name in ("Recorder", "Tessera", "Ada", long_name):
        status, data = _request(srv, f"/agent?seed={seed}&name={quote(name)}&max_nodes=10")
        assert status == 200, data
        assert data["agent"] == "Scout"
    # Since #141 the walk is a simulation that stores nothing (2026-11-03
    # evaluation, R2): no chronicle row under any name, Scout's included.
    assert _agent_rows(seed, "AGENT_VISIT") == []
    assert _chronicled_agents(seed) == set()
    # The cast member's memory is exactly what it was.
    assert persistence.load_agent_memory("Tessera", seed) == before
    for name in ("Recorder", "Ada", long_name, long_name[:32], "Scout"):
        assert persistence.load_agent_memory(name, seed) is None
    assert persistence.get_agent_runs(seed) == []
    assert {m["agent_name"] for m in persistence.list_agent_memories()} == {"Tessera"}


def test_agent_persona_picks_an_archetype_and_cannot_name_anyone(srv):
    seed = 4602
    status, data = _request(
        srv, f"/agent?seed={seed}&max_nodes=5&persona=destabilizer&name=Mallory")
    assert status == 200 and data["agent"] == "Scout"
    assert data["persona"] == "destabilizer"
    status, data = _request(
        srv, f"/agent?seed={seed}&max_nodes=5&persona={quote('Mallory the Great')}")
    assert status == 200 and data["agent"] == "Scout"
    assert data["persona"] == for_name("Scout").name
    # The simulation stores nothing (#141), so neither name nor persona can
    # reach the chronicle.
    assert _agent_rows(seed, "AGENT_VISIT") == []
    assert _chronicled_agents(seed) == set()
    assert data["persona"] in _ARCHETYPES
    assert "Mallory" not in json.dumps(persistence.get_mutations(seed, limit=1000))


# ── GET /observe ────────────────────────────────────────────────────────────

def test_observe_walks_as_observer_never_as_a_registered_player(srv):
    seed = 4603
    ws, status = _ws_connect(srv, seed, "ignored", invite_key=ADA_KEY)
    assert b"101" in status
    try:
        welcome = _ws_frames_until(ws, "welcome")[-1]
        assert welcome["agents"] == []
        # Bea asks for a walker named after Ada, a registered player.
        events = _observe(srv, seed, name="Ada")
        frames = _ws_frames_until(ws, "agent_leave")
    finally:
        ws.close()
    assert events[-1]["done"] is True and events[-1]["nodes_visited"] > 0
    walked = [event for event in events if not event.get("done")]
    assert walked and {event["agent"] for event in walked} == {"Observer"}
    # The live presence the room saw is Observer: it entered and left as
    # Observer, and no presence frame carried Ada's name.
    presence = [frame for frame in frames
                if frame["type"] in {"agent_enter", "agent_move", "agent_leave"}]
    assert presence[0] == {"type": "agent_enter", "name": "Observer",
                           "persona": for_name("Observer").name}
    assert {frame["name"] for frame in presence} == {"Observer"}
    assert presence[-1] == {"type": "agent_leave", "name": "Observer"}
    # Since #141 the walk is live-only: its unapplied events are streamed to
    # the watcher, never broadcast as causal_events, and nothing is stored.
    assert not [frame for frame in frames if frame["type"] == "causal_event"]
    assert _agent_rows(seed, "AGENT_VISIT") == []
    assert _chronicled_agents(seed) == set()


def test_observe_cannot_spawn_a_cast_member_or_a_long_name(srv):
    seed = 4604
    for name in ("Tessera", "x" * 200):
        events = _observe(srv, seed, name=name)
        assert {e["agent"] for e in events if not e.get("done")} == {"Observer"}
    # Live-only since #141: nothing is stored under any name.
    assert _agent_rows(seed, "AGENT_VISIT") == []
    assert _chronicled_agents(seed) == set()


# ── POST /agent/voice ───────────────────────────────────────────────────────

class _Stub:
    name = "fixture"

    def __init__(self):
        self.calls = []

    def configured(self):
        return True

    def default_model(self, task):
        return "fixture-model"

    def cache_reference_tokens(self, model):
        return None

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        return Completion("Footsteps, then quiet.", True, provider=self.name)


@pytest.fixture()
def voice(monkeypatch):
    """A configured voice with the real screen and the real budget ledger."""
    stub = _Stub()
    monkeypatch.delenv(guard.DISABLE_AI_ENV, raising=False)
    monkeypatch.delenv(moderation.DISABLE_MODERATION_ENV, raising=False)
    monkeypatch.setenv(guard.ANTHROPIC_CAP_ENV, "100")
    monkeypatch.setenv(guard.ANTHROPIC_PER_USER_CAP_ENV, "100")
    monkeypatch.setattr(runtime, "get_provider", lambda: stub)
    screens = []
    real_screen = moderation.screen

    def recording_screen(text, **kwargs):
        screens.append(kwargs.get("surface"))
        return real_screen(text, **kwargs)

    monkeypatch.setattr(moderation, "screen", recording_screen)
    return stub, screens


def _counters(key):
    day = guard._utc_day()
    return {
        "voice": persistence.get_cost_calls(guard.VOICE_BUCKET, day),
        "user_voice": persistence.get_cost_calls(
            guard._user_bucket(guard.VOICE_BUCKET, key), day),
        "moderation": persistence.get_cost_calls(
            guard._user_bucket(guard.MODERATION_ACTIONS_BUCKET, key), day),
        "model": persistence.get_cost_calls(
            guard._user_bucket(guard.MODEL_ACTIONS_BUCKET, key), day),
    }


def _quiet(label, node_name, persona=None):
    persona = persona or for_name(label).name
    return {
        "agent": label,
        "persona": persona,
        "node": node_name,
        "response": (f"{label} does not answer. Only the traces of a "
                     f"{persona} remain here, already cooling."),
        "ai": False,
    }


def test_unknown_agent_is_quiet_before_the_screen_budget_or_any_row(srv, voice):
    stub, screens = voice
    seed = 4605
    node = generate_node_hierarchy(seed=seed, max_depth=1)
    # A stale trace an older local DB may still show as a Speak target.
    persistence.record_mutation(seed, node.name, "AGENT_VISIT", None,
                                {"agent": "Recorder", "persona": "scholar"})
    asked = [("Recorder", "Recorder"), ("Ada", "Ada"), (" Bea ", "Bea"),
             ("Tessera the Second", "Tessera the Second"), ("Y" * 80, "Y" * 32),
             # Printable names outside ASCII still echo, a combining mark included.
             ("Élodie", "Élodie"), ("影", "影"), ("Zoe\u0308", "Zoe\u0308"),
             ("", "Someone"), ("   ", "Someone"), (None, "Someone"), (7, "Someone"),
             (["Tessera"], "Someone"), ({"name": "Tessera"}, "Someone")]
    for requested, label in asked:
        status, data = _request(srv, "/agent/voice", body={
            "seed": seed, "node_name": node.name, "agent_name": requested,
            "message": "hello, old light"})
        assert status == 200, (requested, data)
        assert data == _quiet(label, node.name), requested
    # A persona argument still only picks the archetype on the quiet line.
    status, data = _request(srv, "/agent/voice", body={
        "seed": seed, "node_name": node.name, "agent_name": "Recorder",
        "persona": "tender", "message": "hello, old light"})
    assert status == 200 and data == _quiet("Recorder", node.name, "tender")
    assert screens == [] and stub.calls == []
    assert _counters(BEA_KEY) == {"voice": 0, "user_voice": 0, "moderation": 0, "model": 0}
    assert _agent_rows(seed, "AGENT_VOICE") == []
    # The place is still resolved first: an unknown place is the 404.
    status, data = _request(srv, "/agent/voice", body={
        "seed": seed, "node_name": "Forged-11", "agent_name": "Recorder",
        "message": "hello, old light"})
    assert status == 404 and data["error"] == "no such place in this world"


@pytest.mark.parametrize("requested,escape", [
    # Lone surrogates: no UTF-8 form to hash for a persona.
    ("\ud800", "\\ud800"), (" " * 32 + "\ud800", "\\ud800"), ("Ada\udfff", "\\udfff"),
    # Control and format characters: strip() keeps them, so they would echo.
    ("\x00", "\\u0000"), ("\u200b", "\\u200b"), ("\ufeffAda", "\\ufeff"),
])
def test_an_unprintable_name_is_quiet_as_someone_not_echoed_or_a_server_error(
        srv, voice, requested, escape):
    """A name that is not printable once trimmed and capped is a client's
    mistake. A lone surrogate (an escaped ``\\ud800`` in the JSON body)
    cannot be hashed to a persona; NUL, a zero-width space or a BOM would be
    echoed back raw. Each reads as "Someone" — HTTP 200, ``ai: false``, no
    screen, no budget, no row. (``"Scout\\u200b"`` is Scout: ``name_key``
    drops the zero-width space; see the canonical-name test below.)"""
    stub, screens = voice
    seed = 4612
    node = generate_node_hierarchy(seed=seed, max_depth=1)
    body = {"seed": seed, "node_name": node.name, "agent_name": requested,
            "message": "hello, old light"}
    assert escape in json.dumps(body)  # the escape json.loads turns back into the character
    assert identities.canonical(requested) is None
    status, data = _request(srv, "/agent/voice", body=body)
    assert status == 200, data
    assert data == _quiet("Someone", node.name)
    # A persona argument with no UTF-8 form only fails to pick an archetype.
    status, data = _request(srv, "/agent/voice", body={**body, "persona": "\ud800"})
    assert status == 200 and data == _quiet("Someone", node.name)
    assert screens == [] and stub.calls == []
    assert _counters(BEA_KEY) == {"voice": 0, "user_voice": 0, "moderation": 0, "model": 0}
    assert _agent_rows(seed, "AGENT_VOICE") == []


@pytest.mark.parametrize("requested,canonical", [
    ("Tessera", "Tessera"), ("  aunt entropy ", "Aunt Entropy"),
    ("SCOUT", "Scout"), ("observer", "Observer"),
    # A compatibility spelling is the same identity (persistence.name_key).
    ("\uff33\uff43\uff4f\uff55\uff54", "Scout"),
    # So is one with an invisible default-ignorable character, which the key
    # drops (decided under the owner's delegation, 2026-11-04).
    ("Scout\u200b", "Scout"), ("Obs\u00aderver", "Observer"),
])
def test_a_server_identity_is_voiced_under_its_canonical_name(srv, voice, requested, canonical):
    stub, screens = voice
    seed = 4606
    node = generate_node_hierarchy(seed=seed, max_depth=1)
    status, data = _request(srv, "/agent/voice", body={
        "seed": seed, "node_name": node.name, "agent_name": requested,
        "message": "hello, old light"})
    assert status == 200, data
    assert data == {"agent": canonical, "persona": for_name(canonical).name,
                    "node": node.name, "response": "Footsteps, then quiet.", "ai": True}
    assert screens == ["agent"] and len(stub.calls) == 1
    # The voice prompt names the agent by its canonical spelling; the
    # client's raw string never reaches the model as an identity.
    agent_block = stub.calls[0]["system"][-1].text
    assert agent_block.startswith(f"You are {canonical}, a {for_name(canonical).name}. ")
    assert _counters(BEA_KEY) == {"voice": 1, "user_voice": 1, "moderation": 1, "model": 1}
    rows = _agent_rows(seed, "AGENT_VOICE")
    assert len(rows) == 1
    assert rows[0]["data"]["agent"] == canonical
    assert rows[0]["player"] == "Bea"


def test_a_voiced_identity_recalls_the_memory_kept_under_its_canonical_name(srv, voice):
    """``agent_memory`` is keyed by the canonical spelling, so a trimmed,
    lower-case request must still read the cast member's own memory."""
    stub, _ = voice
    seed = 4613
    assert "Aunt Entropy" in WANDERER_CAST
    node = generate_node_hierarchy(seed=seed, max_depth=1)
    persistence.save_agent_memory(
        "Aunt Entropy", seed, [node.name],
        [{"node": "Kiln Seam-7", "action": "listened to the glaze cooling"}])
    status, data = _request(srv, "/agent/voice", body={
        "seed": seed, "node_name": node.name, "agent_name": "  aunt entropy ",
        "message": "hello, old light"})
    assert status == 200 and data["agent"] == "Aunt Entropy" and data["ai"] is True, data
    assert len(stub.calls) == 1
    agent_block = stub.calls[0]["system"][-1].text
    assert "you know 1 place(s) in this world" in agent_block
    assert f"You have stood at {node.name} before" in agent_block
    assert "Kiln Seam-7 — listened to the glaze cooling" in agent_block
    assert "newly arrived" not in agent_block


def test_the_keeper_voiced_by_any_spelling_recalls_its_public_commitment(srv, voice, monkeypatch):
    """``keeper_history`` matches the situation's keeper exactly, so the
    canonical name must reach it: ``"tessera"`` still recalls the decision
    the keeper is bound to."""
    from datetime import datetime, timedelta

    from multiverse.situation import NODES
    from persistence import participants, situations

    stub, _ = voice
    seed = 382  # the authored situation's world
    start = datetime(2026, 9, 12, 12)
    monkeypatch.setattr(situations, "_now", lambda: start)
    situations.install(seed)
    ada = participants.identify(ADA_KEY)["id"]
    for role in ("instrument", "regulator"):
        situations.discover(seed, ada, NODES[role])
    situations.choose(seed, ada, "keeper-recall-choice", "preserve")
    situations.advance(seed, now=start + timedelta(seconds=61))
    committed = [row for row in persistence.get_mutations(seed, limit=1000)
                 if row["type"] == "SITUATION_COMMITTED"]
    assert len(committed) == 1 and committed[0]["node"] == NODES["regulator"]
    holds = "The shared decision holds: Keep the signal under Tessera’s care."
    assert committed[0]["data"]["flavor"].startswith(holds)
    # Voiced at the gallery: the commitment was recorded at the regulator,
    # so only the keeper's recall can bring it into the prompt. Unescaped:
    # by default json.dumps writes the apostrophe as an escape, and the
    # check could never fail.
    gallery = NODES["gallery"]
    gallery_history = persistence.get_node_history(seed, gallery)
    assert committed[0]["id"] not in {event.get("id") for event in gallery_history}
    assert holds not in json.dumps(gallery_history, ensure_ascii=False)
    status, data = _request(srv, "/agent/voice", body={
        "seed": seed, "node_name": gallery, "agent_name": "tessera",
        "message": "what did we decide?"})
    assert status == 200 and data["agent"] == KEEPER == "Tessera" and data["ai"] is True, data
    assert len(stub.calls) == 1
    agent_block = stub.calls[0]["system"][-1].text
    assert holds in agent_block


def test_a_missing_agent_name_is_still_scout(srv, voice):
    stub, _ = voice
    seed = 4607
    node = generate_node_hierarchy(seed=seed, max_depth=1)
    status, data = _request(srv, "/agent/voice", body={
        "seed": seed, "node_name": node.name, "message": "hello, old light"})
    assert status == 200 and data["agent"] == "Scout" and data["ai"] is True
    assert [row["data"]["agent"] for row in _agent_rows(seed, "AGENT_VOICE")] == ["Scout"]


# ── No player may claim a server-owned identity ─────────────────────────────

@pytest.fixture()
def open_srv():
    """No key minted: the ungated local-dev path where names are client-chosen."""
    server = _ThreadedServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield port
    server.shutdown()
    server.server_close()
    thread.join(5)


@pytest.mark.parametrize("name", ["Scout", "observer", " OBSERVER ", "Tessera"])
def test_registration_refuses_an_agent_name_and_keeps_the_token(open_srv, name):
    persistence.create_registration_token("nwr_live")
    status, data = _request(open_srv, "/register", key="",
                            body={"invite": "nwr_live", "name": name})
    assert status == 403 and data["error"] == (
        f"'{name.strip()}' belongs to the world — choose another name")
    assert persistence.lookup_registration_token("nwr_live") is not None
    assert persistence.list_invite_keys() == []
    # Not over-broad: a name that merely contains one is a player's.
    status, data = _request(open_srv, "/register", key="",
                            body={"invite": "nwr_live", "name": "Scoutmaster"})
    assert status == 200, data
    assert [row["name"] for row in persistence.list_invite_keys()] == ["Scoutmaster"]


@pytest.mark.parametrize("name", ["Scout", "%20observer", "OBSERVER"])
def test_keyless_ws_join_as_an_agent_is_refused(open_srv, name):
    sock, status = _ws_connect(open_srv, 4610, name)
    try:
        assert b"403" in status
    finally:
        sock.close()
    assert persistence.get_mutations(4610) == []


def test_keyless_body_name_of_an_agent_is_recorded_anonymously(open_srv):
    seed = 4611
    node = generate_node_hierarchy(seed=seed, max_depth=1)
    for name in ("Observer", " scout "):
        status, _ = _request(open_srv, "/puzzle/attempt", key="", body={
            "seed": seed, "depth": 1, "node_name": node.name,
            "answer": "not it", "player_name": name})
        assert status == 200
    attempts = [row for row in persistence.get_mutations(seed)
                if row["type"] == "PUZZLE_ATTEMPT"]
    assert len(attempts) == 2 and {row["player"] for row in attempts} == {None}


@pytest.mark.parametrize("name", ["Scout", " observer "])
def test_mint_cli_refuses_an_agent_name(name):
    import main

    class Args:
        invite_action = "mint"
        note = None
        unscreened = True

    Args.name = name
    with pytest.raises(SystemExit, match="reserved world name"):
        main.cmd_invite(Args())
    assert persistence.list_invite_keys() == []


@pytest.mark.parametrize("name", ["Observer", "SCOUT"])
def test_play_cli_refuses_an_agent_name(monkeypatch, name):
    import main
    started = []
    monkeypatch.setattr("interface.run_session", lambda **kwargs: started.append(kwargs))

    class Args:
        seed = 42
        depth = 1

    Args.name = name
    with pytest.raises(SystemExit, match="reserved world name"):
        main.cmd_play(Args())
    assert started == []
