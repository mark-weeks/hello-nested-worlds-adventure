"""Day-one recording: presence lifecycle, puzzle attempts, agent-voice
exchanges — the chronicle material that can never be backfilled — plus the
wanderer-name reservation and creation timestamps.
"""
from __future__ import annotations

import base64
import json
import os
import socket
import sqlite3
import threading
import time
import urllib.error
import urllib.request

import pytest

import persistence
from consciousness import WANDERER_CAST
from multiverse.generator import generate_node_hierarchy
from server.rooms import clear_rooms
from tests.test_server_protocol import _client_frame


@pytest.fixture(autouse=True)
def _zero_hop_delay(monkeypatch):
    monkeypatch.setenv("NESTED_WORLDS_HOP_DELAY", "0")
    yield


@pytest.fixture()
def srv():
    from server import _Handler, _ThreadedServer
    server = _ThreadedServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield port
    server.shutdown()


def _ws_connect(port: int, seed: int, name: str, invite_key: str | None = None):
    """Minimal real WebSocket client: upgrade + return (socket, status line)."""
    s = socket.create_connection(("127.0.0.1", port), timeout=5)
    key = base64.b64encode(os.urandom(16)).decode()
    path = f"/ws?seed={seed}&name={name}"
    if invite_key is not None:
        path += f"&key={invite_key}"
    s.sendall((
        f"GET {path} HTTP/1.1\r\nHost: t\r\n"
        "Upgrade: websocket\r\nConnection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
    ).encode())
    head = b""
    while b"\r\n\r\n" not in head:
        chunk = s.recv(4096)
        if not chunk:
            break
        head += chunk
    return s, head.split(b"\r\n", 1)[0]


def _ws_send_json(s: socket.socket, msg: dict) -> None:
    s.sendall(_client_frame(json.dumps(msg).encode()))


