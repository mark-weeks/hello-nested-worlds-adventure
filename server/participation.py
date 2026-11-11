"""Participation notice and consent gate for a disposable staging world.

This is explicitly opt-in operational behavior. It does not choose production
chat retention, a provider, a minimum age, or a deletion promise for the owner.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3

from persistence import participation as consents, participants


_PREFIX = "NESTED_WORLDS_"
_INCOMPLETE = "This test world is not ready for participants. Please contact your facilitator."
_NEEDS_ACCEPTANCE = "Please read and accept the test-world notice before entering."
_UNAVAILABLE = "Participation could not be checked. Please try again."


def required() -> bool:
    """Only an explicit off/absent flag disables the gate; typos fail closed."""
    return os.getenv(_PREFIX + "TEST_WORLD", "").strip() not in ("", "0")


def snapshot(current: dict) -> str:
    """Server-produced text that was displayed, retained with its acknowledgement."""
    document = {name: current[name] for name in
                ("required", "ready", "title", "paragraphs", "minimum_age")}
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
                "revision": "", "title": "Enfolded", "paragraphs": [], "minimum_age": None}
    contact = _text("TEST_CONTACT")
    retention = _text("TEST_RETENTION")
    data_use = _text("TEST_DATA_USE")
    raw_age = os.getenv(_PREFIX + "TEST_MIN_AGE", "").strip()
    try:
        age = int(raw_age) if raw_age.isascii() and raw_age.isdecimal() else None
    except ValueError:
        age = None
    if age is not None and not 1 <= age <= 120:
        age = None
    ready = os.getenv(_PREFIX + "TEST_WORLD", "").strip() == "1" and all((contact, retention, data_use, age))
    paragraphs = [
        "This is a temporary Enfolded test world. It may be reset or removed; your progress is not promised to persist.",
        "Your name, chat, spoken exchanges and gameplay are recorded in this test world. Other invited players can read shared history. Private journal notes do not appear in shared history.",
        "Some travelers you meet are AI. You won't always be able to tell, but if you ask one, it will tell you the truth.",
        "The operator keeps a private copy of this notice and the time you acknowledge it with the test records and their backups, under the retention statement below.",
    ]
    if age is not None:
        paragraphs.append(f"Participation is limited to people aged {age} or older.")
    if contact:
        paragraphs.append(f"Questions or concerns: {contact}")
    if retention:
        paragraphs.append(f"Retention and deletion, including backups: {retention}")
    if data_use:
        paragraphs.append(f"Use of data and model providers: {data_use}")
    result = {"required": True, "ready": bool(ready), "accepted": False,
              "title": "Temporary test world", "paragraphs": paragraphs, "minimum_age": age}
    revision = hashlib.sha256(snapshot(result).encode()).hexdigest() if ready else ""
    return {**result, "revision": revision}


def session_authorized(key: str) -> bool:
    """The existing credential sweep and before-write checks use this fence."""
    if not required():
        return True
    current = notice()
    return current["ready"] and consents.accepted(key, current["revision"])


def authorize(handler, qs) -> bool:
    """Gate a gameplay request before its dispatch can read or change a world."""
    if not required():
        return True
    from server import guard
    handler._private_response = True
    current = notice()
    try:
        accepted = consents.accepted(guard.supplied_key(handler.headers, qs), current["revision"])
    except participants.Unauthorized:
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
                handler._send_error("This world does not require a test-world acknowledgement.", 400)
                return True
            if not current["ready"]:
                handler._send_json({"error": _INCOMPLETE, "participation_required": True}, 503)
                return True
            if set(body) != {"accepted", "revision"} or body.get("accepted") is not True:
                handler._send_error("An affirmative acknowledgement of the current notice is required.", 400)
                return True
            if not isinstance(body.get("revision"), str) or body["revision"] != current["revision"]:
                handler._send_error("The test-world notice changed. Please read it again.", 409)
                return True
            consents.accept(key, current["revision"], snapshot(current))
            current["accepted"] = True
        handler._send_json(current)
    except participants.Unauthorized:
        handler._send_error("forbidden", 403)
    except sqlite3.Error:
        handler._send_error(_UNAVAILABLE, 503)
    return True
