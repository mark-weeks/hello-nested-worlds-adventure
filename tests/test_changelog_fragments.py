"""Changelog fragments: the file every change batch writes, and the fold the
status pull request runs (AGENTS.md, "Working in parallel").

The fold edits the log every cold session navigates by, so these tests pin where
an entry lands, what the fold must leave alone, and which fragments it refuses.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import fold_changelog as fc  # noqa: E402

CHANGELOG = """# Changelog

- **A QA prerelease bullet above the release sections** stays where it is.

## [Unreleased]

### Added

- **Older added entry** (`a.py`). **Verified:** x. **Irreversibility check:** none — y.

### Fixed

- **Older fix** (`b.py`). **Verified:** x. **Irreversibility check:** none — y.

### Added

- **An earlier group inside Unreleased** that must not receive new entries.

## [0.1.0-beta] — 2026-07-19

### Added

- **Released entry**
"""


def fragment_text(headline, section="Added", status=()):
    header = [f"Section: {section}", *(f"Status: {line}" for line in status)]
    return "\n".join(header) + (
        f"\n\n- **{headline}** (`x.py`). What changed and why.\n"
        "  **Verified:** focused tests.\n"
        "  **Irreversibility check:** none — documentation only.\n"
    )


def parsed(headline, **kwargs):
    return fc.parse_fragment("claude-example.md", fragment_text(headline, **kwargs))


def test_fold_puts_the_newest_entry_first_in_the_first_unreleased_section():
    folded = fc.fold(CHANGELOG, [parsed("Merged first"), parsed("Merged second")])
    added = folded.index("### Added")
    order = [folded.index(text) for text in
             ("**Merged second**", "**Merged first**", "**Older added entry**")]
    assert added < order[0] < order[1] < order[2] < folded.index("### Fixed")
    # One blank line under the heading and between entries, as the log is written.
    assert "### Added\n\n- **Merged second**" in folded
    assert "none — documentation only.\n\n- **Merged first**" in folded


def test_a_fix_goes_under_fixed_and_keeps_its_continuation_lines():
    folded = fc.fold(CHANGELOG, [parsed("A correction", section="Fixed")])
    assert ("### Fixed\n\n- **A correction** (`x.py`). What changed and why.\n"
            "  **Verified:** focused tests.\n"
            "  **Irreversibility check:** none — documentation only.\n\n"
            "- **Older fix**") in folded


def test_fold_leaves_everything_outside_the_target_heading_untouched():
    folded = fc.fold(CHANGELOG, [parsed("New"), parsed("Fix", section="Fixed")])
    head, tail = "## [Unreleased]", "### Added\n\n- **An earlier group"
    assert folded[:folded.index(head)] == CHANGELOG[:CHANGELOG.index(head)]
    assert folded[folded.index(tail):] == CHANGELOG[CHANGELOG.index(tail):]
    assert folded.count("**New**") == folded.count("**Fix**") == 1


def test_fold_refuses_a_changelog_without_the_expected_headings():
    with pytest.raises(fc.FragmentError, match="Unreleased"):
        fc.fold("# Changelog\n\n## [0.1.0]\n\n### Added\n", [parsed("New")])
    no_fixed = CHANGELOG.replace("### Fixed\n\n- **Older fix**", "- **Older fix**")
    with pytest.raises(fc.FragmentError, match="### Fixed"):
        fc.fold(no_fixed, [parsed("Fix", section="Fixed")])


@pytest.mark.parametrize("text, reason", [
    (fragment_text("x").replace("**Verified:**", "Verified:"), "Verified"),
    (fragment_text("x").replace("**Irreversibility check:**", "Check:"), "Irreversibility"),
    (fragment_text("x") + "- **A second bullet** for the same pull request.\n", "one bullet"),
    (fragment_text("x").replace("  **Verified:**", "**Verified:**"), "one bullet"),
    (fragment_text("x", section="Changed"), "Section must be"),
    (fragment_text("x").replace("Section: Added\n", ""), "Section must be"),
    ("Section: Added\nSection: Fixed\n" + fragment_text("x").split("\n", 1)[1], "more than one"),
    ("Owner: someone\n" + fragment_text("x"), "unknown header"),
    (fragment_text("x").replace("Section: Added\n\n", "Section: Added\n"), "blank line"),
    (fragment_text("x", status=[""]), "empty Status"),
    ("Section: Added\n\nPlain prose, not a bullet. **Verified:** a. "
     "**Irreversibility check:** b.\n", "one bullet starting"),
    ("Section: Added", "blank line"),
])
def test_malformed_fragments_are_refused(text, reason):
    with pytest.raises(fc.FragmentError, match=reason):
        fc.parse_fragment("claude-example.md", text)


@pytest.mark.parametrize("name", ["Claude-Example.md", "claude/example.md", "notes.txt", ".md"])
def test_fragment_names_follow_the_branch_form(name):
    with pytest.raises(fc.FragmentError, match="name the fragment"):
        fc.parse_fragment(name, fragment_text("x"))


def test_status_lines_keep_their_text_and_stay_out_of_the_entry():
    lines = ["checklist S3: Not started to Partial (endpoint merged)", "roadmap index: add #999"]
    fragment = parsed("With status", status=lines)
    assert fragment.status == tuple(lines)
    assert "Status:" not in fragment.body and "Section:" not in fragment.body


def _git(repo, *args, when=None):
    env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)
    if when:
        env.update(GIT_AUTHOR_DATE=when, GIT_COMMITTER_DATE=when)
    subprocess.run(["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid",
                    "-c", "commit.gpgsign=false", *args],
                   cwd=repo, env=env, check=True, capture_output=True)


def test_cli_folds_in_merge_order_deletes_fragments_and_reports_status(tmp_path, capsys):
    directory = tmp_path / "docs/changelog.d"
    directory.mkdir(parents=True)
    changelog = tmp_path / "docs/CHANGELOG.md"
    changelog.write_text(CHANGELOG, encoding="utf-8")
    (directory / "README.md").write_text("How fragments work.\n", encoding="utf-8")
    _git(tmp_path, "init", "-q")
    # The file name that sorts first lands later, so only commit time can order them.
    (directory / "zeta-earlier.md").write_text(fragment_text("Landed first"), encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "one", when="2026-11-01T10:00:00+00:00")
    (directory / "alpha-later.md").write_text(
        fragment_text("Landed second", status=["checklist F4: Partial to Done"]), encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "two", when="2026-11-02T10:00:00+00:00")

    assert fc.main(["--dir", str(directory), "--changelog", str(changelog)]) == 0

    folded = changelog.read_text(encoding="utf-8")
    assert folded.index("**Landed second**") < folded.index("**Landed first**")
    assert sorted(path.name for path in directory.iterdir()) == ["README.md"]
    out = capsys.readouterr().out
    assert "folded alpha-later.md under ### Added" in out
    assert "status: checklist F4: Partial to Done" in out


def test_cli_changes_nothing_when_a_fragment_is_malformed_or_only_checked(tmp_path, capsys):
    directory = tmp_path / "changelog.d"
    directory.mkdir()
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(CHANGELOG, encoding="utf-8")
    good = directory / "codex-good.md"
    good.write_text(fragment_text("Good"), encoding="utf-8")
    args = ["--dir", str(directory), "--changelog", str(changelog)]

    assert fc.main([*args, "--check"]) == 0
    assert "1 changelog fragment(s) valid" in capsys.readouterr().out
    assert changelog.read_text(encoding="utf-8") == CHANGELOG and good.exists()

    (directory / "codex-bad.md").write_text("Section: Added\n\nno bullet\n", encoding="utf-8")
    for arguments in (args, [*args, "--check"]):
        assert fc.main(arguments) == 1
        assert "codex-bad.md" in capsys.readouterr().err
        assert changelog.read_text(encoding="utf-8") == CHANGELOG
        assert good.exists()


def test_repository_fragments_are_valid_and_the_real_changelog_accepts_a_fold():
    """Runs in the Python gate, so a malformed fragment fails its own pull request."""
    for path, _ in fc.load(ROOT / "docs/changelog.d"):
        assert path.name != "README.md"
    real = (ROOT / "docs/CHANGELOG.md").read_text(encoding="utf-8")
    for section in fc.SECTIONS:
        folded = fc.fold(real, [parsed("Probe entry", section=section)])
        start = real.index("## [Unreleased]")
        assert folded[:start] == real[:start], "the QA bullets above Unreleased must not move"
        heading = folded.index(f"### {section}", start)
        assert folded[heading:].startswith(f"### {section}\n\n- **Probe entry**")
        # Nothing else moved: taking the probe back out restores the file exactly.
        probe = parsed("Probe entry", section=section).body + "\n\n"
        assert folded.replace(probe, "", 1) == real
