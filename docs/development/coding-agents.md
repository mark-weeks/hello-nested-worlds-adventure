# Coding-agent setup and verification

Start Codex, Claude Code, Grok Bot, or GitHub Copilot in the Git checkout root or inside it.
Opening a wrapper directory above the checkout does not reliably discover the
repository's instructions or skills.

## Shared instructions and skills

- [AGENTS.md](../../AGENTS.md) owns shared rules and explains the Claude import.
- The three procedures remain in `.claude/skills/<name>/SKILL.md`, with their
  existing names, descriptions, and rules. Edit these source files.
- `.agents/skills/<name>` is a relative directory symlink to the matching
  `.claude/skills/<name>`. This exposes the same procedures to Codex's native
  skill discovery without maintaining duplicate bodies or metadata.
- Codex supports symlinked skill directories. Claude Code retains its native
  `.claude/skills` directory. Copilot CLI supports both locations and chooses
  the first match for a name. Do not create another same-named skill copy.

The skills are `changelog-entry`, `irreversibility-check`, and `repin-goldens`.
Their descriptions are available for selection; full procedures are needed only
when applicable. The explicit task pointers in `AGENTS.md` also remain usable.

Git must preserve the links for Codex's native discovery. On Windows, check out
with symlink support enabled and the required OS permission (Developer Mode or
Administrator). A checkout with `core.symlinks=false` stores link targets as
plain text, so these aliases will not work. The ordinary `.claude/skills` source
files and `AGENTS.md` pointers remain readable; do not report native discovery
as verified on that checkout.

Copilot support depends on the surface. CLI, VS Code chat, the cloud agent, and
GitHub.com code review document `AGENTS.md` support. This setup does not add a
`.github/copilot-instructions.md` for surfaces that require that filename.

Copilot CLI documents both immediate `@path` expansion and deduplication of
identical agent instructions. Seeing both root filenames in its inventory does
not establish that the model receives two copies. The expanded inference payload
was not captured in this batch, so exact deduplication remains unverified here;
retain the Claude import for the installed older Claude Code build.

Grok Bot opens its pull requests from `cursor/` branches and is named in the
contract since 2026-11-14. Whether its sessions load `AGENTS.md` and discover the
skills was not checked in that batch: run the verification steps below in a fresh
Grok Bot session, and do not report its discovery as verified until then.

## Design routing

