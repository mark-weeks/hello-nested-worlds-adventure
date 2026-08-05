<!-- One batch per PR. The CHANGELOG entry carries the full story; this
     body carries what the merge gate needs. -->

## Summary

<!-- What changed and why, with measured evidence — quantify surprises. -->

## Verification

<!-- ./scripts/check.sh outcome: Ruff, N Python passed, N Vitest passed,
     bundle byte-fresh, installed-wheel smoke. Note if ENFOLDED_E2E=1 ran. -->

## Irreversibility check

<!-- Required (CLAUDE.md "Working rules"; the irreversibility-check skill
     produces this). Does this diff re-pin a golden world, add or alter a
     migration, or add a world_mutations write path / chronicle row?
     For most PRs: "none — <why, from the diff>". If a door trips, list the
     1–2 questions the human gate must answer, hardest first. -->

## CHANGELOG

<!-- Name the docs/CHANGELOG.md entry this PR adds (one entry per change),
     plus any docs/evaluation/ or docs/decisions/ file landing with it. -->
