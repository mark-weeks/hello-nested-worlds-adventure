import sqlite3
import stat

import pytest

import persistence


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    """Redirect the database to a temporary file for every test."""
    db_path = tmp_path / "test_worlds.db"
    monkeypatch.setattr(persistence, "_DB_PATH", db_path)
    yield db_path


class TestInitDb:
    def test_creates_database_file(self, tmp_path):
        persistence.init_db()
        assert persistence._DB_PATH.exists()

    def test_creates_all_tables(self):
        persistence.init_db()
        import sqlite3
        conn = sqlite3.connect(persistence._DB_PATH)
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        conn.close()
        assert {"worlds", "agent_runs", "puzzle_results", "world_mutations",
                "agent_memory", "node_images"}.issubset(tables)

    def test_db_permissions_owner_only(self):
        persistence.init_db()
        mode = persistence._DB_PATH.stat().st_mode
        assert mode & stat.S_IRWXG == 0, "group bits should be unset"
        assert mode & stat.S_IRWXO == 0, "other bits should be unset"


class TestSaveAndListWorlds:
    def test_save_and_list_world(self):
        persistence.save_world(seed=1, node_count=10, max_depth=4, min_breadth=1, max_breadth=2)
        worlds = persistence.list_worlds()
        assert len(worlds) == 1
        assert worlds[0]["seed"] == 1
        assert worlds[0]["node_count"] == 10

    def test_replace_duplicate_seed(self):
        persistence.save_world(seed=42, node_count=5, max_depth=3, min_breadth=1, max_breadth=2)
        persistence.save_world(seed=42, node_count=99, max_depth=3, min_breadth=1, max_breadth=2)
        worlds = persistence.list_worlds()
        assert len(worlds) == 1
        assert worlds[0]["node_count"] == 99

    def test_list_worlds_empty(self):
        assert persistence.list_worlds() == []


class TestSaveAgentRun:
    def test_save_and_retrieve_run(self):
        persistence.save_world(seed=7, node_count=5, max_depth=3, min_breadth=1, max_breadth=2)
        events = [{"node": "A", "level": "Room", "state": "EXPLORE", "action": "explored"}]
        run_id = persistence.save_agent_run("Scout", 7, 3, events)
        assert isinstance(run_id, int)

        runs = persistence.get_agent_runs(7)
        assert len(runs) == 1
        assert runs[0]["agent_name"] == "Scout"
        assert runs[0]["nodes_visited"] == 3

    def test_multiple_runs_same_seed(self):
        persistence.save_world(seed=9, node_count=5, max_depth=3, min_breadth=1, max_breadth=2)
        persistence.save_agent_run("Alpha", 9, 2, [])
        persistence.save_agent_run("Beta", 9, 4, [])
        runs = persistence.get_agent_runs(9)
        assert len(runs) == 2

    def test_get_runs_unknown_seed(self):
        assert persistence.get_agent_runs(9999) == []


class TestWorldMutations:
    def test_record_and_get_mutation(self):
        persistence.record_mutation(7, "Aethon", "PUZZLE_SOLVED", "Alice", {"puzzle": "The Lock"})
        mutations = persistence.get_mutations(7)
        assert len(mutations) == 1
        m = mutations[0]
        assert m["node"]   == "Aethon"
        assert m["type"]   == "PUZZLE_SOLVED"
        assert m["player"] == "Alice"
        assert m["data"]   == {"puzzle": "The Lock"}

    def test_get_mutations_unknown_seed(self):
        assert persistence.get_mutations(9999) == []

    def test_get_mutations_limit(self):
        for i in range(10):
            persistence.record_mutation(5, f"Node{i}", "PUZZLE_SOLVED", None, {})
        assert len(persistence.get_mutations(5, limit=3)) == 3

    def test_record_mutation_null_player(self):
        persistence.record_mutation(3, "Vorrex", "PUZZLE_SOLVED", None, {"puzzle": "Riddle"})
        mutations = persistence.get_mutations(3)
        assert mutations[0]["player"] is None


