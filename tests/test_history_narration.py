"""M3 evidence from real HTTP/CLI/cast actions and immutable legacy fixtures."""
import json
import random
import threading
from contextlib import contextmanager
from unittest.mock import patch
import urllib.parse
import urllib.request

import pytest

import consciousness
import persistence
from causality.staging import drain_due_hops
from interface import _do_scale_verb
from multiverse import store
from multiverse.history import narrate
from server import _Handler, _ThreadedServer, heartbeat
from server.rooms import get_room
from tests.test_delayed_choices import change, land, walk
from tests.test_delivery_recovery import snapshot

SEED = 382


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("NESTED_WORLDS_CANONICAL_SEED", str(SEED))
    monkeypatch.setenv("NESTED_WORLDS_HOP_DELAY", "0")
    monkeypatch.setenv("NESTED_WORLDS_MATURATION_SCALE", "1")
    root = store.world_tree(SEED)
    server = _ThreadedServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_address[1]}"

    class Client:
        notices = []

        def node(self, level):
            return next(n for n in walk(root) if n.level == level)

        def get(self, endpoint, **params):
            with urllib.request.urlopen(url + endpoint + "?" + urllib.parse.urlencode(params)) as reply:
                return json.load(reply)

        def post(self, node, name="Ada", endpoint="/act", **body):
            req = urllib.request.Request(url + endpoint, data=json.dumps({
                "node_name": node.name, "player_name": name, **body}).encode(),
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req) as reply:
                return json.load(reply)

    client = Client()
    client.root = root
    with patch("server.handlers.broadcast", side_effect=lambda room, msg: client.notices.append(msg)), \
            patch("server.heartbeat.broadcast", side_effect=lambda room, msg: client.notices.append(msg)):
        try:
            yield client
        finally:
            server.shutdown()
            server.server_close()
            thread.join(5)


def assert_live_agrees(client):
    entries = client.get("/chronicle", limit=200)["entries"]
    by_id = {r["id"]: r for r in entries}
    messages = [m for m in client.notices if m.get("narration")]
    assert messages
    for message in messages:
        assert message["narration"] == by_id[message["event_id"]]["narration"]
    return entries


def test_real_actions_reach_other_places_and_all_reads_agree(client):
    planet = client.node("Planet")
    galaxy = client.node("Galaxy")
    first = client.post(planet, "Ada")
    replies = [client.post(galaxy, name) for name in ("Ada", "Bea", "Ada")]
    assert len({r["event_id"] for r in replies}) == 3  # names never coalesce actions
    for _ in range(2):
        drain_due_hops(64, world_seed=SEED, broadcaster_batch=heartbeat._pump_broadcast_batch)
    entries = assert_live_agrees(client)
    arrivals = [e for e in entries if e.get("narration", {}).get("phase") == "arrival"]
    assert {e["narration"]["source_event_id"] for e in arrivals} == {
        first["event_id"], *(r["event_id"] for r in replies)}
    for e in arrivals:
        n = e["narration"]
        assert n["origin"] != n["receiver"] == e["node"]
        assert "A ripple from" in n["text"] and "reached" in n["text"]
        assert "chose" not in n["text"] and e["delta"] is None
        assert n["actor_label"] in ("Ada", "Bea")
        source = client.get("/chronicle", before=n["source_event_id"] + 1, limit=1)["entries"][0]
        assert source["id"] == n["source_event_id"] and source["node"] == n["origin"]
    before = snapshot()
    recent = client.get("/history")["mutations"]
    assert all(e["narration"] == next(r for r in entries if r["id"] == e["id"])["narration"] for e in recent)
    local = client.get("/history", node_name=galaxy.parent.name)["mutations"]
    assert local and all(e["narration"]["phase"] == "arrival" for e in local)
    assert snapshot() == before  # every projection is read-only


