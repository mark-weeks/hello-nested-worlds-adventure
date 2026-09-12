# Contributing to Enfolded

Enfolded grows through the people who inhabit it. Playing together, sharing
discoveries, helping newcomers, reporting problems, and testing improvements
are all useful contributions. You do not need to write code to shape the game.

## Start with your experience

Tell us what you were trying to do, what happened, and what you expected.
Where did you become curious, confused, bored, or want to return? A concrete
moment is more useful than a long feature list; you do not need to diagnose
the cause or propose a solution.

- [Share playtesting feedback or an idea](https://github.com/mark-weeks/hello-nested-worlds-adventure/issues/new?template=playtesting.yml).
- [Report a reproducible bug](https://github.com/mark-weeks/hello-nested-worlds-adventure/issues/new?template=bug_report.yml).
- [Browse existing reports](https://github.com/mark-weeks/hello-nested-worlds-adventure/issues)
  and add a useful observation or a reaction when someone has already raised it.

GitHub submissions require an account. An in-game Ideas board for submissions
and voting is [planned](docs/roadmap/community-ideas.md); it is not available
in this change. The
[community process](docs/community/maintaining-the-community.md) describes how
feedback informs decisions and how selected ideas become implementation briefs.

For bugs, include your browser/device, whether you used the map or scene view,
and steps to reproduce if you have them. Screenshots are optional. Remove
invite keys, registration links, and private conversations before posting.
Be respectful, describe the experience rather than attacking a person, and
mark puzzle spoilers so other players can choose whether to read them.

## How decisions get made

Mark Weeks maintains Enfolded's direction and makes acceptance decisions.
Feedback and votes inform priorities; they do not promise a feature or a date.
Maintainers explain decisions, connect accepted work to its original report,
acknowledge contributions, and invite reporters to verify improvements.

Coding agents are the default implementation support. Human maintainers remain
responsible for scope, review, and acceptance. Outside code is welcome for work
agreed in advance, particularly when it brings independent diagnosis, specialist
knowledge, or verification on a device or setup we do not have.

## Before writing code

Open or join an issue and get explicit maintainer agreement on the problem,
scope, and who will work on it before opening a PR. This applies to small code
fixes as well as features. A maintainer's acknowledgment of a report, a popular
idea, or an agent's reply is not an assignment. An issue marked `help wanted`
is available for discussion; agree who is taking it before starting.

Unsolicited implementations may be closed with an explanation. Agreed scope
still requires review and passing checks; it is not a promise to merge.
Suggestions and small documentation corrections can be reported directly in
an issue without preparing a patch.

## Develop and verify locally

1. Fork this repository, clone your fork, and create a branch for the agreed work.
2. Follow [README Setup](README.md#setup) for Python 3.11, Node 20.19+, and
   the locked dependencies. `./setup.sh` installs the development environment.
3. Follow [Running Locally](README.md#running-locally). Paid API keys are optional:
   local development and the core game work with authored voice fallbacks and
   deterministic art. Leave invite keys unminted for an ungated local instance.
4. Run focused checks as you work. Before proposing merge, run
   `./scripts/check.sh`; after installing Chromium with
   `cd frontend && npx playwright install chromium`, run
   `ENFOLDED_E2E=1 ./scripts/check.sh` from the repository root for browser checks.
   Explain any checks you could not run.
5. For frontend changes, rebuild with `npm run build --prefix frontend` and
   include the resulting `static/app/` changes. Preserve bundled dependency
   notices; see [licensing maintenance](docs/community/maintaining-the-community.md#licensing-maintenance).

Enfolded has a permanent shared history. Stored birth identities stay fixed,
history is append-only, and migrations are additive. Puzzles must remain
solvable and keep their answers secret; ambient agents cannot claim human
progress. Read the relevant rules in [CLAUDE.md](CLAUDE.md), which is the
shared engineering contract for human and agent work. Coding agents enter
through [AGENTS.md](AGENTS.md). Follow only supporting procedures relevant
to your change.

## Submit a focused PR

Link the agreed issue and describe the problem, resulting behavior, and evidence.
Include appropriate regression coverage for behavior changes, documentation,
one measured [CHANGELOG](docs/CHANGELOG.md) entry, and the diff-based
irreversibility check described in the PR template. Documentation-only drafts
can report document validation; the canonical check still applies before merge.

AI-assisted contributions are welcome. You must understand and verify your
submission, explain its behavior, and respond to review. Identify material AI
assistance and known limitations. Do not submit unreviewed output or claim
tests or observations that did not happen. Agents do not grant acceptance,
merge, deployment, or access permissions.

## Contribution terms and credit

Contributions intentionally submitted for inclusion in Enfolded are offered
under [Apache License 2.0](LICENSE), unless explicitly stated otherwise and
separately agreed with the maintainer. You retain your copyright; this project
does not require copyright assignment or a separate contributor agreement.
Submit only material you have the right to contribute, retain third-party
notices, and identify material with different terms before it is incorporated.

This applies to submitted code, tests, documentation, and creative assets,
including material shared in issues. An independent implementation of an idea
is different from adapting someone else's expressive work; using a coding agent
does not remove licensing or attribution obligations.

Credit useful reporting, diagnosis, playtesting, and verification as well as
code. Ask before turning a private report into a public issue or naming its
author publicly. Public contributor credit belongs in project communication;
it must not fabricate actions or actor identities in the world's chronicle.
