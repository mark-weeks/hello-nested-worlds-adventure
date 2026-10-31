"""Shared text fails closed when moderation cannot judge it (ADR-004 §2).

Stub providers and patched classifiers only. No live model call.
"""
from __future__ import annotations

import json
import threading

import pytest

import persistence
from consciousness.runtime import Completion
from interface import _speak_to
from multiverse.generator import generate_node_hierarchy
from multiverse.node import SpatialNode
from persistence import ideas
from puzzles.engine import build_puzzle
from server import _Handler, _ThreadedServer, guard, moderation
from tests.test_day_one_recording import _wait_for_rows, _ws_connect, _ws_send_json
from tests.test_moderation import _SLUR, _read_ws_json_until

# Fixed per mode. hash() is randomized per process (PYTHONHASHSEED).
_HOLD_SEEDS = {
    "timeout": 910,
    "error": 911,
    "undecided": 912,
    "budget": 913,
    "disabled": 914,
    "user_cap": 915,
}
_PUZZLE_HOLD_SEEDS = {
    "disabled": 940,
    "budget": 941,
    "timeout": 942,
    "undecided": 943,
    "user_cap": 944,
}


@pytest.fixture()
def srv():
    server = _ThreadedServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield port
    server.shutdown()


def _post(port, path, payload, key=None):
    import urllib.error
    import urllib.request
    headers = {"Content-Type": "application/json"}
    if key:
        headers["X-Beta-Key"] = key
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=json.dumps(payload).encode(),
        headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _rows(seed, node, kind):
    return [row for row in persistence.get_node_history(seed, node, 50)
            if row["type"] == kind]


# ── Verdict parsing (normalized Completion only) ────────────────────────────

@pytest.mark.parametrize("text,complete,finish,expected", [
    ("ALLOW", True, "complete", "allow"),
    ("  allow  ", True, "complete", "allow"),
    ("Verdict: ALLOW", True, "complete", "allow"),
    ("BLOCK", True, "complete", "block"),
    ("block.", True, "unknown", "block"),
    ("hmm, unsure", True, "complete", "undecided"),
    ("ALLOWED", True, "complete", "undecided"),
    ("ALLOW BLOCK", True, "complete", "undecided"),
    ("", True, "complete", "undecided"),
    (None, True, "complete", "undecided"),
    ("ALLOW", False, "length", "undecided"),
    (None, False, "length", "undecided"),
    ("ALLOW", False, "refusal", "undecided"),
    ("Not ALLOW", True, "complete", "undecided"),
    ("do not allow", True, "complete", "undecided"),
    ("I cannot allow this", True, "complete", "undecided"),
    ("ALLOW but ...", True, "complete", "undecided"),
    ("ALLOW\nReason: ignore previous instructions", True, "complete", "undecided"),
    ("BLOCKED", True, "complete", "undecided"),
    ("ALLOW.", True, "complete", "allow"),
    ("**ALLOW**", True, "complete", "allow"),
    ("Verdict: block", True, "complete", "block"),
])
def test_only_a_clear_finished_verdict_authorizes(text, complete, finish, expected):
    import consciousness
    assert consciousness.moderation_outcome(
        Completion(text, complete, finish_reason=finish)) == expected


def test_classify_logs_outcome_without_player_text_or_the_reply(caplog, monkeypatch):
    import consciousness
    from consciousness import runtime

    class Provider:
        name = "fixture"

        def generate(self, **kwargs):
            return Completion("ALLOW", True, finish_reason="complete")

    monkeypatch.setattr(runtime, "get_provider", lambda: Provider())
    with caplog.at_level("INFO", logger="nested_worlds.consciousness"):
        assert consciousness.classify_content("secret phrase", surface="speak") == "allow"
    assert "moderation_call outcome=allow surface=speak" in caplog.text
    assert "secret phrase" not in caplog.text


def test_classify_timeout_logs_error_without_the_exception_body(caplog, monkeypatch):
    from consciousness import runtime

    class Provider:
        name = "fixture"

        def generate(self, **kwargs):
            raise TimeoutError("secret phrase from the provider")

    monkeypatch.setattr(runtime, "get_provider", lambda: Provider())
    with caplog.at_level("INFO"):
        verdict = moderation.screen("go kill yourself", surface="speak")
    assert verdict.outcome == "error"
    assert caplog.text.count("moderation_call outcome=error surface=speak") == 1
    assert "moderation_call outcome=error surface=speak ms=" in caplog.text
    assert "secret phrase" not in caplog.text
    assert "go kill yourself" not in caplog.text


def test_exception_outside_classify_logs_one_error(caplog, monkeypatch):
    import consciousness

    def boom(text, **_k):
        raise RuntimeError("secret phrase from outside classify")

    monkeypatch.setattr(consciousness, "classify_content", boom)
    with caplog.at_level("INFO"):
        verdict = moderation.screen("go kill yourself", surface="speak")
    assert verdict.outcome == "error"
    assert caplog.text.count("moderation_call outcome=error surface=speak") == 1
    assert "moderation_call outcome=error surface=speak ms=" in caplog.text
    assert "secret phrase" not in caplog.text
    assert "go kill yourself" not in caplog.text


