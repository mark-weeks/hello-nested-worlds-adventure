"""Every shared line is classified on a hosted world (owner decisions of
2026-11-18, item 30; batch plan of 2026-11-20, C1).

A hosted world is marked by ``NESTED_WORLDS_REQUIRE_MODEL_POLICY=1`` or a
``NESTED_WORLDS_MODEL_POLICY`` file. There, a locally clean shared line on
Speak, agent voice, Ideas and a published profile still takes one classify
call, and is held when that call cannot be made or finish. Chat, puzzle
free text, CLI speech and names keep the local-first rule, and so does a
local world with neither marker.

The real HTTP routes are driven through the real openai_compatible adapter
with an authored fake transport. No request leaves the process.
"""
from __future__ import annotations

import json
import logging
import re

import pytest

import consciousness
import persistence
from consciousness import honesty, model_policy, runtime
from consciousness.openai_compat_provider import OpenAICompatibleProvider
from multiverse import store
from server import guard, moderation
from tests.test_model_control_outcomes import _MODEL, _policy_file, controlled  # noqa: F401
from tests.test_shared_text_fail_closed import _acknowledge_notice, srv  # noqa: F401

_SEED = 382  # the canonical world the ``http`` fixture serves
_AGENT = "Tessera"
_CLEAN = "hello, old light"
_VOICE_REPLY = "A bell sounds."


def _is_classify(request) -> bool:
    body = json.loads(request.body)
    system = " ".join(str(m.get("content", "")) for m in body.get("messages", [])
                      if m.get("role") == "system")
    is_moderation = "content-safety classifier" in system
    # Both detections must agree: the moderation call is the 32-token one.
    assert is_moderation == (body.get("max_completion_tokens") == 32), body
    return is_moderation


def _reply(content: str, model: str = _MODEL) -> tuple:
    return 200, (), json.dumps({
        "model": model,
        "choices": [{"finish_reason": "stop", "message": {"content": content}}],
        "usage": {"prompt_tokens": 10, "total_tokens": 12, "completion_tokens": 2,
                  "prompt_tokens_details": {"cached_tokens": 0}},
    }).encode()


@pytest.fixture
def hosted(controlled, http, accounts):  # noqa: F811
    """A hosted world (policy file) whose classifier answers ``state.verdict``.

    ``verdict`` is ALLOW, BLOCK, UNDECIDED or ``"unreachable"`` (the
    transport raises a timeout). Every other request is a voice reply.
    """
    state = controlled
    state.verdict = "ALLOW"
    state.classify = []
    state.voice = []

    def transport(request):
        state.requests.append(request)
        if _is_classify(request):
            state.classify.append(request)
            if state.verdict == "unreachable":
                raise TimeoutError("classifier unreachable")
            return _reply(state.verdict)
        state.voice.append(request)
        return _reply(_VOICE_REPLY)

    state.adapter = OpenAICompatibleProvider(transport=transport)
    assert moderation.every_line_required()
    state.http = http
    state.root = store.world_tree(_SEED)
    state.key = accounts[0]
    return state


# ── Route drivers ───────────────────────────────────────────────────────────

def _speak(state, message=_CLEAN):
    return state.http("/speak", body={
        "node_name": state.root.name, "seed": _SEED, "message": message,
        "player_name": "Ada"})[:2]


def _agent(state, message=_CLEAN, agent=_AGENT):
    return state.http("/agent/voice", body={
        "node_name": state.root.name, "seed": _SEED, "agent_name": agent,
        "message": message, "player_name": "Ada"})[:2]


def _idea(state, request_id, title="A clearer crossing"):
    return state.http("/ideas/submit", body={
        "title": title, "description": "A traveler could not find the crossing.",
        "request_id": request_id, "public_credit": False})[:2]


def _profile(state, bio="I map quiet rivers."):
    return state.http("/profile/save", body={
        "bio": bio, "goals": "find the hinge", "published": True})[:2]


def _rows(state, kind):
    return [row for row in persistence.get_node_history(_SEED, state.root.name, 50)
            if row["type"] == kind]


def _ideas(state):
    return state.http("/ideas/list")[1]["ideas"]


def _published(state):
    return state.http("/profile")[1]["profile"]["published"]


