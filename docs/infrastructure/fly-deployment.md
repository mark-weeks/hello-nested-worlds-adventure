# Deploying to Fly.io

This guide walks through standing up Enfolded on Fly.io for
the initial beta. It assumes you have shell access to a clone of this
repository and an Anthropic key in hand.

End state: one VM in one region, one shared canonical world, SQLite on a
persistent volume, the React frontend baked into the image, Sentry wired in,
and per-user invite keys distributed to your testers.

---

## 1. Prerequisites

- A [Fly.io account](https://fly.io) with billing set up (the beta fits
  in the free tier, but card-on-file is required).
- The `flyctl` CLI installed locally:
  ```bash
  curl -L https://fly.io/install.sh | sh
  fly auth login
  ```
- An Anthropic API key (`ANTHROPIC_API_KEY`).
- Optionally, a fal.ai API key (`FAL_KEY`). Scene imagery is an
  enhancement wash over the built-in deterministic node art — without
  the key, every node still renders its generative art; with it,
  `/image` layers AI backgrounds on top.
- Optionally, a Sentry DSN (`SENTRY_DSN`). Sentry is already a default
  dependency — setting the DSN is sufficient to activate it.

---

## 2. Add the deployment files

Three files in the repo root. Commit them in a single PR — they're the
deployment contract.

### `Dockerfile`

Multi-stage build: Node stage compiles the frontend, Python stage
installs the package and serves it. Setting `HOME=/data` puts the
SQLite store on the persistent volume.

```dockerfile
# --- Stage 1: build the React + PixiJS frontend ---
FROM node:20-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./frontend/
RUN cd frontend && npm ci
COPY frontend ./frontend
COPY static ./static
# The postbuild step copies the project license and notices into static/app.
COPY LICENSE NOTICE THIRD_PARTY_NOTICES.txt ./
RUN cd frontend && npm run build

# --- Stage 2: Python runtime ---
FROM python:3.11-slim
WORKDIR /app

# DB lives at $HOME/.nested-worlds/worlds.db — point HOME at the volume.
ENV HOME=/data \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Install Python deps first for layer caching.
COPY pyproject.toml ./
RUN pip install -e . || true

# Copy the rest of the source.
COPY . .

# Overlay the freshly built frontend bundle.
COPY --from=frontend /build/static ./static

# Reinstall now that the package source is present so the editable
# install picks up the modules.
RUN pip install -e .

EXPOSE 8080
CMD ["python", "main.py", "serve", "--host", "0.0.0.0", "--port", "8080"]
```

### `.dockerignore`

Keeps the image small and avoids leaking local state into the build
context.

```
.git
.github
.pytest_cache
__pycache__
*.pyc
*.egg-info
.env
.venv
frontend/node_modules
docs
tests
```

### `fly.toml`

> **The committed `fly.toml` at the repo root is authoritative** — it is
> guarded by `tests/test_deploy_config.py` and may drift ahead of the
> illustrative copy below (sizing and limits in particular). When in doubt,
> read the real file.

