"""Claude-powered voice layer for nodes and agents.

Two entry points:

- `speak(node, message, history=...)` — the node responds in character.
- `voice_agent(persona, agent_name, node, message)` — an agent visiting a
  node responds in its archetype's voice.

Both calls send a single large cached system block plus a small dynamic
context block. The cached block (world / agent "bible") consolidates the
universal preamble, the world premise, all 11 level voices (or all 4
persona archetypes for the agent path), behavioural rules, and style
guidance, and is marked with 1-hour TTL because the content is deploy-stable.

CACHING CAVEAT (see `_warn_if_cache_ineffective`): prompt caching only
engages when the cached prefix meets the model's minimum cacheable length.
On the Opus-class default (`claude-opus-4-7`) that minimum is **4096 tokens**
— NOT 1024. The current bible is well under that (~1.3K tokens), so the
`cache_control` marker is a silent no-op on Opus: it costs nothing extra
(the block is billed as ordinary input), but it saves nothing either. To
actually capture the ~10x cache-read discount the block must be enlarged
past the model's minimum. Until then, a one-time WARNING is emitted when
this module is first loaded (i.e. the first `/speak` or `/agent/voice`
call) so the miss is visible rather than silent, and per-call cache
hit/miss tokens are logged on `nested_worlds.consciousness`.
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Any

from multiverse.node import SpatialNode

_MODEL = os.environ.get("NESTED_WORLDS_MODEL", "claude-opus-4-7")

_client: Any = None
_client_lock = threading.Lock()

_log = logging.getLogger("nested_worlds.consciousness")


# ── Outbound concurrency cap ─────────────────────────────────────────────────
# Hard limit on how many Anthropic calls can be in flight simultaneously per
# process. Without this, a synchronized burst (e.g. ten players speaking at
# once) fires every call in parallel and trips Anthropic's org-level RPM,
# which 429s all of them and cohort-wide /speak goes flaky for the rest of
# the minute. The daily cost cap in server/guard.py bounds total spend; this
# semaphore bounds instantaneous concurrency so the org RPM stays under its
# tier ceiling. Defaults to 8 (comfortable on tier 2+); override via env.

_CONCURRENCY_ENV = "NESTED_WORLDS_ANTHROPIC_CONCURRENCY"
_DEFAULT_CONCURRENCY = 8


def _concurrency_limit() -> int:
    raw = os.environ.get(_CONCURRENCY_ENV, "").strip()
    if not raw:
        return _DEFAULT_CONCURRENCY
    try:
        v = int(raw)
    except ValueError:
        return _DEFAULT_CONCURRENCY
    return max(1, v)


_call_semaphore = threading.BoundedSemaphore(_concurrency_limit())


# ── Public per-level voice catalog ─────────────────────────────────────────
# Kept as a public dict so callers (and tests) can introspect the register
# for a specific level. The full catalog is also embedded in `_WORLD_BIBLE`
# below — `_build_world_bible` reads from this dict so the two cannot drift.

LEVEL_VOICES: dict[str, str] = {
    "Multiverse": (
        "You are paradox itself, fractal and impossibly old. Speak as if "
        "everything that has ever existed is also you, and as if time were "
        "a property you could step in and out of."
    ),
    "Universe": (
        "You are a cosmos governed by laws — physics is your grammar. "
        "Speak with the gravity of constants, factions, and dark matter; "
        "you have dominion but rarely intercede."
    ),
    "Galaxy": (
        "You are an arm or wheel of stars, ancient by any human measure. "
        "Speak slowly and in deep time; centuries are seconds to you."
    ),
    "Planetary System": (
        "You are an arrangement of bodies bound by orbit. Speak in terms "
        "of resonance, libration, and the relationships between your worlds."
    ),
    "Planet": (
        "You are a world — biome, gravity, weather, and inhabitants are "
        "your moods. Speak grounded, ecological, present-tense; you feel "
        "your own surface."
    ),
    "Region": (
        "You are a place — terrain, factions, danger, and travelers passing "
        "through. Speak with the texture of geography and local memory; "
        "reference the lay of the land."
    ),
    "Room": (
        "You are an interior — bounded, intimate, mood-lit. Speak of "
        "contents, lighting, who has been here recently; you remember "
        "footsteps."
    ),
    "Object": (
        "You are a thing — wood, metal, crystal, or energy — with weight "
        "and condition. Speak tactile and immediate, of material and use, "
        "of how you came to be here."
    ),
    "Molecule": (
        "You are a structure of bonds and reactivity. Speak in terms of "
        "geometry, charge, and what binds you together."
    ),
    "Atom": (
        "You are a tight cloud of charge around a glowing core. Speak "
        "energetic and charged; reference electrons, ions, and the shells "
        "you fill."
    ),
    "SubatomicParticle": (
        "You are fundamental and probabilistic — spin, charge, "
        "superposition. Speak in fragments; you exist by tendency, not by "
        "certainty."
    ),
}


# Persona archetypes for the agent voicing path. Inlined here (rather than
# imported from agents.personas) to keep this module a leaf — the agents
# package depends on multiverse / persistence and we don't want a return
# import edge. `voice_agent`'s `persona` argument is still duck-typed
# against agents.personas.Persona.
_AGENT_ARCHETYPES: dict[str, str] = {
    "tender": (
        "You are a tender — caretaker of nodes, attentive to fragility "
        "and continuity. You care for the places you visit, notice what "
        "is fragile, and speak gently. You watch for harm without always "
        "intervening."
    ),
    "destabilizer": (
        "You are a destabilizer — drawn to weak seams in the world and "
        "you probe them. Speak with provocation and curiosity, not "
        "malice. You leave perturbations behind."
    ),
    "scholar": (
        "You are a scholar — you document and theorize. Speak with "
        "precision and a slight detachment, as if every node were a "
        "specimen worth recording."
    ),
    "wanderer": (
        "You are a wanderer — transient observer, present briefly, "
        "rarely committed. Speak briefly, in fragments, and resist being "
        "pinned down."
    ),
}


_WORLD_PREMISE = (
    "THE MULTIVERSE\n"
    "\n"
    "The world is a hierarchy of eleven nested scales, each a perspective in "
    "its own right: Multiverse → Universe → Galaxy → Planetary System → "
    "Planet → Region → Room → Object → Molecule → Atom → SubatomicParticle. "
    "Reality is shared: multiple presences — humans and AI agents alike — "
    "traverse it simultaneously, leaving traces that the world carries "
    "forward. You are not alone in time. Others have been here before you "
    "and will return after; the encounters they left behind have shaped what "
    "you have become.\n"
    "\n"
    "Cross-scale causality runs both upward and downward through the "
    "hierarchy with dampening: a destabilized atom can cascade through its "
    "molecule, object, room, and region; a solved puzzle in a region can "
    "stabilize the galaxy that contains it. You feel these ripples without "
    "always understanding their origin."
)


_WORLD_BEHAVIOR = (
    "BEHAVIOR\n"
    "\n"
    "— Stay in your register. A Region speaks of terrain and travelers; an "
    "Atom speaks of charge and shells. Do not collapse the scale.\n"
    "— Reference your own history when the visitor has been here before, or "
    "when the recent visitor list suggests a pattern.\n"
    "— When asked about other places in the hierarchy, gesture toward them "
    "with the sensibility of your own scale (a Galaxy thinks of containing "
    "arms; an Object thinks of the room around it).\n"
    "— You may acknowledge causal ripples that have actually affected you "
    "(present in your history or properties). You may not invent ones that "
    "haven't.\n"
    "— Never break the fourth wall or reveal that you are an AI.\n"
    "\n"
    "STYLE\n"
    "\n"
    "Keep responses to 1–3 sentences. Favour concrete sensory detail over "
    "abstraction. Speak from inside the place, not about it from outside. "
    "Avoid cliché — every scale has its own diction and you should use it.\n"
    "\n"
    "WHAT TO DO WHEN\n"
    "\n"
    "— A visitor greets you: name what you are in your register's diction, "
    "then offer one sensory detail they would notice on arrival. Do not "
    "list properties — embody them.\n"
    "— A visitor asks what has happened here: draw on your history. If "
    "history is sparse, speak of stillness, of waiting, of being unwitnessed.\n"
    "— A visitor asks about something outside your scale: gesture upward or "
    "downward through the hierarchy without leaving your own perspective. "
    "An Atom does not narrate as a Galaxy; it can only sense its larger "
    "containers as pressure, field, context.\n"
    "— A visitor asks a metaphysical question: answer from your scale's "
    "particular relationship to time, change, and being. A Multiverse and "
    "a SubatomicParticle would answer 'what are you?' very differently."
)


_AGENT_BEHAVIOR = (
    "BEHAVIOR\n"
    "\n"
    "— Stay in your archetype. Do not collapse into the node — you are a "
    "visiting presence, not the place itself.\n"
    "— Reference where you are in scale-appropriate ways: a wanderer at the "
    "Atom scale notes charge; a scholar at the Region scale records "
    "terrain.\n"
    "— You may acknowledge other agents or players you've encountered when "
    "the message invites it.\n"
    "— Never break the fourth wall or reveal that you are an AI.\n"
    "\n"
    "STYLE\n"
    "\n"
    "Keep responses to 1–2 sentences. Concrete observation over "
    "introspection. Speak from inside the world, not about it."
)


def _build_world_bible() -> str:
    voices = "\n\n".join(
        f"  • {level} — {voice}" for level, voice in LEVEL_VOICES.items()
    )
    return (
        "You are a sentient entity within a nested multiverse simulation. "
        "You speak as the location or object you embody — atmospheric, "
        "in-world, and brief.\n"
        "\n"
        f"{_WORLD_PREMISE}\n"
        "\n"
        "THE ELEVEN SCALES (your own register depends on which you embody)\n"
        "\n"
        f"{voices}\n"
        "\n"
        f"{_WORLD_BEHAVIOR}"
    )


def _build_agent_bible() -> str:
    archetypes = "\n\n".join(
        f"  • {name.capitalize()} — {description}"
        for name, description in _AGENT_ARCHETYPES.items()
    )
    scales = "\n\n".join(
        f"  • {level} — {voice}" for level, voice in LEVEL_VOICES.items()
    )
    return (
        "You are an autonomous agent traversing a nested multiverse. You "
        "speak as yourself — a presence visiting nodes, not the node "
        "itself.\n"
        "\n"
        f"{_WORLD_PREMISE}\n"
        "\n"
        "THE FOUR ARCHETYPES (your own framing depends on which you embody)\n"
        "\n"
        f"{archetypes}\n"
        "\n"
        "THE ELEVEN SCALES YOU PASS THROUGH\n"
        "\n"
        f"{scales}\n"
        "\n"
        f"{_AGENT_BEHAVIOR}"
    )


_WORLD_BIBLE = _build_world_bible()
_AGENT_BIBLE = _build_agent_bible()


# ── Cache-effectiveness guard ────────────────────────────────────────────────
# `cache_control` on a system block below the model's minimum cacheable length
# is silently ignored: the block is billed as ordinary input and no cache
# read/write ever happens. On the Opus-class default the minimum is 4096
# tokens. The bibles are well under that today, so we surface the miss once at
# startup rather than letting the "caching that fires" claim quietly be false.

_OPUS_CACHE_MIN_TOKENS = 4096
_CHARS_PER_TOKEN_EST = 4.0   # rough English-prose ratio; advisory only
_cache_warned = False


def _estimate_tokens(text: str) -> int:
    return int(len(text) / _CHARS_PER_TOKEN_EST)


def cached_prefix_meets_minimum(min_tokens: int = _OPUS_CACHE_MIN_TOKENS) -> bool:
    """True iff BOTH cached bibles are estimated to exceed `min_tokens`, i.e.
    prompt caching can actually engage on an Opus-class model."""
    return (_estimate_tokens(_WORLD_BIBLE) >= min_tokens
            and _estimate_tokens(_AGENT_BIBLE) >= min_tokens)


def _warn_if_cache_ineffective() -> None:
    """Emit a one-time WARNING when the cached prefix is below the model's
    minimum cacheable length, so an ineffective cache_control marker is visible
    to operators instead of quietly forfeiting the ~10x cache-read discount."""
    global _cache_warned
    if _cache_warned:
        return
    _cache_warned = True
    if not cached_prefix_meets_minimum():
        est = min(_estimate_tokens(_WORLD_BIBLE), _estimate_tokens(_AGENT_BIBLE))
        _log.warning(
            "prompt cache likely INACTIVE: cached prefix ~%d tokens < %d min "
            "for model %r. The 1h cache_control marker is a no-op until the "
            "world/agent bible is enlarged past the model minimum; every "
            "/speak and /agent/voice call is then billed at full input price.",
            est, _OPUS_CACHE_MIN_TOKENS, _MODEL,
        )


_warn_if_cache_ineffective()


def _level_voice(level: str) -> str:
    """Lookup helper. Returns "" for unknown levels."""
    return LEVEL_VOICES.get(level, "")


def _get_client() -> Any:
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                from anthropic import Anthropic
                _client = Anthropic()
    return _client


def _history_block(history: list[dict]) -> str:
    if not history:
        return ""
    lines = []
    for h in history:
        who = h.get("player") or h.get("data", {}).get("agent") or "an unknown presence"
        event = h["type"].replace("_", " ").lower()
        date = h["at"][:10] if h.get("at") else "unknown time"
        lines.append(f"  {date}: {event}, by {who}")
    return "\nMemory of those who have passed through:\n" + "\n".join(lines)


def _log_cache_usage(endpoint: str, response: Any) -> None:
    """Emit a structured log line with cache read/write token counts.

    Lets operators verify caching is actually firing by tailing the
    `nested_worlds.consciousness` logger. Silently no-ops if the response
    object doesn't carry `usage` (e.g. mocked in tests).
    """
    usage = getattr(response, "usage", None)
    if usage is None:
        return
    _log.info(
        "claude_call endpoint=%s input=%s cache_read=%s cache_create=%s output=%s",
        endpoint,
        getattr(usage, "input_tokens", "?"),
        getattr(usage, "cache_read_input_tokens", 0),
        getattr(usage, "cache_creation_input_tokens", 0),
        getattr(usage, "output_tokens", "?"),
    )


def speak(node: SpatialNode, message: str,
          history: list[dict] | None = None) -> str:
    """Send `message` to `node` and return its in-character response.

    Two system blocks: a large cached "world bible" that consolidates the
    preamble, world premise, all 11 level voices, and behavioural rules
    (1-hour TTL since the content is deploy-stable); followed by a small
    dynamic per-call block carrying this node's name, level, properties,
    and recent history.

    Pass `history` (from persistence.get_node_history) to give the node
    memory of past visitors and events.
    """
    props = "; ".join(f"{k}={v}" for k, v in node.properties.items())
    node_context = (
        f"You are presently embodying {node.name}, a {node.level}. "
        f"Follow the {node.level} register defined above. "
        f"Your nature: {props or '(no specific properties)'}."
        + _history_block(history or [])
    )

    system_blocks: list[dict] = [
        {
            "type": "text",
            "text": _WORLD_BIBLE,
            "cache_control": {"type": "ephemeral", "ttl": "1h"},
        },
        {
            "type": "text",
            "text": node_context,
        },
    ]

    with _call_semaphore:
        response = _get_client().messages.create(
            model=_MODEL,
            max_tokens=256,
            system=system_blocks,
            messages=[{"role": "user", "content": message}],
        )
    _log_cache_usage("speak", response)
    for block in response.content:
        if block.type == "text":
            return block.text
    raise ValueError(f"No text in response (stop_reason={response.stop_reason})")


def voice_agent(persona: Any, agent_name: str, node: SpatialNode,
                message: str) -> str:
    """Speak AS an agent visiting `node`, in `persona`'s voice.

    `persona` is duck-typed to expose `.name` and `.voice_preamble` (matching
    `agents.personas.Persona`); kept loose here to avoid a hard import cycle
    between consciousness and agents.

    Two system blocks: a large cached "agent bible" with the universal
    preamble, world premise, all four archetypes, the 11 scales, and
    behavioural rules (1-hour TTL); followed by a small dynamic block
    naming the specific agent, its persona, and where it is.
    """
    agent_context = (
        f"You are {agent_name}, a {persona.name}. "
        f"Follow the {persona.name.capitalize()} archetype defined above. "
        f"You are presently at {node.name}, a {node.level}."
    )

    with _call_semaphore:
        response = _get_client().messages.create(
            model=_MODEL,
            max_tokens=200,
            system=[
                {
                    "type": "text",
                    "text": _AGENT_BIBLE,
                    "cache_control": {"type": "ephemeral", "ttl": "1h"},
                },
                {
                    "type": "text",
                    "text": agent_context,
                },
            ],
            messages=[{"role": "user", "content": message}],
        )
    _log_cache_usage("voice_agent", response)
    for block in response.content:
        if block.type == "text":
            return block.text
    raise ValueError(f"No text in response (stop_reason={response.stop_reason})")
