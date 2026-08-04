import re

from multiverse.generator import DEFAULT_WORLD_SEED, generate_node_hierarchy
from multiverse import store
from puzzles.generators import _answer_leaks, _edge_marks, build_puzzle
from puzzles.quality import audit_puzzles
from puzzles.types import PuzzleKind


def _walk(node, out):
    out.append(node)
    for child in node.children:
        _walk(child, out)
    return out


class TestWorldReadingFamilies:
    def _examples(self, prefix, seed=DEFAULT_WORLD_SEED):
        nodes = _walk(generate_node_hierarchy(seed=seed), [])
        return [
            (node, build_puzzle(node))
            for node in nodes
            if build_puzzle(node).name.startswith(prefix)
        ]

    def test_keeper_witness_uses_a_readable_ancestor_name(self):
        examples = self._examples("The Keeper Witness")
        assert examples
        for node, puzzle in examples[::40]:
            ancestors = []
            holder = node.parent
            while holder is not None:
                ancestors.append(holder)
                holder = holder.parent
            readable_names = {
                ancestor.name.rsplit("-", 1)[0].lower()
                for ancestor in ancestors
            }
            assert puzzle.kind is PuzzleKind.NAVIGATION
            assert puzzle.answer in readable_names
            assert not _answer_leaks(puzzle, node)

    def test_ancestral_compass_is_a_four_mark_composition(self):
        examples = self._examples("The Ancestral Compass")
        assert examples
        for node, puzzle in examples[::40]:
            assert puzzle.kind is PuzzleKind.LOGIC
            assert len(puzzle.answer) == 4
            assert puzzle.answer.isalnum()
            match = re.search(
                r"At the (.*?), read its (.*?);.*Then, at the (.*?), "
                r"do the same with its (.*?)\.",
                puzzle.prompt,
            )
            assert match, puzzle.prompt
            outer_level, outer_label, inner_level, inner_label = match.groups()
            ancestors = {}
            holder = node.parent
            while holder is not None:
                ancestors[holder.level] = holder
                holder = holder.parent
            outer_value = ancestors[outer_level].properties[
                outer_label.replace(" ", "_")
            ]
            inner_value = ancestors[inner_level].properties[
                inner_label.replace(" ", "_")
            ]
            assert puzzle.answer == (
                _edge_marks(outer_value) + _edge_marks(inner_value)
            )
            assert not _answer_leaks(puzzle, node)

    def test_direct_resolution_preserves_world_reading_puzzles(self):
        # Runtime node resolution reconstructs ancestors but not descendants;
        # both families must therefore depend on the ancestor chain alone.
        examples = self._examples("The Keeper Witness") + \
            self._examples("The Ancestral Compass")
        assert examples
        for node, puzzle in examples[::75]:
            twin = store.resolve_node_by_name(DEFAULT_WORLD_SEED, node.name)
            rebuilt = build_puzzle(twin)
            assert (rebuilt.name, rebuilt.prompt, rebuilt.answer) == (
                puzzle.name, puzzle.prompt, puzzle.answer
            )


class TestPuzzleEcologyGate:
    def test_canonical_launch_world_passes(self):
        result = audit_puzzles(DEFAULT_WORLD_SEED)
        assert result["passed"], result["failures"]
        assert result["puzzle_count"] == 4208

    def test_decode_families_do_not_dominate(self):
        metrics = audit_puzzles(DEFAULT_WORLD_SEED)["metrics"]
        assert metrics["decode_family_ratio"] <= 0.50
        assert metrics["world_reading_family_ratio"] >= 0.55
        assert metrics["largest_family_ratio"] <= 0.25
