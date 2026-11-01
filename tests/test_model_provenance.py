"""Chronicle provenance is the call result, and older rows stay unknown."""
from contextlib import closing
from copy import deepcopy
import json
import logging
from pathlib import Path
import shutil
import sqlite3
import sys
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import quote

import persistence
from consciousness.interventions import Interpreted
from consciousness.runtime import Completion, Voiced
from multiverse import store
from multiverse.situation import NODES


RESOLVED = "fixture-resolved-20261025"
NODE_ALIAS = "alias-node-not-stored"
INHABITANT_ALIAS = "alias-inhabitant-not-stored"
INTENT_ALIAS = "alias-intent-not-stored"
SHARED_ALIAS = "alias-shared-not-stored"
SERVED = {
    NODE_ALIAS: "served-node-20261025",
    INHABITANT_ALIAS: "served-inhabitant-20261025",
    INTENT_ALIAS: "served-intent-20261025",
}
READY = '{"status":"ready","ambiguity":"none","steps":[{"op":"engrave","amount":1}]}'
CLARIFY = '{"status":"clarify","ambiguity":"action","steps":[]}'


def _image(conn):
    return conn.execute(
        """SELECT id, world_seed, node_name, mutation_type, player_name, data,
                  recorded_at, actor_identity, strength, delta, node_version
           FROM world_mutations ORDER BY id"""
    ).fetchall()


def _marks(conn):
    return conn.execute(
        "SELECT mutation_id, provider, resolved_model FROM mutation_model_provenance ORDER BY mutation_id"
    ).fetchall()


class Stub:
    name = "fixture"

    def __init__(self, text=READY, available=True, fail=False, omit_resolved=False):
        self.text = text
        self.available = available
        self.fail = fail
        self.omit_resolved = omit_resolved
        self.calls = []

    def configured(self):
        return self.available

    def cache_reference_tokens(self, model):
        return None

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("upstream detail")
        # The served id is the fake provider's call result. It is not the
        # alias model_for put on the request, and it is not read from config.
        resolved = None if self.omit_resolved else SERVED.get(kwargs.get("model"), RESOLVED)
        return Completion(self.text, True, resolved_model=resolved, provider=self.name)


def _enable(monkeypatch, stub):
    from consciousness import runtime
    from server import guard, moderation
    monkeypatch.delenv(guard.DISABLE_AI_ENV, raising=False)
    monkeypatch.delenv("NESTED_WORLDS_MUTATION_TTL_DAYS", raising=False)
    monkeypatch.setenv(guard.ANTHROPIC_CAP_ENV, "100")
    monkeypatch.setenv(guard.ANTHROPIC_PER_USER_CAP_ENV, "100")
    for name in (runtime.NODE_MODEL_ENV, runtime.INHABITANT_MODEL_ENV,
                 runtime.INTENT_MODEL_ENV, runtime.SHARED_MODEL_ENV,
                 runtime.MODERATION_MODEL_ENV):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(runtime.SHARED_MODEL_ENV, SHARED_ALIAS)
    monkeypatch.setenv(runtime.NODE_MODEL_ENV, NODE_ALIAS)
    monkeypatch.setenv(runtime.INHABITANT_MODEL_ENV, INHABITANT_ALIAS)
    monkeypatch.setenv(runtime.INTENT_MODEL_ENV, INTENT_ALIAS)
    monkeypatch.setattr(runtime, "get_provider", lambda: stub)
    monkeypatch.setattr(moderation, "screen", lambda text, **_kwargs: SimpleNamespace(allowed=True))
    monkeypatch.setattr(guard, "consume_anthropic", lambda **kwargs: True)


def _rows():
    with persistence._connect() as conn:
        return conn.execute(
            """SELECT id, mutation_type, data FROM world_mutations ORDER BY id"""
        ).fetchall()