def _outcomes(caplog):
    """(surface, outcome) for each moderation_call line, in order."""
    found = []
    for record in caplog.records:
        match = re.fullmatch(r"moderation_call outcome=(\w+) surface=(\w+)(?: ms=\d+)?",
                             record.getMessage())
        if match:
            found.append((match.group(2), match.group(1)))
    return found


def _assert_held_everywhere(state, caplog, outcome):
    """A clean line is held on all four surfaces and nothing is published."""
    caplog.clear()
    caplog.set_level(logging.INFO)
    for route, kind in ((_speak, "PLAYER_SPEAK"), (_agent, "AGENT_VOICE")):
        status, data = route(state)
        assert status == 200, data
        assert data.get("held") is True and data["ai"] is False, data
        assert data["response"] == moderation.HOLD_LINE
        assert _rows(state, kind) == []
    status, data = _idea(state, "idea-held-every-1")
    assert status == 422 and data["held"] is True and data["error"] == moderation.IDEAS_HOLD
    status, data = _profile(state)
    assert status == 422 and data["held"] is True and data["error"] == moderation.PROFILE_HOLD
    assert _ideas(state) == []
    assert _published(state) is False
    assert state.voice == []
    assert _outcomes(caplog) == [(surface, outcome)
                                 for surface in ("speak", "agent", "ideas", "profile")]


# ── 1. ALLOW: one classify call per clean shared line ───────────────────────

def test_hosted_allow_classifies_each_clean_line_once_and_publishes(hosted):
    assert moderation._local_tier(_CLEAN) == "clean"

    status, data = _speak(hosted)
    assert status == 200 and data["ai"] is True and data["response"] == _VOICE_REPLY, data
    assert len(hosted.classify) == 1 and len(hosted.voice) == 1
    assert len(_rows(hosted, "PLAYER_SPEAK")) == 1

    status, data = _agent(hosted)
    assert status == 200 and data["ai"] is True and data["response"] == _VOICE_REPLY, data
    assert len(hosted.classify) == 2 and len(hosted.voice) == 2
    assert len(_rows(hosted, "AGENT_VOICE")) == 1

    status, data = _idea(hosted, "idea-allow-every-1")
    assert status == 200 and data["visible"] is True, data
    assert len(hosted.classify) == 3
    assert [row["id"] for row in _ideas(hosted)] == [data["id"]]

    status, data = _profile(hosted)
    assert status == 200 and data["profile"]["published"] is True, data
    assert len(hosted.classify) == 4
    assert _published(hosted) is True
    assert len(hosted.voice) == 2


# ── 2. BLOCK declines; UNDECIDED holds ──────────────────────────────────────

def test_hosted_block_verdict_declines_a_clean_line(hosted):
    hosted.verdict = "BLOCK"
    for route, kind in ((_speak, "PLAYER_SPEAK"), (_agent, "AGENT_VOICE")):
        status, data = route(hosted)
        assert status == 200 and data.get("declined") is True and data["ai"] is False, data
        assert data["response"] == moderation.DECLINE_LINE
        assert _rows(hosted, kind) == []
    status, data = _idea(hosted, "idea-block-every-1")
    assert status == 400 and data["error"] == moderation.IDEAS_DECLINE, data
    status, data = _profile(hosted)
    assert status == 400 and data["error"] == moderation.PROFILE_DECLINE, data
    assert len(hosted.classify) == 4
    assert hosted.voice == []
    assert _ideas(hosted) == [] and _published(hosted) is False


def test_hosted_undecided_verdict_holds_a_clean_line(hosted, caplog):
    hosted.verdict = "UNDECIDED"
    _assert_held_everywhere(hosted, caplog, "undecided")
    assert len(hosted.classify) == 4


# ── 3. Classifier unreachable holds ─────────────────────────────────────────

def test_hosted_unreachable_classifier_holds_a_clean_line_everywhere(hosted, caplog):
    hosted.verdict = "unreachable"
    _assert_held_everywhere(hosted, caplog, "error")
    # Each surface tried the classifier once; none fell back to local-first.
    assert len(hosted.classify) == 4
    assert hosted.voice == []


# ── 4. Caps and the dollar ceiling hold ─────────────────────────────────────

