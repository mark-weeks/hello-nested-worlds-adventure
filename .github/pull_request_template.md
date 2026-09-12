<!-- One batch per PR. The CHANGELOG entry carries the full story; this
     body carries what the merge gate needs. -->

## Summary

<!-- What changed and why, with measured evidence — quantify surprises. -->

## Verification

<!-- Report checks actually run and their outcomes. For documentation-only work,
     include reference/consistency validation. For ./scripts/check.sh, include Ruff,
     Python/Vitest counts, bundle freshness, and installed-wheel smoke; name E2E
     results if run. Distinguish inspected, executed, skipped, and blocked checks.
     Drafts may name remaining verification; the canonical gate still applies
     before proposing merge. -->

## Irreversibility check

<!-- Required (CLAUDE.md "Verification and completion"; the irreversibility-check skill
     produces this). Check birth/golden changes, migrations, chronicle write paths,
     world-meta pins, and era banks against the actual base/head diff.
     For most PRs: "none — <why, from the diff>". If a door trips, list the
     existing ratification and any unresolved decision. Follow the authorization
     boundaries in CLAUDE.md "Verification and completion". -->

## CHANGELOG

<!-- Name the docs/CHANGELOG.md entry this PR adds (one entry per change),
     plus any docs/evaluation/ or docs/decisions/ file landing with it. -->