Pin to a single region, a single machine, and mount a volume at
`/data`. `NESTED_WORLDS_TRUST_PROXY=1` tells the rate limiter to trust
Fly's edge proxy and read the real client IP from the `Fly-Client-IP`
header (Fly overwrites it, so it can't be spoofed). Do **not** rely on
the left-most `X-Forwarded-For` value — Fly *appends* the real client IP,
so the left-most entry is attacker-controlled and would let a client mint
a fresh rate-limit bucket per request. The `[http_service.concurrency]`
block bounds connections at the Fly-proxy layer; the app additionally caps
concurrent WebSockets via `NESTED_WORLDS_MAX_WS_CONNECTIONS` /
`NESTED_WORLDS_MAX_WS_PER_IP`.

`NESTED_WORLDS_CANONICAL_SEED=382` is the deliberately curated launch choice
(`docs/evaluation/2026-08-03-launch-world-census.md`), not a player input.
ADR-007 makes the first production birth permanent and shared; a heartbeat tick
or `/world` request can materialize it once the server is running. Confirm the
production volume is empty before that first start. Staging uses its own
disposable volume, so its birth is rehearsal data, never production canon.

```toml
app = "enfolded-beta"          # change to your unique app name
primary_region = "iad"              # pick the region closest to your testers

[build]
  dockerfile = "Dockerfile"

[env]
  HOME = "/data"
  NESTED_WORLDS_CANONICAL_SEED = "382"    # curated pre-launch; one shared world
  NESTED_WORLDS_TRUST_PROXY = "1"          # safe only behind Fly's edge
  NESTED_WORLDS_MAX_WS_CONNECTIONS = "96"  # under the proxy hard_limit; headroom on 1GB
  SENTRY_ENVIRONMENT = "beta"

[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = false        # keep the in-memory rate limiter / rooms alive
  min_machines_running = 1          # never suspend: persistent WS + in-memory state
  processes = ["app"]

  [http_service.concurrency]
    type = "connections"            # WS sessions are long-lived connections
    soft_limit = 120
    hard_limit = 150                # leave margin above the app's WS cap (96)

  [http_service.checks.health]
    type = "http"
    method = "GET"
    path = "/health"                # cheap, gate-exempt, never calls the LLM
    interval = "30s"
    timeout = "5s"
    grace_period = "10s"

[mounts]
  source = "enfolded_data"
  destination = "/data"

[[vm]]
  size = "shared-cpu-1x"
  memory = "1024mb"                 # headroom for thread-per-connection + in-flight LLM
```

---

## 3. First deploy

Before running anything: **edit the committed `fly.toml`** — set a
unique `app` name and the `primary_region` closest to your testers, and
commit the change. That file is the deployment contract
(`tests/test_deploy_config.py` guards it); the commands below must match
what it says.

> **The first deploy starts the permanent world.** Under the continuity
> policy the database is never wiped between cohorts — whatever your
> first testers do becomes history the project carries forward, forever.
> Deploy when you mean it.

Run these from the repo root.

```bash
# Create the app (no deploy yet), matching the name you set in fly.toml.
fly apps create enfolded-beta

# Provision the persistent volume in the same region as the app.
fly volumes create enfolded_data --region iad --size 1

# Set runtime secrets. These never appear in logs or the image.
# FAL_KEY and SENTRY_DSN are optional — omit either line freely.
fly secrets set \
  ANTHROPIC_API_KEY=sk-ant-... \
  FAL_KEY=... \
  SENTRY_DSN=https://...ingest.sentry.io/...

# REQUIRED for any public deployment: close the invite gate. There is no
# shared key — the gate is the per-user `invite_keys` table and stays OPEN
# until the first per-user key is minted (§6). An ungated server is an open
# proxy to your Anthropic budget (the daily caps bound the damage; they
# don't prevent strangers spending it). Mint the first per-user key in §6
# BEFORE you announce the URL, and do not share the URL until then.

# Deploy. (--first-deploy skips the pre-deploy backup — nothing to back
# up yet. Every subsequent deploy goes through scripts/deploy.sh plain.)
scripts/deploy.sh --first-deploy
```

`fly deploy` builds the Docker image remotely, ships it to the region,
attaches the volume, and rolls the machine over to the new image. First
deploy takes ~3-5 minutes.

### 3a. Staging rehearsal — before the permanent world begins

The first production deploy springs two one-way doors at once: the
content banks freeze and history becomes permanent. Rehearse on a
disposable twin first (ADR-005): the onboarding watch, the WS soak, and
the live-voice probe all run against a world that is thrown away, and
the deploy runbook itself gets exercised end-to-end before the run that
counts. Everything below is the production procedure with a different
app name — `scripts/deploy.sh` honors `FLY_APP`.

```bash
# Stand up the twin (same region; its own volume).
fly apps create enfolded-staging
fly volumes create enfolded_data -a enfolded-staging --region iad --size 1
fly secrets set -a enfolded-staging ANTHROPIC_API_KEY=sk-ant-... # + FAL_KEY / SENTRY_DSN as desired

FLY_APP=enfolded-staging scripts/deploy.sh --first-deploy

# Rehearse against it: mint a key, run the live-voice probe (§8), run
# scripts/ws_soak.py, and watch 2-3 newcomers complete onboarding here —
# never on production. Rehearse a restore (§7) against its volume too.

# Tear it down before launch — the staging chronicle must not linger as
# a second world that looks real.
fly apps destroy enfolded-staging --yes
```

Fix what the rehearsal surfaces, then run §3 against the production app
— deliberately.

---

## 4. Smoke test

```bash
# Should return {"status": "ok"}; /health is exempt from the invite gate.
curl https://enfolded-beta.fly.dev/health

# With a valid invite key, the configured world works and a parallel seed is
# refused before it can be materialized (ADR-007).
curl "https://enfolded-beta.fly.dev/world?depth=2&key=nw_..."
curl -i "https://enfolded-beta.fly.dev/world?seed=43&depth=2&key=nw_..." # 400

# Open the bundled UI in a browser.
open https://enfolded-beta.fly.dev/app

# Tail logs in another terminal.
fly logs
```

Look for:
- `Sentry initialized` on startup (confirms the DSN was picked up).
- One JSON access-log line per request, with `ip_h` (hashed IP) and no
  query string.
- `world heartbeat started` and `causal pump started` (the background
  threads that keep the world alive between requests).
- No `pip install` or migration errors.
- A `403` when you request `/world` **without** a key — proof the invite
  gate is closed. (`/`, `/app`, `/guide`, and `/health` are deliberately
  ungated; data endpoints are not.)

In the first hours with real testers, also watch for
`nested_worlds.client` lines — both browser clients forward their
`window.onerror` crashes to the server log, so a broken deploy surfaces
in `fly logs` instead of only in a tester's DM. (CI's "Browser E2E
smoke" job loads both clients under the production CSP before anything
merges, so this is a second net, not the first.)