@pytest.mark.parametrize("env,outcome", [
    (guard.MODERATION_PER_USER_CAP_ENV, "user_cap"),
    (guard.MODERATION_CAP_ENV, "budget"),
    (guard.MODEL_ACTIONS_PER_USER_ENV, "user_cap"),
])
def test_hosted_spent_classify_or_model_action_cap_holds_a_clean_line(
        hosted, monkeypatch, caplog, env, outcome):
    monkeypatch.setenv(env, "0")
    _assert_held_everywhere(hosted, caplog, outcome)
    assert hosted.classify == []
    assert hosted.requests == []


def test_hosted_spent_dollar_ceiling_holds_a_clean_line(hosted, tmp_path, monkeypatch, caplog):
    path = _policy_file(tmp_path, *runtime.TASKS)
    document = json.loads(path.read_text())
    document["limits"] = {"global_daily_usd": "0.000001", "participant_daily_usd": "0.000001"}
    path.write_text(json.dumps(document))
    monkeypatch.setenv(model_policy.POLICY_ENV, str(path))
    model_policy.reset_for_tests()
    _assert_held_everywhere(hosted, caplog, "budget")
    assert hosted.requests == []


# ── 5. The AI kill switch ───────────────────────────────────────────────────

def test_hosted_kill_switch_holds_ideas_and_profile_without_a_classify_call(
        hosted, monkeypatch, caplog):
    monkeypatch.setenv(guard.DISABLE_AI_ENV, "1")
    caplog.set_level(logging.INFO)
    status, data = _idea(hosted, "idea-dark-every-1")
    assert status == 422 and data["held"] is True and data["error"] == moderation.IDEAS_HOLD
    status, data = _profile(hosted)
    assert status == 422 and data["held"] is True and data["error"] == moderation.PROFILE_HOLD
    assert _ideas(hosted) == [] and _published(hosted) is False
    assert _outcomes(caplog) == [("ideas", "disabled"), ("profile", "disabled")]
    # An ordinary Speak or agent line is held too, not answered quietly: the
    # quiet line means a spent voice allowance after a screen (G3's probe).
    status, data = _speak(hosted)
    assert status == 200 and data == {
        "response": moderation.HOLD_LINE, "ai": False, "held": True}, data
    status, data = _agent(hosted)
    assert status == 200 and data["held"] is True and data["ai"] is False, data
    assert data["response"] == moderation.HOLD_LINE
    # Each held voice line is counted once in the screen reports.
    assert _outcomes(caplog) == [("ideas", "disabled"), ("profile", "disabled"),
                                 ("speak", "disabled"), ("agent", "disabled")]
    assert hosted.requests == []
    assert _rows(hosted, "PLAYER_SPEAK") == [] and _rows(hosted, "AGENT_VOICE") == []


def test_hosted_kill_switch_still_gives_the_authored_identity_answer(hosted, monkeypatch):
    monkeypatch.setenv(guard.DISABLE_AI_ENV, "1")
    status, data = _speak(hosted, "Are you human?")
    assert status == 200, data
    assert data == {"response": honesty.place_answer(hosted.root.level), "ai": False}
    status, data = _agent(hosted, "Are you human?")
    assert status == 200, data
    assert data["ai"] is False and data["agent"] == _AGENT
    assert data["response"] == honesty.agent_answer(data["persona"])
    assert hosted.requests == []
    assert _rows(hosted, "PLAYER_SPEAK") == [] and _rows(hosted, "AGENT_VOICE") == []


def test_hosted_kill_switch_unknown_agent_keeps_its_quiet_line(hosted, monkeypatch):
    monkeypatch.setenv(guard.DISABLE_AI_ENV, "1")
    status, data = _agent(hosted, "Are you human?", agent="Nobody-Here")
    assert status == 200 and data["ai"] is False, data
    assert not honesty.is_authored_answer(data["response"])
    assert hosted.requests == []


# ── 6. A spent voice cap holds nothing ──────────────────────────────────────

@pytest.mark.parametrize("env", [guard.ANTHROPIC_PER_USER_CAP_ENV, guard.VOICE_PER_USER_CAP_ENV])
def test_hosted_spent_voice_cap_classifies_and_answers_quietly(hosted, monkeypatch, env):
    monkeypatch.setenv(env, "0")
    status, data = _speak(hosted)
    assert status == 200, data
    assert data.get("held") is not True
    assert data["response"] != moderation.HOLD_LINE
    assert data == {"response": guard.QUIET_RESPONSE, "ai": False}
    assert len(hosted.classify) == 1
    assert hosted.voice == []
    assert _rows(hosted, "PLAYER_SPEAK") == []