class TestGetNodeHistory:
    def test_returns_events_for_node(self):
        persistence.record_mutation(42, "Vault-3", "PUZZLE_SOLVED", "Alice", {"puzzle": "The Lock"})
        persistence.record_mutation(42, "Vault-3", "AGENT_VISIT", None, {"agent": "Scout"})
        persistence.record_mutation(42, "OtherNode", "PUZZLE_SOLVED", "Bob", {})
        history = persistence.get_node_history(42, "Vault-3")
        assert len(history) == 2
        assert all(h["type"] in ("PUZZLE_SOLVED", "AGENT_VISIT") for h in history)

    def test_excludes_other_nodes(self):
        persistence.record_mutation(42, "Vault-3", "PUZZLE_SOLVED", "Alice", {})
        persistence.record_mutation(42, "OtherNode", "PUZZLE_SOLVED", "Bob", {})
        history = persistence.get_node_history(42, "OtherNode")
        assert len(history) == 1
        assert history[0]["type"] == "PUZZLE_SOLVED"

    def test_excludes_other_seeds(self):
        persistence.record_mutation(1, "Vault-3", "PUZZLE_SOLVED", "Alice", {})
        assert persistence.get_node_history(2, "Vault-3") == []

    def test_respects_limit(self):
        for i in range(10):
            persistence.record_mutation(5, "Node-X", "AGENT_VISIT", None, {"i": i})
        assert len(persistence.get_node_history(5, "Node-X", limit=4)) == 4

    def test_empty_when_no_history(self):
        assert persistence.get_node_history(99, "Ghost") == []

    def test_agent_in_data_field(self):
        persistence.record_mutation(7, "Nexus", "AGENT_VISIT", None, {"agent": "Wanderer"})
        h = persistence.get_node_history(7, "Nexus")
        assert h[0]["data"]["agent"] == "Wanderer"
        assert h[0]["player"] is None


class TestAgentMemoryPersistence:
    def test_save_and_load_memory(self):
        persistence.save_agent_memory("Scout", 42, ["id-1", "id-2"], [{"node": "A", "action": "explored"}])
        m = persistence.load_agent_memory("Scout", 42)
        assert m is not None
        assert m["visited_ids"] == ["id-1", "id-2"]
        assert m["log_entries"][0]["node"] == "A"

    def test_load_missing_returns_none(self):
        assert persistence.load_agent_memory("Ghost", 99) is None

    def test_save_overwrites_existing(self):
        persistence.save_agent_memory("Scout", 1, ["a"], [])
        persistence.save_agent_memory("Scout", 1, ["a", "b", "c"], [])
        m = persistence.load_agent_memory("Scout", 1)
        assert m["visited_ids"] == ["a", "b", "c"]

    def test_different_seeds_are_independent(self):
        persistence.save_agent_memory("Scout", 1, ["x"], [])
        persistence.save_agent_memory("Scout", 2, ["y", "z"], [])
        assert persistence.load_agent_memory("Scout", 1)["visited_ids"] == ["x"]
        assert persistence.load_agent_memory("Scout", 2)["visited_ids"] == ["y", "z"]

    def test_list_agent_memories(self):
        persistence.save_agent_memory("Alpha", 10, ["a", "b"], [])
        persistence.save_agent_memory("Beta",  20, ["c"], [])
        memories = persistence.list_agent_memories()
        names = {m["agent_name"] for m in memories}
        assert "Alpha" in names and "Beta" in names

    def test_list_agent_memories_node_count(self):
        persistence.save_agent_memory("Counter", 5, ["p", "q", "r", "s"], [])
        memories = persistence.list_agent_memories()
        entry = next(m for m in memories if m["agent_name"] == "Counter")
        assert entry["node_count"] == 4


