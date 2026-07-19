"""Golden-master freeze — RE-SCOPED by ADR-006 (Option A, 2026-07-19):
these pins now describe what generator v1 BIRTHS, not the permanent world.

The world is materialized (`multiverse/store.py`, `world_nodes`): the
generator runs once per seed as a birthing tool, born rows are the node's
identity, and a bank edit can no longer touch any world that already
exists (pinned by tests/test_world_store.py::TestBankEditImmunity). What
these digests guard since the pivot: (1) a fresh install birthing a
reference seed must reproduce it exactly — production's launch world is
born from these banks, so until that birth happens, and for every new
seed after it, drift here is still drift worth catching; (2) a meaningful
generator change must be CONSCIOUS — bump GENERATOR_VERSION
(multiverse/store.py), re-pin deliberately, record why in the CHANGELOG.
A failing pin means "you changed what new worlds are born as," not "you
are rewriting the permanent world." The era-name pins are the exception:
era names are still recomputed from display banks at read time, so their
banks remain genuinely frozen until eras are materialized (ADR-006).

The original stakes, kept for history (they describe the pre-pivot world
where the banks WERE the storage medium):

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
# re-pinned 2026-07-06 for the world reshape (level-shaped BREADTH_BY_LEVEL
# replacing uniform 1-3 — the surviving paths kept byte-identical names and
# properties; the root, first universe, every first-child-chain landmark,
# and the root aspect are unchanged).
_REF_SEED = 42
_REF_NODE_COUNT = 293
_REF_NAMES_DIGEST = (
    "f6044332ea2055ce7b27a177d7793179a7374fe946fdad42c39e70017df29af4"
)
_REF_WORLD_DIGEST = (
    "1e514afa5464483212310a11ea6f4f3d6195f3841a8945da49376f7698f2a930"
)

# The world's shape itself: one rng.randint draw per node over these exact
# ranges. Changing any range after first production deploy deletes and
# spawns subtrees in every existing world — same failure class as a bank
# edit, pinned the same way.
_REF_BREADTH_PROFILE = {
    "Multiverse":        (3, 4),
    "Universe":          (3, 4),
    "Galaxy":            (2, 3),
    "Planetary System":  (2, 2),
    "Planet":            (2, 2),
    "Region":            (2, 2),
    "Room":              (1, 2),
    "Object":            (1, 2),
    "Molecule":          (1, 2),
    "Atom":              (1, 2),
    "SubatomicParticle": (1, 2),
}

# The FULL-depth reference world: all 11 levels, the tree the server
# actually serves. The depth-6 pins alone are blind to five levels — Rooms,
# Objects, Molecules, Atoms, SubatomicParticles — whose property banks
# could then be edited with every freeze test green (measured: +1 material
# at the Object level passes all depth-6 pins while deleting 38 full-depth
# nodes and silently changing 19 surviving nodes' property baselines).
# These pins close that blind spot. Pinned 2026-07-05, pre-launch.
_REF_FULL_DEPTH = 11
_REF_FULL_NODE_COUNT = 4439
_REF_FULL_NAMES_DIGEST = (
    "06d672c624f88f6df41fa2ad1dd3e6d68736f5ec0e52ac2036cb4014598257e5"
)
_REF_FULL_WORLD_DIGEST = (
    "b02c167b0d2280f558e69fa60e0400d9ff3d42b8054519a061d2bd753990c414"
)
_REF_FULL_PUZZLES_DIGEST = (
    "32b922f74bcab9b4bba7eb10e7c80962eeeeec20e9502a3d82436bc909ba3bc4"
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
        assert names[10] == "Caloeth-1112"
        assert names[-1] == "Rustmarsh Fens-144322"

    def test_breadth_profile_is_pinned(self):
        from multiverse.generator import BREADTH_BY_LEVEL
        assert BREADTH_BY_LEVEL == _REF_BREADTH_PROFILE, (
            "The world's breadth profile changed. Breadth draws shape which "
            "paths exist: post-launch this deletes and spawns subtrees in "
            "every existing world. Revert (or consciously re-pin pre-launch "
            "only)."
        )

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
        assert nodes[-1].name == "Moramarette-14432222222"


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
            "79518fa8321a421b990008a4384a1ffe044d28af236a6993a2278eeacc30362a"
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


class TestRenewalEpochPuzzlesArePinned:
    def test_epoch_one_and_two_puzzles_are_pinned(self):
        # Solved-state rehydration keys on the puzzle NAME *including* the
        # "· Renewal N" suffix, so renewal-epoch generation is durable-history
        # surface exactly like epoch 0 — an edit to the epoch>0 RNG branch or
        # to any family generator would rename renewed nodes' puzzles and
        # silently reset their solved state while the epoch-0 pin stayed
        # green (the gap the 2026-07-18 evaluation found). Same protocol as
        # the epoch-0 pin: a failure here means stop, revert, or re-pin
        # consciously pre-launch only.
        from puzzles.engine import build_puzzle
        nodes = _walk(generate_node_hierarchy(seed=_REF_SEED, max_depth=6), [])
        pinned = {
            1: "dcda8be3c59211403eff5afddc15fabe1a9d7ac53991efbce776304b28362cf9",
            2: "a71072e573b6d0ac4ea982b7155fa3ed9715d0bf53e6cd88f2c6248a8c0fdeaa",
        }
        for epoch, expected in pinned.items():
            blob = "\n".join(
                f"{n.name}|{build_puzzle(n, epoch=epoch).name}"
                f"|{build_puzzle(n, epoch=epoch).answer}"
                for n in nodes)
            digest = hashlib.sha256(blob.encode()).hexdigest()
            assert digest == expected, (
                f"Renewal-epoch {epoch} puzzle generation changed for the "
                "reference world. Post-launch this resets every RENEWED "
                "solved puzzle. Revert, or re-pin consciously before first "
                "production deploy only."
            )


class TestVerbOverlayKeysAreFrozen:
    def test_overlay_property_keys_are_pinned(self):
        # Verb effects persist as property-overlay deltas keyed by these
        # names; renaming one ("warded" → "guarded") strands every existing
        # overlay row written under the old key. Behavior pin: run each
        # verb against a node crafted to trigger every branch and pin the
        # exact key set it may write.
        from multiverse.node import SpatialNode
        from multiverse.verbs import VERBS, apply_verb

        trigger_props = {
            "attune":    {"stability": "collapsing"},
            "calibrate": {"dark_matter_ratio": 0.3},
            "kindle":    {"star_density": 100},
            "align":     {"ecliptic_tilt_deg": 10.0},
            "seed":      {},
            "ward":      {"danger_level": 5},
            "inscribe":  {},
            "mend":      {"condition": "damaged", "fractured": True},
            "catalyze":  {"bond_count": 3},
            "excite":    {"resonance_nm": 500.0},
            "observe":   {"spin": "superposed", "coherence": 0.5},
        }
        pinned_keys = {
            "attune":    {"stability", "attuned"},
            "calibrate": {"dark_matter_ratio", "calibrated"},
            "kindle":    {"star_density", "kindled"},
            "align":     {"ecliptic_tilt_deg", "aligned"},
            "seed":      {"inhabited", "population", "seeded"},
            "ward":      {"danger_level", "warded"},
            "inscribe":  {"inscriptions"},
            "mend":      {"condition", "fractured"},
            "catalyze":  {"bond_count", "catalyzed"},
            "excite":    {"resonance_nm", "ionized"},
            "observe":   {"spin", "coherence", "observed"},
        }
        for level, verb in VERBS.items():
            node = SpatialNode(name=f"Pin-{level}", level=level,
                               properties=dict(trigger_props[verb.name]))
            changed, _flavor = apply_verb(node, verb, token="freeze-pin")
            assert changed is not None, f"{verb.name} produced no delta"
            assert set(changed) == pinned_keys[verb.name], (
                f"Verb {verb.name!r} writes overlay keys {set(changed)} — "
                f"pinned {pinned_keys[verb.name]}. Renaming an overlay key "
                "post-launch strands every existing overlay row written "
                "under the old name. Revert, or re-pin consciously "
                "pre-launch only."
            )
