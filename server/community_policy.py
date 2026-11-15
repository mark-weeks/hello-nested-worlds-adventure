"""Immutable operator declarations for private chat/report collection.

No retention duration, contact or backup promise is selected by this module.
Missing configuration disables collection, with no permanent-history fallback.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import threading

POLICY_ENV = "NESTED_WORLDS_COMMUNITY_POLICY"
DISABLE_CHAT_ENV = "NESTED_WORLDS_DISABLE_CHAT"
DISABLE_REPORTS_ENV = "NESTED_WORLDS_DISABLE_REPORTS"
MAX_DETAIL_LENGTH = 2000
REPORT_REASONS = (
    ("harassment", "Harassment or bullying"),
    ("harmful_content", "Hateful or threatening content"),
    ("spam", "Spam or disruption"),
    ("other", "Something else"),
)
_MAX_FILE_BYTES = 16_384
_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,159}")
_OFF_DOCUMENT = {"schema_version": 1, "policy_id": "community-collection-disabled",
                 "chat": {"enabled": False}, "reports": {"enabled": False}}


class CommunityPolicyError(ValueError):
    def __init__(self):
        super().__init__("Community collection policy is invalid.")


@dataclass(frozen=True)
class CommunityPolicy:
    policy_id: str
    chat_days: int | None
    chat_retention_mode: str | None
    report_days: int | None
    contact: str
    backup_notice: str
    snapshot_json: str

    @property
    def revision(self) -> str:
        return hashlib.sha256(self.snapshot_json.encode("utf-8")).hexdigest()


_snapshot: CommunityPolicy | None = None
_lock = threading.RLock()


def reset_for_tests() -> None:
    global _snapshot
    with _lock:
        _snapshot = None


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CommunityPolicyError()
        result[key] = value
    return result


def _text(value: object) -> str:
    if (not isinstance(value, str) or not 1 <= len(value) <= 1000
            or value != value.strip() or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise CommunityPolicyError()
    try:
        value.encode("utf-8")
    except UnicodeError:
        raise CommunityPolicyError() from None
    return value


def _retention(route: object, *, until_deleted: bool = False) -> int | str | None:
    if not isinstance(route, dict):
        raise CommunityPolicyError()
    if set(route) == {"enabled"} and route["enabled"] is False:
        return None
    if (until_deleted and set(route) == {"enabled", "retention_mode"}
            and route["enabled"] is True and route["retention_mode"] == "until_deleted"):
        return "until_deleted"
    if set(route) != {"enabled", "retention_days"} or route["enabled"] is not True:
        raise CommunityPolicyError()
    days = route["retention_days"]
    if type(days) is not int or not 1 <= days <= 36500:
        raise CommunityPolicyError()
    return days


def _parse(data: object) -> CommunityPolicy:
    basic = {"schema_version", "policy_id", "chat", "reports"}
    if not isinstance(data, dict) or set(data) not in (basic, basic | {"contact", "backup_notice"}):
        raise CommunityPolicyError()
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise CommunityPolicyError()
    if not isinstance(data["policy_id"], str) or not _SAFE_ID.fullmatch(data["policy_id"]):
        raise CommunityPolicyError()
    chat, reports = _retention(data["chat"], until_deleted=True), _retention(data["reports"])
    chat_mode = None if chat is None else "until_deleted" if chat == "until_deleted" else "days"
    chat_days = chat if type(chat) is int else None
    contact = backup = ""
    if chat is not None or reports is not None or "contact" in data:
        contact = _text(data.get("contact"))
        backup = _text(data.get("backup_notice"))
    encoded = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    encoded.encode("utf-8")
    return CommunityPolicy(data["policy_id"], chat_days, chat_mode, reports, contact, backup, encoded)


def check_file(path: str | Path) -> CommunityPolicy:
    """Offline parse only: no database, network, global activation or defaults."""
    try:
        with Path(path).open("rb") as stream:
            raw = stream.read(_MAX_FILE_BYTES + 1)
        if len(raw) > _MAX_FILE_BYTES:
            raise CommunityPolicyError()
        data = json.loads(raw, object_pairs_hook=_unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(CommunityPolicyError()))
        return _parse(data)
    except CommunityPolicyError:
        raise
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError):
        raise CommunityPolicyError() from None


def initialize() -> CommunityPolicy:
    global _snapshot
    with _lock:
        if _snapshot is None:
            path = os.getenv(POLICY_ENV)
            if path is not None:
                if not path.strip():
                    raise CommunityPolicyError()
                _snapshot = check_file(path.strip())
            else:
                _snapshot = _parse(_OFF_DOCUMENT)
        return _snapshot


def current() -> CommunityPolicy:
    return initialize()


def chat_enabled() -> bool:
    return current().chat_retention_mode is not None and os.getenv(DISABLE_CHAT_ENV, "").strip() != "1"


def reports_enabled() -> bool:
    return current().report_days is not None and os.getenv(DISABLE_REPORTS_ENV, "").strip() != "1"


def disclosure(policy: CommunityPolicy | None = None) -> list[str]:
    """Stable collection wording; temporary kill switches do not grant consent."""
    policy = policy or current()
    chat_period = f"{policy.chat_days} day" + ("" if policy.chat_days == 1 else "s")
    report_period = f"{policy.report_days} day" + ("" if policy.report_days == 1 else "s")
    chat = ("Live traveler messages are delivered to everyone connected to this world. "
            "They are kept in a private log that only operators can read, to look into complaints "
            "and understand how testers played together. They are not added to permanent world "
            "history or model memory. "
            + ("They are kept until you ask for deletion or leave the study; a message needed "
               "for an open report is held until that report closes."
               if policy.chat_retention_mode == "until_deleted" else f"They are kept for {chat_period}.")
            if policy.chat_retention_mode is not None else "Live traveler chat collection is unavailable in this world.")
    reports = (f"Reports and your optional explanation are private to the operator and kept for {report_period}. A cited message is held until its report closes."
               if policy.report_days is not None else "Private reporting is unavailable. Please contact the facilitator if you need help.")
    result = [chat, reports,
              "Place and inhabitant exchanges, and authored ambient traveler conversations, remain recorded in shared world history. Older chat already in the chronicle is not erased by this change; normal history and model views leave it out."]
    if policy.contact:
        result.append(f"Community questions and reports: {policy.contact}")
    if policy.backup_notice:
        result.append("Copies in backups are removed when those backups are deleted. "
                      f"Backup copies and deletion: {policy.backup_notice}")
    return result


def metadata() -> dict:
    policy = current()
    notices = disclosure(policy)
    return {"revision": policy.revision,
            "chat": {"enabled": chat_enabled(), "retention_days": policy.chat_days,
                     "retention_mode": policy.chat_retention_mode,
                     "notice": notices[0]},
            "reports": {"enabled": reports_enabled(), "retention_days": policy.report_days,
                        "notice": notices[1], "max_detail_length": MAX_DETAIL_LENGTH,
                        "reasons": [{"value": code, "label": label} for code, label in REPORT_REASONS]},
            "contact": policy.contact, "backup_notice": policy.backup_notice}


def summary(policy: CommunityPolicy) -> dict:
    return {"policy_id": policy.policy_id, "revision": policy.revision,
            "chat_retention_days": policy.chat_days,
            "chat_retention_mode": policy.chat_retention_mode,
            "report_retention_days": policy.report_days,
            "collection_configured": policy.chat_retention_mode is not None or policy.report_days is not None,
            "backup_treatment_verified": False}