# ── 7. Chat, puzzle, CLI and default surfaces keep local-first ──────────────

@pytest.mark.parametrize("surface", ["chat", "puzzle", "cli", "shared"])
def test_hosted_local_first_surfaces_make_no_classify_call(hosted, surface):
    verdict = moderation.screen(_CLEAN, user_key=hosted.key, surface=surface)
    assert verdict.allowed and verdict.tier == "clean"
    assert hosted.requests == []


def test_hosted_puzzle_excerpt_keeps_a_clean_line_without_a_classify_call(hosted):
    assert moderation.public_excerpt(_CLEAN, user_key=hosted.key) == _CLEAN
    assert hosted.requests == []


def test_hosted_unshared_every_line_surface_keeps_local_first(hosted):
    for surface in sorted(moderation.EVERY_LINE_SURFACES):
        verdict = moderation.screen(_CLEAN, user_key=hosted.key, surface=surface, shared=False)
        assert verdict.allowed and verdict.tier == "clean"
    assert hosted.requests == []


def test_hosted_websocket_chat_publishes_a_clean_line_without_a_classify_call(
        controlled, srv, community_collection):  # noqa: F811
    from tests.test_day_one_recording import _ws_connect, _ws_send_json
    from tests.test_moderation import _read_ws_json_until
    from tests.test_ws_credential_lifetime import _wait_chat_rows
    assert moderation.every_line_required()
    _acknowledge_notice(controlled.key)
    seed = 951
    sender, status_line = _ws_connect(srv, seed, "Ada", invite_key=controlled.key)
    try:
        assert b"101" in status_line
        _read_ws_json_until(sender, "welcome")
        _ws_send_json(sender, {"type": "chat", "text": _CLEAN})
        chats = _wait_chat_rows(seed, None, 1)
        assert [row["text"] for row in chats] == [_CLEAN]
    finally:
        sender.close()
    assert controlled.requests == []


# ── 8. Not hosted: local-first, no provider needed ──────────────────────────

@pytest.fixture(params=[False, True], ids=["no-marker", "test-world"])
def unhosted(request, monkeypatch):
    """Set before ``http`` acknowledges the notice, whose text this changes."""
    if request.param:
        monkeypatch.setenv("NESTED_WORLDS_TEST_WORLD", "1")
    else:
        monkeypatch.delenv("NESTED_WORLDS_TEST_WORLD", raising=False)
    return request.param


def test_unhosted_clean_idea_publishes_with_no_classify_call(unhosted, http, monkeypatch):
    monkeypatch.delenv(model_policy.POLICY_ENV, raising=False)
    monkeypatch.delenv(model_policy.REQUIRED_ENV, raising=False)
    monkeypatch.delenv(runtime.PROVIDER_ENV, raising=False)
    calls = []
    monkeypatch.setattr(consciousness, "classify_content",
                        lambda *a, **k: calls.append(1) or "allow")
    assert not moderation.every_line_required()
    status, data = http("/ideas/submit", body={
        "title": "A clearer crossing", "description": "A traveler could not find it.",
        "request_id": "idea-local-every-1", "public_credit": False})[:2]
    assert status == 200 and data["visible"] is True, data
    assert calls == []
    assert [row["id"] for row in http("/ideas/list")[1]["ideas"]] == [data["id"]]


def test_required_policy_marker_alone_counts_as_hosted_and_holds(monkeypatch, accounts):
    """``NESTED_WORLDS_REQUIRE_MODEL_POLICY=1`` with no policy file is hosted:
    a clean Speak line cannot be classified, so it is held, never local-clean."""
    monkeypatch.delenv(model_policy.POLICY_ENV, raising=False)
    monkeypatch.setenv(model_policy.REQUIRED_ENV, "1")
    calls = []
    monkeypatch.setattr(consciousness, "classify_content",
                        lambda *a, **k: calls.append(1) or "allow")
    assert moderation.every_line_required()
    verdict = moderation.screen(_CLEAN, user_key=accounts[0], surface="speak")
    # No policy file under a required marker is an invalid policy: a control stop.
    assert not verdict.allowed and verdict.outcome == "control_stop"
    assert calls == []
    # The local-first surfaces are unaffected by the marker.
    assert moderation.screen(_CLEAN, user_key=accounts[0], surface="chat").tier == "clean"


