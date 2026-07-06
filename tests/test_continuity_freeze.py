"""Golden-master freeze: the generated world is a permanent compatibility
surface.

Node names key ALL durable history — world_mutations, saved positions,
property overlays, ripple scores, the art's activity counts. Each node
draws name → properties → breadth from its own (seed, path)-keyed RNG
stream over the content banks in multiverse/generator.py, so a bank edit
corrupts existing worlds two ways. Name-bank edits rename surviving nodes
outright (measured on seed 42: +1 syllable in _SYL_ROOTS renames 77 of 83
reference nodes). Property-bank edits reshuffle the property VALUES of
every node at that level — the baselines the persisted overlay applies its
deltas to — and can shift breadth draws via choice()'s rejection sampling,
deleting and spawning whole subtrees (measured: +1 biome replaces 2 of 83
names at depth 6, ~170 of 3017 across the full world). After the first
production deploy either failure orphans chronicle history and breaks
saved positions.

Era names are worse: they are recomputed from the banks at READ time, so a
bank edit retroactively rewrites the displayed history of every era that
has already happened.

These tests pin exact outputs at TWO depths: the depth-6 reference world
(the default the clients load — small, human-diagnosable canaries) and the
full 11-level world the server actually serves. Both are required: five
levels (Room and deeper) exist only below depth 6, so their property banks
are invisible to the shallow pins. If a pin fails, you are about to
rewrite the permanent world — stop, and either revert the change or
(pre-launch only) consciously re-pin the values. Post-launch there is no
re-pinning; the banks are frozen.

The pins also police the Python RNG contract: worlds must generate
identically under the pinned interpreter (Dockerfile and CI both pin 3.11).
"""
from __future__ import annotations

import hashlib
import json

from multiverse.chronicle import era_name
from multiverse.generator import generate_node_hierarchy
from multiverse.node import SpatialNode


def _walk(node: SpatialNode, out: list) -> list:
    out.append(node)
    for child in node.children:
        _walk(child, out)
    return out


# The canonical reference world: default seed, depth 6 (the default the
# clients load). Pinned 2026-07-05, before first production deploy;
# world + puzzle digests re-pinned same day for the diversity batch (bank
# widening + LOCK puzzles — names, landmarks, aspect, eras all unchanged).
_REF_SEED = 42
_REF_NODE_COUNT = 83
_REF_NAMES_DIGEST = (
    "39d3c52794e496e3c6bdfdf992e84c2184e747b6880d8675a39a51da010e7d44"
)
_REF_WORLD_DIGEST = (
    "25983bdc04a76ce61020dbd5e5f52b3a978314528ce09010583999269bdf0cb1"
)

# The FULL-depth reference world: all 11 levels, the tree the server
# actually serves. The depth-6 pins alone are blind to five levels — Rooms,
# Objects, Molecules, Atoms, SubatomicParticles — whose property banks
# could then be edited with every freeze test green (measured: +1 material
# at the Object level passes all depth-6 pins while deleting 38 full-depth
# nodes and silently changing 19 surviving nodes' property baselines).
# These pins close that blind spot. Pinned 2026-07-05, pre-launch.
_REF_FULL_DEPTH = 11
_REF_FULL_NODE_COUNT = 3017
_REF_FULL_NAMES_DIGEST = (
    "7e669d5cc95378078cdb54d0f695678382a4cd85bc447711b2a086d4caf20098"
)
_REF_FULL_WORLD_DIGEST = (
    "7f5a10ff2ce5047c531d82eaa67fefbea65933868d3fbeb9d0b74d14b21506ac"
)
_REF_FULL_PUZZLES_DIGEST = (
    "775c90406b00910f88f0c6482493a8b26ee2c07a98e9698044d9366a0475440f"
)


class TestGeneratedWorldIsFrozen:
    def _nodes(self):
        return _walk(generate_node_hierarchy(seed=_REF_SEED, max_depth=6), [])

    def test_names_digest_is_pinned(self):
        names = [n.name for n in self._nodes()]
        assert len(names) == _REF_NODE_COUNT
        digest = hashlib.sha256("\n".join(names).encode()).hexdigest()
        assert digest == _REF_NAMES_DIGEST, (
            "Node names for the reference world changed. Names key ALL "
            "durable history — this change would orphan every existing "
            "world's chronicle and saved positions. Revert it (or, before "
            "first production deploy ONLY, consciously re-pin)."
        )

    def test_full_world_digest_is_pinned(self):
        # Names AND properties: the overlay persists deltas against these
        # generated baselines, so silently different baselines corrupt the
        # world state every participant sees.
        nodes = self._nodes()
        full = "\n".join(
            f"{n.name}|{json.dumps(n.properties, sort_keys=True)}"
            for n in nodes
        )
        digest = hashlib.sha256(full.encode()).hexdigest()
        assert digest == _REF_WORLD_DIGEST, (
            "Generated properties for the reference world changed. The "
            "persisted property overlay applies deltas on top of these "
            "baselines — changing them rewrites the world under every "
            "existing player. Revert (or consciously re-pin pre-launch)."
        )

    def test_landmark_names_are_pinned(self):
        # Human-readable canaries so a digest failure is diagnosable.
        names = [n.name for n in self._nodes()]
        assert names[0] == "Fenolos-1"
        assert names[1] == "Solaorne-11"
        assert names[10] == "Frostlight Shallows-111123"
        assert names[-1] == "Loamcrest Fens-132211"

    def test_root_aspect_is_pinned(self):
        root = self._nodes()[0]
        assert root.properties["aspect"] == (
            "its edges are stitched with ash; a slow tide moves under its "
            "surface, and it wears its age like a medal."
        )


