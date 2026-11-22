"""The watch community-policy template, read from the guide that documents it.

The guide carries the template and O6's backup wording as fenced blocks under
"Watch policy template". Tests fill the template the way an operator would and
load the result, so a guide edit that breaks the policy fails a test instead of
reaching the twin.
"""
from __future__ import annotations

import json
from pathlib import Path
import re

GUIDE = Path(__file__).resolve().parents[1] / "docs" / "development" / "community-reporting.md"
CONTACT_PLACEHOLDER = "<OWNER: contact>"
BACKUP_PLACEHOLDER = "<OWNER: backup_notice>"
TEST_CONTACT = "watch-test-contact@example.invalid (synthetic; not the owner's address)"


def _section() -> str:
    text = GUIDE.read_text(encoding="utf-8")
    start = text.index("\n## Watch policy template\n")
    end = text.index("\n## ", start + 1)
    return text[start:end]


def _fenced(language: str) -> list[str]:
    return re.findall(rf"^```{language}\n(.*?)^```$", _section(), flags=re.M | re.S)


def template_text() -> str:
    """The JSON template exactly as the guide prints it, placeholders included."""
    blocks = _fenced("json")
    assert len(blocks) == 1, "the guide must print exactly one watch policy template"
    return blocks[0]


def backup_wording() -> str:
    """O6's adopted backup_notice wording, as the guide gives it to paste."""
    blocks = _fenced("text")
    assert len(blocks) == 1, "the guide must print O6's backup wording exactly once"
    return blocks[0].strip("\n")


def filled_template(contact: str = TEST_CONTACT, backup_notice: str | None = None) -> str:
    """Replace each placeholder as an operator would, by text substitution."""
    raw = template_text()
    assert raw.count(CONTACT_PLACEHOLDER) == 1 and raw.count(BACKUP_PLACEHOLDER) == 1
    notice = backup_wording() if backup_notice is None else backup_notice
    filled = (raw.replace(CONTACT_PLACEHOLDER, json.dumps(contact)[1:-1])
                 .replace(BACKUP_PLACEHOLDER, json.dumps(notice)[1:-1]))
    assert "<OWNER" not in filled
    return filled


def write_filled(directory: Path, **kwargs) -> Path:
    path = directory / "watch-community-policy.json"
    path.write_text(filled_template(**kwargs), encoding="utf-8")
    return path
