"""Accepted work survives interrupted delivery; all databases are disposable."""
from unittest.mock import patch
import contextlib
import multiprocessing
import os
from pathlib import Path
import signal
import sqlite3

from causality.laws import law_for
from puzzles.engine import build_puzzle

import pytest

import persistence
from causality.staging import drain_due_hops
from multiverse import store
from server import heartbeat
from server import _Handler


def act(node, seed=382):
    handler = object.__new__(_Handler)
    responses = []
    handler._send_json = responses.append
    handler._do_act({"seed": seed, "node_name": node.name,
                     "player_name": "RecoveryVisitor"})
    return responses[0]


def attempt(call):
    try:
        call()
    except RuntimeError:
        pass


@pytest.mark.parametrize("queue", ["causal", "maturation"])
def test_application_exception_does_not_lose_work(queue):
    root = store.world_tree(seed=382)
    if queue == "causal":
        persistence.enqueue_causal_hop(382, root.name, "DANGER_ALERT", 1,
                                       "up", {}, 0)
        drain = drain_due_hops
        pending = persistence.pending_causal_hops
        seam = "causality.staging.store.world_tree"
    else:
        persistence.enqueue_verb_maturation(382, root.name, "attune",
                                             {"attuned": True}, "Ada", 0)
        drain = heartbeat.drain_matured_verbs
        pending = persistence.pending_verb_maturations
        seam = "server.heartbeat.persistence.record_substance_change"
    with patch(seam, side_effect=RuntimeError("injected application failure")):
        attempt(drain)
    assert pending(382) == 1
    assert persistence.get_node_history(382, root.name) == []