def test_cli_and_cast_use_the_same_source_labels_without_taxonomy(client, capsys):
    galaxy = client.node("Galaxy")
    _do_scale_verb(galaxy, SEED, "CLIVisitor")
    assert "still traveling" in capsys.readouterr().out
    assert heartbeat._persona_act(SEED, get_room(SEED), client.root, "Tessera", "tender",
                                 [galaxy.name], random.Random(1))
    drain_due_hops(64, heartbeat._pump_broadcaster, SEED)
    assert land() == 2
    entries = assert_live_agrees(client)
    for phase in ("accepted", "arrival", "outcome"):
        rows = [e for e in entries if e.get("narration", {}).get("phase") == phase]
        assert {e["narration"]["actor_label"] for e in rows} == {"CLIVisitor", "Tessera"}
        for e in rows:
            assert not {"actor_identity", "persona", "actor_type", "agent"} & e["narration"].keys()
            assert "tender" not in e["narration"]["text"]


@pytest.mark.parametrize("outcome", ["applied", "already_satisfied", "precondition_changed"])
def test_shared_pending_and_terminal_outcomes_remain_honest(client, outcome):
    node = client.node("Galaxy")
    change(node, {"star_density": 999, "kindled": False})
    accepted = client.post(node)
    shared = client.post(node, "Bea")
    assert shared["action_status"] == "shared" and shared["work"] == accepted["work"]
    assert client.get("/node", node_name=node.name)["node"]["pending_actions"][0]["count"] == 1
    if outcome == "already_satisfied":
        change(node, {"kindled": True})
    elif outcome == "precondition_changed":
        change(node, {"star_density": None})
    assert land() == 1
    entries = assert_live_agrees(client)
    landed = next(e for e in entries if e["type"] == "SCALE_ACT_MATURED")
    assert landed["data"]["outcome"] == outcome
    assert landed["narration"]["source_event_id"] == accepted["event_id"]
    assert landed["narration"]["actor_label"] == "Ada"  # join adds no attribution
    if outcome == "applied":
        assert landed["delta"] == {"kindled": True}
        assert landed["data"]["flavor"] in landed["narration"]["text"]
    else:
        assert landed["delta"] is None and landed["node_version"] is None
        assert landed["data"]["flavor"] in landed["narration"]["text"]
    origin = next(e for e in entries if e["id"] == accepted["event_id"])
    assert origin["narration"]["phase"] == "accepted"  # landing cannot rewrite acceptance
    assert "delayed outcome was accepted" in origin["narration"]["text"]


def test_v1_and_v2_outcomes_resolve_retained_delivery_without_reinterpretation(client):
    node = client.node("Galaxy")
    accepted = client.post(node, "Current")
    # Faithful pre-M2 rows: absolute patch and no source_event_id in landed data.
    old_ids = []
    for _ in range(2):
        with persistence.transaction():
            persistence.record_mutation(SEED, node.name, "SCALE_ACT", "Legacy",
                                        {"verb": "kindle", "matures_in": 5})
            source = persistence.latest_event_id()
            old_ids.append(source)
            persistence.enqueue_verb_maturation(SEED, node.name, "kindle", {"star_density": 500},
                                               "Legacy", 0, source_event_id=source)
    assert land() == 3
    entries = assert_live_agrees(client)
    landed = [e for e in entries if e["type"] == "SCALE_ACT_MATURED"]
    assert {e["narration"]["source_event_id"] for e in landed} == {*old_ids, accepted["event_id"]}
    old = [e for e in landed if e["narration"]["actor_label"] == "Legacy"]
    assert len(old) == 2 and all(e["delta"] == {"star_density": 500} for e in old)
    assert len({e["node_version"] for e in old}) == 2


@pytest.mark.parametrize("data,phase,actor,origin", [
    ({"verb": "seed", "_origin": "Same Name-11", "actor": "Ada"}, "arrival", "Ada", "Same Name-11"),
    ({"verb": "seed", "_hop": 2}, "arrival", None, None),
    ({"verb": "seed", "agent": "Tessera"}, "trace", "Tessera", None),
    ({}, "trace", None, None),
    ({"verb": "kindle", "matures_in": 0}, "accepted", None, "Same Name-12"),
])
def test_legacy_partial_evidence_never_fabricates_actor_or_unique_name(data, phase, actor, origin):
    persistence.record_mutation(SEED, "Same Name-12", "SCALE_ACT", None, data,
                                actor_identity="private-credential-hash")
    before = snapshot()
    row = persistence.get_chronicle(SEED)["entries"][0]
    n = row["narration"]
    assert (n["phase"], n["actor_label"], n["origin"]) == (phase, actor, origin)
    assert n["source_event_id"] is None
    assert "[12]" in n["text"] and "private-credential" not in n["text"]
    if phase in ("arrival", "trace"):
        assert "chose" not in n["text"]
        assert ("unrecorded" if phase == "arrival" else "No material change is recorded.") in n["text"]
    if origin and phase == "arrival":
        assert "[11]" in n["text"]  # equal display names retain distinct canonical addresses
    assert snapshot() == before


