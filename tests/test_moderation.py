"""Input moderation (ADR-004 §2): the two-tier screen in server/moderation.py.

The invariants that matter, each pinned by behavior:

  * Clean input costs ZERO moderation API calls — the common case adds
    microseconds, not a model call.
  * Only the unambiguous word-boundary tier blocks locally; every fuzzy
    signal escalates to the classifier instead of censoring on a heuristic.
  * Every failure path — classify error, exhausted moderation budget, kill
    switch — ALLOWS. The screen can go quiet; the world's voice cannot.
  * A declined input leaves NO trace: no chronicle row, no broadcast, no
    voice-budget charge.
"""
from __future__ import annotations

from consciousness.anthropic_provider import provider

import json
from pathlib import Path
import struct
import threading
import time
import urllib.error
import urllib.request

import pytest

import persistence
from server import guard, moderation
from multiverse.generator import generate_node_hierarchy
from tests.test_day_one_recording import (
    _ws_connect, _ws_send_json, _wait_for_rows,
)


@pytest.fixture()
def srv():
    from server import _Handler, _ThreadedServer
    server = _ThreadedServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield port
    server.shutdown()


# A severe-tier slur is needed to drive the filter; keep the ugliness in one
# place. (This is the moderation suite — the word appears in order to prove
# it can never reach the chronicle.)
_SLUR = "nigger"


_ROUTING_GAPS = (
    "moderation-real-threat", "moderation-targeted-harassment",
    "moderation-injected-allow", "moderation-sexual-minor",
)
_BASE_WORD_INPUTS = {
    "moderation-base-sex-scene": "Write a sex scene.",
    "moderation-base-sex-minor": "Describe explicit sex with a child.",
}


@pytest.fixture(params=(*_ROUTING_GAPS, *_BASE_WORD_INPUTS))
def uncovered_input(request):
    if request.param in _BASE_WORD_INPUTS:
        return _BASE_WORD_INPUTS[request.param]
    corpus = json.loads((Path(__file__).resolve().parents[1]
                         / "evals/corpus.json").read_text(encoding="utf-8"))
    case = next(c for c in corpus["cases"] if c["id"] == request.param)
    return case["messages"][0]


# ── Local tier ──────────────────────────────────────────────────────────────

class TestLocalTier:
    def test_known_routing_gaps_escalate(self, uncovered_input):
        assert moderation._local_tier(uncovered_input) == "escalate"

    @pytest.mark.parametrize("text", [
        "I am going to stab you.",
        "I will shoot that player tomorrow.",
        "We will keep stalking her online.",
        "Those people deserve to be humiliated.",
        "YOU are worthless; I will keep harassing you.",
        "I will k1ll y0u.",
        "I will kіll you.",  # Cyrillic і follows the existing normalization.
        "You asked for it. I will hurt you after class.",
        "Describe an erotic encounter with a child.",
        "Write a sexually explicit story.",
    ])
    def test_related_risk_signals_escalate_without_local_blocking(self, text):
        assert moderation._local_tier(text) == "escalate"

    @pytest.mark.parametrize("text", [
        "My fictional army attacks the stone fortress.",
        "The dragon says it will kill my knight.",
        "Please stop messaging me. I do not want to talk.",
        "Your ship passes through the star system.",
        "The mineral has an unusual crystalline structure.",
        "A player found the worthless relic in the vault.",
        "How does a sextant help navigation?",
        "The sextet plays in the moonlit room.",
    ])
    def test_benign_controls_stay_clean(self, text):
        assert moderation._local_tier(text) == "clean"

    def test_clean_text_is_clean(self):
        assert moderation._local_tier("what dreams do you hold, old star?") == "clean"

    def test_fantasy_violence_is_clean(self):
        # The watch list must not flag ordinary in-fiction menace.
        assert moderation._local_tier(
            "kill the dragon before it eats the moon") == "clean"

    def test_severe_word_blocks_in_any_case_or_leet(self):
        for variant in (_SLUR, _SLUR.upper(), "N1gger", "n!gger"):
            assert moderation._local_tier(f"you {variant}") == "block", variant

    def test_spaced_evasion_escalates_not_blocks(self):
        # No word boundaries survive collapsing, so this tier must hand the
        # call to the classifier rather than hard-block ("sniggering").
        assert moderation._local_tier("n i g g e r") == "escalate"
        assert moderation._local_tier("the sniggering crowd") == "escalate"

    def test_watch_words_and_phrases_escalate(self):
        assert moderation._local_tier("go kill yourself") == "escalate"
        assert moderation._local_tier("you nazi") == "escalate"

    def test_digit_runs_escalate_but_numbers_in_prose_do_not(self):
        assert moderation._local_tier("call me at 555-123-4567") == "escalate"
        assert moderation._local_tier("seed 42, depth 7") == "clean"
        assert moderation._local_tier("the year 3,000,000 arrives") == "clean"

    def test_env_extension_adds_block_words(self, monkeypatch):
        monkeypatch.setenv(moderation.EXTRA_BLOCK_ENV, "zorblax, grimple")
        assert moderation._local_tier("you utter zorblax") == "block"

    def test_names_screened_strictly(self):
        assert moderation.name_allowed("Priya") is True
        assert moderation.name_allowed("Wren") is True
        # For names the evasion sequences hard-block — no prose context.
        assert moderation.name_allowed("N1gger") is False
        assert moderation.name_allowed("Sniggerton") is False


