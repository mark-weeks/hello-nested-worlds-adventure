"""A caller's timeout is the budget for the whole provider call.

``TextProvider.generate`` documents it: when the caller passes ``timeout``,
an adapter must not retry past it. Only the moderation classify (3 s) and
the opt-in model probe pass one. Before this, the anthropic adapter handed
the timeout to the SDK as a per-attempt limit, and the SDK retried a
timed-out, 408, 409, 429 or 5xx attempt up to twice, honouring
``retry-after`` up to 60 s. Measured against a local stub, one classify
then made three attempts over about 120 s under a 429 with
``retry-after: 60``, and over 10.4 s against a provider that never
answered. A WebSocket reader, or a request thread, waited all that time.

Every anthropic test here drives the real pinned SDK against a stub HTTP
server on 127.0.0.1 (``ANTHROPIC_BASE_URL``) with a fake key, and the
``openai_compatible`` tests use that adapter's own loopback stub: no
network, no model call. Blocking calls run on a daemon thread with a join
limit, so the old retrying behaviour fails a test instead of hanging the
suite.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler

import pytest

import persistence
from consciousness import runtime
from consciousness.anthropic_provider import AnthropicProvider
from consciousness.runtime import SystemBlock
from multiverse import store
from server import _Handler, _ThreadedServer, moderation
from tests.test_day_one_recording import _ws_connect, _ws_send_json
from tests.test_moderation import _read_ws_json_until
from tests.test_openai_compat_provider import (
    _SECRET, _Loopback, _arm, _start_loopback, _stop_loopback,
)

SEED = 382
LIMIT = 2  # NESTED_WORLDS_ANTHROPIC_CONCURRENCY in these tests
AMBIGUOUS = "go kill yourself"  # the local tier escalates it to one classify
FAKE_KEY = "fixture-not-a-real-key"

_ERRORS = {
    408: "timeout_error", 409: "conflict_error", 429: "rate_limit_error",
    500: "api_error", 529: "overloaded_error",
}


class _AnthropicStub(BaseHTTPRequestHandler):
    """Answers /v1/messages by ``server.mode``; records every attempt."""

    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        return

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length) if length else b""
        self.server.seen.append({
            "at": time.monotonic(), "path": self.path,
            "x-api-key": self.headers.get("x-api-key"),
            "authorization": self.headers.get("authorization"),
            "body": body,
        })
        mode = self.server.mode
        try:
            if mode == "hang":
                # Accept and read the request, then never answer.
                self.server.release.wait(10)
                self.close_connection = True
                return
            if mode == "drop":
                # Read the request, then close the connection unanswered.
                self.close_connection = True
                return
            if mode == "ok":
                self._send(200, {
                    "id": "msg_fixture", "type": "message", "role": "assistant",
                    "model": "fixture-resolved", "stop_reason": "end_turn",
                    "stop_sequence": None,
                    "content": [{"type": "text", "text": "ALLOW"}],
                    "usage": {"input_tokens": 1, "output_tokens": 1},
                })
                return
            status = int(mode)
            self._send(status, {"type": "error", "error": {
                "type": _ERRORS.get(status, "api_error"), "message": "fixture"}})
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

    def _send(self, status, payload):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        for name, value in self.server.extra_headers.items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture
def stub(monkeypatch):
    try:
        server = _Loopback(("127.0.0.1", 0), _AnthropicStub)
    except OSError as exc:
        pytest.skip(f"loopback bind unavailable ({type(exc).__name__})")
    server.mode = "ok"
    server.seen = []
    server.extra_headers = {}
    server.release = threading.Event()
    server._accepting = threading.Event()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    server._thread = thread
    thread.start()
    assert server._accepting.wait(2), "stub accept thread did not start"
    # The SDK reads these when a client is built. Nothing leaves loopback.
    monkeypatch.setenv("ANTHROPIC_BASE_URL", f"http://127.0.0.1:{server.server_address[1]}")
    monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE_KEY)
    for name in ("ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_CUSTOM_HEADERS",
                 "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
                 "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.delenv(name, raising=False)
    try:
        yield server
    finally:
        server.release.set()
        _stop_loopback(server)


@pytest.fixture
def adapter(stub):
    built = AnthropicProvider()
    built._get_client()  # built outside the timed section
    try:
        yield built
    finally:
        built._client.close()


def _bounded(fn, limit):
    """Run ``fn`` on a daemon thread. Fail if it is still running at ``limit``."""
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
    assert not worker.is_alive(), f"provider call still running after {limit}s"
    return box


def _call(adapter, **kwargs):
    return adapter.generate(
        model="claude-haiku-4-5", system=(SystemBlock("classify"),),
        messages=[{"role": "user", "content": "words"}], max_tokens=32, **kwargs)


class TestACallerTimeoutBoundsTheWholeCall:
    @pytest.mark.parametrize("status,error", [
        (429, "RateLimitError"), (529, "OverloadedError"),
        (500, "InternalServerError"), (408, "APIStatusError"),
        (409, "ConflictError"),
    ])
    def test_a_retryable_status_is_one_attempt(self, stub, adapter, status, error):
        import anthropic
        stub.mode = str(status)
        # The SDK would wait this long before each of two retries.
        stub.extra_headers = {"retry-after": "1"}
        box = _bounded(lambda: _call(adapter, timeout=2.0), 10)
        assert isinstance(box.get("error"), anthropic.APIStatusError)
        assert type(box["error"]).__name__ == error
        assert box["error"].status_code == status
        assert len(stub.seen) == 1
        assert box["elapsed"] < 1.0

    def test_a_429_asking_for_a_minute_is_one_prompt_attempt(self, stub, adapter):
        stub.mode = "429"
        stub.extra_headers = {"retry-after": "60"}
        box = _bounded(lambda: _call(adapter, timeout=3.0), 10)
        assert type(box.get("error")).__name__ == "RateLimitError"
        assert len(stub.seen) == 1
        assert box["elapsed"] < 1.0

    def test_a_provider_that_never_answers_returns_within_about_the_timeout(
            self, stub, adapter):
        import anthropic
        stub.mode = "hang"
        box = _bounded(lambda: _call(adapter, timeout=0.5), 10)
        assert isinstance(box.get("error"), anthropic.APITimeoutError)
        assert len(stub.seen) == 1
        assert 0.4 <= box["elapsed"] < 1.5

    def test_a_dropped_connection_is_one_attempt(self, stub, adapter):
        # The SDK retries a connection error too: before this change, three
        # attempts in 1.18 s against a stub that dropped the connection.
        import anthropic
        stub.mode = "drop"
        box = _bounded(lambda: _call(adapter, timeout=2.0), 10)
        assert type(box.get("error")) is anthropic.APIConnectionError
        assert len(stub.seen) == 1
        assert box["elapsed"] < 0.3

    def test_a_zero_budget_is_still_a_budget(self, stub, adapter):
        # 0.0 is falsy but given. On loopback httpx fails the connect at
        # once; the retrying client would back off twice (at least 1.1 s).
        import anthropic
        stub.mode = "529"
        box = _bounded(lambda: _call(adapter, timeout=0.0), 10)
        assert isinstance(box.get("error"), anthropic.APIError)
        assert len(stub.seen) <= 1
        assert box["elapsed"] < 0.3

    def test_a_good_reply_is_unchanged(self, stub, adapter):
        box = _bounded(lambda: _call(adapter, timeout=3.0), 10)
        result = box["value"]
        assert result.text == "ALLOW" and result.complete is True
        assert result.resolved_model == "fixture-resolved"
        assert result.provider == "anthropic"
        assert len(stub.seen) == 1

    def test_both_paths_send_the_same_request_and_credential(self, stub, adapter):
        _call(adapter, timeout=3.0)
        _call(adapter)
        with_deadline, without = stub.seen
        assert with_deadline["path"] == without["path"] == "/v1/messages"
        assert with_deadline["x-api-key"] == without["x-api-key"] == FAKE_KEY
        assert json.loads(with_deadline["body"]) == json.loads(without["body"])

    def test_a_bearer_token_rides_on_the_deadline_call_too(self, stub, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY")
        monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "fixture-bearer")
        built = AnthropicProvider()
        try:
            assert built.configured()
            _call(built, timeout=3.0)
        finally:
            built._client.close()
        assert stub.seen[0]["authorization"] == "Bearer fixture-bearer"
        assert stub.seen[0]["x-api-key"] is None


class TestWithoutACallerTimeoutTheSdkStillRetries:
    def test_an_overloaded_provider_sees_three_attempts(self, stub, adapter):
        import anthropic
        stub.mode = "529"
        stub.extra_headers = {"retry-after-ms": "20"}  # keep the test fast
        box = _bounded(lambda: _call(adapter), 10)
        assert isinstance(box.get("error"), anthropic.APIStatusError)
        assert box["error"].status_code == 529
        assert len(stub.seen) == 3


class TestTheNoRetryClient:
    def test_it_is_built_once_and_shares_the_base_clients_transport(self, stub):
        built = AnthropicProvider()
        try:
            seen = []
            workers = [threading.Thread(
                target=lambda: seen.append(built._get_deadline_client()), daemon=True)
                for _ in range(8)]
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join(5)
            base = built._get_client()
            assert len(seen) == 8 and all(client is seen[0] for client in seen)
            deadline = seen[0]
            assert deadline is not base
            assert deadline.max_retries == 0 and base.max_retries == 2
            # One connection pool, one credential, one destination.
            assert deadline._client is base._client
            assert deadline.api_key == base.api_key == FAKE_KEY
            assert deadline.base_url == base.base_url
        finally:
            built._client.close()

    def test_racing_first_calls_build_one_copy(self, stub, monkeypatch):
        # Eight first calls released together, with the copy slow to build,
        # so each one finds no copy yet: the lock and its re-check must
        # leave one builder and hand the rest that copy.
        built = AnthropicProvider()
        base = built._get_client()
        real = base.with_options
        builds = []

        def slow_with_options(**options):
            builds.append(options)
            time.sleep(0.05)
            return real(**options)

        monkeypatch.setattr(base, "with_options", slow_with_options)
        start = threading.Barrier(8)
        seen = []

        def first_call():
            start.wait(5)
            seen.append(built._get_deadline_client())

        workers = [threading.Thread(target=first_call, daemon=True) for _ in range(8)]
        try:
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join(5)
            assert not any(worker.is_alive() for worker in workers)
            assert builds == [{"max_retries": 0}]
            assert len(seen) == 8 and all(client is seen[0] for client in seen)
            assert seen[0].max_retries == 0
        finally:
            base.close()

    def test_it_follows_a_replaced_base_client(self, stub):
        # The eval harness replaces ``_client`` with its own no-retry copy.
        built = AnthropicProvider()
        try:
            first = built._get_deadline_client()
            replacement = built._get_client().with_options(timeout=7.0)
            built._client = replacement
            second = built._get_deadline_client()
            assert second is not first
            assert second.max_retries == 0 and second.timeout == 7.0
            assert second._client is replacement._client
        finally:
            built._client.close()


# ── The screen: held at once, the slot back, nothing published ─────────────

@pytest.fixture
def anthropic_screen(stub, monkeypatch):
    """The default adapter, rebuilt against the stub, with fresh slots."""
    from consciousness import anthropic_provider
    selected = anthropic_provider.provider
    monkeypatch.setattr(selected, "_client", None)
    monkeypatch.setattr(selected, "_deadline_pair", None)
    monkeypatch.delenv(runtime.PROVIDER_ENV, raising=False)
    monkeypatch.delenv(runtime.MODERATION_MODEL_ENV, raising=False)
    monkeypatch.delenv(moderation.DISABLE_MODERATION_ENV, raising=False)
    monkeypatch.setattr(runtime, "_semaphores", {})
    monkeypatch.setattr(runtime, "_semaphore_limits", {})
    monkeypatch.setenv("NESTED_WORLDS_ANTHROPIC_CONCURRENCY", str(LIMIT))
    stub.mode = "429"
    stub.extra_headers = {"retry-after": "60"}
    try:
        yield stub
    finally:
        if selected._client is not None:
            selected._client.close()


def _free_slots():
    gate = runtime._semaphore_for("anthropic")
    taken = 0
    while gate.acquire(blocking=False):
        taken += 1
    for _ in range(taken):
        gate.release()
    return taken


class TestTheScreenHoldsAtOnce:
    def test_a_rate_limited_classify_holds_the_line_without_waiting_a_minute(
            self, anthropic_screen, caplog):
        import consciousness
        assert consciousness._MODERATION_TIMEOUT_SECONDS == 3.0  # the real one
        assert runtime.get_provider().name == "anthropic"
        caplog.set_level(logging.INFO)
        box = _bounded(lambda: moderation.screen(AMBIGUOUS, surface="chat"), 8)
        verdict = box.get("value")
        assert verdict == moderation.Verdict(False, "error", "error")
        assert moderation.player_line(verdict) == moderation.HOLD_LINE
        assert box["elapsed"] < 3.0
        assert len(anthropic_screen.seen) == 1
        assert "moderation_call outcome=error surface=chat ms=" in caplog.text
        assert AMBIGUOUS not in caplog.text and FAKE_KEY not in caplog.text
        assert _free_slots() == LIMIT

    def test_a_clear_verdict_still_publishes(self, anthropic_screen):
        anthropic_screen.mode = "ok"
        anthropic_screen.extra_headers = {}
        assert moderation.screen(AMBIGUOUS, surface="chat") == \
            moderation.Verdict(True, "classify", "allow")
        assert len(anthropic_screen.seen) == 1
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


def test_a_held_chat_frees_the_reader_within_seconds(base, anthropic_screen):
    """The G5 case: a chat being screened holds the socket's reader."""
    sender, status = _ws_connect(base, SEED, "Ada")
    try:
        assert b"101" in status
        _read_ws_json_until(sender, "welcome")
        started = time.monotonic()
        _ws_send_json(sender, {"type": "chat", "text": AMBIGUOUS})
        declined = _read_ws_json_until(sender, "chat_declined", timeout=8)
        elapsed = time.monotonic() - started
        assert declined["text"] == moderation.HOLD_LINE
        assert elapsed < 3.0
        _ws_send_json(sender, {"type": "ping"})
        assert _read_ws_json_until(sender, "pong") == {"type": "pong"}
    finally:
        sender.close()
    root = store.world_tree(SEED).name
    assert [row for row in persistence.get_node_history(SEED, root, 50)
            if row["type"] == "PLAYER_CHAT"] == []
    assert len(anthropic_screen.seen) == 1
    assert _free_slots() == LIMIT


