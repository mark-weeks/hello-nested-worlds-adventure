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

from agents.roster import profile_for

if TYPE_CHECKING:
    from multiverse.node import SpatialNode

# Openers: how each archetype starts a conversation about a place.
_OPENERS = {
    "tender": [
        "Careful here — {detail}. It needs looking after.",
        "I keep coming back to this {level_l}. {detail}, and no one tends it.",
        "Something here is fragile. {detail}. Mind where you step.",
        "Good — another pair of hands. {detail}, and I can't hold it alone.",
        "Hush a moment. Listen to it. {detail} — it's trying to settle.",
        "I mended something like this once. {detail}. It can be held.",
        "Every scale needs a keeper. Here, it's me. {detail}.",
        "Don't crowd it. {detail}, and it startles easily.",
        "There's a right way to touch a place like this. {detail}.",
        "I've made a list of what needs tending. {detail} — that's item one.",
        "Someone left this to fray. {detail}. Not on my watch.",
        "Stay if you'll help. {detail}, and dusk comes fast here.",
    ],
    "destabilizer": [
        "Feel that? {detail}. One good push and it all rearranges.",
        "This {level_l} is too settled. {detail} — let's see what shakes loose.",
        "I've been leaning on the seams. {detail}. It wants to change.",
        "Don't tell me you're here to preserve this. {detail} — it's begging for a shove.",
        "Structure is a rumor places tell themselves. {detail}. Watch me end it.",
        "I found the load-bearing lie of this place. {detail}.",
        "You call it damage. I call it honesty arriving. {detail}.",
        "Somewhere in here is a thread that unravels the rest. {detail}.",
        "It held yesterday. {detail} — let's ask if it holds today.",
        "The keepers keep, and I ask what for. {detail}.",
        "Give me one reason not to lean on it. {detail} isn't one.",
        "Change is the only tenant that always pays. {detail}.",
    ],
    "scholar": [
        "Note the anomaly: {detail}. Third instance I've catalogued this cycle.",
        "I have questions about this {level_l}. {detail} — that shouldn't hold.",
        "Evidence accumulates. {detail}. My model didn't predict that.",
        "Before you touch anything — {detail}. I need it documented first.",
        "Interesting. My last survey missed this: {detail}.",
        "Page forty-one of my ledger predicted this place. {detail} does not fit.",
        "I count, therefore it counts. {detail} — noted.",
        "The pattern repeats at three scales so far. {detail} makes four.",
        "Do not move. You are standing on a data point. {detail}.",
        "History is just measurement that waited too long. {detail}.",
        "I've named this phenomenon twice already. {detail} demands a third.",
        "If it cannot be catalogued, it will at least be footnoted. {detail}.",
    ],
    "wanderer": [
        "Passing through. Though — {detail}. That almost makes me stay.",
        "I've seen a hundred of these. This one though: {detail}.",
        "Don't mind me. {detail}, is all. I'll be gone before it matters.",
        "The paths crossed here for a reason, maybe. {detail}.",
        "I don't stay. But {detail} — that's worth a pause.",
        "Three scales up, they tell stories about places like this. {detail}.",
        "The road forgets me the moment I pass. {detail} might not.",
        "I've slept in worse. {detail}, though — that's new.",
        "Every place wants to be someone's destination. {detail}.",
        "If you're lost, so am I. {detail}, at least, is honest.",
        "I carry no map. Places like this are the map. {detail}.",
        "Somewhere there's a door I haven't tried. Until then: {detail}.",
    ],
}

# Responses: how each archetype answers, whoever spoke first.
_RESPONSES = {
    "tender": [
        "Then help me steady it instead of talking about it.",
        "It holds because someone held it before us. Remember that.",
        "I'll stay a while after you leave. Someone has to.",
        "Gently. Everything here remembers what's done to it.",
        "Argue if you like. My hands will be busy meanwhile.",
        "It doesn't need your theory. It needs an hour of care.",
        "Leave it better. That's the entire philosophy.",
        "You'd be surprised what stays standing when someone minds it.",
        "The world keeps score in small repairs.",
        "I heard what it's carrying. Lower your voice.",
        "Careful is not the same as afraid.",
        "When you go, I'll still be here, holding the seam.",
    ],
    "destabilizer": [
        "Steady is just slow collapse. I'd rather it be honest.",
        "You document, I demonstrate. Watch.",
        "Everything you're protecting was made by something breaking first.",
        "One crack. That's all I'm asking for. One interesting crack.",
        "Preservation is just decay with better manners.",
        "I've seen what your steadiness costs. It isn't free either.",
        "Then hold it. I'll be curious how long.",
        "Every ruin used to be somebody's certainty.",
        "You keep the walls. I'll keep the questions.",
        "It wants to fall. I'm only agreeing with it.",
        "Note how it trembles when we argue. It's listening.",
        "Order borrows. Entropy collects.",
    ],
    "scholar": [
        "Anecdote isn't evidence. But go on — I'm writing this down.",
        "Curious. The history layer here is thicker than the structure warrants.",
        "If you must interfere, do it where I can measure the delta.",
        "I've read this place's record. We are not the first to argue here.",
        "Your feelings are noted. Literally. In the margin.",
        "Fascinating claim. Zero citations.",
        "The record will show that I sighed here.",
        "Two observers, one node: the sample size finally doubles.",
        "Whatever you break, number the pieces.",
        "I measured this argument three visits ago. Same result.",
        "The chronicle remembers better than either of us.",
        "Speak slower. I'm transcribing.",
    ],
    "wanderer": [
        "You both care too much. It's kind of beautiful.",
        "Wherever this goes, I won't be here to see it. Make it good.",
        "I'll carry word of this place outward. That's my part.",
        "Every node thinks it's the center. This one might be right.",
        "I'll remember this conversation at some other scale entirely.",
        "Settle it without me. The road is patient but I'm not.",
        "You both sound like people who've never left one level.",
        "Somewhere a door just opened. Excuse me.",
        "Keep arguing. It makes the place feel inhabited.",
        "I've heard this exact quarrel two galaxies over.",
        "Whatever you decide, the dust will outvote you.",
        "Passing through was always my strongest opinion.",
    ],
}

_CLOSERS = [
    "The two figures regard each other a moment longer, then turn back to the {level_l}.",
    "Somewhere deeper, something shifts — both of them feel it and say nothing.",
    "The conversation ends the way they all do here: unfinished.",
    "They part without agreeing. The {level_l} keeps both versions.",
    "A silence settles that neither of them owns.",
    "One of them laughs first. Neither admits which.",
    "The {level_l} hums once, as if filing the exchange away.",
    "They stand apart, watching different distances.",
    "Neither says goodbye. At their age, arrivals are the only ceremony.",
    "The words thin out; the place absorbs what's left.",
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


def _with_tic(line: str, speaker: str, rng: random.Random) -> str:
    """A cast regular's signature phrase occasionally rides their line.

    Individuation on top of the archetype banks: two tenders share openers,
    but only The Locksmith adds "Every seal remembers its key." Fires often
    enough to be a recognizable habit, rarely enough to stay a tic.
    """
    profile = profile_for(speaker)
    if profile is not None and profile.tic and rng.random() < 0.4:
        return f"{line} {profile.tic}"
    return line


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
         "line": _with_tic(opener.format(**fmt), agent_a, rng)},
        {"speaker": agent_b, "persona": persona_b,
         "line": _with_tic(response.format(**fmt), agent_b, rng)},
        {"speaker": "", "persona": "",
         "line": closer.format(**fmt)},
    ]
