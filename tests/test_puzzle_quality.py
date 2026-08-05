import re

import pytest

from multiverse.generator import DEFAULT_WORLD_SEED, generate_node_hierarchy
from multiverse import store
from puzzles.generators import _answer_leaks, _edge_marks, build_puzzle
from puzzles.quality import puzzle_family, summarize_puzzles
from puzzles.types import Puzzle, PuzzleKind


def _walk(node, out):
    out.append(node)
    for child in node.children:
        _walk(child, out)
    return out


@pytest.fixture(scope="module")
def launch_puzzle_census():
    """Build the 4,208-node launch census exactly once for this module."""
    nodes = _walk(generate_node_hierarchy(seed=DEFAULT_WORLD_SEED), [])
    pairs = [(node, build_puzzle(node)) for node in nodes]
    return {
        "pairs": pairs,
        "audit": summarize_puzzles(
            [puzzle for _, puzzle in pairs],
            seed=DEFAULT_WORLD_SEED,
        ),
    }


class TestWorldReadingFamilies:
    def _examples(self, launch_puzzle_census, prefix):
        return [
            (node, puzzle)
            for node, puzzle in launch_puzzle_census["pairs"]
            if puzzle.name.startswith(prefix)
        ]

    def test_keeper_witness_scales_from_landmark_to_composition(
        self, launch_puzzle_census,
    ):
        examples = self._examples(
            launch_puzzle_census, "The Keeper Witness",
        )
        assert examples
        gentle = [(node, puzzle) for node, puzzle in examples
                  if puzzle.difficulty <= 2]
        hard = [(node, puzzle) for node, puzzle in examples
                if puzzle.difficulty >= 3]
        assert gentle and hard

        for node, puzzle in gentle[::20]:
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

        for node, puzzle in hard[::20]:
            ancestor_names = []
            holder = node.parent
            while holder is not None:
                ancestor_names.append(holder.name.rsplit("-", 1)[0].lower())
                holder = holder.parent
            answer_words = puzzle.answer.split()
            expected_words = 2 if puzzle.difficulty == 3 else 3
            assert len(answer_words) == expected_words
            assert puzzle.answer not in ancestor_names
            assert all(
                word in {part for name in ancestor_names for part in name.split()}
                for word in answer_words
            )
            assert not _answer_leaks(puzzle, node)

    def test_ancestral_compass_is_a_four_mark_composition(
        self, launch_puzzle_census,
    ):
        examples = self._examples(
            launch_puzzle_census, "The Ancestral Compass",
        )
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

    def test_direct_resolution_preserves_world_reading_puzzles(
        self, launch_puzzle_census,
    ):
        # Runtime node resolution reconstructs ancestors but not descendants;
        # both families must therefore depend on the ancestor chain alone.
        examples = self._examples(
            launch_puzzle_census, "The Keeper Witness",
        ) + self._examples(
            launch_puzzle_census, "The Ancestral Compass",
        )
        assert examples
        for node, puzzle in examples[::75]:
            twin = store.resolve_node_by_name(DEFAULT_WORLD_SEED, node.name)
            rebuilt = build_puzzle(twin)
            assert (rebuilt.name, rebuilt.prompt, rebuilt.answer) == (
                puzzle.name, puzzle.prompt, puzzle.answer
            )

    def test_multiword_answer_leaks_are_screened_mechanically(
        self, launch_puzzle_census,
    ):
        node = launch_puzzle_census["pairs"][0][0]
        prompt_leak = Puzzle(
            name="Future Keeper",
            kind=PuzzleKind.NAVIGATION,
            prompt="The keeper is Golden Anchor Accord, written plainly.",
            answer="golden anchor accord",
        )
        hint_leak = Puzzle(
            name="Future Keeper",
            kind=PuzzleKind.NAVIGATION,
            prompt="Read the keeper.",
            answer="golden anchor accord",
            hints=["Bring back golden anchor accord from the fold."],
        )
        assert _answer_leaks(prompt_leak, node)
        assert _answer_leaks(hint_leak, node)

    def test_family_classifier_handles_renewal_and_unknown_names(
        self, launch_puzzle_census,
    ):
        for suffix, family in (
            (" Inscription", "cipher"),
            (" Progression", "numeric_pattern"),
        ):
            example = next(
                puzzle for _, puzzle in launch_puzzle_census["pairs"]
                if puzzle.name.endswith(suffix)
            )
            renewed = Puzzle(
                name=f"{example.name} · Renewal 2",
                kind=example.kind,
                prompt=example.prompt,
                answer=example.answer,
            )
            assert puzzle_family(renewed) == family

        # A static title that happens to share a generated-family prefix stays
        # authored; explicit pool membership wins over naming convention.
        assert puzzle_family(Puzzle(
            name="The Bond Pattern",
            kind=PuzzleKind.PATTERN,
            prompt="Count the bonds.",
            answer="16",
        )) == "handwritten"
        with pytest.raises(ValueError, match="unclassified generated"):
            puzzle_family(Puzzle(
                name="The Unregistered Future Family",
                kind=PuzzleKind.LOGIC,
                prompt="A future mechanic.",
                answer="future",
            ))


class TestPuzzleEcologyGate:
    def test_canonical_launch_world_passes(self, launch_puzzle_census):
        result = launch_puzzle_census["audit"]
        assert result["passed"], result["failures"]
        assert result["puzzle_count"] == 4208

    def test_decode_families_do_not_dominate(self, launch_puzzle_census):
        metrics = launch_puzzle_census["audit"]["metrics"]
        assert metrics["decode_family_ratio"] <= 0.50
        assert metrics["world_reading_family_ratio"] >= 0.55
        assert metrics["largest_family_ratio"] <= 0.25
