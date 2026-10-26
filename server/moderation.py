"""Input moderation for player-authored text (ADR-004 §2).

Two tiers, cheapest first, applied BEFORE shared text can be seen by
anyone else (`/speak`, `/agent/voice`, WebSocket chat, Ideas, a published
profile, a registered name, and puzzle free text stored in the chronicle):

  1. **Local filter** — in-process, zero API cost/latency. A word-boundary
     match against a small list of unambiguous slurs is a definite BLOCK; a
     match against the broader watch list (including sexual-content cues),
     bounded harm/target or death-threat shapes, an evasion-shaped sequence hit
     (spaced/leet-spelled slurs or threats), or a long digit run (doxxing shape) marks
     the input AMBIGUOUS. These signals request a contextual verdict; they
     never block locally, including when they match benign fiction or reports.
  2. **Model classification** — only ambiguous inputs escalate to one short
     call (`consciousness.classify_content`), charged to moderation's own
     daily budget (`guard.moderation_reserve`), never the voice budget.
     The model id is `runtime.model_for("moderation")`.

**Shared text fails closed.** A timeout, a provider error, disabled
moderation, an exhausted moderation budget, an undecided verdict, or a
per-user cap holds the text: no chronicle row, no broadcast, no visible
idea, no published profile, no registered name. A local or model BLOCK
declines it. Neither path charges the voice budget. Private notes,
unpublished profile text, movement, puzzle correctness, and scale actions
are not held because the screen could not judge. The local CLI `speak`
path stays unscreened only while it is not writing the hosted canonical
world; speech into that world uses this same rule.

Design note on false positives: only the exact word-boundary tier can block
on its own. The fuzzier signals never block locally — they only escalate.
A flaky classifier holds the ambiguous line instead of publishing it.
`moderation_call` records the outcome (allow, block, undecided, error,
disabled, budget, user_cap) with no player text and no raw address.
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

# Distinct from a content decline: the screen did not judge the words, so
# they are not shared. Same fictional register, same HTTP 200 pattern.
HOLD_LINE = (
    "The worlds hold those words for now. They are not shared. "
    "Say it another way, or try again later."
)

# Ideas is a community product surface, not the world's voice.
IDEAS_DECLINE = "Please revise the idea to keep the board respectful."
IDEAS_HOLD = (
    "This idea was not published. It could not be reviewed, so the board "
    "does not show it. Your draft is kept; try again later."
)

# Registration stays a clear choose-another refusal in both cases.
NAME_BLOCK = "that name can't be carried here — choose another name"
NAME_UNAVAILABLE = "names can't be registered just now — choose another"

PROFILE_DECLINE = "Please revise the public profile text."
PROFILE_HOLD = (
    "The public profile was not published. Those words could not be "
    "reviewed. Try again later, or save them without publishing."
)


def moderation_disabled() -> bool:
    return os.environ.get(DISABLE_MODERATION_ENV, "").strip() == "1"


def writes_shared_chronicle(seed: int) -> bool:
    """True when a CLI session would write the hosted canonical world.

    Local multi-world mode (``NESTED_WORLDS_CANONICAL_SEED`` empty, ``off``,
    or ``none``) is the operator terminal: ``speak`` there is not published
    to other players and stays unscreened. When a canonical seed is
    configured — including the launch default when the variable is unset —
    speech into that seed is shared text and uses :func:`screen`. An
    unreadable seed setting is treated as shared so the CLI does not
    publish past a broken boundary.
    """
    try:
        hosted = guard.canonical_seed()
    except ValueError:
        return True
    return hosted is not None and int(seed) == hosted


# ── Verdicts ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Verdict:
    allowed: bool
    tier: str  # clean | blocklist | classify | undecided | error | disabled | budget | user_cap
    outcome: str  # allow | block | undecided | error | disabled | budget | user_cap


_ALLOW_CLEAN = Verdict(True, "clean", "allow")
_BLOCK_LOCAL = Verdict(False, "blocklist", "block")


def player_line(verdict: Verdict) -> str:
    """In-fiction line for a shared-text refusal. Block and hold differ."""
    if verdict.outcome == "block":
        return DECLINE_LINE
    return HOLD_LINE


def http_body(verdict: Verdict, **extra) -> dict:
    """HTTP 200 body. A block is ``declined``; every other refusal is ``held``."""
    body = {"response": player_line(verdict), "ai": False}
    if verdict.outcome == "block":
        body["declined"] = True
    else:
        body["held"] = True
    body.update(extra)
    return body


def _moderation_log(outcome: str, surface: str) -> None:
    # No player text. Addresses are not logged here; a caller that needs one
    # hashes it with observability.hash_ip before it ever reaches this line.
    _log.info("moderation_call outcome=%s surface=%s", outcome, surface)


def screen(text: str, *, user_key: str | None = None, surface: str = "shared") -> Verdict:
    """Screen player-authored text before anyone else can see it.

    Empty text is allowed before the kill switch, so a blank published
    profile still saves. A local block is a finished decline and does not
    spend the action cap. The cap is charged only after that, so a clean
    line still spends it and a slur at the cap is declined. Ambiguous input
    then spends one classify call when the per-user and shared budgets allow
    it. Shared text is allowed only for a local clean verdict or a clear
    ALLOW. Every other result holds or declines it.
    """
    if not text or not str(text).strip():
        return _ALLOW_CLEAN
    if moderation_disabled():
        _moderation_log("disabled", surface)
        return Verdict(False, "disabled", "disabled")

    tier = _local_tier(text)
    if tier == "block":
        _moderation_log("block", surface)
        return _BLOCK_LOCAL
    if not guard.consume_moderation_action(user_key):
        _moderation_log("user_cap", surface)
        return Verdict(False, "user_cap", "user_cap")
    if tier == "clean":
        return _ALLOW_CLEAN

    # Ambiguous → one classify call, after the model-action cap and on
    # moderation's own budget. A model-action refusal does not spend that
    # budget. classify_content logs a finished verdict. This function logs
    # the single outcome=error line if that call, or anything around it, raises.
    if not guard.consume_model_action(user_key):
        _moderation_log("user_cap", surface)
        return Verdict(False, "user_cap", "user_cap")
    reservation = guard.moderation_reserve(user_key)
    if reservation != "ok":
        _moderation_log(reservation, surface)
        return Verdict(False, reservation, reservation)
    try:
        import consciousness
        outcome = consciousness.classify_content(text, surface=surface)
    except Exception:
        _moderation_log("error", surface)
        return Verdict(False, "error", "error")
    if outcome == "allow":
        return Verdict(True, "classify", "allow")
    if outcome == "block":
        return Verdict(False, "classify", "block")
    return Verdict(False, "undecided", "undecided")


def public_excerpt(text: str, *, user_key: str | None = None,
                   surface: str = "puzzle") -> str | None:
    """The player's words when they may be stored for others, else None.

    Puzzle correctness is decided by the caller. This only decides whether
    the free text may enter a shared record.
    """
    if screen(text, user_key=user_key, surface=surface).allowed:
        return text
    return None


def _local_name_ok(name: str) -> bool:
    words = _words(name)
    if set(words) & (_SEVERE_WORDS | _env_terms(EXTRA_BLOCK_ENV)):
        return False
    collapsed = "".join(words)
    squeezed = _squeeze(collapsed)
    if any(sequence in collapsed or sequence in squeezed for sequence in _EVASION_SEQUENCES):
        return False
    return True


def name_refusal(name: str) -> str | None:
    """None when the name may be registered. Otherwise a choose-another line.

    Names stay on the local tier: a short name has no prose context, so
    evasion sequences hard-block and nothing calls the classifier. Disabled
    moderation cannot judge a name, so none are registered. Name checks do
    not charge a per-user cap. A registration token is not an authenticated
    credential yet, and minting has no player key; charging either would
    open a bucket per unchecked string. ``/register`` stays on the write
    rate limit.
    """
    if moderation_disabled():
        _moderation_log("disabled", "name")
        return NAME_UNAVAILABLE
    if not _local_name_ok(name):
        _moderation_log("block", "name")
        return NAME_BLOCK
    return None
