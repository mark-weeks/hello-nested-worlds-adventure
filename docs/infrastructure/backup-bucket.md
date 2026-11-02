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
then fails the job instead of reporting success.

Cloudflare R2 is an example of an S3-compatible store, not a vendor Mark has
chosen. A 30-day retention is the example the job uses when
`ENFOLDED_BACKUP_RETENTION_DAYS` is unset, not a recorded retention period.
Neither choice is an ADR. ADR-005 still describes hour-stamped GitHub
artifacts kept for 90 days, and this runbook does not amend it. The workflow
does not hard-code an account, bucket, or endpoint. Another S3-compatible
store is the same secrets and variables with a different endpoint and region.
The client uses path-style addressing (`{endpoint}/{bucket}/{key}`) and sends
checksums only when the operation requires them, which current AWS CLI
releases need for R2 and for other S3-compatible endpoints.

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
the secret `ENFOLDED_BACKUP_S3_BUCKET`. A repository variable is printed in
the job's environment, and this repository's logs are public.

Find the account ID on the same R2 overview page. The S3 endpoint is:

```text
https://<ACCOUNT_ID>.r2.cloudflarestorage.com
```

No path, query, user, or password. A jurisdictional bucket uses its
jurisdictional host instead (`https://<ACCOUNT_ID>.eu.r2.cloudflarestorage.com`,
or the `.us.` / `.fedramp.` host). Store that URL as the secret
`ENFOLDED_BACKUP_S3_ENDPOINT`. The host contains the account id. For this R2
example, `ENFOLDED_BACKUP_S3_REGION` stays `auto`. For Amazon S3, set the
region to the bucket's region and the endpoint to that region's S3 API host.

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
is caught before the job depends on it. The secret access key is shown once.

Optional, for the freshness command only: a second token with **Object Read
only**, same bucket. The health check uses it when both
`ENFOLDED_BACKUP_S3_LIST_ACCESS_KEY_ID` and
`ENFOLDED_BACKUP_S3_LIST_SECRET_ACCESS_KEY` are set. Otherwise it uses the
write key. Do not set only one of the list pair.

## GitHub settings

Repository **secrets** (Settings → Secrets and variables → Actions → Secrets):

| Secret | Value |
|---|---|
| `FLY_API_TOKEN` | Deploy token for one app: `fly tokens create deploy -a <app>`. Not an organization token |
| `ENFOLDED_BACKUP_S3_ACCESS_KEY_ID` | Access key id for the example token, or the equivalent on another store |
| `ENFOLDED_BACKUP_S3_SECRET_ACCESS_KEY` | Secret access key |
| `ENFOLDED_BACKUP_S3_BUCKET` | Bucket name. A variable would be printed in the public job log |
| `ENFOLDED_BACKUP_S3_ENDPOINT` | `https://<ACCOUNT_ID>.r2.cloudflarestorage.com` for the R2 example. The account id is not a variable |

Repository **variables** (the same page, Variables tab):

| Variable | Value |
|---|---|
| `ENFOLDED_BACKUP_APP` | Fly app name. Defaults to `enfolded-beta` when unset. Use the staging app during rehearsal |
| `ENFOLDED_BACKUP_S3_REGION` | `auto` for the R2 example. Defaults to `auto` when unset |
| `ENFOLDED_BACKUP_RETENTION_DAYS` | Optional. Integer from 1 to 3650. When unset, the job uses **30** as an example, not as a decision Mark has made |
| `ENFOLDED_BACKUP_REQUIRED` | Leave unset until the first real object is in the bucket. Then set exactly `true` |

A typo in the required flag, the region, the retention, the endpoint, or the
bucket fails the job. It does not turn the backup off. Unset bucket settings
with the required flag unset or `false` make an inactive run: no snapshot is
taken and nothing is uploaded. Setting only `FLY_API_TOKEN` does not upload
anywhere.

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

## Retention and deletion

The workflow deletes this app's validated and quarantine objects whose
snapshot-start is at least `ENFOLDED_BACKUP_RETENTION_DAYS` old (the example
when that variable is unset is 30, counted as 30×24 hours from the stamp).
It never deletes the newest validated object for the app, even when that
object is older than the retention period, so a stretch of failed backups
cannot empty the bucket of the last good copy. Quarantine objects are not
protected. The prune step runs only after the store step succeeded
(`steps.store.outcome == 'success'`). Objects for another app, and any key
that is not one of the two names above, are left alone. `delete` and
`delete-before` are the explicit exception: they remove the newest validated
object when an operator asks them to.

