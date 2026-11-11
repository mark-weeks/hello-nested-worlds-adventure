"""Answer withdrawal changes delivery, while the existing pool keeps its rules."""
from __future__ import annotations

import urllib.parse

import persistence
from multiverse import store
from puzzles.engine import PuzzleEngine
from puzzles.instances import get_puzzle
from puzzles.types import Puzzle, PuzzleKind, PuzzleResult
from server import rooms


def _open(request):
    status, opened, _ = request("/puzzle?depth=1")
    assert status == 200 and opened["found"] is True
    assert "correct_answer" not in opened and "answer" not in opened
    root = store.world_tree(seed=382, max_depth=2)
    puzzle = get_puzzle(382, root, 0)
    assert puzzle.name == opened["name"]
    return root, puzzle


def _attempt(request, root, puzzle, answer, *, key=None, **extra):
    body = {"node_name": root.name, "puzzle_name": puzzle.name, "answer": answer,
            **extra}
    result = request("/puzzle/attempt", body=body) if key is None else request(
        "/puzzle/attempt", key, body)
    assert "correct_answer" not in result[1]
    return result


def test_fresh_wrong_correct_and_already_solved_responses_omit_answer(http, accounts):
    root, puzzle = _open(http)
    status, wrong, _ = _attempt(http, root, puzzle, "a plain wrong guess")
    assert status == 200 and wrong["result"] == "UNSOLVED"
    assert wrong["attempt"] == 1 and wrong["contributors"] == ["Ada"]

    status, solved, _ = _attempt(http, root, puzzle, puzzle.answer, key=accounts[1])
    assert status == 200 and solved["result"] == "SOLVED"
    assert solved["attempt"] == 2 and solved["solver"] == "Bea"
    assert solved["contributors"] == ["Ada", "Bea"]
    assert solved["changed"]["stabilized"] is True
    before = persistence.get_mutations(382)

    status, late, _ = _attempt(http, root, puzzle, "another wrong guess")
    assert status == 200 and late["result"] == "SOLVED"
    assert late["attempt"] == 2 and late["solver"] == "Bea"
    assert persistence.get_mutations(382) == before
    status, reopened, _ = http("/puzzle?node_name=" + urllib.parse.quote(root.name))
    assert status == 200 and reopened["solved"]
    assert "correct_answer" not in reopened and "answer" not in reopened


def test_mismatch_and_error_responses_omit_answer_without_spending_attempts(http):
    root, puzzle = _open(http)
    for override, expected_status in (
        ({"puzzle_name": "not the current question"}, 409),
        ({"node_name": "no such place"}, 404),
        ({"seed": "not an integer"}, 400),
    ):
        status, rejected, _ = _attempt(http, root, puzzle, "a plain wrong guess", **override)
        assert status == expected_status and "error" in rejected
    assert persistence.get_puzzle_attempt_state(382, root.name, puzzle.name) == {
        "attempts": 0, "contributors": set()}
    assert persistence.get_mutations(382) == []


def test_stored_multiplayer_pool_rehydrates_without_releasing_answer(http, accounts):
    root, puzzle = _open(http)
    status, response, _ = _attempt(http, root, puzzle, "a plain wrong guess")
    assert status == 200 and response["attempt"] == 1

    # Another player's stored guesses exhaust the same pool outside the cached
    # session. A fresh GET must rehydrate those rows after the room cache clears.
    for _ in range(puzzle.max_attempts - 1):
        persistence.record_mutation(382, root.name, "PUZZLE_ATTEMPT", "Bea",
                                    {"puzzle": puzzle.name, "correct": False},
                                    actor_identity=persistence._credential_digest(accounts[1]))
    rooms.clear_rooms()
    newcomer = "nw_" + "c" * 32
    persistence.mint_invite_key(newcomer, "Carol")

    status, opened, _ = http("/puzzle?depth=1", newcomer)
    assert status == 200 and opened["attempt"] == puzzle.max_attempts
    assert opened["contributors"] == ["Ada", "Bea"]
    assert "correct_answer" not in opened and "answer" not in opened

    for count in (puzzle.max_attempts + 1, puzzle.max_attempts + 2):
        status, failed, _ = _attempt(http, root, puzzle, "a plain wrong guess", key=newcomer)
        assert status == 200 and failed["result"] == "FAILED"
        assert failed["correct"] is False and failed["hint"] is None
        assert failed["attempt"] == count and failed["solver"] is None
        assert failed["contributors"] == ["Ada", "Bea", "Carol"]
        assert failed["changed"] is None

    rows = persistence.get_mutations(382)
    assert sum(row["type"] == "PUZZLE_ATTEMPT" for row in rows) == puzzle.max_attempts + 2
    assert sum(row["type"] == "PUZZLE_FAILED" for row in rows) == 2
    assert not any(row["type"] == "PUZZLE_REARM" for row in rows)

    # Batch 1a withdraws the disclosure only: it does not replace the
    # pool or refuse a legitimately known answer after exhaustion.
    status, solved, _ = _attempt(http, root, puzzle, puzzle.answer, key=accounts[1])
    assert status == 200 and solved["result"] == "SOLVED"
    assert solved["attempt"] == puzzle.max_attempts + 3
    assert solved["solver"] == "Bea" and solved["changed"]["stabilized"] is True
    assert solved["contributors"] == ["Ada", "Bea", "Carol"]
    rows = persistence.get_mutations(382)
    assert sum(row["type"] == "PUZZLE_FAILED" for row in rows) == 2
    assert sum(row["type"] == "PUZZLE_SOLVED" for row in rows) == 1


def test_cli_exhaustion_keeps_answer_private_and_returns_failed(monkeypatch, capsys):
    secret = "the-private-answer-to-this-fixture"
    puzzle = Puzzle(name="A guarded question", kind=PuzzleKind.RIDDLE,
                    prompt="What word is kept behind the door?", answer=secret,
                    hints=["Try another word."], max_attempts=2)
    guesses = iter(["a wrong word", "another wrong word"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(guesses))

    assert PuzzleEngine().run_puzzle(puzzle) is PuzzleResult.FAILED
    output = capsys.readouterr().out
    assert secret not in output
    assert output.rstrip().endswith("The question keeps its answer.")
    assert puzzle.attempts == 2 and puzzle.failed
