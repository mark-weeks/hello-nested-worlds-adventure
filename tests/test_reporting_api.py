"""Private reports use stable receipts, retained evidence and authenticated ownership."""
from __future__ import annotations

from datetime import timedelta
import hashlib
import json
import uuid

import pytest

from consciousness import runtime
from persistence import blocks, community, participants, participation as consents
from server import block_targets, community_policy, moderation, participation


pytestmark = pytest.mark.usefixtures("community_collection")


def report(**changes):
    return {"request_id": str(uuid.uuid4()), "participant": None, "evidence_ref": None,
            "reason": "harassment", "detail": "private report detail", **changes}


def evidence(key=None):
    policy = community_policy.current()
    return community.append_chat(
        user_key=key, session_id=uuid.uuid4().hex, world_seed=382,
        node_name="fixture place", text="private chat evidence", display_name="Local traveler",
        retention_days=policy.chat_days, retention_mode=policy.chat_retention_mode,
        policy_snapshot=policy.snapshot_json)


@pytest.fixture
def anonymous_evidence():
    return evidence()


def test_report_receipt_is_private_and_exact_retry_ignores_obsolete_handles(http, accounts, monkeypatch):
    a, b = (participants.identify(key) for key in accounts)
    body = report(participant=block_targets.handle(a["id"], b["id"]))
    status, receipt, headers = http("/reports", body=body)
    assert status == 200 and set(receipt) == {"report_id", "status"}
    assert receipt["status"] == "received" and "no-store" in headers["Cache-Control"]

    def stale(*_args):
        raise AssertionError("an accepted retry resolved an obsolete handle")

    monkeypatch.setattr(block_targets, "resolve", stale)
    assert http("/reports", body=body)[1] == receipt
    assert http("/reports", body={**body, "detail": "changed private detail"})[0] == 422


@pytest.mark.parametrize("request_id", [
    "abcdef1234564789abcd0123456789ab", "abcdef12-3456-4789-abcd-0123456789ab",
])
def test_canonical_uuid_forms_keep_one_receipt_and_exact_payload_fingerprints(http, accounts, request_id):
    a, b = (participants.identify(key) for key in accounts)
    body = report(request_id=request_id, participant=block_targets.handle(a["id"], b["id"]))
    status, receipt, _ = http("/reports", body=body)
    assert status == 200 and receipt["status"] == "received"
    assert http("/reports", body=body)[1] == receipt
    stored = community.show_report(receipt["report_id"])
    parsed = uuid.UUID(request_id)
    assert stored["request_id"] == parsed.hex
    encoded = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    assert stored["fingerprint"] == hashlib.sha256(encoded.encode()).hexdigest()

    # The aliases share one identifier; a changed public payload is still a
    # conflict, rather than a second report or an implicit payload rewrite.
    alternate = str(parsed) if request_id == parsed.hex else parsed.hex
    assert http("/reports", body={**body, "request_id": alternate})[0] == 422
    assert http("/reports", body={**body, "detail": "changed"})[0] == 422
    assert len(community.list_reports()) == 1


@pytest.mark.parametrize("request_id", [
    "a" * 16, "g" * 32, "z" * 64, "abcdef12_3456_4789_abcd_0123456789ab",
    "ABCDEF12-3456-4789-ABCD-0123456789AB", " abcdef1234564789abcd0123456789ab",
    "{abcdef12-3456-4789-abcd-0123456789ab}", None, 7, [],
])
def test_invalid_request_uuid_refuses_before_retry_lookup_or_report_storage(http, monkeypatch, request_id):
    def forbidden(*_args, **_kwargs):
        pytest.fail("an invalid report UUID reached receipt lookup or storage")

    monkeypatch.setattr(community, "lookup_report_retry", forbidden)
    monkeypatch.setattr(community, "submit_report", forbidden)
    monkeypatch.setattr(community, "evidence_author", forbidden)
    monkeypatch.setattr(block_targets, "resolve", forbidden)
    status, error, _ = http("/reports", body=report(request_id=request_id))
    assert status == 400 and set(error) == {"error"}
    assert community.list_reports() == []


def test_receipt_follows_reporter_rotation_and_remains_available_when_collection_is_disabled(
        http, accounts, monkeypatch):
    a, b = (participants.identify(key) for key in accounts)
    body = report(participant=block_targets.handle(a["id"], b["id"]))
    receipt = http("/reports", body=body)[1]
    rotated = "nw_" + "c" * 32
    participants.rotate(accounts[0], rotated)
    monkeypatch.setenv(community_policy.DISABLE_REPORTS_ENV, "1")
    monkeypatch.setattr(block_targets, "resolve",
                        lambda *_args: pytest.fail("a receipt retry consulted a roster handle"))
    assert http("/reports", key=rotated, body=body)[1] == receipt


def test_agent_and_human_roster_targets_share_the_same_private_report_path(http, accounts):
    viewer = participants.identify(accounts[0])
    handle = block_targets.handle(viewer["id"], blocks.agent_target("Tessera"))
    status, receipt, _ = http("/reports", body=report(participant=handle))
    assert status == 200 and receipt["status"] == "received"


def test_valid_evidence_derives_target_even_with_a_stale_runtime_handle(http, accounts, monkeypatch):
    stored = evidence(accounts[1])
    monkeypatch.setattr(block_targets, "resolve", lambda *_args: (_ for _ in ()).throw(ValueError()))
    status, receipt, _ = http("/reports", body=report(
        participant="f" * 32, evidence_ref=stored["evidence_ref"]))
    assert status == 200 and receipt["status"] == "received"


