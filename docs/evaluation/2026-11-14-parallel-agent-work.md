# Parallel work across three coding agents, Copilot review and Claude Code defaults

*2026-11-14. Measured on `main` at `09c529b` (#170) with #171, #172 and #173 open.
Findings, with the rules the owner (Mark Weeks) adopted from them on 2026-11-14. The
binding text is in [AGENTS.md](../../AGENTS.md) ("Working in parallel"), the procedure
in [the parallel-work guide](../development/parallel-work.md), and the Claude Code
defaults in [coding-agents.md](../development/coding-agents.md).*

## Takeaway

Pull requests from different agents collide in the status documents, not in the code.
Of 60 pairs of pull requests from different agents that were open at the same time,
all 60 changed `docs/CHANGELOG.md` and 9 shared any code or test file. A split by
layer does not fit how the work is shaped, so the adopted rules assign work by concern,
give four resources one writer at a time, and keep new logic out of the two files all
three agents write. Copilot already reviews nearly every
pull request, precisely but once, and usually not the last commit.

## What was asked

How to delegate work across Claude Code, Codex and Grok Bot so they can build in
parallel without conflicting; how to build GitHub Copilot review into that; and when
Claude Code should run Opus or Fable, at what effort, and with ultracode on or off.

## Data and method

[`overlap.py`](2026-11-14-parallel-agent-work/overlap.py) recomputes the tables and the
pair, replay and sample statistics of sections 1 to 4 from two snapshots, and needs
neither network nor git history. The trial merges, the migration #172 holds, Copilot's
presence on 62 of 63 pull requests and the Max-effort details were read from git and
GitHub directly and are not in the snapshots:

```bash
python docs/evaluation/2026-11-14-parallel-agent-work/overlap.py
```

- [`prs.json`](2026-11-14-parallel-agent-work/prs.json): the 63 pull requests from
  #111 to #173 (60 merged, 3 open). The authoring agent comes from the branch prefix:
  `claude/` 27, `cursor/` 24 (Grok Bot, confirmed by the owner), `codex/` 12. Created
  and merged times come from GitHub. Changed files come from git: each merge commit
  against its first parent, and each open pull request against its merge base.
- [`review_sample.json`](2026-11-14-parallel-agent-work/review_sample.json): 22 of
  the 63. Eight (#111 to #114, #147 to #150) were read thread by thread, with each
  finding's outcome. Fourteen (#120, #123, #124, #129, #134, #152, #153, #158, #161,
  #166, #169, #170, #172, #173) were read from review summaries only, so their counts
  are what the review bodies state. The sample was chosen to cover all three authors
  and both ends of the period; it is not random.

The reading was done by subagents through the GitHub API and their returned counts
were not re-derived by hand. A fuller pass over all 63 was started and abandoned when
it exhausted the session's usage limit (section 7).

## Findings

### 1. Where pull requests collide

Share of the 60 merged pull requests that changed each file:

| File | Pull requests | Share |
|---|---|---|
| `docs/CHANGELOG.md` | 60 | 100% |
| `README.md` | 25 | 42% |
| `docs/roadmap/README.md` | 22 | 37% |
| `server/handlers.py` | 21 | 35% |
| `docs/infrastructure/fly-deployment.md` | 20 | 33% |
| `docs/roadmap/beta-launch-checklist.md` | 19 | 32% |
| `main.py` | 18 | 30% |

Sixty pairs of pull requests from different agents were open at the same time. All 60
shared `docs/CHANGELOG.md`. Nine shared any code or test file, most often
`server/handlers.py` (3 pairs). Up to 10 pull requests were open at once.

Trial merges of the three open pull requests agree. #172 with #173 conflicts only in
the launch checklist; #173 with #171 conflicts in the changelog and the checklist;
#172 with #171 merges cleanly. #172 and #173 both edit `server/handlers.py` and
`main.py` without conflict.

Three resources allow one writer by construction: the built client bundle, whose file
name carries a content hash and whose freshness `./scripts/check.sh` enforces; the
next migration number, assigned at merge (#172 holds `0032`); and the checklist
statuses pinned by `tests/test_beta_checklist_counts.py`.

Pairs from the same agent overlap more: of 76 same-agent pairs open together, 22
shared a code or test file. The adopted rules do not address that.

### 2. A split by layer does not fit

Replaying a client / runtime / integrity split (the layers are defined in
`overlap.py`) against all 63: 45 changed layered code, 22 of them touched a single
layer, and 13 stayed inside the layer the split would have given their author. A
first statement of this result in the working session said 13 stayed "in one layer";
that wording was wrong and is corrected here. This is one candidate split, not a
search over splits.

### 3. Who writes what

Each agent has a centre of gravity, by concern more than by directory.

| File | Claude Code | Codex | Grok Bot |
|---|---|---|---|
| `server/handlers.py` | 7 | 5 | 9 |
| `main.py` | 9 | 2 | 7 |
| `consciousness/runtime.py` | 2 | 2 | 9 |
| `server/__init__.py` | 1 | 0 | 7 |
| `evals/harness.py` | 2 | 2 | 5 |
| `server/observability.py` | 5 | 0 | 0 |
| `consciousness/honesty.py` | 2 | 0 | 0 |
| `persistence/sanctions.py` | 2 | 0 | 0 |

By layered file changes, Codex is 61% client, Grok Bot 67% runtime and Claude Code 42%
integrity and 38% client. Grok Bot has opened no pull request since #153 merged on
2026-11-07; #172, on model spend, is Codex's.

### 4. Review, from the sample

| Reviewer | Pull requests reviewed | Rounds | Findings | Per pull request | Found nothing on |
|---|---|---|---|---|---|
| Copilot | 22 | 22 | 32 | 1.5 | 10 |
| An agent with no footer | 17 | 25 | 131 | 7.7 | 0 |
| Claude Code | 14 | 14 | 118 | 8.4 | 0 |
| Codex | 6 | 6 | 5 | 0.8 | 3 |

- Copilot reviewed every sampled pull request exactly once. On 16 of the 22 its
  review covered an earlier commit than the last one.
- In the eight read thread by thread, all 10 of Copilot's findings were fixed and 7
  were substantive; of the agent reviewers' 55 findings, 50 were fixed and 32 were
  substantive. No finding from any reviewer was shown to be wrong.
- Copilot ran at Balanced on most pull requests. It ran at Max on #134 and #172 and
  stated three High-severity issues across the two.
- Twelve of the 22 had three or four reviewers. Seventeen carried a review with no
  footer naming its agent, which the standing review rule requires; its author could
  not be identified.
- No review signed by Grok Bot appears in the sample.

### 5. Copilot code review: documented behaviour

GitHub's documentation could not be opened from the session (the host was outside its
network allowlist). The statements below come from search summaries of docs.github.com
and github.blog, checked by a second pass that was asked to refute them. Treat them as
reported, not read.

| Statement | Second pass |
|---|---|
| Reviews a pull request once unless asked again or "Review new pushes" is enabled | Supported |
| Effort levels Lite, Balanced (default since 2026-10-02) and Max (public preview); about $0.25, $1.50 and $10 per review; selectable per request | Supported |
| Billed by usage since 2026-06-01; an automatic review is charged to the pull request's author; no Actions minutes on public repositories | Supported |
| Approvals are off by default; once an admin enables them they can count toward merge requirements; new commits dismiss an approval | Partly: whether enabling and counting are separate switches was not confirmed |
| Reads `.github/copilot-instructions.md`, path-specific instruction files, `AGENTS.md`, `CLAUDE.md`, `GEMINI.md` and `REVIEW.md` | Supported |
| No hard length limit on instruction files | Partly: a 4,000-character cutoff existed until 2026-06-12 |
| Reads instructions from the pull request's head branch since 2026-07-17 | Reported by the second pass |
| Skips lockfiles and bundled or minified JavaScript; does not read replies in its threads | Reported by the second pass |

Sources: [Copilot code review](https://docs.github.com/en/copilot/concepts/agents/code-review),
[custom instruction support](https://docs.github.com/en/copilot/reference/custom-instructions-support),
[excluded files](https://docs.github.com/en/copilot/reference/review-excluded-files),
and the changelog entries of
[2026-07-17](https://github.blog/changelog/2026-07-17-copilot-code-review-customization-and-configurability-improvements/),
[2026-10-02](https://github.blog/changelog/2026-10-02-copilot-code-review-api-support-and-new-default-effort-level/)
and [2026-10-28](https://github.blog/changelog/2026-10-28-copilot-code-review-merge-with-confidence-with-max-and-approvals/).

What the repository itself shows agrees on two points: Copilot's single review per
pull request (section 4), and its presence on 62 of the 63 pull requests, every one
but #130.

### 6. Claude Code: model and effort

- Anthropic's published prices are $4 and $20 per million input and output tokens for
  Opus 5.5, and $8 and $40 for Fable 5.2.
- Anthropic's own pages describe Opus 5.5 as the model for everyday coding and Fable
  5.2 as the one for ambitious open-ended work. The
  [Claude Code model configuration page](https://code.claude.com/docs/en/model-config),
  read directly, gives `medium` as the default effort for both and `effortLevel` and
  `model` as the settings keys.
- Commit trailers on `main` credit 21 Claude Code pull requests from #137 to #166 to
  Opus 5.5 alone, and #167 and #168 to Fable 5.2. The five Opus-written pull requests
  in the review sample (#147 to #149, #158, #166) drew no High-severity finding. Seven
  of the 16 sampled pull requests written by Codex or Grok Bot drew at least one
  (#114, #124, #134, #152, #153, #161, #172; read from the review bodies, not
  recomputed by the script). The
  pull requests differ in scope and in who reviewed them, so this does not rank the
  agents or the models.
- No effort level is recorded anywhere in the repository. The effort guidance is
  judgement from Anthropic's published advice.

### 7. Ultracode, as observed

The session ran with ultracode on. Its first review pass launched 47 subagents across
three concurrent workflow runs; 2 finished before the session's 5-hour usage limit
stopped the rest. After the limit reset, a redesigned pass read 14 pull requests with
2 subagents, 282,471 tokens and 83 seconds. The container had 4 CPUs, which capped
each workflow at two agents at a time. Splitting one run into three to get around
that cap is what exhausted the limit.

## What the owner adopted

| Rule | Where it lives |
|---|---|
| Work is assigned by concern; a feature stays one pull request | `AGENTS.md`, "Working in parallel" |
| Four single-writer resources, and no new endpoint logic in `server/handlers.py` or `main.py` | `AGENTS.md`; procedure in the parallel-work guide |
| Changelog fragments and the status pull request | `AGENTS.md`, the `changelog-entry` skill, `docs/changelog.d/README.md`, `scripts/fold_changelog.py` |
| Review tiers, the standing cross-agent review, and what an authoring agent may do on its own pull request | `AGENTS.md`, "Working in parallel" |
| Claude Code on Opus 5.5 at high effort by default, Fable 5.2 for one-way-door work, ultracode off | `coding-agents.md`, `.claude/settings.json` |

## What this record does not establish

- That the rules work. They have not yet governed a single pull request.
- That Grok Bot loads `AGENTS.md`. Its sessions were not observed.
- The repository's Copilot settings. They are the owner's and were not inspected.
- Which agent writes the reviews that carry no footer.
- Any ranking of the agents or of the two Claude models. The sample is 22 pull
  requests, chosen rather than drawn, with different scopes and reviewers.
- Copilot's behaviour as GitHub documents it today, beyond the two points the
  repository's own history confirms.

## Open items

- #173 edits `AGENTS.md`, both skills and the PR template inside a feature pull
  request. It and the pull request that carries this record change the same bullet of
  `AGENTS.md`, so the second to merge must rebase.
- #171, #172 and #173 were opened before the fragment rule and keep their direct
  changelog entries.
- The first status pull request will be the first real run of
  `scripts/fold_changelog.py`.
