"""A model call waits a bounded time for a provider slot.

Decision made under the owner's 2026-11-04 delegation: the wait for a slot
under ``NESTED_WORLDS_<NAME>_CONCURRENCY`` is bounded by the call's own
timeout (moderation passes 3 s), else ``NESTED_WORLDS_<NAME>_SLOT_WAIT_SECONDS``
(default 10). Before, every caller queued without limit, holding a request
thread or a WebSocket reader.

Every test here saturates the real per-provider ``BoundedSemaphore`` by
holding all of its permits. Blocking calls run on a daemon thread with a
join limit, so the unbounded wait this replaces fails a test instead of
hanging the suite. No live model call.
"""
from __future__ import annotations

import json
import logging
import threading
import time
import urllib.error
import urllib.request
from contextlib import contextmanager

import pytest

import persistence
from consciousness import runtime
from consciousness.runtime import Completion, SystemBlock
from multiverse import store
from server import _Handler, _ThreadedServer, guard, moderation, observability
from tests.test_day_one_recording import _ws_connect, _ws_send_json
from tests.test_moderation import _read_ws_json_until

SEED = 382
LIMIT = 2
WAIT = 0.5  # NESTED_WORLDS_FIXTURE_SLOT_WAIT_SECONDS in these tests
AMBIGUOUS = "go kill yourself"  # the local tier escalates it to one classify


class _Provider:
    name = "fixture"

    def __init__(self):
        self.calls = []
        self.reply = "A reply."
        self.fail = None

    def configured(self):
        return True

    def cache_reference_tokens(self, model):
        return None

    def default_model(self, task):
        return "fixture-model"

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail is not None:
            raise self.fail
        return Completion(self.reply, True, finish_reason="complete",
                          provider="fixture", resolved_model="fixture-model")


@pytest.fixture
def provider(monkeypatch):
    fixture = _Provider()
    monkeypatch.setattr(runtime, "get_provider", lambda: fixture)
    # A fresh semaphore registry: a permit another test held cannot leak in.
    monkeypatch.setattr(runtime, "_semaphores", {})
    monkeypatch.setattr(runtime, "_semaphore_limits", {})
    monkeypatch.setenv("NESTED_WORLDS_FIXTURE_CONCURRENCY", str(LIMIT))
    monkeypatch.setenv("NESTED_WORLDS_FIXTURE_SLOT_WAIT_SECONDS", str(WAIT))
    monkeypatch.delenv(guard.DISABLE_AI_ENV, raising=False)
    monkeypatch.delenv(moderation.DISABLE_MODERATION_ENV, raising=False)
    return fixture


@contextmanager
def _saturated():
    """Hold every permit of the fixture provider's real semaphore."""
    gate = runtime._semaphore_for("fixture")
    for _ in range(LIMIT):
        assert gate.acquire(blocking=False)
    try:
        yield gate
    finally:
        for _ in range(LIMIT):
            gate.release()


def _free_slots(gate=None):
    """Permits a caller could take now. LIMIT means none leaked."""
    gate = gate or runtime._semaphore_for("fixture")
    taken = 0
    while gate.acquire(blocking=False):
        taken += 1
    for _ in range(taken):
        gate.release()
    return taken


def _bounded(fn, limit):
    """Run ``fn`` on a daemon thread. Fail if it is still waiting at ``limit``."""
    box = {}

    def run():
        try:
            box["value"] = fn()
        except BaseException as exc:  # noqa: BLE001 - reported to the test
            box["error"] = exc
        box["elapsed"] = time.monotonic() - started

    started = time.monotonic()
    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(limit)
    assert not worker.is_alive(), f"still waiting for a slot after {limit}s"
    return box


def _generate(**kwargs):
    return runtime.generate(
        endpoint="speak", model="fixture-model", max_tokens=8,
        system=(SystemBlock("s"),), messages=[{"role": "user", "content": "hi"}],
        **kwargs)


def _count(surface, reason):
    return persistence.get_cost_calls(observability.voice_bucket(surface, reason),
                                      guard._utc_day())


def _voice_records(caplog):
    return [(r.levelno, r.getMessage()) for r in caplog.records
            if r.name == "nested_worlds.voice"]


