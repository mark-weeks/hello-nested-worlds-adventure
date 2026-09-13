"""An HTTP retry returns its committed receipt; distinct intentions stay distinct."""
import hashlib
import json
import re

import persistence as db


def execute(participant: str, seed: int, operation: str, request_id: str,
            payload: dict, apply):
    if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", request_id):
        raise ValueError("Supply a stable request identifier of 8–80 letters, digits, '_' or '-'.")
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    with db.transaction() as conn:
        key = (participant, seed, operation, request_id)
        row = conn.execute("""SELECT fingerprint,response FROM request_receipts
            WHERE participant_id=? AND world_seed=? AND operation=? AND request_id=?""", key).fetchone()
        if row:
            if row[0] != fingerprint:
                raise ValueError("That request identifier belongs to a different action.")
            return json.loads(row[1]), True
        response = apply()
        conn.execute("""INSERT INTO request_receipts
            (participant_id,world_seed,operation,request_id,fingerprint,response) VALUES (?,?,?,?,?,?)""",
            (*key, fingerprint, json.dumps(response)))
        return response, False
