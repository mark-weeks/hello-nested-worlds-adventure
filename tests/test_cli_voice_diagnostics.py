"""CLI failures stay in fiction; opt-in operator logs retain safe diagnostics."""
from contextlib import closing
import logging
from types import SimpleNamespace

import pytest

import consciousness
import interface
import main
import persistence
from consciousness import runtime
from multiverse.node import SpatialNode


@pytest.mark.parametrize('surface', ['command', 'interactive'])
@pytest.mark.parametrize('failure,diagnostic', [
    (RuntimeError('secret credential and private player text'), 'RuntimeError'),
    (runtime.NoTextError('No text in model response (complete=False, finish=refusal)'), 'finish=refusal'),
])
def test_cli_fallback_has_off_screen_diagnostics(monkeypatch, tmp_path, capsys, surface, failure, diagnostic):
    node = SpatialNode(name='Vault', level='Room', properties={})
    monkeypatch.setattr(main.store, 'world_tree', lambda **kwargs: node)
    monkeypatch.setattr(main.wrap, 'is_hinge', lambda *args: False)
    def unavailable(*args, **kwargs):
        raise failure
    monkeypatch.setattr(consciousness, 'speak', unavailable)
    logger = logging.getLogger('nested_worlds.cli')
    monkeypatch.setattr(logger, 'handlers', [logging.NullHandler()])
    monkeypatch.setattr(logger, 'propagate', False)
    monkeypatch.setattr(logger, 'level', logging.WARNING)
    def call():
        if surface == 'command':
            main.cmd_speak(SimpleNamespace(seed=42, node=None, message='Hello'))
        else:
            interface._speak_to(node, 'Hello', seed=42)
    call()  # The default has no stderr handler or lastResort output.
    output = capsys.readouterr()
    assert consciousness.fallback_voice(node) in output.out and output.err == ''
    assert diagnostic not in output.out
    path = tmp_path / 'operator.log'
    with closing(logging.FileHandler(path)) as handler:
        logger.addHandler(handler)
        try:
            call()
        finally:
            logger.removeHandler(handler)
    output = capsys.readouterr()
    assert consciousness.fallback_voice(node) in output.out and output.err == ''
    assert diagnostic in path.read_text()
    assert 'secret credential' not in path.read_text()
    assert persistence.get_node_history(42, node.name) == []
