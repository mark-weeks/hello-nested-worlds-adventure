"""Private preferences survive registry retirement; live handles expose no IDs."""
import pytest

import persistence
from agents import identities
from persistence import blocks, participants
from server import block_targets


def test_retired_agent_can_be_unblocked_only_by_owner(accounts, monkeypatch):
    owner, other = [participants.identify(key)['id'] for key in accounts]
    target = blocks.agent_target('Tessera')
    blocks.set_block(owner, target, True)
    monkeypatch.delitem(identities._CANONICAL, persistence.name_key('Tessera'))
    assert blocks.list_blocks(owner) == [{'id': target, 'name': 'Unavailable traveler'}]
    token = block_targets.wire_blocks(owner, blocks.list_blocks(owner))[0]['id']
    assert block_targets.resolve(owner, token) == target
    # Removal is an owner-scoped operation, even after registry validation fails.
    assert blocks.set_block(other, target, False) == []
    assert blocks.list_blocks(owner)
    assert blocks.set_block(owner, target, False) == []
    with pytest.raises(ValueError):
        blocks.set_block(owner, target, True)
    assert persistence.get_mutations(382) == []


def test_handles_are_scoped_to_viewer_and_runtime_without_changing_preferences(accounts, monkeypatch):
    owner, other = [participants.identify(key)['id'] for key in accounts]
    target = blocks.agent_target('Tessera')
    rows = blocks.set_block(owner, target, True)
    token = block_targets.handle(owner, target)
    assert token != target and token != block_targets.handle(other, target)
    assert block_targets.resolve(owner, token) == target
    with pytest.raises(ValueError):
        block_targets.resolve(other, token)
    monkeypatch.setattr(block_targets, '_KEY', b'fresh-runtime-key')
    new_token = block_targets.wire_blocks(owner, blocks.list_blocks(owner))[0]['id']
    assert new_token != token
    assert block_targets.resolve(owner, new_token) == target
    with pytest.raises(ValueError):
        block_targets.resolve(owner, token)
    assert blocks.list_blocks(owner) == rows


def test_nested_wire_projection_does_not_mutate_internal_filter_ids(accounts):
    owner, other = [participants.identify(key)['id'] for key in accounts]
    agent = blocks.agent_target('Tessera')
    message = {'type': 'welcome', 'participant_id': owner,
               'players': [{'name': 'Bea', 'participant_id': other}],
               'agents': [{'name': 'Tessera', 'participant_id': agent}],
               'blocks': [{'id': agent, 'name': 'Tessera'}]}
    wire = block_targets.wire_message(owner, message)
    assert wire['participant_id'] == block_targets.handle(owner, owner)
    assert wire['players'][0]['participant_id'] == block_targets.handle(owner, other)
    assert wire['agents'][0]['participant_id'] == wire['blocks'][0]['id']
    assert message['players'][0]['participant_id'] == other
    assert message['blocks'][0]['id'] == agent
