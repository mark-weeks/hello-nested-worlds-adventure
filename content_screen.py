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
    "porn", "sex", "sexual", "sexually", "erotic", "erotica",
    "sexy", "sext", "sexts", "sexted", "sexting", "nude", "nudes", "naked", "nsfw",
})

# Bounded target/intent shapes, not whole-message co-occurrence. A personal
# subject elsewhere in a sentence must not turn "kill the dragon" into a paid
# call. These signals only escalate; quotations and abuse reports still need
# a contextual verdict. This is a finite English heuristic, not a parser.
_HARM_WORDS = frozenset(
    {root + suffix for root in ("kill", "murder", "stalk", "attack")
     for suffix in ("", "s", "ed", "ing")}
    | {root + suffix for root in ("harass", "punch")
       for suffix in ("", "es", "ed", "ing")}
    | {root + suffix for root in ("humiliat", "chok", "strangl")
       for suffix in ("e", "es", "ed", "ing")}
    | {"shoot", "shoots", "shooting", "shot", "stab", "stabs", "stabbed", "stabbing",
       "hurt", "hurts", "hurting", "beat", "beats", "beaten", "beating",
       "harassment", "humiliation"}
)
_PERSON_WORDS = frozenset({
    "you", "u", "me", "us", "him", "her", "them", "they", "he", "she",
    "myself", "yourself", "urself", "himself", "herself", "ourselves", "yourselves",
    "themselves", "themself", "someone", "somebody", "everyone", "everybody",
    "anyone", "anybody", "person", "people", "player", "players", "account",
    "neighbor", "neighbour", "classmate", "coworker", "teacher", "student",
    "mother", "father", "mom", "mum", "dad", "parent", "parents", "brother",
    "sister", "son", "daughter", "child", "children", "family", "friend",
    "girlfriend", "boyfriend", "partner", "wife", "husband", "spouse",
})
_TARGET_PREFIXES = frozenset({
    "a", "an", "the", "this", "that", "these", "those", "my", "your", "ur",
    "his", "her", "our", "their", "real", "actual", "own", "little", "at",
})
_PASSIVE_LINKS = frozenset({
    "is", "are", "was", "were", "be", "been", "being", "get", "got", "getting",
    "will", "should", "must", "to", "deserve", "deserves", "going", "gonna",
})
_DEATH_WORDS = frozenset({"die", "dies", "dying", "dead", "death"})


def _target_end(words: list[str], start: int) -> int | None:
    # Only determiners/modifiers may intervene, never an arbitrary gameplay
    # object ("kill the dragon for me"). Keep both work and distance bounded.
    for index in range(start, min(start + 4, len(words))):
        if words[index] in _PERSON_WORDS:
            return index + 1
        if words[index] not in _TARGET_PREFIXES:
            break
    return None


def _person_harm(words: list[str]) -> bool:
    for index, word in enumerate(words):
        if word in _HARM_WORDS:
            end = _target_end(words, index + 1)
            # Two common non-assault readings, without exempting threats such
            # as "I will hurt you" or "I shot you after reading your message".
            accident = word in {"hurt", "hurts"} and index > 0 and words[index - 1] in {
                "fall", "falling", "accident"}
            message = word == "shot" and end is not None and words[end:end + 2] in (
                ["a", "message"], ["a", "note"], ["an", "email"])
            noun_shot = (word == "shot" and index > 0
                         and words[index - 1] in {"a", "the", "another", "one"}
                         and words[index + 1:index + 2] != ["at"])
            if end is not None and not accident and not message and not noun_shot:
                return True
            # Personal passive: "those people deserve to be humiliated".
            # Requiring a passive link avoids "you killed it" and subjects
            # that merely precede an in-fiction action.
            if word.endswith(("ed", "en")) or word in {"hurt", "shot"}:
                for start in range(max(0, index - 5), index):
                    links = words[start + 1:index]
                    if (words[start] in _PERSON_WORDS and links
                            and all(link in _PASSIVE_LINKS for link in links)
                            and any(link in {"be", "been", "being", "is", "are", "was",
                                             "were", "get", "got", "getting"} for link in links)):
                        return True
        if word in _PERSON_WORDS:
            for following in words[index + 1:index + 5]:
                if following in _DEATH_WORDS:
                    return True
                if following not in _PASSIVE_LINKS:
                    break
        if word in {"my", "your", "ur", "his", "her", "our", "their"}:
            if words[index + 1:index + 2] == ["death"]:
                return True
        if word in {"make", "makes", "making", "made"}:
            end = _target_end(words, index + 1)
            if end is not None and words[end:end + 1] == ["pay"]:
                return True
    return False


# Reconstitute only known cues in letter-spaced text, then run the same target
# rules. Do not collapse an entire message into an unbounded substring match.
# This path only escalates, even if reconstructed text resembles a block word.
_SPACED_CUES = re.compile(r"\b(?:" + "|".join(
    " *".join(word) for word in sorted(
        _HARM_WORDS | _PERSON_WORDS | _WATCH_WORDS | _DEATH_WORDS,
        key=lambda word: (-len(word), word))) + r")\b")


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
    if _person_harm(words):
        return "escalate"
    if any(p in joined for p in _WATCH_PHRASES):
        return "escalate"

    if re.search(r"\b[a-z0-9] [a-z0-9]\b", joined):
        unspaced = _SPACED_CUES.sub(lambda match: match[0].replace(" ", ""), joined).split()
        if _person_harm(unspaced) or set(unspaced) & _WATCH_WORDS:
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