def _wait_for_rows(seed, node, mtype, n=1, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        rows = [h for h in persistence.get_node_history(seed, node, 50)
                if h["type"] == mtype]
        if len(rows) >= n:
            return rows
        time.sleep(0.02)
    return [h for h in persistence.get_node_history(seed, node, 50)
            if h["type"] == mtype]


class TestPresenceLifecycle:
    def test_join_move_chat_leave_all_persist(self, srv):
        seed = 251
        root_name = generate_node_hierarchy(seed=seed, max_depth=1).name
        s, status = _ws_connect(srv, seed, "Ada")
        assert b"101" in status

        # Chat BEFORE any move — previously silently dropped.
        _ws_send_json(s, {"type": "chat", "text": "first words"})
        chats = _wait_for_rows(seed, root_name, "PLAYER_CHAT")
        assert chats and chats[0]["data"]["text"] == "first words"

        # Join was recorded at the root, attributed.
        joins = _wait_for_rows(seed, root_name, "PLAYER_JOIN")
        assert joins and joins[0]["player"] == "Ada"

        # A move leaves a trail at the destination.
        target = generate_node_hierarchy(seed=seed, max_depth=2).children[0]
        _ws_send_json(s, {"type": "move", "node": target.name})
        moves = _wait_for_rows(seed, target.name, "PLAYER_MOVE")
        assert moves and moves[0]["player"] == "Ada"

        # Departure persists at the last known node.
        s.close()
        leaves = _wait_for_rows(seed, target.name, "PLAYER_LEAVE")
        assert leaves and leaves[0]["player"] == "Ada"

    def test_moves_feed_the_activity_counts(self, srv):
        seed = 252
        target = generate_node_hierarchy(seed=seed, max_depth=2).children[0]
        s, _ = _ws_connect(srv, seed, "Bee")
        _ws_send_json(s, {"type": "move", "node": target.name})
        _wait_for_rows(seed, target.name, "PLAYER_MOVE")
        counts = persistence.count_mutations_by_node(seed)
        assert counts.get(target.name, 0) >= 1
        s.close()


class TestReservedNames:
    def test_ws_join_as_a_wanderer_is_refused(self, srv):
        cast_name = WANDERER_CAST[0]
        s, status = _ws_connect(srv, 253, cast_name)
        assert b"403" in status
        s.close()

    def test_body_player_name_is_stripped_to_anonymous(self):
        from server.handlers import _parse_player_name
        assert _parse_player_name({"player_name": WANDERER_CAST[0]}) is None
        assert _parse_player_name({"player_name": WANDERER_CAST[0].lower()}) is None
        assert _parse_player_name({"player_name": "Ada"}) == "Ada"
        assert _parse_player_name({}) is None

    def test_ws_join_whitespace_wanderer_now_refused(self, srv):
        # A leading space once slipped a cast name past the WS reserved-name
        # check (cap-then-lower, no strip). The WS path now trims first, so a
        # "%20Tessera" join normalizes to the reserved name and is refused.
        s, status = _ws_connect(srv, 255, "%20" + WANDERER_CAST[0])
        assert b"403" in status
        s.close()

    def test_normalize_client_name_trims_before_reserved_check(self):
        from server.handlers import _normalize_client_name
        assert _normalize_client_name(" " + WANDERER_CAST[0] + " ") is None
        assert _normalize_client_name("  Ada  ") == "Ada"
        assert _normalize_client_name("") is None
        assert _normalize_client_name(None) is None


class TestUniqueNames:
    """ADR-004 §7: a per-user invite key carries a registered, unique name;
    the server uses it and ignores any client-supplied name, and a keyed
    session is never anonymous. The only keyless path is ungated local dev,
    which falls back to the normalized client name."""

    def test_registered_name_is_authoritative_over_client_name(self):
        import server.guard as guard
        from server.handlers import _display_name
        persistence.mint_invite_key("nw_alice", "Alice")
        assert guard.registered_name("nw_alice") == "Alice"
        # A keyed request uses the registered name, ignoring the client's —
        # this is what makes the name unique and unimpersonatable.
        assert _display_name("nw_alice", "Zorg") == "Alice"
        # ...and is never anonymous, even when the client sends no name.
        assert _display_name("nw_alice", None) == "Alice"

    def test_dev_and_keyless_fall_back_to_client_name(self):
        from server.handlers import _display_name
        # Unknown / empty key → ungated-dev path: normalized client name,
        # which may be None (keyless local dev is the one place a session can
        # be nameless; it never reaches real, gated play).
        assert _display_name("", "Ada") == "Ada"
        assert _display_name("not-a-real-key", "Ada") == "Ada"
        assert _display_name("", None) is None

    def test_registered_name_none_for_revoked_key(self):
        import server.guard as guard
        persistence.mint_invite_key("nw_bob", "Bob")
        persistence.revoke_invite_key("nw_bob")
        assert guard.registered_name("nw_bob") is None


class TestNoAnonymousGameplay:
    """ADR-004 §7: with the gate active (a per-user key minted) there is no
    anonymous presence. A keyless request — HTTP or WebSocket — is refused, and
    a keyed session is recorded under its registered name, never a client-chosen
    or empty one. Removing the shared key is what closes the old anonymous path:
    a single shared credential once let many players in under one identity, or
    with no name at all."""

    def test_gate_active_refuses_keyless_ws_join(self, srv):
        # A key is minted → the gate is up → a join with no ?key= is refused
        # before any presence can be recorded.
        persistence.mint_invite_key("nw_named", "Named")
        s, status = _ws_connect(srv, 261, "Ghost")
        assert b"403" in status
        s.close()

    def test_gate_active_refuses_keyless_http(self, srv):
        persistence.mint_invite_key("nw_named", "Named")
        req = urllib.request.Request(f"http://127.0.0.1:{srv}/worlds")
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(req)
        assert exc.value.code == 403

    def test_keyed_ws_join_records_registered_name_over_client_name(self, srv):
        seed = 262
        persistence.mint_invite_key("nw_real", "Aurelia")
        root_name = generate_node_hierarchy(seed=seed, max_depth=1).name
        # Client sends "Zorg" AND a valid key: the registered name wins.
        s, status = _ws_connect(srv, seed, "Zorg", invite_key="nw_real")
        assert b"101" in status
        _ws_send_json(s, {"type": "chat", "text": "hello"})
        joins = _wait_for_rows(seed, root_name, "PLAYER_JOIN")
        assert joins and joins[0]["player"] == "Aurelia"
        assert joins[0]["player"] != "Zorg"
        s.close()


def _post_register(port: int, payload: dict) -> tuple[int, dict]:
    """POST /register without raising on 4xx; returns (status, json body)."""
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/register",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


class TestSelfServiceRegistration:
    """ADR-004 §7 self-service, invite-gated: the operator shares a
    single-use /register?invite=<token> link; the PLAYER picks their own
    unique name and redemption mints their per-user play key. No token, no
    account — the beta stays a closed cohort even though the page and the
    POST are reachable without a play key."""

    def test_register_surface_reachable_while_gate_active(self, srv):
        # Gate up (a key exists) — the registration page still loads, like
        # the UI shell: the registrant has no play key yet.
        persistence.mint_invite_key("nw_named", "Named")
        req = urllib.request.Request(f"http://127.0.0.1:{srv}/register")
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200

    def test_register_logic_is_external_and_served_under_the_csp(self, srv):
        # The page is served under CSP script-src 'self' (no unsafe-inline),
        # which blocks inline <script> blocks wholesale — the whole
        # registration flow silently died that way once (2026-07-19 ensemble
        # evaluation). The logic must live in an external file the server
        # actually serves, ungated like its page; the page must reference it
        # and carry no inline script for the CSP to strangle.
        persistence.mint_invite_key("nw_named", "Named")  # gate up
        with urllib.request.urlopen(
                f"http://127.0.0.1:{srv}/register.js") as resp:
            assert resp.status == 200
            assert "javascript" in resp.headers.get("Content-Type", "")
            body = resp.read().decode()
        assert "getElementById('form')" in body  # the submit wiring shipped
        with urllib.request.urlopen(
                f"http://127.0.0.1:{srv}/register") as resp:
            csp = resp.headers.get("Content-Security-Policy", "")
            html = resp.read().decode()
        assert "script-src 'self'" in csp and "unsafe-inline" not in csp.split(
            "style-src")[0]  # style may be inline; script must not
        assert '<script src="/register.js" defer></script>' in html
        import re
        assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", html), (
            "register.html must carry no inline script — the CSP blocks it")

    def test_full_flow_register_then_play_under_chosen_name(self, srv):
        # The crown path: token → chosen name → minted key → that key
        # authorizes play and the chronicle records the CHOSEN name, even
        # when the client tries to join as someone else.
        seed = 263
        persistence.mint_invite_key("nw_named", "Named")  # gate up
        persistence.create_registration_token("nwr_live")
        status, data = _post_register(
            srv, {"invite": "nwr_live", "name": "Priya"})
        assert status == 200
        key = data["key"]
        assert key.startswith("nw_") and data["url"].startswith("/?key=")

        root_name = generate_node_hierarchy(seed=seed, max_depth=1).name
        s, ws_status = _ws_connect(srv, seed, "Zorg", invite_key=key)
        assert b"101" in ws_status
        _ws_send_json(s, {"type": "chat", "text": "first words"})
        joins = _wait_for_rows(seed, root_name, "PLAYER_JOIN")
        assert joins and joins[0]["player"] == "Priya"
        s.close()

    def test_taken_name_is_409_and_the_token_survives_for_a_retry(self, srv):
        persistence.mint_invite_key("nw_ada", "Ada")
        persistence.create_registration_token("nwr_live")
        status, data = _post_register(
            srv, {"invite": "nwr_live", "name": "  ada "})
        assert status == 409
        assert "choose another" in data["error"]
        # Same invite, different name → in.
        status, _ = _post_register(
            srv, {"invite": "nwr_live", "name": "Adjacent"})
        assert status == 200

    def test_invalid_and_spent_tokens_refused_alike(self, srv):
        persistence.create_registration_token("nwr_live")
        assert _post_register(
            srv, {"invite": "nwr_live", "name": "Aster"})[0] == 200
        # Spent and never-existed read identically (no oracle).
        s1, d1 = _post_register(srv, {"invite": "nwr_live", "name": "Briar"})
        s2, d2 = _post_register(srv, {"invite": "nwr_fake", "name": "Briar"})
        assert (s1, d1["error"]) == (s2, d2["error"]) == (403, "this invite is not valid")
        # Nothing was minted for the refused attempts.
        assert persistence.lookup_invite_key("k_b") is None

    def test_reserved_and_missing_names_refused_token_kept(self, srv):
        persistence.create_registration_token("nwr_live")
        status, data = _post_register(
            srv, {"invite": "nwr_live", "name": WANDERER_CAST[0]})
        assert status == 403 and "belongs to the world" in data["error"]
        assert _post_register(srv, {"invite": "nwr_live", "name": ""})[0] == 400
        assert _post_register(
            srv, {"invite": "nwr_live", "name": "x" * 33})[0] == 400
        # None of those consumed the invite.
        assert persistence.lookup_registration_token("nwr_live") is not None


