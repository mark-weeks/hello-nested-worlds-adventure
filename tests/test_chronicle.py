"""The world chronicle: paginated history + deterministic era names.

Continuity made perceivable — a new arrival must be able to read what every
player and agent did before them, era by era, and the era names must read
identically to every participant forever (pure function of seed + ISO week).
"""
from __future__ import annotations

import json
import threading
import urllib.request

import pytest

import persistence
from multiverse.chronicle import annotate_eras, current_era, era_name


class TestEraNames:
    def test_deterministic_per_seed_and_week(self):
        assert era_name(42, "2026-07-01 12:00:00") == era_name(42, "2026-07-01 23:59:59")
        # Same ISO week, different day → same era.
        assert era_name(42, "2026-06-29 00:00:00") == era_name(42, "2026-07-03 00:00:00")

    def test_differs_across_weeks_and_seeds(self):
        weeks = {era_name(42, f"2026-{m:02d}-15 00:00:00") for m in range(1, 13)}
        assert len(weeks) > 6  # months land in distinct weeks; names vary
        assert era_name(42, "2026-07-01 00:00:00") != era_name(7, "2026-07-01 00:00:00") \
            or era_name(42, "2026-08-01 00:00:00") != era_name(7, "2026-08-01 00:00:00")

    def test_reads_as_fiction(self):
        name = era_name(1, "2026-07-04 00:00:00")
        assert name.startswith("The ")
        assert " of " in name or " " in name[4:]

    def test_current_era_is_a_name(self):
        assert current_era(42).startswith("The ")

    def test_annotate_stamps_every_entry(self):
        entries = [{"at": "2026-07-01 10:00:00"}, {"at": "2026-01-05 10:00:00"}]
        out = annotate_eras(9, entries)
        assert all(e["era"].startswith("The ") for e in out)
        assert out[0]["era"] != out[1]["era"]


class TestChronicleQuery:
    def test_pagination_walks_backward_without_gaps_or_overlap(self):
        for i in range(25):
            persistence.record_mutation(77, f"Node-{i}", "AGENT_VISIT", None, {"i": i})
        page1 = persistence.get_chronicle(77, limit=10)
        assert len(page1["entries"]) == 10
        assert page1["total"] == 25
        assert page1["next_before"] is not None

        page2 = persistence.get_chronicle(77, limit=10, before_id=page1["next_before"])
        page3 = persistence.get_chronicle(77, limit=10, before_id=page2["next_before"])
        assert len(page2["entries"]) == 10
        assert len(page3["entries"]) == 5
        assert page3["next_before"] is None

        ids = [e["id"] for p in (page1, page2, page3) for e in p["entries"]]
        assert len(ids) == 25 == len(set(ids))
        assert ids == sorted(ids, reverse=True)  # newest first throughout

    def test_began_is_the_worlds_first_event(self):
        persistence.record_mutation(78, "Genesis", "AGENT_VISIT", None, {})
        page = persistence.get_chronicle(78)
        assert page["began"] is not None
        assert page["entries"][-1]["node"] == "Genesis"

    def test_empty_world_reads_as_empty(self):
        page = persistence.get_chronicle(424242)
        assert page == {"entries": [], "next_before": None, "total": 0,
                        "began": None}


class TestChronicleEndpoint:
    @pytest.fixture()
    def srv(self):
        from server import _Handler, _ThreadedServer
        server = _ThreadedServer(("127.0.0.1", 0), _Handler)
        port = server.server_address[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()
        yield f"http://127.0.0.1:{port}"
        server.shutdown()

    def test_chronicle_carries_eras_and_pagination(self, srv):
        for i in range(5):
            persistence.record_mutation(91, f"Spire-{i}", "PUZZLE_SOLVED",
                                        "Ada", {"puzzle": f"P{i}"})
        with urllib.request.urlopen(f"{srv}/chronicle?seed=91&limit=3") as resp:
            data = json.loads(resp.read())
        assert data["seed"] == 91
        assert data["total"] == 5
        assert len(data["entries"]) == 3
        assert data["next_before"] is not None
        assert data["era_now"].startswith("The ")
        assert all(e["era"].startswith("The ") for e in data["entries"])
        assert data["entries"][0]["player"] == "Ada"

        nxt = data["next_before"]
        with urllib.request.urlopen(
                f"{srv}/chronicle?seed=91&limit=3&before={nxt}") as resp:
            older = json.loads(resp.read())
        assert len(older["entries"]) == 2
        assert older["next_before"] is None

    def test_bad_params_rejected(self, srv):
        import urllib.error
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(f"{srv}/chronicle?seed=abc")
        assert exc.value.code == 400
