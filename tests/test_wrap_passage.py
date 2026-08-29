"""The wrap passage (ADR-008): the hierarchy closes into a traversal-layer loop.

Descending below any SubatomicParticle surfaces at the Multiverse root;
ascending beyond the root lands at the world's ONE hinge particle. Pinned
here, as behavior:

- SELECTION PURITY: the hinge is a pure function of (seed, world as born)
  — a fresh install of the same seed selects the same particle.
- THE LIVENESS INVARIANT: the hinge sits on a fully unsealed lineage, so
  a root-side traveler (who arrives from outside every seal on that
  lineage) can always cross. On seed 382 the eligible pool is 799 of
  1,505 particles — 706 (46.9%) sit beneath a locked Room.
- PIN IMMUTABILITY: the first selection is stored in world_meta and the
  stored hinge IS the hinge from then on — editing the selector cannot
  move a pinned monument (TestSelectorEditImmunity, the wrap's mirror of
  the store's TestBankEditImmunity).
- THE LOOP IS A PASSAGE, NOT A WORMHOLE: wrap transit runs the standard
  seal gate on every surface; containment stays a tree (no parent link
  is mutated); causality does not wrap.
"""
from __future__ import annotations

import json
import threading
import urllib.request

import pytest

import consciousness
import persistence
from multiverse import store, wrap
from multiverse.node import SpatialNode
from puzzles.gates import seal_check, sealing_room
from tests.test_day_one_recording import (  # noqa: F401
    _wait_for_rows, _ws_connect, _ws_send_json, srv,
)
from tests.test_movement import _recv_frames

SEED = 382  # the launch world — the census below is its permanent record

LAUNCH_HINGE = "Hidden Thorn Quark-11431112111"


def _born_rows(seed):
    store.ensure_born(seed)
    return persistence.get_world_nodes(seed)


def _particle_census(seed):
    """(all particle names, ineligible particle names) from the born rows —
    ineligible means: some ancestor is a Room born locked."""
    rows = _born_rows(seed)
    locked_room_paths = [path for path, _n, level, props, _b in rows
                         if level == "Room" and json.loads(props).get("locked")]
    particles, ineligible = [], []
    for path, name, level, _props, _b in rows:
        if level != "SubatomicParticle":
            continue
        particles.append(name)
        if any(path.startswith(rp + ".") for rp in locked_room_paths):
            ineligible.append(name)
    return particles, ineligible


# ── Selection ───────────────────────────────────────────────────────────────


