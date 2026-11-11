"""A disposable-world notice is acknowledged by its actual participant."""
from __future__ import annotations

import threading
import json
from concurrent.futures import ThreadPoolExecutor

import pytest

import persistence
from persistence import participation as consents, participants
from server import _Handler, _ThreadedServer, guard, participation
from tests.test_day_one_recording import _ws_connect, _ws_send_json
from tests.test_moderation import _read_ws_json_until
from tests.test_ws_credential_lifetime import _until_close, _wait_rows


_CONFIG = {
    "TEST_WORLD": "1",
    "TEST_CONTACT": "Research facilitator: example@example.test",
    "TEST_RETENTION": "The facilitator removes this scratch world and its test backups on 2030-01-31.",
    "TEST_MIN_AGE": "18",
    "TEST_DATA_USE": "This test has no model credentials; no model provider receives test data.",
}


@pytest.fixture(autouse=True)
def clean_test_world_configuration(monkeypatch):
    for key in _CONFIG:
        monkeypatch.delenv("NESTED_WORLDS_" + key, raising=False)


@pytest.fixture
def configured(monkeypatch):
    for key, value in _CONFIG.items():
        monkeypatch.setenv("NESTED_WORLDS_" + key, value)
    return participation.notice()


def _rows(table):
    with persistence._connection() as conn:
        return conn.execute(f"SELECT * FROM {table}").fetchall()


def _accept(http, key=None):
    status, notice, _ = http("/participation", key) if key is not None else http("/participation")
    assert status == 200
    body = {"accepted": True, "revision": notice["revision"]}
    status, notice, _ = http("/participation", key, body) if key is not None else http("/participation", body=body)
    assert status == 200 and notice["accepted"]
    return notice


def test_default_off_preserves_gameplay_and_has_no_consent_enrollment(http):
    status, metadata, headers = http("/participation", "")
    assert status == 200 and metadata == {
        "required": False, "ready": True, "accepted": False,
        "revision": "", "title": "Enfolded", "paragraphs": [], "minimum_age": None,
    }
    assert headers["Cache-Control"] == "no-store"
    assert http("/world?depth=1")[0] == 200
    assert _rows("participation_consents") == []


def test_notice_assets_are_public_and_served_under_the_production_headers(http, configured):
    for path, content_type in (("/participation.js", "application/javascript"), ("/participation.css", "text/css")):
        status, content, headers = http(path, "")
        assert status == 200 and content
        assert headers["Content-Type"].startswith(content_type)
        assert headers["X-Content-Type-Options"] == "nosniff"


def test_public_notice_does_not_enroll_an_account_or_reveal_another_acceptance(http, accounts, configured):
    assert _rows("participant_credentials") == []
    assert http("/participation", "")[1] == configured
    assert http("/participation", accounts[0])[1] == configured
    assert _rows("participant_credentials") == []
    _accept(http)
    assert http("/participation", accounts[1])[1]["accepted"] is False
    assert http("/participation", "")[1]["accepted"] is False
    assert http("/participation", accounts[0])[1]["accepted"] is True
    assert set(http("/participation")[1]) == {
        "required", "ready", "accepted", "revision", "title", "paragraphs", "minimum_age",
    }
    assert len(_rows("participant_credentials")) == 1


@pytest.mark.parametrize("missing", ["TEST_CONTACT", "TEST_RETENTION", "TEST_MIN_AGE", "TEST_DATA_USE"])
def test_incomplete_notice_keeps_shells_available_but_gameplay_and_acceptance_closed(http, configured, monkeypatch, missing):
    monkeypatch.delenv("NESTED_WORLDS_" + missing)
    status, metadata, _ = http("/participation", "")
    assert status == 200 and metadata["required"] and not metadata["ready"]
    assert metadata["revision"] == ""
    for path in ("/health", "/app", "/", "/register", "/guide"):
        assert http(path, "")[0] == 200
    assert http("/world")[0] == 503
    assert http("/participation", body={"accepted": True, "revision": ""})[0] == 503
    assert http("/world", "unknown-key")[0] == 403
    assert _rows("participation_consents") == []
    assert persistence.get_mutations(382) == []
    assert not persistence.world_is_born(382)


@pytest.mark.parametrize("age", ["", "0", "-1", "121", "18.0", "eighteen", "１８"])
def test_invalid_age_is_incomplete_not_a_default_policy(http, configured, monkeypatch, age):
    monkeypatch.setenv("NESTED_WORLDS_TEST_MIN_AGE", age)
    metadata = http("/participation", "")[1]
    assert metadata["minimum_age"] is None and not metadata["ready"]
    assert http("/world")[0] == 503


def test_misspelled_enable_flag_does_not_open_the_test_world(http, configured, monkeypatch):
    monkeypatch.setenv("NESTED_WORLDS_TEST_WORLD", "true")
    metadata = http("/participation", "")[1]
    assert metadata["required"] and not metadata["ready"]
    assert http("/world")[0] == 503