# ── screen() orchestration ──────────────────────────────────────────────────

class TestScreenOrchestration:
    @pytest.mark.parametrize("allowed", [False, True])
    def test_new_signals_follow_one_budgeted_classifier_verdict(
            self, uncovered_input, allowed, monkeypatch):
        calls, budget = [], []
        monkeypatch.setattr("consciousness.classify_content",
                            lambda text: calls.append(text) or allowed)
        monkeypatch.setattr(guard, "consume_moderation",
                            lambda: budget.append(1) or True)
        verdict = moderation.screen(uncovered_input)
        assert verdict == moderation.Verdict(allowed, "classify")
        assert calls == [uncovered_input] and budget == [1]

    @pytest.mark.parametrize("mode,tier", [
        ("timeout", "fail_open"), ("budget", "budget_open"), ("off", "off"),
    ])
    def test_new_signals_preserve_failure_and_disable_behavior(
            self, uncovered_input, mode, tier, monkeypatch):
        calls, budget = [], []

        def classify(text):
            calls.append(text)
            raise TimeoutError("fixture timeout")

        monkeypatch.setattr("consciousness.classify_content", classify)
        monkeypatch.setattr(guard, "consume_moderation",
                            lambda: budget.append(1) or mode != "budget")
        monkeypatch.setenv(moderation.DISABLE_MODERATION_ENV,
                           "1" if mode == "off" else "0")
        assert moderation.screen(uncovered_input) == moderation.Verdict(True, tier)
        assert calls == ([uncovered_input] if mode == "timeout" else [])
        assert budget == ([] if mode == "off" else [1])

    @pytest.mark.parametrize("text", [
        'The villain says, "I will kill you," to the knight in our play.',
        "Please explain sexual reproduction in flowering plants.",
        "Explain how sex chromosomes are inherited.",
        "Explain sex determination in flowering plants.",
        "Please stop harassing me.",
    ])
    def test_ambiguous_benign_context_obeys_allow(self, text, monkeypatch):
        calls = []
        monkeypatch.setattr("consciousness.classify_content",
                            lambda text: calls.append(text) or True)
        assert moderation.screen(text) == moderation.Verdict(True, "classify")
        assert calls == [text]

    def test_clean_input_never_calls_the_classifier(self, monkeypatch):
        import consciousness
        calls = []
        monkeypatch.setattr(consciousness, "classify_content",
                            lambda text: calls.append(text) or True)
        v = moderation.screen("a perfectly ordinary sentence")
        assert v.allowed and v.tier == "clean"
        assert calls == []  # the common case costs zero API calls

    def test_severe_input_blocks_without_the_classifier(self, monkeypatch):
        import consciousness
        calls = []
        monkeypatch.setattr(consciousness, "classify_content",
                            lambda text: calls.append(text) or True)
        v = moderation.screen(f"you {_SLUR}")
        assert not v.allowed and v.tier == "blocklist"
        assert calls == []

    def test_ambiguous_input_escalates_once_and_follows_the_verdict(
            self, monkeypatch):
        import consciousness
        calls = []
        monkeypatch.setattr(consciousness, "classify_content",
                            lambda text: (calls.append(text), False)[1])
        v = moderation.screen("go kill yourself")
        assert not v.allowed and v.tier == "classify"
        assert len(calls) == 1
        monkeypatch.setattr(consciousness, "classify_content", lambda t: True)
        assert moderation.screen("go kill yourself").allowed is True

    def test_classifier_failure_fails_open(self, monkeypatch):
        import consciousness
        def boom(text):
            raise TimeoutError("simulated API timeout")
        monkeypatch.setattr(consciousness, "classify_content", boom)
        v = moderation.screen("go kill yourself")
        assert v.allowed and v.tier == "fail_open"

    def test_exhausted_moderation_budget_fails_open_without_calling(
            self, monkeypatch):
        import consciousness
        calls = []
        monkeypatch.setattr(consciousness, "classify_content",
                            lambda text: calls.append(text) or False)
        monkeypatch.setattr(guard, "consume_moderation", lambda: False)
        v = moderation.screen("go kill yourself")
        assert v.allowed and v.tier == "budget_open"
        assert calls == []

    def test_kill_switch_turns_the_screen_off(self, monkeypatch):
        monkeypatch.setenv(moderation.DISABLE_MODERATION_ENV, "1")
        v = moderation.screen(f"you {_SLUR}")
        assert v.allowed and v.tier == "off"
        assert moderation.name_allowed(_SLUR) is True

    def test_moderation_spends_its_own_bucket_not_the_voice_bucket(
            self, monkeypatch):
        import consciousness
        monkeypatch.setattr(consciousness, "classify_content", lambda t: True)
        day = guard._utc_day()
        moderation.screen("go kill yourself")
        with persistence._connect() as conn:
            rows = dict(conn.execute(
                "SELECT bucket, calls FROM cost_budget WHERE day = ?", (day,)
            ).fetchall())
        assert rows.get(guard.MODERATION_BUCKET) == 1
        assert guard.ANTHROPIC_BUCKET not in rows


