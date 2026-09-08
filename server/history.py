"""Post-commit presentation; a failed read never invalidates accepted work."""
import logging

import persistence


def narration_fields(seed, event_id):
    if not event_id:
        return {}
    try:
        rows = persistence.presented_mutations(seed, [event_id])
        if rows and rows[0].get("narration"):
            return {"event_id": event_id, "narration": rows[0]["narration"]}
    except Exception:
        logging.getLogger(__name__).exception("history projection unavailable for %s", event_id)
    return {}


def broadcast_history_batch(notifications, broadcast):
    """One provenance projection per seed/bounded batch, never per landing row.

    Delivery has already committed. Read/send failures remain best effort and
    cannot replay a delta or prevent the next notification from being attempted.
    """
    seeds = {}
    for seed, message in notifications:
        seeds.setdefault(seed, []).append(message.get("event_id"))
    projected = {}
    for seed, ids in seeds.items():
        try:
            projected[seed] = {r["id"]: r.get("narration") for r in
                               persistence.presented_mutations(seed, ids)}
        except Exception:
            logging.getLogger(__name__).exception("history batch unavailable for world %s", seed)
    for seed, message in notifications:
        narration = projected.get(seed, {}).get(message.get("event_id"))
        try:
            broadcast(seed, {**message, **({"narration": narration} if narration else {})})
        except Exception:
            logging.getLogger(__name__).exception("committed event notice failed")
