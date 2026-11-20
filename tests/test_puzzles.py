import re

import pytest

from puzzles.types import Puzzle, PuzzleKind, PuzzleResult
from puzzles.engine import PuzzleEngine
from multiverse import naming
from multiverse.generator import generate_node_hierarchy
from multiverse.node import SpatialNode
from puzzles.generators import (
    CANONICAL_LEVELS, build_puzzle, node_difficulty,
)


def make_puzzle(**kwargs):
    defaults = dict(
        name="Test Puzzle",
        kind=PuzzleKind.RIDDLE,
        prompt="What is 1+1?",
        answer="2",
        hints=["It's a small number.", "Greater than one."],
        max_attempts=3,
    )
    defaults.update(kwargs)
    return Puzzle(**defaults)


def _tokens(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9.]+", s.lower()))


def _walk(node, acc):
    acc.append(node)
    for c in node.children:
        _walk(c, acc)


CANONICAL_LEVELS = list(CANONICAL_LEVELS)


class TestPuzzleTypes:
    def test_correct_answer_solves(self):
        p = make_puzzle()
        result = p.attempt("2")
        assert result == PuzzleResult.SOLVED
        assert p.solved

    def test_case_insensitive(self):
        p = make_puzzle(answer="echo")
        assert p.attempt("Echo") == PuzzleResult.SOLVED

    def test_whitespace_stripped(self):
        p = make_puzzle(answer="echo")
        assert p.attempt("  echo  ") == PuzzleResult.SOLVED

    def test_wrong_answer_increments_attempts(self):
        p = make_puzzle()
        p.attempt("wrong")
        assert p.attempts == 1
        assert p.result == PuzzleResult.UNSOLVED

    def test_exceeds_max_attempts_fails(self):
        p = make_puzzle(max_attempts=2)
        p.attempt("wrong")
        result = p.attempt("also wrong")
        assert result == PuzzleResult.FAILED
        assert p.failed

    def test_no_attempt_after_solved(self):
        p = make_puzzle()
        p.attempt("2")
        result = p.attempt("2")
        assert result == PuzzleResult.SOLVED
        assert p.attempts == 1  # second attempt was ignored

    def test_hint_after_first_wrong(self):
        p = make_puzzle(hints=["Hint 1", "Hint 2"])
        p.attempt("wrong")
        assert p.hint() == "Hint 1"

    def test_no_hint_before_attempt(self):
        p = make_puzzle(hints=["Hint 1"])
        assert p.hint() is None


class TestPuzzleEngine:
    def test_attach_and_collect(self):
        root = generate_node_hierarchy(seed=42, max_depth=3)
        engine = PuzzleEngine(seed=42)
        engine.attach_puzzles(root)
        puzzles = engine.collect_puzzles(root)
        assert len(puzzles) > 0

    def test_puzzles_at_all_levels(self):
        from multiverse.generator import LEVELS
        root = generate_node_hierarchy(seed=42, max_depth=11)
        engine = PuzzleEngine(seed=42)
        count = engine.attach_puzzles(root)
        nodes = []
        _walk(root, nodes)
        assert count == len(nodes)  # every node grew a puzzle
        assert {n.level for n in nodes
                if engine.puzzle_for(n) is not None} == set(LEVELS)

    def test_attached_puzzles_are_puzzle_instances(self):
        root = generate_node_hierarchy(seed=42, max_depth=7)
        engine = PuzzleEngine(seed=1)
        engine.attach_puzzles(root)
        puzzles = engine.collect_puzzles(root)
        for p in puzzles:
            assert isinstance(p, Puzzle)

    def test_attach_is_idempotent(self):
        root = generate_node_hierarchy(seed=42, max_depth=7)
        engine = PuzzleEngine(seed=1)
        engine.attach_puzzles(root)
        count1 = len(engine.collect_puzzles(root))
        engine.attach_puzzles(root)
        count2 = len(engine.collect_puzzles(root))
        assert count1 == count2


# ── Puzzle quality invariants ──────────────────────────────────────────────
# These replace the old per-generator tests, which asserted the exact trivial
# formula each level used (answer == atomic_number, weight/4, min(3, exits), …).
# The redesign makes puzzles non-trivial, non-leaking, and node-unique, so we
# now assert those PROPERTIES rather than a specific answer.


def _node(level: str, name: str | None = None, **props) -> SpatialNode:
    return SpatialNode(name=name or f"{level}-Node", level=level, properties=props)