@pytest.mark.parametrize("defect", ["missing", "other_world", "wrong_kind", "wrong_node", "conflict"])
def test_broken_source_references_do_not_borrow_attribution(defect):
    seed = 999 if defect == "other_world" else SEED
    persistence.record_mutation(seed, "Source-11", "PLAYER_CHAT" if defect == "wrong_kind" else "SCALE_ACT",
                                "WrongPerson", {"verb": "seed", "matures_in": 5})
    source = persistence.get_mutations(seed)[0]["id"]
    work_id = persistence.enqueue_causal_hop(
        SEED, "Wrong-13" if defect == "wrong_node" else "Receiver-12", "SCALE_ACT", .5, "up", {}, 0,
        source_event_id=99999 if defect == "missing" else source)
    data = {"verb": "seed", "_origin": "Source-11", "delivery": {"queue": "causal_queue", "id": work_id}}
    if defect == "conflict":
        data["source_event_id"] = source + 100
    persistence.record_mutation(SEED, "Receiver-12", "SCALE_ACT", None, data)
    n = persistence.get_mutations(SEED)[0]["narration"]
    assert n["source_event_id"] is None and n["actor_label"] is None
    assert "WrongPerson" not in n["text"] and "unrecorded" in n["text"]


def test_page_projection_has_constant_query_count_and_no_world_hydration(client):
    node = client.node("Galaxy")
    for name in ("Ada", "Bea", "Cy"):
        client.post(node, name)
    drain_due_hops(64, heartbeat._pump_broadcaster, SEED)
    land()
    original_connect = persistence._connect
    queries = []

    @contextmanager
    def traced():
        with original_connect() as conn:
            conn.set_trace_callback(queries.append)
            yield conn

    with patch.object(persistence, "_connect", traced), \
            patch.object(store, "world_tree", side_effect=AssertionError("no world hydration")):
        page = persistence.get_mutations(SEED, limit=200)
    assert len(page) > 10
    assert len([q for q in queries if q.startswith("SELECT")]) == 4
    assert not any("actor_identity" in q or "world_nodes" in q for q in queries)


def test_node_and_agent_speech_receive_arrival_evidence(client):
    node = client.node("Galaxy")
    accepted = client.post(node, "Ada")
    drain_due_hops(64, heartbeat._pump_broadcaster, SEED)
    captured = []

    def voice(*args, **kwargs):
        captured.append(consciousness._history_block(kwargs["history"]))
        return "The ripple is remembered."

    with patch.object(consciousness, "speak", side_effect=voice), \
            patch.object(consciousness, "voice_agent", side_effect=voice):
        client.post(node.parent, endpoint="/speak", message="What happened here?")
        client.post(node.parent, endpoint="/agent/voice", agent_name="Tessera", message="What arrived?")
    assert len(captured) == 2
    for block in captured:
        assert "A ripple from Ada's kindle" in block
        assert f"Source action #{accepted['event_id']}" in block
        assert "scale act, by" not in block and "chose to kindle" not in block


def test_unannotated_speech_history_is_conservative():
    row = {"type": "SCALE_ACT", "node": "Receiver-12", "data": {
        "_origin": "Source-11", "actor": "Ada", "verb": "seed"}}
    assert narrate(row)["text"] in consciousness._history_block([row])


def test_failed_post_commit_projection_keeps_acceptance_and_delivery(client):
    with patch.object(persistence, "presented_mutations", side_effect=RuntimeError("read unavailable")):
        result = client.post(client.node("Galaxy"))
        assert result["action_status"] == "accepted"
        assert land() == 1
    assert persistence.inspect_work("verb_maturation", result["work"]["id"])["status"] == "completed"
    assert client.get("/history")["mutations"][0]["narration"]["source_event_id"] == result["event_id"]