class TestHingeSelection:
    def test_fresh_installs_of_one_seed_agree_on_the_hinge(self, tmp_path, monkeypatch):
        # The determinism contract: the hinge is a pure function of
        # (seed, world as born) — two installs that birthed the same seed
        # select the same particle, with no entropy or clock in the choice.
        names = []
        for install in ("first", "second"):
            db_dir = tmp_path / install
            db_dir.mkdir()
            monkeypatch.setattr(persistence, "_DB_PATH", db_dir / "worlds.db")
            persistence._initialized.discard(db_dir / "worlds.db")
            names.append(wrap.hinge_name(SEED))
        assert names[0] == names[1]

    def test_the_launch_hinge_is_a_worthy_monument(self):
        # Seed 382's hinge, as the tuned selector chooses it. The exact
        # name is pinned deliberately: in production this selection runs
        # once and becomes permanent world identity, so a drifted selector
        # must fail HERE, before launch, not after the pin.
        assert wrap.hinge_name(SEED) == LAUNCH_HINGE
        hinge = store.resolve_node_by_name(SEED, LAUNCH_HINGE)
        assert hinge is not None and hinge.level == "SubatomicParticle"
        # Its born character carries the loop's own physics.
        assert hinge.properties["spin"] == "superposed"
        assert hinge.properties["tendency"] == "entangled"
        assert hinge.properties["coherence"] >= 0.95

    def test_liveness_census_on_the_launch_world(self):
        # The owner-measured numbers from the PR #76 review, reproduced
        # from the born rows: near coin-flip odds of a dead loop had the
        # lineage constraint been skipped.
        particles, ineligible = _particle_census(SEED)
        assert len(particles) == 1505
        assert len(ineligible) == 706
        assert len(particles) - len(ineligible) == 799
        assert wrap.hinge_name(SEED) not in ineligible

    def test_hinge_lineage_is_fully_unsealed_for_a_root_side_traveler(self):
        # The liveness invariant, at the gate that enforces seals: a
        # traveler standing at the root — outside every seal in the world
        # — can cross to the hinge on a fresh world.
        hinge = store.resolve_node_by_name(SEED, wrap.hinge_name(SEED))
        assert sealing_room(hinge) is None
        assert seal_check(SEED, hinge, current_name=store.root_name(SEED)) is None

    def test_a_sealed_lineage_never_wins_however_worthy(self):
        # Every ineligible particle loses to the chosen hinge even if its
        # raw worthiness is higher — the constraint is a filter, not a
        # weight.
        _particles, ineligible = _particle_census(SEED)
        assert wrap.hinge_name(SEED) not in ineligible
        rows = _born_rows(SEED)
        by_name = {name: json.loads(props) for _p, name, level, props, _b in rows
                   if level == "SubatomicParticle"}
        hinge_score = wrap._worthiness(by_name[wrap.hinge_name(SEED)])
        eligible_scores = [wrap._worthiness(p) for n, p in by_name.items()
                           if n not in set(ineligible)]
        assert hinge_score == max(eligible_scores)


# ── The pin ─────────────────────────────────────────────────────────────────