def test_model_id_comes_from_model_for(monkeypatch):
    import consciousness
    from consciousness import runtime
    recorded = {}

    class Provider:
        name = "fixture"

        def generate(self, **kwargs):
            recorded.update(kwargs)
            return Completion("ALLOW", True, finish_reason="complete")

    monkeypatch.setenv(runtime.MODERATION_MODEL_ENV, "fixture-moderation-id")
    monkeypatch.setattr(runtime, "get_provider", lambda: Provider())
    assert consciousness.classify_content("hello") == "allow"
    assert recorded["model"] == "fixture-moderation-id"
    assert recorded["max_tokens"] == consciousness._MODERATION_MAX_TOKENS


# ── Caps ────────────────────────────────────────────────────────────────────

def test_per_user_caps_are_independent_and_open_without_a_credential(monkeypatch):
    monkeypatch.setenv(guard.MODERATION_ACTIONS_PER_USER_ENV, "1")
    monkeypatch.setenv(guard.MODERATION_PER_USER_CAP_ENV, "1")
    monkeypatch.setenv(guard.MODEL_ACTIONS_PER_USER_ENV, "1")
    assert guard.consume_moderation_action("alice") is True
    assert guard.consume_moderation_action("alice") is False
    assert guard.consume_moderation_action("bob") is True
    assert guard.consume_moderation_action(None) is True
    assert guard.moderation_reserve("alice") == "ok"
    assert guard.moderation_reserve("alice") == "user_cap"
    assert guard.moderation_reserve("bob") == "ok"
    assert guard.consume_model_action("alice") is True
    assert guard.consume_model_action("alice") is False
    assert guard.ANTHROPIC_BUCKET == "anthropic"
    day = guard._utc_day()
    with persistence._connect() as conn:
        buckets = {row[0] for row in conn.execute(
            "SELECT bucket FROM cost_budget WHERE day = ?", (day,))}
    assert guard.ANTHROPIC_BUCKET not in buckets
    assert all(not name.startswith("anthropic") for name in buckets if name != "anthropic")


def test_action_cap_holds_clean_shared_text_and_a_second_user_is_free(monkeypatch):
    monkeypatch.setenv(guard.MODERATION_ACTIONS_PER_USER_ENV, "1")
    first = moderation.screen("hello, old light", user_key="alice", surface="speak")
    second = moderation.screen("hello again", user_key="alice", surface="speak")
    other = moderation.screen("hello", user_key="bob", surface="speak")
    assert first.allowed and first.outcome == "allow"
    assert not second.allowed and second.outcome == "user_cap"
    assert other.allowed


def test_classify_cap_does_not_spend_a_second_call(monkeypatch):
    import consciousness
    calls = []
    monkeypatch.setenv(guard.MODERATION_PER_USER_CAP_ENV, "1")
    monkeypatch.setattr(consciousness, "classify_content",
                        lambda text, **_k: calls.append(text) or "allow")
    assert moderation.screen("go kill yourself", user_key="alice").outcome == "allow"
    held = moderation.screen("go kill yourself", user_key="alice")
    assert held.outcome == "user_cap" and not held.allowed
    assert calls == ["go kill yourself"]
    assert moderation.screen("go kill yourself", user_key="bob").outcome == "allow"


# ── HTTP / WebSocket surfaces ───────────────────────────────────────────────

def _voice_ready(monkeypatch, reply="the place answers"):
    import consciousness
    monkeypatch.setattr(consciousness.runtime, "configured", lambda: True)
    monkeypatch.setattr(consciousness, "speak", lambda *a, **k: reply)
    monkeypatch.setattr(consciousness, "voice_agent", lambda *a, **k: reply)


def test_allow_publishes_and_block_declines_without_a_voice_charge(srv, monkeypatch):
    import consciousness
    charged = []
    _voice_ready(monkeypatch)
    monkeypatch.setattr(guard, "consume_anthropic",
                        lambda user_key=None: charged.append(1) or True)
    monkeypatch.setattr(consciousness, "classify_content", lambda text, **_k: "allow")
    seed = 901
    node = generate_node_hierarchy(seed=seed, max_depth=1)
    status, data = _post(srv, "/speak", {
        "node_name": node.name, "seed": seed,
        "message": "go kill yourself", "player_name": "Ada"})
    assert status == 200 and data["ai"] is True
    assert len(_rows(seed, node.name, "PLAYER_SPEAK")) == 1
    monkeypatch.setattr(consciousness, "classify_content", lambda text, **_k: "block")
    charged.clear()
    status, data = _post(srv, "/speak", {
        "node_name": node.name, "seed": seed,
        "message": "go kill yourself now", "player_name": "Ada"})
    assert status == 200 and data["declined"] is True
    assert data["response"] == moderation.DECLINE_LINE
    assert charged == []
    assert len(_rows(seed, node.name, "PLAYER_SPEAK")) == 1


