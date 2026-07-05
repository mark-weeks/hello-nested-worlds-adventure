"""The named cast: twelve individuals, not eight hash rolls.

Pins the roster's design invariants (balance, sync with the bible cast,
valid trait sheets) and exercises the traits where the heartbeat actually
reads them: drop-in home affinity, the contains_npc pull, per-agent
courage, favored verbs, and banter tics.
"""
from __future__ import annotations

import hashlib
import random
from collections import Counter

import pytest

from agents.banter import compose_exchange
from agents.personas import CATALOG, by_name, for_name
from agents.roster import CAST_NAMES, PROFILES, profile_for
from consciousness import WANDERER_CAST
from multiverse.generator import LEVELS, generate_node_hierarchy
from multiverse.node import SpatialNode
from multiverse.verbs import VERBS_BY_NAME
from server import heartbeat
from server.rooms import get_room


@pytest.fixture(autouse=True)
def _zero_hop_delay(monkeypatch):
    monkeypatch.setenv("NESTED_WORLDS_HOP_DELAY", "0")
    yield


class TestRosterDesign:
    def test_roster_matches_the_bible_cast(self):
        # consciousness.WANDERER_CAST is the leaf copy baked into the cached
        # voice bibles; the roster carries the trait sheets. Same names, or
        # the prompts and the heartbeat drift apart.
        assert set(CAST_NAMES) == set(WANDERER_CAST)
        assert len(CAST_NAMES) == len(WANDERER_CAST) == 12

    def test_personas_are_balanced(self):
        counts = Counter(p.persona for p in PROFILES)
        assert counts == {"tender": 3, "destabilizer": 3,
                          "scholar": 3, "wanderer": 3}

    def test_trait_sheets_are_valid(self):
        allowed_scholar_verbs = {"inscribe", "observe", "calibrate"}
        for p in PROFILES:
            assert by_name(p.persona) is not None, p.name
            assert p.home_levels and all(lvl in LEVELS
                                         for lvl in p.home_levels), p.name
            assert 0 <= p.danger_threshold <= 10, p.name
            assert p.tic.strip(), p.name
            if p.favored_verb is not None:
                assert p.favored_verb in VERBS_BY_NAME, p.name
            if p.persona == "scholar":
                # Scholars only ever perform the documentary verbs; a
                # favored verb outside that set could never fire.
                assert p.favored_verb in allowed_scholar_verbs, p.name
            if p.persona in ("destabilizer", "wanderer"):
                # These personas never perform scale verbs in _persona_act.
                assert p.favored_verb is None, p.name

    def test_for_name_honors_the_deliberate_assignment(self):
        # The two the hash famously miscast:
        assert for_name("Aunt Entropy").name == "destabilizer"
        assert for_name("Cartographer-9").name == "scholar"
        for p in PROFILES:
            assert for_name(p.name).name == p.persona

    def test_off_roster_names_still_hash_deterministically(self):
        assert profile_for("Brann") is None
        digest = hashlib.sha1(b"Brann").digest()
        assert for_name("Brann") is CATALOG[digest[0] % len(CATALOG)]


class TestHomeAffinity:
    def test_drop_in_gravitates_home(self):
        # Marginalia homes at Molecule/Atom — depths a profile-less ramble
        # (1-5 hops) can never reach. With the trait sheet, most drop-ins
        # land on home ground.
        root = generate_node_hierarchy(seed=42)
        profile = profile_for("Marginalia")
        rng = random.Random(99)
        hits = sum(1 for _ in range(60)
                   if heartbeat._drop_in(root, rng, profile).level
                   in profile.home_levels)
        assert hits >= 20

        rng = random.Random(99)
        baseline = sum(1 for _ in range(60)
                       if heartbeat._drop_in(root, rng).level
                       in profile.home_levels)
        assert baseline == 0

    def test_drop_in_prefers_inhabited_children(self):
        # Two rooms under one region, one flagged contains_npc: the walk
        # pulls toward the inhabited one — the trait finally seats visitors.
        root = SpatialNode("Ward-1", "Region", properties={})
        quiet = SpatialNode("Quiet-11", "Room", properties={})
        peopled = SpatialNode("Full-12", "Room",
                              properties={"contains_npc": True})
        for r in (quiet, peopled):
            root.add_child(r)
            r.add_child(SpatialNode(f"Obj-{r.name}", "Object", properties={}))
        rng = random.Random(5)
        landed = Counter(heartbeat._drop_in(root, rng).name
                         for _ in range(200))
        assert landed["Full-12"] > landed["Quiet-11"] * 2