class TestNoAnswerLeak:
    """The answer must never be recoverable without solving: not a token in the
    prompt, not in any hint, and not a value the node ships in /world."""

    @pytest.mark.parametrize("level", CANONICAL_LEVELS)
    def test_answer_not_in_prompt(self, level):
        p = build_puzzle(_node(level))
        assert p.answer.lower() not in _tokens(p.prompt), (
            f"{level}: answer {p.answer!r} leaks into the prompt"
        )

    @pytest.mark.parametrize("level", CANONICAL_LEVELS)
    def test_answer_not_in_hints(self, level):
        p = build_puzzle(_node(level))
        for h in p.hints:
            assert p.answer.lower() not in _tokens(h), (
                f"{level}: answer {p.answer!r} leaks into hint {h!r}"
            )

    def test_answer_never_equals_a_shipped_property(self):
        # Build against a real world so the generator sees real property values
        # (theme, biome, shape, element, particle_type, …) and must avoid them.
        root = generate_node_hierarchy(seed=3, max_depth=8)
        engine = PuzzleEngine(seed=3)
        engine.attach_puzzles(root)
        nodes = []
        _walk(root, nodes)
        for n in nodes:
            p = engine.puzzle_for(n)
            propvals = {str(v).lower() for v in n.properties.values()
                        if not isinstance(v, Puzzle)}
            assert p.answer.lower() not in propvals, (
                f"{n.name}: answer {p.answer!r} is a shipped property value"
            )

    def test_puzzles_never_stored_in_node_properties(self):
        # The Puzzle object (whose repr includes the answer and every hint)
        # must never ride on node.properties — that dict is dumped by the CLI
        # `look`, serialized into /world payloads, and rendered into the
        # consciousness system prompt.
        root = generate_node_hierarchy(seed=3, max_depth=6)
        engine = PuzzleEngine(seed=3)
        engine.attach_puzzles(root)
        nodes = []
        _walk(root, nodes)
        for n in nodes:
            assert "puzzle" not in n.properties
            assert not any(isinstance(v, Puzzle) for v in n.properties.values())


class TestSolvableAndClued:
    @pytest.mark.parametrize("level", CANONICAL_LEVELS)
    def test_own_answer_solves(self, level):
        p = build_puzzle(_node(level))
        # Rebuild a fresh instance (build_puzzle may return a shared pool copy).
        q = Puzzle(name=p.name, kind=p.kind, prompt=p.prompt, answer=p.answer,
                   hints=list(p.hints), max_attempts=p.max_attempts)
        assert q.attempt(p.answer) == PuzzleResult.SOLVED

    @pytest.mark.parametrize("level", CANONICAL_LEVELS)
    def test_has_graduated_hints(self, level):
        p = build_puzzle(_node(level))
        assert len(p.hints) >= 2, f"{level}: needs at least two graduated hints"
        assert all(h.strip() for h in p.hints)

    @pytest.mark.parametrize("level", CANONICAL_LEVELS)
    def test_prompt_and_answer_nonempty(self, level):
        p = build_puzzle(_node(level))
        assert p.prompt.strip()
        assert p.answer.strip()


class TestTransformIntegrity:
    """Anagram and cipher puzzles must actually be solvable by reversing their
    transform — otherwise they'd be unfair, not just hard."""

    def _one_of_kind(self, kind: PuzzleKind, level: str) -> Puzzle | None:
        # Different node names select different families; scan a batch to find
        # an instance of the kind we want to check.
        for i in range(200):
            p = build_puzzle(_node(level, name=f"{level}-{i}"))
            if p.kind == kind:
                return p
        return None

    def test_anagram_letters_are_a_permutation(self):
        p = self._one_of_kind(PuzzleKind.ANAGRAM, "Atom")
        assert p is not None
        # The scrambled token in the prompt is the run of capitals.
        scrambled = re.search(r"[A-Z]{3,}", p.prompt).group(0)
        assert sorted(scrambled.lower()) == sorted(p.answer.lower())
        assert scrambled.lower() != p.answer.lower()  # actually scrambled

    def test_cipher_decodes_to_answer(self):
        p = self._one_of_kind(PuzzleKind.CIPHER, "Atom")
        assert p is not None
        cipher = re.search(r"[A-Z]{3,}", p.prompt).group(0).lower()
        shift = int(re.search(r"moved forward by (\d+)", " ".join(p.hints)).group(1))
        decoded = "".join(
            chr((ord(c) - ord("a") - shift) % 26 + ord("a")) for c in cipher
        )
        assert decoded == p.answer.lower()


