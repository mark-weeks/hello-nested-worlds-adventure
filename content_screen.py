"""Shared local text classification. No network, persistence or server dependencies."""
import os
import re
import unicodedata

EXTRA_BLOCK_ENV = "NESTED_WORLDS_MODERATION_BLOCK_EXTRA"
EXTRA_WATCH_ENV = "NESTED_WORLDS_MODERATION_WATCH_EXTRA"

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


def local_tier(text: str) -> str:
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