def test_migration_on_a_copy_leaves_prior_rows_byte_identical(tmp_path, monkeypatch):
    monkeypatch.delenv("NESTED_WORLDS_MUTATION_TTL_DAYS", raising=False)
    migrations = persistence._list_migrations()
    assert max(version for version, _ in migrations) == 28
    prior = [item for item in migrations if item[0] < 28]
    assert prior[-1][0] == 27
    with patch.object(persistence, "_list_migrations", return_value=prior):
        persistence.init_db()
        persistence.record_mutation(
            7, "Vault-11", "PLAYER_SPEAK", "Ada",
            {"message": "hello", "reply": "an old voice", "puzzle": "Keep", "correct": True},
            actor_identity="abcd1234")
        persistence.record_mutation(
            7, "Vault-11", "PUZZLE_SOLVED", "Ada", {"puzzle": "The Lock"})
        with persistence._connect() as conn:
            before = conn.execute("SELECT * FROM world_mutations ORDER BY id").fetchall()
            before_image = _image(conn)
            names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master")}
        assert "mutation_model_provenance" not in names
    snapshot = tmp_path / "pre-provenance.db"
    persistence.backup_to(snapshot)
    with closing(sqlite3.connect(snapshot)) as conn:
        before_inserts = [line for line in conn.iterdump() if "world_mutations" in line and line.startswith("INSERT")]
    upgraded = tmp_path / "upgraded.db"
    shutil.copyfile(snapshot, upgraded)
    monkeypatch.setattr(persistence, "_DB_PATH", upgraded)
    persistence._initialized.discard(upgraded)
    persistence.init_db()
    with persistence._connect() as conn:
        after = conn.execute("SELECT * FROM world_mutations ORDER BY id").fetchall()
        after_image = _image(conn)
        assert _marks(conn) == []
        versions = [row[0] for row in conn.execute("SELECT version FROM schema_version ORDER BY version")]
    assert after == before
    assert after_image == before_image
    with closing(sqlite3.connect(upgraded)) as conn:
        after_inserts = [line for line in conn.iterdump() if "world_mutations" in line and line.startswith("INSERT")]
    assert after_inserts == before_inserts
    assert 28 in versions and 27 in versions
    for row_id in (row[0] for row in before):
        assert persistence.provenance_of(row_id) == {"provider": None, "resolved_model": None}


def test_restored_older_backup_does_not_claim_a_provider(tmp_path, monkeypatch):
    monkeypatch.delenv("NESTED_WORLDS_MUTATION_TTL_DAYS", raising=False)
    migrations = [item for item in persistence._list_migrations() if item[0] < 28]
    with patch.object(persistence, "_list_migrations", return_value=migrations):
        persistence.init_db()
        persistence.record_mutation(7, "Vault-11", "AGENT_VISIT", None, {"agent": "Scout"})
    snapshot = tmp_path / "old.db"
    persistence.backup_to(snapshot)
    with persistence._connect() as conn:
        original = _image(conn)
    live = tmp_path / "live.db"
    monkeypatch.setattr(persistence, "_DB_PATH", live)
    persistence._initialized.discard(live)
    persistence.init_db()
    persistence.restore_from(snapshot)
    # Restart has not run: the restored file has no side table, and a model
    # write must still append the chronicle row.
    persistence.record_mutation(
        7, "Vault-11", "PLAYER_SPEAK", "Ada", {"message": "hi", "reply": "kept"},
        model_provider="fixture", resolved_model=RESOLVED)
    with persistence._connect() as conn:
        assert not conn.execute(
            """SELECT 1 FROM sqlite_master
               WHERE type = 'table' AND name = 'mutation_model_provenance'"""
        ).fetchone()
        assert len(_image(conn)) == 2
    spoken = [row for row in _rows() if row[1] == "PLAYER_SPEAK"]
    assert len(spoken) == 1
    assert persistence.provenance_of(spoken[0][0]) == {"provider": None, "resolved_model": None}
    persistence._initialized.discard(live)
    persistence.init_db()
    with persistence._connect() as conn:
        image = _image(conn)
        assert _marks(conn) == []
    assert image[:1] == original
    assert json.loads(image[1][5])["reply"] == "kept"
    assert persistence.provenance_of(image[1][0]) == {"provider": None, "resolved_model": None}
    # An older column list still reads and appends on the upgraded file.
    with persistence._connect() as conn:
        conn.execute(
            """INSERT INTO world_mutations
               (world_seed, node_name, mutation_type, player_name, data, actor_identity, strength)
               VALUES (7, 'Vault-11', 'PLAYER_CHAT', 'Ada', '{"text":"authored"}', 'abcd', NULL)"""
        )
        chat = conn.execute(
            """SELECT mutation_type, data, actor_identity, strength
               FROM world_mutations WHERE mutation_type = 'PLAYER_CHAT'"""
        ).fetchone()
    assert chat == ("PLAYER_CHAT", '{"text":"authored"}', "abcd", None)
    chat_id = persistence.find_mutations_by_text("authored")[0]["id"]
    assert persistence.provenance_of(chat_id) == {"provider": None, "resolved_model": None}


