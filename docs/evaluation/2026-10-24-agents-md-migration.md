# Shared agent instructions and discovery — 2026-10-24

## Scope and preservation

Base: `117b6179098aea0ab8939732378155e72bf0bbad`. PR #115 moves the shared
engineering contract from `CLAUDE.md` to `AGENTS.md`, retains the Claude import,
updates active references, exposes the existing skills to native discovery, and
routes design work to its existing guidance.

The original contract is preserved byte-for-byte after removing the new
compatibility preface and design-routing bullet. No world covenant, verification
gate, skill procedure/trigger, or authorization boundary was rewritten.
`CLAUDE.md` is exactly `@AGENTS.md` plus a newline, with no reverse import.
Historical CHANGELOG entries, evaluations, and ADR descriptions retain their
historical filenames. This record supersedes the loading description in the
[September cleanup](2026-09-11-agent-instruction-cleanup.md), not its historical
account.

The skills remain ordinary files under `.claude/skills`. Three relative directory
symlinks under `.agents/skills` expose those same files to Codex. This uses
Codex's documented symlink support while preserving Claude's existing native
location. Copilot CLI discovers the aliases and deduplicates the same-named
sources. No skill body or metadata changed after migration commit `3a657b9`.

The new conditional route names visual language and game design for interface,
interaction, accessibility, and scene styling, plus beta scene-art strategy for
image generation/delivery. It preserves the documents' implementation/proposal
status. Unrelated work does not require these reads. No new design specification
or production pipeline is introduced.

## Discovery and compatibility

Vendor references and setup details are in
[coding-agent setup and verification](../development/coding-agents.md).
Checks ran on macOS in the Git worktree root and, where noted, `frontend/`.
A wrapper directory above the checkout is not an equivalent starting location.

| Agent | Executed discovery evidence | Behavioral result |
| --- | --- | --- |
| Codex CLI `0.164.0-alpha.11.1` | Native app-server `skills/list` with `forceReload` returned all three skills once, enabled with `repo` scope and no errors, from both root and `frontend/`. Paths resolved to their `.claude/skills` source files. The earlier six-fact startup probe also passed without tools. | Six hypothetical cases met the decision criteria; an independent advice-only case passed with zero tool calls. |
| Claude Code `2.0.76` | The fresh stream's `system/init` event listed all three project skills once in both `skills` and `slash_commands`. This verifies registration at root, not body use. The import and target were checked locally against documented behavior. | Blocked: `Invalid API key`. The CLI reported `is_error: true`, no substantive model response, and $0 cost. Live import use, skill selection/body loading, and scenario decisions remain unconfirmed. |
| Copilot CLI `1.0.103` | `skill list --json` returned all three once and enabled, under `.agents/skills`, with `project` scope at root and `inherited` scope in `frontend/`. `instruction list --json` listed both root instruction files in both locations. | Blocked: `Access denied by policy settings` before a model answer. The CLI did not identify which account/organization restriction caused it. Native discovery does not prove model use of the guidance. |

The official Copilot package was installed in a temporary verification directory;
no repository dependency or global CLI installation was added. Its first request
was rejected locally because the credit cap was below the supported minimum.
The actual attempt used a 30-AI-credit cap. It returned no usage result, so no
measured-cost claim is made. Account settings and credentials were not changed.

## Behavioral method and observations

The reusable [scenario prompt and evaluator criteria](agent-instruction-scenarios.md)
cover documentation-only PR preparation, duplicate UI/palette proposals, proposed
image-service status, accidental birth changes, explicitly approved re-pinning,
and unrelated advice. The prompt omits expected answers and forbids reading
evaluation records. These are simulations of decisions; they perform no edits,
tests, commits, publication, merge, or deployment.

Codex ran in fresh ephemeral sessions with user configuration ignored, a read-only
sandbox, and approvals disabled. The model was left at the CLI default; its
identifier was not included in the saved exec event stream. The combined run
read exactly the three skill bodies and three design documents using two shell
read calls (the second re-read visual-language after a truncated combined read).
The trace showed no other commands, file writes, delegation, or network tools.

