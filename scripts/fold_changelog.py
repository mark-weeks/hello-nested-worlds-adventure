#!/usr/bin/env python3
"""Fold changelog fragments into docs/CHANGELOG.md.

A change batch records itself as one fragment file in docs/changelog.d/ instead
of editing docs/CHANGELOG.md, so pull requests that are open at the same time do
not collide on the changelog (AGENTS.md, "Working in parallel"). The status pull
request runs this script to move the fragments in.

    python scripts/fold_changelog.py --check   # validate fragments, change nothing
    python scripts/fold_changelog.py           # fold, delete fragments, print status lines

Fragment format (docs/changelog.d/README.md):

    Section: Added
    Status: checklist S3: Not started to Partial
    <blank line>
    - **Headline** ... **Verified:** ... **Irreversibility check:** ...
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECTIONS = ("Added", "Fixed")
UNRELEASED = "## [Unreleased]"
REQUIRED_MARKERS = ("**Verified:**", "**Irreversibility check:**")
NAME = re.compile(r"[a-z0-9][a-z0-9._-]*\.md")


class FragmentError(ValueError):
    """A fragment or the changelog does not have the shape the fold needs."""


@dataclass(frozen=True)
class Fragment:
    name: str
    section: str
    status: tuple[str, ...]
    body: str


def parse_fragment(name: str, text: str) -> Fragment:
    """Parse one fragment file, refusing anything the fold could misplace."""
    if not NAME.fullmatch(name):
        raise FragmentError(
            f"{name}: name the fragment after the branch, in lowercase letters, "
            "digits, dots and hyphens, ending in .md"
        )
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not line.strip():
            header, entry = lines[:index], lines[index + 1:]
            break
    else:
        raise FragmentError(f"{name}: leave a blank line between the header and the entry")

    section = None
    status: list[str] = []
    for line in header:
        key, separator, value = line.partition(":")
        value = value.strip()
        if not separator or key not in ("Section", "Status"):
            raise FragmentError(f"{name}: unknown header line {line!r}")
        if not value:
            raise FragmentError(f"{name}: empty {key}: line")
        if key == "Status":
            status.append(value)
        elif section is not None:
            raise FragmentError(f"{name}: more than one Section: line")
        else:
            section = value
    if section not in SECTIONS:
        raise FragmentError(f"{name}: Section must be one of {', '.join(SECTIONS)}")

    while entry and not entry[0].strip():
        entry.pop(0)
    while entry and not entry[-1].strip():
        entry.pop()
    if not entry or not entry[0].startswith("- **"):
        raise FragmentError(f"{name}: the entry must be one bullet starting with '- **'")
    for line in entry[1:]:
        if line.strip() and not line.startswith("  "):
            raise FragmentError(
                f"{name}: one bullet per fragment, its continuation lines indented "
                f"two spaces; got {line!r}"
            )
    body = "\n".join(line.rstrip() for line in entry)
    for marker in REQUIRED_MARKERS:
        if marker not in body:
            raise FragmentError(f"{name}: the entry needs a {marker} part")
    return Fragment(name, section, tuple(status), body)


def fold(changelog: str, fragments: list[Fragment]) -> str:
    """Return the changelog with the fragments inserted.

    ``fragments`` are given oldest first. Each goes directly under its section
    heading in the first ``## [Unreleased]``, so the newest ends on top.
    """
    lines = changelog.split("\n")
    stripped = [line.rstrip() for line in lines]
    if UNRELEASED not in stripped:
        raise FragmentError(f"the changelog has no {UNRELEASED!r} heading")
    start = stripped.index(UNRELEASED)
    for fragment in fragments:
        heading = f"### {fragment.section}"
        at = None
        for index in range(start + 1, len(lines)):
            if lines[index].startswith("## "):
                break
            if lines[index].rstrip() == heading:
                at = index
                break
        if at is None:
            raise FragmentError(f"no {heading!r} under the first {UNRELEASED}")
        first_entry = at + 1
        while first_entry < len(lines) and not lines[first_entry].strip():
            first_entry += 1
        lines[at + 1:first_entry] = ["", *fragment.body.split("\n"), ""]
    return "\n".join(lines)


def load(directory: Path) -> list[tuple[Path, Fragment]]:
    """Read and validate every fragment in ``directory`` (README.md is not one)."""
    loaded = []
    for path in sorted(directory.glob("*.md")):
        if path.name == "README.md":
            continue
        loaded.append((path, parse_fragment(path.name, path.read_text(encoding="utf-8"))))
    return loaded


def added_at(path: Path) -> float:
    """Commit time at which the fragment landed; uncommitted fragments sort last."""
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--diff-filter=A", "--format=%ct", "--", path.name],
            cwd=path.parent, capture_output=True, text=True, check=False,
        ).stdout.strip()
    except OSError:
        out = ""
    return float(out) if out.isdigit() else float("inf")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fold changelog fragments into the changelog.")
    parser.add_argument("--check", action="store_true",
                        help="validate the fragments and change nothing")
    parser.add_argument("--dir", type=Path, default=ROOT / "docs/changelog.d",
                        help="fragment directory")
    parser.add_argument("--changelog", type=Path, default=ROOT / "docs/CHANGELOG.md",
                        help="changelog to fold into")
    args = parser.parse_args(argv)
    try:
        loaded = load(args.dir)
        if args.check:
            print(f"{len(loaded)} changelog fragment(s) valid")
            return 0
        if not loaded:
            print("No changelog fragments to fold.")
            return 0
        loaded.sort(key=lambda item: (added_at(item[0]), item[0].name))
        text = fold(args.changelog.read_text(encoding="utf-8"),
                    [fragment for _, fragment in loaded])
    except FragmentError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    args.changelog.write_text(text, encoding="utf-8")
    for path, fragment in loaded:
        path.unlink()
        print(f"folded {path.name} under ### {fragment.section}")
        for line in fragment.status:
            print(f"  status: {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