class TestGenerateWaitsABoundedTime:
    def test_a_saturated_provider_answers_busy_within_the_wait_without_a_call(self, provider):
        with _saturated():
            box = _bounded(_generate, 5)
        assert isinstance(box.get("error"), runtime.ProviderBusy)
        assert WAIT * 0.8 <= box["elapsed"] < WAIT + 1.5
        assert provider.calls == []
        assert _free_slots() == LIMIT

    def test_the_calls_own_timeout_bounds_the_wait(self, provider, monkeypatch):
        # A long default proves the call's own timeout is what bounds it.
        monkeypatch.setenv("NESTED_WORLDS_FIXTURE_SLOT_WAIT_SECONDS", "60")
        with _saturated():
            box = _bounded(lambda: _generate(timeout=0.3), 5)
        assert isinstance(box.get("error"), runtime.ProviderBusy)
        assert 0.2 <= box["elapsed"] < 1.8
        assert provider.calls == []
        assert _free_slots() == LIMIT

    def test_a_slot_that_opens_within_the_wait_is_taken(self, provider, monkeypatch):
        monkeypatch.setenv("NESTED_WORLDS_FIXTURE_SLOT_WAIT_SECONDS", "5")
        gate = runtime._semaphore_for("fixture")
        for _ in range(LIMIT):
            assert gate.acquire(blocking=False)
        threading.Timer(0.2, gate.release).start()
        try:
            box = _bounded(_generate, 4)
        finally:
            for _ in range(LIMIT - 1):
                gate.release()
        assert box.get("error") is None and box["value"].text == "A reply."
        assert box["elapsed"] < 3
        assert len(provider.calls) == 1
        assert _free_slots() == LIMIT

    def test_an_unsaturated_call_is_unchanged(self, provider):
        box = _bounded(_generate, 5)
        assert box.get("error") is None
        assert box["value"] == Completion("A reply.", True, finish_reason="complete",
                                          provider="fixture", resolved_model="fixture-model")
        # The provider still receives the caller's own timeout, unaltered.
        assert len(provider.calls) == 1 and provider.calls[0]["timeout"] is None
        assert box["elapsed"] < WAIT
        assert _free_slots() == LIMIT

    def test_a_failing_provider_call_releases_its_slot(self, provider):
        provider.fail = RuntimeError("upstream")
        with pytest.raises(RuntimeError):
            _generate()
        assert _free_slots() == LIMIT

    def test_charges_taken_before_the_wait_stand(self, provider):
        # The cost ledger has no refund; a provider failure after the charge
        # keeps it too. The global voice budget and the per-user caps count
        # the attempt even though the provider was never contacted.
        key = "nw_" + "c" * 32
        day = guard._utc_day()
        with _saturated():
            box = _bounded(lambda: _generate(user_key=key, voice_budget=True), 5)
        assert isinstance(box.get("error"), runtime.ProviderBusy)
        assert persistence.get_cost_calls(guard.VOICE_BUCKET, day) == 1
        assert persistence.get_cost_calls(
            guard._user_bucket(guard.VOICE_BUCKET, key), day) == 1
        assert persistence.get_cost_calls(
            guard._user_bucket(guard.MODEL_ACTIONS_BUCKET, key), day) == 1
        assert provider.calls == []

    @pytest.mark.parametrize("raw,timeout,expected", [
        (None, None, 10.0), ("", None, 10.0), ("  ", None, 10.0),
        ("soon", None, 10.0), ("nan", None, 10.0), ("inf", None, 10.0),
        ("2.5", None, 2.5), ("0", None, 0.0), ("-4", None, 0.0),
        ("60", 3.0, 3.0), (None, 3.0, 3.0), ("1", 0, 1.0), ("1", -2, 1.0),
        ("1", float("nan"), 1.0), ("1", float("inf"), 1.0), ("1", "soon", 1.0),
        ("1e30", None, threading.TIMEOUT_MAX),
    ])
    def test_the_wait_setting(self, monkeypatch, raw, timeout, expected):
        if raw is None:
            monkeypatch.delenv("NESTED_WORLDS_FIXTURE_SLOT_WAIT_SECONDS", raising=False)
        else:
            monkeypatch.setenv("NESTED_WORLDS_FIXTURE_SLOT_WAIT_SECONDS", raw)
        assert runtime._slot_wait("fixture", timeout) == expected

    def test_the_wait_setting_is_per_provider(self, monkeypatch):
        monkeypatch.setenv("NESTED_WORLDS_ANTHROPIC_SLOT_WAIT_SECONDS", "4")
        monkeypatch.delenv("NESTED_WORLDS_OPENAI_COMPATIBLE_SLOT_WAIT_SECONDS", raising=False)
        assert runtime._slot_wait("anthropic") == 4.0
        assert runtime._slot_wait("openai_compatible") == runtime.DEFAULT_SLOT_WAIT_SECONDS

    def test_a_blank_adapter_name_waits_by_the_slots_it_shares(self, monkeypatch):
        # Review finding: _semaphore_for keys a blank adapter name to the
        # default provider's slots, so its wait is that provider's setting,
        # not NESTED_WORLDS__SLOT_WAIT_SECONDS.
        monkeypatch.setattr(runtime, "_semaphores", {})
        monkeypatch.setattr(runtime, "_semaphore_limits", {})
        monkeypatch.setenv("NESTED_WORLDS_ANTHROPIC_SLOT_WAIT_SECONDS", "4")
        monkeypatch.setenv("NESTED_WORLDS__SLOT_WAIT_SECONDS", "60")
        assert runtime._semaphore_for("  ") is runtime._semaphore_for(runtime.DEFAULT_PROVIDER)
        assert runtime._slot_wait("  ") == 4.0
        assert runtime._slot_wait("") == 4.0

    def test_a_slot_is_returned_when_the_call_is_interrupted(self, provider):
        # The release sits in a `finally`, so an interruption that is not an
        # Exception (KeyboardInterrupt, SystemExit) still returns the slot.
        class _Interrupted(BaseException):
            pass

        provider.fail = _Interrupted()
        with pytest.raises(_Interrupted):
            _generate()
        assert len(provider.calls) == 1
        assert _free_slots() == LIMIT

    def test_a_concurrency_change_mid_call_returns_the_slot_it_took(self, provider, monkeypatch):
        # A changed limit gives later callers a fresh semaphore. The call in
        # flight must release the one it acquired: releasing the fresh one
        # raises "released too many times" over a good reply and leaves the
        # old semaphore a permit short for the callers still waiting on it.
        entered, finish = threading.Event(), threading.Event()

        def slow(**kwargs):
            provider.calls.append(kwargs)
            entered.set()
            assert finish.wait(5)
            return Completion("A reply.", True, finish_reason="complete",
                              provider="fixture", resolved_model="fixture-model")

        monkeypatch.setattr(provider, "generate", slow)
        first = runtime._semaphore_for("fixture")
        box = {}

        def run():
            try:
                box["value"] = _generate()
            except BaseException as exc:  # noqa: BLE001 - reported to the test
                box["error"] = exc

        worker = threading.Thread(target=run, daemon=True)
        worker.start()
        assert entered.wait(5)
        monkeypatch.setenv("NESTED_WORLDS_FIXTURE_CONCURRENCY", str(LIMIT + 1))
        second = runtime._semaphore_for("fixture")
        assert second is not first
        finish.set()
        worker.join(5)
        assert not worker.is_alive()
        assert box.get("error") is None and box["value"].text == "A reply."
        assert _free_slots(first) == LIMIT
        assert _free_slots(second) == LIMIT + 1