class TestNodeRuntimeState:
    def test_unknown_node_returns_zero(self):
        assert persistence.get_ripple_score(42, "Ghost") == 0.0

    def test_upsert_then_get(self):
        persistence.upsert_ripple_score(42, "Vault-3", 0.37)
        assert persistence.get_ripple_score(42, "Vault-3") == pytest.approx(0.37)

    def test_upsert_overwrites(self):
        persistence.upsert_ripple_score(42, "Vault-3", 0.2)
        persistence.upsert_ripple_score(42, "Vault-3", 0.8)
        assert persistence.get_ripple_score(42, "Vault-3") == pytest.approx(0.8)

    def test_seeds_isolated(self):
        persistence.upsert_ripple_score(1, "Vault-3", 0.5)
        persistence.upsert_ripple_score(2, "Vault-3", 0.9)
        assert persistence.get_ripple_score(1, "Vault-3") == pytest.approx(0.5)
        assert persistence.get_ripple_score(2, "Vault-3") == pytest.approx(0.9)

    def test_load_ripple_scores_returns_dict(self):
        persistence.upsert_ripple_score(7, "Aethon-1", 0.4)
        persistence.upsert_ripple_score(7, "Vault-3",  0.7)
        scores = persistence.load_ripple_scores(7)
        assert scores == {"Aethon-1": pytest.approx(0.4),
                          "Vault-3":  pytest.approx(0.7)}

    def test_load_ripple_scores_unknown_seed_empty(self):
        assert persistence.load_ripple_scores(9999) == {}


class TestMigrations:
    def test_init_records_all_known_migrations(self):
        persistence.init_db()
        applied = persistence.schema_versions()
        # At minimum, 0001_initial and 0002_indexes both present after init.
        assert 1 in applied
        assert 2 in applied
        assert applied == sorted(applied)

    def test_schema_version_table_exists(self):
        persistence.init_db()
        conn = sqlite3.connect(persistence._DB_PATH)
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
        ).fetchall()
        conn.close()
        assert rows == [("schema_version",)]

    def test_indexes_present_after_init(self):
        persistence.init_db()
        conn = sqlite3.connect(persistence._DB_PATH)
        names = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        )}
        conn.close()
        # The three hot-path indexes from 0002_indexes.sql.
        assert "idx_world_mutations_seed_node" in names
        assert "idx_world_mutations_seed_time" in names
        assert "idx_agent_runs_seed"           in names

    def test_idempotent_on_existing_database(self):
        # Running init twice must not duplicate version rows or fail.
        persistence.init_db()
        first = persistence.schema_versions()
        persistence._initialized.discard(persistence._DB_PATH)
        persistence.init_db()
        second = persistence.schema_versions()
        assert first == second

    def test_runner_skips_unknown_filenames(self, tmp_path, monkeypatch):
        # A stray file that doesn't match the NNNN_name.sql pattern must be
        # ignored — otherwise the runner could try to executescript a README
        # or notes file dropped into the migrations directory.
        bogus_dir = tmp_path / "migrations"
        bogus_dir.mkdir()
        (bogus_dir / "README.md").write_text("# notes")
        (bogus_dir / "0001_real.sql").write_text(
            "CREATE TABLE IF NOT EXISTS m_test (id INTEGER PRIMARY KEY);"
        )
        monkeypatch.setattr(persistence, "_MIGRATIONS_DIR", bogus_dir)
        # Re-initialize so the new migrations dir is consulted.
        persistence._initialized.discard(persistence._DB_PATH)
        persistence.init_db()
        assert persistence.schema_versions() == [1]