**Capacity is measured, not just reasoned:** `scripts/ws_soak.py`
(110 clients against the 96 cap) measured exactly 96 accepted, clean
503 shedding for the excess, ~4,100 broadcast deliveries/s at p99
latency 30 ms, and an 84 MB RSS peak — roughly 12x headroom under the
1 GB allocation. Re-run it against a staging deploy after any change
to the WS layer.

---

## 5. Custom domain (optional)

The app answers at `<app-name>.fly.dev` out of the box. To serve it at
your own domain (e.g. `enfolded.world`):

```bash
# Issue the certificate (Fly provisions and renews Let's Encrypt).
fly certs add enfolded.world

# Then create the DNS records it prints — typically:
#   A    @  ->  <the app's IPv4 from `fly ips list`>
#   AAAA @  ->  <the app's IPv6>
# (or a CNAME to <app-name>.fly.dev for a subdomain).

# Verify issuance:
fly certs show enfolded.world
```

`force_https = true` in `fly.toml` already covers the redirect. Invite
URLs you mint afterwards (§6) can be shared with either hostname.

---

## 6. Mint invite keys

Per-user keys give you revocable, attributable access for each tester, and
they are the whole invite gate — there is no shared key. Every key carries a
unique registered name, so a gated session is always a known, non-anonymous
player (ADR-004 §7). Gate semantics: the gate is OPEN until the first per-user
key below is minted, so everything before this step is publicly reachable —
**mint the first key before you share the URL anywhere.**
`fly ssh console` opens a shell inside the running machine.

Two ways to invite, both single-use per person:

```bash
# (a) Operator-named: you pick the name, hand out a ready-to-play URL.
fly ssh console -C "python main.py invite mint --name Alice --note 'design partner'"

# (b) Self-service: you hand out a registration link; the INVITEE picks
#     their own unique name at /register (told "taken — choose another"
#     if it collides), and redemption mints their play key.
fly ssh console -C "python main.py invite create --note 'for the art channel'"
```

Mint output includes a ready-to-share URL of the form
`https://enfolded-beta.fly.dev/?key=nw_<hex>&name=Alice`; create output
includes `https://<host>/register?invite=nwr_<hex>`. Send one per person —
registration tokens are single-use, so a leaked link mints at most one
account (and an unredeemed leak is revocable, below).

To audit:

```bash
fly ssh console -C "python main.py invite list"
fly ssh console -C "python main.py invite revoke nw_<key>"
fly ssh console -C "python main.py invite tokens --all"
fly ssh console -C "python main.py invite cancel nwr_<token>"
```

---

## 7. Backups

The SQLite store sits on the volume at `/data/.nested-worlds/worlds.db`.
The continuity policy (`docs/roadmap/phase-2-scale.md`) makes this file
the world's permanent chronicle — it is never wiped between cohorts —
so the volume is the only live copy of everything every player and
agent has ever done. Three layers:

**Volume snapshots (automatic).** Fly takes daily snapshots of every
volume by default and retains them for **5 days only**. List with
`fly volumes snapshots list <volume-id>`. Treat these as a convenience,
not the archive.

**Before every deploy (required).** Per the continuity policy, an
online backup is the first step of every deploy, so a bad migration is
a restore, not a lost epoch. `scripts/deploy.sh` encodes this — it
refuses to deploy if the backup fails, and prunes old machine-local
backups. The manual equivalent:

```bash
fly ssh console -C "python main.py backup --to /data/backups/worlds-$(date -u +%Y%m%d).db"
```

