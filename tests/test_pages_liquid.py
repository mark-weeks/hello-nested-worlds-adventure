"""GitHub Pages builds ``docs/`` with Jekyll (github-pages 232).

Liquid treats ``{{`` and ``{%`` as syntax. A markdown file that contains
either aborts that build unless ``docs/_config.yml`` excludes it. The
failure on main since #157 is ``docs/CHANGELOG.md`` line 150. The message
tells the author to add the file to ``exclude`` or reword the prose.
"""
from __future__ import annotations

import fnmatch
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
CONFIG = DOCS / "_config.yml"

_LIQUID_OPENERS = ("{{", "{%")


def read_exclude(text: str) -> list[str]:
    """The ``exclude:`` block list from ``docs/_config.yml``.

    The file is comments plus that one key. Another key would change the
    Pages site, and a flow list is rejected so a misread cannot look empty.
    """
    items: list[str] = []
    seen = False
    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line.startswith("exclude:"):
            if seen:
                raise ValueError(f"line {lineno}: duplicate exclude")
            rest = line[len("exclude:"):].strip()
            if rest and not rest.startswith("#"):
                raise ValueError(
                    f"line {lineno}: write exclude as a block list, not {rest!r}"
                )
            seen = True
            continue
        if line.startswith("  - "):
            if not seen:
                raise ValueError(f"line {lineno}: exclude item before exclude:")
            value = line[4:].strip()
            if " #" in value:
                value = value.split(" #", 1)[0].rstrip()
            if not value or value[0] in "\"'[{*&!|>%@`":
                raise ValueError(
                    f"line {lineno}: exclude entries must be plain paths"
                )
            items.append(value)
            continue
        raise ValueError(
            f"line {lineno}: docs/_config.yml only lists Pages exclude paths "
            f"({stripped!r}). Other keys change the site."
        )
    if not seen:
        raise ValueError("docs/_config.yml has no exclude: list")
    if not items:
        raise ValueError("docs/_config.yml exclude list is empty")
    return items


def is_excluded(relative: str, patterns: list[str]) -> bool:
    """Whether Jekyll 3's entry filter drops ``relative`` (a path under docs/).

    A pattern matches by ``File.fnmatch`` or as a string prefix of the source
    path. ``changelog.d`` therefore drops ``changelog.d/note.md``, and
    ``CHANGELOG.md`` also drops ``CHANGELOG.md-extra``.
    """
    relative = relative.replace("\\", "/")
    for pattern in patterns:
        pattern = pattern.replace("\\", "/").lstrip("/")
        if pattern.startswith("./"):
            pattern = pattern[2:]
        if not pattern:
            raise ValueError("empty exclude entry")
        if fnmatch.fnmatchcase(relative, pattern) or relative.startswith(pattern):
            return True
    return False


def liquid_offenders(docs: Path, patterns: list[str]) -> list[str]:
    offenders = []
    for path in sorted(docs.rglob("*.md")):
        if not path.is_file():
            continue
        relative = path.relative_to(docs).as_posix()
        if is_excluded(relative, patterns):
            continue
        text = path.read_text(encoding="utf-8")
        if any(opener in text for opener in _LIQUID_OPENERS):
            offenders.append(relative)
    return offenders


def failure_message(offenders: list[str]) -> str:
    listed = "\n".join(f"  docs/{name}" for name in offenders)
    return (
        "GitHub Pages builds docs/ with Jekyll, and these markdown files "
        "contain '{{' or '{%' without being listed in docs/_config.yml "
        "exclude, so the build will fail. Add the file to exclude or "
        "reword the prose:\n"
        f"{listed}"
    )


def test_published_docs_markdown_has_no_liquid_syntax():
    patterns = read_exclude(CONFIG.read_text(encoding="utf-8"))
    offenders = liquid_offenders(DOCS, patterns)
    assert offenders == [], failure_message(offenders)


def test_unexcluded_liquid_names_the_file_and_the_remedy(tmp_path: Path):
    docs = tmp_path / "docs"
    nested = docs / "changelog.d"
    nested.mkdir(parents=True)
    (docs / "plain.md").write_text("a quiet page\n", encoding="utf-8")
    (docs / "quoted.md").write_text("a {{ token\n", encoding="utf-8")
    (docs / "tag.md").write_text("a {% token\n", encoding="utf-8")
    (docs / "CHANGELOG.md").write_text("kept {{ and {%\n", encoding="utf-8")
    (nested / "note.md").write_text("kept {{\n", encoding="utf-8")
    (docs / "CHANGELOG.md-extra.md").write_text("prefix {{\n", encoding="utf-8")
    offenders = liquid_offenders(docs, ["CHANGELOG.md", "changelog.d"])
    assert offenders == ["quoted.md", "tag.md"]
    text = failure_message(offenders)
    assert "docs/quoted.md" in text
    assert "docs/tag.md" in text
    assert "Add the file to exclude or reword" in text


def test_pages_config_excludes_the_changelog_and_nothing_nested():
    patterns = read_exclude(CONFIG.read_text(encoding="utf-8"))
    # Membership, not an exact list: the liquid-guard message tells an author
    # to add a file to exclude, and that remedy must not fail this test.
    assert "CHANGELOG.md" in patterns
    assert "CNAME" in patterns
    assert is_excluded("CHANGELOG.md", patterns)
    assert is_excluded("CNAME", patterns)
    assert not is_excluded("roadmap/README.md", patterns)
    assert not is_excluded("changelog.d/README.md", patterns)


def test_pages_config_rejects_anything_but_the_exclude_list():
    with pytest.raises(ValueError, match="only lists Pages exclude paths"):
        read_exclude("exclude:\n  - CHANGELOG.md\ntheme: primer\n")
    with pytest.raises(ValueError, match="block list"):
        read_exclude("exclude: [CHANGELOG.md]\n")
