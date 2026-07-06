"""Pre-mortem hardening: the redaction path and the beta metrics.

Redaction is the sanctioned exception to the append-only chronicle:
content-level, never row-level. These tests pin the contract — the words
go, everything load-bearing stays.
"""
from __future__ import annotations

import sys
from pathlib import Path

import persistence

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import beta_metrics  # noqa: E402


def _chat(seed, node, player, text, identity):
    persistence.record_mutation(seed, node, "PLAYER_CHAT", player,
                                {"text": text}, actor_identity=identity)


class TestRedaction:
    def test_find_then_redact_tombstones_content_only(self):
        _chat(42, "Vault-11", "Mallory", "something awful here", "aaaa1111")
        _chat(42, "Vault-11", "Ada", "lovely weather", "bbbb2222")

        found = persistence.find_mutations_by_text("awful", world_seed=42)
        assert len(found) == 1 and found[0]["player"] == "Mallory"

        summary = persistence.redact_mutation(found[0]["id"],
                                              reason="test cleanup")
        assert summary["fields"] == ["text"]
        assert summary["name_scrubbed"] is False

        rows = persistence.get_mutations(42, limit=10)
        bad = [r for r in rows if r["player"] == "Mallory"][0]
        # The words are gone; the event survives with full shape.
        assert bad["data"]["text"] == "[redacted]"
        assert bad["data"]["redacted"] is True
        assert bad["data"]["redacted_reason"] == "test cleanup"
        assert bad["type"] == "PLAYER_CHAT" and bad["node"] == "Vault-11"
        assert bad["at"]
        # The innocent row is untouched.
        ok = [r for r in rows if r["player"] == "Ada"][0]
        assert ok["data"]["text"] == "lovely weather"

    def test_mechanical_fields_survive_redaction(self):
        # A slur in a puzzle guess: the guess goes, but the fields the co-op
        # counter rehydration reads (puzzle, correct) must survive.
        persistence.record_mutation(
            42, "Cell-111", "PUZZLE_ATTEMPT", "Mallory",
            {"puzzle": "The Sealed Room", "correct": False, "guess": "slur"},
            actor_identity="aaaa1111")
        before = persistence.get_puzzle_attempt_state(
            42, "Cell-111", "The Sealed Room")

        row_id = persistence.find_mutations_by_text("slur")[0]["id"]
        summary = persistence.redact_mutation(row_id)
        assert summary["fields"] == ["guess"]

        after = persistence.get_puzzle_attempt_state(
            42, "Cell-111", "The Sealed Room")
        assert after == before
        data = persistence.get_mutations(42, limit=5)[0]["data"]
        assert data["puzzle"] == "The Sealed Room"
        assert data["correct"] is False
        assert data["guess"] == "[redacted]"

    def test_scrub_name_keeps_actor_identity(self):
        _chat(42, "Vault-11", "OffensiveName", "hi", "cccc3333")
        row_id = persistence.find_mutations_by_text("OffensiveName")[0]["id"]

        summary = persistence.redact_mutation(row_id, scrub_name=True)
        assert summary["name_scrubbed"] is True

        with persistence._connect() as conn:
            player, identity = conn.execute(
                """SELECT player_name, actor_identity FROM world_mutations
                   WHERE id = ?""", (row_id,)).fetchone()
        assert player is None
        assert identity == "cccc3333"  # accountability survives the cleanup

    def test_idempotent_and_missing_id(self):
        _chat(42, "Vault-11", "Ada", "twice", "bbbb2222")
        row_id = persistence.find_mutations_by_text("twice")[0]["id"]
        first = persistence.redact_mutation(row_id)
        second = persistence.redact_mutation(row_id)
        assert first["fields"] == ["text"]
        assert second["fields"] == []  # nothing left to tombstone
        assert persistence.redact_mutation(999_999) is None


class TestBetaMetrics:
    def test_counts_humans_and_excludes_the_cast(self):
        _chat(42, "Vault-11", "Ada", "hello", "bbbb2222")
        persistence.record_mutation(
            42, "Vault-11", "PLAYER_SPEAK", "Ada",
            {"message": "who are you", "reply": "a room"},
            actor_identity="bbbb2222")
        persistence.record_mutation(
            42, "Wilds-12", "SCALE_ACT", None,
            {"verb": "ward", "agent": "Tessera"},
            actor_identity="Tessera")          # ambient cast, not a human
        persistence.record_mutation(
            42, "Wilds-12", "DANGER_ALERT", None, {})  # anonymous rail event

        m = beta_metrics.compute_metrics(persistence._DB_PATH, days=7)
        assert m["visitors"] == 1
        assert m["conversations"] == 1
        assert m["chat_lines"] == 1
        assert m["scale_acts"] == 0            # Tessera's act is not human
        assert m["chronicle_total_rows"] == 4  # ...but the chronicle has it

    def test_returning_visitor_needs_two_distinct_days(self):
        _chat(42, "Vault-11", "Ada", "day two", "bbbb2222")
        m = beta_metrics.compute_metrics(persistence._DB_PATH, days=7)
        assert m["returning_visitors"] == 0

        # Backdate a second visit to yesterday.
        with persistence._connect() as conn:
            conn.execute(
                """INSERT INTO world_mutations
                   (world_seed, node_name, mutation_type, player_name, data,
                    actor_identity, recorded_at)
                   VALUES (42, 'Vault-11', 'PLAYER_MOVE', 'Ada', '{}',
                           'bbbb2222', datetime('now', '-1 day'))""")
        m = beta_metrics.compute_metrics(persistence._DB_PATH, days=7)
        assert m["visitors"] == 1
        assert m["returning_visitors"] == 1
        assert m["return_rate"] == 1.0

    def test_seed_scoping_and_render(self):
        _chat(42, "Vault-11", "Ada", "here", "bbbb2222")
        _chat(7, "Elsewhere-1", "Ben", "there", "dddd4444")
        m42 = beta_metrics.compute_metrics(persistence._DB_PATH, days=7,
                                           seed=42)
        assert m42["visitors"] == 1
        report = beta_metrics.render(m42)
        assert "world 42" in report and "visitors:            1" in report
