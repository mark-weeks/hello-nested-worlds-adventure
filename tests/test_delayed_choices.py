"""M2 request-to-outcome contracts. Every database and HTTP server is disposable."""
import json
import random
import signal
import threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from unittest.mock import patch

import pytest

import persistence
from multiverse import store, wrap
from multiverse.verbs import VERBS
from server import _Handler, _ThreadedServer, heartbeat
from tests.test_delivery_recovery import join, snapshot, start_worker

SEED = 382
CASES = [
    ("attune", "Multiverse", "stability", "attuned", "collapsing", "stable"),
    ("calibrate", "Universe", "dark_matter_ratio", "calibrated", 0.8, 0.7),
    ("kindle", "Galaxy", "star_density", "kindled", 418, 459),
    ("align", "Planetary System", "ecliptic_tilt_deg", "aligned", 10.0, 8.1),
]
SATURATED = {"attune": "stable", "calibrate": 0.5, "kindle": 999, "align": 0.4}


def walk(node):
    yield node
    for child in node.children:
        yield from walk(child)


def change(node, props):
    persistence.record_substance_change(SEED, node.name, "TEST_CHANGE", None, {}, props)


def due():
    with persistence._connect() as conn:
        conn.execute("UPDATE verb_maturation SET due_at = '2000-01-01' WHERE status = 'pending'")


def land():
    due()
    return heartbeat.drain_matured_verbs()


def history(node, kind="SCALE_ACT_MATURED"):
    with persistence._connect() as conn:
        rows = conn.execute(
            """SELECT data, delta, node_version FROM world_mutations
                WHERE world_seed=? AND node_name=? AND mutation_type=? ORDER BY id DESC""",
            (SEED, node.name, kind)).fetchall()
    return [{"data": json.loads(data), "delta": json.loads(delta) if delta else None,
             "node_version": version} for data, delta, version in rows]


@pytest.fixture
def http(monkeypatch):
    monkeypatch.setenv("NESTED_WORLDS_CANONICAL_SEED", str(SEED))
    monkeypatch.setenv("NESTED_WORLDS_MATURATION_SCALE", "1")
    root = store.world_tree(SEED)
    server = _ThreadedServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_address[1]}"

    class Client:
        def node(self, level):
            return next(n for n in walk(root) if n.level == level)

        def post(self, node, name="Ada", **body):
            req = urllib.request.Request(url + "/act", data=json.dumps({
                "node_name": node.name, "player_name": name, **body}).encode(),
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as response:
                return json.load(response)

        def read(self, node):
            with urllib.request.urlopen(url + "/world?depth=4", timeout=10) as response:
                tree = json.load(response)["world"]
            def find(n):
                if n["name"] == node.name:
                    return n
                return next((found for child in n["children"] if (found := find(child))), None)
            return find(tree)

    try:
        yield Client()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)


@pytest.mark.parametrize("verb,level,field,flag,initial,expected", CASES)
def test_concurrent_participants_contribute_once_against_live_state(
        http, verb, level, field, flag, initial, expected):
    node = http.node(level)
    change(node, {field: initial, flag: False})
    with ThreadPoolExecutor(2) as pool:
        replies = list(pool.map(lambda name: http.post(node, name), ["Ada", "Bea"]))
    assert {r["action_status"] for r in replies} == {"accepted"}
    assert all(r["changed"] is None and r["work"]["policy"] == "contribution" for r in replies)
    assert len({r["work"]["id"] for r in replies}) == 2
    accepted = http.read(node)
    assert accepted["properties"][field] == initial
    assert accepted["pending_actions"][0]["count"] == 2
    assert land() == 2
    current = http.read(node)
    assert current["properties"][field] == expected
    assert current["pending_actions"] == []
    assert len(history(node)) == 2
    before = snapshot()
    for reply in replies:
        assert not persistence.deliver_work("verb_maturation", reply["work"]["id"],
                                             lambda row: pytest.fail("duplicate applied"))
    assert snapshot() == before