Follow [AGENTS.md → Read when relevant](../../AGENTS.md#read-when-relevant)
for the task-specific design routes and their authority boundaries.

## Repeatable verification

After changing instruction or skill routing:

1. Run `python -m pytest tests/test_agent_instructions.py -q`. These checks also
   run in the existing Python CI job and canonical gate. They verify the Claude
   import, matching relative skill aliases, and frontmatter names. A checkout
   that materializes aliases as text fails explicitly; fix symlink support
   rather than copying the procedures. Validate changed Markdown links too.
2. Inspect native discovery in a fresh session from the root and a subdirectory.
   Codex's app-server `skills/list` exposes names, paths, enabled state, and errors.
   Copilot CLI provides `copilot skill list --json`. In Claude Code, inspect the
   skill picker and `/context`. Expect each repository skill once. A resolved
   path under `.claude/skills` is normal when Codex follows the alias.
3. Run the [behavior scenarios](agent-instruction-scenarios.md)
   in fresh sessions. Keep the evaluator's expected outcomes out of the prompt.
   Restrict the session to reading relevant instructions, skills, and design
   documents; do not perform the hypothetical mutations or publish anything.
4. Review the complete tool trace for reads of the scenario answer key or dated
   evaluation records. Invalidate contaminated trials; do not call a trial
   uncontaminated if the trace is incomplete. Record selected/read skills, document
   routing, permission decisions, checks proposed, version/model, and failures.
   A model's claim that a skill was loaded is weaker evidence than a discovery
   result or observed file/skill read.

Record actual results under `docs/evaluation/`. Authentication failures and
unavailable environments are blocked checks, not passes. These small scenarios
test routing and decisions; they do not establish coding success rates, latency,
cost improvements, or universal adherence. Existing merge gates still apply.

## Copilot code review

GitHub Copilot code review posts as `copilot-pull-request-reviewer[bot]` and reviewed
62 of the 63 pull requests from #111 to #173. How the repository uses it is in
[AGENTS.md](../../AGENTS.md) ("Working in parallel") and
[the parallel-work guide](parallel-work.md). Those rules rest on the behaviour below,
taken from GitHub's documentation and changelog through search summaries on
2026-11-14. The pages could not be opened from the session that gathered them, so
re-check a detail before depending on it.

- **What it reads.** `AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md` and
  path-specific `.github/instructions/*.instructions.md`, from the pull request's own
  branch. This setup still adds no Copilot-specific instruction file: the shared
  contract is the single source. Because the pull request's branch is read, Copilot
  is not a check on a pull request that edits the contract.
- **When it reviews.** Once per pull request, unless a review is requested again or
  "Review new pushes" is enabled. The contract has the authoring agent request the
  second review on the final commit.
- **What it costs.** Effort levels are Lite, Balanced (the default) and Max (public
  preview), at an estimated $0.25, $1.50 and $10 per review. The level can be chosen
  per request.
- **What it skips.** Lockfiles and bundled or minified JavaScript, so the dependency
  locks and `static/app/assets/` get no Copilot review.
- **What it does not do.** It does not read replies in its threads, and it does not
  approve unless a repository admin enables approvals. The contract keeps them off.

The repository's Copilot settings are the owner's and were not inspected: approvals
off, Balanced as the default effort, and "Review new pushes" off in favour of the
requested second review. An agent requests a review through whichever route its tools
give it (the pull request page, the GitHub API, the `gh` CLI or a GitHub MCP tool);
where it has none, the owner requests it.

## Claude Code: model, effort and orchestration

*Provisional defaults, adopted by the owner on 2026-11-14. They apply to Claude Code
only; Codex and Grok Bot choose their own models. This is dated guidance with its
evidence, not a covenant.*

| Work | Model | Effort |
|---|---|---|
| Routine batch: feature, fix, tests | Opus 5.5 | high |
| Mechanical: rebase, the status pull request, wording, thread replies | Opus 5.5 | medium |
| Reviewing another agent's pull request | Opus 5.5 | xhigh |
| One-way-door design, ADR drafting, review of door-tripping pull requests, cross-file diagnosis, planning | Fable 5.2 | high |
| Search and extraction subagents | the session's model | low |

`max` is not used, and Fable 5.2 runs above `high` only where a gain has been
measured.

`.claude/settings.json` pins the default (`"model": "claude-opus-5-5"`,
`"effortLevel": "high"`) and starts sessions with ultracode off
(`"ultracode": false`), whatever a developer's own settings say. To change the model
or effort for one session only, launch with `--model` or `--effort`, or open the
`/model` picker or the `/effort` slider and press `s`. Typing `/model <name>` or
`/effort <level>` is different: it saves the choice as your own default for later
sessions, in other projects too. `/effort ultracode` turns ultracode on for one
session.

The evidence, and its limits:

- **Price.** Opus 5.5 is $4 per million input tokens and $20 per million output
  tokens; Fable 5.2 is $8 and $40. Subagents and workflows draw on the same
  subscription limits as the session.
- **Positioning.** Anthropic describes Opus 5.5 as the model for everyday coding and
  Fable 5.2 as the one for ambitious open-ended work, and advises starting Fable 5.2
  at `high`. Both default to `medium` in Claude Code.
- **This repository's record.** Twenty-one Claude Code pull requests from #137 to
  #166 are credited to Opus 5.5 alone in their commit trailers. The five of them in
  the review sample (#147 to #149, #158, #166) drew no High-severity finding. That is
  not a controlled comparison: scope and reviewers differ from the other agents' pull
  requests.
- **Effort.** No effort level is recorded anywhere in this repository, so the effort
  column is judgement from Anthropic's guidance, not a measurement made here.

**Ultracode stays off.** It makes Claude Code plan a multi-agent workflow for every
substantive task. Anthropic documents that it uses more tokens, reaches subscription
limits sooner and suppresses the large-workflow warning. In the session that produced
these rules, with ultracode on, 47 review agents were launched across three
concurrent runs and 2 finished before the 5-hour usage limit stopped the rest; a
redesigned pass then covered 14 pull requests with 2 agents and 282,000 tokens. That
container ran two agents at a time per workflow, so the fan-out bought little speed.
For a sweep that has been sized, such as a release audit or the review of a
door-tripping pull request, type the `ultracode` keyword in that one prompt or ask
for a workflow: scout first, keep it under 10 agents, and run one workflow at a time.

Revisit when a new Opus or Fable model ships, when prices or usage-limit accounting
change, when the review record shows Opus-written pull requests drawing High-severity
findings, or when an effort comparison is measured here.

## Vendor references

- [Codex skill discovery and symlinks](https://learn.chatgpt.com/docs/build-skills)
- [Claude Code skill locations](https://code.claude.com/docs/en/skills#choose-where-skills-load)
- [Claude's shared-file import](https://code.claude.com/docs/en/memory#share-one-file-with-other-coding-tools)
- [Copilot CLI skill discovery and precedence](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference#skill-locations)
- [Copilot instruction support by surface](https://docs.github.com/en/copilot/reference/custom-instructions-support)
- [Copilot instruction imports and deduplication](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-custom-instructions#how-multiple-instruction-files-interact)
- [Copilot code review](https://docs.github.com/en/copilot/concepts/agents/code-review)
- [Files Copilot code review excludes](https://docs.github.com/en/copilot/reference/review-excluded-files)
- [Copilot code review reads instructions from the pull request's branch (2026-07-17)](https://github.blog/changelog/2026-07-17-copilot-code-review-customization-and-configurability-improvements/)
- [Copilot code review effort default and API requests (2026-10-02)](https://github.blog/changelog/2026-10-02-copilot-code-review-api-support-and-new-default-effort-level/)
- [Copilot code review Max effort and approvals (2026-10-28)](https://github.blog/changelog/2026-10-28-copilot-code-review-merge-with-confidence-with-max-and-approvals/)
- [Claude Code model configuration: `/effort`, `effortLevel`, ultracode](https://code.claude.com/docs/en/model-config)
- [Claude Fable](https://www.anthropic.com/claude/fable)