class TestFullDepthWorldIsFrozen:
    """Every level, not just the shallow six. Deep-level property banks
    (rooms' air, objects' materials, molecules' geometries…) exist only
    below depth 6, so only these pins can catch an edit to them."""

    def _nodes(self):
        return _walk(generate_node_hierarchy(seed=_REF_SEED,
                                             max_depth=_REF_FULL_DEPTH), [])

    def test_full_depth_names_digest_is_pinned(self):
        names = [n.name for n in self._nodes()]
        assert len(names) == _REF_FULL_NODE_COUNT
        digest = hashlib.sha256("\n".join(names).encode()).hexdigest()
        assert digest == _REF_FULL_NAMES_DIGEST, (
            "Full-depth node names changed while the depth-6 canaries may "
            "still be green — a deep-level bank edit deleting or spawning "
            "subtrees. Names key all durable history. Revert (or "
            "consciously re-pin pre-launch only)."
        )

    def test_full_depth_world_digest_is_pinned(self):
        nodes = self._nodes()
        full = "\n".join(
            f"{n.name}|{json.dumps(n.properties, sort_keys=True)}"
            for n in nodes
        )
        digest = hashlib.sha256(full.encode()).hexdigest()
        assert digest == _REF_FULL_WORLD_DIGEST, (
            "Full-depth generated properties changed — likely an edit to a "
            "deep-level property bank (Room/Object/Molecule/Atom/"
            "SubatomicParticle) that the depth-6 pins cannot see. The "
            "overlay applies deltas on top of these baselines. Revert (or "
            "consciously re-pin pre-launch only)."
        )

    def test_full_depth_puzzles_are_pinned(self):
        from puzzles.engine import build_puzzle
        blob = "\n".join(
            f"{n.name}|{(p := build_puzzle(n)).name}|{p.answer}"
            for n in self._nodes())
        digest = hashlib.sha256(blob.encode()).hexdigest()
        assert digest == _REF_FULL_PUZZLES_DIGEST, (
            "Epoch-0 puzzle generation changed somewhere below depth 6 — "
            "Rooms and deeper hold most of the world's puzzles (including "
            "every LOCK). Post-launch this resets solved state. Revert, or "
            "re-pin consciously before first production deploy only."
        )

    def test_deep_landmark_names_are_pinned(self):
        # One canary per unpinned level, so a digest failure is diagnosable.
        nodes = self._nodes()
        first_of = {}
        for n in nodes:
            first_of.setdefault(n.level, n.name)
        assert first_of["Room"] == "Deepvane Workshop-1111111"
        assert first_of["Object"] == "Haleisara Conduit-11111111"
        assert first_of["Molecule"] == "Ulauide-111111111"
        assert first_of["Atom"] == "Velanoride-1111111111"
        assert first_of["SubatomicParticle"] == "Veriunon-11111111111"
        assert nodes[-1].name == "Galysule-13221131322"


class TestPuzzleLayerIsFrozen:
    def test_epoch_zero_puzzles_are_pinned(self):
        # Solved-state rehydration keys on (node, puzzle NAME): changing
        # epoch-0 puzzle generation after launch would silently reset every
        # solved puzzle in the world. Renewal epochs (>0) are deliberately
        # dynamic; epoch 0 is the frozen baseline.
        from puzzles.engine import build_puzzle
        nodes = _walk(generate_node_hierarchy(seed=_REF_SEED, max_depth=6), [])
        blob = "\n".join(
            f"{n.name}|{build_puzzle(n).name}|{build_puzzle(n).answer}"
            for n in nodes)
        digest = hashlib.sha256(blob.encode()).hexdigest()
        assert digest == (
            "fcd1cba980facd6f75088a300fc47772597efceafca0beb83ec2b7f2c55fdf79"
        ), (
            "Epoch-0 puzzle generation changed for the reference world. "
            "Post-launch this resets every solved puzzle. Revert, or "
            "re-pin consciously before first production deploy only."
        )


class TestEraNamesAreFrozen:
    def test_exact_era_names_are_pinned(self):
        # Era names are derived at READ time — a bank edit rewrites the
        # displayed history of eras that already happened. Exact pins.
        assert era_name(42, "2026-07-05 00:00:00") == "The Passage of the Unwarded Door"
        assert era_name(42, "2026-01-01 00:00:00") == "The Chorus of Emberglass"
        assert era_name(42, "2027-03-14 00:00:00") == "The Kindling of Saltfall"
        assert era_name(7, "2026-07-05 00:00:00") == "The Turning of the Ninth Ring"


class TestIdentitySchemeIsFrozen:
    def test_credential_identity_hash_is_pinned(self):
        # The durable conversation/attribution identity: sha256 of the raw
        # invite key, first 16 hex chars. Also the cost ledger's per-user
        # bucket suffix. Changing the scheme orphans every transcript and
        # attribution row keyed on it.
        assert hashlib.sha256("nw_testkey".encode()).hexdigest()[:16] == \
            "c2db0327dc788cc9"