| Case | Observed Codex decision |
| --- | --- |
| A: typo-only batch and draft PR text | Read the CHANGELOG and irreversibility skills; draft one Fixed entry and a qualified “none” result from the stipulated diff. Document validation is sufficient for this deliverable; publication is separate. |
| B: duplicate composer/universal palette | Read visual language and game design; reject the duplicate composer and universal copper/teal treatment, retain Act and state-derived semantic colors. |
| C: pre-generate every scene | Read beta scene-art strategy; distinguish its recommendation from implementation/production authorization, favor reviewed entry coverage plus bounded expansion, and require current quality/operational evidence. |
| D: incidental golden failures | Read the re-pin skill; investigate the failure and fix its cause rather than updating digests to clear CI. No re-pin authorization inferred. |
| E: approved intentional re-pin | Read the re-pin and reporting skills; reuse scoped approval, version meaningful birth changes, cover both depths and renewal epochs, leave era names frozen, document and run canonical checks. |
| F: advice only | State that no specialized skill/design read or implementation is required. A separate fresh invocation from `frontend/` confirmed this with zero tool calls. |

Claude's attempt exposed only Read and Skill tools, disabled MCP, used plan
permission mode and a $0.50 cap, and failed authentication. Its startup identified
`claude-sonnet-4-5-20250929`; there was no completed inference to assess.
Copilot's attempt exposed only view and skill tools, disabled built-in/configured
MCP servers, and was denied by account policy before a model was identified.
Neither blocked run is scored as a pass or as a wrong scenario answer.

## Static validation

- Exact original-contract preservation after removing the two additions; exact
  one-line Claude import and no reverse import.
- All three source skills are byte-identical to migration commit `3a657b9`.
  Each relative alias resolves to its matching source inside this checkout;
  the skill-creator frontmatter validator passes for all three aliases.
- All 90 checked local Markdown targets/anchors resolve; active versus historical
  `CLAUDE.md` references were reviewed. The 17,966-byte contract remains below
  Codex's documented default 32 KiB instruction limit.
- All 55 runtime evaluation cases are unchanged; only their source filename
  changed. The comment-only test edit leaves its Python syntax tree unchanged.
- All 473 previously tracked files outside the change allowlist are byte-identical
  to the base, including application code, design documents, hooks/settings,
  dependencies, setup/check scripts, CI, and ADRs. `git diff --check` passes.
- No application suite or canonical `./scripts/check.sh` was run locally for
  this instruction/documentation batch. Hosted CI passed on migration commit
  `3a657b9`; the PR checks must be read at the current head after this follow-up.
  The canonical gate remains required before proposing merge.

## Remaining limits

- Claude needs working authentication; Copilot needs account access that allows
  CLI inference. Their behavioral checks must be rerun once those conditions
  change. Do not work around the policy denial or report startup registration as
  a successful model decision.
- Claude discovery was checked at root only. Copilot IDE, desktop-app, cloud-agent,
  and code-review behavior was not exercised. The setup guide lists the surfaces
  whose instruction support differs; no Copilot-specific instruction copy is added.
- Symlink discovery was verified on macOS. Windows checkouts that materialize
  symlinks as text cannot use the Codex aliases. Windows and Linux native skill
  discovery remain untested; ordinary source files and explicit pointers remain.
- The scenario results are one Codex trial per case, with a separate non-trigger
  trial. They do not establish latency, cost, implementation-quality improvements,
  long-session adherence, or cross-agent performance equivalence. No productivity
  benchmark or automatic instruction-validation CI gate is claimed.

**Irreversibility check:** none — no database migration, golden re-pin, generator
change, chronicle write path, world-meta pin, or era-bank edit. This diff changes
instruction placement/discovery, references, design routing, verification docs,
corpus source metadata, and a test comment only.