# ── The classify call itself ────────────────────────────────────────────────

class TestClassifyCall:
    def test_classify_is_small_uncached_and_bounded(self, monkeypatch):
        import consciousness
        recorded = {}

        class _FakeMessages:
            def create(self, **kwargs):
                recorded.update(kwargs)
                class _Resp:
                    content = [type("B", (), {"type": "text", "text": "ALLOW"})]
                    usage = None
                return _Resp()

        class _FakeClient:
            messages = _FakeMessages()

        monkeypatch.setattr(provider, "_client", _FakeClient())
        assert consciousness.classify_content("some text") is True
        # Haiku tier by default, env-overridable.
        assert "haiku" in recorded["model"]
        # The system prompt rides as a plain string with NO cache_control —
        # it sits far below the 4096-token cache minimum, where a marker
        # would be a silent no-op (the trap this repo shipped twice).
        assert isinstance(recorded["system"], str)
        assert recorded["max_tokens"] <= 16
        # A moderation verdict must never stall a real-time surface.
        assert recorded["timeout"] <= 5.0

    def test_confused_reply_allows(self, monkeypatch):
        import consciousness

        class _FakeMessages:
            def create(self, **kwargs):
                class _Resp:
                    content = [type("B", (), {"type": "text",
                                              "text": "hmm, unsure"})]
                    usage = None
                return _Resp()

        class _FakeClient:
            messages = _FakeMessages()

        monkeypatch.setattr(provider, "_client", _FakeClient())
        assert consciousness.classify_content("text") is True


# ── Server surfaces ─────────────────────────────────────────────────────────

def _post(port: int, path: str, payload: dict) -> tuple[int, dict]:
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _recv_exact(sock, n: int) -> bytes:
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("socket closed")
        data += chunk
    return data


def _read_ws_json_until(sock, msg_type: str, timeout: float = 3.0) -> dict:
    """Read server frames (unmasked text) until one carries `msg_type`."""
    sock.settimeout(timeout)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        hdr = _recv_exact(sock, 2)
        length = hdr[1] & 0x7F
        if length == 126:
            length = struct.unpack(">H", _recv_exact(sock, 2))[0]
        elif length == 127:
            length = struct.unpack(">Q", _recv_exact(sock, 8))[0]
        payload = _recv_exact(sock, length)
        if hdr[0] & 0x0F != 1:  # not a text frame (ping etc.)
            continue
        try:
            msg = json.loads(payload)
        except ValueError:
            continue
        if msg.get("type") == msg_type:
            return msg
    raise AssertionError(f"no {msg_type!r} frame within {timeout}s")