def test_new_rows_record_only_the_call_result(monkeypatch):
    persistence.record_mutation(
        1, "N", "PLAYER_SPEAK", "Ada", {"reply": "one"},
        model_provider="fixture", resolved_model=None)
    persistence.record_mutation(
        1, "N", "PLAYER_SPEAK", "Ada", {"reply": "two"},
        model_provider=None, resolved_model=RESOLVED)
    persistence.record_mutation(
        1, "N", "PLAYER_SPEAK", "Ada", {"reply": "blank"},
        model_provider="  ", resolved_model=" \n ")
    persistence.record_mutation(
        1, "N", "AGENT_TALK", None, {"lines": ["authored banter"]},
        model_provider="x" * 201, resolved_model="y" * 201)
    persistence.record_mutation(
        1, "N", "PLAYER_SPEAK", "Ada", {"reply": "object"},
        model_provider={"name": "fixture"}, resolved_model=RESOLVED)  # type: ignore[arg-type]
    rows = _rows()
    assert persistence.provenance_of(rows[0][0]) == {"provider": "fixture", "resolved_model": None}
    assert persistence.provenance_of(rows[1][0]) == {"provider": None, "resolved_model": RESOLVED}
    assert persistence.provenance_of(rows[2][0]) == {"provider": None, "resolved_model": None}
    assert persistence.provenance_of(rows[3][0]) == {"provider": None, "resolved_model": None}
    assert persistence.provenance_of(rows[4][0]) == {"provider": None, "resolved_model": RESOLVED}
    assert persistence.provenance_of(999999) is None


def test_voice_and_intention_rows_use_the_stub_completion(http, monkeypatch):
    stub = Stub("A remembered voice.")
    _enable(monkeypatch, stub)
    node = store.world_tree(382)
    status, body, _ = http("/speak", body={"node_name": node.name, "message": "hello"})
    assert status == 200 and body == {"response": "A remembered voice.", "ai": True}
    assert stub.calls[0]["model"] == NODE_ALIAS
    assert stub.calls[0]["model"] != SHARED_ALIAS
    status, voice, _ = http("/agent/voice", body={
        "agent_name": "Tessera", "node_name": node.name, "message": "where are you?"})
    assert status == 200 and voice["response"] == "A remembered voice." and voice["ai"] is True
    assert stub.calls[1]["model"] == INHABITANT_ALIAS
    quoted = quote(node.name)
    status, history, _ = http(f"/history?seed=382&node_name={quoted}")
    assert status == 200
    kinds = [row["type"] for row in history["mutations"]]
    assert kinds.count("PLAYER_SPEAK") == 1 and kinds.count("AGENT_VOICE") == 1
    for row in history["mutations"]:
        assert "provider" not in row and "resolved_model" not in row
    dumped = json.dumps(history)
    assert "fixture" not in dumped
    for alias in (NODE_ALIAS, INHABITANT_ALIAS, SHARED_ALIAS):
        assert alias not in dumped
    status, chronicle, _ = http("/chronicle?seed=382")
    chronicle_dump = json.dumps(chronicle)
    assert "fixture" not in chronicle_dump and NODE_ALIAS not in chronicle_dump
    expected = {"PLAYER_SPEAK": SERVED[NODE_ALIAS], "AGENT_VOICE": SERVED[INHABITANT_ALIAS]}
    for row in history["mutations"]:
        if row["type"] in expected:
            assert persistence.provenance_of(row["id"]) == {
                "provider": "fixture", "resolved_model": expected[row["type"]]}
            assert expected[row["type"]] not in dumped
    found = persistence.find_mutations_by_text("remembered", world_seed=382)
    assert {row["provider"] for row in found} == {"fixture"}
    assert {row["resolved_model"] for row in found} == set(expected.values())

    name = NODES["instrument"]
    assert http("/position", body={"node": name, "seed": 382, "depth": 9})[0] == 200
    direct = http("/interventions/commit", body={
        "node": name, "steps": [{"op": "engrave"}], "version": 3, "request_id": "direct-steps-01"})
    assert direct[0] == 200 and direct[1]["accepted"]
    calls_after_direct = len(stub.calls)
    stub.text = READY
    interpreted = http("/interventions/commit", body={
        "node": name, "intention": "cut a pattern", "version": 3, "request_id": "model-steps-01"})
    assert interpreted[0] == 200 and interpreted[1]["accepted"]
    assert len(stub.calls) == calls_after_direct + 1
    assert stub.calls[-1]["model"] == INTENT_ALIAS
    assert "fixture" not in json.dumps(interpreted[1])
    assert INTENT_ALIAS not in json.dumps(interpreted[1])
    assert SERVED[INTENT_ALIAS] not in json.dumps(interpreted[1])
    stub.text = CLARIFY
    quiet = http("/interventions/commit", body={
        "node": name, "intention": "change it", "version": 3, "request_id": "clarify-steps-01"})
    assert quiet[0] == 200 and quiet[1]["clarification"] and not quiet[1]["accepted"]
    committed = []
    arrived = []
    for row_id, kind, blob in _rows():
        if kind == "INTERVENTION_COMMITTED":
            committed.append(row_id)
        elif kind == "INTERVENTION_ARRIVED":
            arrived.append(row_id)
    assert len(committed) >= 2 and arrived
    assert persistence.provenance_of(committed[0]) == {"provider": None, "resolved_model": None}
    assert persistence.provenance_of(committed[1]) == {
        "provider": "fixture", "resolved_model": SERVED[INTENT_ALIAS]}
    assert all(persistence.provenance_of(row_id) == {"provider": None, "resolved_model": None}
               for row_id in arrived)
    # The clarification persisted a receipt, not a chronicle row.
    assert not any(kind == "INTERVENTION_COMMITTED" and json.loads(blob).get("phase") == "clarify"
                   for _, kind, blob in _rows())
    with persistence._connect() as conn:
        assert len(_marks(conn)) == 3  # speak, agent voice, interpreted commit

    scripts = str(Path(__file__).resolve().parent.parent / "scripts")
    sys.path.insert(0, scripts)
    import beta_metrics
    metrics = beta_metrics.compute_metrics(persistence._DB_PATH, days=7, seed=382)
    assert metrics["model_provenance"] == [
        {"provider": "fixture", "resolved_model": served, "rows": 1}
        for served in sorted(SERVED.values())]
    rendered = beta_metrics.render(metrics)
    for served in SERVED.values():
        assert f"fixture / {served}" in rendered
    for alias in (NODE_ALIAS, INHABITANT_ALIAS, INTENT_ALIAS, SHARED_ALIAS):
        assert alias not in rendered