def test_resolvable_handle_cannot_override_evidence_author(http, accounts):
    a = participants.identify(accounts[0])
    stored = evidence(accounts[1])
    body = report(participant=block_targets.handle(a["id"], a["id"]),
                  evidence_ref=stored["evidence_ref"])
    status, error, _ = http("/reports", body=body)
    assert status == 422 and set(error) == {"error"}
    assert "private" not in error["error"]


@pytest.mark.parametrize("with_evidence", [False, True])
def test_self_reports_are_refused_for_roster_and_authoritative_evidence(http, accounts, with_evidence):
    own = participants.identify(accounts[0])
    body = report(evidence_ref=evidence(accounts[0])["evidence_ref"]) if with_evidence else report(
        participant=block_targets.handle(own["id"], own["id"]))
    status, error, _ = http("/reports", body=body)
    assert status == 400 and set(error) == {"error"}
    assert community.list_reports() == []


def test_anonymous_local_sender_can_be_reported_through_retained_evidence(anonymous_evidence, http):
    status, receipt, _ = http("/reports", body=report(evidence_ref=anonymous_evidence["evidence_ref"]))
    assert status == 200 and receipt["status"] == "received"


def test_unknown_evidence_is_a_fixed_refusal_and_retained_retry_keeps_receipt(http, accounts, monkeypatch):
    stored = evidence(accounts[1])
    body = report(evidence_ref=stored["evidence_ref"])
    receipt = http("/reports", body=body)[1]

    def expired(**_kwargs):
        raise community.EvidenceUnavailable()

    monkeypatch.setattr(community, "evidence_author", expired)
    assert http("/reports", body=body)[1] == receipt
    status, error, _ = http("/reports", body=report(evidence_ref=stored["evidence_ref"]))
    assert status == 422 and set(error) == {"error"}


def test_until_deleted_evidence_remains_reportable_after_a_long_interval(http, accounts, monkeypatch):
    now = community.utc_now()
    stored = evidence(accounts[1])
    monkeypatch.setattr(community, "utc_now", lambda: now + timedelta(days=365))
    status, receipt, _ = http("/reports", body=report(evidence_ref=stored["evidence_ref"]))
    assert status == 200 and receipt["status"] == "received"


def test_reporter_revoked_during_target_resolution_cannot_collect_a_report(http, accounts, monkeypatch):
    a, b = (participants.identify(key) for key in accounts)
    handle = block_targets.handle(a["id"], b["id"])
    resolve = block_targets.resolve

    def revoked(viewer, token):
        target = resolve(viewer, token)
        import persistence
        persistence.revoke_invite_key(accounts[0])
        return target

    monkeypatch.setattr(block_targets, "resolve", revoked)
    assert http("/reports", body=report(participant=handle))[0] == 403


@pytest.mark.parametrize("changes", [{"reason": []}, {"detail": "x" * 2001},
                                      {"participant": "durable-player-id"}, {"extra": "field"}])
def test_malformed_reports_have_fixed_errors(http, changes):
    status, error, _ = http("/reports", body=report(**changes))
    assert status == 400 and set(error) == {"error"}


def test_maximum_detail_accepts_supplementary_unicode_with_escaped_json(http, accounts):
    a, b = (participants.identify(key) for key in accounts)
    status, receipt, _ = http("/reports", body=report(
        participant=block_targets.handle(a["id"], b["id"]), detail="🧭" * 2000))
    assert status == 200 and receipt["status"] == "received"


def test_reports_require_a_live_personal_key(http):
    assert http("/reports", key="", body=report())[0] == 403


def test_reports_keep_the_current_participation_gate_before_collection(http, accounts, monkeypatch):
    monkeypatch.setenv("NESTED_WORLDS_TEST_WORLD", "1")
    for name, value in {
        "TEST_CONTACT": "Fixture facilitator", "TEST_RETENTION": "Delete fixture data after this test.",
        "TEST_MIN_AGE": "18", "TEST_DATA_USE": "No remote model receives fixture data.",
    }.items():
        monkeypatch.setenv("NESTED_WORLDS_" + name, value)
    a, b = (participants.identify(key) for key in accounts)
    body = report(participant=block_targets.handle(a["id"], b["id"]))
    assert http("/community", key="")[0] == 200
    assert http("/reports", body=body)[0] == 428
    notice = participation.notice()
    consents.accept(accounts[0], notice["revision"], participation.snapshot(notice))
    assert http("/reports", body=body)[0] == 200


def test_public_capability_metadata_contains_no_reports_or_private_evidence(http, accounts):
    evidence(accounts[1])
    status, data, _ = http("/community", key="")
    assert status == 200 and data["reports"]["enabled"] is True
    assert data["reports"]["max_detail_length"] == 2000
    assert "private chat evidence" not in str(data)
    assert http("/reports", body=None)[0] == 400


def test_reporting_never_screens_or_calls_a_model(http, accounts, monkeypatch):
    a, b = (participants.identify(key) for key in accounts)

    def forbidden(*_args, **_kwargs):
        pytest.fail("a private report entered a model or moderation path")

    monkeypatch.setattr(moderation, "screen", forbidden)
    monkeypatch.setattr(runtime, "generate", forbidden)
    assert http("/reports", body=report(participant=block_targets.handle(a["id"], b["id"])))[0] == 200


def test_unavailable_storage_returns_no_private_exception_payload(http, accounts, monkeypatch, caplog):
    a, b = (participants.identify(key) for key in accounts)

    def unavailable(**_kwargs):
        error = community.CommunityUnavailable()
        error.args = ("private report detail and provider key",)
        raise error

    monkeypatch.setattr(community, "submit_report", unavailable)
    status, error, _ = http("/reports", body=report(participant=block_targets.handle(a["id"], b["id"])))
    assert status == 503 and set(error) == {"error"}
    assert "private report detail" not in str(error) + caplog.text