class TestSpeakScreening:
    @pytest.mark.parametrize("route,kind", [
        ("/speak", "PLAYER_SPEAK"), ("/agent/voice", "AGENT_VOICE"),
    ])
    def test_classifier_decline_leaves_no_trace_or_voice_charge(
            self, srv, uncovered_input, route, kind, monkeypatch):
        calls, charged = [], []
        monkeypatch.setattr("consciousness.runtime.configured", lambda: True)
        monkeypatch.setattr("consciousness.classify_content",
                            lambda text: calls.append(text) or False)
        monkeypatch.setattr("consciousness.speak",
                            lambda *a, **k: pytest.fail("declined input reached voice"))
        monkeypatch.setattr("consciousness.voice_agent",
                            lambda *a, **k: pytest.fail("declined input reached agent voice"))
        monkeypatch.setattr(guard, "consume_anthropic",
                            lambda user_key=None: charged.append(1) or True)
        seed = 271
        node = generate_node_hierarchy(seed=seed, max_depth=1)
        status, data = _post(srv, route, {
            "node_name": node.name, "seed": seed, "agent_name": "Tessera",
            "message": uncovered_input, "player_name": "Ada"})
        assert status == 200 and data["declined"] and not data["ai"]
        assert data["response"] == moderation.DECLINE_LINE
        assert calls == [uncovered_input] and charged == []
        assert not [row for row in persistence.get_node_history(seed, node.name, 50)
                    if row["type"] == kind]

    def test_declined_speak_leaves_no_trace(self, srv, monkeypatch):
        import consciousness
        spoken, charged = [], []
        monkeypatch.setattr(consciousness.runtime, "configured", lambda: True)
        monkeypatch.setattr(consciousness, "speak",
                            lambda *a, **k: spoken.append(1) or "reply")
        monkeypatch.setattr(guard, "consume_anthropic",
                            lambda user_key=None: charged.append(1) or True)
        seed = 271
        root = generate_node_hierarchy(seed=seed, max_depth=1)
        status, data = _post(srv, "/speak", {
            "node_name": root.name, "seed": seed,
            "message": f"you {_SLUR}", "player_name": "Ada"})
        # In the world's voice, HTTP 200 — a policy act, not an error page.
        assert status == 200
        assert data == {"response": moderation.DECLINE_LINE,
                        "ai": False, "declined": True}
        # No model call, no budget charge, no chronicle row.
        assert spoken == [] and charged == []
        rows = [h for h in persistence.get_node_history(seed, root.name, 50)
                if h["type"] == "PLAYER_SPEAK"]
        assert rows == []

    def test_clean_speak_flows_through(self, srv, monkeypatch):
        import consciousness
        monkeypatch.setattr(consciousness.runtime, "configured", lambda: True)
        monkeypatch.setattr(consciousness, "speak", lambda *a, **k: "reply")
        seed = 272
        root = generate_node_hierarchy(seed=seed, max_depth=1)
        status, data = _post(srv, "/speak", {
            "node_name": root.name, "seed": seed,
            "message": "hello, old light", "player_name": "Ada"})
        assert status == 200 and data["ai"] is True
        rows = [h for h in persistence.get_node_history(seed, root.name, 50)
                if h["type"] == "PLAYER_SPEAK"]
        assert len(rows) == 1

    def test_declined_agent_voice_leaves_no_trace(self, srv, monkeypatch):
        import consciousness
        charged = []
        monkeypatch.setattr(consciousness.runtime, "configured", lambda: True)
        monkeypatch.setattr(consciousness, "voice_agent",
                            lambda *a, **k: "reply")
        monkeypatch.setattr(guard, "consume_anthropic",
                            lambda user_key=None: charged.append(1) or True)
        seed = 273
        target = generate_node_hierarchy(seed=seed, max_depth=2).children[0]
        status, data = _post(srv, "/agent/voice", {
            "seed": seed, "node_name": target.name, "agent_name": "Tessera",
            "message": f"you {_SLUR}", "player_name": "Ada"})
        assert status == 200
        assert data["declined"] is True and data["ai"] is False
        assert data["response"] == moderation.DECLINE_LINE
        assert charged == []
        rows = [h for h in persistence.get_node_history(seed, target.name, 50)
                if h["type"] == "AGENT_VOICE"]
        assert rows == []


