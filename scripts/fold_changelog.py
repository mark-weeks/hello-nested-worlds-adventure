#!/usr/bin/env python3
"""Fold changelog fragments into docs/CHANGELOG.md.

A change batch records itself as one fragment file in docs/changelog.d/ instead
of editing docs/CHANGELOG.md, so pull requests that are open at the same time do
not collide on the changelog (AGENTS.md, "Working in parallel"). The status pull
request runs this script to move the fragments in.

    python scripts/fold_changelog.py --check   # validate, change nothing
    python scripts/fold_changelog.py           # fold, delete fragments, print status lines

The fold orders entries by where each fragment entered the history of the main
branch, read from git, so it needs a checkout with full history
(git fetch --unshallow origin main).

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
SECTIONS = ("Added", "Changed", "Fixed")
UNRELEASED = "## [Unreleased]"
REQUIRED_MARKERS = ("**Verified:**", "**Irreversibility check:**")
NAME = re.compile(r"[a-z0-9][a-z0-9._-]*\.md")
NAME_RULE = ("name the fragment after the branch, lowercased, in letters, digits, dots, "
             "hyphens and underscores, ending in .md, directly in the fragment directory")
DEFAULT_BASE = "origin/main"


class FragmentError(ValueError):
    """A fragment, the changelog or the checkout is not in the shape the fold needs."""


@dataclass(frozen=True)
class Fragment:
    name: str
    section: str
    status: tuple[str, ...]
    body: str


def parse_fragment(name: str, text: str) -> Fragment:
    """Parse one fragment file, refusing anything the fold could misplace."""
    if not NAME.fullmatch(name):
        raise FragmentError(f"{name}: {NAME_RULE}")
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
    heading in the first ``## [Unreleased]``, so the newest ends on top. Nothing
    past the next ``## `` heading is searched, so a released section never
    receives an entry. A section heading that the first ``## [Unreleased]`` lacks,
    as after a release is cut, is created directly under it.
    """
    lines = changelog.split("\n")
    stripped = [line.rstrip() for line in lines]
    if UNRELEASED not in stripped:
        raise FragmentError(f"the changelog has no {UNRELEASED!r} heading")
    start = stripped.index(UNRELEASED)
    for fragment in fragments:
        if fragment.body in "\n".join(lines):
            raise FragmentError(f"{fragment.name}: this entry is already in the changelog")
        heading = f"### {fragment.section}"
        at = None
        for index in range(start + 1, len(lines)):
            if lines[index].startswith("## "):
                break
            if lines[index].rstrip() == heading:
                at = index
                break
        new_heading = at is None
        if new_heading:
            at = start
        first_entry = at + 1
        while first_entry < len(lines) and not lines[first_entry].strip():
            first_entry += 1
        block = ["", *fragment.body.split("\n"), ""]
        lines[at + 1:first_entry] = ["", heading, *block] if new_heading else block
    return "\n".join(lines)


def load(directory: Path) -> list[tuple[Path, Fragment]]:
    """Read and validate every fragment in ``directory``.

    README.md is the only other file allowed there: anything else, a subdirectory
    included, is refused, so a misnamed fragment fails instead of being skipped.
    """
    if not directory.is_dir():
        raise FragmentError(f"{directory}: no such fragment directory")
    loaded = []
    for path in sorted(directory.iterdir()):
        if path.name == "README.md":
            continue
        if not path.is_file():
            raise FragmentError(f"{path.name}: {NAME_RULE}")
        loaded.append((path, parse_fragment(path.name, path.read_text(encoding="utf-8"))))
    return loaded


