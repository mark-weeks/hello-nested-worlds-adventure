# Backup schedule cadence: what GitHub delivers against the one-hour bound

**Status:** evaluation record, 2026-11-11, read against `main` at `7a7b632`
(#163). Findings and options for the owner. It changes no workflow,
threshold, secret, deployment or ADR status, and it ratifies nothing. Every
recommendation below is **proposed by agent, not decided**.

## Takeaway

GitHub starts `backup.yml` about once every five hours, not every 30 minutes:
**187 runs for 1,831 scheduled ticks (10.2%)** since the cron went
half-hourly on 2026-10-03, with no two runs within an hour of each other. At
that cadence, once backups are activated, an independent `backup_health.py`
check would read `stale` on **79.7%** of hourly checks, and the history lost
with the volume would average **2.77 hours and reach 10.40**, against
ADR-005's one hour. The cause is *inferred* to be GitHub's delivery of the
`schedule` event and not this workflow, the runners or the repository's
activity (finding 3 gives the evidence and what it cannot show), so the
remedy is a different clock (an external dispatcher, or replication that
needs none) or a different bound, and that choice is the owner's.

## Question

The off-host backup is scheduled with `cron: '17,47 * * * *'`
(`.github/workflows/backup.yml:28`). On 2026-11-11 the Actions run list
showed 40 scheduled runs between 2026-10-31 23:44 UTC and 2026-11-10 23:25
UTC. This record re-measures that over the workflow's whole history,
confirms what the runs did, looks for a cause, states what the freshness
gate and the one-hour bound would do at the measured cadence, and sets out
options with their costs.

## Method

- **Run history.** Every run of `backup.yml` from the Actions API (workflow
  id `307600449`), fetched 2026-11-11 at about 02:38 UTC: **1,018 runs**, #1
  (2026-07-06 09:53 UTC) to #1018 (2026-11-10 23:25 UTC). All 1,018 are
  `schedule` events; the workflow has never been dispatched by hand. **1,016
  succeeded and 2 failed.** No further run started between the last one and
  the fetch, 3.2 hours later. Two have started since, #1019 at 03:01 UTC and
  #1020 at 10:53 UTC on 2026-11-11, 3.60 and 7.87 hours after the run before
  each. They are not in the snapshot and change no figure here.
- **Cron eras.** `git log --follow` on the workflow file gives the cron in
  force at each time, by committer timestamp on `main`:

  | From (UTC) | Commit | Cron | Asks for |
  |---|---|---|---|
  | 2026-07-06 02:24 | `20b5915` (#57) | `0 6 * * *` | one run a day |
  | 2026-07-19 04:54 | `818b617` (#69) | `17 * * * *` | one an hour |
  | 2026-10-03 19:50 | `8cfa6cb` (#109) | `17,47 * * * *` | one every 30 minutes |

  The first cron (`0 6 * * 1`, #53) was replaced before it fired.
- **Reproduction.** The run list, the control sample and the script that
  prints every count quoted here are in
  [`2026-11-11-backup-schedule-cadence/`](2026-11-11-backup-schedule-cadence/):
  `python docs/evaluation/2026-11-11-backup-schedule-cadence/cadence.py`.
  It reads the two CSV files beside it, imports `scripts/backup_store.py`
  for one check, and contacts nothing.
- **Job logs.** The newest run's job log (its last 120 of 157 lines, which
  hold the checkout, the gate step and the cleanup), the job records of both
  failed runs and of the longest run, and the log tail of one failure.
- **Code and runbooks.** `scripts/backup_health.py`,
  `scripts/backup_store.py` (`assess_objects`), `scripts/backup_gate.sh`,
  `.github/workflows/backup.yml`, `docs/infrastructure/backup-bucket.md`,
  runbook §7 and §8, ADR-005.
- **External documentation.** The rendered documentation sites
  (`docs.github.com`, `fly.io`) were not reachable from the session that
  wrote this record. Each contract below was read from the publisher's own
  documentation source repository at the commit named in
  [Sources](#sources).
- **Labels.** *Measured*: counted from the run list. *Confirmed*: read in a
  job log, the code or official documentation. *Inferred* and *hypothesis*
  are marked where they occur.

## Findings

### 1. The schedule delivers a fraction of what the cron asks for (measured)

| Cron era | Scheduled ticks | Runs started | Delivered | One run every |
|---|---|---|---|---|
| Daily, 2026-07-06 to 07-19 | 13 | 13 | 100% | 24.2 h |
| Hourly, 2026-07-19 to 10-03 | 1,839 | 818 | 44.5% | 2.25 h |
| Half-hourly, 2026-10-03 to 11-10 | 1,831 | 187 | 10.2% | 4.90 h |

The window first observed (2026-10-31 23:44 to 2026-11-10 23:25 UTC)
reproduces: 40 runs, 39 gaps, mean 6.15 h, minimum 2.87 h, maximum 10.40 h,
none within an hour. Counting the ticks one by one gives 480 in that window;
479 is the span of 239.7 hours times two.

Four things stand out.

- **The half-hourly cron has never been met.** Of 186 gaps since
  2026-10-03, none is an hour or less. The shortest is 1.89 h, the median
  4.71 h, the 95th percentile 7.81 h and the longest 10.40 h (it began
  2026-11-09 09:45 UTC).
- **Asking twice as often did not produce more runs.** The last four whole
  weeks on the hourly cron delivered 43, 41, 41 and 38 runs. The first five
  whole weeks on the half-hourly cron delivered 31, 40, 42, 33 and 28.
- **Delivery has decayed.** From 161 runs in the week of 2026-08-17 to 28
  in the week of 2026-11-02. The percentages below fall further than the
  runs do, because #109 doubled the ticks on 2026-10-03: inside the hourly
  era, where the workflow file did not change at all, delivery went from
  95.8% to 22.6%. By ISO week, with first-parent commits on `main` by
  committer date (UTC) beside it:

  | Week from | Ticks | Runs | Delivered | Commits on `main` |
  |---|---|---|---|---|
  | 07-20 | 168 | 79 | 47.0% | 0 |
  | 07-27 | 168 | 76 | 45.2% | 0 |
  | 08-03 | 168 | 95 | 56.5% | 4 |
  | 08-10 | 168 | 131 | 78.0% | 2 |
  | 08-17 | 168 | 161 | 95.8% | 0 |
  | 08-24 | 168 | 76 | 45.2% | 7 |
  | 08-31 | 168 | 43 | 25.6% | 4 |
  | 09-07 | 168 | 41 | 24.4% | 9 |
  | 09-14 | 168 | 41 | 24.4% | 5 |
  | 09-21 | 168 | 38 | 22.6% | 2 |
  | 09-28 | 196 | 31 | 15.8% | 4 |
  | 10-05 | 336 | 31 | 9.2% | 3 |
  | 10-12 | 336 | 40 | 11.9% | 0 |
  | 10-19 | 336 | 42 | 12.5% | 9 |
  | 10-26 | 336 | 33 | 9.8% | 9 |
  | 11-02 | 336 | 28 | 8.3% | 21 |
  | 11-09 (to 11-10 23:25) | 95 | 7 | 7.4% | 7 |

  The schedule can run close to hourly: in the fortnight from 2026-08-10
  the median gap was 0.96 h. It has not done so since. Over the last 14
  days the mean gap is 5.85 h.
- **Even one run a day arrived late.** All 13 daily runs started, between
  1.42 and 3.88 hours after the 06:00 UTC tick (median 1.95 h).

### 2. The short runs are the documented no-op (confirmed)

The newest run (#1018, run `42923215612`, job `130202999014`) was read from
its log. `FLY_API_TOKEN`, `BACKUP_REQUIRED` and all four
`ENFOLDED_BACKUP_S3_*` values are empty in the job environment. The gate
step printed `##[warning]Backup is inactive before deployment; this run is
not recovery evidence.`, which is the inactive branch of
`scripts/backup_gate.sh`. Steps 4 to 11 (install, backup, download,
validate, store, both prunes) are `skipped`. The job ran from 23:25:19 to
23:25:24 UTC. That confirms what the first observation could only infer
from the run lengths.

Run length, from the run's start to its last update, has a median of 7
to 9 seconds in every era; 15 of 1,018 runs exceed 20 seconds. The longest
by that measure (#929, 3,782 s) is a later update to the run record: its job
ran for 4 seconds.

The two failures are platform failures. #214 (2026-08-06) was cancelled
after 17 minutes without ever being given a runner. #419 (2026-08-17) failed
in "Set up job" on an HTTP 429 while downloading the then-unpinned flyctl
action.

### 3. The cause is the `schedule` event (inferred from four measurements)

What follows rules causes out; it does not observe GitHub's scheduler. The
conclusion is therefore *inferred*, and one question stays open: whether
GitHub delivers this sparsely to every schedule, to this repository's, or to
this workflow's.

**No other schedule to compare with.** `backup.yml` is the only workflow in
this repository that has ever had a `schedule` trigger. `ci.yml` runs on
push and pull request, `release.yml` on tags, `deploy-staging.yml` on manual
dispatch (it has no runs), and the other two are GitHub's own dynamic
workflows. There is no second scheduled workflow to compare against, so
"specific to this workflow" and "general to this repository's schedules"
cannot be told apart from inside the repository.

**Not the workflow's definition.** The workflow file did not change between
#69 (2026-07-19) and #109 (2026-10-03). On that one file and one cron,
delivery was 95.8% in the week of 2026-08-17 and 22.6% in the week of
2026-09-21.

**Not the workflow's own concurrency group.** `backup.yml:34-36` puts every
run in one group, and GitHub cancels a waiting run when a newer one is
queued behind a running one. That is a one-waiting-run rule inside this
repository, and it never applied: the run numbers are 1 to 1,018 with none
missing, no run has the conclusion `cancelled`, no run started before the
run before it had finished, and the shortest gap between two starts is 41.3
minutes against a longest run of 17 minutes. The group has never held a run
back, so it did not thin the cadence.

**Not the runners and not Actions capacity for this repository.** The 60
most recent CI runs for pushes to `main` (2026-09-19 to 2026-11-11) were
created 2 to 5 seconds after their commit (median 3.5 s). The newest backup
job was given a runner 2 seconds after its run was created. Event-triggered
runs start at once during the same weeks in which nine scheduled ticks in
ten produce nothing.

**Not repository activity, as far as commit counts show.** The week with
the best delivery (95.8%, from 2026-08-17) had no commit on `main`. The week
with the most commits (21, from 2026-11-02) delivered 8.3%. This is a
correlation over 17 weeks, not a test.

**What GitHub documents, and whether it applies here** (confirmed in the
documentation source):

| Statement | Applies? |
|---|---|
| "The `schedule` event can be delayed during periods of high loads of GitHub Actions workflow runs. High load times include the start of every hour. If the load is sufficiently high enough, some queued jobs may be dropped. To decrease the chance of delay, schedule your workflow to run at a different time of the hour." | Yes. It is the only documented mechanism, it carries no number, and its one remedy is already in place: the cron has been off the hour since #69. |
| "In a public repository, scheduled workflows are automatically disabled when no repository activity has occurred in 60 days." | No. The workflow's state is `active`, runs continue, and `main` has had commits in every month. |
| "Scheduled workflows will only run on the default branch." / "This event will only trigger a workflow run if the workflow file exists on the default branch." | Satisfied. |
| "The shortest interval you can run scheduled workflows is once every 5 minutes." | Satisfied. |

GitHub documents no delivery rate, no per-repository limit and no rule for
what happens to a tick that comes due while an earlier one is still waiting.

**Hypothesis, not established:** GitHub's scheduler, as distinct from the
workflow's own group ruled out above, holds at most one waiting occurrence
per workflow, so the delivered interval tracks the queue delay and not the
cron. It fits two measurements: asking twice as often changed
nothing, and the delay on a once-a-day cron (1.4 to 3.9 h) is the same order
as the gaps on the faster crons. It cannot be tested from outside GitHub,
and no option below depends on it.

### 4. What happens at this cadence once backups are activated

Two assumptions carry this section. Activated runs are scheduled as the
no-op runs are (*inferred*: GitHub queues the event before it knows what the
job will do). Each run stores one validated object stamped at the run's
start, which is the kindest reading: the real stamp is taken some seconds
later, after the tools are installed. The figures use the half-hourly era,
2026-10-03 to 2026-11-10, with the last 14 days in brackets.

| Check | What it does at the measured cadence |
|---|---|
| `scripts/backup_gate.sh`, including `ENFOLDED_BACKUP_REQUIRED=true` | Passes on every run that starts. It validates configuration for a run that exists; it cannot see a run that never started. |
| The workflow's own steps | Each delivered run stores one validated object. About 4.9 objects a day: roughly 147 in 30 days, where the cost note in `backup-bucket.md` assumes 1,440. |
| `backup_health.py` run right after a backup run, as runbook §7 and the rehearsal list invoke it, and as checklist P3 words its criterion | Exit 0 every time: the object is minutes old. **P3 would pass while the bound does not hold.** |
| `backup_health.py` on an independent hourly schedule with the 60-minute default (checklist P5; runbook §8 "Independent bucket-freshness monitoring") | **`stale` on 727 of 912 checks, 79.7%** [276 of 333, 82.9%]. The repository's own `assess_objects` returns the same counts when given one object per run. Every one of the 186 gaps contains a stale stretch: mean 3.91 h, longest 9.40 h. An alert wired to exit 1 would be raised about five times a day and stand for about 19 hours in every 24. |
| The smallest `--max-age-minutes` that would never have read `stale` | **624** (10.4 h). Over the hourly era it is 798 (13.3 h). |
| ADR-005's one-hour bound | Not met. The newest snapshot is an hour old or less for **20.4%** of the time [17.1%]. Its age at a random instant, which is the history lost if the volume is lost then, has mean **2.77 h**, median 2.47 h, 95th percentile 6.30 h and maximum **10.40 h** [mean 3.18 h, 95th percentile 6.88 h]. |

Three consequences follow.

- **Runbook §7's own condition is met before activation.** It reads: "If
  measured cadence cannot meet that loss window, fix the transport/cadence
  or explicitly revisit ADR-005." The cadence is now measured.
- **Runbook §8's first T-1 week item would mislead.** "Manual dispatch and
  subsequent scheduled runs produce fresh app-specific objects": the
  dispatched run does, and each scheduled run is fresh when it lands, 1.9 to
  10.4 hours after the one before.
- **The exposure is volume or host loss and undetected corruption between
  snapshots.** A bad deploy is covered separately: `scripts/deploy.sh` takes
  a backup first. Fly's daily volume snapshots, kept 5 days, are on the same
  platform (runbook §7).

A platform failure adds one more interval to a gap. Two of 1,018 no-op runs
failed that way.

## Options (proposed by agent, not decided)

Costs are what the option needs built, what it adds to run, and what it puts
at risk. Effort figures are agent estimates. No price below was checked
except where a source is named.

### A. Keep the Actions job, replace the clock: an external scheduler dispatches `backup.yml`

The workflow already declares `workflow_dispatch` (`backup.yml:29`) and is
on the default branch, so nothing in it has to change for a dispatch to
start a run. GitHub's schedule stays as a second, slower trigger.

- **Contract (confirmed).** `POST
  /repos/{owner}/{repo}/actions/workflows/backup.yml/dispatches` with
  `{"ref": "main"}`. A fine-grained token needs the repository permission
  "Actions: write"; a classic token needs `repo`; a GitHub App installation
  token is accepted. Standard GitHub-hosted runners are free in public
  repositories.
- **Which credential (confirmed).** The classic token is the widest: `repo`
  "Grants full access to public and private repositories", and a classic
  token "will grant access to all repositories within the organizations
  that you have access to, as well as all personal repositories". A
  fine-grained token and a GitHub App can each be held to this repository
  and to "Actions: write" alone. Of
  those two the App is the narrower: its installation tokens "expire after 1
  hour" and belong to no person's account, where a fine-grained token is
  "tied to the user who generated" it and lives as long as its expiry
  allows. The price is that the dispatcher holds the App's private key and
  mints a token for each call. None of the three can be limited to one
  workflow, so the independent freshness alert stays the backstop.
- **One run waits at a time (confirmed).** The workflow's concurrency group
  (`backup.yml:34-36`, `cancel-in-progress: false`) lets one run execute and
  one wait: "any existing `pending` job or workflow in the same concurrency
  group will be canceled and the new queued job or workflow will take its
  place." A dispatch that arrives while a backup is running can therefore be
  replaced before it runs, by a later dispatch or by a scheduled run. That
  costs nothing in freshness, since the run that replaces it is newer. It
  does mean the proof counts validated objects in the bucket, never
  dispatch calls, and that a `cancelled` run in the rehearsal is this rule
  at work and not a dropped dispatch. No run has been cancelled so far only
  because the no-op runs last seconds (finding 3); real backups take
  minutes.
- **Where the scheduler runs.** Two candidates were read:
  - *A Cloudflare Worker with a Cron Trigger.* Five-field cron in UTC, so
    `17,47 * * * *` is valid. The Free plan allows 5 Cron Triggers per
    account, 100,000 requests a day and 10 ms of CPU per invocation; one
    HTTP call is expected to fit (*inferred*). A trigger change can take up
    to 15 minutes to propagate. Cloudflare documents no delivery-time
    guarantee: Cron Triggers "run on underutilized machines". If the bucket
    decision (Q4 decision I, packet decision 12) lands on R2, this is the
    same account; if it does not, it is one more vendor.
  - *A separate small Fly app*, such as Fly's Cron Manager, which Fly calls
    its "most production-hardened option" and which runs as an app of its
    own. Its price was not checked.
- **Costs.** About half a day with a staging rehearsal. A long-lived GitHub
  credential outside GitHub: "Actions: write" covers 15 write endpoints, so
  the same token can dispatch `deploy-staging.yml`, cancel or delete runs
  and their logs, and disable workflows, this one included. A token that
  lapses or is revoked stops the backups without an error anywhere, which
  only the independent freshness alert catches. The job still depends on
  GitHub Actions being up.
- **Not established.** How soon a dispatched run starts. No dispatch has
  ever run in this repository. Push-triggered runs start in seconds, so a
  dispatch is expected to (*inferred*); the rehearsal should measure it.
- **What it buys.** The one-hour bound with the built and tested path, and
  full use of the storage estimate in `backup-bucket.md`. Checklist P5
  already needs a scheduler outside GitHub's schedule and a notification
  destination: a freshness check on GitHub's schedule would run every five
  hours and fail with the thing it watches.
- **What it must not share.** The dispatcher and the freshness check can use
  one service, but not one clock without a watcher. If a single scheduler
  fires both and stops, the dispatches and the checks stop together, no
  alert is sent, and GitHub's own schedule carries on at one run in five
  hours. That is the failure runbook §7 names: a check "cannot detect its
  own scheduler stopping". So A also needs one of two things, and each is a
  cost: the freshness check on a second, separately hosted schedule, or a
  missed-check alert held somewhere else, which raises the alarm when the
  check has not reported in.

### B. A scheduler on the Fly machine takes and stores the backup itself

The app machine is always on (`fly.toml`: `auto_stop_machines = false`,
`min_machines_running = 1`), so a local cron keeps its time.

- **Contract (confirmed).** Fly's Supercronic guide runs cron as its own
  process group. That does not fit here: "Every defined process runs in its
  own Fly Machine(s)" and "a volume can be attached to only one Machine", so
  a `cron` process group cannot read `worlds.db`. The cron would have to run
  inside the app's container beside the server, started by the entrypoint.
  Fly's built-in scheduled Machines are ruled out by their own contract: a
  "fuzzy" hourly, daily, weekly or monthly cycle, "Not for precise timing",
  hourly at the finest, and a separate Machine again.
- **Costs.** A day or two with rehearsal. The `Dockerfile` and the
  container's start command change (`CMD ["enfolded", "serve", ...]` today),
  and one container supervises two processes. The image gains Supercronic
  and the AWS CLI, which `backup_store.py` shells out to, or the upload
  client is rewritten. The bucket credential, which can delete, sits on the
  machine it protects. The Actions job log stops being the record of each
  backup. The freshness check still has to run somewhere else.
- **What it buys.** Independence from GitHub's schedule and from GitHub
  Actions for the backup itself. The loss window stays at the snapshot
  interval. It is a new seam in the production image, the class of change
  ADR-005 deferred for Litestream, for less than Litestream gives.

### C. Relax the bound: an ADR-005 revisit

- **Costs.** No build and no spend. The owner amends ADR-005, and the
  runbook, the checklist and the documented `--max-age-minutes` follow.
- **What the number would be.** A limit that never read `stale` on the
  measured history is 624 minutes on the last 38 days and 798 on the hourly
  era. The honest statement is "about half a day of permanent history can be
  lost; three hours is typical".
- **What it risks.** ADR-005 moved off a 24-hour window because it
  "contradicts the covenant". This puts the window at half of that. The
  number is also not the project's to hold: delivery fell from 161 runs a
  week to 28 in eleven weeks, most of it while the workflow file was
  unchanged, and GitHub documents no floor. A bound set from today's distribution can be
  broken tomorrow without notice.
- **A narrower use.** A relaxed limit declared only for the disposable
  staging twin puts no covenant at stake and would let the rehearsal proceed
  while A or D is built.

### D. Bring forward Litestream-style replication (standing commitment 4.1)

- **Contract (confirmed in Litestream's documentation source).** A separate
  process that "continuously copies write-ahead log pages" to a replica; by
  default it replicates "new changes to an S3 replica every second", and
  that asynchronous window is the data-loss window. It works only in WAL
  mode and asks for a 5-second `busy_timeout`; this application already sets
  both (`persistence/__init__.py:93`, `:102`). It works "by effectively
  taking over the checkpointing process". For a single container, as on Fly,
  it supervises the application with `litestream replicate -exec`.
  Cloudflare R2 is an auto-detected S3-compatible target. With
  `retention.enabled: false` (v0.5.8 and later) the credential on the
  machine needs no `DeleteObject`. Two applications replicating to one
  bucket and path can corrupt the replica, so staging and production need
  separate paths.
- **Costs.** Several days: ADR-005 asks for "its own blind-spot pass and
  restore rehearsal". The container's start command changes. Checkpoint
  ownership meets the server's own shutdown checkpoint
  (`persistence.checkpoint`, `persistence/__init__.py:2997`, called at
  `server/__init__.py:256`). The
  restore procedure changes and must be rehearsed. `backup_health.py` reads
  snapshot object names and would not describe a Litestream replica, so
  freshness monitoring has to be redone. A replica credential sits on the
  app machine. ADR-005 rejected "Litestream before launch" as "right
  end-state, wrong week", so this needs the owner to revisit that line.
- **What has changed since that rejection.** It was an argument about launch
  week. The 2026-10-31 target has lapsed and no new date is recorded on
  `main`, so the week is no longer the constraint it was.
- **What it buys.** A loss window of seconds, and the cadence question ends:
  the snapshot workflow becomes the second net ADR-005's revisit note
  already anticipates ("a daily artifact may suffice"), which GitHub's
  schedule delivers several times over.
- **Not checked.** The current Litestream release. The documentation source
  read here was last changed on 2026-07-30.

### E. Leave it as it is

Listed as the baseline. The one-hour bound is unmet, and the P5 alert is
either red four hours in five or not built. It is not compatible with
ADR-005 as it stands.

### What the evidence rules out

- **More cron entries or a shorter interval.** Doubling the request did not
  raise delivery (finding 1).
- **Hosting the freshness check on GitHub's schedule.** It shares the
  failure it is meant to detect.
- **Fly scheduled Machines and a Supercronic process group**, for the
  reasons under B.

### Recommendation (proposed by agent, not decided)

1. **A now.** It is the smallest change that restores the bound, it touches
   no world data path, and most of its scheduler is owed to P5 anyway. Prove
   it on staging before it counts: seven consecutive days in which the
   newest validated object in the bucket is never more than 60 minutes old
   by its snapshot-start, which is how `backup_health.py` measures age. That
   is stricter than gaps of an hour between snapshots: a snapshot is not in
   the bucket until its upload ends, so each object has to land within 60
   minutes of the snapshot-start of the one before it. Read it from the
   bucket listing, not from the Actions badge.
2. **Ask D's timing again as its own decision.** With no launch date, "after
   launch" no longer says when. D is the only option that takes a
   third-party clock out of the continuity covenant.
3. **C only as a declared posture for the staging twin**, if the rehearsal
   should not wait.

The case against this order, so that it is not read as the only one: if the
owner means to do D before first production history, A's dispatcher is
partly throwaway (its freshness monitor is not), and D first is cheaper in
total. And for 8 to 12 invited people a typical three-hour window may be
acceptable to the owner, which is C. The opportunity cost of D is several
days that would otherwise go to the M7 pilot gates.

### Decisions this puts to the owner

1. Does the one-hour bound stand for first production history? If not, what
   is the number, given that GitHub can move it?
2. If it stands: an external dispatcher now (A), replication before first
   production history (D), or A now and D later as ADR-005 has it?
3. Which service holds the dispatch credential? This couples to the pending
   bucket decision (Q4 decision I).

## Follow-up edits this record queues (none made here)

Three texts on `main` say something this measurement contradicts or would
let pass. This record changes none of them: the workflow and the runbook are
outside its scope, and the right wording for the second and third depends on
the option chosen. They are listed so that the batch that acts on the
decision, or a documentation-only correction before it, picks them up.
Proposed by agent, not decided.

| Where | What it says | What is wrong with it |
|---|---|---|
| `.github/workflows/backup.yml:14-18`, the header comment | "Half-hourly full copies leave slack within that one-hour limit." | Measured false for the schedule as GitHub delivers it: no two copies would have been within an hour of each other (finding 1). It holds again only once copies do arrive half-hourly, which is option A or B. Until then the comment can state what is measured, without waiting for the decision. |
| Runbook §8, first T-1 week item (`docs/infrastructure/fly-deployment.md:1279-1281`) | "Manual dispatch and subsequent scheduled runs produce fresh app-specific objects." | Satisfied by a dispatched object and by any scheduled run on the day it lands (finding 4). It needs the gaps between validated objects, read from the bucket over days. |
| Checklist P3's criterion (`docs/roadmap/beta-launch-checklist.md`) | "`backup_health.py` exits 0 on a real validated private-bucket object." | Passes right after any backup, whatever the cadence (finding 4). The criterion over time currently lives only in P5, which is not built. |

Runbook §7 already hedges its own version of the first claim ("it does not
guarantee timely scheduling"), and the cost note in `backup-bucket.md`
(1,440 objects in 30 days) is right for any option that restores the
half-hourly cadence and about ten times too high for the cadence measured
here.

## What this record does not establish

- How soon a dispatched run starts, and whether a dispatched run is ever
  dropped. No dispatch exists to measure.
- That activated runs are scheduled as the no-op runs are. It is inferred.
- Why delivery fell after 2026-08-23. GitHub documents the mechanism only as
  load.
- Whether a Cloudflare Cron Trigger or a Fly Cron Manager job fires on time.
  Neither publisher documents a guarantee; the rehearsal would measure it.
- The size of a hosted `worlds.db`, and so the run time and storage of a
  real backup. Nothing is deployed.

## Sources

Official documentation, read from each publisher's documentation source
repository on 2026-11-11:

- GitHub, `github/docs` at `7c3387d` (2026-11-10):
  `content/actions/reference/workflows-and-actions/events-that-trigger-workflows.md`
  (`schedule`, `workflow_dispatch`), `data/reusables/actions/schedule-delay.md`,
  `data/reusables/actions/branch-requirement.md`,
  `data/reusables/repositories/actions-scheduled-workflow-example.md`,
  `data/reusables/actions/actions-group-concurrency.md`,
  `data/reusables/apps/generate-installation-access-token.md`,
  `content/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens.md`,
  `content/apps/oauth-apps/building-oauth-apps/scopes-for-oauth-apps.md`,
  `src/rest/data/fpt-2026-03-10/actions.json` ("Create a workflow dispatch
  event"), `src/github-apps/data/fpt-2026-03-10/fine-grained-pat-permissions.json`,
  `content/billing/concepts/product-billing/github-actions.md`. Rendered at
  [Events that trigger workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
  and [REST: workflows](https://docs.github.com/en/rest/actions/workflows).
- Fly.io, `superfly/docs` at `15b897c` (2026-11-10):
  `blueprints/task-scheduling.mdx`, `blueprints/supercronic.mdx`,
  `machines/flyctl/fly-machine-run.mdx`, `launch/processes.mdx`,
  `volumes/overview.mdx`. Rendered at
  [Task scheduling guide](https://fly.io/docs/blueprints/task-scheduling/).
- Cloudflare, `cloudflare/cloudflare-docs` at `cd05cef` (2026-11-10):
  `src/content/docs/workers/configuration/cron-triggers.mdx`,
  `src/content/docs/workers/platform/limits.mdx`,
  `src/content/docs/workers/platform/pricing.mdx`. Rendered at
  [Cron Triggers](https://developers.cloudflare.com/workers/configuration/cron-triggers/).
- Litestream, `benbjohnson/litestream.io` at `6b6893d` (2026-07-30):
  `content/how-it-works/_index.md`, `content/tips/index.md`,
  `content/guides/docker/index.md`, `content/guides/s3-compatible/index.md`,
  `content/reference/config.md`. Rendered at
  [litestream.io](https://litestream.io/how-it-works/).

In this repository: `.github/workflows/backup.yml`,
`scripts/backup_health.py`, `scripts/backup_store.py`,
`scripts/backup_gate.sh`,
[backup-bucket.md](../infrastructure/backup-bucket.md),
[runbook §7 and §8](../infrastructure/fly-deployment.md#7-backups),
[ADR-005](../decisions/ADR-005-launch-operations.md), the
[beta readiness record](2026-10-03-beta-readiness.md) ("Remaining gates and
owners"), the [beta launch checklist](../roadmap/beta-launch-checklist.md)
(P3, P5) and the [roadmap index](../roadmap/README.md) (standing commitments
1.2 and 4.1).
