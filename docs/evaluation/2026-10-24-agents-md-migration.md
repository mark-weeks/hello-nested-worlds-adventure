# Shared instructions in AGENTS.md — 2026-10-24

## Scope

Base: `117b6179098aea0ab8939732378155e72bf0bbad`. Move the shared engineering
contract from `CLAUDE.md` to `AGENTS.md`, retain the Claude import, and update
active references. This is a content-preserving migration, not a rewrite of the
world rules, verification gates, skills, or authorization boundaries.

The old `CLAUDE.md` is preserved byte-for-byte in `AGENTS.md` after removing the
new compatibility preface. That preface carries forward the old entry point's
conditional-reading and shared-maintenance instructions. `CLAUDE.md` is exactly
`@AGENTS.md` followed by a newline. There is no reverse import or duplicated
contract to maintain.

Active references in the README, contribution guide, PR template, two skills,
standing continuity roadmap, evaluation corpus source list, and one test comment
now name `AGENTS.md`. Existing CHANGELOG entries, dated evaluations, and ADR
passages describing earlier decisions retain their historical filenames. This
record supersedes the instruction-loading description in the
[September cleanup](2026-09-11-agent-instruction-cleanup.md), not its account of
that earlier work. Skill locations and triggers remain unchanged.

## Compatibility

Vendor documentation was checked on 2026-10-24. Start a new session in the Git
checkout root or inside it; a wrapper directory above the checkout is not an
equivalent project root.

| Agent | Documented route | Verification in this batch |
| --- | --- | --- |
| Codex | Discovers `AGENTS.md` on the project-root-to-working-directory path. [Instructions](https://learn.chatgpt.com/docs/agent-configuration/agents-md). | Fresh Codex CLI `0.164.0-alpha.11.1` probe passed from the checkout root, using a read-only sandbox and no user configuration. The event stream contained no tool calls. |
| Claude Code | `CLAUDE.md` expands `@AGENTS.md`. Current releases also offer direct `AGENTS.md` support; keeping the import covers older releases. [Import guidance](https://code.claude.com/docs/en/memory#share-one-file-with-other-coding-tools). | Import target and complete contract checked locally. Installed CLI `2.0.76` predates direct support. A fresh probe with tools disabled and a $0.50 cap stopped at authentication (`Invalid API key`) before model output and reported $0 cost. Live loading remains unconfirmed. |
| GitHub Copilot | CLI discovers both root files and expands relative `@` imports. [CLI instructions](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-custom-instructions). | File placement and import graph checked against documented behavior. No live Copilot session was exercised; a standalone CLI was unavailable in the validation environment. |

Copilot's [support matrix](https://docs.github.com/en/copilot/reference/custom-instructions-support)
also lists `AGENTS.md` for VS Code chat, the cloud agent, and GitHub.com code
review. Some other surfaces accept only `.github/copilot-instructions.md`.
This migration does not add support for those surfaces or claim that every
Copilot integration loads the contract. It adds no competing instruction copy.

The Codex probe prohibited tools and asked only about repository instructions
already loaded at startup. It correctly returned the canonical filename, the
three sanctioned chronicle maintenance mechanisms, the specific golden re-pin
approval scope, provider/model optionality, the conditional voice-reference path,
and the final rule to update the matching skill and PR template when a working
rule changes. This checks sampled startup-context coverage, not universal
instruction adherence or improved coding performance.

## Validation

- Exact preservation comparison against the base contract, allowing only the
  added compatibility preface.
- Exact one-line import check, existing target, no reverse import, and 17,428
  project-instruction bytes below Codex's documented 32 KiB default limit.
- All 81 local Markdown targets/anchors resolve for the migrated contract and changed
  references; remaining `CLAUDE.md` mentions reviewed as compatibility or history.
- Skill metadata unchanged; bodies differ only in the canonical filename.
- Evaluation JSON parses; all 55 cases and all fields except the source filename
  are unchanged. The test module's Python syntax tree is unchanged.
- All 473 tracked files outside the change allowlist are byte-identical to the
  base, including application source, hooks/settings, setup/check scripts, CI,
  existing dated evaluations, and ADRs. `git diff --check` passes.
- No application suites were run for this documentation/reference migration.
  The existing canonical pre-merge gate remains required; no merge readiness or
  deployment claim is made.

**Irreversibility check:** none — no migration, golden re-pin, generator change,
chronicle write path, world-meta pin, or era-bank edit. The diff moves guidance
and updates references, corpus source metadata, and a test comment only.
