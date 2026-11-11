"""Operational notice acknowledgements, separate from world history."""
from __future__ import annotations

import hashlib

import persistence as db
from persistence import participants


def accepted(key: str, revision: str) -> bool:
    """Read a live credential's acknowledgement without enrolling it.

    A missing, revoked or sanctioned credential is refused even if it once
    accepted. Metadata reads do not create participant or consent rows.
    """
    if not key:
        raise participants.Unauthorized("A current personal invite is required.")
    digest = db._credential_digest(key)
    db.init_db()
    with db._connection() as conn:
        if not conn.execute(participants._LIVE_INVITE, (digest,)).fetchone():
            raise participants.Unauthorized("A current personal invite is required.")
        return conn.execute("""SELECT 1 FROM participation_consents c
            JOIN participant_credentials k ON k.participant_id=c.participant_id
            WHERE k.credential_digest=? AND c.revision=?""", (digest, revision)).fetchone() is not None


def accept(key: str, revision: str, notice_json: str) -> None:
    """Validate and acknowledge under the same write lock, idempotently."""
    if not key:
        raise participants.Unauthorized("A current personal invite is required.")
    if hashlib.sha256(notice_json.encode()).hexdigest() != revision:
        raise ValueError("The notice snapshot does not match its revision.")
    digest = db._credential_digest(key)
    with db.transaction() as conn:
        # A revocation or rotation between an earlier metadata read and
        # this submission cannot acknowledge on the old credential.
        if not conn.execute(participants._LIVE_INVITE, (digest,)).fetchone():
            raise participants.Unauthorized("A current personal invite is required.")
        owner = participants._ensure(conn, digest)
        conn.execute("""INSERT INTO participation_consents(participant_id,revision,notice_json)
            VALUES (?,?,?) ON CONFLICT(participant_id,revision) DO NOTHING""", (owner, revision, notice_json))