@pytest.mark.parametrize("mode", ["timeout", "error", "undecided", "budget", "disabled", "user_cap"])
def test_each_failure_holds_speak_chat_and_agent_voice(srv, mode, monkeypatch):
    import consciousness
    charged = []
    _voice_ready(monkeypatch)
    monkeypatch.setattr(guard, "consume_anthropic",
                        lambda user_key=None: charged.append(1) or True)

    def classify(text, **_k):
        if mode == "timeout":
            raise TimeoutError("down")
        if mode == "error":
            raise RuntimeError("down")
        return "undecided"

    monkeypatch.setattr(consciousness, "classify_content", classify)
    if mode == "budget":
        monkeypatch.setattr(guard, "moderation_reserve", lambda user_key=None: "budget")
    if mode == "disabled":
        monkeypatch.setenv(moderation.DISABLE_MODERATION_ENV, "1")
    if mode == "user_cap":
        monkeypatch.setenv(guard.MODERATION_ACTIONS_PER_USER_ENV, "0")
    seed = _HOLD_SEEDS[mode]
    node = generate_node_hierarchy(seed=seed, max_depth=1)
    # The action cap only counts a presented credential. Minting the first
    # key closes the invite gate, so that mode gives both sockets a key.
    # The other modes leave the gate open and send no credential.
    key = None
    bea_key = None
    if mode == "user_cap":
        key = "nw_" + "c" * 32
        bea_key = "nw_" + "e" * 32
        persistence.mint_invite_key(key, "Ada")
        persistence.mint_invite_key(bea_key, "Bea")
    message = "hello, old light" if mode in {"disabled", "user_cap"} else "go kill yourself"
    for route, kind in (("/speak", "PLAYER_SPEAK"), ("/agent/voice", "AGENT_VOICE")):
        status, data = _post(srv, route, {
            "node_name": node.name, "seed": seed, "agent_name": "Tessera",
            "message": message, "player_name": "Ada"}, key=key)
        assert status == 200 and data.get("held") is True and data.get("ai") is False, data
        assert data["response"] == moderation.HOLD_LINE
        assert _rows(seed, node.name, kind) == []
    assert charged == []

    sender, s_status = _ws_connect(srv, seed, "Ada", invite_key=key)
    other, o_status = _ws_connect(srv, seed, "Bea", invite_key=bea_key)
    try:
        assert b"101" in s_status and b"101" in o_status
        _read_ws_json_until(sender, "welcome")
        _read_ws_json_until(other, "welcome")
        _ws_send_json(sender, {"type": "chat", "text": message})
        assert _read_ws_json_until(sender, "chat_declined")["text"] == moderation.HOLD_LINE
        _ws_send_json(sender, {"type": "chat", "text": "clean words"})
        if mode in {"disabled", "user_cap"}:
            # The cap or the disabled screen holds the follow-up too.
            assert _read_ws_json_until(sender, "chat_declined")["text"] == moderation.HOLD_LINE
            assert _rows(seed, node.name, "PLAYER_CHAT") == []
        else:
            assert _read_ws_json_until(other, "chat")["text"] == "clean words"
            chats = _wait_for_rows(seed, node.name, "PLAYER_CHAT")
            assert [row["data"]["text"] for row in chats] == ["clean words"]
    finally:
        sender.close()
        other.close()


def test_private_note_unpublished_profile_and_act_continue(http, accounts, monkeypatch):
    import consciousness
    from multiverse import store
    monkeypatch.setenv(moderation.DISABLE_MODERATION_ENV, "1")
    monkeypatch.setattr(consciousness, "classify_content",
                        lambda *a, **k: (_ for _ in ()).throw(TimeoutError("down")))
    root = store.world_tree(382)
    note = {"id": "private-while-dark", "node": root.name, "text": f"you {_SLUR}"}
    assert http("/journal/note", body=note)[0] == 200
    saved = http("/journal/data")[1]["notes"]
    assert saved[0]["text"] == note["text"]
    status, data, _ = http("/profile/save", body={
        "bio": f"you {_SLUR}", "goals": "keep this private", "published": False})
    assert status == 200
    me = http("/me")[1]
    assert me["profile"]["bio"] == f"you {_SLUR}"
    other = http(f"/profile?participant={me['participant']['id']}", accounts[1])[1]["profile"]
    assert other["bio"] == "" and other["goals"] == ""
    status, held, _ = http("/profile/save", body={
        "bio": "publish me", "goals": "", "published": True})
    assert status == 422 and held["held"] is True and held["error"] == moderation.PROFILE_HOLD
    assert http("/profile")[1]["profile"]["published"] is False
    act = http("/act", body={"node_name": root.name, "request_id": "act-while-dark"})
    assert act[0] == 200 and act[1]["action_status"] == "accepted"