@pytest.mark.parametrize("seam", ["enqueue_verb_maturation", "enqueue_causal_hop"])
def test_initial_scheduling_failure_does_not_partially_accept_act(seam):
    root = store.world_tree(seed=382)
    galaxy = root.children[0].children[0]
    original = getattr(persistence, seam)

    def write_then_fail(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("injected initial scheduling failure")

    with patch.object(persistence, seam, write_then_fail):
        attempt(lambda: act(galaxy))
    assert persistence.pending_verb_maturations(382) == 0
    assert persistence.pending_causal_hops(382) == 0
    assert persistence.get_node_history(382, galaxy.name) == []
    assert galaxy.name not in persistence.load_node_property_overrides(382)

# Spawned workers use only the explicit test path. No inherited live DB or
# interpreter globals; SIGKILL really terminates SQLite with an open transaction.

QUEUES = ("causal_queue", "verb_maturation")


def solve(node, seed=382):
    handler = object.__new__(_Handler)
    responses = []
    handler._send_json = responses.append
    handler._do_puzzle_attempt({
        "seed": seed, "depth": 11, "node_name": node.name, "player_name": "RecoverySolver",
        "answer": build_puzzle(node).answer})
    return responses[0]


def walk(root):
    yield root
    for child in root.children:
        yield from walk(child)


def accept_work(queue):
    root = store.world_tree(seed=382)
    if queue == "causal_queue":
        node = next(n for n in walk(root) if n.level == "Room"
                    and law_for(n).name == "Fractal")
        assert solve(node)["correct"]
    else:
        node = root.children[0].children[0]
        assert act(node)["matures_in"] > 0
    # Acceptance links every initial work item to the committed origin.
    # Advance only disposable queue clocks, keeping production timing unchanged.
    with persistence._connect() as conn:
        sources = conn.execute(
            f"SELECT source_event_id FROM {queue}").fetchall()
        origin = conn.execute(
            "SELECT id FROM world_mutations WHERE node_name = ? AND mutation_type = ?",
            (node.name, "PUZZLE_SOLVED" if queue == "causal_queue" else "SCALE_ACT")).fetchone()[0]
        assert sources and all(source == (origin,) for source in sources)
        conn.execute(f"UPDATE {queue} SET due_at = datetime('now', '-1 second')")
    return persistence.due_work(queue, 100)[0]


def drain(queue, **kwargs):
    if queue == "causal_queue":
        return drain_due_hops(**kwargs)
    return heartbeat.drain_matured_verbs(**kwargs)


def snapshot():
    """Compare canonical effects, historical deltas and pressure, not clocks."""
    with persistence._connect() as conn:
        history = conn.execute(
            """SELECT node_name, mutation_type, player_name, data, strength,
                      delta, node_version FROM world_mutations ORDER BY id""").fetchall()
    return history, persistence.load_node_property_overrides(382), persistence.load_ripple_scores(382)


def fault_worker(db, queue, phase, ready=None, go=None, work_id=None):
    persistence._DB_PATH = Path(db)
    persistence._initialized.clear()
    os.environ["NESTED_WORLDS_CANONICAL_SEED"] = ""
    os.environ["NESTED_WORLDS_HOP_DELAY"] = "0"
    persistence.init_db()

    def die(*args, **kwargs):
        os.kill(os.getpid(), signal.SIGKILL)

    with contextlib.ExitStack() as patches:
        if work_id is not None:
            patches.enter_context(patch.object(persistence, "due_work", return_value=[work_id]))
        if phase == "before_apply":
            seam = ("causality.staging.store.world_tree" if queue == "causal_queue"
                    else "server.heartbeat.persistence.record_substance_change")
            patches.enter_context(patch(seam, side_effect=die))
        elif phase in ("after_effect", "after_continuation", "initial_maturation", "initial_hop"):
            name = {"after_effect": "record_substance_transition" if queue == "causal_queue"
                    else "record_substance_change", "after_continuation": "enqueue_causal_hop",
                    "initial_maturation": "enqueue_verb_maturation", "initial_hop": "enqueue_causal_hop"}[phase]
            original = getattr(persistence, name)

            def write_then_die(*args, **kwargs):
                original(*args, **kwargs)
                die()

            patches.enter_context(patch.object(persistence, name, write_then_die))
        elif phase == "before_commit":
            class InterruptedConnection(sqlite3.Connection):
                def execute(self, sql, parameters=()):
                    result = super().execute(sql, parameters)
                    if "completed_at = datetime" in sql:
                        die()
                    return result

            def connect():
                conn = sqlite3.connect(db, factory=InterruptedConnection)
                conn.execute("PRAGMA busy_timeout=5000")
                return conn

            patches.enter_context(patch.object(persistence, "_connect", connect))
        if ready is not None:
            ready.set()
            assert go.wait(15)
        if phase.startswith("initial_"):
            act(store.world_tree(seed=382).children[0].children[0])
        elif queue == "causal_queue":
            drain_due_hops(limit=1, broadcaster=die if phase == "after_commit" else None)
        elif phase == "after_commit":
            with patch.object(heartbeat, "broadcast", die):
                heartbeat.drain_matured_verbs(limit=1)
        else:
            heartbeat.drain_matured_verbs(limit=1)


def start_worker(queue, phase, **kwargs):
    worker = multiprocessing.get_context("spawn").Process(
        target=fault_worker,
        args=(str(persistence._DB_PATH), queue, phase), kwargs=kwargs)
    worker.start()
    return worker


def join(worker, expected=0):
    worker.join(20)
    if worker.is_alive():
        worker.kill()
        worker.join(5)
        pytest.fail("worker did not finish within 20 seconds")
    assert worker.exitcode == expected


@pytest.mark.parametrize("queue", QUEUES)
@pytest.mark.parametrize("phase", ["before_apply", "after_effect", "before_commit", "after_commit"])
def test_sigkill_and_restart_recover_exactly_one_effect(queue, phase, tmp_path, monkeypatch):
    monkeypatch.setenv("NESTED_WORLDS_HOP_DELAY", "0")
    work_id = accept_work(queue)
    backup = tmp_path / "accepted.db"
    persistence.backup_to(backup)
    assert drain(queue, limit=1) == 1
    expected = snapshot()
    persistence.restore_from(backup)
    join(start_worker(queue, phase), -signal.SIGKILL)
    row = persistence.inspect_work(queue, work_id)
    assert row["status"] == ("completed" if phase == "after_commit" else "pending")
    # A second new interpreter, not a reused in-process snapshot, recovers.
    join(start_worker(queue, "recover", work_id=work_id))
    assert snapshot() == expected
    # Delivery of the same durable ID never invokes application again.
    with patch("causality.staging._apply_hop", side_effect=AssertionError("duplicate effect")):
        assert not persistence.deliver_work(queue, work_id, lambda row: pytest.fail("replayed"))
    assert not persistence.retry_work(queue, work_id)
    with persistence._connect() as conn:
        count = conn.execute(
            """SELECT COUNT(*) FROM world_mutations
               WHERE json_extract(data, '$.delivery.queue') = ?
                 AND json_extract(data, '$.delivery.id') = ?""", (queue, work_id)).fetchone()[0]
    assert count == 1


def test_sigkill_after_continuation_insert_rolls_back_entire_hop(tmp_path, monkeypatch):
    monkeypatch.setenv("NESTED_WORLDS_HOP_DELAY", "0")
    work_id = accept_work("causal_queue")
    before = snapshot()
    candidates = persistence.due_work("causal_queue", 100)
    join(start_worker("causal_queue", "after_continuation"), -signal.SIGKILL)
    assert snapshot() == before
    assert persistence.due_work("causal_queue", 100) == candidates
    join(start_worker("causal_queue", "recover"))
    assert persistence.inspect_work("causal_queue", work_id)["status"] == "completed"
    with persistence._connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM causal_queue WHERE parent_id = ?",
                            (work_id,)).fetchone()[0] == 1


