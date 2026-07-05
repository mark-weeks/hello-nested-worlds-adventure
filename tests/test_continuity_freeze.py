"""Golden-master freeze: the generated world is a permanent compatibility
surface.

Node names key ALL durable history — world_mutations, saved positions,
property overlays, ripple scores, the art's activity counts. Names and
properties are drawn from one per-node RNG stream over the content banks in
multiverse/generator.py, so ANY edit to ANY bank (even appending one item)
reshuffles nearly every name in every existing world: measured on seed 42,
adding a single syllable to _SYL_ROOTS renames 77 of 83 nodes, and adding a
single biome renames 64 of 83. After the first production deploy that means
orphaning the entire chronicle and breaking every saved position.

Era names are worse: they are recomputed from the banks at READ time, so a
bank edit retroactively rewrites the displayed history of every era that
has already happened.

These tests pin exact outputs. If one fails, you are about to rewrite the
permanent world — stop, and either revert the change or (pre-launch only)
consciously re-pin the values. Post-launch there is no re-pinning; the
banks are frozen.

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
# clients load). Pinned 2026-07-05, before first production deploy.
_REF_SEED = 42
_REF_NODE_COUNT = 83
_REF_NAMES_DIGEST = (
    "39d3c52794e496e3c6bdfdf992e84c2184e747b6880d8675a39a51da010e7d44"
)
_REF_WORLD_DIGEST = (
    "7664d82fc3fffa7103abbfeed00504d195dad5b924a750b2d4bfb08e4b6e74fc"
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