class TestModerationHoldsWithinItsTimeout:
    def test_a_saturated_screen_holds_shared_text_in_about_three_seconds(
            self, provider, monkeypatch, caplog):
        # The real classify timeout (3 s), and a long default wait that must
        # not apply: the screen's own timeout bounds the slot wait.
        import consciousness
        assert consciousness._MODERATION_TIMEOUT_SECONDS == 3.0
        monkeypatch.setenv("NESTED_WORLDS_FIXTURE_SLOT_WAIT_SECONDS", "60")
        provider.reply = "ALLOW"
        caplog.set_level(logging.INFO)
        with _saturated():
            box = _bounded(lambda: moderation.screen(AMBIGUOUS, surface="chat"), 8)
        verdict = box["value"]
        assert verdict == moderation.Verdict(False, "busy", "busy")
        assert 2.5 <= box["elapsed"] < 5.0
        assert moderation.player_line(verdict) == moderation.HOLD_LINE
        assert moderation.http_body(verdict) == {
            "response": moderation.HOLD_LINE, "ai": False, "held": True}
        assert provider.calls == []
        assert "moderation_call outcome=busy surface=chat ms=" in caplog.text
        assert AMBIGUOUS not in caplog.text
        assert _free_slots() == LIMIT

    def test_an_unsaturated_screen_still_judges(self, provider):
        provider.reply = "ALLOW"
        assert moderation.screen(AMBIGUOUS, surface="chat") == \
            moderation.Verdict(True, "classify", "allow")
        assert len(provider.calls) == 1 and provider.calls[0]["timeout"] == 3.0
        assert _free_slots() == LIMIT


