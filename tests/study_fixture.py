"""Explicit adult enrollment for normal invited-study server journeys."""
from persistence import participation as consents
from server import participation


def acknowledge_current_study(key: str) -> None:
    """Record this synthetic adult's agreement to the real current notice.

    Entry/refusal tests deliberately do not call this helper. The stored notice
    includes the affirmative 18+ statement, just as the participation endpoint's
    validated acknowledgement does.
    """
    current = participation.notice()
    if current["required"]:
        assert current["ready"]
        consents.accept(key, current["revision"], participation.snapshot(current))
