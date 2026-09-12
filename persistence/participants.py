"""Participant ownership separate from credentials and immutable world history."""
from __future__ import annotations

import json
import secrets

import persistence as db

AVATARS = ("lantern", "leaf", "star", "river")


class Unauthorized(ValueError):
    pass


def _ensure(conn, digest):
    row = conn.execute(
        "SELECT participant_id FROM participant_credentials WHERE credential_digest=?",
        (digest,)).fetchone()
    if row:
        return row[0]
    participant = secrets.token_hex(16)
    conn.execute("INSERT INTO participants(id) VALUES (?)", (participant,))
    conn.execute("""INSERT INTO participant_credentials
        (credential_digest, participant_id, actor_identity) VALUES (?, ?, ?)""",
        (digest, participant, digest[:16]))
    return participant


_LIVE_INVITE = "SELECT name FROM invite_keys WHERE key=? AND revoked_at IS NULL"


def identify(key: str) -> dict:
    """Always require a live invite, including in otherwise ungated local mode.

    Every authenticated read (situation polls, act pre-flight, journal,
    profile) passes through here, so the steady state must not queue behind
    the single SQLite writer: a known credential is resolved on a plain
    connection, and the write transaction is entered only on first use.
    """
    if not key:
        raise Unauthorized("A current personal invite is required.")
    digest = db._credential_digest(key)
    db.init_db()
    with db._connection() as conn:
        row = conn.execute(_LIVE_INVITE, (digest,)).fetchone()
        if not row:
            raise Unauthorized("A current personal invite is required.")
        known = conn.execute(
            "SELECT participant_id FROM participant_credentials WHERE credential_digest=?",
            (digest,)).fetchone()
    if known:
        return {"id": known[0], "name": row[0]}
    with db.transaction() as conn:
        # Re-read under the write lock: a revocation may have landed between reads.
        row = conn.execute(_LIVE_INVITE, (digest,)).fetchone()
        if not row:
            raise Unauthorized("A current personal invite is required.")
        participant = _ensure(conn, digest)
    return {"id": participant, "name": row[0]}


def rotate(credential: str, replacement: str) -> dict:
    """Operator-only replacement, by secret or unique digest prefix; atomic."""
    if not replacement.startswith("nw_") or len(replacement) < 35:
        raise ValueError("Replacement must be a newly generated personal key.")
    with db.transaction() as conn:
        digest = db._credential_digest(credential)
        rows = conn.execute("SELECT key, name FROM invite_keys WHERE key=? AND revoked_at IS NULL",
                            (digest,)).fetchall()
        prefix = credential.strip().rstrip("…")
        if not rows and len(prefix) >= 12 and all(c in "0123456789abcdef" for c in prefix):
            rows = conn.execute("""SELECT key, name FROM invite_keys
                WHERE key LIKE ? AND revoked_at IS NULL""", (prefix + "%",)).fetchall()
        if len(rows) != 1:
            raise ValueError("No single active credential matched; nothing changed.")
        digest, name = rows[0]
        participant = _ensure(conn, digest)
        new_digest = db._credential_digest(replacement)
        # Never merge independently issued accounts or resurrect an old alias.
        if conn.execute("SELECT 1 FROM participant_credentials WHERE credential_digest=?",
                        (new_digest,)).fetchone():
            raise ValueError("Replacement credential has already been used.")
        conn.execute("""INSERT INTO participant_credentials
            (credential_digest, participant_id, actor_identity) VALUES (?, ?, ?)""",
            (new_digest, participant, new_digest[:16]))
        conn.execute(f"UPDATE participant_credentials SET replaced_at={db._NOW} WHERE credential_digest=?",
                     (digest,))
        # Resume, name and budget configuration stay on the same operational row.
        conn.execute("UPDATE invite_keys SET key=? WHERE key=?", (new_digest, digest))
    return {"id": participant, "name": name}


def actor_aliases(identity: str) -> list[str]:
    """Explicit operator-established lineage only; no display-name inference."""
    db.init_db()
    with db._connection() as conn:
        owners = conn.execute("""SELECT DISTINCT participant_id FROM participant_credentials
            WHERE actor_identity=?""", (identity,)).fetchall()
        if len(owners) != 1:
            return [identity]
        return [r[0] for r in conn.execute("""SELECT actor_identity FROM participant_credentials
            WHERE participant_id=? ORDER BY created_at, credential_digest""", (owners[0][0],))]


def profile(participant: str, *, owner=False) -> dict:
    db.init_db()
    with db._connection() as conn:
        row = conn.execute("""SELECT bio, goals, avatar, published, home_seed, home_node
            FROM participant_profiles WHERE participant_id=?""", (participant,)).fetchone()
        name = conn.execute("""SELECT i.name FROM invite_keys i JOIN participant_credentials c
            ON c.credential_digest=i.key WHERE c.participant_id=? AND i.revoked_at IS NULL LIMIT 1""",
            (participant,)).fetchone()
    if not name:
        raise ValueError("That profile is unavailable.")
    result = {"id": participant, "name": name[0], "bio": "", "goals": "",
              "avatar": "lantern", "published": False}
    if row and (owner or row[3]):
        result.update(bio=row[0], goals=row[1], avatar=row[2], published=bool(row[3]))
    if owner:
        result["home"] = {"seed": row[4], "node": row[5]} if row and row[5] else None
    return result


