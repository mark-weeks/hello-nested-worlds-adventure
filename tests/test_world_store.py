"""The materialized world (ADR-006 Option A): the store IS the world.

Three contracts pinned here, in order of importance:

1. **Bank-edit immunity** — the covenant that replaced the launch freeze.
   Once a world is born, editing a content bank changes NOTHING about it:
   not a name, not a property, not a resolution. Banks govern only the
   birth of not-yet-born worlds. This is the test that made the freeze
   obsolete; if it ever fails, the world's identity has come unmoored
   from its storage and history is at risk.

2. **Birth equivalence** — at birth, the store serves exactly what the
   generator generated: same names, levels, properties, child order,
   addresses and keys, at every depth view; stored resolution returns that
   same identity and refuses names that were never born.

3. **Birth discipline** — births are idempotent (a born world is never
   re-born) and lazy (first visit births).

4. **Names, addresses and keys** (ADR-041) — a born name is three words and
   unique in its world; the path is the address; the key is the name joined
   to the address, except in a world born under generator version 2 or
   earlier, whose stored name already is its key.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3

import pytest

import persistence
from multiverse import naming, store
from multiverse.generator import generate_node_hierarchy

SEED = 4242  # not the canonical 42: keep these worlds test-local


def _assert_same_tree(gen, stored):
    assert gen.name == stored.name
    assert gen.level == stored.level
    assert gen.properties == stored.properties
    assert gen.address == stored.address and gen.address
    assert gen.key == stored.key and gen.key
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
        generated = generate_node_hierarchy(seed=SEED, max_depth=11)
        generated_by_name = {}

        def index(node):
            generated_by_name[node.name] = node
            for child in node.children:
                index(child)

        index(generated)
        for name in _sample_names(root):
            got = store.resolve_node_by_name(SEED, name)
            ref = generated_by_name[name]
            assert got is not None
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

    def test_refuses_names_that_were_never_born(self):
        root = store.world_tree(seed=SEED, max_depth=11)
        real = root.children[0]                # a Universe, address "1N"
        other_world = store.root_name(SEED + 7)
        assert other_world != root.name
        forged = [
            "Fake Name Here",                   # three words, never born
            f"{real.name}-{real.address}",      # the version-2 spelling
            real.key,                           # the key is not a name
            real.name + "9",
            real.name.lower(),
            real.name + " ",
            real.address,                       # an address is not a name
            "Deep-1" + "1" * 11,
            other_world,                        # born, but in another world
            "",
        ]
        for name in forged:
            assert store.resolve_node_by_name(SEED, name) is None, name
        assert store.resolve_node_by_name(SEED, None) is None
        assert store.address_of(SEED, "Fake Name Here") is None
        assert store.key_of(SEED, "Fake Name Here") is None


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
        changed_names = tuple(
            f"Changed{i}" for i, _ in enumerate(gen.NAME_QUALIFIERS)
        )
        monkeypatch.setattr(gen, "NAME_QUALIFIERS", changed_names)
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

        changed_names = tuple(
            f"Changed{i}" for i, _ in enumerate(gen.NAME_QUALIFIERS)
        )
        monkeypatch.setattr(gen, "NAME_QUALIFIERS", changed_names)
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


def _walk(root):
    out, stack = [], [(root, (1,))]
    while stack:
        node, path = stack.pop()
        out.append((node, path))
        for i, child in enumerate(node.children, start=1):
            stack.append((child, path + (i,)))
    return out


class TestNamesAddressesAndKeys:
    """ADR-041: the name is a label, the path is the address, and the key
    is the string a generator-version-2 world stored as the name."""

    @pytest.mark.parametrize("seed", [SEED, 382])
    @pytest.mark.parametrize("depth", [6, 11])
    def test_generated_names_are_three_words_and_unique(self, seed, depth):
        nodes = _walk(generate_node_hierarchy(seed=seed, max_depth=depth))
        names = [node.name for node, _ in nodes]
        assert len(set(names)) == len(names)
        for name in names:
            words = name.split(" ")
            assert len(words) == 3 and all(w.isalpha() for w in words), name
            assert "-" not in name
            assert naming.legacy_address(name) is None

    @pytest.mark.parametrize("depth", [6, 11])
    def test_generated_nodes_carry_address_and_key(self, depth):
        for node, path in _walk(generate_node_hierarchy(seed=SEED, max_depth=depth)):
            digits = "".join(str(i) for i in path)
            assert node.address == digits
            assert node.key == f"{node.name}-{digits}"
            assert naming.node_key(node) == node.key
            assert naming.node_address(node) == digits
            assert naming.node_path(node) == ".".join(str(i) for i in path)
            assert not naming.name_carries_address(node)

    def test_the_key_is_the_name_generator_version_2_stored(self):
        # Seed 382 at depth 6: the digest of every key, in walk order, is the
        # names digest the version-2 freeze pinned. No keyed input moved.
        nodes = []

        def walk(node):
            nodes.append(node)
            for child in node.children:
                walk(child)

        walk(generate_node_hierarchy(seed=382, max_depth=6))
        digest = hashlib.sha256(
            "\n".join(n.key for n in nodes).encode()).hexdigest()
        assert digest == (
            "f4599db11c7d63eee140752131ce773c042caa906fa5991f82be83b23cc429d9")

    def test_stored_nodes_carry_address_and_key(self):
        assert store.generator_version(SEED) == store.GENERATOR_VERSION == 3
        rows = {path: name for path, name, *_ in persistence.get_world_nodes(SEED)}
        for node, path in _walk(store.world_tree(seed=SEED, max_depth=11)):
            dotted = ".".join(str(i) for i in path)
            digits = dotted.replace(".", "")
            assert rows[dotted] == node.name
            assert node.address == digits
            assert node.key == f"{node.name}-{digits}"

    def test_resolution_carries_address_and_key_up_the_chain(self):
        tree = store.world_tree(seed=SEED, max_depth=11)
        deepest = max(_walk(tree), key=lambda pair: len(pair[1]))[0]
        got = store.resolve_node_by_name(SEED, deepest.name)
        assert len(deepest.address) == 11
        expected = deepest
        while expected is not None:
            assert (got.name, got.address, got.key) == (
                expected.name, expected.address, expected.key)
            got, expected = got.parent, expected.parent
        assert got is None
        assert store.address_of(SEED, deepest.name) == deepest.address
        assert store.key_of(SEED, deepest.name) == deepest.key

    def test_node_at_reads_the_stored_name_from_an_address(self):
        tree = store.world_tree(seed=SEED, max_depth=4)
        for node, path in _walk(tree):
            for form in (node.address, ".".join(str(i) for i in path)):
                got = store.node_at(SEED, form)
                assert (got.name, got.key) == (node.name, node.key)
        for unborn in ("", "2", "10", "19", "1" * 12, "1.x", None):
            assert store.node_at(SEED, unborn) is None, unborn

    def test_hand_built_nodes_key_on_their_name(self):
        from multiverse.node import SpatialNode
        plain = SpatialNode("Vault", "Room")
        assert naming.node_key(plain) == "Vault"
        assert naming.node_address(plain) is None
        assert naming.node_path(plain) is None
        old_style = SpatialNode("Vault-112", "Room")
        assert naming.node_key(old_style) == "Vault-112"
        assert naming.node_address(old_style) == "112"
        assert naming.node_path(old_style) == "1.1.2"
        assert naming.name_carries_address(old_style)


def _v2_rows():
    """A small world as generator version 2 stored it: suffixed names."""
    return [
        ("1", "Elder Reed Cosmos-1", "Multiverse", json.dumps({"theme": "a"}), 2),
        ("1.1", "Ashen Ember Sphere-11", "Universe", json.dumps({"laws": "b"}), 1),
        ("1.2", "Hollow Reed Sphere-12", "Universe", json.dumps({"laws": "c"}), 0),
        ("1.1.1", "Mossbound Bell Disc-111", "Galaxy", json.dumps({"dust": "d"}), 0),
    ]


class TestWorldBornUnderVersionTwo:
    """A world born before ADR-041 keeps its stored names, and its key is
    the stored name alone: appending the address again would move every
    keyed draw."""

    V2 = SEED + 20

    def _birth(self):
        assert persistence.save_world_nodes(self.V2, _v2_rows(), 2) == 4

    def test_version_is_read_from_the_rows(self):
        self._birth()
        assert persistence.world_generator_version(self.V2) == 2
        assert store.generator_version(self.V2) == 2
        assert persistence.world_generator_version(SEED + 21) is None

    def test_tree_keeps_stored_names_as_keys(self):
        self._birth()
        root = store.world_tree(seed=self.V2, max_depth=3)
        stored = {path.replace(".", ""): name for path, name, *_ in _v2_rows()}
        seen = _walk(root)
        assert len(seen) == 4
        for node, path in seen:
            digits = "".join(str(i) for i in path)
            assert node.name == stored[digits]
            assert node.address == digits
            assert node.key == node.name
            assert naming.node_key(node) == node.name
            assert naming.name_carries_address(node)

    def test_resolves_by_its_stored_name(self):
        self._birth()
        got = store.resolve_node_by_name(self.V2, "Mossbound Bell Disc-111")
        assert got is not None and got.level == "Galaxy"
        assert (got.address, got.key) == ("111", "Mossbound Bell Disc-111")
        assert got.parent.name == "Ashen Ember Sphere-11"
        assert got.parent.key == "Ashen Ember Sphere-11"
        assert got.parent.parent.name == "Elder Reed Cosmos-1"
        assert got.parent.parent.parent is None
        assert store.address_of(self.V2, "Hollow Reed Sphere-12") == "12"
        assert store.key_of(self.V2, "Hollow Reed Sphere-12") == "Hollow Reed Sphere-12"
        assert store.node_at(self.V2, "12").name == "Hollow Reed Sphere-12"

    def test_refuses_forged_and_stripped_names(self):
        self._birth()
        for name in ("Mossbound Bell Disc", "Mossbound Bell Disc-112",
                     "Fake-11", "Ashen Ember Sphere-11-11", "NoSuffix"):
            assert store.resolve_node_by_name(self.V2, name) is None, name


class TestNameUniqueness:
    """ADR-041 D2: checked at birth, loudly, and enforced by the database."""

    def test_a_repeated_name_at_birth_raises_and_writes_nothing(self):
        seed = SEED + 30
        rows = [
            ("1", "Elder Reed Cosmos", "Multiverse", "{}", 2),
            ("1.1", "Ashen Ember Sphere", "Universe", "{}", 0),
            ("1.2", "Ashen Ember Sphere", "Universe", "{}", 0),
        ]
        with pytest.raises(ValueError, match="Ashen Ember Sphere"):
            persistence.save_world_nodes(seed, rows, store.GENERATOR_VERSION)
        assert not persistence.world_is_born(seed)
        assert persistence.get_world_nodes(seed) == []

    def test_a_generator_that_repeats_a_name_cannot_birth_a_world(self, monkeypatch):
        import multiverse.generator as gen

        seed = SEED + 31
        monkeypatch.setattr(gen, "NAME_QUALIFIERS",
                            tuple("Same" for _ in gen.NAME_QUALIFIERS))
        store._birth_rows_cache.clear()
        try:
            with pytest.raises(ValueError, match="more than one node"):
                store.world_tree(seed=seed, max_depth=3)
            assert not persistence.world_is_born(seed)
            assert (seed, store.GENERATOR_VERSION) not in store._birth_rows_cache
        finally:
            store._birth_rows_cache.clear()

    def test_a_name_ending_in_appended_digits_cannot_be_born(self, monkeypatch):
        import multiverse.generator as gen

        seed = SEED + 32
        forms = dict(gen.NAME_FORMS)
        forms["Multiverse"] = tuple(f"{form}-1" for form in forms["Multiverse"])
        monkeypatch.setattr(gen, "NAME_FORMS", forms)
        store._birth_rows_cache.clear()
        try:
            with pytest.raises(ValueError, match="appended digits"):
                store.birth_world(seed)
            assert not persistence.world_is_born(seed)
        finally:
            store._birth_rows_cache.clear()

    def test_the_unique_index_refuses_a_second_row_with_a_born_name(self):
        store.birth_world(SEED)
        name = store.root_name(SEED)
        with persistence._connect() as conn:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    """INSERT INTO world_nodes
                       (world_seed, path, name, level, properties, breadth,
                        generator_version, born_at)
                       VALUES (?, '1.9.9', ?, 'Galaxy', '{}', 0, 3, 'now')""",
                    (SEED, name))
            conn.rollback()
        assert len([row for row in persistence.get_world_nodes(SEED)
                    if row[1] == name]) == 1

    def test_the_same_name_may_be_born_in_two_worlds(self):
        row = [("1", "Elder Reed Cosmos", "Multiverse", "{}", 0)]
        assert persistence.save_world_nodes(SEED + 33, row, 3) == 1
        assert persistence.save_world_nodes(SEED + 34, row, 3) == 1
        assert store.resolve_node_by_name(SEED + 33, "Elder Reed Cosmos").address == "1"
        assert store.resolve_node_by_name(SEED + 34, "Elder Reed Cosmos").address == "1"

    def test_name_lookup_uses_the_unique_index(self):
        store.birth_world(SEED)
        with persistence._connect() as conn:
            plan = " ".join(str(row[-1]) for row in conn.execute(
                """EXPLAIN QUERY PLAN SELECT path, generator_version
                   FROM world_nodes WHERE world_seed = ? AND name = ?""",
                (SEED, "x")).fetchall())
        assert "idx_world_nodes_name" in plan and "SCAN" not in plan