class TestPuzzleAttempts:
    def _attempt(self, port, seed, node, answer, name="Ada"):
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/puzzle/attempt",
            data=json.dumps({"seed": seed, "depth": 6, "node_name": node,
                             "answer": answer, "player_name": name}).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())

    def test_every_guess_is_recorded(self, srv):
        seed = 254
        target = generate_node_hierarchy(seed=seed, max_depth=6).children[0]
        self._attempt(srv, seed, target.name, "wrong one")
        self._attempt(srv, seed, target.name, "wrong two", name="Bee")
        rows = [h for h in persistence.get_node_history(seed, target.name, 50)
                if h["type"] == "PUZZLE_ATTEMPT"]
        assert len(rows) == 2
        assert {r["player"] for r in rows} == {"Ada", "Bee"}
        assert all(r["data"]["correct"] is False for r in rows)

    def test_attempt_counter_survives_a_restart(self, srv):
        seed = 255
        target = generate_node_hierarchy(seed=seed, max_depth=6).children[0]
        first = self._attempt(srv, seed, target.name, "wrong one")
        assert first["attempt"] == 1
        # Simulate a deploy: all in-memory rooms (and their PuzzleSessions)
        # are gone; the pooled counter must rehydrate from the attempt log.
        clear_rooms()
        second = self._attempt(srv, seed, target.name, "wrong two", name="Bee")
        assert second["attempt"] == 2, "a deploy must not refund attempts"
        assert "Ada" in second["contributors"]


