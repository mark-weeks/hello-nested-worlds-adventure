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
import re
import unicodedata
from dataclasses import dataclass

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


# ── Normalization ───────────────────────────────────────────────────────────

# Common single-character substitutions used to sneak words past filters.
_LEET = str.maketrans({
    "@": "a", "4": "a", "3": "e", "1": "i", "!": "i",
    "0": "o", "$": "s", "5": "s", "7": "t",
})

# Homoglyph fold: letters from other scripts that render identically (or
# near-identically) to Latin ones. Without this, a slur written with one
# Cyrillic vowel had its non-ASCII letters *stripped* by the [^a-z0-9] pass —
# matching neither the block tier nor any escalation trigger, entering the
# chronicle screened by nothing. Applied after NFKC (which already folds
# fullwidth forms and ligatures) and casefold (which lowers the uppercase
# variants into the forms mapped here). Deliberately only the classic
# confusable set — unmapped scripts still strip, and redaction remains the
# backstop for what no filter catches.
_CONFUSABLES = str.maketrans({
    # Cyrillic
    "а": "a", "в": "b", "е": "e", "ё": "e", "к": "k", "м": "m", "н": "h",
    "о": "o", "р": "p", "с": "c", "т": "t", "у": "y", "х": "x", "і": "i",
    "ї": "i", "ѕ": "s", "ј": "j", "ԁ": "d", "ԛ": "q", "ԝ": "w",
    # Greek
    "α": "a", "ε": "e", "η": "n", "ι": "i", "κ": "k", "ν": "v", "ο": "o",
    "ρ": "p", "τ": "t", "υ": "u", "χ": "x",
    # Latin look-alikes
    "ı": "i", "ɡ": "g", "ℓ": "l",
})


def _normalize(text: str) -> str:
    """NFKC + casefold + homoglyph fold — one canonical form for matching."""
    return unicodedata.normalize("NFKC", text).casefold().translate(_CONFUSABLES)


def _words(text: str) -> list[str]:
    """Normalized, leet-mapped, punctuation-stripped word list."""
    mapped = _normalize(text).translate(_LEET)
    return re.sub(r"[^a-z0-9]+", " ", mapped).split()


def _squeeze(s: str) -> str:
    """Collapse letter runs ('niiice' → 'nice') for evasion-shape matching."""
    return re.sub(r"(.)\1+", r"\1", s)


# ── Term lists ──────────────────────────────────────────────────────────────
# Content-moderation blocklist. Kept deliberately small and unambiguous:
# every entry here is a severe slur with no benign word-boundary reading —
# anything context-dependent belongs on the WATCH list (escalates, never
# blocks locally). Stored casefolded/leet-normalized to match `_words`.

_SEVERE_WORDS = frozenset({
    "nigger", "niggers", "nigga", "niggas",
    "faggot", "faggots", "fag",
    "kike", "kikes",
    "spic", "spics",
    "chink", "chinks",
    "wetback", "wetbacks",
    "tranny", "trannies",
    "raghead", "ragheads",
})

# Context-dependent or milder terms: common enough in benign play (fantasy
# menace, venting, quoted lyrics) that blocking locally would misfire, but
# worth one cheap classify when they appear.
_WATCH_WORDS = frozenset({
    "rape", "rapist", "raping",
    "kys",
    "nazi", "nazis", "hitler",
    "pedo", "pedophile", "paedophile",
    "molest", "molester",
    "cunt", "whore", "slut",
    "porn",
})

# Multi-word phrases checked against the space-joined normalized text.
_WATCH_PHRASES = (
    "kill yourself",
    "kill urself",
    "go die",
)

# Evasion-shaped sequences: matched against the space-stripped and
# run-squeezed forms, so "n i g g e r" and "faaggot" surface. ESCALATE-only —
# substrings have no word boundaries ("sniggering"), so the classifier gets
# the final say.
_EVASION_SEQUENCES = tuple(sorted(
    {w for w in _SEVERE_WORDS if len(w) >= 5}
    | {_squeeze(w) for w in _SEVERE_WORDS if len(_squeeze(w)) >= 5}
))

# A long unbroken digit run is the shape of a phone number / ID — the
# doxxing case ADR-004 §2 names. Escalate, don't block: big numbers are
# also just cosmology talk in this game.
_DIGIT_RUN = re.compile(r"\d{7,}")


def _env_terms(env_var: str) -> frozenset[str]:
    raw = os.environ.get(env_var, "")
    return frozenset(t.strip().casefold() for t in raw.split(",") if t.strip())


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


def _local_tier(text: str) -> str:
    """'block' | 'escalate' | 'clean' — the zero-cost decision."""
    words = _words(text)
    word_set = set(words)
    if word_set & (_SEVERE_WORDS | _env_terms(EXTRA_BLOCK_ENV)):
        return "block"

    joined = " ".join(words)
    if word_set & (_WATCH_WORDS | _env_terms(EXTRA_WATCH_ENV)):
        return "escalate"
    if any(p in joined for p in _WATCH_PHRASES):
        return "escalate"

    collapsed = joined.replace(" ", "")
    squeezed = _squeeze(collapsed)
    if any(s in collapsed or s in squeezed for s in _EVASION_SEQUENCES):
        return "escalate"
    # Digit runs are checked on the RAW text (the leet map above rewrites
    # digits into letters), with common separators collapsed so a spaced or
    # dashed phone number still reads as one run.
    if _DIGIT_RUN.search(re.sub(r"[\s\-.()]+", "", text)):
        return "escalate"
    return "clean"


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
