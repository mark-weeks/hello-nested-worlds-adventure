"""Operator community declarations are explicit, immutable and offline."""
from __future__ import annotations

from copy import deepcopy
import json
import socket
import urllib.request

import pytest

import persistence
from persistence import participation as consents
from server import community_policy as policy, participation


def _forbidden(*args, **kwargs):
    raise AssertionError("policy parsing reached an external side effect")


@pytest.fixture(autouse=True)
def isolated_policy(monkeypatch, _community_test_policy):
    monkeypatch.delenv(policy.POLICY_ENV, raising=False)
    monkeypatch.delenv(policy.DISABLE_CHAT_ENV, raising=False)
    monkeypatch.delenv(policy.DISABLE_REPORTS_ENV, raising=False)
    policy.reset_for_tests()
    yield
    policy.reset_for_tests()


def _document():
    return {
        "schema_version": 1, "policy_id": "synthetic-community-test",
        "chat": {"enabled": True, "retention_days": 2},
        "reports": {"enabled": True, "retention_days": 3},
        "contact": "Synthetic fixture operator",
        "backup_notice": "Synthetic fixture backup statement; no production approval.",
    }


def _file(tmp_path, data=None):
    path = tmp_path / "community.json"
    path.write_text(json.dumps(_document() if data is None else data))
    return path


def test_missing_policy_freezes_collection_off_without_retention_or_contact_defaults(monkeypatch, tmp_path):
    current = policy.current()
    assert (current.chat_days, current.report_days, current.contact, current.backup_notice) == (None, None, "", "")
    assert not policy.chat_enabled() and not policy.reports_enabled()
    monkeypatch.setenv(policy.POLICY_ENV, str(_file(tmp_path)))
    monkeypatch.setenv(policy.DISABLE_CHAT_ENV, "0")
    monkeypatch.setenv(policy.DISABLE_REPORTS_ENV, "0")
    assert policy.current() is current
    assert not policy.chat_enabled() and not policy.reports_enabled()
    assert not persistence._DB_PATH.exists()


def test_offline_check_neither_activates_nor_touches_database_or_network(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "init_db", _forbidden)
    monkeypatch.setattr(socket, "create_connection", _forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", _forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", _forbidden)
    checked = policy.check_file(_file(tmp_path))
    assert checked.chat_days == 2 and checked.report_days == 3
    assert policy.current().chat_days is None
    assert not policy.chat_enabled() and not persistence._DB_PATH.exists()


def test_until_deleted_is_explicit_chat_only_and_disclosed_without_a_deadline(tmp_path, monkeypatch):
    data = _document()
    data["chat"] = {"enabled": True, "retention_mode": "until_deleted"}
    path = _file(tmp_path, data)
    monkeypatch.setenv(policy.POLICY_ENV, str(path))
    declared = policy.initialize()
    assert declared.chat_days is None and declared.chat_retention_mode == "until_deleted"
    metadata = policy.metadata()
    assert metadata["chat"]["enabled"] is True
    assert metadata["chat"]["retention_days"] is None
    assert metadata["chat"]["retention_mode"] == "until_deleted"
    assert "until you ask for deletion or leave the study" in metadata["chat"]["notice"]
    assert "only operators can read" in metadata["chat"]["notice"]
    assert "until that report closes" in metadata["chat"]["notice"]
    data["reports"] = {"enabled": True, "retention_mode": "until_deleted"}
    with pytest.raises(policy.CommunityPolicyError):
        policy.check_file(_file(tmp_path, data))


@pytest.mark.parametrize("route", [
    {"enabled": True, "retention_mode": "forever"},
    {"enabled": True, "retention_mode": "until_deleted", "retention_days": 1},
    {"enabled": False, "retention_mode": "until_deleted"},
])
def test_invalid_until_deleted_declaration_is_refused(tmp_path, route):
    data = _document()
    data["chat"] = route
    with pytest.raises(policy.CommunityPolicyError):
        policy.check_file(_file(tmp_path, data))


@pytest.mark.parametrize("route", ["chat", "reports"])
def test_enabling_one_route_requires_only_its_explicit_retention(tmp_path, route):
    data = _document()
    other = "reports" if route == "chat" else "chat"
    data[other] = {"enabled": False}
    result = policy.check_file(_file(tmp_path, data))
    assert getattr(result, "chat_days" if route == "chat" else "report_days") in (2, 3)
    assert getattr(result, "report_days" if route == "chat" else "chat_days") is None


@pytest.mark.parametrize("field,value", [
    ("schema_version", True), ("schema_version", 2), ("schema_version", "1"),
    ("policy_id", ""), ("policy_id", "untrusted path/secret"),
    ("contact", ""), ("contact", " padded "), ("contact", "line\nbreak"),
    ("contact", "x" * 1001), ("contact", "\ud800"),
    ("backup_notice", ""), ("backup_notice", None), ("backup_notice", "line\x7fbreak"),
])
def test_invalid_operator_fields_are_rejected_without_echoing_them(tmp_path, field, value):
    data = _document()
    data[field] = value
    with pytest.raises(policy.CommunityPolicyError, match="^Community collection policy is invalid.$"):
        policy.check_file(_file(tmp_path, data))


