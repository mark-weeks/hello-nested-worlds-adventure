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
| `BACKUP_FLY_SSH_TOKEN` | `<OWNER: BACKUP_FLY_SSH_TOKEN>` from the SSH token command below. The job passes this value to flyctl as `FLY_API_TOKEN`. Not an organization token, and not a deploy token |
| `ENFOLDED_BACKUP_S3_ACCESS_KEY_ID` | `<OWNER: ENFOLDED_BACKUP_S3_ACCESS_KEY_ID>` |
| `ENFOLDED_BACKUP_S3_SECRET_ACCESS_KEY` | `<OWNER: ENFOLDED_BACKUP_S3_SECRET_ACCESS_KEY>` |
| `ENFOLDED_BACKUP_S3_BUCKET` | `<OWNER: ENFOLDED_BACKUP_S3_BUCKET>` Bucket name. A variable would be printed in the public job log |
| `ENFOLDED_BACKUP_S3_ENDPOINT` | `<OWNER: ENFOLDED_BACKUP_S3_ENDPOINT>` `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`. The account id is not a variable |
| `ENFOLDED_BACKUP_S3_LIST_ACCESS_KEY_ID` | `<OWNER: ENFOLDED_BACKUP_S3_LIST_ACCESS_KEY_ID>` The read-only pair. Set both list secrets or neither |
| `ENFOLDED_BACKUP_S3_LIST_SECRET_ACCESS_KEY` | `<OWNER: ENFOLDED_BACKUP_S3_LIST_SECRET_ACCESS_KEY>` |
| `ENFOLDED_BACKUP_HEARTBEAT_URL` | Optional. `<OWNER: heartbeat URL>`. Only the ping step reads it. An empty value sends no request. [Backup dispatch and the heartbeat](backup-dispatch.md). Not one of the six bucket secrets |

