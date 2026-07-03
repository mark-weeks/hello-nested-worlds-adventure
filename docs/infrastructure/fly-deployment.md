# Deploying to Fly.io

This guide walks through standing up Nested Worlds Adventure on Fly.io for
the initial beta. It assumes you have shell access to a clone of this
repository and an Anthropic + fal.ai key in hand.

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
- A fal.ai API key (`FAL_KEY`).
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
app = "nested-worlds-beta"          # change to your unique app name
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
  source = "nested_worlds_data"
  destination = "/data"

[[vm]]
  size = "shared-cpu-1x"
  memory = "512mb"
```

---

## 3. First deploy

Run these from the repo root.

```bash
# Create the app (no deploy yet). Skip if `fly.toml`'s app name is already taken.
fly apps create nested-worlds-beta

# Provision the persistent volume in the same region as the app.
fly volumes create nested_worlds_data --region iad --size 1

# Set runtime secrets. These never appear in logs or the image.
fly secrets set \
  ANTHROPIC_API_KEY=sk-ant-... \
  FAL_KEY=... \
  SENTRY_DSN=https://...ingest.sentry.io/...

# Optional: shared ops invite key (per-user keys still work alongside it).
fly secrets set NESTED_WORLDS_BETA_KEY=$(openssl rand -hex 16)

# Deploy.
fly deploy
```

`fly deploy` builds the Docker image remotely, ships it to the region,
attaches the volume, and rolls the machine over to the new image. First
deploy takes ~3-5 minutes.

---

## 4. Smoke test

```bash
# Should return {"status": "ok"}; /health is exempt from the invite gate.
curl https://nested-worlds-beta.fly.dev/health

# Open the bundled UI in a browser.
open https://nested-worlds-beta.fly.dev/app

# Tail logs in another terminal.
fly logs
```

Look for:
- `Sentry initialized` on startup (confirms the DSN was picked up).
- One JSON access-log line per request, with `ip_h` (hashed IP) and no
  query string.
- No `pip install` or migration errors.

---

## 5. Mint invite keys

Per-user keys give you revocable, attributable access for each tester.
`fly ssh console` opens a shell inside the running machine.

```bash
fly ssh console -C "python main.py invite mint --name Alice --note 'design partner'"
```

The output includes a ready-to-share URL of the form
`https://nested-worlds-beta.fly.dev/app?key=nw_<hex>&name=Alice`.
Send one to each tester.

To audit:

```bash
fly ssh console -C "python main.py invite list"
fly ssh console -C "python main.py invite revoke nw_<key>"
```

---

## 6. Backups

The SQLite store sits on the volume at `/data/.nested-worlds/worlds.db`.
Two layers:

**Volume snapshots (automatic).** Fly takes daily snapshots of every
volume by default and retains them for 5 days. List with
`fly volumes snapshots list <volume-id>`.

**Application-level backups (recommended weekly).** Run the online
backup CLI and stream the result off-host:

```bash
fly ssh console -C "python main.py backup --to /data/backups/worlds-$(date -u +%Y%m%d).db"
fly ssh sftp get /data/backups/worlds-YYYYMMDD.db ./local-backups/
```

For an automated cadence, add a tiny cron job on your laptop or a CI
schedule that runs the two commands above.

---

## 7. Day-2 operations

| Task | Command |
|---|---|
| Tail logs | `fly logs` |
| Open a shell in the running machine | `fly ssh console` |
| Redeploy after a code change | `git push` (CI runs) then `fly deploy` |
| See current machine status | `fly status` |
| Restart the machine | `fly machine restart <id>` |
| Inspect the volume | `fly volumes list` |
| Adjust a runtime cap | `fly secrets set NESTED_WORLDS_ANTHROPIC_DAILY_CALLS=1000` |
| Kill switch AI without redeploy | `fly secrets set NESTED_WORLDS_DISABLE_AI=1` |

A `fly secrets set` triggers an automatic rolling redeploy. The single
machine means there is roughly 10-30 seconds of downtime per change, and
**every deploy drops live WebSocket sessions** (browsers auto-reconnect) —
acceptable for a beta. On SIGTERM the server drains, stops accepting new
connections, and checkpoints the SQLite WAL back into the main file, so a
redeploy never leaves a large `-wal` sidecar to replay on next boot. The
`cost_budget` and `invite_keys` tables live on the volume, so they survive
restarts and redeploys.

---

## 8. When to graduate

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
