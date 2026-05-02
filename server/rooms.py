"""Multiplayer room state for the nested-worlds server.

A room is keyed by world seed; each connected WebSocket player is a `Player`.
Broadcasting handles per-socket failures by evicting dead players.
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field

from server.protocol import ws_send


@dataclass
class Player:
    name: str
    seed: int
    current_node: str
    session_id: str
    sock: object
    _lock: threading.Lock = field(default_factory=threading.Lock, compare=False, repr=False)

    def send(self, msg: dict) -> bool:
        try:
            with self._lock:
                ws_send(self.sock, json.dumps(msg))
            return True
        except OSError:
            return False


@dataclass
class Room:
    players: dict = field(default_factory=dict)   # session_id → Player
    lock: threading.Lock = field(default_factory=threading.Lock, compare=False, repr=False)


_rooms: dict[int, Room] = {}
_rooms_lock = threading.Lock()


def get_room(seed: int) -> Room:
    with _rooms_lock:
        if seed not in _rooms:
            _rooms[seed] = Room()
        return _rooms[seed]


def broadcast(room: Room, msg: dict, exclude: str | None = None) -> None:
    with room.lock:
        targets = list(room.players.items())
    failed = []
    for sid, player in targets:
        if sid == exclude:
            continue
        if not player.send(msg):
            failed.append(sid)
    if failed:
        with room.lock:
            for sid in failed:
                room.players.pop(sid, None)


def snapshot(room: Room) -> list[dict]:
    with room.lock:
        return [{"name": p.name, "node": p.current_node, "session_id": p.session_id}
                for p in room.players.values()]