class TestPruneMutations:
    def test_prune_zero_is_noop(self):
        persistence.record_mutation(1, "N", "AGENT_VISIT", None, {})
        assert persistence.prune_mutations(0) == 0
        assert len(persistence.get_mutations(1)) == 1

    def test_prune_negative_is_noop(self):
        persistence.record_mutation(1, "N", "AGENT_VISIT", None, {})
        assert persistence.prune_mutations(-5) == 0
        assert len(persistence.get_mutations(1)) == 1

    def test_prune_removes_old_rows_only(self):
        # Insert one fresh + one ancient row by manually backdating it.
        persistence.record_mutation(1, "Fresh", "AGENT_VISIT", None, {})
        persistence.record_mutation(1, "Stale", "AGENT_VISIT", None, {})
        conn = sqlite3.connect(persistence._DB_PATH)
        conn.execute(
            "UPDATE world_mutations SET recorded_at = datetime('now', '-90 days') "
            "WHERE node_name = 'Stale'"
        )
        conn.commit()
        conn.close()
        removed = persistence.prune_mutations(30)
        assert removed == 1
        nodes = {m["node"] for m in persistence.get_mutations(1)}
        assert nodes == {"Fresh"}

    def test_env_flag_triggers_prune_on_init(self, monkeypatch):
        # Seed an ancient mutation, then re-init with the TTL env var set.
        # The chronicle is continuity-protected, so the TTL only acts when
        # paired with the explicit override flag.
        persistence.record_mutation(1, "Stale", "AGENT_VISIT", None, {})
        conn = sqlite3.connect(persistence._DB_PATH)
        conn.execute(
            "UPDATE world_mutations SET recorded_at = datetime('now', '-90 days')"
        )
        conn.commit()
        conn.close()
        monkeypatch.setenv("NESTED_WORLDS_MUTATION_TTL_DAYS", "30")
        monkeypatch.setenv("NESTED_WORLDS_ALLOW_HISTORY_PRUNE", "1")
        persistence._initialized.discard(persistence._DB_PATH)
        persistence.init_db()
        assert persistence.get_mutations(1) == []

    def test_ttl_without_override_preserves_the_chronicle(self, monkeypatch, caplog):
        # Continuity policy: world_mutations is permanent. A bare TTL is
        # refused with a warning; only the explicit override prunes.
        persistence.record_mutation(1, "Stale", "AGENT_VISIT", None, {})
        conn = sqlite3.connect(persistence._DB_PATH)
        conn.execute(
            "UPDATE world_mutations SET recorded_at = datetime('now', '-90 days')"
        )
        conn.commit()
        conn.close()
        monkeypatch.setenv("NESTED_WORLDS_MUTATION_TTL_DAYS", "30")
        monkeypatch.delenv("NESTED_WORLDS_ALLOW_HISTORY_PRUNE", raising=False)
        persistence._initialized.discard(persistence._DB_PATH)
        import logging
        with caplog.at_level(logging.WARNING, logger="nested_worlds.persistence"):
            persistence.init_db()
        assert len(persistence.get_mutations(1)) == 1
        assert any("continuity" in r.message for r in caplog.records)

    def test_invalid_env_var_is_ignored(self, monkeypatch):
        persistence.record_mutation(1, "Fresh", "AGENT_VISIT", None, {})
        monkeypatch.setenv("NESTED_WORLDS_MUTATION_TTL_DAYS", "not-a-number")
        persistence._initialized.discard(persistence._DB_PATH)
        persistence.init_db()
        # No prune attempted, fresh row still present.
        assert len(persistence.get_mutations(1)) == 1


class TestSavePuzzleResult:
    def test_save_puzzle_result(self):
        persistence.save_puzzle_result(world_seed=5, puzzle_name="The Lock", result="SOLVED", attempts=2)
        # No exception means success; verify via direct query
        import sqlite3
        conn = sqlite3.connect(persistence._DB_PATH)
        rows = conn.execute("SELECT puzzle_name, result, attempts FROM puzzle_results").fetchall()
        conn.close()
        assert len(rows) == 1
        assert rows[0] == ("The Lock", "SOLVED", 2)