class TestHingePin:
    def test_first_ask_pins_into_world_meta(self):
        name = wrap.hinge_name(SEED)
        assert persistence.get_world_meta(SEED, wrap.HINGE_META_KEY) == name

    def test_pin_refuses_overwrite(self):
        first = wrap.hinge_name(SEED)
        survived = persistence.pin_world_meta(
            SEED, wrap.HINGE_META_KEY, "Usurper Quark-11111111111")
        assert survived == first
        assert persistence.get_world_meta(SEED, wrap.HINGE_META_KEY) == first

    def test_concurrent_first_askers_converge_on_one_hinge(self):
        store.ensure_born(SEED)
        barrier = threading.Barrier(8)
        results: list[str] = []

        def ask():
            barrier.wait()
            results.append(wrap.hinge_name(SEED))

        threads = [threading.Thread(target=ask) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(results) == 8
        assert len(set(results)) == 1


class TestSelectorEditImmunity:
    """The wrap's mirror of the store's TestBankEditImmunity: permanent
    world identity must not depend on mutable code. Once a world's hinge
    is pinned, editing the selection rule changes what FUTURE worlds pin —
    never where an existing world's monument stands."""

    def test_selector_edit_cannot_move_a_pinned_hinge(self, monkeypatch):
        pinned = wrap.hinge_name(SEED)
        monkeypatch.setattr(wrap, "_select_hinge",
                            lambda seed: "Edited Selector Quark-12111111111")
        assert wrap.hinge_name(SEED) == pinned

    def test_selector_is_consulted_only_at_pin_time(self):
        # A dedicated MonkeyPatch instance: the function-scoped fixture is
        # SHARED with conftest's DB isolation, so .undo() on it would point
        # persistence back at the real home DB (the batch-1 harness trap).
        patch = pytest.MonkeyPatch()
        try:
            # An unpinned world takes whatever the current selector says…
            patch.setattr(wrap, "_select_hinge",
                          lambda seed: "First Pin Quark-13111111111")
            assert wrap.hinge_name(7001) == "First Pin Quark-13111111111"
        finally:
            patch.undo()
        # …and keeps it after the selector changes back: the pin, not the
        # code, is the identity.
        assert wrap.hinge_name(7001) == "First Pin Quark-13111111111"


# ── The loop over the wire (browser surface) ───────────────────────────────


class TestLoopOverTheWire:
    def test_world_response_carries_the_wrap_block(self, srv):
        with urllib.request.urlopen(
                f"http://127.0.0.1:{srv}/world?seed={SEED}&depth=4") as resp:
            data = json.loads(resp.read())
        assert data["wrap"]["root"] == data["world"]["name"]
        assert data["wrap"]["hinge"] == wrap.hinge_name(SEED)
        # The authored surfaces ride with the world so every client
        # speaks the same fiction at the crossing.
        assert data["wrap"]["descent_line"] == wrap.DESCENT_LINE
        assert data["wrap"]["ascent_line"] == wrap.ASCENT_LINE
        assert data["wrap"]["descent_passage"] == wrap.DESCENT_PASSAGE
        assert data["wrap"]["ascent_passage"] == wrap.ASCENT_PASSAGE

    def test_ws_loop_crosses_both_directions_through_the_gate(self, srv):
        hinge = wrap.hinge_name(SEED)
        root_name = store.root_name(SEED)
        s, status = _ws_connect(srv, SEED, "Pilgrim")
        assert b"101" in status
        # Ascend beyond the root: land at the hinge (liveness holds).
        _ws_send_json(s, {"type": "move", "node": hinge})
        moves = _wait_for_rows(SEED, hinge, "PLAYER_MOVE")
        assert moves and moves[0]["player"] == "Pilgrim"
        # Descend below the particle: surface at the root.
        _ws_send_json(s, {"type": "move", "node": root_name})
        moves = _wait_for_rows(SEED, root_name, "PLAYER_MOVE")
        assert moves and moves[0]["player"] == "Pilgrim"
        s.close()

    def test_the_wrap_is_not_a_wormhole_past_a_seal(self, srv):
        # A root-side traveler may cross only to the hinge's unsealed
        # lineage; a particle beneath a locked Room stays sealed to them —
        # the loop must not become a way around any door.
        rows = _born_rows(SEED)
        locked_paths = [p for p, _n, level, props, _b in rows
                        if level == "Room" and json.loads(props).get("locked")]
        sealed_particle = next(
            name for path, name, level, _props, _b in rows
            if level == "SubatomicParticle"
            and any(path.startswith(lp + ".") for lp in locked_paths))
        s, _ = _ws_connect(srv, SEED, "Trespasser")
        _ws_send_json(s, {"type": "move", "node": sealed_particle})
        frames = _recv_frames(
            s, lambda fs: any(f.get("type") == "move_denied" for f in fs))
        denied = [f for f in frames if f.get("type") == "move_denied"]
        assert denied and denied[0]["reason"] == "sealed"
        s.close()


# ── The loop in the terminal (CLI surface) ─────────────────────────────────


class TestCliLoop:
    def _fresh_session_stack(self, depth=6):
        import interface
        interface._session_crossings.clear()
        root = store.world_tree(seed=SEED, max_depth=depth)
        return [root]

    def test_up_at_the_root_lands_at_the_hinge(self, capsys):
        from interface import _wrap_ascend
        stack = self._fresh_session_stack(depth=6)
        _wrap_ascend(stack, SEED)
        out = capsys.readouterr().out
        assert stack[-1].name == wrap.hinge_name(SEED)
        # The stack is the hinge's true ancestry: repeated ascent cycles
        # through its ancestor chain (ADR-008's honest topology claim),
        # even though the session opened at a depth-6 view.
        assert len(stack) == 11
        assert stack[0].level == "Multiverse"
        assert wrap.ASCENT_LINE in out

    def test_descend_below_the_particle_surfaces_at_the_root(self, capsys):
        from interface import _descend, _wrap_ascend
        stack = self._fresh_session_stack()
        _wrap_ascend(stack, SEED)
        capsys.readouterr()
        _descend(stack, 1, SEED)
        out = capsys.readouterr().out
        assert len(stack) == 1
        assert stack[0].level == "Multiverse"
        assert wrap.DESCENT_LINE in out

    def test_cli_crossings_enter_the_chronicle(self, capsys):
        # A crossing is a move like any other in the chronicle (ADR-008):
        # a main.py play crossing leaves the same permanent PLAYER_MOVE
        # trace a browser crossing does — at the landing, attributed.
        from interface import _descend, _wrap_ascend
        stack = self._fresh_session_stack()
        _wrap_ascend(stack, SEED, player_name="Pilgrim")
        hinge = wrap.hinge_name(SEED)
        moves = [h for h in persistence.get_node_history(SEED, hinge)
                 if h["type"] == "PLAYER_MOVE"]
        assert moves and moves[0]["player"] == "Pilgrim"
        _descend(stack, 1, SEED, player_name="Pilgrim")
        root_name = store.root_name(SEED)
        moves = [h for h in persistence.get_node_history(SEED, root_name)
                 if h["type"] == "PLAYER_MOVE"]
        assert moves and moves[0]["player"] == "Pilgrim"

    def test_the_authored_line_speaks_once_per_session(self, capsys):
        from interface import _descend, _wrap_ascend
        stack = self._fresh_session_stack()
        _wrap_ascend(stack, SEED)
        _descend(stack, 1, SEED)   # first descent — the line
        _wrap_ascend(stack, SEED)  # (ascent already spoken above)
        capsys.readouterr()
        _descend(stack, 1, SEED)   # second descent — a way you know
        out = capsys.readouterr().out
        assert wrap.DESCENT_LINE not in out
        assert wrap.ASCENT_LINE not in out

    def test_the_cli_wrap_routes_through_the_seal_gate(self, capsys):
        # The gate is consulted on every crossing — were a hinge lineage
        # ever sealed (impossible today by the liveness invariant, but the
        # routing must not depend on that), the threshold holds. Dedicated
        # MonkeyPatch instances: .undo() on the shared fixture would also
        # undo conftest's DB isolation (the batch-1 harness trap).
        import puzzles.gates as gates
        from interface import _descend, _wrap_ascend
        sealed = pytest.MonkeyPatch()
        sealed.setattr(
            gates, "seal_check",
            lambda seed, target, current_name=None: {
                "sealed_by": "x", "keeper": "y",
                "puzzle": "z", "prompt": "the way asks its question"})
        try:
            stack = self._fresh_session_stack()
            _wrap_ascend(stack, SEED)
            assert len(stack) == 1  # the threshold held: no crossing
            assert "sealed" in capsys.readouterr().out
            # A refused crossing leaves no trace in the chronicle.
            assert not [h for h in persistence.get_node_history(
                            SEED, wrap.hinge_name(SEED))
                        if h["type"] == "PLAYER_MOVE"]
        finally:
            sealed.undo()

        # And inward: a full-lineage stack stays where it is.
        stack = self._fresh_session_stack()
        _wrap_ascend(stack, SEED)
        sealed = pytest.MonkeyPatch()
        sealed.setattr(
            gates, "seal_check",
            lambda seed, target, current_name=None: {"sealed_by": "x"})
        try:
            before = list(stack)
            _descend(stack, 1, SEED)
            assert stack == before
        finally:
            sealed.undo()

    def test_look_offers_the_passage_at_both_ends(self, capsys):
        from interface import _print_look
        hinge = store.resolve_node_by_name(SEED, wrap.hinge_name(SEED))
        _print_look(hinge)
        out = capsys.readouterr().out
        assert wrap.DESCENT_PASSAGE in out
        assert "no deeper paths" not in out
        root = store.world_tree(seed=SEED, max_depth=1)
        _print_look(root)
        assert wrap.ASCENT_PASSAGE in capsys.readouterr().out

    def test_middle_scale_leaves_are_not_offered_the_wrap(self, capsys):
        # A depth-limited view's horizon (a Region with its children
        # beyond the view) is a view boundary, not the loop.
        from interface import _print_look
        root = store.world_tree(seed=SEED, max_depth=6)
        leaf = root
        while leaf.children:
            leaf = leaf.children[0]
        assert leaf.level != "SubatomicParticle"
        _print_look(leaf)
        out = capsys.readouterr().out
        assert wrap.DESCENT_PASSAGE not in out
        assert "no deeper paths" in out


# ── The hinge knows what it is ─────────────────────────────────────────────


@pytest.fixture
def captured_speak_call():
    """consciousness._get_client stub capturing .messages.create kwargs."""
    from unittest.mock import MagicMock
    captured: dict = {}

    class _FakeMessages:
        def create(self, **kwargs):
            captured.update(kwargs)
            response = MagicMock()
            response.content = [MagicMock(type="text", text="ok")]
            return response

    fake_client = MagicMock()
    fake_client.messages = _FakeMessages()
    original = consciousness._client
    consciousness._client = fake_client
    try:
        yield captured
    finally:
        consciousness._client = original


class TestHingeLore:
    def test_hinge_voice_carries_the_lore(self, captured_speak_call):
        node = SpatialNode(name="Hidden Thorn Quark-11431112111",
                           level="SubatomicParticle",
                           properties={"spin": "superposed"})
        consciousness.speak(node, "What is this place?", hinge=True)
        dynamic = captured_speak_call["system"][1]["text"]
        assert "hinge" in dynamic
        assert "enfolds the whole" in dynamic

    def test_ordinary_particles_know_nothing_of_it(self, captured_speak_call):
        node = SpatialNode(name="Plain Quark-12111111111",
                           level="SubatomicParticle", properties={})
        consciousness.speak(node, "What is this place?")
        assert "hinge" not in captured_speak_call["system"][1]["text"]

    def test_speak_endpoint_tells_the_hinge_it_is_the_hinge(self, srv, monkeypatch):
        seen = {}

        def fake_speak(node, message, history=None, transcript=None,
                       ripple_score=0.0, speaker=None, hinge=False):
            seen[node.name] = hinge
            return "spoken"

        monkeypatch.setattr(consciousness, "speak", fake_speak)
        hinge = wrap.hinge_name(SEED)
        root_name = store.root_name(SEED)
        for target in (hinge, root_name):
            body = json.dumps({"node_name": target, "seed": SEED,
                               "message": "who are you?"}).encode()
            req = urllib.request.Request(
                f"http://127.0.0.1:{srv}/speak", data=body,
                headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req).read()
        assert seen[hinge] is True
        assert seen[root_name] is False

    def test_standalone_speak_command_knows_the_hinge(self, monkeypatch):
        # Every surface that speaks for a node passes the hinge flag —
        # including the documented standalone `main.py speak` path.
        import main
        seen = {}

        def fake_speak(node, message, history=None, transcript=None,
                       ripple_score=0.0, speaker=None, hinge=False):
            seen[node.name] = hinge
            return "spoken"

        monkeypatch.setattr(consciousness, "speak", fake_speak)
        hinge = wrap.hinge_name(SEED)
        root_name = store.root_name(SEED)
        for target in (hinge, root_name):
            args = type("Args", (), {"seed": SEED, "node": target,
                                     "message": "who are you?"})()
            main.cmd_speak(args)
        assert seen[hinge] is True
        assert seen[root_name] is False


# ── Containment stays a tree ───────────────────────────────────────────────


class TestContainmentUntouched:
    def test_no_parent_link_expresses_the_loop(self):
        # The loop lives in the traversal layer only: the root has no
        # parent, the hinge has no children, and every ancestor walk
        # terminates — the finite-chain assumption every lineage walker
        # relies on (law_for, sealing_room, __repr__) still holds.
        root = store.world_tree(seed=SEED, max_depth=11)
        assert root.parent is None
        hinge = store.resolve_node_by_name(SEED, wrap.hinge_name(SEED))
        assert hinge.children == []
        steps = 0
        cursor = hinge
        while cursor.parent is not None:
            cursor = cursor.parent
            steps += 1
            assert steps <= 11, "ancestor chain must stay finite"
        assert cursor.level == "Multiverse"
