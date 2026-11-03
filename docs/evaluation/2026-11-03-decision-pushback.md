# Decisions a qualified engineer would push back on — 2026-11-03

Base: `23b8830` (#136). Question, from the owner: are there decisions in this
repo that a qualified engineer would strongly push back on as fundamentally
flawed, inappropriate, or a poor fit for the objectives? Objectives were taken
from the repo itself: an invited 8–12 person beta on one Fly machine with
SQLite, a solo owner working through AI agents, a budget-conscious, permanent
shared world, and a launch the [roadmap index](../roadmap/README.md) records
as not yet deployed.

## Verdict

No decision needs a rewrite. Nine decisions survived adversarial verification
as **significant**; none as fundamental. They fall into two groups:

1. **Permanent data, loosely guarded writes and recovery.** The repo polices
   agents' *code* changes to the permanent world rigorously (golden pins,
   birth immutability, the irreversibility check). The *runtime* paths that
   create permanent rows, and the systems that protect those rows, did not
   meet that standard: the invite gate failed open, player-reachable GETs
   wrote permanent rows under a caller-chosen name, a keyword filter decides
   what becomes permanent public text, outages were invisible to the
   operator, and off-host recovery rests on a cron that can silently stop.
2. **Effort pointed away from the critical path.** Provider optionality was
   built before any live evaluation, the beta gate cannot read "go" before
   the cohort plays, two co-equal clients go into a single pilot, and no rule
   redirects agent work while owner-only launch steps stall.

