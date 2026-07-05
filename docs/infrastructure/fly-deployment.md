# Deploying to Fly.io

This guide walks through standing up Enfolded on Fly.io for
the initial beta. It assumes you have shell access to a clone of this
repository and an Anthropic key in hand.

End state: one VM in one region, SQLite on a persistent volume, the
React frontend baked into the image, Sentry wired in, and per-user
invite keys distributed to your testers.

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

```toml
app = "enfolded-beta"          # change to your unique app name
primary_region = "iad"              # pick the region closest to your testers

[build]
  dockerfile = "Dockerfile"

[env]
  HOME = "/data"
  NESTED_WORLDS_TRUST_PROXY = "1"
  SENTRY_ENVIRONMENT = "beta"

[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = false        # keep the in-memory rate limiter / rooms alive
  min_machines_running = 1
  processes = ["app"]

  [http_service.concurrency]
    type = "connections"            # WS sessions are long-lived connections
    soft_limit = 180
    hard_limit = 200

  [http_service.checks.health]
    type = "http"
    method = "GET"
    path = "/health"
    interval = "30s"
    timeout = "5s"
    grace_period = "10s"

[mounts]
  source = "enfolded_data"
  destination = "/data"

[[vm]]
  size = "shared-cpu-1x"
  memory = "512mb"
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

# REQUIRED for any public deployment: close the invite gate. The gate
# stays OPEN until either this shared key is set or the first per-user
# key is minted (§6) — an ungated server is an open proxy to your
# Anthropic budget (the daily caps bound the damage; they don't prevent
# strangers spending it). Set this now so the app is born gated.
fly secrets set NESTED_WORLDS_BETA_KEY=$(openssl rand -hex 16)

# Deploy. (--first-deploy skips the pre-deploy backup — nothing to back
# up yet. Every subsequent deploy goes through scripts/deploy.sh plain.)
scripts/deploy.sh --first-deploy
```

`fly deploy` builds the Docker image remotely, ships it to the region,
attaches the volume, and rolls the machine over to the new image. First
deploy takes ~3-5 minutes.

---

## 4. Smoke test

```bash
# Should return {"status": "ok"}; /health is exempt from the invite gate.
curl https://enfolded-beta.fly.dev/health

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

**Before inviting testers (recommended):** the WS capacity numbers
(`NESTED_WORLDS_MAX_WS_CONNECTIONS=96` against 1 GB) are reasoned, not
measured. A twenty-minute soak — a script opening ~100 concurrent
WebSocket sessions against the deployment while you watch `fly status`
memory — turns them into facts before your testers do it for you.

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

Per-user keys give you revocable, attributable access for each tester.
Note the gate semantics: the invite gate closes as soon as **either**
`NESTED_WORLDS_BETA_KEY` is set (§3) **or** the first per-user key below
is minted — if you skipped the shared key, everything before this step
is publicly reachable, so mint before you share the URL anywhere.
`fly ssh console` opens a shell inside the running machine.

```bash
fly ssh console -C "python main.py invite mint --name Alice --note 'design partner'"
```

The output includes a ready-to-share URL of the form
`https://enfolded-beta.fly.dev/app?key=nw_<hex>&name=Alice`.
Send one to each tester.

To audit:

```bash
fly ssh console -C "python main.py invite list"
fly ssh console -C "python main.py invite revoke nw_<key>"
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

**Off-host copies (recommended weekly).** Stream a backup off the
machine, then prune what's already copied — the backups directory
shares the 1 GB volume with the live DB and grows by one file per
deploy:

```bash
fly ssh sftp get /data/backups/worlds-YYYYMMDD.db ./local-backups/
fly ssh console -C "sh -c 'ls -t /data/backups/*.db | tail -n +6 | xargs -r rm'"
```

The automated cadence ships in the repo:
`.github/workflows/backup.yml` runs every Monday (or on demand via
workflow_dispatch), takes an online backup on the machine, downloads it,
and stores it as a GitHub artifact with 90-day retention. It activates
the moment you add a `FLY_API_TOKEN` repository secret
(`fly tokens create deploy`); until then it no-ops with a notice.

### Restoring from a backup

The policy's promise is "a bad migration is a restore, not a lost
epoch" — this is the restore. It overwrites the live database with the
backup; everything recorded since that backup is lost, so read the
event counts it prints.

```bash
# 1. Restore (uses the sqlite backup API in reverse — safe against the
#    running server's per-operation connections; --yes skips the prompt).
fly ssh console -C "python main.py restore --from /data/backups/worlds-YYYYMMDD.db --yes"

# 2. Restart so in-memory state (rooms, puzzle sessions, rate buckets)
#    matches the restored world.
fly machine restart <machine-id>
```

If the backup only exists off-host, upload it first:
`fly ssh sftp shell` then `put ./local-backups/worlds-YYYYMMDD.db /data/backups/`.
This procedure was rehearsed against a live server in the
pre-deployment review (backup → mutate → restore → verified rollback).

---

## 8. Day-2 operations

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

## 9. When to graduate

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

A `shared-cpu-1x` / 512 MB machine plus a 1 GB volume runs roughly
$2-5/month at the 20-user beta scale. Anthropic and fal.ai usage are
separate and bounded by the daily call caps you set in env.