# ── 9. A sincere identity question always gets its authored answer ──────────

_ASK = "Are you human?"


def _identity_rows(state):
    return _rows(state, "PLAYER_SPEAK") + _rows(state, "AGENT_VOICE")


def test_hosted_allowed_identity_question_is_answered_and_recorded(hosted):
    status, data = _speak(hosted, _ASK)
    assert status == 200 and data["ai"] is False, data
    assert data["response"] == honesty.place_answer(hosted.root.level)
    status, data = _agent(hosted, _ASK)
    assert status == 200 and data["ai"] is False, data
    assert data["response"] == honesty.agent_answer(data["persona"])
    # Classified once each, answered without a voice call, and kept (O16(c)).
    assert len(hosted.classify) == 2 and hosted.voice == []
    assert len(_rows(hosted, "PLAYER_SPEAK")) == 1
    assert len(_rows(hosted, "AGENT_VOICE")) == 1


@pytest.mark.parametrize("verdict", ["UNDECIDED", "unreachable"])
def test_hosted_held_identity_question_is_answered_but_not_recorded(hosted, verdict):
    hosted.verdict = verdict
    status, data = _speak(hosted, _ASK)
    assert status == 200 and data.get("held") is not True, data
    assert data == {"response": honesty.place_answer(hosted.root.level), "ai": False}
    status, data = _agent(hosted, _ASK)
    assert status == 200 and data.get("held") is not True, data
    assert data["ai"] is False and data["response"] == honesty.agent_answer(data["persona"])
    # One classify attempt each; the fallback is local-first and stores nothing.
    assert len(hosted.classify) == 2 and hosted.voice == []
    assert _identity_rows(hosted) == []


def test_hosted_shared_classify_budget_spent_still_answers_identity(hosted, monkeypatch):
    monkeypatch.setenv(guard.MODERATION_CAP_ENV, "0")
    status, data = _speak(hosted, _ASK)
    assert status == 200 and data == {
        "response": honesty.place_answer(hosted.root.level), "ai": False}
    assert hosted.requests == [] and _identity_rows(hosted) == []


def test_hosted_blocked_identity_question_stays_declined(hosted):
    hosted.verdict = "BLOCK"
    for route in (_speak, _agent):
        status, data = route(hosted, _ASK)
        assert status == 200 and data.get("declined") is True, data
        assert data["response"] == moderation.DECLINE_LINE
    assert len(hosted.classify) == 2
    assert _identity_rows(hosted) == []


def test_hosted_moderation_disabled_holds_identity_too(hosted, monkeypatch):
    """The moderation kill switch holds every shared and unshared line alike."""
    monkeypatch.setenv(moderation.DISABLE_MODERATION_ENV, "1")
    status, data = _speak(hosted, _ASK)
    assert status == 200 and data.get("held") is True, data
    assert hosted.requests == [] and _identity_rows(hosted) == []


def test_hosted_held_identity_question_spends_one_moderation_action(hosted, monkeypatch):
    """With one moderation action left, an undecided identity question is
    still answered: the fallback does not screen, or charge, a second time."""
    monkeypatch.setenv(guard.MODERATION_ACTIONS_PER_USER_ENV, "1")
    hosted.verdict = "UNDECIDED"
    status, data = _speak(hosted, _ASK)
    assert status == 200 and data == {
        "response": honesty.place_answer(hosted.root.level), "ai": False}, data
    assert len(hosted.classify) == 1 and _identity_rows(hosted) == []
    # That was the last action: the next line is held at the cap, unclassified.
    status, data = _speak(hosted, _ASK)
    assert status == 200 and data.get("held") is True, data
    assert len(hosted.classify) == 1


def test_hosted_ambiguous_identity_question_gets_one_classify_attempt(hosted, monkeypatch):
    """A locally ambiguous identity question is not privately allowed when
    the classifier cannot judge it, and is never classified twice."""
    monkeypatch.setenv(moderation.EXTRA_WATCH_ENV, "human")
    assert moderation._local_tier(_ASK) == "escalate"
    hosted.verdict = "UNDECIDED"
    status, data = _speak(hosted, _ASK)
    assert status == 200 and data.get("held") is True, data
    assert len(hosted.classify) == 1 and _identity_rows(hosted) == []


