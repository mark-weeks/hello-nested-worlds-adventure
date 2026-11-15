"""Live chat commits to private storage before delivery and never to history."""
from __future__ import annotations

from contextlib import contextmanager
import json
import threading
from types import SimpleNamespace

import pytest

import persistence
from persistence import community, participants
from server import _Handler, _ThreadedServer, community_policy, websocket
from tests.test_day_one_recording import _ws_connect, _ws_send_json
from tests.test_ws_credential_lifetime import _until_close, _until_type


pytestmark = pytest.mark.usefixtures("community_collection")


@contextmanager
def running(*keys):
    from persistence import participation as consents
    from server import participation
    current = participation.notice()
    if current["required"]:
        assert current["ready"]
        for key in keys:
            consents.accept(key, current["revision"], participation.snapshot(current))
    server = _ThreadedServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    sockets = []
    try:
        for index, key in enumerate(keys):
            sock, status = _ws_connect(server.server_port, 382, f"Local{index}", invite_key=key)
            assert b"101" in status
            sockets.append(sock)
            _until_type(sock, "welcome")
        yield sockets
    finally:
        for sock in sockets:
            sock.close()
        server.shutdown()
        server.server_close()
        thread.join(5)


def test_private_commit_precedes_every_chat_broadcast(accounts, monkeypatch):
    observed = []
    original = websocket.broadcast

    def checked(room, message, **kwargs):
        if message.get("type") == "chat":
            assert not persistence.in_transaction()
            stored = community.evidence_author(evidence_ref=message["evidence_ref"], world_seed=382)
            assert stored["participant_id"] == participants.identify(accounts[0])["id"]
            observed.append(message)
        return original(room, message, **kwargs)

    monkeypatch.setattr(websocket, "broadcast", checked)
    with running(*accounts) as (sender, receiver):
        _ws_send_json(sender, {"type": "chat", "text": "private fixture chat", "ref": "draft-1"})
        sent = _until_type(sender, "chat")[0]
        received = _until_type(receiver, "chat")[0]
        assert sent["evidence_ref"] == received["evidence_ref"]
        assert sent["text"] == received["text"] == "private fixture chat"
        assert "ref" not in sent and "ref" not in received
    assert len(observed) == 1
    with persistence._connection() as conn:
        assert conn.execute("SELECT count(*) FROM world_mutations WHERE mutation_type='PLAYER_CHAT'").fetchone()[0] == 0
    public = json.dumps(persistence.get_mutations(382))
    assert "private fixture chat" not in public


def test_failed_log_commit_is_a_private_decline_and_never_broadcast(accounts, monkeypatch, caplog):
    from server import moderation
    screened, collected = [], []

    def screen(text, **kwargs):
        screened.append(text)
        return SimpleNamespace(allowed=True)

    def unavailable(**_kwargs):
        collected.append(_kwargs["text"])
        error = community.CommunityUnavailable()
        error.args = ("private payload that must not be logged",)
        raise error

    monkeypatch.setattr(moderation, "screen", screen)
    monkeypatch.setattr(community, "append_chat", unavailable)
    with running(*accounts) as (sender, receiver):
        _ws_send_json(sender, {"type": "chat", "text": "private fixture chat", "ref": "keep-this-draft"})
        declined, _ = _until_type(sender, "chat_declined")
        assert declined == {"type": "chat_declined", "ref": "keep-this-draft",
                            "text": "Your message could not be delivered. Please try again later."}
        _ws_send_json(receiver, {"type": "ping"})
        _, before = _until_type(receiver, "pong")
        assert not any(row.get("type") in ("chat", "chat_declined") for row in before)
    assert screened == collected == ["private fixture chat"]
    assert "private payload that must not be logged" not in caplog.text
    with persistence._connection() as conn:
        assert conn.execute("SELECT count(*) FROM world_mutations WHERE mutation_type='PLAYER_CHAT'").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM private_chat_messages").fetchone()[0] == 0


@pytest.mark.parametrize("unavailable", ["missing", "disabled", "emergency"])
def test_unavailable_chat_never_screens_or_collects_a_draft(accounts, monkeypatch, tmp_path, unavailable):
    from consciousness import runtime
    from server import moderation

    if unavailable == "missing":
        monkeypatch.delenv(community_policy.POLICY_ENV)
    elif unavailable == "emergency":
        monkeypatch.setenv(community_policy.DISABLE_CHAT_ENV, "1")
    else:
        path = tmp_path / "unavailable-community.json"
        path.write_text(json.dumps({
            "schema_version": 1, "policy_id": "disabled-fixture",
            "chat": {"enabled": False}, "reports": {"enabled": False},
        }))
        monkeypatch.setenv(community_policy.POLICY_ENV, str(path))
    community_policy.reset_for_tests()

    def forbidden(*_args, **_kwargs):
        pytest.fail("an unavailable chat surface screened or collected a draft")

    monkeypatch.setattr(moderation, "screen", forbidden)
    monkeypatch.setattr(runtime, "generate", forbidden)
    monkeypatch.setattr(community, "append_chat", forbidden)
    with running(*accounts) as (sender, receiver):
        _ws_send_json(sender, {"type": "chat", "text": "not collected", "ref": "draft-2"})
        assert _until_type(sender, "chat_declined")[0] == {
            "type": "chat_declined", "ref": "draft-2", "text": "Chat is unavailable in this world.",
        }
        _ws_send_json(receiver, {"type": "ping"})
        assert not any(row.get("type") in ("chat", "chat_declined") for row in _until_type(receiver, "pong")[1])
    with persistence._connection() as conn:
        assert conn.execute("SELECT count(*) FROM world_mutations WHERE mutation_type='PLAYER_CHAT'").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM private_chat_messages").fetchone()[0] == 0


