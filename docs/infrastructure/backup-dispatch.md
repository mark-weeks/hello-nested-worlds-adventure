# Backup dispatch and the heartbeat

The owner sets up two hosts for off-host backups. One dispatches
`.github/workflows/backup.yml`. The other notices when a validated backup
stops reporting. This page is that handoff, from
[O14](../roadmap/owner-decisions-2026-11-20.md#o14-observability-and-alerts-items-11-13).
The bucket, the tokens, and the `backup` environment are in
[backup-bucket.md](backup-bucket.md). Nothing here creates an account, a
token, or a secret.

[Item 11](../roadmap/owner-decisions-2026-11-18.md) asks for an outside
scheduler every 30 minutes, and for the one-hour bound to be proven over
seven consecutive days on the twin. O14 chooses a fine-grained GitHub token
for the dispatch, and a separately hosted heartbeat for the alarm.

Sentry and the `/guide` uptime check stay in O14. This page is the backup
dispatcher and the backup heartbeat.

## Why the dispatcher and the monitor are different hosts

A service that both starts the backups and is the only watcher cannot raise
its own absence. When that service stops, it sends no dispatch and no alert.
The missed backups and the missed alarm are the same outage. The monitor has
to be a different host, and it must not be a job that the dispatcher starts.

GitHub's own cron is not that second host. On `17,47 * * * *`, from
2026-10-03 to 2026-11-10, GitHub started 187 of 1,831 scheduled ticks
(10.2%), about one run every 4.90 hours, and none of the 186 gaps was an
hour or less. The measurement is the
[cadence record](../evaluation/2026-11-11-backup-schedule-cadence.md). The
cron stays in the workflow. It is not the clock that meets the bound.

## Dispatcher

`<OWNER: scheduler service>` sends one `workflow_dispatch` every 30 minutes.
Host it outside GitHub Actions and outside the Fly app being backed up.

The credential is a fine-grained personal access token:

- Repository access is only `mark-weeks/hello-nested-worlds-adventure`.
- Repository permission **Actions** is **Read and write**. That is the access
  level GitHub's permissions table requires for
  `POST /repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches`
  ([permissions](https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens#actions),
  read 2026-11-22). Leave every other repository permission, and every
  account permission, at no access.
- The same Actions write level includes the other write endpoints in that
  table, among them disabling this workflow, cancelling a run, and deleting
  Actions artifacts, caches, and logs. The table has no dispatch-only level.
  Store the token as a credential that can do those things.
- Expiry is 90 days. When the token is created, write that expiry date in
  `<OWNER: operator log>`. Replace the token in the scheduler before that
  date, then revoke the old one.

The token lives in the scheduler's secret store. It is not a secret of this
repository, and this workflow does not read it. `permissions` stay
`contents: read`.

The request, with the token supplied by the scheduler rather than typed into
a shell:

```text
POST /repos/mark-weeks/hello-nested-worlds-adventure/actions/workflows/backup.yml/dispatches
Accept: application/vnd.github+json
Authorization: Bearer <OWNER: fine-grained token>
X-GitHub-Api-Version: 2026-03-10

{"ref":"main"}
```

`backup.yml` is the workflow id. The workflow takes no inputs. `ref` is the
branch name `main`. The job then sees `GITHUB_REF` as `refs/heads/main` and
refuses anything else. The `backup` environment's deployment branches are
`main` only, which is what withholds the secrets.

Success is HTTP 200, with `workflow_run_id`, `run_url`, and `html_url` in
the body
([create a workflow dispatch event](https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event),
read 2026-11-22). A green badge on that run is not the one-hour proof. The
proof is the listing check below.

The workflow's concurrency group is `off-host-backup`, with
`cancel-in-progress: false`, so one backup runs at a time. Keep the dispatch
at 30 minutes. A shorter interval stacks requests behind a run that has not
finished. The cadence record describes that group as keeping a single
waiting run.

## Heartbeat monitor

`<OWNER: heartbeat service>` is the second host. It does not dispatch
`backup.yml`. It alerts when no fresh validated backup has reported for
longer than the one-hour bound plus one check interval.

The bound is 60 minutes: ADR-005's recovery target, and the default of
`scripts/backup_health.py`. The check interval is
`<OWNER: heartbeat check interval>`, how often the monitor itself looks. A
backup that is still inside the hour can sit unseen until the next look, so
the threshold is 60 minutes plus that one interval. The extra interval is
why one late look does not page. The alarm still fires if the dispatcher has
stopped, because the monitor is not the dispatcher.

Choose an interval that is short beside an hour. The formula is the
decision; the number is the monitor's setting.

Alerts go to `<OWNER: project alert address>`
([O6](../roadmap/owner-decisions-2026-11-20.md#o6-notice-and-community-policy-values-item-6)'s
project address), with `<OWNER: second operator>` copied
([O8](../roadmap/owner-decisions-2026-11-20.md#o8-people-and-dates)). Both are
still owner values. The monitor's own field for a second recipient is part of
`<OWNER: heartbeat service>`.

The ping means one validated upload was stored. It does not mean the
successive snapshot-start times stayed inside an hour. That is the proof
tool below. A quarantine upload does not ping, so a run that only stored an
invalid snapshot does not reset the monitor.

## How the workflow pings

The job's "Ping the backup heartbeat" step runs only when validation
succeeded and the store step succeeded. The condition is
`steps.validate.outcome == 'success' && steps.store.outcome == 'success'`.
A quarantined object takes the other branch of the store step, and this step
does not run.

The step reads the optional `backup` environment secret
`ENFOLDED_BACKUP_HEARTBEAT_URL`. An empty or whitespace-only value sends no
request and the step exits 0. The backup job is otherwise unchanged, and
`scripts/backup_gate.sh` does not read this name. Do not also create a
repository secret of the same name. GitHub uses a repository secret when the
environment secret is missing
([secrets](https://docs.github.com/en/actions/reference/security/secrets)).

When the value is set it must be an `https://` URL with no spaces. The step
sends one HTTP POST with an empty body and does not follow redirects. A
response in 200–299 is success. Anything else fails the step. The URL is not
written to the job log or the step summary. `curl -q` ignores a curl config
file. The runner's process list can still see the URL while the request
runs, so treat the URL as a secret.

Set the secret only after the monitor's URL answers 2xx to that empty POST.
A failed ping fails the job after the object is already stored. Prune still
runs: its condition is the store step, which has already succeeded. The step
summary line "Stored a validated snapshot." is the sign that the object is
in the bucket and the red step is the monitor.

`<OWNER: heartbeat URL>` is the whole request target, token included, stored
as `ENFOLDED_BACKUP_HEARTBEAT_URL`. The workflow does not append a query or
a body. Point the twin's monitor at the twin, and point a new monitor at
production when production is re-armed. One monitor does not serve both.

## The seven-day bound proof

`scripts/backup_freshness_proof.py` reads the bucket listing and reports
whether successive validated snapshot-start times meet the bound. It lists
objects and does not upload, download, or delete. It does not use the write
key. Set both `ENFOLDED_BACKUP_S3_LIST_ACCESS_KEY_ID` and
`ENFOLDED_BACKUP_S3_LIST_SECRET_ACCESS_KEY`, plus the bucket, the endpoint,
and `ENFOLDED_BACKUP_S3_REGION`. One of the list values alone makes the
command fail before it calls the store. The write key alone is not accepted.

A day is 24 hours. The default window is 7 days, ending at the clock, which
is the twin's seven-day run. The default bound is 60 minutes. Pass means all
three of these:

- a validated, nonempty snapshot for this app is already current at the
  window's start (its snapshot-start is inside the bound of that instant, or
  a snapshot sits on the start);
- every later successive snapshot-start gap through the last snapshot in the
  window is within the bound;
- the last snapshot-start is within the bound of the window's end.

Quarantine names, empty objects, other apps, and stamps in the future do not
count. The time is the stamp in the object name. `LastModified` is not the
clock. An exact gap of 60 minutes passes. One second over fails. Retention
is 30 days, and prune deletes older copies of this app, so a window longer
than that cannot pass once those copies are gone. `--days` accepts 1 to 366.

JSON goes to stdout. The summary goes to stderr: pass or fail, the count of
validated snapshots inside the window, the widest gap, every gap over the
bound with both UTC timestamps, and the first and last object. Exit 0
passes. Exit 1 fails the bound, including an empty listing. Exit 2 means the
listing or the credentials could not be read.

```bash
python scripts/backup_freshness_proof.py --app enfolded-staging
python scripts/backup_freshness_proof.py --app enfolded-beta --days 7
```

Run it for the app whose objects you mean. `enfolded-staging` does not
satisfy `enfolded-beta`.

A saved listing needs no credentials and contacts nothing. `--now` is
allowed only with `--objects`, and it is the UTC time the listing was saved.
The compact stamp form (`20261122T120000Z`) is accepted. Without `--now`,
the command uses the clock, so an old file fails the closing gap.

```bash
python scripts/backup_freshness_proof.py \
  --app enfolded-beta \
  --objects listing.json \
  --now 2026-11-22T12:00:00Z
```

This is the check for the rehearsal and for production after the dispatcher
is enabled. A passing `backup_health.py` shows only the newest object at
that moment. A green workflow run shows that one job finished.

The 2026-11-11 cadence record also describes a stricter reading: each object
has to land in the bucket within 60 minutes of the previous snapshot-start,
which needs the upload time. This tool does not read `LastModified`. The
pass/fail above is snapshot-start to snapshot-start, the same clock
`backup_health.py` uses for age.

## Retirement and re-arming

Follow O14's order. This page does not restate it.

- Twin retirement, after the final snapshot:
  [O14](../roadmap/owner-decisions-2026-11-20.md#o14-observability-and-alerts-items-11-13).
  The operator copy is
  [Retiring the twin's backup schedule](backup-bucket.md#retiring-the-twins-backup-schedule).
- Production re-arm, a separate owner act:
  [O14](../roadmap/owner-decisions-2026-11-20.md#o14-observability-and-alerts-items-11-13)
  and
  [Re-arming production backups](backup-bucket.md#re-arming-production-backups).
  O14's "successive validated production snapshots meet the one-hour bound"
  is this proof tool, run against the production app's listing. A new
  heartbeat monitor is pointed at production. The twin's monitor is not
  reused.

`<OWNER: retire the twin backup schedule>` and
`<OWNER: re-arm production backups>` are the owner acts. The scheduler
account, the heartbeat account, the fine-grained token, and
`ENFOLDED_BACKUP_HEARTBEAT_URL` are the inputs this page does not have.