class TestInviteKeys:
    def test_mint_and_lookup(self):
        persistence.mint_invite_key("k_alice", "Alice", note="alpha cohort")
        row = persistence.lookup_invite_key("k_alice")
        assert row is not None
        assert row["name"] == "Alice"
        assert row["note"] == "alpha cohort"
        assert row["revoked_at"] is None
        assert row["last_used_at"] is None

    def test_lookup_unknown_returns_none(self):
        assert persistence.lookup_invite_key("does-not-exist") is None

    def test_touch_updates_last_used(self):
        persistence.mint_invite_key("k_bob", "Bob")
        persistence.touch_invite_key("k_bob")
        row = persistence.lookup_invite_key("k_bob")
        assert row is not None
        assert row["last_used_at"] is not None

    def test_touch_unknown_is_noop(self):
        # Should not raise — the UPDATE just matches zero rows.
        persistence.touch_invite_key("does-not-exist")

    def test_revoke_blocks_lookup(self):
        persistence.mint_invite_key("k_carol", "Carol")
        assert persistence.revoke_invite_key("k_carol") is True
        # Revoked keys read as None to keep the auth path simple.
        assert persistence.lookup_invite_key("k_carol") is None

    def test_revoke_idempotent(self):
        persistence.mint_invite_key("k_dave", "Dave")
        assert persistence.revoke_invite_key("k_dave") is True
        # Second revoke finds no active row and returns False so the CLI
        # can give an honest "no active key matched" message.
        assert persistence.revoke_invite_key("k_dave") is False

    def test_list_default_hides_revoked(self):
        persistence.mint_invite_key("k_active", "Active")
        persistence.mint_invite_key("k_dead", "Dead")
        persistence.revoke_invite_key("k_dead")
        names = {r["name"] for r in persistence.list_invite_keys()}
        assert names == {"Active"}

    def test_list_all_includes_revoked(self):
        persistence.mint_invite_key("k_active", "Active")
        persistence.mint_invite_key("k_dead", "Dead")
        persistence.revoke_invite_key("k_dead")
        names = {r["name"] for r in persistence.list_invite_keys(include_revoked=True)}
        assert names == {"Active", "Dead"}

    def test_duplicate_key_raises(self):
        persistence.mint_invite_key("k_dup", "First")
        with pytest.raises(sqlite3.IntegrityError):
            persistence.mint_invite_key("k_dup", "Second")

    def test_mint_rejects_duplicate_name(self):
        # ADR-004 §7: every player's name is unique (the registered name is
        # the player's authoritative display name at runtime).
        persistence.mint_invite_key("k_ada1", "Ada")
        with pytest.raises(persistence.NameUnavailable):
            persistence.mint_invite_key("k_ada2", "Ada")

    def test_mint_name_uniqueness_is_case_and_whitespace_insensitive(self):
        persistence.mint_invite_key("k_ada1", "Ada")
        for variant in ("ada", "  ADA  ", "aDa"):
            with pytest.raises(persistence.NameUnavailable):
                persistence.mint_invite_key("k_x", variant)

    def test_unique_name_index_backstops_the_app_check(self):
        # Even a direct insert that bypasses mint_invite_key's guard is
        # rejected by the DB UNIQUE index on lower(trim(name)) (migration 0011).
        persistence.mint_invite_key("k_ada1", "Ada")
        with pytest.raises(sqlite3.IntegrityError):
            with persistence._connect() as conn:
                conn.execute(
                    "INSERT INTO invite_keys (key, name) VALUES (?, ?)",
                    ("k_ada2", " ADA "))