@pytest.mark.parametrize("verb,level,field,flag,initial,expected", CASES)
def test_only_one_time_mark_remains_shared_across_participants_and_repetition(
        http, verb, level, field, flag, initial, expected):
    node = http.node(level)
    change(node, {field: SATURATED[verb], flag: False})
    with ThreadPoolExecutor(4) as pool:
        replies = list(pool.map(lambda name: http.post(node, name), ["Ada", "Bea", "Ada", "Dee"]))
    assert sorted(r["action_status"] for r in replies) == ["accepted", "shared", "shared", "shared"]
    assert len({r["work"]["id"] for r in replies}) == 1
    assert len({r["work"]["due_at"] for r in replies}) == 1
    assert len(history(node, "SCALE_ACT")) == 1
    pending = http.read(node)["pending_actions"]
    assert len(pending) == 1 and pending[0]["count"] == 1
    assert all("no additional" in r["flavor"] for r in replies if r["action_status"] == "shared")
    assert land() == 1
    assert http.read(node)["properties"][flag] is True
    before = snapshot()
    assert http.post(node)["action_status"] == "noop"
    assert snapshot() == before  # no origin/ripple for saturated admission


@pytest.mark.parametrize("verb,level,field,flag,initial,expected", CASES)
def test_mark_only_never_turns_into_later_growth(http, verb, level, field, flag, initial, expected):
    node = http.node(level)
    change(node, {field: SATURATED[verb], flag: False})
    reply = http.post(node)
    assert reply["work"]["policy"] == "transition"
    change(node, {field: initial})
    assert land() == 1
    assert http.read(node)["properties"][field] == initial
    assert history(node)[0]["data"]["changed"] == {flag: True}


@pytest.mark.parametrize("verb,level,field,flag,initial,expected", CASES)
def test_changed_circumstances_explicitly_close_without_delta(
        http, verb, level, field, flag, initial, expected):
    node = http.node(level)
    change(node, {field: initial, flag: False})
    reply = http.post(node)
    change(node, {field: None})  # a deletion must not fall back to the born value
    assert land() == 1
    row = persistence.inspect_work("verb_maturation", reply["work"]["id"])
    assert row["status"] == "completed" and row["outcome"] == "precondition_changed"
    event = history(node)[0]
    assert event["delta"] is None and event["node_version"] is None
    assert event["data"]["changed"] is None
    assert "Nothing changes" in event["data"]["flavor"]
    assert field not in http.read(node)["properties"]
    assert http.post(node)["action_status"] == "noop"


def test_intervening_growth_is_preserved_and_missing_flag_not_reaccepted(http):
    node = http.node("Galaxy")
    change(node, {"star_density": 418, "kindled": True})
    http.post(node)
    change(node, {"star_density": 800, "kindled": False})
    land()
    current = http.read(node)["properties"]
    assert current["star_density"] == 840
    assert current["kindled"] is False  # this accepted operation did not include the flag


def test_mark_only_joins_a_contribution_carrying_the_same_pending_flag(http):
    node = http.node("Galaxy")
    first = http.post(node)
    change(node, {"star_density": 999})
    second = http.post(node, "Bea")
    assert second["action_status"] == "shared" and first["work"] == second["work"]
    land()
    assert history(node)[0]["data"]["changed"] == {"kindled": True}


def test_saturation_closes_later_accepted_contributions_without_fabricated_delta(http):
    node = http.node("Galaxy")
    change(node, {"star_density": 998, "kindled": True})
    replies = [http.post(node) for _ in range(3)]  # distinct requests, same participant
    assert len({r["work"]["id"] for r in replies}) == 3
    assert land() == 3
    assert http.read(node)["properties"]["star_density"] == 999
    outcomes = [persistence.inspect_work("verb_maturation", r["work"]["id"])["outcome"] for r in replies]
    assert outcomes == ["applied", "already_satisfied", "already_satisfied"]
    assert sum(e["delta"] is not None for e in history(node)) == 1


