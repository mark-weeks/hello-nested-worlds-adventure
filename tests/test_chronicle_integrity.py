"""Chronicle integrity: every event lands exactly once, attributed to a
durable actor identity — because the chronicle is permanent and attribution
can never be backfilled.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import urllib.request

import pytest

import persistence
from multiverse.generator import generate_node_hierarchy


@pytest.fixture(autouse=True)
def _zero_hop_delay(monkeypatch):
    monkeypatch.setenv("NESTED_WORLDS_HOP_DELAY", "0")
    # Legacy semantics: these tests predate deep time; verbs act instantly.
    monkeypatch.setenv("NESTED_WORLDS_MATURATION_SCALE", "0")
    yield


@pytest.fixture()
def srv():
    from server import _Handler, _ThreadedServer
    server = _ThreadedServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


def _post(srv, path, body, headers=None):
    req = urllib.request.Request(
        f"{srv}{path}", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


class TestSchema:
    def test_actor_identity_column_exists(self):
        persistence.init_db()
        with sqlite3.connect(persistence._DB_PATH) as conn:
            cols = {r[1] for r in conn.execute(
                "PRAGMA table_info(world_mutations)")}
        assert "actor_identity" in cols


class TestSingleCanonicalRecord:
    def test_act_records_exactly_once_at_origin(self, srv):
        root = generate_node_hierarchy(seed=142, max_depth=6)
        target = root.children[0]
        _post(srv, "/act", {"seed": 142, "depth": 6,
                            "node_name": target.name, "player_name": "Ada"})
        acts = [h for h in persistence.get_node_history(142, target.name, 50)
                if h["type"] == "SCALE_ACT"]
        assert len(acts) == 1, "origin must not double-record"
        assert acts[0]["player"] == "Ada"

    def test_solve_records_exactly_once_at_origin(self, srv):
        from puzzles.engine import build_puzzle
        root = generate_node_hierarchy(seed=142, max_depth=6)
        target = root.children[0]
        answer = build_puzzle(target).answer
        data = _post(srv, "/puzzle/attempt", {
            "seed": 142, "depth": 6, "node_name": target.name,
            "answer": answer, "player_name": "Ada"})
        assert data["correct"] is True
        solves = [h for h in persistence.get_node_history(142, target.name, 50)
                  if h["type"] == "PUZZLE_SOLVED"]
        assert len(solves) == 1, "origin must not double-record"
        assert solves[0]["player"] == "Ada"

    def test_staged_rings_still_record(self, srv):
        # Suppressing the origin duplicate must NOT silence the rings: hop
        # rows are the only chronicle trace those nodes get.
        from causality.staging import drain_due_hops
        root = generate_node_hierarchy(seed=143, max_depth=6)
        target = root.children[0]
        _post(srv, "/act", {"seed": 143, "depth": 6,
                            "node_name": target.name, "player_name": "Ada"})
        assert persistence.pending_causal_hops(143) >= 2
        drain_due_hops()
        parent_types = [h["type"] for h in
                        persistence.get_node_history(143, root.name, 50)]
        assert "SCALE_ACT" in parent_types


class TestActorIdentity:
    def test_credentialed_act_carries_the_stable_hash(self, srv):
        # Mint a real per-user key; the chronicle row must carry
        # sha256(key)[:16], not just the mutable display name.
        key = "nw_integrity_test_key"
        persistence.mint_invite_key(key, "Ada", note="test")
        expected = hashlib.sha256(key.encode()).hexdigest()[:16]
        root = generate_node_hierarchy(seed=144, max_depth=6)
        _post(srv, "/act",
              {"seed": 144, "depth": 6, "node_name": root.children[0].name,
               "player_name": "Ada"},
              headers={"X-Beta-Key": key})
        page = persistence.get_chronicle(144)
        acts = [e for e in page["entries"] if e["type"] == "SCALE_ACT"]
        assert acts and acts[0]["actor"] == expected
        assert acts[0]["player"] == "Ada"  # display label preserved alongside

    def test_keyless_act_falls_back_to_display_name(self, srv):
        root = generate_node_hierarchy(seed=145, max_depth=6)
        _post(srv, "/act", {"seed": 145, "depth": 6,
                            "node_name": root.children[0].name,
                            "player_name": "Freya"})
        page = persistence.get_chronicle(145)
        acts = [e for e in page["entries"] if e["type"] == "SCALE_ACT"]
        assert acts and acts[0]["actor"] == "Freya"

    def test_failed_puzzle_keeps_its_human(self, srv):
        from puzzles.engine import build_puzzle
        root = generate_node_hierarchy(seed=146, max_depth=6)
        target = root.children[0]
        p = build_puzzle(target)
        data = None
        for _ in range(p.max_attempts):
            data = _post(srv, "/puzzle/attempt", {
                "seed": 146, "depth": 6, "node_name": target.name,
                "answer": "definitely wrong", "player_name": "Freya"})
        assert data["result"] == "FAILED"
        fails = [h for h in persistence.get_node_history(146, target.name, 50)
                 if h["type"] == "PUZZLE_FAILED"]
        assert fails and fails[0]["player"] == "Freya"

    def test_speak_row_carries_identity_column(self, srv):
        # /speak degrades to the fallback voice without an API key, but the
        # keyless path exercises attribution only on success; assert via the
        # persistence API directly instead.
        persistence.record_mutation(
            147, "Spire-11", "PLAYER_SPEAK", "Ada",
            {"message": "hello", "identity": "abcd"}, actor_identity="abcd")
        page = persistence.get_chronicle(147)
        assert page["entries"][0]["actor"] == "abcd"


class TestDeterministicOrder:
    def test_same_second_events_read_back_in_insert_order(self):
        for i in range(30):
            persistence.record_mutation(148, f"N-{i}", "AGENT_VISIT", None, {"i": i})
        muts = persistence.get_mutations(148, limit=30)
        seq = [m["data"]["i"] for m in muts]
        assert seq == sorted(seq, reverse=True), (
            "same-second rows must read back newest-first by id, "
            "not in arbitrary order")
