"""Evidence-bound prose for existing history and speech, independent of actors' type."""
import math

from multiverse.utils import display_name, node_address


def label(value):
    return value if isinstance(value, str) and value.strip() else None


def data_of(entry):
    return entry["data"] if isinstance(entry.get("data"), dict) else {}


def place(name):
    name = label(name)
    if not name:
        return "an unrecorded place"
    address = node_address(name)
    return f"{display_name(name)} [{address}]" if address is not None else name


def actor(entry):
    data = data_of(entry)
    # These are recorded labels only. Never render actor_identity/actor hashes,
    # infer a human/agent taxonomy, or equate matching names with identity.
    return label(entry.get("player")) or label(data.get("actor")) or label(data.get("agent"))


def narrate(entry, source=None):
    data = data_of(entry)
    kind = entry.get("type")
    ref = data.get("delivery") or {}
    arrival = bool(data.get("_origin") or data.get("_hop")
                   or (isinstance(ref, dict) and ref.get("queue") == "causal_queue"))
    if kind not in ("SCALE_ACT", "SCALE_ACT_MATURED") and not arrival:
        return None
    receiver = label(entry.get("node"))
    origin = source["node"] if source else label(data.get("_origin"))
    who = actor(source) if source else actor(entry)
    original = data_of(source) if source else data
    verb = label(original.get("verb")) or "act"
    act = f"{who}'s {verb}" if who else f"the {verb}"
    source_id = source["id"] if source else None
    delta = any(isinstance(value, dict) and value
                for value in (entry.get("delta"), data.get("changed")))
    delay = data.get("matures_in")
    delayed = type(delay) in (int, float) and math.isfinite(delay) and delay >= 0

    if kind == "SCALE_ACT_MATURED":
        phase = "outcome"
        text = (f"Delayed outcome of {act} at {place(origin)}." if origin else
                f"Delayed {verb} outcome at {place(receiver)}"
                + (f", attributed to {who}." if who else "."))
        if data.get("outcome") in ("already_satisfied", "precondition_changed"):
            text += " " + (label(data.get("flavor")) or "Nothing changes.")
        elif delta:
            text += " " + (label(data.get("flavor")) or "The recorded change took effect.")
        else:
            text += " No material change is recorded."
    elif arrival:
        phase = "arrival"
        # Event kinds are mechanical names; AGENT_VISIT must never become an
        # actor taxonomy in the chronicle or a node/inhabitant's memory context.
        event_name = {
            "AGENT_VISIT": "a passage", "PUZZLE_SOLVED": "a puzzle's resolution",
            "PUZZLE_FAILED": "a resisted puzzle", "DANGER_ALERT": "a disturbance",
            "STRUCTURAL_CHANGE": "a structural shift",
            "CONSTELLATION_COMPLETE": "a constellation's completion",
        }.get(kind, "an earlier event")
        effect = act if kind == "SCALE_ACT" else (
            event_name + (f" by {who}" if who else ""))
        cause = f"{effect} at {place(origin)}" if origin else effect
        noun = "A ripple" if kind == "SCALE_ACT" else "An effect"
        text = f"{noun} from {cause} reached {place(receiver)}."
    elif delayed or delta:
        phase = "accepted" if delayed else "action"
        origin = receiver
        text = f"{who or 'Someone'} chose to {verb} at {place(receiver)}."
        text += (" A delayed outcome was accepted." if phase == "accepted"
                 else " The recorded change took effect.")
        if entry.get("id"):
            text += f" Action #{entry['id']}."
    else:
        phase = "trace"
        text = f"A trace of {verb}" + (f" attributed to {who}" if who else "")
        text += f" was recorded at {place(receiver)}. No material change is recorded."

    if phase in ("arrival", "outcome"):
        text += (f" Source action #{source_id}." if source_id else
                 " The original action is unrecorded." if not origin else
                 " The exact original action is unrecorded.")
    return {"phase": phase, "text": text, "origin": origin, "receiver": receiver,
            "actor_label": who, "source_event_id": source_id}
