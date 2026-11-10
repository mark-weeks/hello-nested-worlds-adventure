"""Private preferences survive registry retirement; live handles expose no IDs."""
from collections import OrderedDict

import pytest

import persistence
from agents import identities
from persistence import blocks, participants
from server import block_targets
from server.rooms import Player, get_room
from tests.test_server_rooms import FakeSock


@pytest.fixture(autouse=True)
def isolated_handle_cache(monkeypatch):
    monkeypatch.setattr(block_targets, '_HANDLES', OrderedDict())


def test_retired_agent_can_be_unblocked_only_by_owner(accounts, monkeypatch):
    owner, other = [participants.identify(key)['id'] for key in accounts]
    target = blocks.agent_target('Tessera')
    blocks.set_block(owner, target, True)
    monkeypatch.delitem(identities._CANONICAL, persistence.name_key('Tessera'))
    assert blocks.list_blocks(owner) == [{'id': target, 'name': 'Unavailable traveler'}]
    token = block_targets.wire_blocks(owner, blocks.list_blocks(owner))[0]['id']
    block_targets._HANDLES.clear()  # Saved targets remain removable without the cache.
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


def test_recently_displayed_disconnected_target_resolves_without_database(accounts, monkeypatch):
    owner, other = [participants.identify(key)['id'] for key in accounts]
    token = block_targets.wire_message(owner, {'type': 'chat', 'participant_id': other})['participant_id']

    def no_database():
        raise AssertionError('A recently displayed handle must not scan historical participants.')

    monkeypatch.setattr(persistence, '_connection', no_database)
    assert block_targets.resolve(owner, token) == other


def test_bounded_cache_keeps_recent_handles_and_falls_back_to_live_or_saved_targets(accounts, monkeypatch):
    owner, other = [participants.identify(key)['id'] for key in accounts]
    monkeypatch.setattr(block_targets, '_HANDLE_LIMIT', 2)
    token = block_targets.handle(owner, other)
    retained = block_targets.handle(owner, 'agent:Tessera')
    assert block_targets.resolve(owner, token) == other  # Refresh this entry's recency.
    block_targets.handle(owner, 'agent:Vex')
    assert (owner, retained) not in block_targets._HANDLES
    assert len(block_targets._HANDLES) == 2
    block_targets.handle(owner, 'agent:Halden')
    assert (owner, token) not in block_targets._HANDLES
    # A long-disconnected, unblocked and evicted target requires a fresh live
    # handle. No all-time participant scan is made to recover old display data.
    with pytest.raises(ValueError):
        block_targets.resolve(owner, token)
    room = get_room(382)
    room.players['other'] = Player('Bea', 382, 'root', 'other', FakeSock(), participant_id=other)
    assert block_targets.resolve(owner, token) == other
    room.players.clear()
    blocks.set_block(owner, other, True)
    block_targets._HANDLES.clear()
    assert block_targets.resolve(owner, token) == other
    with pytest.raises(ValueError):
        block_targets.resolve(other, token)


@pytest.mark.parametrize('token', ['?', 'é' * 32, 'A' * 32, ['0' * 32], None])
def test_non_handle_input_is_refused(token):
    with pytest.raises(ValueError, match='Choose another traveler'):
        block_targets.resolve('viewer', token)