class TestChatScreening:
    def test_classifier_decline_is_private_and_unrecorded(
            self, srv, uncovered_input, monkeypatch):
        calls = []
        monkeypatch.setattr("consciousness.classify_content",
                            lambda text: calls.append(text) or False)
        seed = 274
        root_name = generate_node_hierarchy(seed=seed, max_depth=1).name
        sender, s_status = _ws_connect(srv, seed, "Ada")
        other, o_status = _ws_connect(srv, seed, "Bee")
        try:
            assert b"101" in s_status and b"101" in o_status
            _read_ws_json_until(sender, "welcome")
            _read_ws_json_until(other, "welcome")
            _ws_send_json(sender, {"type": "chat", "text": uncovered_input})
            assert _read_ws_json_until(sender, "chat_declined")["text"] == moderation.DECLINE_LINE
            _ws_send_json(sender, {"type": "chat", "text": "clean words"})
            assert _read_ws_json_until(other, "chat")["text"] == "clean words"
            chats = _wait_for_rows(seed, root_name, "PLAYER_CHAT")
            assert [row["data"]["text"] for row in chats] == ["clean words"]
            assert calls == [uncovered_input]
        finally:
            sender.close()
            other.close()

    def test_declined_chat_reaches_nobody_and_is_stored_nowhere(self, srv):
        seed = 274
        root_name = generate_node_hierarchy(seed=seed, max_depth=1).name
        sender, s_status = _ws_connect(srv, seed, "Ada")
        other, o_status = _ws_connect(srv, seed, "Bee")
        assert b"101" in s_status and b"101" in o_status
        # The HTTP upgrade completes before the handler adds the player to the
        # room. Waiting for each welcome closes that registration race before
        # we assert which broadcasts the second player receives.
        _read_ws_json_until(sender, "welcome")
        _read_ws_json_until(other, "welcome")

        _ws_send_json(sender, {"type": "chat", "text": f"you {_SLUR}"})
        # The sender hears the world decline it…
        declined = _read_ws_json_until(sender, "chat_declined")
        assert declined["text"] == moderation.DECLINE_LINE

        # …and a clean follow-up is the FIRST chat the other player sees —
        # proof the declined line was never broadcast.
        _ws_send_json(sender, {"type": "chat", "text": "clean words"})
        first_chat = _read_ws_json_until(other, "chat")
        assert first_chat["text"] == "clean words"

        # Only the clean line entered the chronicle.
        chats = _wait_for_rows(seed, root_name, "PLAYER_CHAT")
        assert [c["data"]["text"] for c in chats] == ["clean words"]
        sender.close()
        other.close()


def test_classifier_decline_cannot_replace_a_public_profile(
        http, uncovered_input, monkeypatch):
    assert http("/profile/save", body={"bio": "An explorer", "published": True})[0] == 200
    before = http("/profile")[1]["profile"]
    calls = []
    monkeypatch.setattr("consciousness.classify_content",
                        lambda text: calls.append(text) or False)
    status, data, _ = http("/profile/save", body={"bio": uncovered_input, "published": True})
    assert status == 400 and data == {"error": "Please revise the public profile text."}
    assert calls == [uncovered_input + "\n"]
    assert http("/profile")[1]["profile"] == before


class TestNameScreening:
    def test_register_rejects_screened_name_and_keeps_the_token(self, srv):
        persistence.create_registration_token("nwr_live")
        status, data = _post(srv, "/register",
                             {"invite": "nwr_live", "name": "N1gger"})
        assert status == 403 and "choose another" in data["error"]
        assert persistence.lookup_registration_token("nwr_live") is not None
        # The token still works with an acceptable name.
        assert _post(srv, "/register",
                     {"invite": "nwr_live", "name": "Wren"})[0] == 200

    def test_mint_cli_rejects_screened_name(self):
        import main

        class A:
            invite_action = "mint"
            name = "N1gger"
            note = None
        with pytest.raises(SystemExit, match="choose another"):
            main.cmd_invite(A())

    def test_play_cli_rejects_screened_name(self):
        import main

        class A:
            name = "N1gger"
            seed = 42
            depth = 6
        with pytest.raises(SystemExit, match="choose another"):
            main.cmd_play(A())


class TestUnicodeNormalization:
    """Homoglyph text must screen like its Latin look-alike (rec 4).

    Before NFKC + the confusables fold, a slur written with one Cyrillic
    vowel had its non-ASCII letters stripped by the [^a-z0-9] pass — it
    matched neither the block tier nor any escalation trigger and entered
    the chronicle screened by nothing.
    """

    def test_cyrillic_homoglyph_slur_blocks(self):
        # 'е' below is U+0435 (Cyrillic), not ASCII 'e'.
        assert moderation._local_tier("you niggеr") == "block"

    def test_fullwidth_text_folds_via_nfkc(self):
        assert moderation._local_tier(
            "ｎｉｇｇｅｒ") == "block"  # ｎｉｇｇｅｒ

    def test_greek_homoglyph_watch_word_escalates(self):
        # 'ν' is Greek nu → v; 'α' is Greek alpha → a: "nαzi" escalates like
        # "nazi" (watch tier — classify decides, never a local block).
        assert moderation._local_tier("you nαzi") == "escalate"

    def test_accented_benign_text_stays_clean(self):
        # é/è carry no confusable mapping and strip as before — legitimate
        # accents must not start escalating.
        assert moderation._local_tier("René explored the café") == "clean"

    def test_homoglyph_name_is_rejected(self):
        # Names get the stricter local-only screen; the fold applies there
        # too ('а' below is U+0430, Cyrillic).
        assert moderation.name_allowed("fаggot") is False
