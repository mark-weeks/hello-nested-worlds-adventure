"""One age and participation notice for study registration and personal invites.

The owner-set minimum is 18. Explicit test-world mode or any invited world
requires acknowledgement. Collection settings, revocation and cancellation
cannot remove the permanently latched invitation requirement.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3

from persistence import participation as consents, participants


_PREFIX = "NESTED_WORLDS_"
_INCOMPLETE = "This study is not ready for participants. Please contact your facilitator."
_NEEDS_ACCEPTANCE = "Please read and accept the participation notice before entering."
_UNAVAILABLE = "Participation could not be checked. Please try again."
_OFF = frozenset({"", "0", "false", "off", "no"})
_ON = frozenset({"1", "true", "on", "yes"})
MINIMUM_AGE = 18


def _test_world_flag() -> str:
    return os.getenv(_PREFIX + "TEST_WORLD", "").strip().casefold()


def required() -> bool:
    """Every invited world requires entry consent, independently of collection."""
    if _test_world_flag() not in _OFF:
        return True
    from server import guard
    return guard.invite_gate_active()


def snapshot(current: dict) -> str:
    """Server-produced text that was displayed, retained with its acknowledgement."""
    document = {name: current[name] for name in
                ("required", "ready", "temporary", "title", "paragraphs", "minimum_age",
                 "age_confirmation", "agreement")}
    document["accepted"] = False
    return json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _text(name: str) -> str:
    value = os.getenv(_PREFIX + name, "").strip()
    try:
        value.encode("utf-8")
    except UnicodeError:
        return ""
    return value


def notice() -> dict:
    """Effective plain-text notice, with a revision over everything displayed.

    The revision is empty while incomplete. Configuration is read at use time
    so an already open socket is fenced when its accepted notice changes.
    """
    if not required():
        return {"required": False, "ready": True, "accepted": False,
                "temporary": False, "revision": "", "title": "Enfolded",
                "paragraphs": [], "minimum_age": None, "age_confirmation": "",
                "agreement": ""}
    contact = _text("TEST_CONTACT")
    retention = _text("TEST_RETENTION")
    data_use = _text("TEST_DATA_USE")
    raw_age = os.getenv(_PREFIX + "TEST_MIN_AGE", "").strip()
    # The owner set 18; a stale/conflicting override cannot silently change it.
    age = MINIMUM_AGE if raw_age in ("", str(MINIMUM_AGE)) else None
    temporary = _test_world_flag() in _ON
    valid_mode = _test_world_flag() in _ON | _OFF
    ready = valid_mode and all((contact, retention, data_use, age))
    paragraphs = [
        ("This is a temporary Enfolded test world. It may be reset or removed; your progress is not promised to persist."
         if temporary else "This Enfolded study uses a continuing world. Its records follow the retention statement below."),
        "Your name, exchanges with places and inhabitants, and gameplay are recorded in shared world history. Private journal notes do not appear in shared history. Traveler messages follow the separate private-log notice below.",
        "Some travelers are AI. Enfolded's own AI travelers are instructed not to claim to be human. Ask plainly whether one is AI; a reply may be silent when voices are unavailable.",
        "The operator keeps a private copy of this notice and the time you acknowledge it with the study records and their backups, under the retention statement below.",
    ]
    from server import community_policy
    try:
        paragraphs.extend(community_policy.disclosure())
    except community_policy.CommunityPolicyError:
        ready = False
        paragraphs.append("Community collection is unavailable. Please contact the facilitator.")
    if age is not None:
        paragraphs.append(f"Participation is limited to people aged {age} or older.")
    if contact:
        paragraphs.append(f"Questions or concerns: {contact}")
    if retention:
        paragraphs.append(f"Retention and deletion, including backups: {retention}")
    if data_use:
        paragraphs.append(f"Use of data and model providers: {data_use}")
    result = {"required": True, "ready": bool(ready), "accepted": False,
              "temporary": temporary,
              "title": "Temporary test world" if temporary else "Before you join this study",
              "paragraphs": paragraphs, "minimum_age": age,
              "age_confirmation": "I confirm I am 18 years old or older." if ready else "",
              "agreement": ("I have read this notice and agree to participate in this "
                            + ("temporary test world." if temporary else "Enfolded study.")) if ready else ""}
    revision = hashlib.sha256(snapshot(result).encode()).hexdigest() if ready else ""
    return {**result, "revision": revision}


def session_authorized(key: str) -> bool:
    """Revalidate the live credential and notice for a credentialed socket."""
    current = notice()
    return current["ready"] and consents.accepted(key, current["revision"])


def authorize(handler, qs, *, raise_unauthorized: bool = False) -> bool:
    """Gate a gameplay request before its dispatch can read or change a world."""
    if not required():
        return True
    from server import guard
    handler._private_response = True
    current = notice()
    try:
        accepted = consents.accepted(guard.supplied_key(handler.headers, qs), current["revision"])
    except participants.Unauthorized:
        if raise_unauthorized:
            # An adapter with its own credential-failure limiter owns the
            # refusal. The notice check still precedes identity enrollment.
            raise
        handler._send_error("forbidden", 403)
        return False
    except sqlite3.Error:
        handler._send_error(_UNAVAILABLE, 503)
        return False
    if not current["ready"]:
        handler._send_json({"error": _INCOMPLETE, "participation_required": True}, 503)
        return False
    if not accepted:
        handler._send_json({"error": _NEEDS_ACCEPTANCE, "participation_required": True}, 428)
        return False
    # Preserve the usual throttled last-used accounting and recheck the
    # credential after the acknowledgement read, before dispatch.
    if not guard.check_invite_key(handler.headers, qs):
        handler._send_error("forbidden", 403)
        return False
    return True


def handle(handler, path, qs, body=None) -> bool:
    """Public GET metadata; a live personal credential alone may acknowledge."""
    if path != "/participation":
        return False
    from server import guard
    handler._private_response = True
    current = notice()
    key = guard.supplied_key(handler.headers, qs)
    try:
        if key or body is not None:
            current["accepted"] = consents.accepted(key, current["revision"])
        if body is not None:
            if not current["required"]:
                handler._send_error("This world does not require a participation acknowledgement.", 400)
                return True
            if not current["ready"]:
                handler._send_json({"error": _INCOMPLETE, "participation_required": True}, 503)
                return True
            if (set(body) != {"accepted", "revision", "age_confirmed"}
                    or body.get("accepted") is not True or body.get("age_confirmed") is not True):
                handler._send_error("An affirmative acknowledgement of the current notice is required.", 400)
                return True
            if not isinstance(body.get("revision"), str) or body["revision"] != current["revision"]:
                handler._send_error("The participation notice changed. Please read it again.", 409)
                return True
            consents.accept(key, current["revision"], snapshot(current))
            current["accepted"] = True
        handler._send_json(current)
    except participants.Unauthorized:
        handler._send_error("forbidden", 403)
    except sqlite3.Error:
        handler._send_error(_UNAVAILABLE, 503)
    return True