A bucket lifecycle rule is an outer age limit, not a copy of the workflow
prune. It expires objects by age and cannot keep the newest one. Set it to
the workflow retention plus 7 days or more, prefix `offhost/`, action delete.
A rule with the same day count as the workflow will delete the last good
copy when the schedule stops, which cancels the keep-newest floor. On R2 this
is the bucket's Settings → Object Lifecycle Rules. Wrangler can set the same
rule; use the command on
[object lifecycles](https://developers.cloudflare.com/r2/buckets/object-lifecycles/)
rather than guessing its flags. R2 may take up to about a day after the
expiration to remove an object. The lifecycle permission is an admin action;
do not put it on the workflow token.
Infrequent Access is not the default: it has a minimum storage duration and
retrieval fees, and the free tier does not apply to it.

To delete one backup, from a shell that has the write key, the bucket, and the endpoint:

```bash
python scripts/backup_store.py delete \
  --app enfolded-beta \
  --key offhost/worlds-backup-enfolded-beta-20261003T113000Z.db
```

The command refuses a key that is not a validated or quarantine object for
that app. To delete every such object whose snapshot-start is at or before a
time (the copies that still contain text you have since redacted):

```bash
python scripts/backup_store.py delete-before \
  --app enfolded-beta \
  --before 20261003T113000Z
```

Redaction of the live database does not edit these objects. Delete the objects
that still contain the original words. Retention is the bound only for copies
you do not delete on request.

## Restore

List or name the object, download it, validate it, then restore on an isolated
app. The health check does not download anything.

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
bucket, the endpoint, and either the list-only key or the write key. It is
not a step in `backup.yml`. Until those values are set the command exits 2.
Once they are set and no validated object exists, it reports `missing`.

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

## Rehearsal checklist

Do this on the staging app before any production history.

- [ ] Bucket exists, Standard storage, public development URL off, no custom domain, no managed public access.
- [ ] Token is Object Read & Write on that bucket only. A disposable put and delete succeeded. Admin Read & Write was not used.
- [ ] Secrets and variables are set. `ENFOLDED_BACKUP_REQUIRED` is still unset.
- [ ] Manual dispatch of `backup.yml` stores a validated snapshot. The job summary does not print the object key, the bucket, or the account id, and the log has no artifact upload.
- [ ] `python scripts/backup_health.py --app <staging-app>` exits 0. `--max-age-minutes 1` against an old stamp exits 1.
- [ ] Download, `validate_backup.py`, checksum, and `python main.py restore` on the isolated staging machine. Record the checksum, snapshot time, app, release SHA, and elapsed time.
- [ ] A deliberately invalid snapshot (or a failed validation) is stored only under `offhost/unvalidated-worlds-backup-...` and the run is red. The health check does not count it.
- [ ] With `ENFOLDED_BACKUP_REQUIRED=true` and one required value removed, a dispatch fails and uploads nothing. Restore the value afterward.
- [ ] Delete the rehearsal objects if they are no longer needed (`delete` or `delete-before`).
- [ ] Set the lifecycle rule's prefix to `offhost/` and its day count to the retention plus 7 or more. The rule does not keep the newest object.
- [ ] Switch `ENFOLDED_BACKUP_APP` to production only when that app is the one being backed up. Set `ENFOLDED_BACKUP_REQUIRED=true` before accepting permanent history.

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
`worlds.db` to weigh. A 30-minute cadence kept for the example 30 days is
**1,440** objects, plus any quarantine copies:

`1,440 × 300 MB = 432,000 MB = 432 GB-month`

At the published Standard rate of **$0.015 per GB-month**, 432 GB-month is
**$6.48**, roughly **$6.30** a month if the file is a little under 300 MB.
The included 10 GB-month holds about **7 MB** per copy (`10 GB / 1,440`),
not a few hundred megabytes. At about 500 MB per copy the same count is
about $10.80 a month (`1,440 × 0.5 GB × $0.015`). The puts and lists of one
app stay inside the operation allowance. Check the pricing page again when
the database has a measured size, or when Mark chooses a different retention.
This note is not a bill, and it is not a decision to spend that money.
