<!-- One batch per PR. The CHANGELOG entry carries the full story; this
     body carries what the merge gate needs. -->

## Summary

<!-- What changed and why, with measured evidence — quantify surprises. -->

## Agreed scope and contribution

<!-- Link the issue and maintainer agreement before implementation. Owner-directed
     maintenance may cite that direction instead of inventing an issue. Explain
     material AI assistance, known limitations, and reporting/verification credit.
     See CONTRIBUTING.md for rights and third-party attribution requirements. -->

<!-- For player-facing changes: identify the existing surface extended or replaced.
     Check that no parallel control duplicates it and no player can force another
     human or AI player's actions. Validate scale-native effects and presentation. -->

<!-- For participation gates: verify that consent-required 428 and participation
     configuration/check 503 are plain operational notice decisions, with a way
     to review the notice. Keep them distinct from authored world voices and
     preserve in-fiction fallbacks for model, moderation and gameplay outcomes. -->

<!-- For provider/model changes: identify the task, provider and exact model/version;
     link comparative quality, capability, latency/reliability and total-cost evidence
     under ADR-034. State adapter/config compatibility, rollback and unverified live
     behavior. Neutral wording or mocked calls do not establish provider portability. -->

## Parallel work

<!-- AGENTS.md "Working in parallel". Name any single-writer resource this batch holds:
     the client bundle (frontend/ and static/app/), a migration, or the working rules.
     Confirm it leaves docs/CHANGELOG.md, docs/roadmap/README.md and
     docs/roadmap/beta-launch-checklist.md alone, or say that it is the status pull
     request. Name the review tier it falls in and the agent that reviews it under
     the standing assignment. -->

## Verification

<!-- Report checks actually run and their outcomes. For documentation-only work,
     include reference/consistency validation. For ./scripts/check.sh, include Ruff,
     Python/Vitest counts, bundle freshness, and installed-wheel smoke; name E2E
     results if run. Distinguish inspected, executed, skipped, and blocked checks.
     Drafts may name remaining verification; the canonical gate still applies
     before proposing merge. -->

## Irreversibility check

<!-- Required (AGENTS.md "Verification and completion"; the irreversibility-check skill
     produces this). Check birth/golden changes, migrations, chronicle write paths,
     world-meta pins, and era banks against the actual base/head diff.
     For most PRs: "none — <why, from the diff>". If a door trips, list the
     existing ratification and any unresolved decision. Follow the authorization
     boundaries in AGENTS.md "Verification and completion". -->

## CHANGELOG

<!-- Name the docs/changelog.d/ fragment this PR adds (one entry per change, with a
     Status: line for each status-document change it calls for), plus any
     docs/evaluation/ or docs/decisions/ file landing with it. -->
