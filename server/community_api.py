"""Public collection capabilities and private authenticated report receipts."""
from __future__ import annotations

import hashlib
import json
import logging
import re
import sqlite3

from persistence import community, participants
from server import block_targets, community_policy, guard

_log = logging.getLogger("nested_worlds.community")
_BODY_KEYS = {"request_id", "participant", "evidence_ref", "reason", "detail"}
_HANDLE = re.compile(r"[0-9a-f]{32}")
_INVALID = "The report request is invalid. Please check it and try again."
_EVIDENCE = "That evidence is unavailable. Please refresh and choose a retained message."
_TARGET = "That traveler could not be selected. Please refresh and choose again."
_CONFLICT = "This report request has changed. Please start a new report."
_UNAVAILABLE = "Reporting is unavailable. Please contact the facilitator."


def _receipt(stored: dict) -> dict:
    # Keep persistence metadata, including any later operator-only fields,
    # outside the public acknowledgement contract.
    return {"report_id": stored["report_id"], "status": "received"}


def _text(value: object, maximum: int, *, empty: bool = False) -> bool:
    if not isinstance(value, str) or len(value) > maximum or (not empty and not value):
        return False
    try:
        value.encode("utf-8")
    except UnicodeError:
        return False
    return True


def _validate(body: dict) -> None:
    if set(body) != _BODY_KEYS:
        raise ValueError()
    community.normalize_uuid(body["request_id"])
    target = body["participant"]
    if target is not None and (not isinstance(target, str) or not _HANDLE.fullmatch(target)):
        raise ValueError()
    evidence = body["evidence_ref"]
    if evidence is not None and not _text(evidence, 128):
        raise ValueError()
    if (body["reason"] not in {code for code, _label in community_policy.REPORT_REASONS}
            or not _text(body["detail"], community_policy.MAX_DETAIL_LENGTH, empty=True)):
        raise ValueError()


def handle(handler, path: str, qs: dict, body: dict | None = None) -> bool:
    if path not in {"/community", "/reports"}:
        return False
    handler._private_response = True
    if path == "/community":
        if body is not None:
            handler._send_error(_INVALID, 400)
            return True
        try:
            handler._send_json(community_policy.metadata())
        except community_policy.CommunityPolicyError:
            handler._send_error(_UNAVAILABLE, 503)
        return True
    if body is None:
        handler._send_error(_INVALID, 400)
        return True
    try:
        user_key = guard.supplied_key(handler.headers, qs)
        reporter = participants.identify(user_key)
        _validate(body)
        encoded = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        fingerprint = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        # Runtime roster handles can expire on restart. Exact retries belong
        # to the stable reporter and are resolved before consulting them.
        retried = community.lookup_report_retry(user_key, body["request_id"], fingerprint)
        if retried is not None:
            handler._send_json(_receipt(retried))
            return True
        if not community_policy.reports_enabled():
            handler._send_error(_UNAVAILABLE, 503)
            return True
        declared = community_policy.current()
        world_seed = guard.world_seed(qs.get("seed", [None])[0])
        target = None
        if body["participant"] is not None:
            try:
                target = block_targets.resolve(reporter["id"], body["participant"])
            except ValueError:
                if body["evidence_ref"] is None:
                    handler._send_error(_TARGET, 422)
                    return True
        if body["evidence_ref"] is not None:
            author = community.evidence_author(
                evidence_ref=body["evidence_ref"], world_seed=world_seed)
            if target is not None and target != author["participant_id"]:
                handler._send_error(_TARGET, 422)
                return True
            target = author["participant_id"]
        elif target is None:
            handler._send_error(_TARGET, 422)
            return True
        receipt = community.submit_report(
            user_key=user_key, request_id=body["request_id"], fingerprint=fingerprint,
            world_seed=world_seed, target_id=target, evidence_ref=body["evidence_ref"],
            reason=body["reason"], detail=body["detail"],
            retention_days=declared.report_days, policy_snapshot=declared.snapshot_json,
        )
        handler._send_json(_receipt(receipt))
    except participants.Unauthorized:
        handler._send_error("forbidden", 403)
    except community.EvidenceUnavailable:
        handler._send_error(_EVIDENCE, 422)
    except community.ReportConflict:
        handler._send_error(_CONFLICT, 422)
    except (community.CommunityUnavailable, sqlite3.Error, community_policy.CommunityPolicyError) as exc:
        _log.error("Private reporting unavailable (%s)", type(exc).__name__)
        handler._send_error(_UNAVAILABLE, 503)
    except (ValueError, TypeError):
        handler._send_error(_INVALID, 400)
    except Exception as exc:
        _log.error("Private reporting unavailable (%s)", type(exc).__name__)
        handler._send_error(_UNAVAILABLE, 503)
    return True
