"""Bounded, read-only provenance. Never search for a source by actor or time."""
import json

from multiverse.history import narrate


FIELDS = "id, node_name, mutation_type, player_name, data, recorded_at, delta, node_version"


def data_of(entry):
    return entry["data"] if isinstance(entry.get("data"), dict) else {}


def decode(row):
    return {"id": row[0], "node": row[1], "type": row[2], "player": row[3],
            "data": json.loads(row[4]) if row[4] else {}, "at": row[5],
            "delta": json.loads(row[6]) if row[6] else None, "node_version": row[7]}


def positive_id(value):
    return value if type(value) is int and value > 0 else None


def project(conn, seed, entries):
    # Public endpoints page at <=200. Internal image history permits 1000;
    # chunk that bounded read rather than exceeding SQLite's parameter limit.
    for offset in range(0, len(entries), 200):
        _project_page(conn, seed, entries[offset:offset + 200])
    return entries


def _project_page(conn, seed, entries):
    work = {}
    refs = {}
    for entry in entries:
        data = data_of(entry)
        ref = data.get("delivery")
        if isinstance(ref, dict) and ref.get("queue") in ("causal_queue", "verb_maturation"):
            work_id = positive_id(ref.get("id"))
            if work_id:
                refs.setdefault(ref["queue"], set()).add(work_id)
    for queue, ids in refs.items():
        # Queue names come only from the closed allowlist above.
        kind = "kind" if queue == "causal_queue" else "verb"
        placeholders = ",".join("?" for _ in ids)
        rows = conn.execute(
            f"SELECT id, node_name, {kind}, source_event_id FROM {queue} "
            f"WHERE world_seed=? AND id IN ({placeholders})", (seed, *ids)).fetchall()
        work.update({(queue, r[0]): r for r in rows})

    candidates = []
    source_ids = set()
    for entry in entries:
        data = data_of(entry)
        direct = positive_id(data.get("source_event_id"))
        ref = data.get("delivery")
        linked = None
        conflict = False
        if isinstance(ref, dict) and ref.get("queue") in ("causal_queue", "verb_maturation"):
            row = work.get((ref.get("queue"), positive_id(ref.get("id"))))
            if row:
                expected = (entry["type"] if ref["queue"] == "causal_queue"
                            else data.get("verb") if entry["type"] == "SCALE_ACT_MATURED" else None)
                if row[1] != entry["node"] or row[2] != expected:
                    conflict = True
                else:
                    linked = positive_id(row[3])
            # Missing retained work is a provenance gap, not permission to guess.
        if direct and linked and direct != linked:
            conflict = True
        source_id = None if conflict else direct or linked
        if source_id:
            source_ids.add(source_id)
        candidates.append((entry, source_id))

    sources = {}
    if source_ids:
        placeholders = ",".join("?" for _ in source_ids)
        rows = conn.execute(
            f"SELECT {FIELDS} FROM world_mutations WHERE world_seed=? "
            f"AND id IN ({placeholders})", (seed, *source_ids)).fetchall()
        sources = {r[0]: decode(r) for r in rows}
    for entry, source_id in candidates:
        source = sources.get(source_id)
        if source:
            data, original = data_of(entry), data_of(source)
            expected = "SCALE_ACT" if entry["type"] == "SCALE_ACT_MATURED" else entry["type"]
            # An explicit link must still agree with the recorded kind/location
            # and point backward to an origin, never to another arriving hop.
            if (source["type"] != expected or source["id"] >= entry["id"]
                    or original.get("_origin") or original.get("_hop") or original.get("delivery")
                    or (data.get("_origin") and data["_origin"] != source["node"])
                    or (entry["type"] == "SCALE_ACT_MATURED" and source["node"] != entry["node"])
                    or (data.get("verb") and data["verb"] != original.get("verb"))):
                source = None
        narration = narrate(entry, source)
        if narration:
            entry["narration"] = narration