class TestPerNodeUniqueness:
    def test_same_node_identity_is_deterministic(self):
        # Co-op safety: everyone standing on a node must see the same puzzle,
        # and a rebuilt world must regenerate it identically — regardless of the
        # engine's own seed.
        a = build_puzzle(_node("Room", name="Vault-7"))
        b = build_puzzle(_node("Room", name="Vault-7"))
        assert (a.name, a.prompt, a.answer) == (b.name, b.prompt, b.answer)

    def test_different_nodes_mostly_differ(self):
        # 30 sibling Room nodes should not all collapse to one puzzle the way
        # the old property-keyed generator did (min(3, exits) → 3 answers ever).
        answers = {build_puzzle(_node("Room", name=f"Room-{i}")).answer
                   for i in range(30)}
        assert len(answers) >= 10

    def test_world_repetition_is_low(self):
        # Across a realistic tree, the fraction of exact-duplicate puzzles must
        # be far below the pre-redesign 35%, and no single puzzle may dominate
        # the way "The Widdershins Door" once did (~150 identical copies).
        root = generate_node_hierarchy(seed=11, max_depth=8)
        engine = PuzzleEngine(seed=11)
        engine.attach_puzzles(root)
        nodes = []
        _walk(root, nodes)
        pz = [engine.puzzle_for(n) for n in nodes if engine.puzzle_for(n)]
        sigs = {}
        for p in pz:
            sigs[(p.name, p.prompt, p.answer)] = sigs.get((p.name, p.prompt, p.answer), 0) + 1
        distinct = len(sigs)
        assert distinct / len(pz) >= 0.75, (
            f"only {distinct}/{len(pz)} distinct puzzles"
        )
        assert max(sigs.values()) <= len(pz) * 0.1, "one puzzle dominates the tree"


class TestDifficultyIsPerNode:
    """Traversal is non-linear (drop in anywhere, move up or down, explore
    continuously), so difficulty is a property of the individual node — spread
    across the full range at every scale — NOT a function of depth."""

    def test_eleven_canonical_levels(self):
        assert set(CANONICAL_LEVELS) == {
            "Multiverse", "Universe", "Galaxy", "Planetary System", "Planet",
            "Region", "Room", "Object", "Molecule", "Atom", "SubatomicParticle",
        }

    def test_difficulty_is_deterministic_per_node(self):
        a = node_difficulty(_node("Room", name="Vault-7"))
        b = node_difficulty(_node("Room", name="Vault-7"))
        assert a == b
        assert 1 <= a <= 4

    def test_difficulty_spread_at_every_scale(self):
        # Both the top (Multiverse) and the bottom (SubatomicParticle) scales
        # must carry the full range of difficulties — no scale is uniformly
        # easy or uniformly hard. This is the crux of the non-linear model.
        for level in ("Multiverse", "SubatomicParticle"):
            seen = {node_difficulty(_node(level, name=f"{level}-{i}"))
                    for i in range(60)}
            assert seen == {1, 2, 3, 4}, (
                f"{level} should carry every difficulty, saw {sorted(seen)}"
            )

    def test_difficulty_not_determined_by_scale(self):
        # A Multiverse node can be the hardest tier; a subatomic node can be the
        # easiest — the exact opposite of a depth curve.
        mv = [node_difficulty(_node("Multiverse", name=f"M-{i}")) for i in range(60)]
        sub = [node_difficulty(_node("SubatomicParticle", name=f"S-{i}")) for i in range(60)]
        assert max(mv) == 4 and min(sub) == 1

    def test_puzzle_carries_node_difficulty(self):
        for level in CANONICAL_LEVELS:
            n = _node(level, name=f"{level}-77")
            p = build_puzzle(n)
            assert p.difficulty == node_difficulty(n)
            assert 1 <= p.difficulty <= 4

    def test_attempts_track_puzzle_difficulty(self):
        # Fairness travels with the puzzle: a harder puzzle grants at least as
        # many attempts as an easier one, wherever it sits.
        by_diff = {}
        for i in range(400):
            n = _node("Object", name=f"Object-{i}")
            p = build_puzzle(n)
            by_diff.setdefault(p.difficulty, p.max_attempts)
        assert 1 in by_diff and 4 in by_diff
        assert by_diff[4] >= by_diff[1]


class TestCanonicalLevelsUseGenerator:
    """Every canonical scale must resolve through the new generator (rich,
    node-voiced kinds), never fall through to the generic default pool."""

    def test_every_level_yields_a_rich_kind(self):
        rich = {PuzzleKind.ANAGRAM, PuzzleKind.CIPHER, PuzzleKind.PATTERN,
                PuzzleKind.RIDDLE, PuzzleKind.LOGIC, PuzzleKind.SEQUENCE,
                PuzzleKind.LOCK, PuzzleKind.NAVIGATION}
        for level in CANONICAL_LEVELS:
            p = build_puzzle(_node(level))
            assert p.kind in rich


