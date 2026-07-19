"""The materialized world (ADR-006 Option A): the store IS the world.

Three contracts pinned here, in order of importance:

1. **Bank-edit immunity** — the covenant that replaced the launch freeze.
   Once a world is born, editing a content bank changes NOTHING about it:
   not a name, not a property, not a resolution. Banks govern only the
   birth of not-yet-born worlds. This is the test that made the freeze
   obsolete; if it ever fails, the world's identity has come unmoored
   from its storage and history is at risk.

2. **Birth equivalence** — at birth, the store serves exactly what the
   generator generated: same names, levels, properties, and child order,
   at every depth view, and resolution refuses exactly the forgeries the
   generator's resolver refused.

3. **Birth discipline** — births are idempotent (a born world is never
   re-born) and lazy (first visit births).
"""
from __future__ import annotations

import pytest

import persistence
from multiverse import store
from multiverse.generator import (
    generate_node_hierarchy, resolve_node_by_name,
)

SEED = 4242  # not the canonical 42: keep these worlds test-local


def _assert_same_tree(gen, stored):
    assert gen.name == stored.name
    assert gen.level == stored.level
    assert gen.properties == stored.properties
    assert len(gen.children) == len(stored.children)
    for g, s in zip(gen.children, stored.children):
        _assert_same_tree(g, s)


def _sample_names(root, per_level=1):
    """One node name per level, walking first-child chains and siblings."""
    names, seen = [], set()
    def walk(n):
        if n.level not in seen:
            seen.add(n.level)
            names.append(n.name)
        for c in n.children:
            walk(c)
    walk(root)
    return names


class TestBirthEquivalence:
    def test_stored_world_equals_generated_world_at_both_depths(self):
        for depth in (6, 11):
            _assert_same_tree(
                generate_node_hierarchy(seed=SEED, max_depth=depth),
                store.world_tree(seed=SEED, max_depth=depth),
            )

    def test_depth_view_is_a_true_prefix_of_the_full_world(self):
        shallow = store.world_tree(seed=SEED, max_depth=4)
        full = store.world_tree(seed=SEED, max_depth=11)
        def prefix_check(s, f):
            assert (s.name, s.level, s.properties) == (f.name, f.level, f.properties)
            assert len(s.children) <= len(f.children) or not s.children
            for sc, fc in zip(s.children, f.children):
                prefix_check(sc, fc)
        prefix_check(shallow, full)

    def test_depth_validation_matches_generator(self):
        with pytest.raises(ValueError):
            store.world_tree(seed=SEED, max_depth=0)
        with pytest.raises(ValueError):
            store.world_tree(seed=SEED, max_depth=12)

    def test_root_name(self):
        assert store.root_name(SEED) == generate_node_hierarchy(
            seed=SEED, max_depth=1).name


class TestResolutionParity:
    def test_resolves_every_level_with_ancestry(self):
        root = store.world_tree(seed=SEED, max_depth=11)
        for name in _sample_names(root):
            got = store.resolve_node_by_name(SEED, name)
            ref = resolve_node_by_name(SEED, name)
            assert got is not None and ref is not None
            assert got.name == ref.name == name
            assert got.level == ref.level
            assert got.properties == ref.properties
            assert got.children == []  # identity + ancestry, never structure
            # The ancestor chain matches, link for link.
            g, r = got, ref
            while r.parent is not None:
                assert g.parent is not None
                g, r = g.parent, r.parent
                assert g.name == r.name
            assert g.parent is None

    def test_refuses_the_same_forgeries_as_the_generator(self):
        root = store.world_tree(seed=SEED, max_depth=11)
        real = root.children[0].name           # a Universe, path "1.N"
        suffix = real.rpartition("-")[2]
        forged = [
            "Fake-11",                          # base not born at this path
            f"Nothing-{suffix}",                # ditto, real path
            real.rpartition("-")[0] + "-10",    # zero digit
            "NoSuffix",                         # no path at all
            real + "9",                         # step beyond born breadth
            "Deep-1" + "1" * 11,                # longer than the hierarchy
        ]
        for name in forged:
            assert store.resolve_node_by_name(SEED, name) is None, name
            assert resolve_node_by_name(SEED, name) is None, name


class TestBirthDiscipline:
    def test_first_visit_births_lazily(self):
        fresh = SEED + 1
        assert not persistence.world_is_born(fresh)
        store.world_tree(seed=fresh, max_depth=3)
        assert persistence.world_is_born(fresh)

    def test_birth_is_idempotent(self):
        first = store.birth_world(SEED + 2)
        assert first > 0
        assert store.birth_world(SEED + 2) == 0
        assert len(persistence.get_world_nodes(SEED + 2)) == first


class TestBankEditImmunity:
    """Editing a content bank must never touch a born world. This is the
    covenant that replaced the pre-launch freeze (ADR-006 Option A)."""

    def test_a_born_world_ignores_bank_edits(self, monkeypatch):
        import multiverse.generator as gen

        before = store.world_tree(seed=SEED, max_depth=6)
        sample = _sample_names(store.world_tree(seed=SEED, max_depth=11))

        # Sabotage the banks the way the freeze docstrings warn about —
        # PREPENDED so every index-based pick shifts and regeneration
        # would rename essentially every node...
        monkeypatch.setattr(gen, "_SYL_ROOTS", ["zzyx"] + gen._SYL_ROOTS)
        # ...and make sure the store's in-process birth cache can't mask
        # the edit — a re-birth attempt would now use the edited banks.
        store._birth_rows_cache.clear()

        # The born world is untouched: same tree, same resolutions.
        _assert_same_tree(before, store.world_tree(seed=SEED, max_depth=6))
        for name in sample:
            assert store.resolve_node_by_name(SEED, name) is not None, name

    def test_banks_govern_births_of_new_worlds(self, monkeypatch):
        import multiverse.generator as gen

        unborn = SEED + 3
        reference = generate_node_hierarchy(seed=unborn, max_depth=4)

        monkeypatch.setattr(gen, "_SYL_ROOTS", ["zzyx"] + gen._SYL_ROOTS)
        store._birth_rows_cache.clear()
        try:
            born_after_edit = store.world_tree(seed=unborn, max_depth=4)
            # A world born AFTER the edit expresses the edited banks —
            # generation still governs birth, and the +1-syllable shift
            # renames nodes exactly as the old freeze warnings measured.
            assert born_after_edit.name != reference.name or any(
                b.name != r.name for b, r in
                zip(born_after_edit.children, reference.children)
            )
        finally:
            store._birth_rows_cache.clear()  # never leak edited-bank rows