def _git(directory: Path, *args: str) -> str | None:
    """Output of a git command run in ``directory``; None when it cannot run or fails.

    The two log settings are fixed so the order does not depend on the caller's
    git configuration.
    """
    try:
        done = subprocess.run(
            ["git", "-c", "log.follow=false", "-c", "log.showRoot=true", *args],
            cwd=directory, capture_output=True, text=True, check=False)
    except OSError:
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def merge_order(paths: list[Path], base: str | None = None) -> dict[Path, float]:
    """Where each fragment entered ``base``: the rank, counted from the root, of the
    first-parent commit on ``base`` that added it.

    ``base`` defaults to origin/main, or to the checked-out branch where there is
    no origin/main. Ranking on the main branch keeps its merge order even when the
    status branch has taken main in by a merge of its own. A fragment merged by a
    true merge commit takes the merge's place, not that of the commit that wrote
    it; one deleted and added again takes its latest add. The rank is a position
    in history, so commits made in the same second still order correctly.
    Fragments added by the same commit, and fragments not on ``base`` at all, tie
    and are ordered by file name; the latter sort last. History that cannot be
    read is an error: ordering by file name alone would silently misplace entries.
    """
    directory = paths[0].parent
    if _git(directory, "rev-parse", "--is-inside-work-tree") != "true":
        raise FragmentError("run the fold inside the repository checkout; "
                            "the order of entries comes from git history")
    if _git(directory, "rev-parse", "--is-shallow-repository") != "false":
        raise FragmentError("this checkout has shallow history, so the order of entries "
                            "cannot be read; run 'git fetch --unshallow origin main' first")
    if base is None:
        found = _git(directory, "rev-parse", "--verify", "--quiet", f"{DEFAULT_BASE}^{{commit}}")
        base = DEFAULT_BASE if found else "HEAD"
    elif _git(directory, "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}") is None:
        raise FragmentError(f"--base {base}: no such branch or commit")
    order = {}
    for path in paths:
        # -m is implied by --first-parent since git 2.31; it stays for older git.
        commit = _git(directory, "log", "-1", "--first-parent", "-m", "--diff-filter=A",
                      "--format=%H", base, "--", path.name)
        if commit is None:
            raise FragmentError(f"{path.name}: could not read its git history")
        if not commit:
            order[path] = float("inf")
            continue
        rank = _git(directory, "rev-list", "--first-parent", "--count", commit)
        if rank is None or not rank.isdigit():
            raise FragmentError(f"{path.name}: could not place {commit[:12]} in history")
        order[path] = float(rank)
    return order


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fold changelog fragments into the changelog.")
    parser.add_argument("--check", action="store_true",
                        help="validate the fragments against the changelog and change nothing")
    parser.add_argument("--dir", type=Path, default=ROOT / "docs/changelog.d",
                        help="fragment directory")
    parser.add_argument("--changelog", type=Path, default=ROOT / "docs/CHANGELOG.md",
                        help="changelog to fold into")
    parser.add_argument("--base", default=None,
                        help="branch whose history orders the entries "
                             f"(default: {DEFAULT_BASE}, else the checked-out branch)")
    args = parser.parse_args(argv)
    try:
        loaded = load(args.dir)
        raw = args.changelog.read_bytes()
        if b"\r\n" in raw:
            raise FragmentError(f"{args.changelog.name} has CRLF line endings; convert it to LF")
        changelog = raw.decode("utf-8")
        if args.check:
            fold(changelog, [fragment for _, fragment in loaded])
            print(f"{len(loaded)} changelog fragment(s) valid")
            return 0
        if not loaded:
            print("No changelog fragments to fold.")
            return 0
        order = merge_order([path for path, _ in loaded], args.base)
        loaded.sort(key=lambda item: (order[item[0]], item[0].name))
        text = fold(changelog, [fragment for _, fragment in loaded])
        args.changelog.write_bytes(text.encode("utf-8"))
    except (FragmentError, OSError, UnicodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    result = 0
    for path, fragment in loaded:
        print(f"folded {path.name} under ### {fragment.section}")
        for line in fragment.status:
            print(f"  status: {line}")
        try:
            path.unlink()
        except OSError as error:
            print(f"error: {path.name} is folded but could not be deleted ({error}); "
                  "delete it by hand", file=sys.stderr)
            result = 1
    return result


if __name__ == "__main__":
    sys.exit(main())