class TestRegistrationTokens:
    """ADR-004 §7 self-service: a single-use registration token is redeemed
    by the PLAYER choosing their own name; redemption mints the per-user
    invite key and consumes the token in one transaction."""

    def test_create_and_lookup(self):
        persistence.create_registration_token("nwr_t1", note="for Priya")
        row = persistence.lookup_registration_token("nwr_t1")
        assert row is not None and row["note"] == "for Priya"
        assert row["redeemed_at"] is None and row["revoked_at"] is None

    def test_redeem_mints_the_key_and_spends_the_token(self):
        persistence.create_registration_token("nwr_t1")
        persistence.redeem_registration_token("nwr_t1", "k_priya", "Priya")
        # The play key exists under the chosen name…
        assert persistence.lookup_invite_key("k_priya")["name"] == "Priya"
        # …and the token is spent (single-use), with an audit trail. Tokens
        # are stored hashed at rest, so the audit row carries the digest, not
        # the plaintext link.
        assert persistence.lookup_registration_token("nwr_t1") is None
        digest = persistence._credential_digest("nwr_t1")
        spent = [r for r in persistence.list_registration_tokens(include_spent=True)
                 if r["token"] == digest][0]
        assert spent["redeemed_name"] == "Priya"
        assert spent["redeemed_at"] is not None

    def test_taken_name_rolls_back_and_leaves_token_redeemable(self):
        # The crux of the flow: NameUnavailable must NOT consume the token —
        # the whole redemption is one transaction, so the player retries with
        # another name on the same invite.
        persistence.mint_invite_key("k_ada", "Ada")
        persistence.create_registration_token("nwr_t1")
        with pytest.raises(persistence.NameUnavailable):
            persistence.redeem_registration_token("nwr_t1", "k_x", "  ADA ")
        assert persistence.lookup_registration_token("nwr_t1") is not None
        assert persistence.lookup_invite_key("k_x") is None
        # Same token, fresh name → succeeds.
        persistence.redeem_registration_token("nwr_t1", "k_x", "Adjacent")
        assert persistence.lookup_invite_key("k_x")["name"] == "Adjacent"

    def test_double_redeem_and_unknown_token_refused(self):
        persistence.create_registration_token("nwr_t1")
        persistence.redeem_registration_token("nwr_t1", "k_a", "Aster")
        with pytest.raises(persistence.TokenInvalid):
            persistence.redeem_registration_token("nwr_t1", "k_b", "Briar")
        with pytest.raises(persistence.TokenInvalid):
            persistence.redeem_registration_token("nwr_nope", "k_c", "Cove")
        # The failed redeems minted nothing.
        assert persistence.lookup_invite_key("k_b") is None
        assert persistence.lookup_invite_key("k_c") is None

    def test_cancel_is_single_shot_and_blocks_redemption(self):
        persistence.create_registration_token("nwr_t1")
        assert persistence.cancel_registration_token("nwr_t1") is True
        assert persistence.cancel_registration_token("nwr_t1") is False
        with pytest.raises(persistence.TokenInvalid):
            persistence.redeem_registration_token("nwr_t1", "k_x", "Xen")

    def test_redeemed_token_cannot_be_cancelled(self):
        # A redeemed token has already become an invite key; revoking THAT
        # account is revoke_invite_key, not cancel.
        persistence.create_registration_token("nwr_t1")
        persistence.redeem_registration_token("nwr_t1", "k_a", "Aster")
        assert persistence.cancel_registration_token("nwr_t1") is False
        assert persistence.lookup_invite_key("k_a") is not None


class TestPlayerPosition:
    """Cross-device resume: the last node is stored per invite key, so it
    follows the player across devices."""

    def test_save_then_get_round_trips(self):
        persistence.mint_invite_key("k_pos", "Pat")
        assert persistence.save_player_position(
            "k_pos", "Planet · Droven-13", 42, 6, 1, 3) is True
        pos = persistence.get_player_position("k_pos")
        assert pos == {
            "node": "Planet · Droven-13", "seed": 42,
            "depth": 6, "min_breadth": 1, "max_breadth": 3,
        }

    def test_save_overwrites_previous(self):
        persistence.mint_invite_key("k_move", "Mo")
        persistence.save_player_position("k_move", "Galaxy · Xel", 7, 5, 2, 4)
        persistence.save_player_position("k_move", "Atom · Fe-2", 9, 8, 1, 2)
        pos = persistence.get_player_position("k_move")
        assert pos["node"] == "Atom · Fe-2"
        assert pos["seed"] == 9

    def test_get_before_any_save_is_none(self):
        persistence.mint_invite_key("k_fresh", "Fran")
        assert persistence.get_player_position("k_fresh") is None

    def test_positions_are_independent_per_key(self):
        persistence.mint_invite_key("k_a", "A")
        persistence.mint_invite_key("k_b", "B")
        persistence.save_player_position("k_a", "Room · Attic", 1, 4, 1, 2)
        persistence.save_player_position("k_b", "Molecule · H2O", 2, 4, 1, 2)
        assert persistence.get_player_position("k_a")["node"] == "Room · Attic"
        assert persistence.get_player_position("k_b")["node"] == "Molecule · H2O"

    def test_unknown_key_save_noops_and_get_none(self):
        # No row to update — the write is a no-op (False) and there's nothing
        # to read back, so the client keeps its own localStorage cache.
        assert persistence.save_player_position("nope", "X", 1, 1, 1, 1) is False
        assert persistence.get_player_position("nope") is None

    def test_empty_key_is_noop(self):
        # The shared env key / no-key session supplies "" here.
        assert persistence.save_player_position("", "X", 1, 1, 1, 1) is False
        assert persistence.get_player_position("") is None

    def test_revoked_key_cannot_save_or_read(self):
        persistence.mint_invite_key("k_rev", "Rev")
        persistence.save_player_position("k_rev", "Universe · U-0", 3, 6, 1, 3)
        persistence.revoke_invite_key("k_rev")
        assert persistence.save_player_position("k_rev", "Y", 4, 6, 1, 3) is False
        assert persistence.get_player_position("k_rev") is None