def test_missing_response_model_does_not_store_the_task_alias(http, monkeypatch):
    stub = Stub("A remembered voice.", omit_resolved=True)
    _enable(monkeypatch, stub)
    node = store.world_tree(382)
    status, body, _ = http("/speak", body={"node_name": node.name, "message": "hello"})
    assert status == 200 and body["ai"] is True
    assert stub.calls[0]["model"] == NODE_ALIAS
    rows = _rows()
    assert len(rows) == 1
    mark = persistence.provenance_of(rows[0][0])
    assert mark == {"provider": "fixture", "resolved_model": None}
    with persistence._connect() as conn:
        stored = conn.execute(
            "SELECT provider, resolved_model FROM mutation_model_provenance"
        ).fetchall()
    assert stored == [("fixture", None)]
    assert NODE_ALIAS not in json.dumps(stored)


def test_chronicle_row_delete_removes_provenance():
    """Break-glass hard delete is not a command. A DELETE of the chronicle row must not orphan the call result."""
    persistence.record_mutation(
        1, "N", "PLAYER_SPEAK", "Ada", {"reply": "erase me"},
        model_provider="fixture", resolved_model=SERVED[NODE_ALIAS])
    persistence.record_mutation(
        1, "N", "AGENT_VOICE", "Tessera", {"reply": "keep me"},
        model_provider="fixture", resolved_model=SERVED[INHABITANT_ALIAS])
    rows = _rows()
    gone, kept = rows[0][0], rows[1][0]
    with persistence._connect() as conn:
        conn.execute("DELETE FROM world_mutations WHERE id = ?", (gone,))
        remaining = conn.execute(
            "SELECT mutation_id, provider, resolved_model FROM mutation_model_provenance"
        ).fetchall()
        chronicle = conn.execute("SELECT id FROM world_mutations").fetchall()
    assert chronicle == [(kept,)]
    assert remaining == [(kept, "fixture", SERVED[INHABITANT_ALIAS])]
    assert persistence.provenance_of(gone) is None
    assert persistence.provenance_of(kept) == {
        "provider": "fixture", "resolved_model": SERVED[INHABITANT_ALIAS]}


