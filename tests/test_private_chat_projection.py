"""Private chat stays out of shared history without rewriting legacy rows."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

import consciousness
import persistence
from persistence import community, history
from scripts import beta_metrics
from server import heartbeat, imageprompt


_SEED = 382
_NODE = "Vault-11"
_SECRET = "private legacy chat words"


def _event(kind, data=None, *, player="Ada", at=None, node=_NODE):
    persistence.record_mutation(_SEED, node, kind, player, data or {}, actor_identity="legacy-actor")
    with persistence._connection() as conn:
        event_id = conn.execute("SELECT MAX(id) FROM world_mutations").fetchone()[0]
        if at is not None:
            conn.execute("UPDATE world_mutations SET recorded_at=? WHERE id=?", (at, event_id))
    return event_id


def _raw_rows():
    with persistence._connection() as conn:
        return conn.execute("SELECT * FROM world_mutations ORDER BY id").fetchall()


def test_legacy_chat_is_hidden_before_public_history_limits_and_preserved_exactly():
    first = _event("PLAYER_SPEAK", {"message": "A public question.", "reply": "A public answer."})
    second = _event("AGENT_TALK", {"a": "Tessera", "b": "Karst", "lines": []})
    hidden = [_event("PLAYER_CHAT", {"text": _SECRET, "index": i}) for i in range(30)]
    before = _raw_rows()
    assert [row["id"] for row in persistence.get_node_history(_SEED, _NODE, 2)] == [second, first]
    assert [row["id"] for row in persistence.get_node_history(_SEED, _NODE, 2, include_narration=False)] == [second, first]
    assert [row["id"] for row in persistence.get_mutations(_SEED, 2)] == [second, first]
    assert persistence.presented_mutations(_SEED, hidden) == []
    assert [row["id"] for row in persistence.presented_mutations(_SEED, [*hidden, second, first])] == [first, second]
    assert _raw_rows() == before
    assert _SECRET not in json.dumps(persistence.get_chronicle(_SEED))


def test_selected_notification_limit_is_applied_to_visible_events():
    hidden = [_event("PLAYER_CHAT", {"text": _SECRET}) for _ in range(205)]
    public = _event("AGENT_VISIT")
    assert [row["id"] for row in persistence.presented_mutations(_SEED, [*hidden, public])] == [public]


def test_public_chronicle_counts_birth_and_cursors_ignore_legacy_chat():
    _event("PLAYER_CHAT", {"text": _SECRET}, at="2026-01-01 00:00:00")
    oldest = _event("AGENT_VISIT", at="2026-02-01 00:00:00")
    _event("PLAYER_CHAT", {"text": _SECRET}, at="2026-02-02 00:00:00")
    newest = _event("PLAYER_SPEAK", {"message": "public"}, at="2026-02-03 00:00:00")
    _event("PLAYER_CHAT", {"text": _SECRET}, at="2026-02-04 00:00:00")
    first = persistence.get_chronicle(_SEED, limit=1)
    assert first["total"] == 2 and first["began"] == "2026-02-01 00:00:00"
    assert [row["id"] for row in first["entries"]] == [newest]
    assert first["next_before"] == newest
    second = persistence.get_chronicle(_SEED, limit=1, before_id=first["next_before"])
    assert [row["id"] for row in second["entries"]] == [oldest]
    assert second["next_before"] is None and second["total"] == 2


def test_world_with_only_legacy_chat_has_no_public_history():
    _event("PLAYER_CHAT", {"text": _SECRET})
    assert persistence.get_chronicle(_SEED) == {"entries": [], "next_before": None, "total": 0, "began": None}


def test_linked_source_projection_never_loads_a_legacy_chat(monkeypatch):
    hidden = _event("PLAYER_CHAT", {"text": _SECRET})
    public = _event("SCALE_ACT", {"verb": "ward", "source_event_id": hidden, "_origin": _NODE})
    original_decode = history.decode

    def visible_only(row):
        assert row[2] != "PLAYER_CHAT", "linked source loaded hidden chat content"
        return original_decode(row)

    monkeypatch.setattr(history, "decode", visible_only)
    row, = persistence.presented_mutations(_SEED, [public])
    assert row["narration"]["source_event_id"] is None
    assert _SECRET not in json.dumps(row)
    with persistence._connection() as conn:
        assert history.project(conn, _SEED, [{"id": hidden, "type": "PLAYER_CHAT", "data": {"text": _SECRET}}]) == []


def test_model_history_defensively_omits_raw_chat_before_narration():
    raw = [
        {"type": "PLAYER_CHAT", "player": "Ada", "data": {"text": _SECRET},
         "narration": {"text": _SECRET}},
        {"type": "PLAYER_SPEAK", "player": "Ada", "data": {"message": "A public question.", "reply": "A public answer."}},
        {"type": "AGENT_TALK", "data": {"a": "Tessera", "b": "Karst", "lines": [{"speaker": "Tessera", "line": "An authored conversation."}]}},
    ]
    rendered = consciousness._history_block(raw)
    assert _SECRET not in rendered
    assert "A public question." in rendered and "A public answer." in rendered
    assert "An authored conversation." in rendered
    assert consciousness._history_block(raw[:1]) == ""


def test_chat_flood_does_not_displace_model_history():
    public = _event("PLAYER_SPEAK", {"message": "Remember this public exchange."})
    with persistence.transaction():
        for _ in range(1001):
            persistence.record_mutation(_SEED, _NODE, "PLAYER_CHAT", "Ada", {"text": _SECRET})
    assert [row["id"] for row in consciousness.history_for_voice(_SEED, _NODE, limit=1)] == [public]


def test_metadata_activity_window_preserves_old_art_without_loading_words():
    with persistence.transaction():
        for _ in range(5):
            persistence.record_mutation(_SEED, _NODE, "AGENT_VISIT", None, {})
        for i in range(1000):
            persistence.record_mutation(_SEED, _NODE, "PLAYER_CHAT", "Ada" if i % 2 else "Bea", {"text": _SECRET})
    before = _raw_rows()
    with persistence._connection() as conn:
        legacy = [history.decode(row) for row in conn.execute(
            f"SELECT {history.FIELDS} FROM world_mutations WHERE world_seed=? AND node_name=? ORDER BY recorded_at DESC,id DESC LIMIT 1000",
            (_SEED, _NODE)).fetchall()]
    activity = persistence.get_node_activity_history(_SEED, _NODE)
    assert len(activity) == 1000 and all(set(row) == {"id", "type", "player", "at"} for row in activity)
    assert imageprompt.derive_modifiers({}, activity) == imageprompt.derive_modifiers({}, legacy) == ["warm, impressionist, layered"]
    assert imageprompt.style_signature("Room", {}, activity) == imageprompt.style_signature("Room", {}, legacy)
    assert _SECRET not in imageprompt.assemble_prompt("Room", _NODE, {}, activity)
    assert _SECRET not in imageprompt.assemble_prompt("Room", _NODE, {}, legacy)
    assert persistence.count_mutations_by_node(_SEED) == {_NODE: 1005}
    assert _raw_rows() == before


def test_authored_banter_keeps_the_old_mixed_activity_window(monkeypatch):
    for i in range(55):
        _event("AGENT_TALK" if i % 10 == 0 else "PLAYER_CHAT", {"text": _SECRET})
    ordinals = []

    def compose(*args, ordinal):
        ordinals.append(ordinal)
        return [{"speaker": "Tessera", "line": "An authored line."}]

    monkeypatch.setattr("agents.banter.compose_exchange", compose)
    monkeypatch.setattr(heartbeat, "broadcast", lambda *args: None)
    heartbeat._hold_conversation(_SEED, object(), SimpleNamespace(name=_NODE, level="Room"),
                                 "Tessera", "scholar", "Karst", "tender")
    assert ordinals == [5]


@pytest.fixture
def retained_chat_archive(tmp_path):
    """Metadata contract on an archive; no application migration is needed."""
    path = tmp_path / "chat-archive.db"
    now = datetime.now(timezone.utc)
    def stamp(value):
        return value.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    with sqlite3.connect(path) as conn:
        conn.execute("""CREATE TABLE private_chat_messages (
            world_seed INTEGER, participant_id TEXT, created_at TEXT,
            expires_at TEXT, text TEXT)""")
        conn.executemany("INSERT INTO private_chat_messages VALUES (?,?,?,?,?)", [
            (_SEED, "Ada", stamp(now), stamp(now + timedelta(days=1)), _SECRET),
            (_SEED, "Ada", stamp(now - timedelta(days=2)), stamp(now - timedelta(days=1)), _SECRET),
            (99, "Ada", stamp(now), stamp(now + timedelta(days=1)), _SECRET),
            (_SEED, "Bea", stamp(now), stamp(now + timedelta(days=1)), _SECRET),
            (_SEED, "Ada", stamp(now - timedelta(days=10)), stamp(now + timedelta(days=1)), _SECRET),
        ])
    return path


def test_metrics_count_retained_rows_on_read_only_archive_without_loading_text(retained_chat_archive):
    before = retained_chat_archive.read_bytes()
    with sqlite3.connect(f"file:{retained_chat_archive}?mode=ro", uri=True) as conn:
        def metadata_only(action, table, column, database, trigger):
            if action == sqlite3.SQLITE_READ and table == "private_chat_messages" and column == "text":
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        conn.set_authorizer(metadata_only)
        result = beta_metrics._retained_chat_counts(
            conn, beta_metrics._window(7, None, None), seed=_SEED,
            excluded_participants=("Bea",),
        )
    assert result == {"available": True, "scope": "retained_only", "retained_lines": 1,
                      "expired_or_uncollected": "unavailable"}
    assert retained_chat_archive.read_bytes() == before


def test_metrics_do_not_recover_expired_chat_for_an_absolute_archive_window(retained_chat_archive):
    yesterday = datetime.now(timezone.utc) - timedelta(days=2)
    with sqlite3.connect(f"file:{retained_chat_archive}?mode=ro", uri=True) as conn:
        result = beta_metrics._retained_chat_counts(
            conn, beta_metrics._window(None, yesterday - timedelta(hours=1), yesterday + timedelta(hours=1)),
            seed=_SEED, excluded_participants=(),
        )
    assert result["retained_lines"] == 0
    assert result["expired_or_uncollected"] == "unavailable"


def test_metrics_missing_private_schema_is_unavailable_not_zero():
    with sqlite3.connect(":memory:") as conn:
        result = beta_metrics._retained_chat_counts(
            conn, beta_metrics._window(7, None, None), seed=None, excluded_participants=(),
        )
    assert result["available"] is False and result["retained_lines"] is None


def test_legacy_chat_no_longer_creates_per_person_action_metrics():
    _event("PLAYER_CHAT", {"text": _SECRET})
    before = _raw_rows()
    result = beta_metrics.compute_metrics(persistence._DB_PATH, days=7)
    assert result["visitors"] == result["acting_visitors"] == result["returning_visitors"] == 0
    assert "PLAYER_CHAT" not in result["events_by_type"]
    assert result["top_nodes"] == []
    assert result["chat_lines"] == result["chat_log"]["retained_lines"]
    assert result["chat_log"]["scope"] == "retained_only"
    assert "unavailable" in beta_metrics.render(result)
    assert _SECRET not in json.dumps(result) and _raw_rows() == before


def test_private_chat_and_its_expiry_never_change_art_or_model_history():
    _event("PLAYER_SPEAK", {"message": "A public place exchange."})
    activity = persistence.get_node_activity_history(_SEED, _NODE)
    signature = imageprompt.style_signature("Room", {}, activity)
    before = _raw_rows()
    private = community.append_chat(
        user_key=None, session_id=str(uuid.uuid4()), world_seed=_SEED, node_name=_NODE,
        text=_SECRET, display_name="Bea", retention_days=2,
        policy_snapshot='{"fixture":"synthetic private projection"}',
    )
    assert beta_metrics.compute_metrics(persistence._DB_PATH, days=7)["chat_lines"] == 1
    assert persistence.get_node_activity_history(_SEED, _NODE) == activity
    assert _SECRET not in consciousness._history_block(consciousness.history_for_voice(_SEED, _NODE))
    assert _SECRET not in imageprompt.assemble_prompt("Room", _NODE, {}, activity)
    now = datetime.now(timezone.utc)
    with persistence._connection() as conn:
        conn.execute("UPDATE private_chat_messages SET created_at=?,expires_at=? WHERE evidence_ref=?",
                     ((now - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                      (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S.%fZ"), private["evidence_ref"]))
    assert beta_metrics.compute_metrics(persistence._DB_PATH, days=7)["chat_lines"] == 0
    assert imageprompt.style_signature("Room", {}, persistence.get_node_activity_history(_SEED, _NODE)) == signature
    assert persistence.count_mutations_by_node(_SEED) == {_NODE: 1}
    assert _raw_rows() == before