class TestRestore:
    def test_restore_rolls_the_world_back_to_the_backup(self, tmp_path):
        # Chronicle 2 events, snapshot, add 2 more, restore → back to 2.
        persistence.record_mutation(881, "A-1", "AGENT_VISIT", None, {})
        persistence.record_mutation(881, "B-1", "AGENT_VISIT", None, {})
        snap = tmp_path / "snap.db"
        persistence.backup_to(snap)
        persistence.record_mutation(881, "C-1", "AGENT_VISIT", None, {})
        persistence.record_mutation(881, "D-1", "AGENT_VISIT", None, {})
        assert len(persistence.get_mutations(881, limit=10)) == 4

        counts = persistence.restore_from(snap)
        assert counts["events_before"] >= counts["events_after"]
        nodes = {m["node"] for m in persistence.get_mutations(881, limit=10)}
        assert nodes == {"A-1", "B-1"}

    def test_restore_refuses_a_missing_file(self, tmp_path):
        import pytest as _pytest
        with _pytest.raises(FileNotFoundError):
            persistence.restore_from(tmp_path / "nope.db")

    def test_restore_refuses_a_non_database_file(self, tmp_path):
        import pytest as _pytest
        junk = tmp_path / "junk.db"
        junk.write_text("this is not sqlite")
        with _pytest.raises(ValueError, match="not a SQLite database"):
            persistence.restore_from(junk)

    def test_restore_refuses_a_foreign_database(self, tmp_path):
        # A valid sqlite file that is NOT a worlds backup must be refused —
        # a typo'd path can't be allowed to blank the chronicle.
        import pytest as _pytest
        other = tmp_path / "other.db"
        conn = sqlite3.connect(other)
        conn.execute("CREATE TABLE cats (name TEXT)")
        conn.commit()
        conn.close()
        with _pytest.raises(ValueError, match="not a worlds backup"):
            persistence.restore_from(other)