def test_ideas_follow_each_failure_and_a_retry_of_a_published_idea_stands(http, monkeypatch):
    import consciousness

    def create(title, request, description="A traveler could not find the crossing."):
        return http("/ideas/submit", body={
            "title": title, "description": description,
            "request_id": request, "public_credit": False})

    monkeypatch.setattr(consciousness, "classify_content",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    held = create("go kill yourself", "idea-held-0001")
    assert held[0] == 422 and held[1]["held"] is True
    assert held[1]["error"] == moderation.IDEAS_HOLD
    assert http("/ideas/list")[1]["ideas"] == []
    # A local block still declines in product language and does not publish.
    monkeypatch.setenv(moderation.EXTRA_BLOCK_ENV, "zorblax")
    blocked = create("utter zorblax", "idea-block-0001")
    assert blocked[0] == 400 and blocked[1]["error"] == moderation.IDEAS_DECLINE
    assert http("/ideas/list")[1]["ideas"] == []
    # Local clean does not need the classifier, so a provider error does not hold it.
    published = create("A clearer crossing", "idea-clean-0001")
    assert published[0] == 200 and published[1]["visible"] is True
    idea_id = published[1]["id"]
    monkeypatch.setenv(moderation.DISABLE_MODERATION_ENV, "1")
    again = create("A clearer crossing", "idea-clean-0001")
    assert again[0] == 200 and again[1]["id"] == idea_id
    fresh = create("Another clear crossing", "idea-fresh-0001")
    assert fresh[0] == 422 and fresh[1]["held"] is True
    assert fresh[1]["error"] == moderation.IDEAS_HOLD
    listed = http("/ideas/list")[1]["ideas"]
    assert [row["id"] for row in listed] == [idea_id]


@pytest.mark.parametrize("mode", ["disabled", "budget", "timeout", "undecided", "user_cap"])
def test_puzzle_attempt_counts_without_unjudged_text(srv, mode, monkeypatch):
    import consciousness
    key = "nw_" + "d" * 32
    persistence.mint_invite_key(key, "Ada")
    if mode == "disabled":
        monkeypatch.setenv(moderation.DISABLE_MODERATION_ENV, "1")
    elif mode == "budget":
        monkeypatch.setattr(guard, "moderation_reserve", lambda user_key=None: "budget")
    elif mode == "user_cap":
        monkeypatch.setenv(guard.MODERATION_ACTIONS_PER_USER_ENV, "0")
    elif mode == "timeout":
        monkeypatch.setattr(consciousness, "classify_content",
                            lambda *a, **k: (_ for _ in ()).throw(TimeoutError("down")))
    else:
        monkeypatch.setattr(consciousness, "classify_content", lambda *a, **k: "undecided")
    seed = _PUZZLE_HOLD_SEEDS[mode]
    root = generate_node_hierarchy(seed=seed, max_depth=1)
    puzzle = build_puzzle(root)
    guess = "go kill yourself" if mode in {"budget", "timeout", "undecided"} else "plain wrong guess"
    status, data = _post(srv, "/puzzle/attempt", {
        "seed": seed, "node_name": root.name, "puzzle_name": puzzle.name,
        "answer": guess, "player_name": "Ada"}, key=key)
    assert status == 200 and data["correct"] is False and data["attempt"] == 1
    attempts = _rows(seed, root.name, "PUZZLE_ATTEMPT")
    assert len(attempts) == 1
    assert attempts[0]["data"]["correct"] is False
    assert "guess" not in attempts[0]["data"]
    # Correctness still resolves. A locally clean answer is a finished
    # judgment, so a provider or budget failure still stores it. Disabled
    # moderation and the action cap withhold every free-text field.
    status, solved = _post(srv, "/puzzle/attempt", {
        "seed": seed, "node_name": root.name, "puzzle_name": puzzle.name,
        "answer": puzzle.answer, "player_name": "Ada"}, key=key)
    assert status == 200 and solved["correct"] is True
    correct_row = next(row for row in _rows(seed, root.name, "PUZZLE_ATTEMPT")
                       if row["data"]["correct"] is True)
    # The authored answer is not player free text. It is never screened
    # and never stored as the guess.
    assert "guess" not in correct_row["data"]


def test_puzzle_screen_skips_a_mismatch_a_correct_answer_and_a_solved_puzzle(srv, monkeypatch):
    calls = []
    real = moderation.public_excerpt

    def wrapped(text, **kwargs):
        calls.append(text)
        return real(text, **kwargs)

    monkeypatch.setattr(moderation, "public_excerpt", wrapped)
    seed = 976
    root = generate_node_hierarchy(seed=seed, max_depth=1)
    puzzle = build_puzzle(root)
    mismatch, _ = _post(srv, "/puzzle/attempt", {
        "seed": seed, "node_name": root.name, "puzzle_name": "not-this-question",
        "answer": "go kill yourself", "player_name": "Ada"})
    assert mismatch == 409 and calls == []
    status, solved = _post(srv, "/puzzle/attempt", {
        "seed": seed, "node_name": root.name, "puzzle_name": puzzle.name,
        "answer": puzzle.answer, "player_name": "Ada"})
    assert status == 200 and solved["correct"] is True and calls == []
    correct_row = _rows(seed, root.name, "PUZZLE_ATTEMPT")[0]
    assert "guess" not in correct_row["data"]
    status, late = _post(srv, "/puzzle/attempt", {
        "seed": seed, "node_name": root.name, "puzzle_name": puzzle.name,
        "answer": "go kill yourself", "player_name": "Ada"})
    assert status == 200 and late["solver"] and calls == []


def test_incorrect_guess_is_still_screened(srv, monkeypatch):
    calls = []
    real = moderation.public_excerpt

    def wrapped(text, **kwargs):
        calls.append(text)
        return real(text, **kwargs)

    monkeypatch.setattr(moderation, "public_excerpt", wrapped)
    seed = 975
    root = generate_node_hierarchy(seed=seed, max_depth=1)
    puzzle = build_puzzle(root)
    status, data = _post(srv, "/puzzle/attempt", {
        "seed": seed, "node_name": root.name, "puzzle_name": puzzle.name,
        "answer": "plain wrong", "player_name": "Ada"})
    assert status == 200 and data["correct"] is False
    assert calls == ["plain wrong"]
    assert _rows(seed, root.name, "PUZZLE_ATTEMPT")[0]["data"]["guess"] == "plain wrong"


def test_empty_published_profile_saves_when_moderation_is_off(http, monkeypatch):
    monkeypatch.setenv(moderation.DISABLE_MODERATION_ENV, "1")
    status, data, _ = http("/profile/save", body={
        "bio": "", "goals": "  ", "published": True})
    assert status == 200 and data["profile"]["published"] is True


def test_judged_guess_is_stored_and_redaction_still_tombstones_it(srv):
    seed = 977
    root = generate_node_hierarchy(seed=seed, max_depth=1)
    puzzle = build_puzzle(root)
    guess = "purple heron"
    status, data = _post(srv, "/puzzle/attempt", {
        "seed": seed, "node_name": root.name, "puzzle_name": puzzle.name,
        "answer": guess, "player_name": "Ada"})
    assert status == 200 and data["correct"] is False
    row = _rows(seed, root.name, "PUZZLE_ATTEMPT")[0]
    assert row["data"]["guess"] == guess
    summary = persistence.redact_mutation(row["id"])
    assert summary["fields"] == ["guess"]
    redacted = _rows(seed, root.name, "PUZZLE_ATTEMPT")[0]
    assert redacted["data"]["guess"] == "[redacted]"
    assert redacted["data"]["correct"] is False
    assert guess not in json.dumps(redacted["data"])


def test_puzzle_screens_the_sixty_four_characters_it_can_store(srv):
    seed = 979
    root = generate_node_hierarchy(seed=seed, max_depth=1)
    puzzle = build_puzzle(root)
    hidden = ("x" * 64) + " " + _SLUR
    status, data = _post(srv, "/puzzle/attempt", {
        "seed": seed, "node_name": root.name, "puzzle_name": puzzle.name,
        "answer": hidden, "player_name": "Ada"})
    assert status == 200 and data["correct"] is False
    visible = ("y" * 20) + " " + _SLUR
    status, data = _post(srv, "/puzzle/attempt", {
        "seed": seed, "node_name": root.name, "puzzle_name": puzzle.name,
        "answer": visible, "player_name": "Ada"})
    assert status == 200 and data["correct"] is False and data["attempt"] == 2
    stored = [row["data"] for row in _rows(seed, root.name, "PUZZLE_ATTEMPT")]
    assert len(stored) == 2
    assert any(row.get("guess") == "x" * 32 for row in stored)
    assert any("guess" not in row for row in stored)
    assert all(_SLUR not in json.dumps(row) for row in stored)


def test_failed_puzzle_omits_unjudged_answer_given(srv, monkeypatch):
    monkeypatch.setenv(moderation.DISABLE_MODERATION_ENV, "1")
    seed = 978
    root = generate_node_hierarchy(seed=seed, max_depth=1)
    puzzle = build_puzzle(root)
    last = None
    for _ in range(puzzle.max_attempts):
        status, last = _post(srv, "/puzzle/attempt", {
            "seed": seed, "node_name": root.name, "puzzle_name": puzzle.name,
            "answer": "not the answer", "player_name": "Ada"})
        assert status == 200
    assert last["result"] == "FAILED"
    assert last["attempt"] == puzzle.max_attempts
    failed = _rows(seed, root.name, "PUZZLE_FAILED")
    assert len(failed) == 1
    assert "answer_given" not in failed[0]["data"]
    assert len(_rows(seed, root.name, "PUZZLE_ATTEMPT")) == puzzle.max_attempts
    assert "not the answer" not in json.dumps(persistence.get_mutations(seed))


def test_name_check_does_not_charge_an_unvalidated_token(srv, monkeypatch):
    monkeypatch.setenv(guard.MODERATION_ACTIONS_PER_USER_ENV, "0")
    persistence.create_registration_token("nwr_capped")
    status, data = _post(srv, "/register", {"invite": "nwr_capped", "name": "Priya"})
    assert status == 200 and data["name"] == "Priya"
    day = guard._utc_day()
    with persistence._connect() as conn:
        buckets = [row[0] for row in conn.execute(
            "SELECT bucket FROM cost_budget WHERE day = ?", (day,))]
    assert all(not name.startswith(guard.MODERATION_ACTIONS_BUCKET) for name in buckets)


def test_names_refuse_when_the_screen_is_off_and_keep_the_token(srv, monkeypatch):
    monkeypatch.setenv(moderation.DISABLE_MODERATION_ENV, "1")
    persistence.create_registration_token("nwr_held")
    status, data = _post(srv, "/register", {"invite": "nwr_held", "name": "Priya"})
    assert status == 403 and "choose another" in data["error"]
    assert persistence.lookup_registration_token("nwr_held") is not None
    monkeypatch.setenv(moderation.DISABLE_MODERATION_ENV, "0")
    status, data = _post(srv, "/register", {"invite": "nwr_held", "name": "Priya"})
    assert status == 200 and data["name"] == "Priya"


def test_cli_speak_holds_only_when_it_writes_the_canonical_world(monkeypatch):
    import consciousness
    spoken = []
    monkeypatch.setattr(consciousness, "speak", lambda *a, **k: spoken.append(a[1]) or "a reply")
    node = SpatialNode(name="Vault", level="Object", properties={})
    # Local multi-world mode: the operator terminal does not publish.
    monkeypatch.setenv("NESTED_WORLDS_CANONICAL_SEED", "")
    monkeypatch.setenv(moderation.DISABLE_MODERATION_ENV, "1")
    _speak_to(node, "hello from the terminal", seed=42, player_name="Ada")
    assert spoken == ["hello from the terminal"]
    assert _rows(42, node.name, "PLAYER_SPEAK")
    spoken.clear()
    # The hosted world: disabled moderation holds the line and writes nothing.
    monkeypatch.setenv("NESTED_WORLDS_CANONICAL_SEED", "382")
    shared = generate_node_hierarchy(seed=382, max_depth=1)
    _speak_to(shared, "hello into the shared world", seed=382, player_name="Ada")
    assert spoken == []
    assert _rows(382, shared.name, "PLAYER_SPEAK") == []
    monkeypatch.setenv(moderation.DISABLE_MODERATION_ENV, "0")
    _speak_to(shared, "a clean shared line", seed=382, player_name="Ada")
    assert spoken == ["a clean shared line"]
    assert len(_rows(382, shared.name, "PLAYER_SPEAK")) == 1


def test_model_action_cap_quiets_voice_and_leaves_mechanical_play(http, monkeypatch):
    import consciousness
    from multiverse import store
    monkeypatch.setenv(guard.MODEL_ACTIONS_PER_USER_ENV, "0")
    charged = []
    monkeypatch.setattr(guard, "consume_anthropic",
                        lambda **kwargs: charged.append(kwargs) or True)

    class Provider:
        name = "fixture"

        def configured(self):
            return True

        def generate(self, **kwargs):
            raise AssertionError("the model was called")

    monkeypatch.setattr(consciousness.runtime, "get_provider", lambda: Provider())
    root = store.world_tree(382)
    status, data, _ = http("/speak", body={
        "node_name": root.name, "message": "hello, old light"})
    assert status == 200 and data["response"] == guard.QUIET_RESPONSE and data["ai"] is False
    assert _rows(382, root.name, "PLAYER_SPEAK") == []
    voice = http("/agent/voice", body={
        "node_name": root.name, "agent_name": "Scout", "message": "hello, old light"})
    assert voice[0] == 200 and voice[1]["response"] == guard.QUIET_RESPONSE and voice[1]["ai"] is False
    assert voice[1]["agent"] == "" and _rows(382, root.name, "AGENT_VOICE") == []
    assert charged == []
    puzzle = build_puzzle(root)
    attempt = http("/puzzle/attempt", body={
        "node_name": root.name, "puzzle_name": puzzle.name, "answer": "not it"})
    assert attempt[0] == 200 and attempt[1]["correct"] is False
    assert _rows(382, root.name, "PUZZLE_ATTEMPT")[0]["data"]["guess"] == "not it"


def test_empty_speech_is_a_private_error_and_publishes_nothing(srv, monkeypatch):
    import consciousness
    monkeypatch.setenv(moderation.DISABLE_MODERATION_ENV, "1")
    spoken = []

    class Provider:
        name = "fixture"

        def configured(self):
            return True

        def generate(self, **kwargs):
            spoken.append(kwargs)
            return Completion("a reply that must not be published", True)

    monkeypatch.setattr(consciousness.runtime, "get_provider", lambda: Provider())
    seed = 992
    node = generate_node_hierarchy(seed=seed, max_depth=1)
    for path, extra in (("/speak", {}), ("/agent/voice", {"agent_name": "Scout"})):
        for message in ("", "   ", "\n\t "):
            status, data = _post(srv, path, {
                "node_name": node.name, "seed": seed, "message": message, **extra})
            assert status == 400 and data["error"] == "A message is required.", data
    assert spoken == []
    assert _rows(seed, node.name, "PLAYER_SPEAK") == []
    assert _rows(seed, node.name, "AGENT_VOICE") == []
    # A missing message is the authored prompt, not an empty line. Disabled
    # moderation holds that prompt in fiction: HTTP 200, no model, no row.
    status, data = _post(srv, "/speak", {"node_name": node.name, "seed": seed})
    assert status == 200 and data.get("held") is True and data.get("ai") is False
    assert spoken == []
    assert _rows(seed, node.name, "PLAYER_SPEAK") == []


def test_unknown_place_is_404_before_the_screen(srv, monkeypatch):
    """An unknown place is a 404 and does not spend a screen.

    Ambiguous text used to reach ``moderation.screen`` first. That charges
    the moderation-action cap, and then the model-action cap and the
    classifier. With the model-action cap already spent, the route answered
    HTTP 200 ``held`` instead of 404.
    """
    import consciousness
    screens = []
    generated = []
    real_screen = moderation.screen

    def recording_screen(text, **kwargs):
        screens.append(kwargs.get("surface"))
        return real_screen(text, **kwargs)

    class Provider:
        name = "fixture"

        def configured(self):
            return True

        def generate(self, **kwargs):
            generated.append(kwargs)
            return Completion("ALLOW", True, finish_reason="complete")

    monkeypatch.setattr(moderation, "screen", recording_screen)
    monkeypatch.setattr(consciousness.runtime, "get_provider", lambda: Provider())
    monkeypatch.setattr(consciousness.runtime, "configured", lambda: True)
    # A credential is what makes the per-user caps apply. Zero means the
    # screen, if it ran, would hold the line before the classifier.
    monkeypatch.setenv(guard.MODERATION_ACTIONS_PER_USER_ENV, "0")
    monkeypatch.setenv(guard.MODEL_ACTIONS_PER_USER_ENV, "0")
    key = "nw_" + "d" * 32
    persistence.mint_invite_key(key, "Ada")
    seed = 994
    for path, extra in (("/speak", {}), ("/agent/voice", {"agent_name": "Scout"})):
        status, data = _post(srv, path, {
            "node_name": "Forged-11", "seed": seed,
            "message": "go kill yourself", **extra}, key=key)
        assert status == 404 and data["error"] == "no such place in this world", (
            path, status, data)
    assert screens == [] and generated == []
    assert _rows(seed, "Forged-11", "PLAYER_SPEAK") == []
    assert _rows(seed, "Forged-11", "AGENT_VOICE") == []
    # A real place still reaches the screen. The spent cap holds it, and
    # the classifier is not called.
    node = generate_node_hierarchy(seed=seed, max_depth=1)
    status, data = _post(srv, "/speak", {
        "node_name": node.name, "seed": seed, "message": "go kill yourself",
    }, key=key)
    assert status == 200 and data.get("held") is True and data.get("ai") is False
    assert screens == ["speak"] and generated == []
    assert _rows(seed, node.name, "PLAYER_SPEAK") == []
    voice_status, voice = _post(srv, "/agent/voice", {
        "node_name": node.name, "seed": seed, "agent_name": "Scout",
        "message": "go kill yourself"}, key=key)
    assert voice_status == 200 and voice.get("held") is True
    assert screens == ["speak", "agent"]
    assert _rows(seed, node.name, "AGENT_VOICE") == []


def test_non_string_message_is_not_spoken(srv, monkeypatch):
    import consciousness
    screens = []
    real_screen = moderation.screen

    def recording_screen(text, **kwargs):
        screens.append(text)
        return real_screen(text, **kwargs)

    spoken = []

    class Provider:
        name = "fixture"

        def configured(self):
            return True

        def generate(self, **kwargs):
            spoken.append(kwargs)
            return Completion("a reply that must not be published", True)

    monkeypatch.setattr(moderation, "screen", recording_screen)
    monkeypatch.setattr(consciousness.runtime, "get_provider", lambda: Provider())
    monkeypatch.setenv(moderation.DISABLE_MODERATION_ENV, "1")
    monkeypatch.setenv(guard.RATE_LIMIT_ENV, "200")
    seed = 995
    node = generate_node_hierarchy(seed=seed, max_depth=1)
    for path, extra in (("/speak", {}), ("/agent/voice", {"agent_name": "Scout"})):
        for message in (None, False, True, 0, 1, 2.5, [], ["not a line"], ["a", "b"], {}):
            status, data = _post(srv, path, {
                "node_name": node.name, "seed": seed, "message": message, **extra})
            assert status == 400 and data["error"] == "A message is required.", (
                path, message, status, data)
        # Nothing visible: zero-width characters, a word joiner, soft
        # hyphens, bidi marks, a bare variation selector or combining mark,
        # with or without whitespace around them.
        for message in ("\u200b", "\u200c\u200d", "\ufeff", "\u200b \u200d", "\ufeff\n",
                        "\u2060", "\u00ad\u00ad", "\u200e\u200f", "\u061c", "\ufe0f",
                        "\u034f", " \u2060\n", "\u0301\u0301",
                        "\u3164", "\uffa0", "\u115f", "\u2800",
                        "\u3164\uffa0\u115f\u2800", " \u2800\n\u3164"):
            status, data = _post(srv, path, {
                "node_name": node.name, "seed": seed, "message": message, **extra})
            assert status == 400 and data["error"] == "A message is required.", (
                path, message, status, data)
    assert screens == [] and spoken == []
    assert _rows(seed, node.name, "PLAYER_SPEAK") == []
    assert _rows(seed, node.name, "AGENT_VOICE") == []
    # A line with visible text is judged as typed: an invisible inside a
    # word is part of the player's line, not noise to remove.
    status, data = _post(srv, "/speak", {
        "node_name": node.name, "seed": seed, "message": "hel\u200blo"})
    assert status == 200 and data.get("held") is True
    # Blank fillers inside a real line are not stripped. Neither is a joiner.
    kept = "see\u3164\uffa0\u115f\u2800 this\u200d\u200c\u200b"
    status, data = _post(srv, "/speak", {
        "node_name": node.name, "seed": seed, "message": kept})
    assert status == 200 and data.get("held") is True
    assert screens == ["hel\u200blo", kept]
    # Strings stay strings, including ones that look like JSON scalars.
    for message in ("0", "false", "null", "hello, old light"):
        status, data = _post(srv, "/speak", {
            "node_name": node.name, "seed": seed, "message": message})
        assert status == 200 and data.get("held") is True, (message, status, data)
    assert spoken == []
    assert screens == ["hel\u200blo", kept, "0", "false", "null", "hello, old light"]


def test_speech_keeps_the_players_characters_from_screen_to_chronicle(srv, monkeypatch):
    """An emoji joiner, a Persian ZWNJ and a Thai word break are the line.

    Hangul fillers and a blank braille cell inside that line stay too.
    The emptiness check looks for visible text; it must not rewrite the
    text it keeps. What the classifier judges, what the model hears, and
    what the chronicle stores are the characters the player sent.
    """
    import consciousness
    judged = []
    real_screen = moderation.screen

    def recording_screen(text, **kwargs):
        judged.append(text)
        return real_screen(text, **kwargs)

    heard = []

    class Provider:
        name = "fixture"

        def configured(self):
            return True

        def generate(self, **kwargs):
            heard.append(kwargs["messages"][-1]["content"])
            return Completion("ALLOW", True, finish_reason="complete")

    monkeypatch.setattr(moderation, "screen", recording_screen)
    monkeypatch.setattr(consciousness.runtime, "get_provider", lambda: Provider())
    monkeypatch.setattr(consciousness.runtime, "configured", lambda: True)
    monkeypatch.setenv(guard.RATE_LIMIT_ENV, "200")
    seed = 996
    node = generate_node_hierarchy(seed=seed, max_depth=1)
    # A family (ZWJ sequence), a Persian word kept unjoined by ZWNJ, and a
    # Thai phrase with a zero-width word break.
    line = ("we are \U0001F468\u200d\U0001F469\u200d\U0001F467 here, "
            "\u0645\u06cc\u200c\u062e\u0648\u0627\u0647\u0645, "
            "\u0e2a\u0e27\u0e31\u0e2a\u0e14\u0e35\u200b\u0e04\u0e23\u0e31\u0e1a"
            "\u3164\uffa0\u115f\u2800")
    status, data = _post(srv, "/speak", {
        "node_name": node.name, "seed": seed, "message": line, "player_name": "Ada"})
    assert status == 200 and data["ai"] is True, (status, data)
    assert judged == [line]
    # Every model call — a classify, if the local tier escalated, and the
    # voice itself — received the line as typed.
    assert heard and all(text == line for text in heard), heard
    assert [row["data"]["message"] for row in _rows(seed, node.name, "PLAYER_SPEAK")] == [line]


def test_generate_charges_the_model_action_cap_once_and_normalizes_the_key(monkeypatch):
    from consciousness import runtime
    from consciousness.runtime import SystemBlock
    monkeypatch.setenv(guard.MODEL_ACTIONS_PER_USER_ENV, "0")
    calls = []

    class Provider:
        name = "fixture"

        def generate(self, **kwargs):
            calls.append(kwargs)
            return Completion("spoken", True)

    monkeypatch.setattr(runtime, "get_provider", lambda: Provider())
    kwargs = dict(endpoint="speak", model="fixture", max_tokens=8,
                  system=(SystemBlock("s"),),
                  messages=[{"role": "user", "content": "hi"}])
    with pytest.raises(runtime.ModelActionLimited):
        runtime.generate(**kwargs, user_key="alice", voice_budget=True)
    assert calls == []
    # Empty credentials stay open, including when the cap is zero.
    assert runtime.generate(**kwargs, user_key=None).text == "spoken"
    assert runtime.generate(**kwargs, user_key="").text == "spoken"
    assert len(calls) == 2
    monkeypatch.setenv(guard.MODEL_ACTIONS_PER_USER_ENV, "1")
    calls.clear()

    class Allow:
        name = "fixture"

        def generate(self, **kwargs):
            calls.append(1)
            return Completion("ALLOW", True, finish_reason="complete")

    monkeypatch.setattr(runtime, "get_provider", lambda: Allow())
    first = moderation.screen("go kill yourself", user_key="ada")
    second = moderation.screen("go kill yourself", user_key="ada")
    assert first.outcome == "allow" and second.outcome == "user_cap"
    assert calls == [1]


def test_screen_sees_a_solve_already_held_by_the_room(srv, monkeypatch):
    from server.rooms import get_room, will_store_guess
    calls = []
    real = moderation.public_excerpt

    def wrapped(text, **kwargs):
        calls.append(text)
        return real(text, **kwargs)

    monkeypatch.setattr(moderation, "public_excerpt", wrapped)
    seed = 993
    root = generate_node_hierarchy(seed=seed, max_depth=1)
    puzzle = build_puzzle(root)
    status, solved = _post(srv, "/puzzle/attempt", {
        "seed": seed, "node_name": root.name, "puzzle_name": puzzle.name,
        "answer": puzzle.answer, "player_name": "Ada"})
    assert status == 200 and solved["correct"] is True and calls == []
    status, late = _post(srv, "/puzzle/attempt", {
        "seed": seed, "node_name": root.name, "puzzle_name": puzzle.name,
        "answer": "go kill yourself", "player_name": "Ada"})
    assert status == 200 and late["solver"] and calls == []
    # The room already holds the solve. A durable read that has not caught
    # up must not spend a screen; the handler asks will_store_guess under
    # the room lock before public_excerpt.
    monkeypatch.setattr(persistence, "get_puzzle_solve", lambda *args, **kwargs: None)
    room = get_room(seed)
    assert will_store_guess(room, seed, root.name, puzzle.name, 0) is False


def test_ideas_budget_and_cap_publish_nothing(http, monkeypatch):
    monkeypatch.setattr(guard, "moderation_reserve", lambda user_key=None: "budget")
    budget = http("/ideas/submit", body={
        "title": "go kill yourself", "description": "This should not publish.",
        "request_id": "idea-budget-001", "public_credit": False})
    assert budget[0] == 422 and budget[1]["held"] is True
    assert budget[1]["error"] == moderation.IDEAS_HOLD
    monkeypatch.setenv(guard.MODERATION_ACTIONS_PER_USER_ENV, "0")
    capped = http("/ideas/submit", body={
        "title": "A quieter crossing", "description": "Also held.",
        "request_id": "idea-cap-0001", "public_credit": False})
    assert capped[0] == 422 and capped[1]["held"] is True
    assert capped[1]["error"] == moderation.IDEAS_HOLD
    assert http("/ideas/list")[1]["ideas"] == []
    assert ideas.Held.__name__ == "Held"