@pytest.fixture
def base(monkeypatch):
    monkeypatch.setenv("NESTED_WORLDS_CANONICAL_SEED", str(SEED))
    server = _ThreadedServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)


def _post(port, path, body):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.status, json.load(resp), time.monotonic() - started
    except urllib.error.HTTPError as exc:
        return exc.code, json.load(exc), time.monotonic() - started


def _rows(kind):
    root = store.world_tree(SEED).name
    return [row for row in persistence.get_node_history(SEED, root, 50)
            if row["type"] == kind]


@pytest.fixture
def quick_screen(monkeypatch):
    # The 3 s screen bound is pinned above; the HTTP and socket paths use a
    # shorter classify timeout so the suite does not wait it out each time.
    import consciousness
    monkeypatch.setattr(consciousness, "_MODERATION_TIMEOUT_SECONDS", 0.3)


class TestVoiceSurfaces:
    def test_speak_answers_the_nodes_silence_within_the_wait(self, base, provider, caplog):
        import consciousness
        root = store.world_tree(SEED)
        caplog.set_level(logging.WARNING, logger="nested_worlds")
        with _saturated():
            status, data, elapsed = _post(base, "/speak", {
                "node_name": root.name, "message": "hello"})
        assert status == 200 and data == {
            "response": consciousness.fallback_voice(root), "ai": False}
        assert elapsed < WAIT + 2
        assert provider.calls == []
        assert _rows("PLAYER_SPEAK") == []
        assert _count("speak", "busy") == 1 and _count("speak", "provider") == 0
        assert _voice_records(caplog) == [(
            logging.ERROR, "voice_fallback surface=speak reason=busy exception=-")]
        assert _free_slots() == LIMIT

    def test_speak_held_by_a_busy_screen_is_recorded_as_busy(
            self, base, provider, quick_screen, caplog):
        caplog.set_level(logging.INFO)
        with _saturated():
            status, data, elapsed = _post(base, "/speak", {
                "node_name": store.world_tree(SEED).name, "message": AMBIGUOUS})
        assert status == 200 and data == {
            "response": moderation.HOLD_LINE, "ai": False, "held": True}
        assert elapsed < 2.5
        assert provider.calls == [] and _rows("PLAYER_SPEAK") == []
        assert _count("speak", "busy") == 1 and _count("speak", "screen") == 0
        assert AMBIGUOUS not in caplog.text
        assert _free_slots() == LIMIT

    def test_an_unsaturated_speak_still_answers(self, base, provider):
        status, data, _ = _post(base, "/speak", {
            "node_name": store.world_tree(SEED).name, "message": "hello"})
        assert status == 200 and data == {"response": "A reply.", "ai": True}
        assert len(provider.calls) == 1
        assert len(_rows("PLAYER_SPEAK")) == 1
        assert _free_slots() == LIMIT

    def test_agent_voice_answers_the_agents_silence(self, base, provider):
        with _saturated():
            status, data, elapsed = _post(base, "/agent/voice", {
                "node_name": store.world_tree(SEED).name, "agent_name": "Tessera",
                "message": "what arrived?"})
        assert status == 200 and data["ai"] is False
        assert data["agent"] == "Tessera"
        assert data["response"].startswith("Tessera does not answer.")
        assert elapsed < WAIT + 2
        assert provider.calls == [] and _rows("AGENT_VOICE") == []
        assert _count("agent_voice", "busy") == 1
        assert _free_slots() == LIMIT

    def test_an_intention_points_to_the_explicit_actions(self, provider):
        from types import SimpleNamespace

        from server import intervention_api
        with _saturated():
            box = _bounded(lambda: intervention_api._propose(
                "tidy the shelf", "", "Room-1", SimpleNamespace(level="Room"), {}), 5)
        proposal, quiet = box["value"]
        assert proposal is None
        assert quiet == {"ai": False, "response": intervention_api._UNSETTLED,
                         "steps": [], "accepted": False}
        assert provider.calls == []
        assert _count("intention", "busy") == 1 and _count("intention", "provider") == 0
        assert _free_slots() == LIMIT

    def test_a_chat_is_held_and_the_reader_is_free_again(self, base, provider, quick_screen):
        sender, status = _ws_connect(base, SEED, "Ada")
        try:
            assert b"101" in status
            _read_ws_json_until(sender, "welcome")
            with _saturated():
                started = time.monotonic()
                _ws_send_json(sender, {"type": "chat", "text": AMBIGUOUS})
                declined = _read_ws_json_until(sender, "chat_declined", timeout=5)
                elapsed = time.monotonic() - started
            assert declined["text"] == moderation.HOLD_LINE
            assert elapsed < 2.5
            _ws_send_json(sender, {"type": "ping"})
            assert _read_ws_json_until(sender, "pong") == {"type": "pong"}
        finally:
            sender.close()
        assert provider.calls == [] and _rows("PLAYER_CHAT") == []
        assert _free_slots() == LIMIT