# ── The other built-in adapter already conforms ────────────────────────────

class TestOpenAICompatibleConforms:
    @pytest.fixture
    def compat(self, monkeypatch):
        from consciousness.openai_compat_provider import OpenAICompatibleProvider
        server = _start_loopback()
        _arm(monkeypatch, url=f"http://127.0.0.1:{server.server_address[1]}/v1", key=_SECRET)
        try:
            yield OpenAICompatibleProvider(), server
        finally:
            _stop_loopback(server)

    def test_a_server_error_is_one_post(self, compat):
        from consciousness.openai_compat_provider import ProviderHTTPError
        adapter, server = compat
        server.mode = "fail"  # the handler answers 500
        box = _bounded(lambda: adapter.generate(
            model="compat-moderation", system=(SystemBlock("classify"),),
            messages=[{"role": "user", "content": "words"}], max_tokens=32,
            timeout=2.0), 10)
        assert isinstance(box.get("error"), ProviderHTTPError)
        assert box["error"].status == 500
        assert len(server.seen) == 1
        assert box["elapsed"] < 1.0

    def test_a_slow_server_is_one_post_within_the_timeout(self, compat):
        from consciousness.openai_compat_provider import ProviderTimeout
        adapter, server = compat
        server.mode = "slow"  # answers after 2 s
        box = _bounded(lambda: adapter.generate(
            model="compat-moderation", system=(SystemBlock("classify"),),
            messages=[{"role": "user", "content": "words"}], max_tokens=32,
            timeout=0.5), 10)
        assert isinstance(box.get("error"), ProviderTimeout)
        assert len(server.seen) == 1
        assert 0.4 <= box["elapsed"] < 1.5