def test_authored_fallback_records_no_provider(http, monkeypatch, caplog):
    import consciousness
    from consciousness import runtime
    stub = Stub(available=False)
    _enable(monkeypatch, stub)
    node = store.world_tree(382)
    status, body, _ = http("/speak", body={"node_name": node.name, "message": "hello"})
    assert status == 200 and body["ai"] is False
    assert body["response"] == consciousness.fallback_voice(node)
    assert stub.calls == []
    assert _rows() == []

    stub.available = True
    stub.fail = True
    caplog.set_level(logging.WARNING, logger="nested_worlds")
    status, body, _ = http("/speak", body={"node_name": node.name, "message": "hello"})
    assert status == 200 and body["ai"] is False
    assert body["response"] == consciousness.fallback_voice(node)
    assert _rows() == []
    fallbacks = [
        record.getMessage() for record in caplog.records
        if record.name == "nested_worlds" and record.getMessage().startswith("speak fallback")
    ]
    assert fallbacks == [f"speak fallback ({node.name}): RuntimeError"]
    assert "upstream detail" not in fallbacks[0]

    def authored(*args, **kwargs):
        return consciousness.fallback_voice(node)
    monkeypatch.setattr(consciousness, "speak", authored)
    monkeypatch.setattr(runtime, "configured", lambda: True)
    status, body, _ = http("/speak", body={"node_name": node.name, "message": "hello again"})
    assert status == 200 and body["ai"] is True
    rows = _rows()
    assert len(rows) == 1
    assert json.loads(rows[0][2])["reply"] == consciousness.fallback_voice(node)
    assert persistence.provenance_of(rows[0][0]) == {"provider": None, "resolved_model": None}


def test_cli_and_play_record_voiced_provenance_before_slicing(monkeypatch, capsys):
    import consciousness
    import main
    from interface import _speak_to
    node = store.world_tree(382)

    def voiced(*args, **kwargs):
        return Voiced("heard in full", "fixture", RESOLVED)
    monkeypatch.setattr(consciousness, "speak", voiced)
    main.cmd_speak(SimpleNamespace(seed=382, node=node.name, message="hello"))
    _speak_to(node, "hello there", seed=382, player_name="Ada")
    rows = _rows()
    assert len(rows) == 2
    assert all(persistence.provenance_of(row[0]) == {"provider": "fixture", "resolved_model": RESOLVED}
               for row in rows)
    assert all(json.loads(row[2])["reply"] == "heard in full" for row in rows)
    capsys.readouterr()


def test_redaction_tombstones_words_and_keeps_provenance():
    persistence.record_mutation(
        42, "Vault-11", "PLAYER_SPEAK", "Mallory",
        {"message": "something awful", "reply": "a model line",
         "puzzle": "The Sealed Room", "correct": False},
        actor_identity="aaaa1111",
        model_provider="fixture", resolved_model=RESOLVED)
    row_id = persistence.find_mutations_by_text("awful", world_seed=42)[0]["id"]
    summary = persistence.redact_mutation(row_id, reason="test cleanup")
    assert summary["fields"] == ["message", "reply"]
    data = persistence.get_mutations(42, limit=5)[0]["data"]
    assert data["message"] == "[redacted]" and data["reply"] == "[redacted]"
    assert data["puzzle"] == "The Sealed Room" and data["correct"] is False
    assert "provider" not in data and RESOLVED not in json.dumps(data)
    assert persistence.provenance_of(row_id) == {"provider": "fixture", "resolved_model": RESOLVED}
    with persistence._connect() as conn:
        identity = conn.execute(
            "SELECT actor_identity FROM world_mutations WHERE id = ?", (row_id,)
        ).fetchone()[0]
    assert identity == "aaaa1111"


def test_prune_removes_the_side_row_with_the_chronicle_row():
    persistence.record_mutation(
        1, "N", "PLAYER_SPEAK", "Ada", {"reply": "old"},
        model_provider="fixture", resolved_model=RESOLVED)
    with persistence._connect() as conn:
        conn.execute(
            "UPDATE world_mutations SET recorded_at = datetime('now', '-10 day')")
    assert persistence.prune_mutations(7) == 1
    with persistence._connect() as conn:
        assert _marks(conn) == []
        assert conn.execute("SELECT COUNT(*) FROM world_mutations").fetchone()[0] == 0


def test_voiced_text_keeps_string_behavior():
    heard = Voiced("A remembered voice.", "fixture", RESOLVED)
    assert heard == "A remembered voice."
    assert json.dumps({"response": heard}) == '{"response": "A remembered voice."}'
    assert type(heard[:4]) is str
    assert heard.provider == "fixture" and heard.resolved_model == RESOLVED
    copied = deepcopy(heard)
    assert copied == heard and type(copied) is Voiced
    assert copied.provider == "fixture" and copied.resolved_model == RESOLVED
    steps = Interpreted([{"op": "engrave", "amount": 1}], "fixture", RESOLVED)
    copied_steps = deepcopy(steps)
    assert copied_steps == [{"op": "engrave", "amount": 1}]
    assert type(copied_steps) is Interpreted
    assert copied_steps.provider == "fixture" and copied_steps.resolved_model == RESOLVED
