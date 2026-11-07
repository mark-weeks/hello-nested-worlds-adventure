"""The beta checklist header must match the rows it summarizes.

The at-a-glance counts are hand-maintained. A status edit that forgets to
recount them would ship a false go/no-go picture. This test parses only the
item tables (header ``| ID | Item |``) so prose pipes and the summary tables
are not rows.
"""
from __future__ import annotations

import re
from pathlib import Path

_CHECKLIST = (
    Path(__file__).resolve().parents[1] / "docs" / "roadmap" / "beta-launch-checklist.md"
)
_STATUSES = ("Done", "Partial", "Not started", "Unknown")
_ID = re.compile(r"^[A-Z]+\d+[a-z]?$")


def _cells(line: str) -> list[str]:
    parts = [part.strip() for part in line.strip().strip("|").split("|")]
    return parts


def _item_rows(text: str) -> list[tuple[str, str, str, str]]:
    rows: list[tuple[str, str, str, str]] = []
    section = ""
    in_items = False
    for line in text.splitlines():
        if line.startswith("## "):
            section = line[3:].strip()
            in_items = False
            continue
        if line.startswith("| ID | Item |"):
            in_items = True
            continue
        if in_items and line.startswith("|---"):
            continue
        if in_items and not line.startswith("|"):
            in_items = False
            continue
        if not in_items or not line.startswith("|"):
            continue
        cells = _cells(line)
        if not cells or not _ID.match(cells[0]):
            continue
        statuses = [cell for cell in cells if cell in _STATUSES]
        assert len(statuses) == 1, f"{cells[0]} has statuses {statuses}"
        gate = cells[-1]
        rows.append((cells[0], statuses[0], gate, section))
    return rows


def _status_header(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for status in _STATUSES:
        match = re.search(rf"^\| {re.escape(status)} \| (\d+) \|$", text, re.M)
        assert match, f"missing at-a-glance count for {status}"
        counts[status] = int(match.group(1))
    return counts


def test_checklist_counts_match_the_rows():
    text = _CHECKLIST.read_text()
    rows = _item_rows(text)
    assert len(rows) == 95
    assert len({row[0] for row in rows}) == 95

    counted = {status: 0 for status in _STATUSES}
    by_section: dict[str, dict[str, int]] = {}
    for _item_id, status, _gate, section in rows:
        counted[status] += 1
        bucket = by_section.setdefault(section, {name: 0 for name in _STATUSES})
        bucket[status] += 1
    assert _status_header(text) == counted

    category_rows = []
    in_categories = False
    for line in text.splitlines():
        if line.startswith("| Category |"):
            in_categories = True
            continue
        if in_categories and line.startswith("|---"):
            continue
        if in_categories and not line.startswith("|"):
            break
        if not in_categories:
            continue
        cells = _cells(line)
        assert len(cells) == 6, cells
        name, items, done, partial, not_started, unknown = cells
        category_rows.append(name)
        bucket = by_section[name]
        assert int(items) == sum(bucket.values()), name
        assert [int(done), int(partial), int(not_started), int(unknown)] == [
            bucket["Done"],
            bucket["Partial"],
            bucket["Not started"],
            bucket["Unknown"],
        ], name
    assert category_rows == list(by_section)
    assert len(category_rows) == 16

    blocks = [row for row in rows if "Blocks beta" in row[2]]
    open_blocks = [row for row in blocks if row[1] != "Done"]
    glance = re.search(
        r"^(\d+) items in (\d+) categories\. (\d+) block beta, and (\d+) of them are still open\.$",
        text,
        re.M,
    )
    assert glance, "at-a-glance sentence missing"
    assert int(glance.group(1)) == 95
    assert int(glance.group(2)) == 16
    assert int(glance.group(3)) == len(blocks)
    assert int(glance.group(4)) == len(open_blocks)

    # Same-schema rollback is written; the live staging drill is not.
    f4 = next(row for row in rows if row[0] == "F4")
    assert f4[1] == "Partial"
    assert f4[2] == "**Blocks beta**"
    f5 = next(row for row in rows if row[0] == "F5")
    assert f5[1] == "Done"
    p6 = next(row for row in rows if row[0] == "P6")
    assert p6[1] == "Done"
    assert p6[2] == "**Blocks beta**"
