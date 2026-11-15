"""Changelog fragments: the file every change batch writes, and the fold the
status pull request runs (AGENTS.md, "Working in parallel").

The fold edits the log every cold session navigates by, so these tests pin where
an entry lands, what the fold must leave alone, which fragments it refuses, and
that it stops instead of guessing an order it cannot read.
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

### Fixed

- **Released fix**
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


def test_fold_never_reaches_into_a_released_or_a_later_unreleased_section():
    # Unreleased has no "### Fixed" here, and the released section below it does.
    no_fixed = CHANGELOG.replace("### Fixed\n\n- **Older fix**", "- **Older fix**")
    with pytest.raises(fc.FragmentError, match="### Fixed"):
        fc.fold(no_fixed, [parsed("Fix", section="Fixed")])
    with pytest.raises(fc.FragmentError, match="Unreleased"):
        fc.fold("# Changelog\n\n## [0.1.0]\n\n### Added\n", [parsed("New")])
    lower = "\n## [Unreleased]\n\n### Added\n\n- **A stale lower section**\n"
    folded = fc.fold(CHANGELOG + lower, [parsed("New")])
    released = "## [0.1.0-beta]"
    assert folded[folded.index(released):] == (CHANGELOG + lower)[CHANGELOG.index(released):]


def test_fold_tolerates_trailing_spaces_on_headings_and_keeps_them():
    spaced = CHANGELOG.replace("## [Unreleased]\n", "## [Unreleased]  \n", 1).replace(
        "### Added\n", "### Added \n", 1)
    folded = fc.fold(spaced, [parsed("New")])
    assert "## [Unreleased]  \n\n### Added \n\n- **New**" in folded


def test_fold_refuses_an_entry_that_is_already_in_the_changelog():
    once = fc.fold(CHANGELOG, [parsed("New")])
    with pytest.raises(fc.FragmentError, match="already in the changelog"):
        fc.fold(once, [parsed("New")])


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
    assert fc.parse_fragment("codex-feature_x.2.md", fragment_text("x")).section == "Added"


def test_status_lines_keep_their_text_and_stay_out_of_the_entry():
    lines = ["checklist S3: Not started to Partial (endpoint merged)", "roadmap index: add #999"]
    fragment = parsed("With status", status=lines)
    assert fragment.status == tuple(lines)
    assert "Status:" not in fragment.body and "Section:" not in fragment.body


def _git(repo, *args, when=None):
    env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)
    if when:
        stamp = f"2026-11-{when:02d}T10:00:00+00:00"
        env.update(GIT_AUTHOR_DATE=stamp, GIT_COMMITTER_DATE=stamp)
    subprocess.run(["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid",
                    "-c", "commit.gpgsign=false", *args],
                   cwd=repo, env=env, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    """A git repository holding a changelog and an empty fragment directory."""
    root = tmp_path / "repo"
    directory = root / "docs/changelog.d"
    directory.mkdir(parents=True)
    (root / "docs/CHANGELOG.md").write_text(CHANGELOG, encoding="utf-8")
    (directory / "README.md").write_text("How fragments work.\n", encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "checkout", "-q", "-b", "trunk")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "start", when=1)
    return root


def _fold(root, *extra):
    return fc.main(["--dir", str(root / "docs/changelog.d"),
                    "--changelog", str(root / "docs/CHANGELOG.md"), *extra])


def _commit_fragment(root, name, headline, when, **kwargs):
    (root / "docs/changelog.d" / name).write_text(fragment_text(headline, **kwargs),
                                                  encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", name, when=when)


def test_cli_folds_in_commit_order_deletes_fragments_and_reports_status(repo, capsys):
    # The file name that sorts first landed later, so only history can order them.
    _commit_fragment(repo, "zeta-earlier.md", "Landed first", when=2)
    _commit_fragment(repo, "alpha-later.md", "Landed second", when=3,
                     status=["checklist F4: Partial to Done"])
    # A fragment still uncommitted is the newest of all.
    (repo / "docs/changelog.d/beta-uncommitted.md").write_text(
        fragment_text("Not yet committed"), encoding="utf-8")

    assert _fold(repo) == 0

    folded = (repo / "docs/CHANGELOG.md").read_text(encoding="utf-8")
    assert (folded.index("**Not yet committed**") < folded.index("**Landed second**")
            < folded.index("**Landed first**") < folded.index("**Older added entry**"))
    assert [path.name for path in (repo / "docs/changelog.d").iterdir()] == ["README.md"]
    out = capsys.readouterr().out
    assert "folded alpha-later.md under ### Added" in out
    assert "status: checklist F4: Partial to Done" in out


def test_a_true_merge_orders_by_when_it_merged_not_when_it_was_written(repo):
    _git(repo, "checkout", "-q", "-b", "a")
    _commit_fragment(repo, "a.md", "Written first, merged last", when=2)
    _git(repo, "checkout", "-q", "-b", "b", "trunk")
    _commit_fragment(repo, "b.md", "Written second, merged first", when=3)
    _git(repo, "checkout", "-q", "trunk")
    _git(repo, "merge", "-q", "--no-ff", "-m", "merge b", "b", when=4)
    _git(repo, "merge", "-q", "--no-ff", "-m", "merge a", "a", when=5)

    assert _fold(repo) == 0

    folded = (repo / "docs/CHANGELOG.md").read_text(encoding="utf-8")
    assert folded.index("merged last**") < folded.index("merged first**")


def test_the_fold_stops_when_history_cannot_give_the_order(repo, tmp_path, capsys):
    _commit_fragment(repo, "zeta-earlier.md", "Landed first", when=2)
    _commit_fragment(repo, "alpha-later.md", "Landed second", when=3)
    shallow = tmp_path / "shallow"
    subprocess.run(["git", "clone", "-q", "--depth", "1", repo.as_uri(), str(shallow)],
                   check=True, capture_output=True)
    plain = tmp_path / "plain"
    (plain / "docs/changelog.d").mkdir(parents=True)
    for name in ("docs/CHANGELOG.md", "docs/changelog.d/alpha-later.md"):
        (plain / name).write_text((repo / name).read_text(encoding="utf-8"), encoding="utf-8")

    for root, reason in ((shallow, "shallow history"), (plain, "inside the repository")):
        assert _fold(root) == 1
        assert reason in capsys.readouterr().err
        assert (root / "docs/CHANGELOG.md").read_text(encoding="utf-8") == CHANGELOG
        assert (root / "docs/changelog.d/alpha-later.md").exists()


def test_check_and_fold_change_nothing_when_anything_is_wrong(tmp_path, capsys):
    directory = tmp_path / "changelog.d"
    directory.mkdir()
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(CHANGELOG, encoding="utf-8")
    good = directory / "codex-good.md"
    good.write_text(fragment_text("Good"), encoding="utf-8")
    args = ["--dir", str(directory), "--changelog", str(changelog)]

    assert fc.main([*args, "--check"]) == 0
    assert "1 changelog fragment(s) valid" in capsys.readouterr().out

    def refused(arguments, reason):
        assert fc.main(arguments) == 1
        assert reason in capsys.readouterr().err
        assert good.exists()

    # --check proves the fold would be accepted, not only that fragments parse.
    changelog.write_text(CHANGELOG.replace("### Added", "### New"), encoding="utf-8")
    refused([*args, "--check"], "### Added")
    changelog.write_bytes(CHANGELOG.replace("\n", "\r\n").encode("utf-8"))
    refused([*args, "--check"], "CRLF")
    assert b"\r\n" in changelog.read_bytes()
    changelog.write_text(CHANGELOG, encoding="utf-8")
    refused(["--dir", str(tmp_path / "missing"), "--changelog", str(changelog), "--check"],
            "no such fragment directory")
    refused(["--dir", str(directory), "--changelog", str(tmp_path / "missing.md")], "missing.md")

    # A stray entry fails its own pull request instead of being skipped.
    nested = directory / "codex"
    nested.mkdir()
    (nested / "report-flow.md").write_text(fragment_text("Nested"), encoding="utf-8")
    for arguments in (args, [*args, "--check"]):
        refused(arguments, "codex: name the fragment")
    (nested / "report-flow.md").unlink()
    nested.rmdir()
    for name, text in (("codex-x.MD", fragment_text("Upper")), ("notes.txt", "notes"),
                       ("codex-bad.md", "Section: Added\n\nno bullet\n")):
        stray = directory / name
        stray.write_text(text, encoding="utf-8")
        for arguments in (args, [*args, "--check"]):
            refused(arguments, name)
        stray.unlink()
    assert changelog.read_text(encoding="utf-8") == CHANGELOG


def test_an_empty_fragment_directory_is_not_an_error(tmp_path, capsys):
    directory = tmp_path / "changelog.d"
    directory.mkdir()
    (directory / "README.md").write_text("How fragments work.\n", encoding="utf-8")
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(CHANGELOG, encoding="utf-8")
    assert fc.main(["--dir", str(directory), "--changelog", str(changelog)]) == 0
    assert "No changelog fragments to fold." in capsys.readouterr().out
    assert changelog.read_text(encoding="utf-8") == CHANGELOG


def test_repository_fragments_are_valid_and_the_real_changelog_accepts_a_fold(capsys):
    """Runs in the Python gate, so a malformed fragment fails its own pull request."""
    assert fc.main(["--check"]) == 0, capsys.readouterr().err
    real = (ROOT / "docs/CHANGELOG.md").read_text(encoding="utf-8")
    # Headings are matched as whole lines: entry prose may quote a heading mid-line.
    start = real.index("\n## [Unreleased]\n") + 1
    for section in fc.SECTIONS:
        folded = fc.fold(real, [parsed("Probe entry", section=section)])
        assert folded[:start] == real[:start], "the QA bullets above Unreleased must not move"
        heading = folded.index(f"\n### {section}\n", start) + 1
        assert folded[heading:].startswith(f"### {section}\n\n- **Probe entry**")
        # Nothing else moved: taking the probe back out restores the file exactly.
        probe = parsed("Probe entry", section=section).body + "\n\n"
        assert folded.replace(probe, "", 1) == real
