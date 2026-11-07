"""A private block changes live delivery, never another player's world history."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import threading
import time
import urllib.error
import urllib.request

import pytest

import persistence
from multiverse import store
from persistence import blocks, participants, sanctions
from server import _Handler, _ThreadedServer
from server.block_targets import handle
from server.rooms import (Player, agent_enter, agent_leave, agent_move, agents_snapshot,
                          broadcast, clear_rooms, get_room, snapshot)
from tests.test_day_one_recording import _ws_connect, _ws_send_json
from tests.test_server_rooms import FakeSock, StallSock, _wait_for
from tests.test_ws_credential_lifetime import _until_type


KEY_C = 'nw_' + 'c' * 32


@pytest.fixture
def server(accounts):
    srv = _ThreadedServer(('127.0.0.1', 0), _Handler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    sockets = []

    def request(key, body=None):
        req = urllib.request.Request(f'http://127.0.0.1:{srv.server_port}/blocks',
            data=json.dumps(body).encode() if body is not None else None,
            headers={'X-Beta-Key': key, 'Content-Type': 'application/json'})
        try:
            response = urllib.request.urlopen(req, timeout=5)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            return response.status, json.load(response), dict(response.headers)

    def join(key):
        sock, status = _ws_connect(srv.server_port, 382, 'ignored', invite_key=key)
        assert b'101' in status
        sockets.append(sock)
        return sock, _until_type(sock, 'welcome')[0]

    yield request, join
    for sock in sockets:
        sock.close()
    srv.shutdown()
    srv.server_close()
    thread.join(5)


def test_block_survives_both_rotations_restart_and_target_sanction(accounts):
    a, b = [participants.identify(k) for k in accounts]
    expected = [{'id': b['id'], 'name': 'Bea'}]
    with ThreadPoolExecutor(4) as pool:
        assert list(pool.map(lambda _: blocks.set_block(a['id'], b['id'], True), range(8))) == [expected] * 8
    assert blocks.list_blocks(b['id']) == []  # One-way, private ownership.
    a_key, b_key = 'nw_' + 'x' * 32, 'nw_' + 'y' * 32
    participants.rotate(accounts[0], a_key)
    participants.rotate(accounts[1], b_key)
    persistence._initialized.discard(persistence._DB_PATH)
    clear_rooms()
    assert blocks.list_blocks(participants.identify(a_key)['id']) == expected
    sanctions.ban('Bea', reason='test')
    assert blocks.list_blocks(a['id']) == expected
    assert blocks.set_block(a['id'], b['id'], False) == []
    assert blocks.set_block(a['id'], b['id'], False) == []
    assert persistence.get_mutations(382) == []
    with persistence._connection() as conn:
        assert conn.execute('SELECT COUNT(*) FROM participant_blocks').fetchone()[0] == 0


@pytest.mark.parametrize('target,blocked', [
    (None, True), ([], True), ('unknown', True), ('0' * 32, True),
    ('self', True), ('other', 1), ('other', 'false'), ('other', None),
])
def test_invalid_block_is_rejected_without_a_row(accounts, target, blocked):
    a, b = [participants.identify(k)['id'] for k in accounts]
    target = {'self': a, 'other': b}.get(target, target) if isinstance(target, str) else target
    with pytest.raises(ValueError):
        blocks.set_block(a, target, blocked)
    assert blocks.list_blocks(a) == []


def test_http_ownership_strict_shape_privacy_and_unblock_revoked_target(server, accounts):
    from server.block_targets import handle
    request, _ = server
    a, b = [participants.identify(k) for k in accounts]
    target = handle(a['id'], b['id'])
    response = request(accounts[0], {'participant': target, 'blocked': True, 'owner': b['id']})
    assert response[:2] == (200, {'blocks': [{'id': target, 'name': 'Bea'}]})
    assert response[2]['Cache-Control'] == 'no-store'
    assert all(value not in json.dumps(response) for value in (*accounts, a['id'], b['id']))
    assert request(accounts[1])[1] == {'blocks': []}
    assert request('')[0] == request('nw_' + 'z' * 32)[0] == 403
    for data in ({}, {'participant': target, 'blocked': 1},
                 {'participant': handle(a['id'], a['id']), 'blocked': True},
                 {'participant': b['id'], 'blocked': True},
                 {'participant': handle(b['id'], b['id']), 'blocked': True}):
        assert request(accounts[0], data)[0] == 400
    assert persistence.revoke_invite_key(accounts[1])
    assert request(accounts[0])[1]['blocks'][0]['name'] == 'Bea'
    assert request(accounts[0], {'participant': target, 'blocked': False})[:2] == (200, {'blocks': []})
    assert persistence.get_mutations(382) == []


def _through_pong(sock):
    _ws_send_json(sock, {'type': 'ping'})
    return _until_type(sock, 'pong')[1]


def test_real_sockets_one_way_all_tabs_reconnect_unblock_and_history(server, accounts):
    request, join = server
    persistence.mint_invite_key(KEY_C, 'Cleo')
    bea, bw = join(accounts[1])
    ada, aw = join(accounts[0])
    ada2, _ = join(accounts[0])
    cleo, _ = join(KEY_C)
    a, b, c = [participants.identify(key)['id'] for key in (*accounts, KEY_C)]
    target = handle(a, b)
    cleo_target = handle(c, b)
    assert len({target, cleo_target, bw['participant_id']}) == 3
    assert all(identity not in json.dumps(aw) for identity in (a, b, c))
    assert next(p for p in aw['players'] if p['name'] == 'Bea')['participant_id'] == target
    for sock in (ada, ada2, bea, cleo):
        _through_pong(sock)

    assert request(accounts[0], {'participant': target, 'blocked': True})[0] == 200
    for sock in (ada, ada2):
        changed, _ = _until_type(sock, 'blocks_changed')
        assert changed['blocks'] == [{'id': target, 'name': 'Bea'}]
        assert not any(p['participant_id'] == target for p in changed['players'])
    for sock in (bea, cleo):
        assert not any(m['type'] == 'blocks_changed' for m in _through_pong(sock))

    _ws_send_json(bea, {'type': 'chat', 'text': 'The signal reaches Cleo.'})
    assert _until_type(bea, 'chat')[0]['participant_id'] == bw['participant_id']
    chat = _until_type(cleo, 'chat')[0]
    assert chat['text'] == 'The signal reaches Cleo.'
    assert chat['participant_id'] == cleo_target
    target_node = store.world_tree(382).name
    _ws_send_json(bea, {'type': 'move', 'node': target_node})
    assert _until_type(cleo, 'player_move')[0]['participant_id'] == cleo_target
    bea2, _ = join(accounts[1])
    assert _until_type(cleo, 'player_join')[0]['participant_id'] == cleo_target
    for sock in (ada, ada2):
        assert not any(m.get('participant_id') == target for m in _through_pong(sock))

    # Blocking a person never suppresses world changes or records.
    broadcast(get_room(382), {'type': 'causal_event', 'participant_id': b,
                             'kind': 'RIPPLE', 'node': target_node})
    for sock in (ada, ada2):
        assert _until_type(sock, 'causal_event')[0]['participant_id'] == target
    assert _wait_for(lambda: any(r['type'] == 'PLAYER_CHAT' and r['player'] == 'Bea'
                                for r in persistence.get_mutations(382)))
    row = next(r for r in persistence.get_mutations(382) if r['type'] == 'PLAYER_CHAT')
    assert row['data']['text'] == 'The signal reaches Cleo.'

    _ws_send_json(ada, {'type': 'chat', 'text': 'Bea still hears me.'})
    assert _until_type(bea, 'chat')[0]['name'] == 'Ada'
    ada3, reconnect = join(accounts[0])
    assert reconnect['blocks'] == [{'id': target, 'name': 'Bea'}]
    assert not any(p['participant_id'] == target for p in reconnect['players'])
    assert request(accounts[0], {'participant': target, 'blocked': False})[0] == 200
    for sock in (ada, ada2, ada3):
        changed, _ = _until_type(sock, 'blocks_changed')
        assert changed['blocks'] == []
        assert len([p for p in changed['players'] if p['participant_id'] == target]) == 2
    _through_pong(bea2)
    _ws_send_json(bea2, {'type': 'chat', 'text': 'Visible again.'})
    for sock in (ada, ada2, ada3):
        assert _until_type(sock, 'chat')[0]['text'] == 'Visible again.'
    bea2.close()
    leave = _until_type(cleo, 'player_leave')[0]
    assert leave['participant_id'] == cleo_target
    assert b not in json.dumps(leave)


def test_writer_discards_queued_preblock_traffic_even_after_unblock():
    sock = FakeSock()
    player = Player('Ada', 382, 'root', 'a', sock, participant_id='a' * 32)
    target = 'b' * 32
    player.send_lock.acquire()
    player.start_writer()
    try:
        player.send({'type': 'chat', 'participant_id': target, 'text': 'stale'})
        assert _wait_for(lambda: player.outbox.empty())  # Dequeued, waiting for send lock.
        player.set_blocks([{'id': target, 'name': 'Bea'}])
        player.set_blocks([])
    finally:
        player.send_lock.release()
    player.send({'type': 'pong'})
    assert _wait_for(lambda: len(sock.sent) == 1)
    assert sock.sent[0].endswith(b'{"type": "pong"}')
    player.stop_writer()
    player._writer.join(2)


def test_queued_welcome_rechecks_roster_and_slow_writer_does_not_stall_blocks():
    room = get_room(382)
    slow_sock = StallSock()
    slow = Player('Ada', 382, 'root', 'a', slow_sock, participant_id='a' * 32)
    target = Player('Bea', 382, 'root', 'b', FakeSock(), participant_id='b' * 32)
    room.players.update(a=slow, b=target)
    slow.send_lock.acquire()
    slow.start_writer()
    slow.send({'type': 'welcome', 'players': snapshot(room)})
    assert _wait_for(lambda: slow.outbox.empty())
    try:
        from server.rooms import sync_blocks
        started = time.monotonic()
        sync_blocks(slow.participant_id, [{'id': target.participant_id, 'name': 'Bea'}])
        broadcast(room, {'type': 'causal_event', 'kind': 'RIPPLE'})
        assert time.monotonic() - started < 0.5
        assert len(target.sock.sent) == 1
    finally:
        slow_sock.release.set()
        slow.send_lock.release()
    assert _wait_for(lambda: len(slow_sock.sent) == 3)
    # Decode the WebSocket frame independently of short/extended length.
    from tests.test_ws_credential_lifetime import _read_frame
    class BytesSocket:
        def __init__(self, data):
            self.data = data
        def recv(self, n):
            result, self.data = self.data[:n], self.data[n:]
            return result
    welcome = json.loads(_read_frame(BytesSocket(slow_sock.sent[0]))[1])
    assert welcome['blocks'] == [{'id': handle(slow.participant_id, target.participant_id), 'name': 'Bea'}]
    assert [p['name'] for p in welcome['players']] == ['Ada']
    slow.stop_writer()
    slow._writer.join(2)


def test_agents_share_the_block_list_without_credentialed_accounts(accounts):
    a = participants.identify(accounts[0])['id']
    b = participants.identify(accounts[1])['id']
    blocks.set_block(a, b, True)
    result = blocks.set_block(a, 'agent:Tessera', True)
    assert {tuple(row.values()) for row in result} == {(b, 'Bea'), ('agent:Tessera', 'Tessera')}
    rotated = 'nw_' + 'x' * 32
    participants.rotate(accounts[0], rotated)
    persistence._initialized.discard(persistence._DB_PATH)
    assert blocks.list_blocks(participants.identify(rotated)['id']) == result
    assert blocks.list_blocks(b) == []
    assert blocks.set_block(a, 'agent:Tessera', False) == [{'id': b, 'name': 'Bea'}]
    assert persistence.get_mutations(382) == []
    with persistence._connection() as conn:
        assert conn.execute('SELECT COUNT(*) FROM participants').fetchone()[0] == 2


@pytest.mark.parametrize('target', ['agent:Stranger', 'agent:tessera', 'agent: Tessera',
                                   'agent:Ｔｅｓｓｅｒａ', 'agent:', 'Tessera'])
def test_agent_targets_are_exact_registry_identities(accounts, target):
    owner = participants.identify(accounts[0])['id']
    with pytest.raises(ValueError):
        blocks.set_block(owner, target, True)
    assert blocks.list_blocks(owner) == []


def test_every_server_owned_identity_can_be_blocked_and_unblocked(accounts):
    from agents.identities import SERVER_IDENTITIES
    owner = participants.identify(accounts[0])['id']
    for name in SERVER_IDENTITIES:
        target = 'agent:' + name
        assert blocks.set_block(owner, target, True) == [{'id': target, 'name': name}]
        assert blocks.set_block(owner, target, False) == []


def test_agent_live_block_filters_rosters_speech_encounters_and_summaries(server, accounts):
    request, join = server
    ada, _ = join(accounts[0])
    ada2, _ = join(accounts[0])
    bea, _ = join(accounts[1])
    owner = participants.identify(accounts[0])['id']
    tessera = handle(owner, 'agent:Tessera')
    vex = handle(owner, 'agent:Vex')
    room = get_room(382)
    agent_enter(room, 'Tessera', 'tender')
    agent_move(room, 'Tessera', 'Vault-1')
    agent_enter(room, 'Vex', 'destabilizer')
    agent_move(room, 'Vex', 'Vault-1')
    for sock in (ada, ada2, bea):
        _through_pong(sock)
    assert request(accounts[0], {'participant': tessera, 'blocked': True})[0] == 200
    for sock in (ada, ada2):
        changed = _until_type(sock, 'blocks_changed')[0]
        assert changed['blocks'] == [{'id': tessera, 'name': 'Tessera'}]
        assert [a['name'] for a in changed['agents']] == ['Vex']

    agent_move(room, 'Tessera', 'Vault-2')
    encounter = {'type': 'agent_encounter', 'agent1': 'Tessera', 'agent2': 'Vex', 'node': 'Vault-2'}
    broadcast(room, encounter)
    exchange = {'type': 'agent_talk', 'a': 'Tessera', 'b': 'Vex', 'node': 'Vault-2',
                'lines': [{'speaker': 'Tessera', 'line': 'Piece by piece.'},
                          {'speaker': 'Vex', 'line': 'Ask me how it breaks.'},
                          {'speaker': None, 'line': 'The two travelers part.'}]}
    persistence.record_mutation(382, 'Vault-2', 'AGENT_TALK', None, exchange)
    broadcast(room, exchange)
    broadcast(room, {'type': 'agent_done', 'name': 'Tessera', 'node': 'Vault-2', 'nodes_visited': 2})
    agent_leave(room, 'Tessera')
    for sock in (ada, ada2):
        frames = _through_pong(sock)
        assert [m['type'] for m in frames] == ['agent_talk']
        assert frames[0]['lines'] == [{'speaker': 'Vex', 'line': 'Ask me how it breaks.',
                                      'participant_id': vex}]
        assert 'a' not in frames[0] and frames[0]['b'] == 'Vex'
        assert frames[0]['participant_ids'] == [vex]
    seen = _through_pong(bea)
    assert [m['type'] for m in seen] == ['agent_move', 'agent_encounter', 'agent_talk',
                                       'agent_done', 'agent_leave']
    assert len(next(m for m in seen if m['type'] == 'agent_talk')['lines']) == 3
    assert request(accounts[1])[1]['blocks'] == []
    assert persistence.get_mutations(382)[0]['data']['lines'] == exchange['lines']

    # Effects remain shared even when the blocked agent caused them.
    for kind in ('causal_event', 'scale_act', 'puzzle_solved'):
        broadcast(room, {'type': kind, 'agent': 'Tessera', 'name': 'Tessera',
                         'participant_id': 'agent:Tessera', 'node': 'Vault-2'})
    assert [m['type'] for m in _through_pong(ada)] == ['causal_event', 'scale_act', 'puzzle_solved']
    agent_enter(room, 'Tessera', 'tender')
    agent_move(room, 'Tessera', 'Vault-3')
    ada3, welcome = join(accounts[0])
    assert welcome['blocks'] == [{'id': tessera, 'name': 'Tessera'}]
    assert [a['name'] for a in welcome['agents']] == ['Vex']
    assert request(accounts[0], {'participant': tessera, 'blocked': False})[0] == 200
    for sock in (ada, ada2, ada3):
        changed = _until_type(sock, 'blocks_changed')[0]
        assert changed['blocks'] == []
        assert {a['name'] for a in changed['agents']} == {'Tessera', 'Vex'}
    broadcast(room, exchange)
    assert len(_until_type(ada, 'agent_talk')[0]['lines']) == 3


def test_queued_agent_speech_and_welcome_recheck_current_policy():
    sock = FakeSock()
    player = Player('Ada', 382, 'root', 'a', sock, participant_id='a' * 32)
    room = get_room(382)
    agent_enter(room, 'Tessera', 'tender')
    player.send_lock.acquire()
    player.start_writer()
    try:
        player.send({'type': 'agent_talk', 'a': 'Tessera', 'b': 'Vex',
                     'lines': [{'speaker': 'Tessera', 'line': 'Already queued.'}]})
        assert _wait_for(lambda: player.outbox.empty())
        player.send({'type': 'welcome', 'agents': agents_snapshot(room), 'players': []})
        player.set_blocks([{'id': 'agent:Tessera', 'name': 'Tessera'}])
    finally:
        player.send_lock.release()
    player.send({'type': 'pong'})
    assert _wait_for(lambda: len(sock.sent) == 2)
    from tests.test_ws_credential_lifetime import _read_frame
    class BytesSocket:
        def __init__(self, data):
            self.data = data
        def recv(self, n):
            result, self.data = self.data[:n], self.data[n:]
            return result
    welcome = json.loads(_read_frame(BytesSocket(sock.sent[0]))[1])
    assert welcome['type'] == 'welcome' and welcome['agents'] == []
    player.stop_writer()
    player._writer.join(2)


def _sent_messages(sock):
    from tests.test_ws_credential_lifetime import _read_frame

    class BytesSocket:
        def __init__(self, data):
            self.data = data

        def recv(self, n):
            result, self.data = self.data[:n], self.data[n:]
            return result

    return [json.loads(_read_frame(BytesSocket(frame))[1]) for frame in sock.sent]


def test_delayed_writer_preserves_each_block_change_but_refreshes_welcome():
    from server.rooms import sync_blocks

    room = get_room(382)
    player = Player('Ada', 382, 'root', 'a', FakeSock(), participant_id='a' * 32)
    target = Player('Bea', 382, 'root', 'b', FakeSock(), participant_id='b' * 32)
    room.players.update(a=player, b=target)
    player.send_lock.acquire()
    player.start_writer()
    try:
        player.send({'type': 'welcome', 'players': snapshot(room)})
        assert _wait_for(lambda: player.outbox.empty())
        sync_blocks(player.participant_id, [{'id': target.participant_id, 'name': 'Bea'}])
        sync_blocks(player.participant_id, [])
    finally:
        player.send_lock.release()
    try:
        assert _wait_for(lambda: len(player.sock.sent) == 3)
        welcome, blocked, unblocked = _sent_messages(player.sock)
        assert welcome['type'] == 'welcome' and welcome['blocks'] == []
        assert blocked['type'] == unblocked['type'] == 'blocks_changed'
        assert blocked['blocks'] == [
            {'id': handle(player.participant_id, target.participant_id), 'name': 'Bea'}]
        assert unblocked['blocks'] == []
        assert [p['name'] for p in blocked['players']] == ['Ada']
        assert [p['name'] for p in unblocked['players']] == ['Ada', 'Bea']
    finally:
        player.stop_writer()
        player._writer.join(2)


def test_agent_broadcast_enriches_once_for_all_recipients_and_queued_delivery(monkeypatch):
    import server.rooms as rooms

    calls = []
    original = rooms.agent_target

    def counted(name):
        calls.append(name)
        return original(name)

    monkeypatch.setattr(rooms, 'agent_target', counted)
    room = get_room(382)
    players = [Player(name, 382, 'root', name, FakeSock(), participant_id=name * 32)
               for name in ('a', 'b', 'c')]
    players[0].set_blocks([{'id': 'agent:Tessera', 'name': 'Tessera'}])
    for player in players:
        room.players[player.session_id] = player
        player.start_writer()
    exchange = {'type': 'agent_talk', 'a': 'Tessera', 'b': 'Vex',
                'lines': [{'speaker': 'Tessera', 'line': 'One.'},
                          {'speaker': 'Vex', 'line': 'Two.'}]}
    try:
        broadcast(room, exchange)
        assert _wait_for(lambda: all(len(p.sock.sent) == 1 for p in players))
        assert sorted(calls) == ['Tessera', 'Vex']
        filtered = _sent_messages(players[0].sock)[0]
        assert 'a' not in filtered and filtered['b'] == 'Vex'
        assert [line['speaker'] for line in filtered['lines']] == ['Vex']
        for player in players[1:]:
            assert len(_sent_messages(player.sock)[0]['lines']) == 2
        assert all('participant_id' not in line for line in exchange['lines'])
    finally:
        for player in players:
            player.stop_writer()
            player._writer.join(2)
