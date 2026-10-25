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

The reusable [scenario prompt and evaluator criteria](../development/agent-instruction-scenarios.md)
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
- Checked local Markdown targets/anchors resolve; active versus historical
  `CLAUDE.md` references were reviewed. The 17,966-byte contract remains below
  Codex's documented default 32 KiB instruction limit.
- The entire runtime evaluation corpus, including its historical source label,
  is byte-identical to the base. Its digest remains
  `5b88b98630f33e7a24cc53312763dc2a6277e1f47f6ab8f27e91311bed4b3202`.
  The comment-only test edit leaves its Python syntax tree unchanged.
- Previously tracked files outside the change allowlist are byte-identical
  to the base, including application code, design documents, hooks/settings,
  dependencies, setup/check scripts, CI, and ADRs. `git diff --check` passes.
- Hosted Python, frontend, browser, and Copilot-review checks passed on `f2de204`.
  The review follow-up runs focused instruction-configuration and evaluation
  harness tests locally; it does not claim a local full application suite or
  canonical `./scripts/check.sh` run. The canonical gate remains required before
  proposing merge; inspect hosted checks at the current PR head.

## Review follow-up

The corpus metadata concern was confirmed against `evals.harness.digest`,
`review_packet`, and `compare`: even a source-label change affects the digest
used to match historical runs. The first migration changed it from `5b88b986…`
to `22a9447a…` without changing cases or version. The corpus is restored
byte-for-byte; its old `CLAUDE.md` label is historical provenance. Changing the digest algorithm
or versioning policy is separate evaluation-tooling work. A fixture run using
the base corpus reproduced both pre-fix errors: `review corpus differs from the
run` and `comparison mismatch: corpus_sha256`. Its review packet and a paired
fixture comparison both succeeded with the restored corpus. No externally stored
provider runs were modified or inspected.

The existing Codex trace was checked again: it reads only the three skill bodies
and the three design documents, never the answer key or dated evaluations.
The reusable scenario guide now lives under `docs/development/` and explicitly
invalidates a trial if its trace shows answer-key/evaluation reads. A readable
answer key is not a security boundary; traces are required evidence here.

All six vendor-reference pages and linked section anchors were checked again.
GitHub documents import expansion and identical-instruction deduplication; the
inventory alone cannot prove double-loading. The expanded Copilot inference
payload remains unverified after the earlier account-policy denial. No fresh
Claude or Copilot inference was attempted in this review follow-up; no changed
authentication or policy condition was established.

`tests/test_agent_instructions.py` adds guards for the exact Claude import,
complete matching relative skill aliases, and frontmatter identity/description.
They run in existing pytest CI and the canonical script, without new dependencies.
Local Python 3.11 verification passed all 81 focused cases: 78 evaluation-harness
tests and 3 instruction-configuration tests; Ruff passed on the new test module.
An isolated clean configuration passed, while seven deliberately malformed
configurations failed the intended guards: import drift, a plain-text alias, a
dangling target, a wrong target, a missing alias, an extra copy, and a mismatched
frontmatter name. These checks do not verify model adherence.
The changelog stays under Fixed because this corrects instruction discovery; its
entry now links to this evidence instead of repeating the full verification table.
The cited ADR-004/005/006 filename references describe historical practices and
changes, so they remain historical. Their old provider claims are not current
endorsements under the preserved provider-optionality contract.

## Remaining limits

- Claude needs working authentication; Copilot needs account access that allows
  CLI inference. Their behavioral checks must be rerun once those conditions
  change. Do not work around the policy denial or report startup registration as
  a successful model decision.
- Claude discovery was checked at root only. Copilot IDE, desktop-app, cloud-agent,
  and code-review surfaces did not run the controlled scenarios. The successful
  Copilot PR review on `f2de204` does not expose its instruction-loading trace. The setup guide lists the surfaces
  whose instruction support differs; no Copilot-specific instruction copy is added.
- Symlink discovery was verified on macOS. Windows checkouts that materialize
  symlinks as text cannot use the Codex aliases. Windows and Linux native skill
  discovery remain untested; ordinary source files and explicit pointers remain.
- The scenario results are one Codex trial per case, with a separate non-trigger
  trial. They do not establish latency, cost, implementation-quality improvements,
  long-session adherence, or cross-agent performance equivalence. No productivity
  benchmark is claimed. Structural instruction checks now run in existing Python
  CI; they do not establish native loading or model behavior.

**Irreversibility check:** none — no database migration, golden re-pin, generator
change, chronicle write path, world-meta pin, or era-bank edit. This diff changes
instruction placement/discovery, references, design routing, verification docs,
configuration regression checks, and a test comment only. The runtime evaluation
corpus is unchanged from the base.
