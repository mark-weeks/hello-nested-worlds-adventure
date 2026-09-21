"""An HTTP retry returns its committed receipt; distinct intentions stay distinct.

Every reply is a receipt, including a quiet one given while the interpreter
was unavailable: a same-ID retry returns it without another model call, so a
negative answer can never race a later acceptance of the same request. A
later try is a new request ID (ADR-028).
"""
import hashlib
import json
import re

import persistence as db


def _fingerprint(request_id, payload):
    if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", request_id):
        raise ValueError("Supply a stable request identifier of 8–80 letters, digits, '_' or '-'.")
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _find(conn, key, fingerprint):
    row = conn.execute("""SELECT fingerprint,response FROM request_receipts
        WHERE participant_id=? AND world_seed=? AND operation=? AND request_id=?""", key).fetchone()
    if row is None:
        return None
    if row[0] != fingerprint:
        raise ValueError("That request identifier belongs to a different action.")
    return row[1]  # Keep a stored JSON null distinct from no row.


def lookup(participant, seed, operation, request_id, payload):
    """Recover before any model call; execute rechecks under the writer lock."""
    fingerprint = _fingerprint(request_id, payload)
    with db._connection() as conn:
        response = _find(conn, (participant, seed, operation, request_id), fingerprint)
        return json.loads(response) if response is not None else None


def execute(participant: str, seed: int, operation: str, request_id: str,
            payload: dict, apply):
    fingerprint = _fingerprint(request_id, payload)
    with db.transaction() as conn:
        key = (participant, seed, operation, request_id)
        response = _find(conn, key, fingerprint)
        if response is not None:
            return json.loads(response), True
        response = apply()
        conn.execute("""INSERT INTO request_receipts
            (participant_id,world_seed,operation,request_id,fingerprint,response) VALUES (?,?,?,?,?,?)""",
            (*key, fingerprint, json.dumps(response)))
        return response, False
