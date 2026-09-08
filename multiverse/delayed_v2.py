"""Frozen M2 operation interpreter. Never dispatch accepted work to VERBS.

Future tuning gets a new version/module. The booleans pin the components
admitted at acceptance; a mark-only operation cannot later become growth.
"""
import math


FIELDS = {
    "attune": ("Multiverse", "stability", "attuned"),
    "calibrate": ("Universe", "dark_matter_ratio", "calibrated"),
    "kindle": ("Galaxy", "star_density", "kindled"),
    "align": ("Planetary System", "ecliptic_tilt_deg", "aligned"),
}


def _step(verb, value):
    """(valid precondition, next value), preserving v2's arithmetic."""
    if verb == "attune":
        steps = {"collapsing": "fraying", "fraying": "stable", "stable": "stable"}
        return (True, steps[value]) if isinstance(value, str) and value in steps else (False, value)
    if type(value) not in (int, float) or not math.isfinite(value):
        return False, value
    if verb == "kindle":
        if type(value) is not int or not 0 <= value <= 999:
            return False, value
        return True, min(999, value + max(1, value // 20))
    if verb == "calibrate":
        if not 0 <= value <= 1:
            return False, value
        new = value
        if abs(value - 0.5) > 0.01:
            candidate = round(min(max(value + (0.05 if value < 0.5 else -0.05), 0), 1), 2)
            if abs(candidate - 0.5) < abs(value - 0.5):
                new = candidate
        return True, new
    if value < 0:
        return False, value
    return True, min(value, round(value * 0.9, 1)) if value > 0.05 else value


def prepare(verb, level, properties):
    if verb not in FIELDS or FIELDS[verb][0] != level:
        raise ValueError("unsupported v2 delayed verb/level")
    _, field, flag = FIELDS[verb]
    valid, next_value = _step(verb, properties.get(field))
    if not valid:
        return None, "precondition_changed"
    adjust = next_value != properties.get(field)
    mark = not bool(properties.get(flag))
    if not adjust and not mark:
        return None, "already_satisfied"
    return {"adjust": adjust, "mark": mark}, None


def policy(operation):
    return "contribution" if operation["adjust"] else "transition"


def apply(verb, level, properties, operation):
    if (verb not in FIELDS or FIELDS[verb][0] != level
            or not isinstance(operation, dict) or set(operation) != {"adjust", "mark"}
            or any(type(v) is not bool for v in operation.values())
            or not any(operation.values())):
        raise ValueError("unsupported v2 delayed operation")
    _, field, flag = FIELDS[verb]
    valid, next_value = _step(verb, properties.get(field))
    if not valid:
        return None, "precondition_changed"
    changed = {}
    if operation["adjust"] and next_value != properties.get(field):
        changed[field] = next_value
    if operation["mark"] and not properties.get(flag):
        changed[flag] = True
    return changed or None, "applied" if changed else "already_satisfied"


def acceptance_flavor(verb, operation, shared=False):
    if shared:
        return (f"The {verb} already traveling here carries this same change. "
                "You join its wait; no additional change is planted.")
    if policy(operation) == "transition":
        return f"The {verb} is planted: one shared change is still traveling."
    return (f"Your {verb} is planted: one contribution is still traveling. "
            "It will tend what it finds when it arrives; there may be nothing left to change.")


def outcome_flavor(verb, outcome):
    if outcome == "applied":
        return f"The {verb} planted here settles at last — the change arrives."
    if outcome == "already_satisfied":
        return f"The {verb} finds this work already fulfilled. Nothing more changes."
    return f"The {verb} can no longer take hold in the changed conditions here. Nothing changes."
