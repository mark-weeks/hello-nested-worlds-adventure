# Working in parallel

*The owner (Mark Weeks) directed the adoption of these rules on 2026-11-14; they take
effect with the owner's merge of the pull request that added them. The binding rules are in
[AGENTS.md](../../AGENTS.md) ("Working in parallel"); this page is the procedure
behind them. The measurements are in
[the 2026-11-14 record](../evaluation/2026-11-14-parallel-agent-work.md).*

Three coding agents open pull requests under the owner's login, and GitHub Copilot
reviews them. Their code rarely collides. Their status documents always did: of 60
pairs of pull requests from different agents that were open at the same time, all 60
touched a shared status document and 9 touched any shared code or test file. The
rules here remove the shared writes and leave the code alone.

## Who takes what

Work is assigned by concern. A layer split does not fit this repository: replaying a
client / runtime / integrity split against pull requests #111 to #173, 45 changed
layered code; 22 of them touched a single layer and only 13 stayed inside the layer
the split would have given their author.

| Agent | Branches | Default concern | Covers |
|---|---|---|---|
| Codex | `codex/` | The player journey in `/app` | Entry and admission, the Act and Speak surfaces, block and report UI, accessibility, device checks |
| Grok Bot | `cursor/` | Model runtime and operations | Provider adapters, model policy and spend, the eval harness, timeouts and request guards, CI, release, backup and staging workflows, dependency locks, rollback |
| Claude Code | `claude/` | Integrity, safety and records | Moderation, sanctions, identity and honesty, session and credential lifetimes, puzzle secrecy, chronicle integrity, measurement, decision records, the status pull request |

- A feature stays one pull request owned by one agent, even when it needs a client
  change, an endpoint and a table.
- Where two concerns meet, the agent whose concern owns the server-side rule owns the
  pull request. A report button backed by a moderation rule is Claude Code's pull
  request.
- An explicit assignment from the owner wins over the defaults.

## Four single-writer resources and one placement rule

Before starting a batch, check the open pull requests for any of the four resources it
needs. Each pull request names the ones it holds under "Parallel work" in its
description. The earliest-opened pull request that names a resource holds it, drafts
included; a later one waits or asks the owner.

1. **Status documents.** `docs/CHANGELOG.md`, `docs/roadmap/README.md` and
   `docs/roadmap/beta-launch-checklist.md` (with `tests/test_beta_checklist_counts.py`)
   are written only by the status pull request. A feature writes a
   [changelog fragment](../changelog.d/README.md) with a `Status:` line for each
   change it calls for. In `README.md` and the runbook, a feature changes only the
   text it makes untrue or newly necessary. Standing counts and what-has-shipped lines
   are the exception: the feature records them as a `Status:` line even when it makes
   them untrue.
2. **The client bundle.** `static/app/assets/` holds a build whose file name carries a
   content hash, and `./scripts/check.sh` fails on a stale one, so two open pull
   requests that change `frontend/` cannot both be current. One at a time, whichever
   agent's concern the change falls under. Whoever changes `frontend/` commits the
   rebuild.
3. **Migrations.** Numbers are assigned at merge, so two open migrations claim the
   same number. One at a time. The pull request also updates the migration set pinned
   in `scripts/verify_wheel.py` and `tests/test_verify_wheel.py`, and renumbers if
   another migration merges first.
4. **Working rules.** `AGENTS.md`, `.claude/skills/`,
   `.github/pull_request_template.md`, `.claude/settings.json` and the guides that
   state these rules (this page, [coding-agents.md](coding-agents.md) and the
   [fragment README](../changelog.d/README.md)) change only in a pull request of their
   own that the owner asked for. A feature that needs a rule changed says so and waits.

The placement rule covers `server/handlers.py` and `main.py`. All three agents write
these files, so nobody can hold them. Keep new endpoint or command logic out of them:
put it in a `server/*_api.py` module (the pattern of `intervention_api.py`,
`ideas_api.py`, `participant_api.py` and `situation_api.py`) and register it in the
dispatch. Fixes to existing handlers are fine.

## The status pull request

Claude Code prepares it when the owner asks, and does not open one unprompted. The
owner normally asks within a working day of a merge. One status pull request may cover
several merged pull requests.

1. Cut the status branch from an up-to-date `main`, in a checkout with full history
   (`git fetch --unshallow origin main` in a cloud session), and run
   `python scripts/fold_changelog.py`. It moves every fragment into
   `docs/CHANGELOG.md`, newest first, deletes the fragments and prints their `Status:`
   lines.
2. Apply each `Status:` line to the document it names. When a checklist status that
   `tests/test_beta_checklist_counts.py` pins changes, update the test with it.
3. Refresh the standing counts the merged work changed: the top migration in the
   roadmap index, the migration count in `README.md`, and the like.
4. Restamp the verification line at the top of `docs/roadmap/README.md`.
5. Run `./scripts/check.sh`. The status pull request writes no fragment of its own.

## Review tiers

| Pull request | Review |
|---|---|
| Every pull request | Copilot when it opens, and once more on the final commit at the repository's default effort |
| Changes code | Plus one executing review by a different agent: Claude Code reviews Codex and Grok Bot; Codex reviews Claude Code |
| Trips a one-way door, or touches spend limits, moderation, authentication or deployment | The agent review, and the owner reads the irreversibility check |
| Changes the working rules | The same cross-agent review, and the owner's read. Copilot's review is not a check here, because it reads `AGENTS.md` from the pull request's own branch |

- **Request the second Copilot review when marking the pull request ready.** Copilot
  reviews once unless asked again. In a 22-pull-request sample its one review covered
  an earlier commit than the last on 16. That request is the only Copilot review an
  agent asks for: any other, a Max-effort one included, is the owner's to request.
- **When Copilot cannot run,** for example because its budget is spent, say so in the
  pull request and go on with the agent review. Its review of the pull request that
  added these rules failed that way, with HTTP 402.
- **Answer every finding in its thread:** fixed in a named commit, or declined with
  the reason. Copilot does not read replies; the reply is for the owner and for
  measuring reviewers.
- **Sign every review** with a footer naming the agent, as the review rule in
  `AGENTS.md` requires. In the sample 17 of 22 pull requests carried a review with no
  footer, so its author could not be identified.
- **A review the owner asked for always counts,** whichever agent wrote it. The owner
  may ask any agent to review any pull request.
- **One standing agent review per pull request.** Twelve of the 22 sampled pull
  requests had three or four reviewers. A further agent review needs the owner to ask.
- Findings that disclose an exploitable vulnerability in deployed code, a secret,
  player data or puzzle answers still go to the owner privately. Copilot cannot do
  that; keep such fixes out of a public pull request until the owner decides.

## What the owner holds

- Merging, and assigning a batch to an agent other than the default.
- The repository's Copilot settings and budget: approvals off, the default effort,
  and "Review new pushes" off in favour of the requested second review.
- Any Copilot review beyond the two above, a Max-effort one included.
- Asking for a further agent review, from any agent.

## Revisit when

- Two open pull requests conflict in a file that is not on the list above, twice in a
  month. Add the file or split it.
- The owner finds the status documents more than a week behind `main`.
- Grok Bot's discovery of `AGENTS.md` fails the checks in
  [coding-agents.md](coding-agents.md).
- GitHub changes how Copilot code review re-reviews, reads instructions or is priced.