@pytest.mark.parametrize("phase", ["initial_maturation", "initial_hop"])
def test_sigkill_during_acceptance_leaves_no_partial_promise(phase):
    store.ensure_born(382)
    join(start_worker("verb_maturation", phase), -signal.SIGKILL)
    assert persistence.pending_verb_maturations(382) == 0
    assert persistence.pending_causal_hops(382) == 0
    assert snapshot() == ([], {}, {})
    assert act(store.world_tree(seed=382).children[0].children[0])["matures_in"] > 0


@pytest.mark.parametrize("queue", QUEUES)
def test_concurrent_processes_apply_one_candidate_once(queue):
    work_id = accept_work(queue)
    # Both workers see exactly the same candidate; other accepted work stays pending.
    with persistence._connect() as conn:
        conn.execute(f"UPDATE {queue} SET due_at = datetime('now', '+1 day') WHERE id != ?",
                     (work_id,))
    ctx = multiprocessing.get_context("spawn")
    go, a_ready, b_ready = ctx.Event(), ctx.Event(), ctx.Event()
    a = start_worker(queue, "recover", ready=a_ready, go=go, work_id=work_id)
    b = start_worker(queue, "recover", ready=b_ready, go=go, work_id=work_id)
    try:
        assert a_ready.wait(15) and b_ready.wait(15)
        go.set()
        join(a)
        join(b)
    finally:
        for worker in (a, b):
            if worker.is_alive():
                worker.kill()
                worker.join(5)
    assert persistence.inspect_work(queue, work_id)["attempts"] == 1
    with persistence._connect() as conn:
        assert conn.execute(
            """SELECT COUNT(*) FROM world_mutations WHERE
               json_extract(data, '$.delivery.queue') = ? AND
               json_extract(data, '$.delivery.id') = ?""", (queue, work_id)).fetchone()[0] == 1