# ── Names, addresses and keys (ADR-041) ─────────────────────────────────────
# A born name is its three words; the address is carried beside it; every
# keyed draw takes the key, which is the name generator version 2 stored. So
# a place serves the same puzzle whichever generation its world was born
# under, and only wording that pointed at the digits in a name differs.

_SUFFIX_WORDING = ("dash", "lineage mark", "lineage digits", "final digit")


def _address_tree(seed: int, depth: int):
    """A freshly generated world and each node's address digits."""
    root = generate_node_hierarchy(seed=seed, max_depth=depth)
    nodes: list[SpatialNode] = []
    _walk(root, nodes)
    return root, nodes


def _as_version_two(nodes) -> None:
    """Rename a generated tree the way generator version 2 stored it: each
    name ends in its path digits, and the key is the stored name alone."""
    for n in nodes:
        n.name = f"{n.name}-{n.address}"
        n.key = n.name


def _served(node, epoch):
    p = build_puzzle(node, epoch)
    return (p.kind, p.name, p.answer, p.difficulty, p.max_attempts)


class TestNamesAndAddresses:
    SEED = 911

    def test_generated_nodes_carry_an_address_and_a_key(self):
        _, nodes = _address_tree(self.SEED, 6)
        for n in nodes:
            assert n.address and n.address.isdigit()
            assert not n.name.endswith(n.address)
            assert naming.node_key(n) == f"{n.name}-{n.address}"

    def test_a_place_serves_the_same_puzzle_under_either_generation(self):
        _, new = _address_tree(self.SEED, 7)
        _, old = _address_tree(self.SEED, 7)
        _as_version_two(old)
        assert len(new) == len(old) > 300
        for a, b in zip(new, old):
            assert node_difficulty(a) == node_difficulty(b)
            for epoch in (0, 1, 2):
                assert _served(a, epoch) == _served(b, epoch), (a.name, epoch)

    def test_text_differs_only_by_the_name_and_the_reworded_lines(self):
        _, new = _address_tree(self.SEED, 7)
        _, old = _address_tree(self.SEED, 7)
        _as_version_two(old)
        reworded = 0
        for a, b in zip(new, old):
            chain = []
            x, y = a, b
            while x is not None:
                chain.append((y.name, x.name))
                x, y = x.parent, y.parent
            for epoch in (0, 1):
                p, q = build_puzzle(a, epoch), build_puzzle(b, epoch)
                assert len(p.hints) == len(q.hints)
                for new_text, old_text in zip([p.prompt, *p.hints],
                                              [q.prompt, *q.hints]):
                    for suffixed, bare in chain:
                        old_text = old_text.replace(suffixed, bare)
                    if new_text != old_text:
                        reworded += 1
                        assert any(w in old_text for w in _SUFFIX_WORDING) or \
                            "written where everything else is" in old_text, (
                                a.name, old_text, new_text)
        assert reworded > 50

    def test_new_wording_never_points_at_a_suffix(self):
        _, nodes = _address_tree(self.SEED, 7)
        for n in nodes:
            for epoch in (0, 1, 2):
                p = build_puzzle(n, epoch)
                for text in [p.prompt, *p.hints]:
                    assert not any(w in text for w in _SUFFIX_WORDING), (
                        n.name, text)
                    assert f"-{n.address}" not in text, (n.name, text)

    def test_a_version_two_world_keeps_its_wording(self):
        _, nodes = _address_tree(self.SEED, 7)
        _as_version_two(nodes)
        texts = [t for n in nodes for p in [build_puzzle(n)]
                 for t in [p.prompt, *p.hints]]
        for line in (
            "Its living name is everything before the dash and digits.",
            "Strip each dash and lineage digits before counting its words.",
            "Read the final digit after the dash.",
            "Count the digits after the dash, then subtract this place itself.",
        ):
            assert line in texts, line
        assert any(t.endswith("the words before its lineage mark.")
                   for t in texts)

    def test_new_wording_is_served_where_the_old_was(self):
        _, nodes = _address_tree(self.SEED, 7)
        texts = [t for n in nodes for p in [build_puzzle(n)]
                 for t in [p.prompt, *p.hints]]
        for line in (
            "Its living name is its name in full, every word.",
            "Count the words of each living name exactly as it is written.",
            "Read the final step of this place's address.",
            "Count the steps in this place's address, then subtract this "
            "place itself.",
        ):
            assert line in texts, line
        assert any(t.endswith("the words it is called by.") for t in texts)

    def test_the_address_counts_as_shown_text(self):
        # The address is served beside the name, so an answer equal to its
        # digits is on show wherever the name is printed.
        from puzzles.generators import _answer_leaks
        place = SpatialNode("Hollow Reed Sphere", "Universe")
        place.address, place.key = "11", "Hollow Reed Sphere-11"
        prompt = "A pattern pulses through Hollow Reed Sphere: 3, 5, 7, 9, ?"
        assert _answer_leaks(make_puzzle(prompt=prompt, answer="11"), place)
        assert not _answer_leaks(make_puzzle(prompt=prompt, answer="13"), place)
        elsewhere = SpatialNode("Hollow Reed Sphere", "Universe")
        elsewhere.address, elsewhere.key = "12", "Hollow Reed Sphere-12"
        assert not _answer_leaks(make_puzzle(prompt=prompt, answer="11"),
                                 elsewhere)
        # A holder's address shows where the holder is named.
        child = SpatialNode("Mossbound Bell Disc", "Galaxy")
        child.address, child.key = "111", "Mossbound Bell Disc-111"
        place.add_child(child)
        hint = "The keeper is Hollow Reed Sphere — the Universe that holds it."
        assert _answer_leaks(
            make_puzzle(prompt="Speak.", answer="11", hints=[hint]), child)
        # The screen reads; it never rewrites what is served.
        assert make_puzzle(prompt=prompt, answer="11").prompt == prompt

    def test_enfold_reads_the_address_not_the_name(self):
        from puzzles.generators import _make_enfold, node_rng
        place = SpatialNode("Quiet Salt Whorl", "Galaxy")
        place.address, place.key = "132", "Quiet Salt Whorl-132"
        answers = set()
        for i in range(40):
            place.key = f"Quiet Salt Whorl-132:{i}"  # vary the draw only
            answers.add(_make_enfold(place, node_rng(place), 2).answer)
        assert answers == {"2", "8"}  # held by two, eight within, second
        unplaced = SpatialNode("Quiet Salt Whorl", "Galaxy")
        assert _make_enfold(unplaced, node_rng(unplaced), 2) is None

    def test_the_stored_world_serves_what_the_generator_does(self):
        from multiverse import store
        seed = 4431
        _, nodes = _address_tree(seed, 6)
        for n in nodes[::9]:
            stored = store.resolve_node_by_name(seed, n.name)
            assert naming.node_key(stored) == naming.node_key(n)
            for epoch in (0, 1):
                assert _served(stored, epoch) == _served(n, epoch)


