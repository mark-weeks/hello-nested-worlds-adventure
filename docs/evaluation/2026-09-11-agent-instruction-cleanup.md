# Agent instruction cleanup — 2026-09-11

## Scope and findings

The reviewed base is `b32c3f5` on `main`. The repository has two root instruction
files, three skills under `.claude/skills/`, a Claude SessionStart hook and permission
configuration, and a PR template. No nested agent instructions, additional repository
skills, or separate Copilot/Cursor rules were found. The README contribution pointer
and CHANGELOG are the only other existing documents changed. This evaluation compares
that committed base with the final PR tree; the runtime reference and this audit are new.

At the base, voice/cache advice is standing context, skill descriptions repeat procedural
details, and completion and permission rules are mixed with merge preparation. This
cleanup routes occasional procedures by task and makes deliverable boundaries explicit.
The CHANGELOG has both `[Unreleased]` subsections and older unsectioned bullets at the top.
The skill now specifies `[Unreleased]` as the sole insertion region and this PR's correction
is under `### Fixed`; historical entries stay in place. Existing PR-specific merge
authorization and roadmap gates are retained.

## Result and preserved constraints

- `AGENTS.md` remains a short pointer to the shared `CLAUDE.md` contract. Setup commands
  live in that contract, and an already-loaded copy need not be read again.
- Advice, plans, drafts, implementation, verification, and publication have distinct
  outcomes. Authorized implementation includes relevant checks, inspection of affected
  user-visible behavior, and correction of failures introduced by the change. A blocker
  stops dependent work; independent preparation continues.
- Irreversibility checks use the actual local batch or PR base/head, including new files.
  Re-pin ratification requires the owner's explicit approval for that specific pin change
  in the current task or PR; a historical ADR or CHANGELOG is not standing approval.
  That approval is reused for unchanged scope; unresolved decisions retain the human gate.
  Publication requires authorization, merge authorization names the particular PR, and
  auto-merge remains forbidden.
- The re-pin procedure retains versioning, both depth-6 and full-depth coverage, renewal
  epochs 1 and 2, frozen era banks, and the canonical check. Accidental golden failures
  require fixing code. Skill names and explicit invocation/permission settings are unchanged.
- World covenants are byte-for-byte unchanged. Birth records remain immutable; the text
  now distinguishes existing overlays/chronicled deltas from the broader proposed evolution
  grammar. The determinism explanation follows served state; its prohibitions and Wayback
  contract are unchanged. Golden guidance recognizes existing ratification.
- Canonical seed ownership, seal escape, human/agent progress separation, append-only
  history, sanctioned maintenance paths, additive migrations, backups, and deployment
  gates remain. Conditional ADR routing retains product acceptance gates. ADR-019–022
  remain marked Proposed: their implementation references guide authorized maintenance,
  without ratifying proposals or authorizing broader designs. Enforcing invariant suites
  are named beside the focused-check guidance.
- [Voice/cache diagnosis](../development/agent-runtime.md) preserves the prefix-length
  guards and their historical rationale, using source configuration and current model
  documentation instead of presenting one threshold as universal.

## Instruction loading and measurement

The loading review used current official documentation on 2026-09-11. It is an inspection
of documented behavior and repository paths, not a fresh-session integration test.