@pytest.mark.parametrize("route", ["chat", "reports"])
@pytest.mark.parametrize("value", [None, {}, [], {"enabled": True}, {"enabled": 1, "retention_days": 2},
    {"enabled": "false"}, {"enabled": False, "retention_days": 2},
    {"enabled": True, "retention_days": True}, {"enabled": True, "retention_days": 0},
    {"enabled": True, "retention_days": -1}, {"enabled": True, "retention_days": 36501},
    {"enabled": True, "retention_days": 2.0}, {"enabled": True, "retention_days": "2"},
    {"enabled": True, "retention_days": None}, {"enabled": True, "retention_days": 2, "extra": 1},
])
def test_invalid_route_never_borrows_a_retention_default(tmp_path, route, value):
    data = _document()
    data[route] = value
    with pytest.raises(policy.CommunityPolicyError):
        policy.check_file(_file(tmp_path, data))


@pytest.mark.parametrize("missing", ["schema_version", "policy_id", "chat", "reports", "contact", "backup_notice"])
def test_enabled_policy_requires_every_applicable_field(tmp_path, missing):
    data = _document()
    del data[missing]
    with pytest.raises(policy.CommunityPolicyError):
        policy.check_file(_file(tmp_path, data))


def test_unknown_top_level_fields_are_refused(tmp_path):
    data = _document()
    data["automatic_erasure_guaranteed"] = True
    with pytest.raises(policy.CommunityPolicyError):
        policy.check_file(_file(tmp_path, data))


@pytest.mark.parametrize("raw", [
    b'{"schema_version":1,"schema_version":1,"policy_id":"x","chat":{"enabled":false},"reports":{"enabled":false}}',
    b'{"schema_version":1,"policy_id":"x","chat":{"enabled":false,"enabled":false},"reports":{"enabled":false}}',
    b'{"schema_version":NaN}', b'{"schema_version":Infinity}', b"\xff", b"not JSON",
    b"[" * 2000 + b"]" * 2000, b" " * 16385,
])
def test_malformed_duplicate_or_oversized_files_have_safe_errors(tmp_path, raw):
    path = tmp_path / "untrusted.json"
    path.write_bytes(raw)
    with pytest.raises(policy.CommunityPolicyError, match="^Community collection policy is invalid.$"):
        policy.check_file(path)


@pytest.mark.parametrize("path", ["", "   ", "/nonexistent/private-community-policy.json"])
def test_supplied_invalid_path_refuses_instead_of_defaulting_off(monkeypatch, path):
    monkeypatch.setenv(policy.POLICY_ENV, path)
    with pytest.raises(policy.CommunityPolicyError):
        policy.initialize()
    assert not persistence._DB_PATH.exists()


def test_snapshot_survives_file_and_environment_changes(tmp_path, monkeypatch):
    first = _file(tmp_path)
    monkeypatch.setenv(policy.POLICY_ENV, str(first))
    original = policy.initialize()
    original_metadata = deepcopy(policy.metadata())
    first.write_text("malformed replacement")
    replacement = tmp_path / "off.json"
    replacement.write_text(json.dumps({"schema_version": 1, "policy_id": "other",
                                       "chat": {"enabled": False}, "reports": {"enabled": False}}))
    monkeypatch.setenv(policy.POLICY_ENV, str(replacement))
    assert policy.current() is original and policy.metadata() == original_metadata
    assert policy.chat_enabled() and policy.reports_enabled()
    assert json.loads(original.snapshot_json) == _document()


def test_revision_follows_effective_document_not_json_formatting(tmp_path):
    path = _file(tmp_path)
    first = policy.check_file(path)
    data = _document()
    path.write_text(json.dumps(dict(reversed(list(data.items()))), indent=3))
    assert policy.check_file(path).revision == first.revision
    data["backup_notice"] = "A different synthetic backup statement."
    path.write_text(json.dumps(data))
    assert policy.check_file(path).revision != first.revision


def test_emergency_denials_change_availability_without_invalidating_consent(tmp_path, monkeypatch, accounts):
    monkeypatch.setenv(policy.POLICY_ENV, str(_file(tmp_path)))
    for key, value in {"TEST_WORLD": "1", "TEST_CONTACT": "Fixture facilitator",
                       "TEST_RETENTION": "Synthetic test records and backups only.",
                       "TEST_MIN_AGE": "18", "TEST_DATA_USE": "No provider receives fixture data."}.items():
        monkeypatch.setenv("NESTED_WORLDS_" + key, value)
    before = participation.notice()
    assert before["ready"]
    consents.accept(accounts[0], before["revision"], participation.snapshot(before))
    metadata = policy.metadata()
    for name in (policy.DISABLE_CHAT_ENV, policy.DISABLE_REPORTS_ENV):
        monkeypatch.setenv(name, "1")
    denied = policy.metadata()
    assert not denied["chat"]["enabled"] and not denied["reports"]["enabled"]
    assert denied["revision"] == metadata["revision"]
    assert denied["chat"]["notice"] == metadata["chat"]["notice"]
    assert denied["reports"]["notice"] == metadata["reports"]["notice"]
    assert participation.notice()["revision"] == before["revision"]
    assert participation.session_authorized(accounts[0])
    monkeypatch.setenv(policy.DISABLE_CHAT_ENV, "0")
    monkeypatch.setenv(policy.DISABLE_REPORTS_ENV, "0")
    assert policy.chat_enabled() and policy.reports_enabled()
