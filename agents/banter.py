"""Agent-to-agent conversation — the world generates its own stories.

When two wanderers meet at a node during a heartbeat traversal, they
exchange a few in-character lines. The exchange is synthesized here —
deterministic, zero API cost, honoring the heartbeat's "costs nothing per
tick" contract — from each speaker's persona archetype and what the node
actually is: its level, its properties, its accumulated history. The
conversation is then recorded as an AGENT_TALK chronicle entry, so players
who arrive later find the transcript in node history (and the node's
Claude voice, which reads history, can allude to what was said here).

Determinism: same (seed, node, pair, meeting-ordinal) → same exchange.
Different meetings at the same place read differently because the ordinal
advances.
"""
from __future__ import annotations

import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from multiverse.node import SpatialNode

# Openers: how each archetype starts a conversation about a place.
_OPENERS = {
    "tender": [
        "Careful here — {detail}. It needs looking after.",
        "I keep coming back to this {level_l}. {detail}, and no one tends it.",
        "Something here is fragile. {detail}. Mind where you step.",
        "Good — another pair of hands. {detail}, and I can't hold it alone.",
    ],
    "destabilizer": [
        "Feel that? {detail}. One good push and it all rearranges.",
        "This {level_l} is too settled. {detail} — let's see what shakes loose.",
        "I've been leaning on the seams. {detail}. It wants to change.",
        "Don't tell me you're here to preserve this. {detail} — it's begging for a shove.",
    ],
    "scholar": [
        "Note the anomaly: {detail}. Third instance I've catalogued this cycle.",
        "I have questions about this {level_l}. {detail} — that shouldn't hold.",
        "Evidence accumulates. {detail}. My model didn't predict that.",
        "Before you touch anything — {detail}. I need it documented first.",
    ],
    "wanderer": [
        "Passing through. Though — {detail}. That almost makes me stay.",
        "I've seen a hundred of these. This one though: {detail}.",
        "Don't mind me. {detail}, is all. I'll be gone before it matters.",
        "The paths crossed here for a reason, maybe. {detail}.",
    ],
}

# Responses: how each archetype answers, whoever spoke first.
_RESPONSES = {
    "tender": [
        "Then help me steady it instead of talking about it.",
        "It holds because someone held it before us. Remember that.",
        "I'll stay a while after you leave. Someone has to.",
        "Gently. Everything here remembers what's done to it.",
    ],
    "destabilizer": [
        "Steady is just slow collapse. I'd rather it be honest.",
        "You document, I demonstrate. Watch.",
        "Everything you're protecting was made by something breaking first.",
        "One crack. That's all I'm asking for. One interesting crack.",
    ],
    "scholar": [
        "Anecdote isn't evidence. But go on — I'm writing this down.",
        "Curious. The history layer here is thicker than the structure warrants.",
        "If you must interfere, do it where I can measure the delta.",
        "I've read this place's record. We are not the first to argue here.",
    ],
    "wanderer": [
        "You both care too much. It's kind of beautiful.",
        "Wherever this goes, I won't be here to see it. Make it good.",
        "I'll carry word of this place outward. That's my part.",
        "Every node thinks it's the center. This one might be right.",
    ],
}

_CLOSERS = [
    "The two figures regard each other a moment longer, then turn back to the {level_l}.",
    "Somewhere deeper, something shifts — both of them feel it and say nothing.",
    "The conversation ends the way they all do here: unfinished.",
    "They part without agreeing. The {level_l} keeps both versions.",
]


def _detail(node: "SpatialNode", rng: random.Random) -> str:
    """One concrete, property-grounded observation about the node."""
    props = node.properties or {}
    candidates: list[str] = []
    if "aspect" in props:
        candidates.append(str(props["aspect"]))
    if isinstance(props.get("danger_level"), int) and props["danger_level"] >= 6:
        candidates.append(f"the danger here reads {props['danger_level']} of 10")
    if props.get("condition") in ("damaged", "corrupted"):
        candidates.append(f"the material is {props['condition']}")
    if props.get("stability") in ("fraying", "collapsing"):
        candidates.append(f"the weave is {props['stability']}")
    if props.get("stabilized"):
        candidates.append("someone stabilized this place, recently")
    if isinstance(props.get("inscriptions"), int) and props["inscriptions"] > 0:
        candidates.append(f"{props['inscriptions']} inscription(s) cut into the walls")
    if node.ripple_score >= 0.3:
        candidates.append("the causal pressure here hums under everything")
    if not candidates:
        for key in ("weather", "lighting", "air", "sky", "glow", "membrane"):
            if key in props:
                candidates.append(f"the {key} is {props[key]}")
                break
    if not candidates:
        candidates.append(f"this {node.level.lower()} is quieter than it should be")
    return rng.choice(candidates)


def compose_exchange(seed: int, node: "SpatialNode",
                     agent_a: str, persona_a: str,
                     agent_b: str, persona_b: str,
                     ordinal: int = 0) -> list[dict[str, str]]:
    """A short deterministic exchange between two co-located agents.

    Returns [{speaker, persona, line}, ...] — 2 spoken lines plus a closing
    stage direction (speaker ""). Same inputs → same exchange, forever.
    """
    # Order-independent pair key: A meeting B is the same conversation as
    # B meeting A.
    pair = ":".join(sorted((agent_a, agent_b)))
    rng = random.Random(f"talk:{seed}:{node.name}:{pair}:{ordinal}")

    detail = _detail(node, rng)
    fmt = {"detail": detail, "level_l": node.level.lower()}

    opener = rng.choice(_OPENERS.get(persona_a, _OPENERS["wanderer"]))
    response = rng.choice(_RESPONSES.get(persona_b, _RESPONSES["wanderer"]))
    closer = rng.choice(_CLOSERS)

    return [
        {"speaker": agent_a, "persona": persona_a,
         "line": opener.format(**fmt)},
        {"speaker": agent_b, "persona": persona_b,
         "line": response.format(**fmt)},
        {"speaker": "", "persona": "",
         "line": closer.format(**fmt)},
    ]