def test_unhosted_kill_switch_keeps_the_quiet_line(http, monkeypatch, accounts):
    monkeypatch.delenv(model_policy.POLICY_ENV, raising=False)
    monkeypatch.delenv(model_policy.REQUIRED_ENV, raising=False)
    monkeypatch.setenv(guard.DISABLE_AI_ENV, "1")
    root = store.world_tree(_SEED)
    status, data = http("/speak", body={
        "node_name": root.name, "seed": _SEED, "message": _CLEAN,
        "player_name": "Ada"})[:2]
    assert status == 200 and data == {"response": guard.QUIET_RESPONSE, "ai": False}


def _moderation_route_off(tmp_path, monkeypatch):
    tasks = [task for task in runtime.TASKS if task != runtime.MODERATION_TASK]
    monkeypatch.setenv(model_policy.POLICY_ENV, str(_policy_file(tmp_path, *tasks)))
    model_policy.reset_for_tests()


def test_identity_question_with_route_stop_is_counted_once(
        hosted, tmp_path, monkeypatch, caplog):
    _moderation_route_off(tmp_path, monkeypatch)
    caplog.set_level(logging.INFO)
    status, data = _speak(hosted, _ASK)
    assert status == 200 and data == {
        "response": honesty.place_answer(hosted.root.level), "ai": False}, data
    assert _outcomes(caplog) == [("speak", "disabled")]
    assert hosted.requests == [] and _identity_rows(hosted) == []


def test_identity_question_with_route_stop_at_the_cap_is_counted_once(
        hosted, tmp_path, monkeypatch, caplog):
    _moderation_route_off(tmp_path, monkeypatch)
    monkeypatch.setenv(guard.MODERATION_ACTIONS_PER_USER_ENV, "0")
    caplog.set_level(logging.INFO)
    status, data = _speak(hosted, _ASK)
    assert status == 200 and data.get("held") is True, data
    assert _outcomes(caplog) == [("speak", "user_cap")]
    assert hosted.requests == []


# ── 10. A profile save is validated before any screen ───────────────────────

_BIO, _GOALS = "I map quiet rivers.", "find the hinge"


def _save(state, **fields):
    body = {"bio": _BIO, "goals": _GOALS, **fields}
    return state.http("/profile/save", body=body)[:2]


def _own_profile(state):
    return state.http("/profile")[1]["profile"]


@pytest.mark.parametrize("fields", [
    {"published": "false"},
    {"published": "true"},
    {"published": 1},
    {"published": True, "avatar": "not-an-avatar"},
    {"published": True, "avatar": ["lantern"]},
], ids=["string-false", "string-true", "integer", "bad-avatar", "list-avatar"])
def test_hosted_invalid_profile_save_is_refused_before_any_classify_call(hosted, fields):
    status, data = _save(hosted, **fields)
    assert status == 400, data
    assert hosted.classify == [] and hosted.requests == []
    assert _published(hosted) is False


@pytest.mark.parametrize("fields", [{}, {"published": False}], ids=["omitted", "false"])
def test_hosted_private_profile_save_makes_no_classify_call(hosted, fields):
    status, data = _save(hosted, **fields)
    assert status == 200, data
    assert data["profile"]["published"] is False
    assert hosted.classify == [] and hosted.requests == []
    assert _own_profile(hosted)["bio"] == _BIO


def test_hosted_published_profile_save_is_classified_once_and_published(hosted):
    status, data = _save(hosted, published=True, avatar="river")
    assert status == 200 and data["profile"]["published"] is True, data
    assert len(hosted.classify) == 1
    assert _published(hosted) is True


@pytest.mark.parametrize("verdict,status_code", [
    ("BLOCK", 400), ("UNDECIDED", 422), ("unreachable", 422)])
def test_hosted_refused_publication_leaves_a_private_profile_private(
        hosted, verdict, status_code):
    status, _ = _save(hosted, published=False)
    assert status == 200 and hosted.classify == []
    hosted.verdict = verdict
    status, data = _save(hosted, published=True, avatar="river")
    assert status == status_code, data
    assert len(hosted.classify) == 1
    assert _published(hosted) is False