class TestConcurrentFirstTouch:
    def test_joining_rush_does_not_race_the_migrations(self, tmp_path, monkeypatch):
        # Regression for the WS-soak finding: N request threads hitting a
        # fresh database simultaneously must not race _run_migrations
        # ("duplicate column name" from a re-applied ALTER).
        import threading as _threading
        fresh = tmp_path / "fresh" / "worlds.db"
        monkeypatch.setattr(persistence, "_DB_PATH", fresh)
        persistence._initialized.discard(fresh)
        errors = []

        def touch(i):
            try:
                persistence.record_mutation(1, f"Rush-{i}", "AGENT_VISIT", None, {})
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [_threading.Thread(target=touch, args=(i,)) for i in range(12)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
        # Every migration applied exactly once.
        conn = sqlite3.connect(fresh)
        versions = [r[0] for r in conn.execute(
            "SELECT version FROM schema_version ORDER BY version")]
        conn.close()
        assert versions == sorted(set(versions))
        assert len(persistence.get_mutations(1, limit=20)) == 12


# ── Credentials hashed at rest (2026-07-18 evaluation rec 5) ────────────────

class TestCredentialsAtRest:
    """Invite keys and registration tokens are stored as sha256 digests.

    Everything *derived* from a credential (actor_identity, cost-ledger
    buckets) was already hashed; the credential row itself was the one
    plaintext copy, handed over by every DB backup. These tests pin the
    at-rest form, the plaintext-in/digest-stored round trip, the one-time
    legacy backfill, and the operator's revoke-by-digest-prefix path (the
    plaintext is unrecoverable after mint, so revocation must not need it).
    """

    def test_plaintext_key_is_never_stored(self):
        persistence.mint_invite_key("nw_secret1", "Resa")
        conn = sqlite3.connect(persistence._DB_PATH)
        stored = [r[0] for r in conn.execute("SELECT key FROM invite_keys")]
        conn.close()
        assert stored == [persistence._credential_digest("nw_secret1")]
        # …and the plaintext the player holds still authorizes.
        assert persistence.lookup_invite_key("nw_secret1")["name"] == "Resa"

    def test_plaintext_token_is_never_stored(self):
        persistence.create_registration_token("nwr_leaky")
        conn = sqlite3.connect(persistence._DB_PATH)
        stored = [r[0] for r in
                  conn.execute("SELECT token FROM registration_tokens")]
        conn.close()
        assert stored == [persistence._credential_digest("nwr_leaky")]
        assert persistence.lookup_registration_token("nwr_leaky") is not None

    def test_legacy_plaintext_rows_hash_on_init_and_still_authorize(self):
        # A pre-hashing DB carries plaintext `nw_…` rows. The next init must
        # convert them in place — and the holder's key must keep working.
        persistence.init_db()
        conn = sqlite3.connect(persistence._DB_PATH)
        conn.execute("INSERT INTO invite_keys (key, name) VALUES (?, ?)",
                     ("nw_legacy", "Olde"))
        conn.commit()
        conn.close()
        persistence._initialized.discard(persistence._DB_PATH)
        row = persistence.lookup_invite_key("nw_legacy")  # re-inits, backfills
        assert row is not None and row["name"] == "Olde"
        conn = sqlite3.connect(persistence._DB_PATH)
        stored = [r[0] for r in conn.execute("SELECT key FROM invite_keys")]
        conn.close()
        assert "nw_legacy" not in stored
        assert persistence._credential_digest("nw_legacy") in stored

    def test_revoke_accepts_a_unique_digest_prefix(self):
        persistence.mint_invite_key("nw_gone", "Gone")
        digest = persistence._credential_digest("nw_gone")
        assert persistence.revoke_invite_key(digest[:12]) is True
        assert persistence.lookup_invite_key("nw_gone") is None

    def test_short_prefix_revokes_nothing(self):
        # <12 chars is refused outright — a fat-fingered fragment must never
        # revoke a key by accident.
        persistence.mint_invite_key("nw_short", "Short")
        digest = persistence._credential_digest("nw_short")
        assert persistence.revoke_invite_key(digest[:8]) is False
        assert persistence.lookup_invite_key("nw_short") is not None

    def test_digest_is_not_a_credential(self):
        # Knowing the stored digest must revoke, never authorize: the auth
        # path hashes its input, so presenting the digest looks up
        # sha256(digest) — a different row that doesn't exist.
        persistence.mint_invite_key("nw_authz", "Authz")
        digest = persistence._credential_digest("nw_authz")
        assert persistence.lookup_invite_key(digest) is None

    def test_cancel_token_by_digest_prefix(self):
        persistence.create_registration_token("nwr_oops")
        digest = persistence._credential_digest("nwr_oops")
        assert persistence.cancel_registration_token(digest[:12]) is True
        assert persistence.lookup_registration_token("nwr_oops") is None


class TestConnectionConfig:
    def test_busy_timeout_is_set(self):
        # WAL allows one writer at a time and this process always has
        # several (request threads, heartbeat, causal pump); busy_timeout=0
        # turns momentary contention into instant "database is locked"
        # errors that tear down WS sessions. _connect must configure a wait.
        persistence.init_db()
        conn = persistence._connect()
        (ms,) = conn.execute("PRAGMA busy_timeout").fetchone()
        conn.close()
        assert ms == 5000