@pytest.mark.parametrize("level,properties", [
    ("Galaxy", {"star_density": True}), ("Galaxy", {"star_density": -1}),
    ("Universe", {"dark_matter_ratio": 2}), ("Planetary System", {"ecliptic_tilt_deg": -1}),
    ("Multiverse", {"stability": ["stable"]}),
])
def test_invalid_acceptance_never_marks_or_schedules(http, level, properties):
    node = http.node(level)
    change(node, properties)
    before = snapshot()
    reply = http.post(node)
    assert reply["action_status"] == "noop" and reply["outcome"] == "precondition_changed"
    assert persistence.pending_verb_maturations(SEED) == 0
    assert snapshot() == before


def test_v2_does_not_dispatch_through_latest_effect_at_acceptance_or_landing(http, monkeypatch):
    node = http.node("Galaxy")
    def future(*args):
        pytest.fail("latest effect interpreted accepted v2 work")
    monkeypatch.setitem(VERBS, "Galaxy", replace(VERBS["Galaxy"], effect=future))
    reply = http.post(node)
    assert reply["action_status"] == "accepted"
    assert land() == 1
    assert http.read(node)["properties"]["star_density"] == 438


@pytest.mark.parametrize("malformation", ["version", "operation"])
def test_unknown_operation_stays_pending_while_valid_work_progresses(http, malformation):
    node = http.node("Galaxy")
    bad, good = http.post(node), http.post(node, "Bea")
    with persistence._connect() as conn:
        if malformation == "version":
            conn.execute("UPDATE verb_maturation SET semantics_version=999 WHERE id=?", (bad["work"]["id"],))
        else:
            conn.execute("UPDATE verb_maturation SET operation=? WHERE id=?",
                         ('{"adjust":true,"mark":true,"future":1}', bad["work"]["id"]))
    assert land() == 1
    bad_row = persistence.inspect_work("verb_maturation", bad["work"]["id"])
    assert bad_row["status"] == "pending" and bad_row["last_error"]
    assert persistence.inspect_work("verb_maturation", good["work"]["id"])["outcome"] == "applied"


def test_legacy_absolute_patches_remain_distinct_and_can_coexist_with_v2(http):
    node = http.node("Galaxy")
    patch_value = {"star_density": 438, "kindled": True}
    legacy = [persistence.enqueue_verb_maturation(SEED, node.name, "kindle", patch_value, "Legacy", 0)
              for _ in range(2)]
    modern = http.post(node)
    assert land() == 3
    assert http.read(node)["properties"]["star_density"] == 459
    events = list(reversed(history(node)))
    assert [e["delta"] for e in events[:2]] == [patch_value, patch_value]
    assert [e["node_version"] for e in events] == [1, 2, 3]
    before = snapshot()
    for work_id in legacy + [modern["work"]["id"]]:
        assert not persistence.deliver_work("verb_maturation", work_id, lambda row: pytest.fail("replayed"))
    assert snapshot() == before


def test_shared_v2_never_coalesces_accepted_legacy_mark(http):
    node = http.node("Galaxy")
    change(node, {"star_density": 999, "kindled": False})
    legacy = persistence.enqueue_verb_maturation(SEED, node.name, "kindle", {"kindled": True}, "Legacy", 0)
    modern = http.post(node)
    assert modern["action_status"] == "accepted" and modern["work"]["id"] != legacy
    assert land() == 2
    assert persistence.inspect_work("verb_maturation", legacy)["outcome"] == "applied"
    assert persistence.inspect_work("verb_maturation", modern["work"]["id"])["outcome"] == "already_satisfied"