def test_every_gameplay_dispatch_is_fenced_before_world_writes_or_provider_calls(http, configured, monkeypatch):
    from consciousness import runtime
    from server import moderation

    def forbidden(*args, **kwargs):
        pytest.fail("An unacknowledged request reached moderation or a provider")

    monkeypatch.setattr(runtime, "generate", forbidden)
    monkeypatch.setattr(moderation, "screen", forbidden)
    for path in ("/world", "/history", "/chronicle", "/position", "/me", "/journal/data",
                 "/worlds", "/puzzle?node_name=unknown", "/ideas/list"):
        status, body, headers = http(path)
        assert status == 428 and body["participation_required"]
        assert headers["Cache-Control"] == "no-store"
    for path in ("/speak", "/agent/voice", "/image", "/puzzle/attempt", "/act", "/position",
                 "/journal/note", "/profile/save", "/blocks", "/ideas/submit"):
        assert http(path, body={"message": "hello", "node_name": "unknown"})[0] == 428
    assert persistence.get_mutations(382) == []
    assert not persistence.world_is_born(382)
    assert _rows("participant_credentials") == []
    assert _rows("participation_consents") == []


@pytest.mark.parametrize("body,code", [
    ({}, 400),
    ({"accepted": False, "revision": "current"}, 400),
    ({"accepted": 1, "revision": "current"}, 400),
    ({"accepted": "true", "revision": "current"}, 400),
    ({"accepted": True, "revision": "current", "participant": "someone-else"}, 400),
    ({"accepted": True, "revision": None}, 409),
    ({"accepted": True, "revision": "outdated"}, 409),
])
def test_acceptance_requires_an_affirmative_current_submission(http, configured, body, code):
    if body.get("revision") == "current":
        body = {**body, "revision": configured["revision"]}
    assert http("/participation", body=body)[0] == code
    assert _rows("participation_consents") == []


def test_accepted_notice_opens_only_that_person_and_repeats_idempotently(http, accounts, configured):
    accepted = _accept(http)
    rows = _rows("participation_consents")
    assert len(rows) == 1 and rows[0][1] == accepted["revision"]
    assert _accept(http) == accepted
    assert _rows("participation_consents") == rows
    assert persistence.get_mutations(382) == []
    assert http("/world?depth=1")[0] == 200
    assert http("/world?depth=1", accounts[1])[0] == 428


def test_concurrent_acknowledgements_keep_one_owner_and_one_snapshot(accounts, configured):
    document = participation.snapshot(configured)
    with ThreadPoolExecutor(4) as pool:
        list(pool.map(lambda _: consents.accept(accounts[0], configured["revision"], document), range(4)))
    assert len(_rows("participant_credentials")) == 1
    assert len(_rows("participants")) == 1
    assert len(_rows("participation_consents")) == 1
    assert persistence.get_mutations(382) == []


def test_acceptance_survives_restart_and_rotation_but_refuses_the_old_key(http, accounts, configured):
    _accept(http)
    before = _rows("participation_consents")
    replacement = "nw_" + "c" * 32
    participants.rotate(accounts[0], replacement)
    persistence._initialized.discard(persistence._DB_PATH)
    assert http("/participation", replacement)[1]["accepted"]
    assert http("/world?depth=1", replacement)[0] == 200
    assert http("/participation", accounts[0])[0] == 403
    assert http("/participation", accounts[0], {"accepted": True, "revision": configured["revision"]})[0] == 403
    assert _rows("participation_consents") == before


@pytest.mark.parametrize("field", ["TEST_CONTACT", "TEST_RETENTION", "TEST_DATA_USE", "TEST_MIN_AGE"])
def test_every_effective_notice_change_requires_its_own_acknowledgement(http, configured, monkeypatch, field):
    _accept(http)
    value = "21" if field == "TEST_MIN_AGE" else _CONFIG[field] + " Updated."
    monkeypatch.setenv("NESTED_WORLDS_" + field, value)
    current = http("/participation")[1]
    assert current["ready"] and not current["accepted"]
    assert current["revision"] != configured["revision"]
    assert http("/world")[0] == 428
    assert http("/participation", body={"accepted": True, "revision": configured["revision"]})[0] == 409
    _accept(http)
    assert len(_rows("participation_consents")) == 2
    saved = {row[1]: json.loads(row[2]) for row in _rows("participation_consents")}
    assert saved[configured["revision"]] == json.loads(participation.snapshot(configured))
    assert saved[current["revision"]] == json.loads(participation.snapshot(current))


def test_unknown_and_revoked_credentials_cannot_accept(http, accounts, configured):
    assert http("/participation", "unknown")[0] == 403
    assert http("/participation", "", {"accepted": True, "revision": configured["revision"]})[0] == 403
    _accept(http)
    persistence.revoke_invite_key(accounts[0])
    assert http("/participation")[0] == 403
    assert http("/world")[0] == 403
    with pytest.raises(participants.Unauthorized):
        consents.accept(accounts[0], configured["revision"], participation.snapshot(configured))
    assert len(_rows("participation_consents")) == 1


