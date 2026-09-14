"""Input moderation for player-authored text (ADR-004 §2).

Two tiers, cheapest first, applied BEFORE anything enters the permanent
chronicle (`/speak`, `/agent/voice`, WS chat) or the name registry:

  1. **Local filter** — in-process, zero API cost/latency. A word-boundary
     match against a small list of unambiguous slurs is a definite BLOCK; a
     match against the broader watch list, an evasion-shaped sequence hit
     (spaced/leet-spelled slurs), or a long digit run (doxxing shape) marks
     the input AMBIGUOUS.
  2. **Haiku classify** — only ambiguous inputs escalate to one short,
     uncached Messages-API call (`consciousness.classify_content`), charged
     to moderation's own daily budget (`guard.consume_moderation`), never
     the voice budget.

**Fail-open everywhere**: an API error, a timeout, or an exhausted
moderation budget ALLOWS the input — content-level redaction stays the
backstop (ADR-004 §1), and a safety feature must never become the thing
that breaks chat. The kill switch (`NESTED_WORLDS_DISABLE_MODERATION=1`)
turns the whole screen off without a redeploy, matching the AI/image
switches.

Design note on false positives: only the exact word-boundary tier can block
on its own. The fuzzier signals (collapsed sequences, run-squeezed text,
watch words) never block locally — they only escalate, so the classifier
absorbs the ambiguity ("sniggering", the river Niger, fantasy violence) and
an over-eager heuristic costs a fraction of a cent, not a censored player.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from content_screen import (
    _words, _squeeze, _SEVERE_WORDS, _EVASION_SEQUENCES, _env_terms,
    local_tier as _local_tier,
)
from server import guard

_log = logging.getLogger("nested_worlds.moderation")

DISABLE_MODERATION_ENV = "NESTED_WORLDS_DISABLE_MODERATION"
# Hot-tunable extensions (comma-separated words/phrases), so an operator can
# react to live abuse without a redeploy — same posture as the kill switches.
EXTRA_BLOCK_ENV = "NESTED_WORLDS_MODERATION_BLOCK_EXTRA"
EXTRA_WATCH_ENV = "NESTED_WORLDS_MODERATION_WATCH_EXTRA"

# The authored refusal — in the world's voice, actionable, and the same line
# everywhere so clients can rely on it. HTTP 200 + this line, never an error
# page: a content decline is a policy act, but it still speaks in fiction.
DECLINE_LINE = "The worlds decline to carry those words. Say it another way."


def moderation_disabled() -> bool:
    return os.environ.get(DISABLE_MODERATION_ENV, "").strip() == "1"


# ── Verdicts ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Verdict:
    allowed: bool
    tier: str  # off | clean | blocklist | classify | fail_open | budget_open


_ALLOW_OFF    = Verdict(True, "off")
_ALLOW_CLEAN  = Verdict(True, "clean")
_BLOCK_LOCAL  = Verdict(False, "blocklist")



def screen(text: str) -> Verdict:
    """Screen player-authored text before it enters the chronicle.

    The common case (clean input) costs zero API calls and microseconds of
    CPU; only ambiguous inputs spend a classify call. Every failure path
    ALLOWS — the screen can go quiet, the world's voice cannot.
    """
    if moderation_disabled():
        return _ALLOW_OFF
    if not text or not text.strip():
        return _ALLOW_CLEAN

    tier = _local_tier(text)
    if tier == "block":
        return _BLOCK_LOCAL
    if tier == "clean":
        return _ALLOW_CLEAN

    # Ambiguous → one classify call, on moderation's own budget.
    if not guard.consume_moderation():
        _log.warning("moderation budget exhausted — failing open")
        return Verdict(True, "budget_open")
    try:
        import consciousness
        allowed = consciousness.classify_content(text)
        return Verdict(allowed, "classify")
    except Exception as exc:
        _log.warning("moderation classify failed open: %s", exc)
        return Verdict(True, "fail_open")


def name_allowed(name: str) -> bool:
    """Local-only screen for registered display names (mint + /register).

    Names are permanent, unique, and visible everywhere, so this tier is
    STRICTER than `screen`: the evasion sequences hard-block here instead of
    escalating (a 32-char name has no prose context to be innocent in, and
    the registrant can simply choose another). No API call — registration
    stays synchronous and cheap; `redact --scrub-name` remains the backstop.
    """
    if moderation_disabled():
        return True
    words = _words(name)
    if set(words) & (_SEVERE_WORDS | _env_terms(EXTRA_BLOCK_ENV)):
        return False
    collapsed = "".join(words)
    squeezed = _squeeze(collapsed)
    if any(s in collapsed or s in squeezed for s in _EVASION_SEQUENCES):
        return False
    return True