class TestAgentVoiceRecording:
    def test_exchange_persists_into_node_memory(self, srv, monkeypatch):
        import consciousness
        monkeypatch.setattr(
            consciousness, "voice_agent",
            lambda *a, **k: "The dust remembers your question.")
        seed = 256
        target = generate_node_hierarchy(seed=seed, max_depth=2).children[0]
        req = urllib.request.Request(
            f"http://127.0.0.1:{srv}/agent/voice",
            data=json.dumps({"seed": seed, "node_name": target.name,
                             "agent_name": "Tessera", "message": "who passed?",
                             "player_name": "Ada"}).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
        assert data["ai"] is True

        rows = [h for h in persistence.get_node_history(seed, target.name, 50)
                if h["type"] == "AGENT_VOICE"]
        assert len(rows) == 1
        assert rows[0]["player"] == "Ada"
        assert rows[0]["data"]["agent"] == "Tessera"
        assert "dust remembers" in rows[0]["data"]["reply"]

    def test_node_voice_renders_it_as_witnessed_not_spoken(self):
        from consciousness import _history_block
        block = _history_block([{
            "type": "AGENT_VOICE", "player": "Ada", "at": "2026-07-05 01:00:00",
            "data": {"agent": "Tessera", "message": "who passed?",
                     "reply": "Many. Few mattered."},
        }])
        assert "Ada spoke with Tessera here" in block
        assert 'Tessera answered: "Many. Few mattered."' in block
        assert "you answered" not in block  # the node must not claim the reply


class TestCreationTimestamps:
    def test_new_rows_carry_created_at(self):
        persistence.save_agent_memory("TS-Agent", 257, ["a"], [])
        persistence.increment_ripple_score(257, "TS-Node", 0.1)
        with sqlite3.connect(persistence._DB_PATH) as conn:
            am = conn.execute(
                "SELECT created_at FROM agent_memory WHERE agent_name='TS-Agent'"
            ).fetchone()
            nr = conn.execute(
                "SELECT created_at FROM node_runtime_state WHERE node_name='TS-Node'"
            ).fetchone()
        assert am and am[0]
        assert nr and nr[0]

    def test_updates_preserve_the_birth_timestamp(self):
        persistence.save_agent_memory("TS-Keep", 258, ["a"], [])
        with sqlite3.connect(persistence._DB_PATH) as conn:
            born = conn.execute(
                "SELECT created_at FROM agent_memory WHERE agent_name='TS-Keep'"
            ).fetchone()[0]
        persistence.save_agent_memory("TS-Keep", 258, ["a", "b"], [])
        with sqlite3.connect(persistence._DB_PATH) as conn:
            after = conn.execute(
                "SELECT created_at FROM agent_memory WHERE agent_name='TS-Keep'"
            ).fetchone()[0]
        assert after == born