@pytest.mark.parametrize("queue", QUEUES)
def test_exception_after_effect_rolls_back_and_retries(queue):
    work_id = accept_work(queue)
    before = snapshot()
    seam = "record_substance_transition" if queue == "causal_queue" else "record_substance_change"
    original = getattr(persistence, seam)

    def fail(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("after effect and historical delta")

    with patch.object(persistence, seam, fail):
        assert drain(queue, limit=1) == 0
    assert snapshot() == before
    row = persistence.inspect_work(queue, work_id)
    assert row["status"] == "pending" and row["attempts"] == 1
    assert "after effect and historical delta" in row["last_error"]
    assert row["retry_at"] is not None
    persistence.retry_work(queue, work_id)
    assert drain(queue, limit=1) == 1
    assert persistence.inspect_work(queue, work_id)["attempts"] == 2


def test_failed_hop_does_not_starve_good_work(monkeypatch):
    root = store.world_tree(seed=382)
    bad = persistence.enqueue_causal_hop(382, root.name, "NOT_A_KIND", 1, "up", {}, 0)
    good = persistence.enqueue_causal_hop(382, root.name, "DANGER_ALERT", 1, "up", {}, 0)
    assert drain_due_hops() == 1
    assert persistence.inspect_work("causal_queue", bad)["status"] == "pending"
    assert persistence.inspect_work("causal_queue", good)["outcome"] == "applied"
    # No retry ceiling silently converts failure into completion.
    for _ in range(12):
        persistence.retry_work("causal_queue", bad)
        drain_due_hops()
    assert persistence.inspect_work("causal_queue", bad)["attempts"] == 13


@pytest.mark.parametrize("queue", QUEUES)
def test_missing_node_has_inspectable_terminal_outcome(queue):
    if queue == "causal_queue":
        work_id = persistence.enqueue_causal_hop(382, "Missing-999", "DANGER_ALERT", 1, "up", {}, 0)
    else:
        work_id = persistence.enqueue_verb_maturation(382, "Missing-999", "kindle", {"kindled": True}, "Ada", 0)
    assert drain(queue) == 0
    row = persistence.inspect_work(queue, work_id)
    assert row["status"] == "completed" and row["outcome"] == "missing_node"
    assert persistence.get_node_history(382, "Missing-999") == []


@pytest.mark.parametrize("queue", QUEUES)
def test_broadcast_failure_does_not_retry_material_effect(queue):
    work_id = accept_work(queue)

    def fail(*args, **kwargs):
        assert getattr(persistence._transaction_state, "connection", None) is None
        assert persistence.inspect_work(queue, work_id)["status"] == "completed"
        raise RuntimeError("notification lost after commit")

    if queue == "causal_queue":
        assert drain_due_hops(limit=1, broadcaster=fail) == 1
    else:
        with patch.object(heartbeat, "broadcast", fail):
            assert heartbeat.drain_matured_verbs(limit=1) == 1
    before = snapshot()
    assert not persistence.deliver_work(queue, work_id, lambda row: pytest.fail("replayed"))
    assert snapshot() == before


def test_pending_legacy_migration_and_backup_restore(tmp_path, monkeypatch):
    migrations = persistence._list_migrations()
    # Recreate an actual v17 database, including pre-law and current-law work.
    with patch.object(persistence, "_list_migrations",
                      return_value=[m for m in migrations if m[0] <= 17]):
        persistence.init_db()
    root = store.world_tree(seed=382)
    from multiverse import wrap
    wrap.hinge_name(382)
    galaxy = root.children[0].children[0]
    persistence.record_mutation(382, galaxy.name, "SCALE_ACT", "Legacy",
                                {"verb": "kindle", "matures_in": 120})
    with persistence._connect() as conn:
        conn.execute("""INSERT INTO verb_maturation
            (world_seed,node_name,verb,changed,actor,due_at)
            VALUES (382,?,'kindle',?,'Legacy',datetime('now'))""",
            (galaxy.name, '{"star_density":438,"kindled":true}'))
        for payload in ('{}', '{"_hop":1,"_origin":"Legacy-Origin","_origin_level":"Galaxy"}'):
            conn.execute("""INSERT INTO causal_queue
                (world_seed,node_name,kind,strength,direction,payload,due_at)
                VALUES (382,?,'DANGER_ALERT',0.5,'up',?,datetime('now'))""",
                (root.name, payload))
        legacy = {q: conn.execute(f"SELECT * FROM {q}").fetchall() for q in QUEUES}
        identities = conn.execute("SELECT * FROM world_nodes ORDER BY path").fetchall()
        pins = conn.execute("SELECT * FROM world_meta").fetchall()
        history = conn.execute("SELECT * FROM world_mutations").fetchall()
    before_upgrade = tmp_path / "v17.db"
    persistence.backup_to(before_upgrade)
    persistence._initialized.clear()
    persistence.init_db()
    with persistence._connect() as conn:
        for q in QUEUES:
            rows = conn.execute(f"SELECT * FROM {q}").fetchall()
            assert [r[:len(legacy[q][0])] for r in rows] == legacy[q]
        assert conn.execute("SELECT * FROM world_nodes ORDER BY path").fetchall() == identities
        assert conn.execute("SELECT * FROM world_meta").fetchall() == pins
        assert conn.execute("SELECT * FROM world_mutations").fetchall() == history
    backup = tmp_path / "v18-pending.db"
    persistence.backup_to(backup)
    monkeypatch.setenv("NESTED_WORLDS_HOP_DELAY", "0")
    assert drain_due_hops() == 2
    assert heartbeat.drain_matured_verbs() == 1
    expected = snapshot()
    with persistence._connect() as conn:
        # Pre-law strength fires as-is; _hop row dampens itself on arrival.
        strengths = conn.execute("SELECT strength FROM world_mutations WHERE node_name = ? ORDER BY id",
                                 (root.name,)).fetchall()
    assert strengths == [(0.5,), (0.25,)]
    assert expected[1][galaxy.name] == {"star_density": 438, "kindled": True}
    persistence.restore_from(backup)
    from server.rooms import clear_rooms
    clear_rooms()
    join(start_worker("causal_queue", "recover"))
    join(start_worker("causal_queue", "recover"))
    join(start_worker("verb_maturation", "recover"))
    assert snapshot() == expected
    # A pre-upgrade rollback is a whole DB restore, preserving pending inputs.
    persistence.restore_from(before_upgrade)
    persistence._initialized.clear()
    persistence.init_db()
    assert persistence.pending_causal_hops(382) == 2
    assert persistence.pending_verb_maturations(382) == 1


def test_solve_initial_enqueue_failure_retries_in_same_process(monkeypatch):
    root = store.world_tree(seed=382)
    node = next(n for n in walk(root) if n.level == "Room")
    with patch.object(persistence, "enqueue_causal_hop", side_effect=RuntimeError("initial ring failed")):
        with pytest.raises(RuntimeError):
            solve(node)
    assert persistence.get_puzzle_solve(382, node.name, build_puzzle(node).name) is None
    assert persistence.get_node_history(382, node.name) == []
    assert solve(node)["correct"]
    before = snapshot()
    assert solve(node)["correct"]
    assert snapshot() == before


@pytest.mark.parametrize("queue", QUEUES)
def test_database_commit_failure_preserves_pending_work(queue):
    work_id = accept_work(queue)
    before = snapshot()
    real_connect = persistence._connect
    failed = False

    class CommitFailure(sqlite3.Connection):
        def __exit__(self, exc_type, exc, tb):
            nonlocal failed
            if exc_type is None and self.in_transaction and not failed:
                failed = True
                self.rollback()
                raise sqlite3.OperationalError("injected commit failure")
            return super().__exit__(exc_type, exc, tb)

    def connect():
        conn = sqlite3.connect(persistence._DB_PATH, factory=CommitFailure)
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    with patch.object(persistence, "_connect", connect):
        assert drain(queue, limit=1) == 0
    assert failed and snapshot() == before
    assert "commit failure" in persistence.inspect_work(queue, work_id)["last_error"]
    assert persistence._connect is real_connect
    persistence.retry_work(queue, work_id)
    assert drain(queue, limit=1) == 1


def test_effect_and_continuation_exception_commit_together(monkeypatch):
    monkeypatch.setenv("NESTED_WORLDS_HOP_DELAY", "0")
    work_id = accept_work("causal_queue")
    before = snapshot()
    original = persistence.enqueue_causal_hop

    def fail(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("continuation insertion failed")

    with patch.object(persistence, "enqueue_causal_hop", fail):
        assert drain_due_hops(limit=1) == 0
    assert snapshot() == before
    with persistence._connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM causal_queue WHERE parent_id = ?",
                            (work_id,)).fetchone()[0] == 0
    persistence.retry_work("causal_queue", work_id)
    assert drain_due_hops(limit=1) == 1


def test_overlapping_http_acts_keep_two_legacy_absolute_outcomes(monkeypatch):
    import json
    import threading
    import urllib.request
    from concurrent.futures import ThreadPoolExecutor
    from server import _ThreadedServer
    monkeypatch.setenv("NESTED_WORLDS_MATURATION_SCALE", "0.001")
    root = store.world_tree(seed=382)
    galaxy = root.children[0].children[0]
    server = _ThreadedServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def post(name):
        req = urllib.request.Request(
            f"http://127.0.0.1:{server.server_address[1]}/act",
            data=json.dumps({"seed": 382, "node_name": galaxy.name, "player_name": name}).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.load(response)

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            replies = list(pool.map(post, ("Ada", "Bea")))
        assert replies[0]["changed"] == replies[1]["changed"]
        assert persistence.pending_verb_maturations(382) == 2
        assert galaxy.name not in persistence.load_node_property_overrides(382)
        assert heartbeat.drain_matured_verbs() == 2
        assert persistence.load_node_property_overrides(382)[galaxy.name] == replies[0]["changed"]
        assert len(persistence.get_substance_deltas(382, galaxy.name)) == 2
        # A fresh request sees the committed outcome despite missing broadcasts.
        with urllib.request.urlopen(
                f"http://127.0.0.1:{server.server_address[1]}/world?seed=382&depth=3",
                timeout=10) as response:
            world = json.load(response)
        served = world["world"]["children"][0]["children"][0]
        assert served["name"] == galaxy.name
        for key, value in replies[0]["changed"].items():
            assert served["properties"][key] == value
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)


@pytest.mark.parametrize("queue", QUEUES)
def test_exception_after_successful_commit_cannot_replay_effect(queue):
    work_id = accept_work(queue)
    failed = False

    class LostCommitAcknowledgment(sqlite3.Connection):
        def __exit__(self, exc_type, exc, tb):
            nonlocal failed
            committed = exc_type is None and self.in_transaction
            result = super().__exit__(exc_type, exc, tb)
            if committed and not failed:
                failed = True
                raise sqlite3.OperationalError("commit acknowledgment lost")
            return result

    with patch.object(persistence, "_connect", side_effect=lambda: sqlite3.connect(
            persistence._DB_PATH, factory=LostCommitAcknowledgment)):
        assert drain(queue, limit=1) == 0
    assert failed
    row = persistence.inspect_work(queue, work_id)
    assert row["status"] == "completed" and row["outcome"] == "applied"
    before = snapshot()
    assert not persistence.deliver_work(queue, work_id, lambda row: pytest.fail("replayed"))
    assert snapshot() == before


@pytest.mark.parametrize("queue", QUEUES)
def test_future_version_is_retained_without_using_current_rules(queue):
    work_id = accept_work(queue)
    before = snapshot()
    with persistence._connect() as conn:
        conn.execute(f"UPDATE {queue} SET semantics_version = 99 WHERE id = ?", (work_id,))
    assert drain(queue, limit=1) == 0
    row = persistence.inspect_work(queue, work_id)
    assert row["status"] == "pending" and "unsupported" in row["last_error"]
    assert snapshot() == before


def test_cli_and_cast_initial_enqueue_failures_are_atomic(monkeypatch):
    import random
    import interface
    from server.rooms import get_room
    root = store.world_tree(seed=382)
    galaxy = root.children[0].children[0]
    with patch.object(persistence, "enqueue_causal_hop", side_effect=RuntimeError("initial ring failed")):
        with pytest.raises(RuntimeError):
            interface._do_scale_verb(galaxy, 382, "CLIVisitor")
        with pytest.raises(RuntimeError):
            heartbeat._persona_act(382, get_room(382), root, "Tender", "tender",
                                   [galaxy.name], random.Random(1), None)
        with pytest.raises(RuntimeError):
            heartbeat._persona_act(382, get_room(382), root, "Entropy", "destabilizer",
                                   [galaxy.name], random.Random(1), None)
    assert snapshot() == ([], {}, {})
    assert persistence.pending_causal_hops(382) == 0
    assert persistence.pending_verb_maturations(382) == 0


def test_nested_failure_cannot_commit_if_exception_is_caught():
    with pytest.raises(RuntimeError, match="nested database operation failed"):
        with persistence.transaction():
            with contextlib.suppress(RuntimeError):
                with persistence.transaction():
                    persistence.record_mutation(382, "test", "AGENT_VISIT", None, {})
                    raise RuntimeError("failed nested work")
    assert persistence.get_node_history(382, "test") == []


@pytest.mark.parametrize("queue", QUEUES)
@pytest.mark.parametrize("blob", ['["invalid root"]', 'invalid json'])
def test_malformed_payload_is_retained_without_partial_effect(queue, blob):
    work_id = accept_work(queue)
    before = snapshot()
    field = "payload" if queue == "causal_queue" else "changed"
    with persistence._connect() as conn:
        conn.execute(f"UPDATE {queue} SET {field} = ? WHERE id = ?", (blob, work_id))
    assert drain(queue, limit=1) == 0
    row = persistence.inspect_work(queue, work_id)
    assert row["status"] == "pending" and row["last_error"]
    assert row[field] == blob
    assert snapshot() == before