**Off-host copies (every 30 minutes; freshness must be checked).** ADR-005 targets
at most one hour of lost history. A schedule alone does not establish that bound:
[GitHub documents delayed and dropped scheduled jobs](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).
The workflow takes an online backup, downloads a self-contained SQLite file,
checks integrity and required tables, and retains it with 90-day retention even
when validation fails. A failed check keeps the run failed and labels the artifact
`unvalidated-worlds-backup-<app>-<UTC snapshot-start>` for operator salvage. These
copies never count as healthy backups. A successful upload is not yet a restore rehearsal.

Before a separately authorized launch, configure the repository:

- Secret `FLY_API_TOKEN`: deployment-scoped access to the intended Fly app.
- Variable `ENFOLDED_BACKUP_APP`: the exact app name (default `enfolded-beta`).
  Use the staging app during rehearsal; switch deliberately before production.
- Variable `ENFOLDED_BACKUP_REQUIRED`: exactly `true` before permanent history is
  accepted. Missing credentials then fail the workflow. Before activation, a
  missing token with the variable unset or exactly `false` produces an explicit
  inactive warning and no recovery claim. Any other value fails configuration;
  a typo cannot silently turn enforcement off.

Manually dispatch `backup.yml`; inspect the artifact, not just the job badge.
Artifacts are named `worlds-backup-<app>-<UTC snapshot-start>`; staging copies
cannot satisfy the production check. Run this read-only check with authenticated
GitHub CLI access (`actions:read`):

```bash
python scripts/backup_health.py --repository mark-weeks/hello-nested-worlds-adventure --app enfolded-beta
```