def test_live_batches_bound_projection_and_send_failure_does_not_replay(client):
    for name in ("Ada", "Bea", "Cy"):
        client.post(client.node("Galaxy"), name)
    with patch.object(persistence, "presented_mutations", wraps=persistence.presented_mutations) as project, \
            patch("causality.delivery.monotonic", return_value=0):
        drain_due_hops(64, world_seed=SEED, broadcaster_batch=heartbeat._pump_broadcast_batch)
        sizes = [len(call.args[1]) for call in project.call_args_list]
        assert sum(sizes) > 3
        assert sizes == [8] * (sum(sizes) // 8) + ([sum(sizes) % 8] if sum(sizes) % 8 else [])
    calls = []

    def broken(room, message):
        calls.append(message)
        if len(calls) == 1:
            raise OSError("lost first send")

    with patch("server.heartbeat.broadcast", side_effect=broken), \
            patch.object(persistence, "presented_mutations", wraps=persistence.presented_mutations) as project, \
            patch("causality.delivery.monotonic", return_value=0):
        assert land() == 3
        assert project.call_count == 1
    assert len(calls) == 3
    assert land() == 0
    assert len([e for e in persistence.get_mutations(SEED) if e["type"] == "SCALE_ACT_MATURED"]) == 3


@pytest.mark.parametrize("data", [None, [], {"actor": [], "_origin": 9},
                                  {"delivery": {"queue": [], "id": {}}}])
def test_malformed_legacy_metadata_keeps_history_readable(data):
    persistence.record_mutation(SEED, "Receiver-12", "SCALE_ACT", None, data)
    n = persistence.get_mutations(SEED)[0]["narration"]
    assert n["actor_label"] is None and n["origin"] is None
    assert ("unrecorded" if n["phase"] == "arrival" else "No material change is recorded.") in n["text"]


def test_legacy_first_hand_trace_reports_missing_change_in_reads_and_speech():
    persistence.record_mutation(SEED, "Mire-112", "SCALE_ACT", "Ada", {"verb": "ward"})
    rows = [persistence.get_node_history(SEED, "Mire-112")[0],
            persistence.get_chronicle(SEED)["entries"][0]]
    for row in rows:
        text = row["narration"]["text"]
        assert text == "A trace of ward attributed to Ada was recorded at Mire [112]. No material change is recorded."
        assert text in consciousness._history_block([row])


def test_count_style_history_read_is_one_query_and_keeps_bounded_window():
    with persistence.transaction():
        for index in range(1005):
            persistence.record_mutation(SEED, "Mire-112", "SCALE_ACT", "Ada", {"verb": "ward", "index": index})
    original_connect = persistence._connect
    queries = []

    @contextmanager
    def traced():
        with original_connect() as conn:
            conn.set_trace_callback(queries.append)
            yield conn

    with patch.object(persistence, "_connect", traced), \
            patch("persistence.history.project", side_effect=AssertionError("unused narration")):
        rows = persistence.get_node_history(SEED, "Mire-112", 1000, include_narration=False)
    assert len(rows) == 1000
    assert rows[0]["data"]["index"] == 1004 and rows[-1]["data"]["index"] == 5
    assert all("narration" not in row for row in rows)
    assert len([q for q in queries if q.startswith("SELECT")]) == 1


def test_image_and_banter_keep_style_and_ordinal_without_projection(client, monkeypatch):
    from agents.banter import compose_exchange
    from server import imageprompt

    monkeypatch.delenv("NESTED_WORLDS_DISABLE_IMAGES", raising=False)
    node = client.node("Galaxy")
    for index in range(55):
        persistence.record_mutation(SEED, node.name, "AGENT_TALK" if index % 10 == 0 else "PLAYER_CHAT",
                                    "Ada" if index % 2 else "Bea", {})
    history = persistence.get_node_history(SEED, node.name, 1000)
    expected_key = f"{SEED}:{node.name}:{len(history) // 5}:{imageprompt.style_signature(node.level, node.properties, history)}"
    ordinal = sum(h["type"] == "AGENT_TALK" for h in history[:50])
    with patch("persistence.history.project", side_effect=AssertionError("unused narration")), \
            patch.object(persistence, "get_cached_image", return_value="https://example.test/image.png") as cached, \
            patch("agents.banter.compose_exchange", wraps=compose_exchange) as compose:
        reply = client.post(node, endpoint="/image")
        heartbeat._hold_conversation(SEED, get_room(SEED), node, "Tessera", "scholar", "Karst", "tender")
    assert reply["url"] == "https://example.test/image.png"
    cached.assert_called_once_with(expected_key)
    assert compose.call_args.kwargs["ordinal"] == ordinal == 5


@pytest.mark.parametrize("trigger", ["commits", "time"])
def test_live_batch_flushes_before_the_rest_of_the_real_drain(client, trigger):
    count = 9 if trigger == "commits" else 3
    accepted = [client.post(client.node("Galaxy"), f"Visitor{index}") for index in range(count)]
    work_ids = [a["work"]["id"] for a in accepted]
    clock = [0.0]
    sent = []
    original_apply = heartbeat._apply_maturation
    applied = 0

    def apply(row, notifications):
        nonlocal applied
        # The next transaction starts only after the preceding partial batch
        # has been published. Assertions are outside the callback error guard.
        if applied == (8 if trigger == "commits" else 2):
            assert [m["work_id"] for m in sent] == work_ids[:applied]
        applied += 1
        if trigger == "time" and applied == 2:
            clock[0] = 0.06
        return original_apply(row, notifications)

    def capture(room, message):
        assert persistence.inspect_work("verb_maturation", message["work_id"])["status"] == "completed"
        sent.append(message)

    with patch("causality.delivery.monotonic", side_effect=lambda: clock[0]), \
            patch.object(heartbeat, "_apply_maturation", side_effect=apply), \
            patch("server.heartbeat.broadcast", side_effect=capture), \
            patch.object(persistence, "presented_mutations", wraps=persistence.presented_mutations) as project:
        assert land() == count
        assert project.call_count == 2
    assert [m["work_id"] for m in sent] == work_ids
    assert len({m["event_id"] for m in sent}) == count
    assert land() == 0


def test_partial_committed_notices_flush_if_later_delivery_aborts(client):
    accepted = [client.post(client.node("Galaxy"), name) for name in ("Ada", "Bea", "Cy")]
    original_deliver = persistence.deliver_work
    calls = 0

    def deliver(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise RuntimeError("drain interrupted")
        return original_deliver(*args, **kwargs)

    with patch.object(persistence, "deliver_work", side_effect=deliver), \
            patch("causality.delivery.monotonic", return_value=0):
        with pytest.raises(RuntimeError, match="drain interrupted"):
            land()
    matured = [m for m in client.notices if m.get("matured")]
    assert [m["work_id"] for m in matured] == [a["work"]["id"] for a in accepted[:2]]
    assert land() == 1
    assert land() == 0


def test_malformed_legacy_waits_and_patches_do_not_invent_acceptance_or_change():
    for value in (None, "0", "later", {}, [], True, -1, float("inf"), float("nan")):
        row = {"type": "SCALE_ACT", "node": "Mire-112", "data": {"matures_in": value}}
        assert narrate(row)["phase"] == "trace"
    for value in (None, {}, [], [1], "changed", True, 1):
        for row in ({"delta": value}, {"data": {"changed": value}}):
            assert narrate({"type": "SCALE_ACT", "node": "Mire-112", **row})["phase"] == "trace"
    for changed in ({"count": 0}, {"active": False}, {"mark": None}):
        row = {"type": "SCALE_ACT", "node": "Mire-112", "delta": {}, "data": {"changed": changed}}
        assert narrate(row)["phase"] == "action"


@pytest.mark.parametrize("kind", ["AGENT_VISIT", "PUZZLE_SOLVED", "PUZZLE_FAILED",
                                  "DANGER_ALERT", "STRUCTURAL_CHANGE", "CONSTELLATION_COMPLETE"])
def test_other_arriving_effects_use_fictional_events_without_actor_taxonomy(kind):
    row = {"type": kind, "node": "Receiver-12", "data": {
        "_origin": "Source-11", "agent": "Tessera", "persona": "scholar"}}
    text = narrate(row)["text"]
    assert "An effect from" in text and "by Tessera" in text
    assert "Source [11]" in text and "reached Receiver [12]" in text
    assert not any(term in text.lower() for term in ("agent", "human", "scholar"))
    assert text in consciousness._history_block([row])