@pytest.mark.parametrize("policy_failure", ["emergency", "availability_error"])
def test_chat_disabled_during_screen_keeps_the_final_collection_fence(accounts, monkeypatch, policy_failure):
    from server import moderation

    def invalid():
        raise community_policy.CommunityPolicyError()

    def disable(*_args, **_kwargs):
        if policy_failure == "emergency":
            monkeypatch.setenv(community_policy.DISABLE_CHAT_ENV, "1")
        else:
            monkeypatch.setattr(community_policy, "chat_enabled", invalid)
        return type("Allowed", (), {"allowed": True})()

    monkeypatch.setattr(moderation, "screen", disable)
    monkeypatch.setattr(community, "append_chat",
                        lambda **_kwargs: pytest.fail("chat collected after an emergency disable"))
    with running(*accounts) as (sender, receiver):
        _ws_send_json(sender, {"type": "chat", "text": "not collected", "ref": "draft-3"})
        assert _until_type(sender, "chat_declined")[0] == {
            "type": "chat_declined", "ref": "draft-3", "text": "Chat is unavailable in this world.",
        }
        _ws_send_json(receiver, {"type": "ping"})
        assert not any(row.get("type") in ("chat", "chat_declined") for row in _until_type(receiver, "pong")[1])
    with persistence._connection() as conn:
        assert conn.execute("SELECT count(*) FROM private_chat_messages").fetchone()[0] == 0


def test_unkeyed_local_chat_has_private_session_evidence_without_a_participant():
    with running(None, None) as (sender, receiver):
        _ws_send_json(sender, {"type": "chat", "text": "local private line"})
        line = _until_type(receiver, "chat")[0]
        author = community.evidence_author(evidence_ref=line["evidence_ref"], world_seed=382)
        assert author["participant_id"] is None
        assert len(author["session_id"]) == 32
        assert author["name"] == "Local0"


def test_revocation_after_screen_leaves_no_private_line(accounts, monkeypatch):
    from server import moderation

    def revoke(*_args, **_kwargs):
        persistence.revoke_invite_key(accounts[0])
        return type("Allowed", (), {"allowed": True})()

    monkeypatch.setattr(moderation, "screen", revoke)
    monkeypatch.setattr(community, "append_chat",
                        lambda **_kwargs: pytest.fail("a revoked chat was collected"))
    with running(*accounts) as (sender, receiver):
        _ws_send_json(sender, {"type": "chat", "text": "revoked during screen"})
        left = _until_type(receiver, "player_leave")[0]
        assert left["name"] == "Ada"


@pytest.mark.parametrize("text", ["embedded\x00text", "\ud800", "\udfff"])
def test_invalid_text_is_a_permanent_decline_before_screen_or_storage(accounts, monkeypatch, text):
    from server import moderation

    def forbidden(*_args, **_kwargs):
        pytest.fail("invalid chat text reached moderation or storage")

    monkeypatch.setattr(moderation, "screen", forbidden)
    monkeypatch.setattr(community, "append_chat", forbidden)
    with running(*accounts) as (sender, receiver):
        _ws_send_json(sender, {"type": "chat", "text": text, "ref": "invalid-draft"})
        decline, before = _until_type(sender, "chat_declined")
        assert decline == {"type": "chat_declined", "ref": "invalid-draft",
                           "text": "A valid message is required."}
        assert not any(frame.get("type") == "error" for frame in before)
        _ws_send_json(receiver, {"type": "ping"})
        assert not any(frame.get("type") == "chat" for frame in _until_type(receiver, "pong")[1])
    with persistence._connection() as conn:
        assert conn.execute("SELECT count(*) FROM private_chat_messages").fetchone()[0] == 0


def test_invalid_policy_during_screen_closes_session_before_private_write(accounts, monkeypatch):
    from server import moderation

    def invalid():
        raise community_policy.CommunityPolicyError()

    def corrupt(*_args, **_kwargs):
        monkeypatch.setattr(community_policy, "current", invalid)
        return SimpleNamespace(allowed=True)

    monkeypatch.setattr(moderation, "screen", corrupt)
    monkeypatch.setattr(community, "append_chat",
                        lambda **_kwargs: pytest.fail("invalid study policy collected chat"))
    with running(*accounts) as (sender, _receiver):
        _ws_send_json(sender, {"type": "chat", "text": "invalid policy during screen"})
        code, before = _until_close(sender)
        assert code == 1008
        assert not any(frame.get("type") in ("chat", "error") for frame in before)


def test_until_deleted_policy_collects_no_expiry_without_history(accounts, monkeypatch, tmp_path):
    declaration = tmp_path / "until-deleted.json"
    declaration.write_text(json.dumps({
        "schema_version": 1, "policy_id": "until-deleted-fixture",
        "chat": {"enabled": True, "retention_mode": "until_deleted"},
        "reports": {"enabled": False}, "contact": "Fixture operator",
        "backup_notice": "Synthetic disposable backups.",
    }))
    monkeypatch.setenv(community_policy.POLICY_ENV, str(declaration))
    community_policy.reset_for_tests()
    with running(*accounts) as (sender, receiver):
        _ws_send_json(sender, {"type": "chat", "text": "private until deletion"})
        message = _until_type(receiver, "chat")[0]
    with persistence._connection() as conn:
        assert conn.execute("SELECT expires_at,retention_days FROM private_chat_messages WHERE evidence_ref=?",
                            (message["evidence_ref"],)).fetchone() == (None, None)
        assert conn.execute("SELECT count(*) FROM world_mutations WHERE mutation_type='PLAYER_CHAT'").fetchone()[0] == 0