| Agent surface | Loading behavior and repository routing |
| --- | --- |
| Claude Code | Loads applicable `CLAUDE.md` files; ordinary project skills expose descriptions before their bodies are invoked. The runtime reference is a conditional path, not an import. Native `@path` imports would load the referenced content at startup. [Memory](https://code.claude.com/docs/en/memory), [skills](https://code.claude.com/docs/en/skills). |
| Codex | Discovers `AGENTS.md` along the repository-root-to-working-directory path, subject to overrides and configured limits. This entry point explicitly requests the shared contract. Native repository skill discovery uses `.agents/skills`, so these `.claude/skills` procedures are routed by file path; this cleanup does not claim native Codex discovery or add a second catalog. [Instructions](https://learn.chatgpt.com/docs/agent-configuration/agents-md), [skills](https://learn.chatgpt.com/docs/build-skills). |
| Copilot | Cloud agent and CLI support these agent instruction files; support differs across IDE/chat/review surfaces. CLI can load both root files and immediately expands `@path` references. The pointer avoids repeating the contract. [Support matrix](https://docs.github.com/en/copilot/reference/custom-instructions-support), [CLI loading](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-custom-instructions). |

No automatically imported reference was substituted for removed text. Existing Claude
hook/permission configuration stays unchanged. Global and managed instructions are outside
this repository; they can still require additional reading or confirmations. Repository
cleanup cannot override that loading or those controls.

Counts use whitespace-delimited words from the fetched base and final files, excluding
YAML keys for skill descriptions:

| Reading surface | Base | Final |
| --- | ---: | ---: |
| Shared contract (`CLAUDE.md`) | 2,263 | 1,897 |
| Entry point plus shared contract | 2,351 | 1,951 |
| Three skill descriptions combined | 125 | 44 |

The entry point plus contract decreases by 400 words (17.0%). Claude's shared-contract
reduction is 366 words (16.2%); skill descriptions decrease by 81 words (64.8%). These
surfaces have different loaders and should not be presented as a universal startup token
count. Detailed procedures remain available on demand; there is no measured claim about model quality, latency, cost, or interruption frequency.

## Validation performed

- All three skills pass the Skill Creator structural validator. YAML comparison against
  the base confirms the same names and unchanged metadata other than descriptions.
  Each contains only `name` and `description`; no invocation, tool, or permission override
  was added or removed.
- Local Markdown links, concrete code-formatted file references, and named ADRs resolve.
  Dynamic filename examples and ADR ranges were reviewed against their directories.
- Byte comparisons preserve the world-covenant section, canonical-seed and hinge rules,
  era/continuity rules, determinism prohibitions, and Wayback contract. The three edited
  invariant passages were reviewed for intent: immutable birth versus mutable state,
  reuse of ratification, and deterministic rendering of served state.
- Claude settings/hook, setup/check scripts, CI/release/backup workflows, and runtime pins
  match the base byte-for-byte. Removing this PR's single entry from `[Unreleased]` →
  `### Fixed` reproduces the base CHANGELOG byte-for-byte. The ten-file diff contains only
  guidance and related documentation. `git diff --check` passes.
- Local application suites were not run for this documentation-only cleanup. The canonical
  `./scripts/check.sh` and optional `ENFOLDED_E2E=1` path were inspected, not executed.
  The required canonical gate before proposing merge is retained; this delivery is a draft
  PR. CI results are reported on the PR, separately from local document validation.

## Representative scenario review

These fifteen cases were manually traced through the final written instructions. All are
consistent with the intended routing and completion boundaries; no independent agent runs
or production operations were performed for these scenarios.

| Request or condition | Applicable reading and expected boundary |
| --- | --- |
| Explain per-node puzzle difficulty | Shared covenant and relevant source; answer the question. No skill, code edit, CHANGELOG, or merge workflow is required. |
| Correct a documentation typo | Edit and validate the document; use CHANGELOG/irreversibility skills when recording the batch. No re-pin or runtime reference. |
| Implement an endpoint fix whose regression test fails | Inspect the affected behavior, fix the introduced failure, rerun affected checks, and preserve the canonical pre-merge gate. A first patch is not completion. |
| Prepare a documentation draft PR | CHANGELOG and irreversibility skills; document actual checks and gaps. Publish only with authorization, preserving merge/deploy boundaries. |
| Assess an uncommitted batch containing a new file | Include staged, unstaged, and new files in the local diff assessment; exclude unrelated work. No remote PR discovery is required. |
| Intentional birth change with explicit owner approval for these pins in the current task or PR | Re-pin skill; reuse that specific approval, version the change, cover both depths and renewal epochs, leave era banks frozen, run the canonical check. |
| Accidental RNG change breaks golden digests | Diagnose and fix code. A failing pin alone does not activate an authorized re-pin. |
| Proposed re-pin changes the approved pins or continuity consequences | Seek only the new consequential decision before changing those pins; continue independent analysis. |
| Only an old ratified ADR or historical re-pin entry exists | Neither authorizes new pins. Ask for the owner's explicit approval for the current pin change before re-pinning. |
| Record a batch when the CHANGELOG has top-level bullets and release sections | Use the first `[Unreleased]` and its applicable Added/Fixed subsection. This cleanup belongs in Fixed; older entries remain untouched. |
| Maintain implemented M1–M4 behavior described by a Proposed ADR | Read the affected record and enforcing code/tests within the authorized scope. Preserve existing guarantees; the pointer does not ratify the proposal or authorize broader work. |
| Rename existing era display banks | Frozen-bank covenant applies. The re-pin skill cannot authorize this; the ADR/materialization boundary remains. |
| Diagnose flat voices or change cache structure | Runtime reference and affected prompt tests; check applicable live-model assumptions and disclose unavailable live evidence. Unrelated edits do not load this reference. |
| Change a WebSocket/API external contract | Verify the changed interface against current official docs or a live run before implementation. Do not review unrelated external systems. |
| Green PR after authorization to merge a different PR | No merge authorization carries over; no auto-merge. Prepare the current PR for review and retain the specific owner gate. |

Remaining validation limits are fresh-session loading and measured agent behavior. A future
comparison would hold model, tools, and repository snapshot constant and score correctness,
missed boundaries, interruptions, and user corrections. Shorter reading and structural
validation alone do not establish improved behavior.

**Irreversibility check:** none — guidance and related documentation only; no migration,
golden re-pin, generator change, chronicle write path, world-meta pin, or era-bank change.