The architectural choices that look most alarming to a newcomer held up (see
[Looks wrong, holds up](#looks-wrong-holds-up)).

This batch fixes R1–R3. R4–R9 need owner decisions, credentials, or both.

## Method

Five reviewers each took one dimension: runtime and security; persistence and
permanence; AI integration and content safety; client and testing; process and
scope. Each returned candidate decisions with file:line evidence, the repo's own
rationale stated at its strongest, and whether the repo already acknowledged the
concern. A separate verifier per dimension then tried to refute every candidate:
it re-read the cited lines, ran cheap experiments, and argued the strongest
counter-case for this project's constraints. Of **29** candidates, **11**
survived as significant (two pairs were the same defect seen from two
dimensions, so **9** distinct findings), **18** were downgraded to moderate, and
none was refuted outright. Status below: *executed* means reproduced by running
the code on a scratch database; *read* means verified from source and docs.

## Findings

### R1 — The invite gate failed open (fixed here)

*Executed.* Whether a credential was needed was inferred per request from
whether `invite_keys` held an active row, and any exception counted as "no
keys" (`server/guard.py` `invite_gate_active`, before this batch). With one key
minted, a keyless `GET /players` returned 403; after `revoke_invite_key` on that
key it returned 200, and `/history` returned 200. With `list_invite_keys` patched
to raise, keyless requests were admitted. Ordinary operator actions reach that
state: revoke-all during an incident, a future suspend-all built on
`revoked_at` (checklist G5), a restore from a pre-mint backup. An open gate
admits `/speak` (bounded only by the global cap, since per-user caps need a
credential) and `/ws` with an unscreened `?name=`, and every act becomes a
permanent row. The owner had already moved shared-text moderation to fail-closed
on 2026-10-25; authentication had not followed.

### R2 — Agent runs and voices took their identity from the caller (fixed here)

*Executed.* `GET /agent` ran a 500-node FSM walk under any `name`, persona and
threshold on a bus wired to the record, ripple and substance handlers, then
overwrote that name's agent memory. `GET /observe` did the same for 40 nodes and
broadcast the chosen name as a live presence. `POST /agent/voice` recorded a
model line under any `agent_name`. No client calls `GET /agent`. The
reserved-cast check applied only to player names, and the rows carried no
`actor_identity`. Measured on a scratch world: three high-threshold GETs wrote
1,137 rows each; a 20,000-character name (the `/agent` name had no cap) wrote
22.8 MB from one GET, so about 15 requests could fill the 1 GB volume.
Redaction keeps mechanical fields, so none of it could be removed short of a
whole-database restore. This breaks the first covenant: a human selected an
agent, or another player's name, as the performer of permanent acts.

### R3 — "Failure stays in fiction" had no operator counterpart (fixed here)

*Read.* Every voice failure returned HTTP 200 with `ai: false` (correct for
players) and only a WARNING with the exception class; the budget path logged
nothing. `/health` is static and the planned `/guide` uptime ping serves a static
file. `scripts/beta_metrics.py` counted only successful conversations. A rotated
provider key or a full disk would therefore produce a week of silence that reads
as low engagement, corrupting the pilot's central measurement (curiosity and
return in a model-voiced world) after the fact. The runbook's own line, "Quiet
degradation hides outages by design", relied on one manual probe on launch day.

### R4 — A keyword filter decides what becomes permanent public text

*Executed.* `server/moderation.py` returns `_ALLOW_CLEAN` when the local tier
calls a line clean, before any classifier call, and the 2026-10-25 ADR-004
amendment makes a local clean verdict "a completed judgment". These all returned
`clean` from `content_screen.local_tier`: a home address with a child's school,
"I know where you live and I am coming for you tonight", "go hang yourself",
"I hope you get cancer", a targeted-harassment line, and "Sieg heil, 1488". Each
would be broadcast, stored as chronicle, and quoted into that node's voice
prompt for later visitors. At the repo's Haiku figures a classifier call costs
about $0.0004, and the same text already reaches the voice provider in node
history, so the cost and data-minimization reasons for skipping it are weak at
this scale. Checklist S1 ("shared text fails closed") is accurate only to its
narrower exit criterion. **Held for the owner** because it reverses an
owner-approved amendment. Recommendation: classify every non-empty shared line
when the classifier is available, keep the local block as a free pre-filter and
the local-only path for outages, budget it in dollars, and delimit player text
in the classifier prompt.

### R5 — Off-host recovery does not match "never wiped"

*Read.* Off-host copies are a GitHub Actions schedule that SSHes into the
machine, pulls the whole database and uploads it (`.github/workflows/backup.yml`,
which itself says "Scheduling can be delayed or dropped"). The repository is
public, and GitHub disables scheduled workflows in public repositories after 60
days without activity. The runbook's recommended lifecycle rule "deletes the last
copy once the schedule has been stopped" (`docs/infrastructure/backup-bucket.md`),
about 37 days at the example retention. One set of secrets holds both Fly SSH and
bucket delete, with no object lock or versioning. Continuous WAL replication was
deferred as "right end-state, wrong week" (ADR-005); the launch has since slipped,
so before the first production write is now the cheaper moment. **Held for the
owner** (ADR-005 sequencing, Fly and bucket accounts). Recommendation: continuous
replication before the first production write, keeping the pull as a daily
second copy; object lock or versioning; a lifecycle rule that never removes the
newest object; a freshness monitor that does not depend on the same schedule.

### R6 — Provider optionality was built before any live evaluation

*Read.* Eleven of the 26 PRs from #111 to #136 (about 13.5k added lines) went to
provider and model abstraction. Stripping the justified parts (provenance, the
harness, small config changes) leaves about 7k lines, including a 960-line
stdlib HTTP adapter with an 1,840-line test file. The evaluation harness rejects
that adapter (`evals/harness.py`: provider must be `fixture` or `anthropic`), the
destinations allowed to receive player text (S2) are undecided, and no live call
has evaluated any provider (`2026-10-05-model-evaluations.md`). ADR-034's own
trigger for a second adapter — existing routing preventing a worthwhile
comparison — was never met, because no comparison exists. The scarce resource
spent was the owner's review time. **Held for the owner.** Recommendation: freeze
adapter work at the current registry, run the M4 live evaluation of the incumbent
and its successor through the existing harness, and add a provider only after a
measured gap.

### R7 — The beta gate cannot read "go" before the cohort plays

*Read.* `docs/roadmap/beta-launch-checklist.md` defines what must be true before
8–12 people play as 95 items, 54 blocking. Its go/no-go list includes the cohort
itself (K2), cohort outcomes (R1, C2c), cohort operations (B2), and production
service levels (P1 latency, F4 ten-minute rollback, G5 one-minute suspension). It
can only be overridden, which defeats a gate. **Held for the owner** (a living
document whose thresholds are the owner's proposals). Recommendation: split it
into an entry gate of about ten items, the pilot's measurements, and a post-pilot
backlog.

### R8 — Two co-equal clients go into one pilot on an outdated rationale

*Read.* Invites land on `/` because it has "no WebGL dependency"
(`main.py` `invite_share_url`, ADR-005 §3), but PixiJS no longer renders anything
in `/app` (`frontend/src/main.jsx` imports only the CSP shim; the scene is a 2D
canvas), and `/app` already passes GPU-free and renderer-failure e2e cases. The
journal's recap links (`static/journal.js`) send returning players into `/app`,
which has a different layout, sound default and return trail, so the pilot would
measure orientation on one client and return on the other. Device evidence (Y5)
blocks the beta either way, so deferring D7 to December gains nothing. **Held for
the owner** (D7). Recommendation: choose the cohort's client before recruitment
and point invites and journal links at it.

### R9 — No rule redirects agent work while owner-only launch steps stall

*Read.* Plans authorize nothing by design (AGENTS.md; `next-steps-2026-q4.md`).
The October operator steps (Fly account, staging twin, hosted backups) stayed
open while provider work merged, and the plan itself was edited to make
cross-provider adapters a pre-pilot dependency (#112). The repo names "perpetual
pre-launch" as its largest risk (`2026-10-03-ambition-and-boundaries.md`) and no
rule acts on it. The binding constraint was owner availability, which no agent
can supply; the pushback is against spending the owner's attention on reviews of
work off the critical path. **Held for the owner.** Recommendation: while an
owner-only launch step has been open more than about a week, agents take no new
abstraction or capability work and only make that step easier.

## What this batch changes

- **R1.** `NESTED_WORLDS_INVITE_GATE=required` (set in `fly.toml`) keeps the gate
  closed whatever the key table holds. Unset or `auto` keeps the local-development
  behaviour. An exception while deciding, or an unrecognised value, denies; an
  unrecognised value also fails the boot, and the boot log prints the gate state.
  In auto mode `invite revoke` refuses the last active key unless `--allow-open`
  is passed (matching revocation's own parsing, the listing's `…` included);
  `invite mint` and `invite revoke` print the gate state.
- **R2.** `GET /agent` is a simulation: an unwired bus, no chronicle row, ripple,
  property delta, agent run, agent memory or puzzle pin (`Agent.pin_puzzles`),
  and a capped name that cannot be a cast member's. `GET /observe` streams a
  live walk to the watcher under the server's own `Observer` name, which is now
  reserved like the cast names, and stores nothing; its unapplied events no
  longer reach the room as `causal_event`s (presence still does). Operator walks go through the
  CLI (`python main.py agent`, and the `play` ambient mode, which records
  traces), unchanged. `POST /agent/voice` speaks only as a
  cast member (canonical spelling), an agent standing at that node now, or an
  agent whose own walked traces lie there (`persistence.has_agent_trace`, which
  ignores AGENT_VOICE rows so a typed name cannot bootstrap itself); anything
  else is a 404 before the screen, at no cost.
- **R3.** Every player-facing voice surface (`speak`, `agent_voice`, `intention`)
  reports each answer to `server.observability.voice_outcome`: a
  `voice_fallback surface=... reason=...` line on `nested_worlds.voice` (ERROR,
  so a Sentry event, for `provider`, `db` and `unconfigured`; WARNING for
  `budget`, `action_cap` and `disabled`) and a daily counter in `cost_budget`
  under the `voice_outcome:` prefix (surface and reason only; store failures are
  logged, not counted). The counter waits at most 50 ms on a locked store, and
  an answered line is counted after its reply is written, so a player who hung
  up is never counted as a provider failure. `python main.py voice-health` reports the window and
  exits 1 on failures or, with `--probe`, a failed live probe.
  `scripts/beta_metrics.py` reports answered and quiet lines.

**Review of this batch.** An adversarial review of the diff (three lenses, each
verified) found seven defects in the first commit, all fixed here: the revoke
guard missed the listing's `…` form; `Observer` was a registrable player name,
and room-wide live presence let any player voice it anywhere; `/observe` still
broadcast unapplied `DANGER_ALERT`/visit events room-wide; a disconnect after a
successful reply was counted as a provider failure; the counter write could
hold a quiet reply for the 5 s busy timeout (measured 5.05 s against 0.04 s); the
"store nothing" walks still pinned puzzle definitions (20 from one GET); and
the fly.toml gate line and boot check had no test. Refuted: counting store
failures (deliberately logged instead).

**Product-visible change.** Explorer "Observe" walks no longer leave traces in
history, and other players no longer see their unapplied events as causal
notices; they still see the observer walk. The ambient cast still walks and records continuously, and the CLI
paths are unchanged.

## Not verified here

- Nothing is deployed, so no hosted behaviour was observed. Whether `fly ssh
  console -C` sessions carry the machine's `[env]` (which the `invite revoke`
  check reads) is assumed from Fly's documented behaviour, not tested.
- That an ERROR record on `nested_worlds.voice` becomes a Sentry event relies on
  the SDK's default logging integration (event level ERROR); no live DSN was used.
- No scheduler runs `voice-health`. Where it runs and whom it alerts is the same
  open decision as checklist P5.

## Looks wrong, holds up

- **stdlib `http.server`, `ThreadingMixIn` and a hand-rolled RFC 6455 server.**
  Careful (masking, fragment reassembly, control-frame limits, read and write
  deadlines, a bounded per-player outbox) and tested against the `websockets`
  client. Fine for this cohort. ADR-001's revisit triggers are not measurable as
  written: the thread trigger sits above the Fly proxy's hard limit.
- **SQLite on one volume with a `BEGIN IMMEDIATE` writer fence.** Correct for
  acceptance-plus-effect atomicity at this scale. The gap is replication (R5),
  not the engine.
- **Append-only chronicle, immutable born rows, one canonical seed, the pinned
  wrap hinge.** These are the one-way doors that are cheap only before history
  exists. Sound.
- **The committed bundle with a freshness gate, vendored d3, a strict
  `script-src` CSP, a test suite larger than the code** (mostly behavioural), and
  **owner merge per PR**.
- **FSM agents without model cognition.** Deliberate cost and determinism
  control; the tagline oversells it.

## Downgraded (real, below the bar)

The Python `<3.12` pin is unnecessary (full-depth births and puzzle definitions
were byte-identical on CPython 3.11.18, 3.12.3 and 3.13.18) but harmless for the
beta. Voice and intention calls inherit the Anthropic SDK's 600 s timeout with
two retries and an unbounded semaphore wait. The bearer key stays in the address
bar. Kill switches and caps are env vars, and changing one restarts the only
machine (this batch corrects the guard docstring that said otherwise). Every
WebSocket reconnect writes JOIN/MOVE/LEAVE rows. Animation speed tracks the
display refresh rate. The unused PixiJS dependency is about 36% of the shipped
JS. Rollback compatibility is maintained for databases that never reached
production. Model replies become shared node memory unscreened (bounded by the
10-row prompt window; fixed most cheaply alongside R4). Permanence from the first
invited player is a held decision with a "retained research" option already
written.
