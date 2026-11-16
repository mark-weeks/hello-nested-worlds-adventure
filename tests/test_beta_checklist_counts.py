"""The study inventory is complete and its stage/status summaries are truthful.

Rows retain their historical evidence status. Entry is governed by scoped
admission controls; outcomes requiring participants cannot block the first
study. Parse only item tables so the compact control table is not mistaken
for more inventory items.
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

    stages = ("Admission evidence", "Study measurement", "Later improvement")
    stage_counts = {name: {"items": 0, "done": 0} for name in stages}
    for item_id, status, stage_cell, _section in rows:
        stage = stage_cell.split(" · ", 1)[0]
        assert stage in stages, (item_id, stage_cell)
        stage_counts[stage]["items"] += 1
        stage_counts[stage]["done"] += status == "Done"

    for stage in stages:
        match = re.search(
            rf"^\| {re.escape(stage)} \| (\d+) \| (\d+) \| (\d+) \|$",
            text,
            re.M,
        )
        assert match, f"missing stage summary for {stage}"
        items, done, open_items = map(int, match.groups())
        assert items == stage_counts[stage]["items"]
        assert done == stage_counts[stage]["done"]
        assert open_items == items - done

    # Retain the complete source inventory, not a smaller relabelled checklist.
    expected_ids = {
        *"C1 C2a C2b C2c C3 C4 C5 C6 C7".split(),
        *(f"{prefix}{number}" for prefix, count in {
            "O": 4, "R": 5, "D": 5, "A": 4, "S": 5, "E": 5,
            "P": 7, "B": 5, "M": 6, "Y": 6, "L": 5, "F": 6,
            "K": 4, "G": 12, "U": 7,
        }.items() for number in range(1, count + 1)),
    }
    assert {row[0] for row in rows} == expected_ids


def test_participant_outcomes_do_not_become_admission_requirements():
    stages = {item_id: stage.split(" · ", 1)[0] for item_id, _, stage, _ in
              _item_rows(_CHECKLIST.read_text())}
    participant_outcomes = {
        "C1", "C2a", "C2c", "C4", "C6", "O1", "O2", "O3", "O4",
        "R1", "B2", "K2", "K3", "K4",
    }
    assert {stages[item_id] for item_id in participant_outcomes} == {
        "Study measurement"
    }
    # Actual safety, data and cost controls still need applicable pre-entry proof.
    admission_controls = {
        "C7", "A1", "S1", "S2", "S3", "S4", "S5", "E1", "E2", "E4",
        "R3", "P3", "P4", "P5", "P6", "F3", "F4", "F6", "G5", "G11",
    }
    assert {stages[item_id] for item_id in admission_controls} == {
        "Admission evidence"
    }
    # Neither broad provider abstraction nor future community machinery is needed
    # to admit people to a facilitated study with checked operator controls.
    assert {stages[item_id] for item_id in ("M1", "M2", "M3", "G1", "G2")} == {
        "Later improvement"
    }
