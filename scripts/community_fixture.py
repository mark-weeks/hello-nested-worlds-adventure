"""Explicit synthetic community settings for disposable test servers only.

These values are test data, never deployment defaults or owner decisions.
"""
from __future__ import annotations

import json
import os
from pathlib import Path


def configure(directory: str | Path, *, chat: bool = True, reports: bool = True) -> Path:
    from server import community_policy
    path = Path(directory) / "community-policy.fixture.json"
    data = {"schema_version": 1, "policy_id": "browser-fixture-only",
            "chat": {"enabled": chat}, "reports": {"enabled": reports}}
    if chat:
        data["chat"]["retention_mode"] = "until_deleted"
    if reports:
        data["reports"]["retention_days"] = 1
    if chat or reports:
        data.update(contact="Test facilitator",
                    backup_notice="Synthetic test backup handling; not deployment policy.")
    path.write_text(json.dumps(data))
    os.environ[community_policy.POLICY_ENV] = str(path)
    # A synthetic invited study still exercises the real notice and age gate.
    # Respect explicit per-suite settings, including deliberately empty values.
    for name, value in {
        "TEST_CONTACT": "Test facilitator",
        "TEST_RETENTION": "Synthetic study records are deleted after this disposable test.",
        "TEST_DATA_USE": "No remote model receives synthetic fixture data.",
    }.items():
        os.environ.setdefault("NESTED_WORLDS_" + name, value)
    community_policy.reset_for_tests()
    return path