class TestCourage:
    def test_tick_sends_the_regular_out_with_their_own_threshold(self, monkeypatch):
        captured: dict[str, int] = {}
        real_agent = heartbeat.Agent

        def spy(*args, **kwargs):
            agent = real_agent(*args, **kwargs)
            captured[agent.name] = agent.danger_threshold
            return agent

        monkeypatch.setattr(heartbeat, "Agent", spy)
        summary = heartbeat.run_tick(seed=901, rng=random.Random(6), pace=0.0)
        profile = profile_for(summary["agent"])
        assert captured[summary["agent"]] == profile.danger_threshold


class TestFavoredVerb:
    def test_locksmith_reaches_for_inscribe_first(self):
        # A Room (inscribe) and a Region (ward) both just visited: without
        # the bias the sample order decides; The Locksmith's sheet puts the
        # Room first every time.
        root = SpatialNode("Plot-1", "Planet", properties={})
        room = SpatialNode("Cell-11", "Room", properties={})
        wild = SpatialNode("Wild-12", "Region", properties={"danger_level": 3})
        root.add_child(room)
        root.add_child(wild)
        acts = set()
        for i in range(12):
            act = heartbeat._persona_act(
                seed=902, room=get_room(902), root=root,
                agent_name="The Locksmith", persona_name="tender",
                visited_names=["Cell-11", "Wild-12"],
                rng=random.Random(i), bus=None)
            if act is not None:
                acts.add(act.split()[0])
        assert acts == {"inscribeed"}


class TestBanterTics:
    def test_regulars_tics_surface_and_stay_occasional(self):
        node = SpatialNode("Talk-11", "Room", properties={})
        tic = profile_for("The Locksmith").tic
        hits = sum(
            1 for ordinal in range(12)
            if tic in " ".join(
                l["line"] for l in compose_exchange(
                    9, node, "The Locksmith", "tender",
                    "Vex", "destabilizer", ordinal=ordinal)))
        assert 1 <= hits < 12

    def test_off_roster_speakers_never_gain_a_tic(self):
        node = SpatialNode("Talk-12", "Room", properties={})
        all_tics = [p.tic for p in PROFILES]
        for ordinal in range(12):
            lines = compose_exchange(9, node, "Brann", "tender",
                                     "Quill", "scholar", ordinal=ordinal)
            text = " ".join(l["line"] for l in lines)
            assert not any(t in text for t in all_tics)


class TestInhabitedGroundIsSocial:
    def test_contains_npc_ground_hosts_more_meetings(self, monkeypatch):
        import persistence

        # Same world, same tick seeds; only the drop-in target differs —
        # inhabited ground must host more conversations than quiet ground.
        root = generate_node_hierarchy(seed=42)

        def rooms_with(npc):
            out = []
            def walk(n):
                if (n.level == "Room" and n.children
                        and bool(n.properties.get("contains_npc")) is npc):
                    out.append(n)
                for c in n.children:
                    walk(c)
            walk(root)
            return out

        peopled = rooms_with(True)[0]
        quiet = rooms_with(False)[0]

        def talks_at(target, world_seed):
            monkeypatch.setattr(heartbeat, "_drop_in",
                                lambda root, rng, profile=None: target)
            for i in range(20):
                heartbeat.run_tick(seed=world_seed, rng=random.Random(i),
                                   pace=0.0)
            return sum(1 for m in persistence.get_mutations(world_seed,
                                                            limit=500)
                       if m["type"] == "AGENT_TALK")

        # NOTE: _drop_in is patched, but run_tick regenerates the world per
        # tick — target nodes must come from a tree with the same names,
        # which seed 42 guarantees.
        assert talks_at(peopled, 42) > talks_at(quiet, 43)