def test_sanction_refuses_consented_key_without_disclosing_private_reason(http, accounts, configured):
    from persistence import sanctions
    _accept(http)
    recorded = _rows("participation_consents")
    sanction = sanctions.ban("Ada", "Private operator-only reason")
    for path in ("/participation", "/world"):
        assert http(path)[:2] == (403, {"error": "forbidden"})
    assert http("/participation", body={"accepted": True, "revision": configured["revision"]})[:2] == (403, {"error": "forbidden"})
    assert _rows("participation_consents") == recorded
    sanctions.lift(sanction["id"], "Resolved")
    assert http("/participation")[1]["accepted"]


def test_self_service_registration_mints_no_implicit_acknowledgement(http, configured):
    persistence.create_registration_token("nwr_participation_test")
    status, response, _ = http("/register", "", {"invite": "nwr_participation_test", "name": "Cara"})
    assert status == 200
    key = response["key"]
    assert _rows("participation_consents") == []
    assert http("/participation", key)[1]["accepted"] is False
    assert http("/world", key)[0] == 428
    _accept(http, key)
    assert http("/world?depth=1", key)[0] == 200


def test_database_check_failure_fails_closed_without_a_stack_or_internal_error(http, configured, monkeypatch):
    import sqlite3
    def unavailable(*args, **kwargs):
        raise sqlite3.OperationalError("private database detail")
    monkeypatch.setattr(consents, "accepted", unavailable)
    for path in ("/participation", "/world"):
        status, response, _ = http(path)
        assert status == 503
        assert response == {"error": "Participation could not be checked. Please try again."}


def test_public_metadata_and_acceptance_keep_existing_read_write_rate_bounds(http, configured, monkeypatch):
    monkeypatch.setenv(guard.READ_RATE_LIMIT_ENV, "1")
    guard.READ_RATE_LIMITER.reset()
    assert http("/participation", "")[0] == 200
    assert http("/participation", "")[0] == 429
    monkeypatch.setenv(guard.RATE_LIMIT_ENV, "1")
    guard.RATE_LIMITER.reset()
    assert http("/participation", body={})[0] == 400
    assert http("/participation", body={})[0] == 429
    assert _rows("participation_consents") == []


def test_revision_is_stable_and_operator_copy_is_plain_text(http, configured, monkeypatch):
    assert participation.notice() == configured
    monkeypatch.setenv("NESTED_WORLDS_TEST_CONTACT", "  " + _CONFIG["TEST_CONTACT"] + "  ")
    assert participation.notice()["revision"] == configured["revision"]
    monkeypatch.setenv("NESTED_WORLDS_TEST_CONTACT", "<script>operator copy</script>")
    metadata = http("/participation", "")[1]
    assert metadata["paragraphs"][-3] == "Questions or concerns: <script>operator copy</script>"
    assert metadata["revision"] != configured["revision"]


@pytest.fixture
def port(monkeypatch):
    monkeypatch.setenv("NESTED_WORLDS_CANONICAL_SEED", "382")
    server = _ThreadedServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_port
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)


def test_unacknowledged_websocket_upgrade_makes_no_join_or_world(port, accounts, configured):
    sock, status = _ws_connect(port, 382, "Ada", invite_key=accounts[0])
    sock.close()
    assert b"428" in status
    assert persistence.get_mutations(382) == []
    assert not persistence.world_is_born(382)


def test_notice_revision_change_closes_sending_socket_before_chat_writes(port, accounts, configured, monkeypatch):
    consents.accept(accounts[0], configured["revision"], participation.snapshot(configured))
    sock, status = _ws_connect(port, 382, "Ada", invite_key=accounts[0])
    assert b"101" in status
    try:
        _read_ws_json_until(sock, "welcome")
        monkeypatch.setenv("NESTED_WORLDS_TEST_RETENTION", "A revised operator retention statement.")
        _ws_send_json(sock, {"type": "chat", "text": "must not be recorded"})
        code, _ = _until_close(sock)
        assert code == 1008
        assert not [row for row in persistence.get_mutations(382) if row["type"] == "PLAYER_CHAT"]
    finally:
        sock.close()


def test_notice_revision_change_also_closes_a_listen_only_socket(port, accounts, configured, monkeypatch):
    monkeypatch.setattr(guard, "WS_SWEEP_INTERVAL_SEC", 0.05)
    consents.accept(accounts[0], configured["revision"], participation.snapshot(configured))
    sock, status = _ws_connect(port, 382, "Ada", invite_key=accounts[0])
    assert b"101" in status
    try:
        _read_ws_json_until(sock, "welcome")
        monkeypatch.setenv("NESTED_WORLDS_TEST_DATA_USE", "A revised provider statement.")
        code, _ = _until_close(sock)
        assert code == 1008
        assert len(_wait_rows(382, "PLAYER_LEAVE", "Ada", 1)) == 1
    finally:
        sock.close()