def save_profile(participant: str, data: dict) -> dict:
    bio, goals = data.get("bio", ""), data.get("goals", "")
    avatar, published = data.get("avatar", "lantern"), data.get("published", False)
    if not isinstance(bio, str) or len(bio) > 500 or not isinstance(goals, str) or len(goals) > 500:
        raise ValueError("Bio and goals may each contain up to 500 characters.")
    if avatar not in AVATARS or not isinstance(published, bool):
        raise ValueError("Choose an available avatar and profile visibility.")
    with db.transaction() as conn:
        conn.execute(f"""INSERT INTO participant_profiles(participant_id,bio,goals,avatar,published)
            VALUES (?,?,?,?,?) ON CONFLICT(participant_id) DO UPDATE SET
            bio=excluded.bio,goals=excluded.goals,avatar=excluded.avatar,
            published=excluded.published,updated_at={db._NOW}""",
            (participant, bio, goals, avatar, int(published)))
    return profile(participant, owner=True)


def set_home(participant: str, seed: int, node: str | None):
    with db.transaction() as conn:
        conn.execute(f"""INSERT INTO participant_profiles(participant_id,home_seed,home_node)
            VALUES (?,?,?) ON CONFLICT(participant_id) DO UPDATE SET
            home_seed=excluded.home_seed,home_node=excluded.home_node,updated_at={db._NOW}""",
            (participant, seed if node else None, node))


def notes(participant: str, seed: int) -> list[dict]:
    db.init_db()
    with db._connection() as conn:
        rows = conn.execute("""SELECT id,node_name,text,updated_at FROM journal_notes
            WHERE participant_id=? AND world_seed=? ORDER BY updated_at DESC,id LIMIT 100""",
            (participant, seed)).fetchall()
    return [dict(zip(("id", "node", "text", "updated_at"), row)) for row in rows]


def save_note(participant: str, seed: int, node: str, text: str, note_id: str) -> None:
    if not isinstance(text, str) or len(text) > 2000:
        raise ValueError("A note may contain up to 2,000 characters.")
    if not isinstance(note_id, str) or not 8 <= len(note_id) <= 80:
        raise ValueError("A stable note identifier is required.")
    with db.transaction() as conn:
        existing = conn.execute("SELECT participant_id,world_seed FROM journal_notes WHERE id=?",
                                (note_id,)).fetchone()
        if existing and existing != (participant, seed):
            raise ValueError("That note is unavailable.")
        if not text.strip():
            conn.execute("DELETE FROM journal_notes WHERE id=? AND participant_id=?", (note_id, participant))
            return
        count = conn.execute("SELECT COUNT(*) FROM journal_notes WHERE participant_id=? AND world_seed=?",
                             (participant, seed)).fetchone()[0]
        if not existing and count >= 100:
            raise ValueError("This journal holds 100 notes. Edit or remove one first.")
        conn.execute(f"""INSERT INTO journal_notes(id,participant_id,world_seed,node_name,text)
            VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
            node_name=excluded.node_name,text=excluded.text,updated_at={db._NOW}""",
            (note_id, participant, seed, node, text))


def recap(participant: str, seed: int) -> list[dict]:
    """Recent consequences at saved places or explicitly joined situations; no note text."""
    db.init_db()
    with db._connection() as conn:
        rows = conn.execute("""SELECT id,node_name,mutation_type,data FROM world_mutations
            WHERE world_seed=? AND delta IS NOT NULL AND node_name IN (
                SELECT node_name FROM journal_notes WHERE participant_id=? AND world_seed=?
                UNION SELECT home_node FROM participant_profiles WHERE participant_id=? AND home_seed=?
                UNION SELECT DISTINCT m.node_name FROM world_mutations m JOIN situations s
                  ON json_extract(m.data,'$.situation')=s.id JOIN situation_discoveries d ON d.situation_id=s.id
                  WHERE d.participant_id=? AND s.world_seed=? AND m.world_seed=?)
            ORDER BY id DESC LIMIT 8""", (seed, participant, seed, participant, seed, participant, seed, seed)).fetchall()
    projected = {r['id']: r for r in db.presented_mutations(seed, [row[0] for row in rows])}
    return [{"event_id": row[0], "node": row[1],
             "text": projected.get(row[0], {}).get("narration", {}).get("text")
                 or json.loads(row[3]).get("flavor") or "A recorded change reached this place."}
            for row in rows]



def has_visited(participant, seed, node):
    db.init_db()
    with db._connection() as conn:
        return bool(conn.execute("""SELECT 1 FROM invite_keys i JOIN participant_credentials c
            ON c.credential_digest=i.key WHERE c.participant_id=? AND i.last_seed=? AND i.last_node=?
            UNION SELECT 1 FROM world_mutations m JOIN participant_credentials c
            ON c.actor_identity=m.actor_identity WHERE c.participant_id=? AND m.world_seed=?
            AND m.node_name=? AND m.mutation_type IN ('PLAYER_MOVE','PLAYER_JOIN') LIMIT 1""",
            (participant, seed, node, participant, seed, node)).fetchone())