`<OWNER: delete the repository copies of the backup secrets>`
If an environment secret is missing, `secrets.<NAME>` falls back to a
repository secret of the same name. GitHub's
[secrets reference](https://docs.github.com/en/actions/reference/security/secrets)
says the lowest level that has the name wins, so a missing environment
secret leaves the repository copy in place. The job would keep running on
that copy, and the run would look the same as one that read the environment.
Delete the repository copies of the six `ENFOLDED_BACKUP_S3_*` names and of
`FLY_API_TOKEN`. Then confirm that Settings → Secrets and variables →
Actions → Repository secrets lists none of those seven names, and none of
`BACKUP_FLY_SSH_TOKEN`.

The job reads the Fly token as `secrets.BACKUP_FLY_SSH_TOKEN`. That name is
not `FLY_API_TOKEN`, so a leftover repository deploy token is not what this
job receives when the environment secret is missing or mistyped. The six
bucket secrets still use their `ENFOLDED_BACKUP_S3_*` names, so a repository
copy of one of those is what the job receives until that copy is deleted.
A repository secret is also readable by a workflow on another branch.

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

A typo in the required flag, the region, the endpoint, or the bucket fails
the job. It does not turn the backup off. Retention is the literal 30 in the
workflow, so there is no retention value to mistype. A read-only list pair
with exactly one half set fails the gate before a snapshot is stored. Unset bucket settings
with the required flag unset or `false` make an inactive run: no snapshot is
taken and nothing is uploaded. Setting only `FLY_API_TOKEN` does not upload
anywhere.

## Fly token

The job runs `flyctl ssh console` and `flyctl ssh sftp get` against one app.
A token that can do that can read participant chat and reports on that app.
The same token can add a WireGuard peer on that app's Fly organization. A
peer joins the organization's private network. That network reaches the
private addresses of every app in the org, not only the app named with `-a`.
If `enfolded-staging` and `enfolded-beta` share an organization, the twin's
backup token can reach production that way, without the public edge.

**Verified, from source, not from a live call.** flyctl 0.5.1 is the version
the workflow installs. Its `fly tokens create` command, in
`internal/command/tokens/create.go` at tag `v0.5.1`, has a subcommand `ssh`
whose help text is "Create token for SSH'ing to a single app. To be able to
SSH to an app, this token is also allowed to connect to the org's wireguard
network." The implementation mints an app deploy-profile token and then
prints a different token: read on the org and app, plus mutations limited
to `issueCertificate` and `addWireGuardPeer`. That second mutation is what
the help text calls connecting to the org's WireGuard network. It can add a
peer, and that peer is not limited to the app named with `-a`. The unattenuated deploy token is not what the command prints. The same file's
`deploy` subcommand prints the unattenuated app token, which can manage the
app. `machine-exec` can limit shell commands, but this job uses `ssh console`
and `ssh sftp get`, which are the SSH token's commands, not `machine exec`.

**Not verified.** This change does not call Fly. It does not show that the
SSH token can complete `ssh console` and `ssh sftp get`, and it does not
show how far a peer created with this token can reach. The default expiry
in that source is 20 years (`time.Hour * 24 * 365 * 20`).

`<OWNER: create the backup Fly token>` From a terminal, for the twin, with
flyctl 0.5.1 or the same `tokens create ssh` command:

```bash
fly tokens create ssh -a enfolded-staging --expiry 720h
```

`<OWNER: SSH token expiry>` `720h` is 30 days. That is the life to pass for
the twin. The source default, with no `--expiry`, is 20 years
(`time.Hour * 24 * 365 * 20` on `newSSH` in flyctl 0.5.1). Pass a different
`--expiry` when 30 days is the wrong life. A missed revocation then expires
on its own. Revoke the token when the twin is destroyed (O7). Production
uses the same 720-hour life when it is re-armed, and
`<OWNER: production backup token rotation>` replaces that secret before the
720 hours run out.

The command prints one line. Paste that line into the GitHub environment
secret `BACKUP_FLY_SSH_TOKEN` with no characters added. The secret field
stores every character typed there, so a quote mark becomes part of the
token and flyctl rejects it. Include a `FlyV1 ` prefix when the command
prints one. Quoting belongs on a shell argument, in the confirmation below,
and not in the secret field. Do not use `fly tokens create deploy`,
`fly tokens create org`, or `fly auth token`.

`<OWNER: put the twin in its own Fly organization, or record that this org-wide WireGuard reach is accepted>`
Do not store this token for a twin that shares production's organization
until that choice is recorded. A token that can reach the production
organization is still never a fallback for the staging deploy workflow.

`<OWNER: confirm the SSH token on the app>` Confirm the printed token. Do
not confirm it by deploying.

The committed `fly.toml` sets `app = "enfolded-beta"`. A bare `fly deploy`
from this checkout selects that production app. The terminal may still be
the owner's `fly auth login`, so that deploy can ship production, and a
denial that names the wrong app can make an overprivileged staging token
look SSH-only. Do not run `fly deploy` here.

flyctl 0.5.1's `fly tokens debug`
([`internal/command/tokens/debug.go`](https://github.com/superfly/flyctl/blob/v0.5.1/internal/command/tokens/debug.go))
decodes the macaroon and prints the caveats. It does not call Fly. In that
version, `Load` applies the config file, then `FLY_ACCESS_TOKEN` when it is
set and otherwise `FLY_API_TOKEN`, then `-t` when that flag is passed
(`internal/config/config.go`).

flyctl 0.5.1 stores config under `FLY_CONFIG_DIR` when that variable is
set, and otherwise under `~/.fly`
([`helpers/config.go`](https://github.com/superfly/flyctl/blob/v0.5.1/helpers/config.go)
`GetConfigDirectory`). The agent socket is `fly-agent.sock` in that same
directory
([`internal/command/agent/agent.go`](https://github.com/superfly/flyctl/blob/v0.5.1/internal/command/agent/agent.go)
`socketPath`). A terminal that has already used `fly ssh` reuses the saved
peer and the running agent, so this check would never exercise the candidate
token's `addWireGuardPeer`. The empty directory below is what makes the
check use a new peer. The first manual dispatch from `main` is the proof
that the stored secret works: a GitHub runner starts with no saved flyctl
state. This local check is the check that the printed token can open a
shell and copy a file. In a private terminal, with the exact printed token:

```bash
unset FLY_ACCESS_TOKEN FLY_API_TOKEN
export FLY_CONFIG_DIR="$(mktemp -d)"
read -rs FLY_API_TOKEN
export FLY_API_TOKEN
fly tokens debug
```

At the silent prompt, paste the printed token and press Enter. Do not type
the token after `FLY_API_TOKEN=`. A command that includes the token is saved
in shell history and can appear in the process list. `read -rs` does not
echo it and does not put it on a command line. The token is in the process
environment while the commands below run. Read the JSON on that terminal
and delete it. Do not paste it into a log, a ticket, or this repository.
One decoded macaroon lists mutations `issueCertificate` and `addWireGuardPeer`
and no others. Another is the read attenuation `runSSH` adds
(`resset.ActionRead`). Stop if the mutations list is anything else, or if
the output is the single unattenuated token `fly tokens create deploy`
prints. Seeing exactly those two mutations is the expected SSH token. It is
not evidence that a peer cannot reach another app: `addWireGuardPeer` is
the organization-wide permission. The app id in that JSON is numeric
(`Apps` in macaroon v0.3.2, the module flyctl 0.5.1 requires). Matching
that number to a name is not this check.

The SSH checks use the same shell and name the app. `-a` is required.
Omitting it follows `fly.toml` to `enfolded-beta`. Do not pass the token
with `-t`.

```bash
fly wireguard list <OWNER: org slug>
fly ssh console -a <OWNER: Fly app name> -C "echo backup-token-ok"
fly ssh sftp get -a <OWNER: Fly app name> /data/backups/<disposable>.db <local-file>
fly wireguard list <OWNER: org slug>
fly wireguard remove <OWNER: org slug> <OWNER: peer name this check added>
fly agent stop
rm -rf "$FLY_CONFIG_DIR"
unset FLY_CONFIG_DIR FLY_API_TOKEN
```

`fly wireguard list` prints every peer in the organization
(`GetWireGuardPeers` in flyctl 0.5.1), not only the peer in this directory.
Record the list before the SSH commands and again after. Remove only a peer
that this check added. `fly wireguard remove` takes the org slug and that
peer name (`runWireguardRemove`). If list or remove is refused, stop and
remove the new peer with the owner's own login in another terminal that is
not using this token. Do not store a wider token so the removal can succeed.

Use a disposable file, not the live chronicle. If either SSH command fails,
stop and use the fallback O7 names, `fly tokens create deploy -a <app>`,
for that one app only. Record which command was stored. Do not widen the
token before that check fails.

A live test that the token cannot deploy needs its own authorization. Run
it only against a disposable app created for that test, with `-a` set to
that app and `FLY_API_TOKEN` set to the candidate as above. Do not use `enfolded-beta`.
A refusal that names a different app does not show the
token is SSH-only. This change did not run the debug command or the SSH
commands.

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
workflow passes `30` to `backup_store.py prune --retention-days`.
`backup_gate.sh` only checks `ENFOLDED_BACKUP_RETENTION_DAYS` when it is
set. A manual prune must pass `--retention-days 30`.
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

One fresh object is not the seven-day bound. Successive validated
snapshot-start times are
[`scripts/backup_freshness_proof.py`](backup-dispatch.md#the-seven-day-bound-proof).
The external scheduler and the separately hosted heartbeat are
[Backup dispatch and the heartbeat](backup-dispatch.md).

## Re-arming production backups

A separate owner act, from
[O14](../roadmap/owner-decisions-2026-11-20.md#o14-observability-and-alerts-items-11-13).
A manual dispatch snapshots the running app over `flyctl ssh`, so no
production object can exist before the first production deploy. Production
backups are re-armed after that deploy.

`<OWNER: re-arm production backups>`

Before the first production boot:

1. Store the production Fly token
   (`fly tokens create ssh -a enfolded-beta --expiry 720h`) as
   `BACKUP_FLY_SSH_TOKEN`, and the bucket secrets, in the `backup`
   environment. `<OWNER: production backup token rotation>` replaces that
   secret before the 720 hours run out.
2. Leave `ENFOLDED_BACKUP_APP` unset, or set it to `enfolded-beta`.
3. Confirm `ENFOLDED_BACKUP_HEARTBEAT_URL` is unset, then re-enable the
   "Off-host backup" workflow if it was disabled.
4. Retarget the external dispatcher to production, and leave it paused.

The pre-boot recovery evidence is the staging restore.

After the first production deploy, before any invitation:

1. Run one manual dispatch from `main` and confirm a validated production
   snapshot is stored, not a quarantined one.
2. Only then `<OWNER: set ENFOLDED_BACKUP_REQUIRED=true>`.
3. Enable the external dispatcher. GitHub's own schedule alone has shown
   five-hour gaps against the one-hour bound.
4. Confirm successive validated production snapshots meet the one-hour bound
   with `python scripts/backup_freshness_proof.py --app enfolded-beta --since <UTC snapshot-start of the dispatcher's first validated object>`.
   That check ignores the manual dispatch and any older object, starts at the
   first snapshot-start at or after that instant, and requires at least two.
   The printed window starts at that snapshot, not at the filter. Each
   checked snapshot needs the `.ready` marker the store writes after the
   snapshot PUT returns. A snapshot from before that marker existed does not
   pass. `--from-first` keeps the manual object, so a gap of more than an
   hour before the dispatcher fails until seven days exist. The seven-day
   window is not this gate. The twin's rehearsal stays the seven-day command.
5. Point a new heartbeat monitor at production, and only then set
   `ENFOLDED_BACKUP_HEARTBEAT_URL` to that monitor. The twin's URL has to be
   gone already (the retirement step below). Alerts go to the project
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
6. After the final twin ping, delete the `backup` environment secret
   `ENFOLDED_BACKUP_HEARTBEAT_URL`. Do this before the workflow is enabled
   for production. The secret is shared by both apps. O14's five steps
   predate it; this is the extra step.

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
- [ ] `<OWNER: create the backup Fly token>` with `fly tokens create ssh -a enfolded-staging --expiry 720h`. Paste the printed line into `BACKUP_FLY_SSH_TOKEN` with no added quotes. `<OWNER: confirm the SSH token on the app>` with `FLY_CONFIG_DIR` set to an empty directory, `fly tokens debug`, and the two SSH commands bound to that token and `-a`. Remove any WireGuard peer that check added. Do not run `fly deploy` from this checkout.
- [ ] Manual dispatch of `backup.yml` from `main` stores a validated snapshot. The job summary does not print the object key, the bucket, or the account id, and the log has no artifact upload.
- [ ] `python scripts/backup_health.py --app <staging-app>` exits 0. `--max-age-minutes 1` against an old stamp exits 1.
- [ ] The [dispatcher and the heartbeat](backup-dispatch.md) are the two hosts from O14. After seven days of validated snapshots, `python scripts/backup_freshness_proof.py --app <staging-app>` exits 0. A green workflow run is not that proof.
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