It queries artifact pages and checks the candidate's originating run. Only a
completed, successful `backup.yml` run on `main`, triggered by the schedule or a
manual dispatch from the same repository, qualifies. Workflow identity, branch,
repository and commit metadata must match; an expected filename alone is not proof.
It exits 0 for a qualifying nonempty, nonexpired artifact whose snapshot-start is
no more than 60 minutes old; 1 for missing/stale; 2 when status cannot be determined.
It does not download data, validate contents, or restore anything. Old artifact names
and quarantined copies are not counted. Metadata follows the
[GitHub artifact API](https://docs.github.com/en/rest/actions/artifacts) and
[workflow-run API](https://docs.github.com/en/rest/actions/workflow-runs).

Run this check independently after workflow completion. A workflow cannot certify
its own successful conclusion while still running, and cannot detect its own
scheduler stopping. The backup job itself fails on invalid configuration,
validation or upload failure. Arrange the independent check and operator notification
before launch; this batch provides the command, not an external monitor.
The `:17` and `:47` schedule leaves 30 minutes of nominal slack within the unchanged
one-hour freshness limit; it does not guarantee timely scheduling. If measured
cadence cannot meet that loss window, fix the transport/cadence or explicitly
revisit ADR-005. Record several subsequent artifacts before calling automation proven.

Download the selected artifact through GitHub, retain its run ID, snapshot time,
app, release SHA and file checksum, and rehearse the restore below on an isolated
instance. Treat downloaded data as private operator data, never a public fixture.

### Restoring from a backup

For M1 queue upgrades, pending-work inspection, and the prohibition on mixed
old/new workers, also follow [delayed-work recovery](delivery-recovery.md).

The policy's promise is "a bad migration is a restore, not a lost
epoch" — this is the restore. It overwrites the live database with the
backup; everything recorded since that backup is lost, so read the
event counts it prints.

```bash
# 1. Stop all application/heartbeat writers while retaining maintenance access.
#    Restore uses SQLite backup in reverse; --yes skips the confirmation prompt.
fly ssh console -C "python main.py restore --from /data/backups/worlds-YYYYMMDD.db --yes"

# 2. Restart so in-memory state (rooms, puzzle sessions, rate buckets)
#    matches the restored world.
fly machine restart <machine-id>
```

If the backup only exists off-host, upload it first:
`fly ssh sftp shell` then `put ./local-backups/worlds-YYYYMMDD.db /data/backups/`.
Earlier local rehearsals covered backup → mutate → restore. They do not prove
that this deployment's off-host artifact can be recovered. On isolated staging,
verify born rows/hinge and historical deltas, rotated identities and private-note
access, pinned puzzles, saved positions, pending inputs and completed fences.
Start a compatible build, confirm pending effects complete once, retry the original
request IDs, and check that no other account can read private notes. Record the
artifact checksum and elapsed recovery time. Never rehearse by rolling back the
continuing participant world.

### Redaction — the sanctioned exception to append-only

The chronicle is permanent, but permanence needs an escape hatch for
abuse (a slur cut into a room, doxxing in chat, a poisoned puzzle
guess). Policy: redaction is **content-level, never row-level** — the
event, its node, its type, its timestamp, and its durable
`actor_identity` all survive; only the human-authored words are
tombstoned to `[redacted]`. Mechanical fields (puzzle names, correct
flags, verbs) are preserved, so co-op counters and renewal epochs are
untouched. Deleting whole rows is NOT an option; if you think you need
that, you actually need `restore` (§7) plus a conversation.

```bash
# 1. Find the offending rows (read-only substring search).
fly ssh console -C "python main.py redact --find 'the offending text'"

# 2. Tombstone by id. --scrub-name also nulls the display name (for
#    names that are themselves the abuse); actor_identity is kept so
#    accountability survives the cleanup. --reason stores a short note.
fly ssh console -C "python main.py redact --id 12345 --scrub-name --reason 'ToS' --yes"
```

No restart is needed — history is read per request. If the abusive text
also fed a cached node image, delete that node's `node_images` row (the
image regenerates on next request). Off-host backups made before the
redaction still contain the original text; their 90-day artifact expiry
is the retention bound.

---

## 8. Launch window

This checklist is the launch-day distillation of the pre-mortem hardening
batch (see the "Pre-mortem hardening" entry in `docs/CHANGELOG.md`, PR #57)
and the launch-readiness findings in
`docs/evaluation/2026-07-04-deep-evaluation.md`. Work through it top to
bottom on the day.

**Current experience rehearsal (2026-10-03):** Record the selected commit,
bundled client, database schema, target app, canonical seed, client default,
browser/device list, operator, and time in the readiness record. Local fixtures,
hosted staging, and participant evidence are separate entries.

Before any upgrade, stop all writers and verify a complete backup. On disposable
staging, exercise invite gating/rotation, private notes, pinned puzzles, saved
position, direct Act submission, independently overlapping delayed v3 attempts,
lost acknowledgements and retries, reconnect, process death with pending work,
and recovery from the downloaded backup. Use a compatible application build;
older binaries must not interpret newer accepted work. Retain legacy v1/v2
receipts and pending outcomes without opening new scripted choices.

Do not run `python main.py situation` as onboarding. The scripted controller is
retired; follow the [current pilot protocol](../evaluation/2026-09-12-pilot-protocol.md)
for exploration and return. A production restore discards intervening history
and remains an exceptional disaster operation, not an ordinary release rollback.

**T-1 week:**

- [ ] Backup target and token configured; `ENFOLDED_BACKUP_REQUIRED=true`.
      Manual dispatch and subsequent scheduled runs produce fresh app-specific artifacts.
- [ ] Isolated restore rehearsed from a downloaded artifact of the intended app;
      before first production, use its staging twin, then verify production backup
      immediately after first deploy and before inviting participants.
- [ ] Independent artifact-freshness monitoring and failure notification exercised.
      A green no-op and an uptime ping cannot satisfy this gate.
- [ ] `SENTRY_DSN` set; `fly logs` shows `Sentry initialized` on boot.
- [ ] External uptime ping pointed at `/guide` (ungated, exercises the
      full serving path). Any free checker works.
- [ ] Size the day-one budgets deliberately: launch day is the highest-
      traffic day the app will ever see. Estimate
      `cohort size x expected exchanges x cost per exchange` and set
      `NESTED_WORLDS_ANTHROPIC_DAILY_CALLS` (and `_FAL_DAILY_CALLS`)
      with headroom above it — the `_PER_USER` caps already bound any
      single account; the global cap is the one that can mute the whole
      cohort at the worst moment.
- [ ] Watch 2-3 people who have never seen the app complete onboarding
      (screen share is fine) — **on the staging rehearsal app (§3a),
      never on production**: their first fumbling sessions must not
      become permanent world history. Fix what confuses them, tear the
      staging app down, then deploy production.

**Launch day:**

- [ ] **Deploy freeze** — one machine means every deploy drops all live
      sessions. Nothing ships during the window short of a fire.
- [ ] **Live-model probes** — verify both node conversation and intention
      interpretation on disposable staging, including clarification/refusal and
      an observed explicit-action equivalent. Keep credentials and private text out
      of evidence. Optional audio is separate. Quiet degradation hides outages by design,
      so verify the voice is LIVE, not just answering: a `/speak` reply
      must carry `"ai": true`. `"ai": false` means the failure voice is
      covering for a missing key or an exhausted budget (the probe spends
      one budgeted call — that's the point):
      `curl -s -X POST https://<app>/speak -H 'X-Beta-Key: <key>' -H 'Content-Type: application/json' -d '{"message":"hello"}' | grep -o '"ai": true'`
- [ ] Watch spend as the cohort arrives: the `cost_budget` table carries
      per-day counters — `fly ssh console -C "sqlite3 /data/.nested-worlds/worlds.db 'SELECT * FROM cost_budget ORDER BY day DESC LIMIT 20'"`.
- [ ] Mint **one key per person** (`python main.py invite mint --name ...`).
      This is the only way in — there is no shared key (it was removed
      because one credential merges transcript identities, budget buckets,
      and attribution, and lets players collapse to one identity or play
      anonymously). Each key's name is unique; a name already taken is
      rejected at mint. Say so in the invite message.
- [ ] Onboard the cohort in the same window, not a trickle — encounters,
      co-op puzzles, and live cascades only exist when people overlap.
      Keep the initial curiosity observation unprompted. After recording it, an
      optional exploration prompt may help; record assistance and reminders under
      protocol 2. Do not force a scripted route or another traveler's action.

**T+1 day and weekly:**

- [ ] Read the world's own numbers — visitors, RETURNING visitors,
      conversations, solves — straight from the chronicle:
      `python scripts/beta_metrics.py --days 1` (works on the machine or
      against any off-host backup with `--db`). The return rate is the
      success metric for a contemplative world; decide response
      thresholds before you look.

---

## 9. Day-2 operations

| Task | Command |
|---|---|
| Tail logs | `fly logs` |
| Open a shell in the running machine | `fly ssh console` |
| Redeploy after a code change | `git push` (CI runs), then `scripts/deploy.sh` (backs up first, per §7) |
| See current machine status | `fly status` |
| Restart the machine | `fly machine restart <id>` |
| Inspect the volume | `fly volumes list` |
| Restore from a backup | `python main.py restore --from <file>` then restart (§7) |
| Adjust a runtime cap | `fly secrets set NESTED_WORLDS_ANTHROPIC_DAILY_CALLS=1000` |
| Kill switch AI without redeploy | `fly secrets set NESTED_WORLDS_DISABLE_AI=1` |
| Slow/speed causal ripple travel | `fly secrets set NESTED_WORLDS_HOP_DELAY=30` |
| Pause staged-cascade drain (hops queue durably) | `fly secrets set NESTED_WORLDS_CAUSAL_PUMP=0` |

A `fly secrets set` triggers an automatic rolling redeploy. The single
machine means there is roughly 10-30 seconds of downtime per change, and
**every deploy drops live WebSocket sessions** (browsers auto-reconnect) —
acceptable for a beta. In-flight causal cascades are safe to deploy over:
staged hops live in the durable `causal_queue` table, so a ripple pauses
during the rollover and resumes when the pump thread comes back up. On
SIGTERM the server drains, stops accepting new connections, and
checkpoints the SQLite WAL back into the main file, so a redeploy never
leaves a large `-wal` sidecar to replay on next boot. The `cost_budget`
and `invite_keys` tables live on the volume, so they survive restarts
and redeploys.

---

## 10. When to graduate

The phase-2 scale plan in `docs/roadmap/phase-2-scale.md` names the
triggers for moving past this single-VM setup. The relevant ones for
Fly:

- **Anthropic RPM headroom shrinks** → raise
  `NESTED_WORLDS_ANTHROPIC_DAILY_CALLS` and
  `NESTED_WORLDS_ANTHROPIC_CONCURRENCY`; no infra change needed.
- **`/image` requests dominate egress** → put Cloudflare in front and
  cache `/image` responses; the URL stays the same.
- **SQLite write contention shows up in latency p99** → execute ADR-003
  (Postgres switchover). Fly + Neon Postgres is a one-day migration;
  the volume drops away.
- **You need a second region** → scale to two machines, but only after
  the rooms registry and rate limiter move to Redis (also in the
  roadmap). Until then, stay single-region.

---

## Cost expectation

A `shared-cpu-1x` / 1 GB machine plus a 1 GB volume runs roughly
$2-5/month at the 20-user beta scale. Anthropic and fal.ai usage are
separate and bounded by the daily call caps you set in env.