class TestSealsReadAddresses:
    """The seal never imprisons, and it tells inside from outside by
    address: one lookup of the stored name, whatever generation the world
    was born under."""

    def _locked_room(self, root):
        nodes: list[SpatialNode] = []
        _walk(root, nodes)
        return next(n for n in nodes if n.level == "Room"
                    and n.properties.get("locked") and n.children)

    def _check(self, seed):
        from multiverse import store
        from puzzles.gates import inside_seal, seal_check
        root = store.world_tree(seed)
        room = self._locked_room(root)
        deep = room.children[0].children[0]
        sibling = next(c for c in room.parent.children if c is not room)
        assert seal_check(seed, deep) is not None
        assert seal_check(seed, deep, current_name=room.name) is None
        assert seal_check(seed, room, current_name=deep.name) is None
        assert seal_check(seed, deep, current_name=sibling.name) is not None
        assert seal_check(seed, deep, current_name=root.name) is not None
        assert seal_check(seed, deep, current_name="No Such Place") is not None
        # A name the world does not hold is outside, digits or not.
        forged = f"Forged-{room.address}1"
        assert seal_check(seed, deep, current_name=forged) is not None
        # Without a world to ask, the room's own subtree answers.
        assert inside_seal(None, room, deep.name)
        assert not inside_seal(None, room, sibling.name)
        return room

    def test_in_a_world_born_with_plain_names(self):
        room = self._check(4432)
        assert naming.legacy_address(room.name) is None

    def test_in_a_world_born_under_generator_version_two(self):
        import json
        import persistence
        from multiverse import store
        seed = 4433
        _, nodes = _address_tree(seed, 11)
        rows = [(naming.dotted_of(n.address), f"{n.name}-{n.address}",
                 n.level, json.dumps(n.properties, ensure_ascii=False),
                 len(n.children)) for n in nodes]
        assert persistence.save_world_nodes(seed, rows, 2) == len(rows)
        assert store.generator_version(seed) == 2
        room = self._check(seed)
        assert room.name.endswith(f"-{room.address}")
        assert naming.node_key(room) == room.name
