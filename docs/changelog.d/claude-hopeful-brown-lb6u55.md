Section: Changed
Status: checklist S1 evidence: add that on a hosted world every shared line on Speak, agent voice, Ideas and a published profile is classified and only a clear ALLOW publishes it; an unreachable or undecided classifier, a spent cap, the spend ceiling and the AI kill switch hold it (`server/moderation.py`, `tests/test_every_line_moderation.py`); status stays Done
Status: checklist entry requirement 4 evidence: safe holds for unjudged shared text now cover locally clean hosted lines on those four surfaces (owner item 30); no rehearsal on the twin is claimed

- **Every shared line is classified on a hosted world** (`server/moderation.py`,
  `server/handlers.py`, `docs/decisions/ADR-004-day-one-data-policy.md`,
  `tests/test_every_line_moderation.py`). Owner item 30 (2026-11-18), batch C1.
  Where `NESTED_WORLDS_REQUIRE_MODEL_POLICY=1` or a model-policy file marks the
  world as hosted, a line on Speak, agent voice, Ideas or a published profile
  that will be stored or shown to others takes one classify call even when the
  local tier finds it clean. A clear ALLOW publishes it; BLOCK declines it; an
  undecided verdict, an unreachable classifier, a spent moderation or
  model-action cap, or the dollar ceiling holds it. With the AI kill switch on,
  hosted Ideas and profiles are held before any charge. Chat, puzzle free text,
  CLI speech, names and every local world keep the local-first rule. A sincere
  identity question is never silenced by a hold: it is answered under the
  local-first rule and not recorded; a decline still declines. A recorded
  hosted exchange now spends two model actions. Incident response, the
  deployment guide and the README rows for `DISABLE_AI` and
  `MODERATION_MODEL` now say so.
  **Verified:** `tests/test_every_line_moderation.py` 29 passed; the full
  `./scripts/check.sh` gate (see the pull request for counts).
  **Irreversibility check:** no one-way door — no migration, no stored-row
  rewrite, no birth or pin change; the rule is read from environment markers at
  request time and reverts with the code. It changes moderation, so it waits for
  the owner's read.
