Section: Fixed

- **`python main.py speak` screens lines into the hosted world before recording
  them** (`main.py`, `tests/test_shared_text_fail_closed.py`). `cmd_speak` wrote a
  `PLAYER_SPEAK` chronicle row without calling `server.moderation.screen`, although
  the moderation module's own rule says CLI speech into the canonical world is shared
  text, and interactive play (`interface._speak_to`) already followed it. Other voices
  read those rows as history. The command now applies the same gate as interactive
  play: when `writes_shared_chronicle(seed)` is true, the line goes through
  `screen(..., surface="cli")` before the voice is called. A local block prints the
  authored decline line; any hold prints the hold line; neither calls the voice nor
  writes a row. Local multi-world mode stays the unscreened operator terminal. Found
  while reviewing the C1 every-line moderation work; not part of that pull request.
  **Verified:** the new behaviour test drives `main.cmd_speak` with a blocklisted
  line, a line held by disabled moderation, a clean line and a local-mode line; it
  fails on the previous `main.py` (the blocked line was voiced and recorded) and
  passes with the fix. `./scripts/check.sh` passed: Ruff clean, 4,343 Python tests
  passed with one skip, 258 client unit tests passed, bundle freshness and the
  installed-wheel smoke test passed; browser E2E was not run (Chromium suite is
  opt-in).
  **Irreversibility check:** none — no migration, no golden re-pin, no world-meta or
  era-bank change, and no new `world_mutations` write path: the diff only adds a
  screen in front of the existing `record_mutation` call in `cmd_speak`, so it can
  write fewer rows, never new ones. It touches moderation, so it waits for the
  owner's read.