class TestWithAPlayerCredential:
    """The routes a keyed player reaches: fiction, no row, nothing private logged."""

    def test_an_intention_through_the_endpoint_answers_in_fiction(
            self, http, accounts, provider, caplog):
        from multiverse.situation import NODES
        from server import intervention_api
        name = NODES["instrument"]
        intention = "let the surface remember the river"
        assert http("/position", body={"node": name, "seed": SEED, "depth": 9})[0] == 200
        caplog.set_level(logging.INFO)
        with _saturated():
            started = time.monotonic()
            status, data, _ = http("/interventions/commit", body={
                "node": name, "intention": intention, "version": 3,
                "request_id": "busy-00000001"})
            elapsed = time.monotonic() - started
        assert status == 200 and data == {
            "ai": False, "response": intervention_api._UNSETTLED,
            "steps": [], "accepted": False}
        assert elapsed < WAIT + 2
        assert provider.calls == []
        assert _count("intention", "busy") == 1 and _count("intention", "provider") == 0
        assert accounts[0] not in caplog.text and intention not in caplog.text
        assert _free_slots() == LIMIT

    def test_speak_keeps_the_charges_and_logs_neither_key_nor_words(
            self, http, accounts, provider, caplog):
        import consciousness
        root = store.world_tree(SEED)
        message = "the lantern hums over the river"  # locally clean: no classify
        caplog.set_level(logging.INFO)
        with _saturated():
            status, data, _ = http("/speak", body={"node_name": root.name, "message": message})
        assert status == 200 and data == {
            "response": consciousness.fallback_voice(root), "ai": False}
        assert provider.calls == [] and _rows("PLAYER_SPEAK") == []
        assert _count("speak", "busy") == 1
        day = guard._utc_day()
        for bucket in (guard.VOICE_BUCKET, guard.MODEL_ACTIONS_BUCKET):
            assert persistence.get_cost_calls(guard._user_bucket(bucket, accounts[0]), day) == 1
        assert accounts[0] not in caplog.text and message not in caplog.text
        assert _free_slots() == LIMIT


class TestVoiceHealth:
    def _run(self, *argv):
        import main
        args = main.build_parser().parse_args(["voice-health", *argv])
        args.func(args)

    def test_busy_is_a_failure_the_operator_sees(self, monkeypatch, capsys, caplog):
        monkeypatch.setattr(runtime, "configured", lambda *args, **kwargs: True)
        caplog.set_level(logging.WARNING, logger="nested_worlds")
        observability.voice_outcome("speak", "ok")
        observability.voice_outcome("speak", "busy")
        assert _voice_records(caplog) == [(
            logging.ERROR, "voice_fallback surface=speak reason=busy exception=-")]
        with pytest.raises(SystemExit, match="1 voice failure"):
            self._run()
        assert "speak        answered    1   quiet: busy 1" in capsys.readouterr().out


@pytest.mark.parametrize("surface", ["ideas", "profile"])
def test_a_busy_screen_holds_ideas_and_published_profiles(provider, quick_screen, http, surface):
    # Every surface maps a non-block verdict to its hold; pin the two HTTP
    # surfaces that answer 422 with `held` besides the voice paths.
    provider.reply = "ALLOW"
    with _saturated():
        if surface == "ideas":
            status, body, _ = http("/ideas/submit", body={
                "title": AMBIGUOUS, "description": "A traveler could not find the crossing.",
                "request_id": "idea-busy-0001", "public_credit": False})
            hold = moderation.IDEAS_HOLD
        else:
            status, body, _ = http("/profile/save", body={
                "bio": AMBIGUOUS, "goals": "", "published": True})
            hold = moderation.PROFILE_HOLD
    assert status == 422 and body["held"] is True and body["error"] == hold
    assert provider.calls == []
    assert _free_slots() == LIMIT
    if surface == "ideas":
        assert http("/ideas/list")[1]["ideas"] == []
    else:
        assert http("/profile")[1]["profile"]["published"] is False

