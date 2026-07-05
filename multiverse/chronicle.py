"""The world chronicle: history made legible.

The `world_mutations` table is the world's permanent memory — every solve,
speech, act, agent visit, and danger since the seed was first opened (the
continuity policy forbids pruning it). This module shapes that log for
display: entries are grouped into **eras** — one per ISO week of world
history — and each era gets a deterministic in-fiction name derived from
(seed, year, week), so "the week of 2026-06-29" reads as
"The Vigil of Emberglass" and reads the same for every player, on every
client, forever.
"""
from __future__ import annotations

import random
from datetime import date, datetime

_ERA_OPENERS = [
    "The Vigil", "The Season", "The Drift", "The Reckoning", "The Quiet",
    "The Kindling", "The Turning", "The Long Watch", "The Mending",
    "The Deep Survey", "The Passage", "The Chorus",
]

_ERA_SUBJECTS = [
    "of Emberglass", "of Saltfall", "of the Folded Membrane", "of Pale Orbits",
    "of the Unwarded Door", "of Slow Lightning", "of the Ninth Ring",
    "of Hollow Stars", "of the Patient Atom", "of Verdigris",
    "of the Second Inscription", "of Threadbare Light", "of the Waking Tide",
    "of Umbral Weather", "of the Counted Bonds", "of Glass Rain",
]


def _week_key(at: str) -> tuple[int, int]:
    """ISO (year, week) for a stored `recorded_at` string (UTC)."""
    day = datetime.strptime(at[:10], "%Y-%m-%d").date()
    iso = day.isocalendar()
    return iso[0], iso[1]


def era_name(seed: int, at: str) -> str:
    """Deterministic era name for the ISO week containing `at`.

    Same (seed, week) → same name, always — the chronicle must read
    identically to every participant and never rewrite itself.
    """
    year, week = _week_key(at)
    rng = random.Random(f"era:{seed}:{year}:{week}")
    return f"{rng.choice(_ERA_OPENERS)} {rng.choice(_ERA_SUBJECTS)}"


def annotate_eras(seed: int, entries: list[dict]) -> list[dict]:
    """Stamp each chronicle entry (dicts with an `at` key) with its era."""
    out = []
    for e in entries:
        era = era_name(seed, e["at"]) if e.get("at") else ""
        out.append(dict(e, era=era))
    return out


def current_era(seed: int) -> str:
    """The era name for the present moment (server clock, UTC week)."""
    return era_name(seed, date.today().isoformat())
