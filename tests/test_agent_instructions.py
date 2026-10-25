"""Keep the shared instruction entry points discoverable after a checkout."""
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / '.claude/skills'
ALIASES = ROOT / '.agents/skills'


def test_claude_imports_the_shared_contract():
    assert (ROOT / 'CLAUDE.md').read_bytes() == b'@AGENTS.md\n'
    contract = (ROOT / 'AGENTS.md').read_text(encoding='utf-8')
    assert contract.strip(), 'The imported shared contract must not be empty'
    assert not re.search(r'^\s*@(?:\./)?CLAUDE\.md\s*$', contract, re.M), 'Import cycle'


def test_skill_aliases_cover_the_sources_without_copies():
    sources = {p.name: p for p in SOURCES.iterdir() if p.is_dir()}
    aliases = {p.name: p for p in ALIASES.iterdir() if not p.name.startswith('.')}
    assert sources, 'No repository skills found'
    assert aliases.keys() == sources.keys(), 'Missing or extra skill discovery entry'
    for name, source in sources.items():
        alias = aliases[name]
        assert alias.is_symlink(), f'{name}: enable Git/OS symlinks; do not copy skills'
        assert not alias.readlink().is_absolute(), f'{name}: alias must be checkout-relative'
        assert alias.resolve(strict=True) == source, f'{name}: wrong skill target'
        assert (alias / 'SKILL.md').is_file(), f'{name}: missing skill entry point'


def test_skill_frontmatter_matches_its_discovery_name():
    for source in SOURCES.iterdir():
        if not source.is_dir():
            continue
        text = (source / 'SKILL.md').read_text(encoding='utf-8')
        assert text.startswith('---\n'), f'{source.name}: missing frontmatter'
        frontmatter, separator, _ = text[4:].partition('\n---\n')
        assert separator, f'{source.name}: unclosed frontmatter'
        names = re.findall(r'^name:[ \t]*(.*?)\s*$', frontmatter, re.M)
        assert len(names) == 1, f'{source.name}: require one name field'
        name = names[0]
        if name.startswith(('"', "'")):
            assert name[-1:] == name[:1], f'{source.name}: unclosed name quote'
            name = name[1:-1]
        assert name == source.name, f'{source.name}: mismatched skill name {name!r}'
        assert re.search(r'^description:[ \t]*\S.*$', frontmatter, re.M), source.name
