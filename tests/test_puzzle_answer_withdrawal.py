"""Answer withdrawal changes delivery, while the existing pool keeps its rules."""
from __future__ import annotations

from contextlib import contextmanager
import json
import threading
import urllib.error
import urllib.parse
import urllib.request

import persistence
from multiverse import store
from puzzles.engine import PuzzleEngine
from puzzles.instances import get_puzzle
from puzzles.types import Puzzle, PuzzleKind, PuzzleResult
from server import _Handler, _ThreadedServer, rooms


@contextmanager
def _live_server(default_key):
    """A real server instance that can restart against the same fixture DB."""
    server = _ThreadedServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def request(path, key=default_key, body=None):
        req = urllib.request.Request(
            f"http://127.0.0.1:{server.server_port}{path}",
            data=json.dumps(body).encode() if body is not None else None,
            headers={"X-Beta-Key": key, "Content-Type": "application/json"})
        try:
            response = urllib.request.urlopen(req, timeout=10)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            return response.status, json.load(response), dict(response.headers)

    try:
        yield request
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)


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


def test_stored_multiplayer_pool_survives_server_restart_without_releasing_answer(accounts, monkeypatch):
    monkeypatch.setenv("NESTED_WORLDS_CANONICAL_SEED", "382")
    with _live_server(accounts[0]) as first:
        root, puzzle = _open(first)
        status, response, _ = _attempt(first, root, puzzle, "a plain wrong guess")
        assert status == 200 and response["attempt"] == 1

    # Another player's stored guesses can exhaust the same pool without this
    # process having seen them. This is the future batch's rollback scenario.
    for _ in range(puzzle.max_attempts - 1):
        persistence.record_mutation(382, root.name, "PUZZLE_ATTEMPT", "Bea",
                                    {"puzzle": puzzle.name, "correct": False},
                                    actor_identity=persistence._credential_digest(accounts[1]))
    rooms.clear_rooms()
    newcomer = "nw_" + "c" * 32
    persistence.mint_invite_key(newcomer, "Carol")

    with _live_server(newcomer) as restarted:
        status, opened, _ = restarted("/puzzle?depth=1")
        assert status == 200 and opened["attempt"] == puzzle.max_attempts
        assert opened["contributors"] == ["Ada", "Bea"]
        assert "correct_answer" not in opened and "answer" not in opened

        for count in (puzzle.max_attempts + 1, puzzle.max_attempts + 2):
            status, failed, _ = _attempt(restarted, root, puzzle, "a plain wrong guess")
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
        status, solved, _ = _attempt(restarted, root, puzzle, puzzle.answer, key=accounts[1])
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
    assert output.rstrip().endswith("Failed.")
    assert puzzle.attempts == 2 and puzzle.failed