@pytest.mark.parametrize("phase", ["before_commit", "after_commit"])
def test_terminal_noop_survives_process_death_and_restart(http, phase):
    node = http.node("Galaxy")
    reply = http.post(node)
    change(node, {"star_density": 999, "kindled": True})
    due()
    join(start_worker("verb_maturation", phase), -signal.SIGKILL)
    join(start_worker("verb_maturation", "recover"))
    assert len(history(node)) == 1
    assert persistence.inspect_work("verb_maturation", reply["work"]["id"])["outcome"] == "already_satisfied"
    assert history(node)[0]["delta"] is None


def test_cli_cast_and_http_share_one_time_admission(http, capsys):
    import interface
    from server.rooms import get_room
    node = http.node("Universe")
    change(node, {"dark_matter_ratio": 0.5, "calibrated": False})
    root = store.world_tree(SEED)
    cast_node = next(n for n in walk(root) if n.name == node.name)
    # Cast is the first accepter; the stale CLI tree must not create another.
    result = heartbeat._persona_act(SEED, get_room(SEED), root, "Tender", "tender",
                                    [cast_node.name], random.Random(1))
    assert result
    interface._do_scale_verb(node, SEED, "Ada")
    assert "no additional change" in capsys.readouterr().out
    assert http.post(node, "Bea")["action_status"] == "shared"
    assert persistence.pending_verb_maturations(SEED) == 1
    assert land() == 1


def test_m1_to_m2_migration_pending_backup_restore_and_dedup(http, tmp_path, monkeypatch):
    # Build a separate real v18 database, then migrate without rewriting rows.
    db = tmp_path / "upgrade.db"
    monkeypatch.setattr(persistence, "_DB_PATH", db)
    migrations = persistence._list_migrations()
    with patch.object(persistence, "_list_migrations", return_value=[m for m in migrations if m[0] <= 18]):
        persistence.init_db()
    node = store.world_tree(SEED).children[0].children[0]
    wrap.hinge_name(SEED)
    with persistence._connect() as conn:
        for _ in range(2):
            conn.execute("""INSERT INTO verb_maturation(world_seed,node_name,verb,changed,actor,due_at)
                VALUES (382,?,'kindle','{"star_density":438,"kindled":true}','Legacy','2000-01-01')""", (node.name,))
        # Completed legacy fence must survive too.
        conn.execute("UPDATE verb_maturation SET status='completed',outcome='applied' WHERE id=1")
        before = {table: conn.execute(f"SELECT * FROM {table}").fetchall()
                  for table in ("verb_maturation", "world_nodes", "world_meta", "world_mutations")}
    rollback = tmp_path / "v18.db"
    persistence.backup_to(rollback)
    persistence._initialized.discard(db)
    persistence.init_db()
    with persistence._connect() as conn:
        assert conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0] == 19
        for table, rows in before.items():
            now = conn.execute(f"SELECT * FROM {table}").fetchall()
            assert [r[:len(rows[0])] for r in now] == rows if rows else now == []
    modern = http.post(node)
    root = http.node("Multiverse")
    change(root, {"stability": "stable", "attuned": False})
    shared = http.post(root)
    assert http.post(root, "Bea")["work"] == shared["work"]
    due()
    backup = tmp_path / "v19-pending.db"
    persistence.backup_to(backup)
    assert heartbeat.drain_matured_verbs() == 3
    expected = snapshot()
    persistence.restore_from(backup)
    join(start_worker("verb_maturation", "recover"))
    join(start_worker("verb_maturation", "recover"))
    join(start_worker("verb_maturation", "recover"))
    assert snapshot() == expected
    for work_id in (1, 2, modern["work"]["id"], shared["work"]["id"]):
        assert not persistence.deliver_work("verb_maturation", work_id, lambda row: pytest.fail("restored duplicate"))
    persistence.restore_from(rollback)
    persistence._initialized.discard(db)
    persistence.init_db()
    assert persistence.pending_verb_maturations(SEED) == 1
    assert persistence.inspect_work("verb_maturation", 1)["status"] == "completed"
