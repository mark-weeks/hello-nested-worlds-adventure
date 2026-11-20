# Private off-host backup bucket

The half-hourly workflow (`.github/workflows/backup.yml`) copies `worlds.db`
off the Fly volume. That file holds the chronicle, including player chat.
GitHub's [artifact list endpoint](https://docs.github.com/en/rest/actions/artifacts#list-artifacts-for-a-repository)
says anyone with read access to the repository can use it. This repository is
public, so a backup stored with `actions/upload-artifact` would be a public
object list. The workflow does not upload artifacts, and it has no artifact
fallback when the bucket is missing or validation fails.

Nothing is deployed yet, and the artifact upload this replaces had not run
against a live database. The job stays a green no-op until the Fly token and
the bucket settings below are present. Set `ENFOLDED_BACKUP_REQUIRED=true`
only after a manual dispatch has stored a real object: missing configuration
then fails the job instead of reporting success. For production, that
dispatch is after the first production deploy, not before it. The order is
[Re-arming production backups](#re-arming-production-backups).

Cloudflare R2 is the S3-compatible store, and retention is 30 days. Both were
recorded on 2026-11-20
([O7](../roadmap/owner-decisions-2026-11-20.md#o7-backup-bucket-lifecycle-and-the-delete-lock-items-11-12)).
The workflow writes `30`. There is no retention variable. ADR-005 still
describes hour-stamped GitHub artifacts kept for 90 days, and this runbook
does not amend it. The workflow does not hard-code an account, bucket, or
endpoint. The client uses path-style addressing (`{endpoint}/{bucket}/{key}`)
and sends checksums only when the operation requires them, which current AWS
CLI releases need for R2.

A bucket lock of 7 days, counted from each object's upload, and a lifecycle
rule of 37 days on `offhost/` are settings on the bucket. The lifecycle is an
operator backstop. It is not a deletion date promised to players. The served
notice keeps the wording in
[O6](../roadmap/owner-decisions-2026-11-20.md#o6-notice-and-community-policy-values-item-6)
until the [erasure check](#erasure-check) below is done and recorded.

The commands below need AWS CLI v2 on `PATH`. The workflow installs its own
pinned copy. A laptop or operator shell does not.

## Create the bucket

In the Cloudflare dashboard, create one R2 bucket for backups. Use Standard
storage. Leave the bucket private:

- Do not enable the public development URL (`r2.dev`).
- Do not attach a custom domain.
- Do not turn on managed public access.

R2 buckets are private until one of those is enabled
([public buckets](https://developers.cloudflare.com/r2/buckets/public-buckets/)).
A dedicated bucket is the scope boundary: the workflow token below is limited
to it, and a lifecycle rule can cover the whole `offhost/` prefix. The bucket
name is lowercase letters, numbers, and hyphens, 3–63 characters. Store it as
the `backup` environment secret `ENFOLDED_BACKUP_S3_BUCKET`. A repository
variable is printed in the job's environment, and this repository's logs are
public. A repository secret is readable by a workflow on any branch.

Find the account ID on the same R2 overview page. The S3 endpoint is:

```text
https://<ACCOUNT_ID>.r2.cloudflarestorage.com
```

No path, query, user, or password. A jurisdictional bucket uses its
jurisdictional host instead (`https://<ACCOUNT_ID>.eu.r2.cloudflarestorage.com`,
or the `.us.` / `.fedramp.` host). Store that URL as the `backup` environment
secret `ENFOLDED_BACKUP_S3_ENDPOINT`. The host contains the account id.
`ENFOLDED_BACKUP_S3_REGION` is the repository variable `auto`. Do not enable
bucket versioning. O7 records none. Whether a delete leaves a hidden copy is
not verified here; the erasure check's third item records it.

## API token

Create an R2 API token from the R2 overview's API Tokens page
([Authentication](https://developers.cloudflare.com/r2/api/tokens/)). Choose
**Object Read & Write** and scope it to this bucket only. Cloudflare documents
that permission as read, write, and list on the buckets you select. Listing is
part of read: a token that cannot list cannot feed the freshness check. Do not
use Admin Read & Write for the workflow. That permission creates and deletes
buckets and edits bucket configuration. Lifecycle rules are an admin change in
the dashboard, not something the backup token should do.

Object Read & Write is what the upload, the retention prune, and a deletion
request call through the S3 API (`PutObject`, `ListObjectsV2`, `GetObject`,
`DeleteObject`). Before setting `ENFOLDED_BACKUP_REQUIRED=true`, put a
disposable object with the token and delete it, so a token that cannot delete
is caught before the job depends on it. Also delete two disposable objects in
one `DeleteObjects` call: that batch API is what prune uses, and its billing
is not the same documented free `DeleteObject`. Use keys that do not start
with `offhost/` for that pair of checks. A 7-day bucket lock on `offhost/`
refuses a delete of a young object there, which does not tell you whether the
token can delete. The secret access key is shown once. Store both keys as
`backup` environment secrets.

Optional read credential, not a list-only key: a second token with **Object
Read only**, same bucket. Cloudflare defines that permission as read and list.
R2 has no list-only permission, so this token can `GetObject` every backup,
player chat and private notes included. Protect it the way you protect the
database. A credential that can only list is a ListBucket-only S3 policy,
which R2 does not offer.

The health check, the retention prune, and `delete-before` list with this pair
when both `ENFOLDED_BACKUP_S3_LIST_ACCESS_KEY_ID` and
`ENFOLDED_BACKUP_S3_LIST_SECRET_ACCESS_KEY` are set. A download does not: `get`
uses the write key. Set both or neither. One of them alone makes those listing
commands fail closed. The names still say `LIST_` because that is the pair
already documented for operators; the permission is read, not list-only. In
GitHub they are `backup` environment secrets. An operator shell that runs the
health check uses its own copy of the same pair. That copy is not a repository
secret.

## GitHub `backup` environment

Do these steps before the workflow file that names `environment: backup` runs
on `main`. GitHub's
[Managing environments](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments)
says that a workflow run which references an environment that does not exist
creates one, with no protection rules and no secrets. Anyone who can edit a
workflow can cause that creation. Only a repository admin can configure the
environment. Create it, and set the branch rule, before merge.

The job sets `deployment: false`. GitHub's
[Using environments without deployments](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/control-deployments#using-environments-without-deployments)
says that still restricts which branches can use the environment's secrets,
and that it does not add a deployment record. A wait timer and required
reviewers still hold the job. A custom deployment protection rule fails the
job when `deployment` is false. This cron is unattended, so add none of those
three.

`<OWNER: create the GitHub Actions environment named backup>`
Settings → Environments → New environment. The name is `backup`.

`<OWNER: set the backup environment's deployment branches to main only>`
Deployment branches and tags → Selected branches and tags → Add deployment
branch or tag rule → Ref type **Branch** → name pattern `main`. That is the
same rule the staging environment uses. Do not add a tag rule. The scheduled
run uses the repository's default branch, which is `main`, and the workflow
refuses any `GITHUB_REF` other than `refs/heads/main`.

`<OWNER: disallow administrator bypass on the backup environment>`
Deselect "Allow administrators to bypass configured protection rules", then
save. Leave required reviewers, the wait timer, and custom protection rules
off.

### Environment secrets

These are secrets of the `backup` environment, never repository secrets. A
workflow on any branch can read a repository secret. Between them, the write
pair can delete every snapshot and the read-only pair can read every snapshot,
player chat included.

| Secret | Value |
|---|---|
| `FLY_API_TOKEN` | `<OWNER: FLY_API_TOKEN>` from the SSH token command below. Not an organization token, and not a deploy token |
| `ENFOLDED_BACKUP_S3_ACCESS_KEY_ID` | `<OWNER: ENFOLDED_BACKUP_S3_ACCESS_KEY_ID>` |
| `ENFOLDED_BACKUP_S3_SECRET_ACCESS_KEY` | `<OWNER: ENFOLDED_BACKUP_S3_SECRET_ACCESS_KEY>` |
| `ENFOLDED_BACKUP_S3_BUCKET` | `<OWNER: ENFOLDED_BACKUP_S3_BUCKET>` Bucket name. A variable would be printed in the public job log |
| `ENFOLDED_BACKUP_S3_ENDPOINT` | `<OWNER: ENFOLDED_BACKUP_S3_ENDPOINT>` `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`. The account id is not a variable |
| `ENFOLDED_BACKUP_S3_LIST_ACCESS_KEY_ID` | `<OWNER: ENFOLDED_BACKUP_S3_LIST_ACCESS_KEY_ID>` The read-only pair. Set both list secrets or neither |
| `ENFOLDED_BACKUP_S3_LIST_SECRET_ACCESS_KEY` | `<OWNER: ENFOLDED_BACKUP_S3_LIST_SECRET_ACCESS_KEY>` |

`<OWNER: delete the repository copies of the backup secrets>`
After the environment secrets exist, delete any repository copies of the
seven names above, including a repository `FLY_API_TOKEN`. The job does not
read a repository secret. A copy left behind is still readable by a workflow
on another branch that does not use this environment.

### Repository variables

The repository holds only these three. Retention is not one of them. If
`ENFOLDED_BACKUP_RETENTION_DAYS` exists as a repository variable, delete it:
the workflow no longer reads it, and a leftover value cannot change the 30
days.

| Variable | Value |
|---|---|
| `ENFOLDED_BACKUP_APP` | `<OWNER: ENFOLDED_BACKUP_APP>` Fly app name. Unset, the workflow uses `enfolded-beta`. Set `enfolded-staging` while the watch twin is the app being backed up |
| `ENFOLDED_BACKUP_S3_REGION` | `auto` |
| `ENFOLDED_BACKUP_REQUIRED` | Leave unset until a manual dispatch has stored a validated object. Then `<OWNER: set ENFOLDED_BACKUP_REQUIRED=true>` exactly. For production, that is after the first production deploy |

A typo in the required flag, the region, the retention, the endpoint, or the
bucket fails the job. It does not turn the backup off. Unset bucket settings
with the required flag unset or `false` make an inactive run: no snapshot is
taken and nothing is uploaded. Setting only `FLY_API_TOKEN` does not upload
anywhere.

## Fly token

The job runs `flyctl ssh console` and `flyctl ssh sftp get` against one app.
A token that can do that can read participant chat and reports on that app.

**Verified, from source, not from a live call.** flyctl 0.5.1 is the version
the workflow installs. Its `fly tokens create` command, in
`internal/command/tokens/create.go` at tag `v0.5.1`, has a subcommand `ssh`
whose help text is "Create token for SSH'ing to a single app. To be able to
SSH to an app, this token is also allowed to connect to the org's wireguard
network." The implementation mints an app deploy-profile token and then
prints a different token: read on the org and app, plus mutations limited
to `issueCertificate` and `addWireGuardPeer`. That second mutation is what
the help text calls connecting to the org's WireGuard network; it can add a
peer. The unattenuated deploy token is not what the command prints. The same file's
`deploy` subcommand prints the unattenuated app token, which can manage the
app. `machine-exec` can limit shell commands, but this job uses `ssh console`
and `ssh sftp get`, which are the SSH token's commands, not `machine exec`.

**Not verified.** This change does not call Fly. It does not show that the
SSH token can complete `ssh console` and `ssh sftp get`, or that it is
refused for `fly deploy`. The default expiry in that source is 20 years
(`time.Hour * 24 * 365 * 20`).

`<OWNER: create the backup Fly token>` From a terminal, for the app this job
backs up, with flyctl 0.5.1 or the same `tokens create ssh` command:

```bash
fly tokens create ssh -a <OWNER: Fly app name>
```

Paste the whole printed line, including a `FlyV1 ` prefix if the command
prints one, as the environment secret `FLY_API_TOKEN`. Quote it. Do not use
`fly tokens create deploy`, `fly tokens create org`, or `fly auth token`.
`<OWNER: SSH token expiry>` The source default is 20 years. Pass `--expiry`
when a shorter life is wanted. Revoke the token when the twin is destroyed,
and again when production backups are retired.

`<OWNER: confirm the SSH token on the app>` One `ssh console` and one
`ssh sftp get` of a disposable file, plus one `fly deploy` that must be
refused. If the SSH token cannot do the two SSH commands, stop and use the
fallback O7 names, `fly tokens create deploy -a <app>`, for that one app
only. Record which command was stored. Do not widen the token before that
check fails.

## Bucket lock and lifecycle

`<OWNER: add the 7-day bucket lock on offhost/>` In the Cloudflare dashboard,
open the bucket → Settings → Bucket lock rules → Add rule. Prefix `offhost/`.
Retention 7 days. O7 counts those 7 days from each object's upload. Cloudflare's
[bucket locks](https://developers.cloudflare.com/r2/buckets/bucket-locks/)
page shows that duration as an Age condition of 604800 seconds, and says a
rule with no prefix covers the whole bucket, so set the prefix. A blocked
single-object delete returns HTTP 409 `ObjectLockedByBucketPolicy`. A
`DeleteObjects` call, which is what prune uses, returns HTTP 200 and names
the locked keys in the body. `scripts/backup_store.py` treats those errors
as a failed prune. A lock longer than 30 days would fail that step. The
adopted lock is 7 days, so an object the prune deletes is already unlocked.
The lock wins over a lifecycle rule. It does not block the 37-day lifecycle. This page was
read on 2026-11-20. When the age starts was not tried against R2; the erasure
check records it.

`<OWNER: add the 37-day lifecycle rule on offhost/>` Settings → Object
lifecycle rules. Prefix `offhost/`, action delete, 37 days (the 30-day
retention plus 7). This is the operator backstop from O7. It expires by age
and cannot keep the newest object. Once the schedule has stopped, it removes
the last copy after 37 days. R2 may take up to about a day after the
expiration to remove an object. The lifecycle permission is an admin action;
do not put it on the workflow token. Use the command on
[object lifecycles](https://developers.cloudflare.com/r2/buckets/object-lifecycles/)
rather than guessing its flags. Do not promise this period in the player
notice until the erasure check is recorded (O6).

`<OWNER: leave bucket versioning off>` O7 records no versioning.

### Erasure check

Before any notice gives a backup deletion date or age limit, check and record
these three things on this bucket, using a disposable object under `offhost/`.
This change does not run the check.

1. **The configured lock.** Record the effective lock rule, then check that a
   delete attempted inside the seven days is refused and one after them
   succeeds. A delete that succeeds proves nothing on its own, because it
   also succeeds with no lock at all.
2. **The effective lifecycle rule.** Its prefix covers `offhost/` and its age
   is 37 days.
3. **No retained copy.** After the delete, no copy of the object can be
   retrieved.

`<OWNER: record the erasure check>` The effective lock, the lifecycle rule,
and whether any copy remained. Until that record exists, O6's notice wording
stands.

## Object names

Keys, not GitHub artifact names:

```text
offhost/worlds-backup-<app>-<YYYYMMDDTHHMMSSZ>.db
offhost/unvalidated-worlds-backup-<app>-<YYYYMMDDTHHMMSSZ>.db
```

`<YYYYMMDDTHHMMSSZ>` is the UTC time the snapshot started on the machine, the
same stamp the old artifact name used. The `unvalidated-` key is the quarantine
copy. Validation still fails the run. `scripts/backup_health.py` ignores every
quarantine key, a wrong app, an empty object, and a stamp in the future. Age is
the stamp in the name, not the upload time.

The runner's downloaded file is discarded with the job. It is not an artifact.
An app name that is a prefix of another (`enfolded` and `enfolded-staging`)
shares that list prefix. `enfolded-beta` and `enfolded-staging` do not.

## Retention and deletion

The workflow deletes this app's validated and quarantine objects whose
snapshot-start is at least 30 days old (30×24 hours from the stamp). The
workflow sets that number. A shell that runs `backup_gate.sh` without
`ENFOLDED_BACKUP_RETENTION_DAYS` uses the same 30.
It never deletes the newest validated object for the app, even when that
object is older than the retention period, so a stretch of failed backups
cannot empty the bucket of the last good copy. Quarantine objects are not
protected. The prune step runs only after the store step succeeded
(`steps.store.outcome == 'success'`). Objects for another app, and any key
that is not one of the two names above, are left alone. `delete` of one named
key can still remove the newest validated object. `delete-before` cannot: it
keeps the newest nonempty validated object, refuses a cutoff in the future,
and can print the keys with `--dry-run` before it deletes. `--after` limits
the window to snapshots that can contain text written at that time. A zero-byte
or otherwise unusable `Size` is not the copy that floor protects.

A bucket lifecycle rule is an outer age limit, not a copy of the workflow
prune. It expires objects by age and cannot keep the newest one. The adopted
rule is 37 days, prefix `offhost/`, action delete, as in
[Bucket lock and lifecycle](#bucket-lock-and-lifecycle). Any lifecycle rule
deletes the last copy once the schedule has been stopped that many days; 37
days only delays it by 7 days past the 30-day prune. On R2 this is the
bucket's Settings → Object Lifecycle Rules. R2 may take up to about a day
after the expiration to remove an object. The lifecycle permission is an
admin action; do not put it on the workflow token.
Infrequent Access is not the default: it has a minimum storage duration and
retrieval fees, and the free tier does not apply to it.

To delete one backup, from a shell that has the write key, the bucket, and the endpoint:

```bash
python scripts/backup_store.py delete \
  --app enfolded-beta \
  --key offhost/worlds-backup-enfolded-beta-20261003T113000Z.db
```

The command refuses a key that is not a validated or quarantine object for
that app. It can remove the newest validated object, because it names one key.

Redaction of the live database does not edit stored objects, and it does not
edit the machine-local copies at `/data/backups/*.db` or a downloaded
`./worlds-backup.db`. Those still hold the original words. Do this in order.
The workflow concurrency group serializes workflow runs, not this shell, so a
snapshot that started before the redaction can upload after a delete.

1. Redact the live text.
2. Dispatch `backup.yml` and wait until that run has finished.
3. Confirm `python scripts/backup_health.py --app enfolded-beta` reports a
   snapshot taken after the redaction. That newest nonempty validated object
   is the one `delete-before` keeps. If you delete first, the copy that still
   has the text is the one that stays.
4. Dry-run, then delete only the window that can contain the text. `--after`
   is when the text was written. `--before` is the last snapshot that can
   still contain it. A future `--before` is refused, and the command does not
   list or delete.

```bash
python scripts/backup_store.py delete-before \
  --app enfolded-beta \
  --after 20261001T000000Z \
  --before 20261003T113000Z \
  --dry-run
python scripts/backup_store.py delete-before \
  --app enfolded-beta \
  --after 20261001T000000Z \
  --before 20261003T113000Z
```

Then delete the machine-local copies that still hold the text. Retention is
the bound only for copies you do not delete on request.

## Restore

Install AWS CLI v2 on the machine that runs these commands. List or name the
object, download it, validate it, then restore on an isolated app. The health
check does not download anything. `get` writes the destination as mode `0600`
and removes a partial file if the transfer is interrupted. List and delete
wait at most 120 seconds. A download or upload waits
`ENFOLDED_BACKUP_S3_TIMEOUT_SECONDS` (default 3600; `0` or `none` waits until
the process ends). The workflow job still ends at 20 minutes, which bounds the
runner side. The child drops inherited `AWS_*` settings, including
`AWS_CA_BUNDLE`, so an operator behind a TLS-intercepting proxy needs the
store's certificate in the default trust store.

```bash
export ENFOLDED_BACKUP_S3_BUCKET=enfolded-backups
export ENFOLDED_BACKUP_S3_ENDPOINT=https://<ACCOUNT_ID>.r2.cloudflarestorage.com
export ENFOLDED_BACKUP_S3_REGION=auto
export ENFOLDED_BACKUP_S3_ACCESS_KEY_ID=...
export ENFOLDED_BACKUP_S3_SECRET_ACCESS_KEY=...

python scripts/backup_store.py get \
  --app enfolded-beta \
  --key offhost/worlds-backup-enfolded-beta-20261003T113000Z.db \
  --dest ./worlds-backup.db
python scripts/validate_backup.py ./worlds-backup.db
sha256sum ./worlds-backup.db
```

`validate_backup.py` checks integrity, `DELETE` journal mode, and the required
tables. It does not modify the file. A quarantine object can be downloaded for
salvage; it is not a healthy backup. Treat the file as private operator data.

Upload it to the isolated machine and restore there, as in
[fly-deployment.md](fly-deployment.md) §7. Do not restore over the continuing
participant world.

## Freshness

Run this after the workflow has finished, from a shell with AWS CLI v2, the
bucket, the endpoint, and either the write key or the optional read key. That
read key can download every backup; it is not limited to this command, and
prune and `delete-before` list with it whenever both read variables are set.
The command itself only lists. It is not a step in `backup.yml`. Until those
values are set the command exits 2. Once they are set and no validated object
exists, it reports `missing`. A half-set read pair exits 2 and names the
incomplete credential; it does not print the key.

```bash
python scripts/backup_health.py --app enfolded-beta
```

Exit 0 means the newest validated nonempty object for that app has a
snapshot-start within 60 minutes. Exit 1 means missing or stale. Exit 2 means
the listing could not be read. `--max-age-minutes 1` is the stale-window drill:
it exits 1 when the newest good object is older than a minute. Staging objects
do not satisfy the production app name.

Offline, the same decision runs against a saved listing and does not contact
the bucket:

```bash
python scripts/backup_health.py --app enfolded-beta --objects listing.json
```

## Re-arming production backups

A separate owner act, from
[O14](../roadmap/owner-decisions-2026-11-20.md#o14-observability-and-alerts-items-11-13).
A manual dispatch snapshots the running app over `flyctl ssh`, so no
production object can exist before the first production deploy. Production
backups are re-armed after that deploy.

`<OWNER: re-arm production backups>`

Before the first production boot:

1. Store the production Fly token (`fly tokens create ssh -a enfolded-beta`)
   and the bucket secrets in the `backup` environment.
2. Leave `ENFOLDED_BACKUP_APP` unset, or set it to `enfolded-beta`.
3. Re-enable the "Off-host backup" workflow if it was disabled.
4. Retarget the external dispatcher to production, and leave it paused.

The pre-boot recovery evidence is the staging restore.

After the first production deploy, before any invitation:

1. Run one manual dispatch from `main` and confirm a validated production
   snapshot is stored, not a quarantined one.
2. Only then `<OWNER: set ENFOLDED_BACKUP_REQUIRED=true>`.
3. Enable the external dispatcher. GitHub's own schedule alone has shown
   five-hour gaps against the one-hour bound.
4. Confirm successive validated production snapshots meet the one-hour bound.
5. Point a new heartbeat monitor at production. Alerts go to the project
   address, with the second operator copied (O14). The monitor is hosted
   separately from the dispatcher.

## Retiring the twin's backup schedule

After the twin's final snapshot, from O14. With
`ENFOLDED_BACKUP_REQUIRED=true`, every later run fails, and the workflow also
runs on its own cron at :17 and :47 each hour. Unset,
`ENFOLDED_BACKUP_APP` falls back to `enfolded-beta`, so a staging token left
in place would be aimed at production.

`<OWNER: retire the twin backup schedule>`

1. Stop the scheduler's dispatch.
2. Disable the "Off-host backup" workflow.
3. Delete the `ENFOLDED_BACKUP_REQUIRED` and `ENFOLDED_BACKUP_APP` variables.
4. Revoke the backup token and delete its `backup` environment secret.
5. Pause or delete the twin's heartbeat monitor.

Deleting the twin's objects by hand waits until the 7-day lock allows it.
Emptying the bucket is refused while a bucket lock rule is still configured
([bucket locks](https://developers.cloudflare.com/r2/buckets/bucket-locks/)).

## Rehearsal checklist

Do this on the staging app before any production history.

- [ ] `<OWNER: create the GitHub Actions environment named backup>` and `<OWNER: set the backup environment's deployment branches to main only>`, with administrator bypass off, before the workflow runs on `main`.
- [ ] Bucket exists, Standard storage, public development URL off, no custom domain, no managed public access. Versioning is off.
- [ ] Token is Object Read & Write on that bucket only. A disposable put and delete, on keys outside `offhost/`, succeeded, including one `DeleteObjects` of two keys. Admin Read & Write was not used.
- [ ] `<OWNER: add the 7-day bucket lock on offhost/>` and `<OWNER: add the 37-day lifecycle rule on offhost/>`.
- [ ] Environment secrets are set, and `<OWNER: delete the repository copies of the backup secrets>` is done. The three repository variables are the only ones. `ENFOLDED_BACKUP_APP` is `enfolded-staging`. `ENFOLDED_BACKUP_REQUIRED` is still unset.
- [ ] `<OWNER: create the backup Fly token>` with `fly tokens create ssh`, and `<OWNER: confirm the SSH token on the app>`.
- [ ] Manual dispatch of `backup.yml` from `main` stores a validated snapshot. The job summary does not print the object key, the bucket, or the account id, and the log has no artifact upload.
- [ ] `python scripts/backup_health.py --app <staging-app>` exits 0. `--max-age-minutes 1` against an old stamp exits 1.
- [ ] Download, `validate_backup.py`, checksum, and `python main.py restore` on the isolated staging machine. Every backup containing `private_chat_messages` requires `--deletions <latest-export>` with the latest independently preserved operator deletion record, even when a current database exists; a fresh-boot empty export is not authoritative. Follow the [restore procedure](fly-deployment.md#restoring-from-a-backup), then record the checksum, snapshot time, app, release SHA, and elapsed time.
- [ ] A deliberately invalid snapshot (or a failed validation) is stored only under `offhost/unvalidated-worlds-backup-...` and the run is red. The health check does not count it.
- [ ] With `ENFOLDED_BACKUP_REQUIRED=true` and one required value removed, a dispatch fails and uploads nothing. Restore the value afterward.
- [ ] `<OWNER: record the erasure check>` on a disposable `offhost/` object.
- [ ] Delete rehearsal objects that are no longer needed only after the lock allows it (`delete` or `delete-before`).
- [ ] Production follows [Re-arming production backups](#re-arming-production-backups). Do not set `ENFOLDED_BACKUP_REQUIRED=true` for production before the first production deploy has stored a validated snapshot.

## Cost

Cloudflare's [R2 pricing](https://developers.cloudflare.com/r2/pricing/) (page
updated 30 October 2026) includes, each month, for Standard storage: **10
GB-month** of storage, **1 million** Class A operations, and **10 million**
Class B operations. Egress is free. The free tier does not apply to Infrequent
Access. Past the included Standard storage, the published rate is **$0.015 per
GB-month**. Operations past the included counts are $4.50 per million Class A
and $0.36 per million Class B. Cloudflare rounds usage up to the next billing
unit.

The free 10 GB-month does not cover a half-hourly copy of a database this
size. This assumes each snapshot is about **300 MB**. That size has not been
measured on a hosted database; nothing is deployed, so there is no production
`worlds.db` to weigh. A 30-minute cadence kept for the recorded 30 days is
**1,440** objects, plus any quarantine copies:

`1,440 × 300 MB = 432,000 MB = 432 GB-month`

At the published Standard rate of **$0.015 per GB-month**, 432 GB-month is
**$6.48** before the included 10 GB-month. That allowance leaves **422
GB-month**, which is **$6.33**. The free tier covers about **6.9 MB** per
copy (`10 / 1,440` GB), not a few hundred megabytes. At 500 MB per copy the
same count is 720 GB-month: **$10.80** before the allowance and **$10.65**
after it (`710 × $0.015`). The puts and lists of one app stay inside the
operation allowance, so that charge is **$0**. Check the pricing page again
when the database has a measured size. The nominal half-hourly count is not
what GitHub has been starting; the
[cadence record](../evaluation/2026-11-11-backup-schedule-cadence.md) measured
about one run every five hours. This note is not a bill, and it is not a
decision to spend that money.
