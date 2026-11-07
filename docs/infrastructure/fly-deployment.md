# Deploying to Fly.io

This guide walks through standing up Enfolded on Fly.io for
the initial beta. It assumes you have shell access to a clone of this
repository and a key for the configured provider (currently Anthropic) in hand.

End state: one VM in one region, one shared canonical world, SQLite on a
persistent volume, the React frontend baked into the image, Sentry wired in,
and per-user invite keys distributed to your testers.

Same-schema rollback is [below](#same-schema-release-rollback). Incidents
(kill switches, redaction, who decides) are the
[incident response playbook](incident-response.md).

---

## 1. Prerequisites

- A [Fly.io account](https://fly.io) with billing set up (the beta fits
  in the free tier, but card-on-file is required).
- The `flyctl` CLI installed locally:
  ```bash
  curl -L https://fly.io/install.sh | sh
  fly auth login
  ```
- A key for the configured provider (currently Anthropic): `ANTHROPIC_API_KEY`.
  The owner's provider data rule (§3a, "Provider data rule") applies to the
  account that holds it: no training or data-sharing opt-in.
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
RUN pip install -e ".[anthropic]" || true

# Copy the rest of the source.
COPY . .

# Overlay the freshly built frontend bundle.
COPY --from=frontend /build/static ./static

# Reinstall now that the package source is present so the editable
# install picks up the modules.
RUN pip install -e ".[anthropic]"

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
`NESTED_WORLDS_MAX_WS_PER_IP`. Plain HTTP has three further bounds, each
read at request time. `NESTED_WORLDS_HTTP_READ_TIMEOUT` (default 30
seconds) is the deadline for the request line, headers, and body.
`NESTED_WORLDS_HTTP_WRITE_TIMEOUT` (default 30 seconds) is separate: it
bounds one blocked response send, not the whole body, so a client that
keeps accepting bytes — a slow download of a scene image or a world tree —
is not cut off for taking longer than 30 seconds overall. A client that
stops reading is dropped after 30 seconds and the handler slot is freed.
Thirty seconds matches the read budget: long enough for congestion or a
brief pause, short enough that a silent reader cannot pin a thread until
restart. A finished WebSocket upgrade lifts both timers and the session
keeps the existing 60-second idle timer. `NESTED_WORLDS_MAX_HANDLER_THREADS` (default 160) caps threads
inside requests, including open WebSockets. Past that, a new connection
gets `503` with `Retry-After: 2` and `{"error":"server busy"}` instead of
waiting. 160 is above the WebSocket default (128, or 96 in the committed
`fly.toml`) and above the proxy `hard_limit` of 150, so those still shed
first. A saturated cap also answers `/health` with 503. That is deliberate:
the refusal is sent before the request is read, so exempting `/health`
would mean reading on the accept path, and a process that is refusing
every player should fail its health check. The write timeout is what
keeps a client that stopped reading from making that 503 last. A client that
takes longer than the read budget to send — a stalled link, or a very
slow upload of the 64 KB maximum body — is closed; a body that stalls
after the headers returns `408`.

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
# until the first per-user key or registration invite is issued (§6);
# from then on it stays closed, even if every key is later revoked. An ungated server is an open
# proxy to the configured provider's budget (currently Anthropic). The daily
# caps bound the damage; they don't prevent strangers spending it. Mint the
# first per-user key in §6 BEFORE you announce the URL, and do not share the
# URL until then.

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

**Staging is declared disposable** (ADR-004, 2026-10-25 amendment). Its
world, chronicle and invite keys are rehearsal data, never production canon.
They are destroyed with the app before launch. Tell every tester that its
history is temporary (pilot protocol 2).

**Venue for the newcomer watch (owner, 2026-11-07):** "Let's expedite the
test build, preferably in a staging environment rather than local." The
owner prefers this staging twin for the 2-3 newcomer watch. The local,
declared-disposable world in the
[facilitator kit](../evaluation/2026-11-02-newcomer-watch-kit.md) stays a
fallback only.

#### One-time setup (owner)

Run these from the repo root, in this order. The provider key goes in after
the first invite key exists. The invite gate stays open until the first key
is minted (§6), and the voice cannot spend in that window if the key is not
yet set. Without it, places and inhabitants answer the authored quiet line
(`"ai": false`). Name screening at mint is local and needs no provider
(`server/moderation.py`, `name_refusal`).

```bash
# 1. A Fly account with billing (card on file), flyctl installed, and
#    `fly auth login` (§1).

# 2. The twin: same region, its own volume. The volume name must be
#    enfolded_data because the committed fly.toml mounts that name.
fly apps create enfolded-staging
fly volumes create enfolded_data -a enfolded-staging --region iad --size 1

# 3. A deploy token for the staging app only. In GitHub, store it as the
#    repository Actions secret FLY_API_TOKEN_STAGING (Settings > Secrets and
#    variables > Actions). Paste it exactly as printed. Never use an
#    organization token for the organization that holds production, and
#    never a personal token (fly auth token): either can reach production.
fly tokens create deploy -a enfolded-staging

# 4. First deploy: Actions > "Deploy staging" > Run workflow, ref main,
#    first_deploy checked. From a terminal instead:
#      gh workflow run deploy-staging.yml -f ref=main -f first_deploy=true
#    or, without GitHub:
#      FLY_APP=enfolded-staging scripts/deploy.sh --first-deploy

# 5. Close the gate at once: mint one key per tester (2-3). Each output line
#    "Share the URL: <BASE>/app?key=..." becomes
#    https://enfolded-staging.fly.dev/app?key=... . Send each URL to its
#    tester only, never in an issue, a PR, a chat channel or a CI log.
fly ssh console -a enfolded-staging -C "python main.py invite mint --name <Name> --note 'disposable staging watch'"

# 6. Now the provider key. FAL_KEY and SENTRY_DSN are optional. Setting
#    secrets restarts the machine.
fly secrets set -a enfolded-staging \
  ANTHROPIC_API_KEY=sk-ant-... \
  FAL_KEY=... \
  SENTRY_DSN=https://...ingest.sentry.io/... \
  SENTRY_ENVIRONMENT=staging

# 7. Check it: /health ok, the gate closed, the voice live (§8 probe).
curl https://enfolded-staging.fly.dev/health
curl -i https://enfolded-staging.fly.dev/world        # 403 without a key
fly ssh console -a enfolded-staging -C "printenv SENTRY_ENVIRONMENT"
```

**Sentry environment.** The committed `fly.toml` sets
`SENTRY_ENVIRONMENT = "beta"` in `[env]`, and `scripts/deploy.sh` passes no
extra arguments to `fly deploy`, so neither the workflow nor the script can
change it without editing production config. Step 6 sets
`SENTRY_ENVIRONMENT=staging` as a staging secret instead. Whether a Fly
secret overrides an `[env]` value of the same name was not verified from the
session that wrote this. Step 7's `printenv` settles it. If it prints
`beta`, give staging its own Sentry project's DSN so its events never mix
with production's, or leave `SENTRY_DSN` unset on staging.

#### Redeploying staging after a merge

`.github/workflows/deploy-staging.yml` redeploys the twin from GitHub
Actions, so an agent or the owner can do it without the owner's machine. It
runs only on manual dispatch (`gh workflow run deploy-staging.yml -f ref=main`),
one run at a time, and GitHub offers it for dispatch once the file is on
`main`. It cannot be pointed at another app:

- The app name `enfolded-staging` is written into the workflow. It is not an
  input or a repository variable. The first step refuses any other value,
  and the deploy step names the app again when it calls `scripts/deploy.sh`.
- Its only secret is `FLY_API_TOKEN_STAGING`. It never reads
  `FLY_API_TOKEN`, the token `backup.yml` uses.
- It runs `scripts/deploy.sh` from the checked-out ref: backup first, schema
  check, prune, then `fly deploy`. With `first_deploy` it passes
  `--first-deploy`. It then polls `https://enfolded-staging.fly.dev/health`
  for `{"status": "ok"}`: 30 attempts, 10 s apart, 10 s each, about 10
  minutes at most.
- It mints no invite keys and runs no `fly ssh console` command of its own.
  A key printed in a job log is a leaked credential, so step 5 stays a
  terminal step.

The guards in the file catch a mistake in the file. They cannot stop a ref
whose own `scripts/deploy.sh` ignores `FLY_APP`. The token's scope is what
stops that, so step 3's token must be scoped to `enfolded-staging` alone.
`tests/test_deploy_staging_workflow.py` checks the guards and runs the
workflow's step scripts against a stub `fly`.

**Not verified from the session that wrote this** (it could not reach
fly.io):

- That a deploy token from `fly tokens create deploy -a enfolded-staging` is
  refused by every other app. The production guard above rests on it.
- That such a token permits `fly ssh console`. `scripts/deploy.sh` uses it
  for the backup, the schema probe and the prune on every deploy except
  `--first-deploy`. `backup.yml` already assumes the same for its own token.
  If it does not, the backup step fails and `deploy.sh` refuses to deploy,
  so nothing changes on Fly. The fallback is to redeploy from the owner's
  machine (`FLY_APP=enfolded-staging scripts/deploy.sh`). Another is to move
  staging into a Fly organization of its own and store a token for that
  organization only. A token that can reach the production organization is
  never a fallback.
- That `fly deploy -a enfolded-staging` targets staging although the
  committed `fly.toml` says `app = "enfolded-beta"`. The procedure above has
  always assumed it.
- That a deploy token can build on Fly's remote builder from a GitHub runner
  (`scripts/deploy.sh` passes neither `--remote-only` nor `--local-only`).
- That the pinned `setup-flyctl` action puts `flyctl` on the path. The
  workflow sets `FLY_BIN=flyctl`, as `backup.yml` calls `flyctl`.
- That a Fly secret overrides an `[env]` value (Sentry environment, above),
  and that `fly secrets set` restarts the running machine.

#### Provider data rule

**Owner, 2026-11-07 (packet decision 10 / S2, with L4):** "Information can
only be shared with model providers to facilitate game play. Enfolded data
must not be used to train frontier models." This binds staging and
production alike.

- Do not opt the provider account or organization that holds
  `ANTHROPIC_API_KEY` into any training or data-sharing programme, a
  development partner programme included. Do not submit feedback that
  contains player content.
- Anthropic's help centre, as a web search returned it on 2026-11-07, says
  customer content sent through the API under its commercial terms is not
  used to train its models by default. The exceptions are a customer who
  opts in, for example to a development partner programme, and feedback a
  customer submits. The page itself could not be opened from the session
  that wrote this. Read it before the first outside tester's text reaches
  the voice.
- Check any other destination against this rule before it receives player
  text. That includes an `openai_compatible` base URL (ADR-035, Proposed)
  and any second provider.
- Image prompts copy no player messages. `server/imageprompt.py` counts
  distinct speakers and quotes none of them.

This records the rule for operators. It does not build S2's allowlist in
config or write L4's data-use note for each provider.

#### Teardown before launch

The staging chronicle must not linger as a second world that looks real.

```bash
# Rehearse against it first: the live-voice probe (§8), scripts/ws_soak.py,
# the newcomer watch, and a restore (§7) against its volume. Never on
# production.
fly apps destroy enfolded-staging --yes
```

Then delete the `FLY_API_TOKEN_STAGING` repository secret. Without it the
workflow stops at its token step and deploys nothing.

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
key or registration invite below is issued, so everything before this step is
publicly reachable — **mint the first key before you share the URL anywhere.**
The gate then latches: revoking every key does not reopen it. Revoking a key
also ends that player's open WebSocket. A move or chat its rate limit admits
closes it at once (status 1008), and any other frame, keepalives included,
closes it once 2 s have passed since its last check. The server does not
wait for frames: it re-checks every open socket whose last check is 5 s old,
whether or not the client sends anything. A socket that only listens, or
holds a frame open, therefore stops receiving room broadcasts within about
5 s of revocation: one 5 s sweep interval plus one database read. Its close
(status 1008) and its departure from the room follow within about 1 s more,
even if the client has stopped reading: the server waits at most 1 s to
write a close frame, then shuts the socket down without one. One exception
remains: a chat being screened by the model provider. Nothing reaches that
client meanwhile and the chat is refused afterwards, but its close and
departure wait for the screening: at most 3 s for a slot under the
provider's concurrency limit (the classify's own timeout), then one classify
attempt with no retries under that same 3 s (the slot wait does not count
against it).
An error reply, a 429 with retry-after included, ends the screening at once
and holds the chat; a provider that never answers ends it after about 3 s
(3.07 s measured against a local stub). The 3 s applies to each network
phase (connect, send, each read), not to the whole reply, so a provider that
trickles its reply can take longer: a stub that sent its body a chunk a
second took 6.0 s. A frame must still finish arriving within 10 s of its first byte or
the socket is closed (status 1002). Any keyless
socket opened before the first key or invite closes the same way.
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
`https://enfolded-beta.fly.dev/app?key=nw_<hex>&name=Alice`; create output
includes `https://<host>/register?invite=nwr_<hex>`. Send one per person —
registration tokens are single-use, so a leaked link mints at most one
account (and an unredeemed leak is revocable, below).
Registration also enters `/app`, the owner-approved pilot default recorded
in ADR-005's 2026-11-04 revision. Journal and return links use that client;
the World map remains available at `/`. This choice does not complete the
cohort device checks or authorize deployment.

To audit:

```bash
fly ssh console -C "python main.py invite list"
fly ssh console -C "python main.py invite revoke nw_<key>"
fly ssh console -C "python main.py invite tokens --all"
fly ssh console -C "python main.py invite cancel nwr_<token>"
```

### Suspending or banning a player

Suspend or ban when a player should lose access but could come back.
Revoke when access ends for good.

| Action | Command | Ends | Name and key |
|---|---|---|---|
| Suspend | `sanction suspend <name> --hours N` or `--days N` (1 hour to 365 days, whole hours or days) | At its expiry, or `sanction lift` | Kept. The same key works again afterwards. |
| Ban | `sanction ban <name>` | Only by `sanction lift` | Kept. The same key works again once lifted. |
| Revoke | `invite revoke <key>` | Never. There is no un-revoke. | Burned. Minting refuses the name, and a fresh invite creates a new participant with an empty journal and profile. |

```bash
# A reason is required for every suspend, ban and lift.
fly ssh console -C "python main.py sanction suspend Alice --hours 24 --reason 'spam in chat, second warning'"
fly ssh console -C "python main.py sanction ban Alice --reason 'threats to another player'"

# Or keep the reason off every command line: open a shell on the machine,
# pass --reason -, type the reason, then press Enter and Ctrl-D.
fly ssh console
cd /app && python main.py sanction ban Alice --reason -

# Active sanctions, with their ids and reasons. --all adds lifted and expired ones.
fly ssh console -C "python main.py sanction list"
fly ssh console -C "python main.py sanction list --all"

# End one early, by id from the list.
fly ssh console -C "python main.py sanction lift 3 --reason 'appeal accepted'"
```

`<name>` is the registered name in any case or Unicode form, compared as
registration compares names (`persistence.name_key`: trimmed, then
Unicode's compatibility caseless match, which is NFD, case fold, NFKD, case
fold again, then every invisible default-ignorable character removed (a
zero-width space, a soft hyphen, a variation selector), recomposed as NFKC,
and trimmed again), or the participant id. A database written before that
comparison can hold two names with one key (`Élodie` and `élodie`, or `Ada`
and `Ada` followed by a zero-width space); `python main.py invite duplicates`
lists them (§7). Such a name is refused as ambiguous, listing each spelling
and its participant id where one exists, and nothing is recorded: name the
participant id instead. The sanction attaches to the participant, not to the key,
so rotating the key does not escape it. No restart is needed. The player's
next HTTP request is refused. An open WebSocket closes the same way as a
revoked key's (see the invite-gate paragraph above): at once on a move or chat
its rate limit admits. Otherwise it stops receiving the world within about
5 s, including a client that sends nothing or trickles a frame, and is closed
and leaves the room within about 1 s more, except while a chat is being
screened by the model provider (the exception above).
When the suspension expires or the sanction is lifted,
the same key resolves to the same participant again. Journal, profile, home
and saved position are untouched throughout.

What the player sees: the same `403 {"error": "forbidden"}` as a revoked key
(Ideas, which authenticates on its own, answers its usual 403 "Open your
current personal game invite to participate in Ideas."). No reason, kind or
end time is shown. Telling the player what was decided and why, and any
appeal, is checklist G8, a held owner decision. Neither client yet tells the
player their invite stopped working.

What other players see: the player leaves the room as from any other
departure. While the sanction lasts, their published profile reads as
unavailable at `/profile` (`400 {"error": "That profile is unavailable."}`),
exactly as a revoked player's does. It is visible again once the sanction is
lifted or expires. The owner's 2026-11-03 direction settled this (ADR-004,
sanction-records amendment).

What is recorded: one `sanctions` row per suspension or ban and one
`sanction_lifts` row per lift (migration 0029). No application command
edits or deletes them, so `sanction list --all` is the complete history.
Nothing is written to the chronicle. The disconnect writes the same
`PLAYER_LEAVE` row as any other departure, and nothing marks it as a
sanction. Overlapping sanctions each have to end: lifting a ban leaves an
active suspension in force. The application's logs carry the sanction id
and kind only, never the reason, the name or a credential.

A reason is one line with at least one visible character: tabs, newlines,
other control characters, and a reason made only of spaces or zero-width
characters are refused. `sanction list` and the other `sanction` output
print any non-printable character in a name or reason as an escape such as
`\x1b`, so a stored control sequence never reaches your terminal.

**A reason on the command line is recorded outside the database.**
`fly ssh console -C "... --reason '...'"` is a command line on your machine,
so the reason goes into your local shell history, and while the command runs
it is in the process arguments of `flyctl` on your machine and of `python`
on the app machine. `--reason -` on `suspend`, `ban` and `lift` reads the
reason from standard input instead; one trailing newline is dropped. Run it
from an interactive `fly ssh console` shell, as above, so the reason is
typed into the program and not into any shell. If you do type a reason on
the command line, keep it out of your history: in bash, set
`HISTCONTROL=ignorespace` (or `ignoreboth`) and start the command with a
space (zsh: `setopt HIST_IGNORE_SPACE`). Otherwise delete the entry
afterwards (bash: `history -d <number>`) and check that your history file,
such as `~/.bash_history`, no longer holds it.

**Sanction reasons are private operator data, and they enter every
backup.** They are never shown to players, but they sit in the live database
and therefore in every machine-local `/data/backups/*.db` copy, every
off-host object, and any downloaded `./worlds-backup.db` (§7). Unlike
chronicle text, `redact` does not reach them. Write reasons you would be
content to see restored from a backup. Keep them short and factual, with no
contact details and no other player's private data. The player-facing
privacy notice (checklist L3) must name this record: that sanction decisions
and their reasons are kept, privately, for as long as backups are. The
backup retention period is not decided yet (decision I in the
[Q4 plan](../roadmap/next-steps-2026-q4.md)).

**Erasing a sanction reason (break-glass).** No application command edits
or deletes a sanction. If a reason must be erased, for example on an erasure
request, this manual procedure is the one ADR-004 accepts for beta (the
2026-11-03 sanction-records amendment, under §1's narrow break-glass). It
replaces the reason with `[erased]`, as `redact` does for chronicle words,
and keeps the row, so the decision stays recorded and an active sanction
stays in force. Deleting the row instead would end the sanction.

1. Stop all application and heartbeat writers while keeping maintenance
   access, as in step 1 of "Restoring from a backup" (§7).
2. Find the sanction's id with `sanction list --all`, then run this from an
   interactive `fly ssh console` shell, with that id in place of `3`. It
   tombstones the sanction's reason and its lift's reason, if any. `VACUUM`
   rewrites the file so no free page keeps the old text, and the checkpoint
   empties the write-ahead log. The checkpoint cannot finish while another
   connection is still open, and the old text then stays in the database
   file. The snippet prints `busy` in that case: stop whatever still has the
   database open and run the snippet again.

   ```bash
   cd /app && python - <<'EOF'
   import sqlite3
   db = sqlite3.connect("/data/.nested-worlds/worlds.db")
   with db:
       db.execute("UPDATE sanctions SET reason = '[erased]' WHERE id = ?", (3,))
       db.execute("UPDATE sanction_lifts SET reason = '[erased]' WHERE sanction_id = ?", (3,))
   db.execute("VACUUM")
   busy = db.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0]
   db.close()
   print("busy: another connection is open; the old text is still on disk" if busy else "erased")
   EOF
   ```

3. Start the writers again, and check `sanction list --all` shows `[erased]`.
4. Remove the older copies that still hold the reason, in the order given for
   redacted text ([backup-bucket.md](backup-bucket.md), "Retention and
   deletion"): dispatch `backup.yml`, confirm `backup_health.py` reports a
   snapshot taken after the erasure, then `scripts/backup_store.py
   delete-before` with `--after` set to when the reason was written (the
   sanction's `created_at` when its reason must go; the lift's `lifted_at`
   only when the lift's reason alone must go), as a UTC stamp such
   as `20261001T000000Z`, and `--before` set to the last snapshot that can
   still hold it, dry run first. Delete the
   machine-local `/data/backups/*.db` copies and any downloaded
   `./worlds-backup.db` made since then. Fly's volume snapshots also hold it
   until they expire (5 days, §7). A reason typed on a command line is also
   in that shell's history (above).

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

Also before every deploy, check that no two registered names are one name
under the comparison registration uses (ADR-004 §7, `persistence.name_key`):

```bash
fly ssh console -C "python main.py invite duplicates"
```

It only reads. With every name its own, it prints `No two registered names
share a name key, and none shares one with a reserved world name.` and exits
0. Otherwise it exits 1 and lists each group, revoked names included: each
spelling through the CLI's escaping and again exactly as Python's `ascii()`
(so a composed and a decomposed `Élodie`, or a name with a zero-width space,
read differently), its key's digest prefix, when it was created, and whether
it is revoked. A registered name that is one of the world's own agent names
under the key (`Scout` followed by a zero-width space, which registration
accepted until 2026-11-04) is listed as a group headed by that agent's name.
Registration cannot create a group, so one means rows written before the
comparison, or a restored backup holding them. Both players keep working
under their own spellings, and nothing renames a stored name, but the
sanction CLI refuses the shared name (name the participant id) and other
players may not tell the two apart. Stop and take the list to the owner
before deploying. Nothing removes or renames a registered row, and revoked
names stay listed, so a group the owner has already decided on stays in the
output and the exit status stays 1: compare the list with the one the owner
saw, and stop only for a group that is new. `scripts/deploy.sh` does not run
this check; run it by hand before the script. A machine still running a
build without the command answers `invalid choice: 'duplicates'`; run the
check right after deploying the first build that has it.

**Off-host copies (every 30 minutes; freshness must be checked).** ADR-005 targets
at most one hour of lost history. A schedule alone does not establish that bound:
[GitHub documents delayed and dropped scheduled jobs](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).
The workflow takes an online backup, downloads a self-contained SQLite file,
checks integrity and required tables, and stores it in a private S3-compatible
bucket. Cloudflare R2 is an example of that store, and a 30-day retention is
the example used when the retention variable is unset. Mark has not recorded
either choice. Setup, the token, retention, and the rehearsal list are in
[backup-bucket.md](backup-bucket.md).

GitHub's artifact list is available to anyone with read access to the
repository ([artifact API](https://docs.github.com/en/rest/actions/artifacts#list-artifacts-for-a-repository)).
This repository is public, so the database is not uploaded as an Actions
artifact, including when validation fails or the bucket is not configured.
A failed check keeps the run failed and stores the file as
`offhost/unvalidated-worlds-backup-<app>-<UTC snapshot-start>.db` for operator
salvage. A healthy object is
`offhost/worlds-backup-<app>-<UTC snapshot-start>.db`. Quarantine names never
count as healthy backups. A successful upload is not yet a restore rehearsal.

The bucket is private: no public `r2.dev` URL and no custom domain. The job
reads secrets and variables. `FLY_API_TOKEN` is a deploy token for one app
(`fly tokens create deploy -a <app>`), not an organization token. The S3
access key, secret, bucket, and endpoint are secrets. The endpoint contains
the account id, and a bucket stored as a variable would appear in the public
job log. Region, retention, the app name, and `ENFOLDED_BACKUP_REQUIRED` are
variables. Until the token and the bucket settings are set, the scheduled run
is an inactive no-op and uploads nothing. The job log does not print the
object key.

Before a separately authorized launch, configure the repository as in the
bucket runbook, then:

- Variable `ENFOLDED_BACKUP_APP`: the exact app name (default `enfolded-beta`).
  Use the staging app during rehearsal; switch deliberately before production.
- Variable `ENFOLDED_BACKUP_REQUIRED`: exactly `true` before permanent history is
  accepted. Missing credentials or bucket settings then fail the workflow.
  Before activation, a missing value with the variable unset or exactly `false`
  produces an explicit inactive warning and no recovery claim. Any other value
  fails configuration; a typo cannot silently turn enforcement off.
- Variable `ENFOLDED_BACKUP_RETENTION_DAYS`: optional. When it is unset the
  workflow uses **30** as an example, not as a recorded retention period. It
  deletes this app's backup objects whose snapshot-start is at least that many
  days old, and it never deletes the newest validated object. Prune runs only
  after the store step succeeded. A lifecycle rule on prefix `offhost/` must
  be the retention plus 7 days or more. That rule expires by age and does not
  keep the newest copy, so it is an outer bound, not a substitute for the
  keep-newest prune. This replaces the old 90-day artifact expiry. The
  replacement of that expiry is not itself a decision to keep copies for 30
  days.

Manually dispatch `backup.yml` and confirm the object, not just the job badge.
Staging keys cannot satisfy the production check. Run this read-only check
with AWS CLI v2, the bucket, the endpoint, and either the write key or the
optional read key from the runbook. An R2 Object Read token can download every
backup; it is not a list-only key, and prune and `delete-before` list with it
when both read variables are set. The check itself only lists. It does not use
the GitHub API:

```bash
python scripts/backup_health.py --app enfolded-beta
```

It lists `offhost/` in the bucket and keeps the newest validated, nonempty
object for that app. Exit 0 when that object's snapshot-start is no more than
60 minutes old; 1 for missing or stale; 2 when the listing cannot be read.
It does not download data, validate contents, or restore anything. Quarantine
keys, other apps, empty objects, and future stamps are not counted. Age is the
stamp in the name, so a slow upload cannot freshen an old snapshot.

Run this check independently after workflow completion. A workflow cannot certify
its own successful conclusion while still running, and cannot detect its own
scheduler stopping. The backup job itself fails on invalid configuration,
validation, or upload failure. Arrange the independent check and operator notification
before launch; this batch provides the command, not an external monitor.
The `:17` and `:47` schedule leaves 30 minutes of nominal slack within the unchanged
one-hour freshness limit; it does not guarantee timely scheduling. If measured
cadence cannot meet that loss window, fix the transport/cadence or explicitly
revisit ADR-005. Record several subsequent objects before calling automation proven.

Download the selected object with `python scripts/backup_store.py get` (see the
runbook), retain its snapshot time, app, release SHA and file checksum, and
rehearse the restore below on an isolated instance. Treat downloaded data as
private operator data, never a public fixture.

### Same-schema release rollback

Use this when the running release and the previous release ship the same
schema and the new release is the problem. It is not a restore. History
stays. Target under 10 minutes once the app exists; that live staging drill
has not been run (checklist F4, which waits on F1).

```bash
# 1. Previous successful release, not the one running now.
fly releases -a enfolded-beta --image

# 2. Backup, schema check, then redeploy that image. Quote the ref.
scripts/deploy.sh --rollback 'registry.fly.io/enfolded-beta:deployment-…'

# 3. The process must be listening, and the logs must not show a schema refusal.
curl https://enfolded-beta.fly.dev/health
fly logs -a enfolded-beta
```

What the script does, in order:

1. `python main.py backup --to /data/backups/worlds-<UTC stamp>.db` on the
   machine. If that fails, it stops. Nothing is deployed.
2. Reads `MAX(schema_version)` from the live chronicle over
   `fly ssh console -C`. Hallpass shell-splits that command and execs the
   words; it does not run a shell. The probe starts with `env` and quotes
   the whole `python3 -c` argument, so the Python source stays one
   argument.
   It reads the highest migration file inside the image with
   `fly console -a <app> --image <ref> --skip-dns-registration -C ...`.
   `fly console` starts an ephemeral machine whose init is `/bin/sleep inf`
   (flyctl `ToConsoleMachineConfig`: restart `no`, auto-destroy, DNS
   registration skipped), SSHes in, and copies that command's stdout.
   `fly machine run` is not used: it prints launch metadata and does not
   stream guest stdout. No `--volume` and no `--port`, so the probe does
   not mount the chronicle and does not join the proxy. After the command,
   flyctl stops the machine and waits up to 15 seconds for it to be destroyed.
3. Deploys only when those two numbers are equal:
   `fly deploy -a enfolded-beta --image <ref>` (`--image` / `-i` is flyctl's
   "Docker image to deploy"). A newer or older image is refused. The backup
   from step 1 is kept. Machine-local backups are pruned to the newest five
   only after the check passes, and a failed prune does not block the deploy.
4. Prints the `/health` and `fly logs` checks.

`--first-deploy` cannot be combined with `--rollback`. The image ref must
be `registry.fly.io/<this app>:<tag>` or
`registry.fly.io/<this app>@sha256:<64 hex>`. Any other registry, app, or
a ref that looks like a flag or contains whitespace or shell
metacharacters is rejected before `fly` is called.

`FLY_APP` selects the app (default `enfolded-beta`). `FLY_BIN` selects the
flyctl binary (default `fly`).

A normal `scripts/deploy.sh` also refuses when this checkout's migrations
are older than the live chronicle, so deploying an old tree does not boot
an incompatible image. A newer checkout may migrate forward. That is a
deploy, not a rollback. `--rollback` of a newer image is refused because
the image would migrate on boot.

The process itself repeats the guard before it migrates. Startup reads
`schema_version` read-only and exits 1 when the chronicle is newer than
`known_schema_version()` (the highest migration shipped in that binary).
It then checks `NESTED_WORLDS_CANONICAL_SEED` and the model configuration.
`persistence.init_db` runs only after those checks, still before the port
opens. It repeats the refusal from a read-only open before it opens the
file writable, so a newer chronicle keeps its bytes and journal mode.
The migration guard inside `init_db` still refuses if the file changes
after that read. A release that ships the next migration and a bad seed or model id
exits with the chronicle unmigrated, so `--rollback` to the previous
release can still boot. The log line starts `chronicle schema_version`.

**When to stop.** If the script says the image schema is older than the
chronicle, do not look for a flag that skips the check. Go to
[Restoring from a backup](#restoring-from-a-backup). Restoring abandons
history written after that backup. There is no in-place downgrade.

**Budget caps are not copied by the script.** Both images read and write
`anthropic` and `fal_ai`, including the `:u:<hash>` per-user keys, so a
spent counter stays spent. An older binary does not read
`NESTED_WORLDS_VOICE_*` or `NESTED_WORLDS_IMAGE_*`. If those are the only
caps set, rollback uses the older defaults (voice 500 and 150, image 200
and 60) and can admit calls this binary already refused. Same-schema
equality does not preserve the limits. Before the older image boots, write
every effective cap onto the legacy variable that image reads:

| Effective cap | Legacy variable the older binary reads | Older default |
|---|---|---|
| Voice, global | `NESTED_WORLDS_ANTHROPIC_DAILY_CALLS` | 500 |
| Voice, per user | `NESTED_WORLDS_ANTHROPIC_DAILY_CALLS_PER_USER` | 150 |
| Image, global | `NESTED_WORLDS_FAL_DAILY_CALLS` | 200 |
| Image, per user | `NESTED_WORLDS_FAL_DAILY_CALLS_PER_USER` | 60 |

The effective value is the integer this binary enforces. One name set, or
both equal, uses that integer. Both set to different non-negative integers
uses the lower one. `0` is a valid refusal and must be copied as `0`. A
non-integer or a negative value makes this binary refuse startup and treat
the cap as 0. The older binary does not see a bad neutral value. A
non-integer legacy value falls through to the older default, and a negative
legacy value is clamped to 0. Set an explicit non-negative integer on each
of the four legacy variables before rolling back. A legacy-only deployment
already agrees. A neutral-only cap, or a higher leftover legacy value, does
not.

`fly secrets set` takes one or more `NAME=VALUE` pairs
(`fly secrets set [flags] NAME=VALUE ...`). `--stage` saves them and skips
the machine update. `fly secrets unset` takes names, not `NAME=VALUE`
(`fly secrets unset [flags] NAME ...`), and its `--stage` flag also skips
the update. `fly secrets deploy` then redeploys the current release with
the staged secrets and does not rebuild the image. There is no command
that sets and unsets in one invocation. Stage the four legacy values, then
deploy, and only then roll the image back:

```bash
fly secrets set -a enfolded-beta \
  NESTED_WORLDS_ANTHROPIC_DAILY_CALLS=<voice global> \
  NESTED_WORLDS_ANTHROPIC_DAILY_CALLS_PER_USER=<voice per user> \
  NESTED_WORLDS_FAL_DAILY_CALLS=<image global> \
  NESTED_WORLDS_FAL_DAILY_CALLS_PER_USER=<image per user> \
  --stage
fly secrets deploy -a enfolded-beta
scripts/deploy.sh --rollback 'registry.fly.io/enfolded-beta:deployment-…'
```

The neutral names are optional to remove. The older binary ignores them.
To drop them in the same restart, stage the unset before `fly secrets
deploy`. An unset without `--stage` updates the machines immediately:

```bash
fly secrets unset -a enfolded-beta \
  NESTED_WORLDS_VOICE_DAILY_CALLS \
  NESTED_WORLDS_VOICE_DAILY_CALLS_PER_USER \
  NESTED_WORLDS_IMAGE_DAILY_CALLS \
  NESTED_WORLDS_IMAGE_DAILY_CALLS_PER_USER \
  --stage
```

**If the machine will not stay up.** A schema mismatch that was deployed
by hand exits before listen, `fly ssh` fails, and `scripts/deploy.sh` cannot
take its backup. Redeploy the last image that matched the live schema:

```bash
fly deploy -a enfolded-beta --image 'registry.fly.io/enfolded-beta:deployment-…'
```

Use the ref from `fly releases --image` for the release that was healthy.
When `/health` is ok again, decide whether a restore is still required.
Do not restore until a binary that understands the current file is running,
unless you are replacing the database file by the restore procedure below
from a shell on that recovered machine.

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
#    A machine-local deploy copy is worlds-YYYYMMDD.db.
fly ssh console -C "python main.py restore --from /data/backups/worlds-YYYYMMDD.db --yes"

#    An off-host object is downloaded as ./worlds-backup.db and uploaded to
#    the same name. Use that path, not the dated deploy-backup name:
fly ssh console -C "python main.py restore --from /data/backups/worlds-backup.db --yes"

# 2. Restart so in-memory state (rooms, puzzle sessions, rate buckets)
#    matches the restored world.
fly machine restart <machine-id>
```

If the backup only exists off-host, download it with `scripts/backup_store.py get`
to `./worlds-backup.db`, run `scripts/validate_backup.py ./worlds-backup.db`,
then upload that same file: `fly ssh sftp shell`, then
`put ./worlds-backup.db /data/backups/worlds-backup.db`. Restore from
`/data/backups/worlds-backup.db`.
Earlier local rehearsals covered backup → mutate → restore. They do not prove
that this deployment's off-host object can be recovered. On isolated staging,
verify born rows/hinge and historical deltas, rotated identities and private-note
access, pinned puzzles, saved positions, pending inputs and completed fences.
Start a compatible build, confirm pending effects complete once, retry the original
request IDs, and check that no other account can read private notes. Record the
object checksum and elapsed recovery time. Never rehearse by rolling back the
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
redaction still contain the original text, and so do the machine-local
`/data/backups/*.db` copies and any downloaded `./worlds-backup.db`. Redact
the live text first, dispatch `backup.yml` and wait for it, then confirm
`backup_health.py` reports a snapshot taken after the redaction. Only then
run `scripts/backup_store.py delete` for one key, or `delete-before` with
`--after` and `--before` for the window that can still contain the text.
`--dry-run` prints that window and deletes nothing. A future cutoff is
refused. `delete` of one named key can remove the newest validated object.
`delete-before` and the retention prune cannot: both keep the newest
nonempty validated object. The example retention when the variable is unset
is 30 days, which Mark has not adopted as a decision. Any lifecycle rule
deletes the last copy once the schedule has been stopped that many days;
retention + 7 only delays it by 7 days. The rule does not keep the newest
object. Expiry is not a substitute for deleting a copy you were asked to
remove.

Redaction removes words from the chronicle. It does not keep their author
out: suspend or ban them for that (§6, "Suspending or banning a player").
Sanction reasons are not chronicle rows, and `redact` does not reach them.

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
and remains an exceptional disaster operation. An ordinary release rollback
on the same schema is [same-schema release rollback](#same-schema-release-rollback),
not this restore.

**T-1 week:**

- [ ] Private bucket, token, and variables configured ([backup-bucket.md](backup-bucket.md));
      `ENFOLDED_BACKUP_REQUIRED=true`. Manual dispatch and subsequent scheduled runs
      produce fresh app-specific objects. The job does not publish a GitHub artifact.
- [ ] Isolated restore rehearsed from a downloaded object of the intended app;
      before first production, use its staging twin, then verify production backup
      immediately after first deploy and before inviting participants.
- [ ] Independent bucket-freshness monitoring and failure notification exercised.
      A green no-op and an uptime ping cannot satisfy this gate.
- [ ] `SENTRY_DSN` set; `fly logs` shows `Sentry initialized` on boot.
- [ ] External uptime ping pointed at `/guide` (ungated, exercises the
      full serving path). Any free checker works.
- [ ] Size the day-one budgets deliberately: launch day is the highest-
      traffic day the app will ever see. Estimate
      `cohort size x expected exchanges x cost per exchange` and set
      `NESTED_WORLDS_VOICE_DAILY_CALLS` (and `NESTED_WORLDS_IMAGE_DAILY_CALLS`;
      the legacy `NESTED_WORLDS_ANTHROPIC_DAILY_CALLS` and
      `NESTED_WORLDS_FAL_DAILY_CALLS` names are still accepted, and a day
      already spent under `anthropic` or `fal_ai` stays on those keys, so
      it still counts). On an existing machine, set each legacy variable
      to the same integer in that `fly secrets set`. A leftover lower
      legacy value clamps the raise. `fly secrets unset` is a separate
      command.
      Set them with headroom above the estimate — the `_PER_USER` caps already bound any
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
      Buckets that start `voice_outcome:` or `moderation_outcome:` are
      outcome counts, not spend; `python main.py voice-health` prints the
      day's voice and moderation budget use without them.
- [ ] Watch the voice, not just the server. `fly ssh console -C "python main.py voice-health"`
      prints answered and quiet lines per surface (`speak`, `agent_voice`,
      `intention`) and reason (`provider`, `unconfigured`, `screen`, `busy`,
      `db`, `budget`, `action_cap`, `disabled`) and the day's budget use.
      `screen` means the moderation classifier failed or gave no usable
      verdict, so shared text was held before the voice was asked; moderation's
      own budget, per-user cap and disable switch count as `budget`,
      `action_cap` and `disabled`, and a content decline is policy and is not
      recorded. `busy` means every slot under the provider's concurrency limit
      (`NESTED_WORLDS_ANTHROPIC_CONCURRENCY`, default 8) stayed taken for the
      whole wait: the call's own timeout (3 s for the moderation classify that
      screens a line), else `NESTED_WORLDS_ANTHROPIC_SLOT_WAIT_SECONDS`
      (default 10 s). The provider was not called and the player got the same
      authored silence, or hold line, as a provider failure. Either the
      provider is slow or hung (a voice call passes no timeout of its own, so
      the adapter's per-attempt `NESTED_WORLDS_ANTHROPIC_TIMEOUT_SECONDS`,
      default 60 s, retried twice by the SDK, ends a hung call within about
      3 minutes, at most 5 if the provider answers errors with a retry-after
      of up to 60 s; that call then counts as `provider`) or
      demand outran the limit: check the provider first, then raise the limit.
      These counts cover the voice surfaces. The "Shared-text screens"
      section that follows covers every screened surface (`speak`, `agent`,
      `chat`, `ideas`, `profile`, `puzzle`, `name`, `cli`): per day and
      surface, the screens that logged a `moderation_call` line, then each
      outcome other than `allow`, then the day's moderation budget use. A
      locally clean line is not logged or counted, so `allow` counts
      classifier allows only. Three outcomes are screen failures and make it
      exit 1, because the text was held without being judged. `busy`: no
      provider slot opened within the classify's 3 s; check the provider,
      then raise the concurrency limit, as for the voice. `error`: the
      classify raised (provider error, timeout, or no usable moderation
      model id). A classify is one provider attempt with no retries inside
      its 3 s, so a single transient 429, 5xx or dropped connection is one
      `error` and fails the check; the player can send the text again. The
      `ms=` on the `moderation_call outcome=error` lines separates a slow
      provider from an immediate refusal, and `voice-health --probe` makes
      one tiny live call per distinct model id, the moderation model's
      included (also one attempt, so re-run it after a transient error).
      `undecided`: the classify
      finished without the one-word ALLOW or BLOCK it asks for (other text,
      a length stop or a refusal); a steady share suggests the configured
      `NESTED_WORLDS_MODERATION_MODEL` does not keep to that reply, so check
      it with the [evaluation harness](../../evals/README.md) before keeping
      it. `block` is a content decline, and `budget`,
      `user_cap` and `disabled` are limits: reported, never a failure. A
      failed screen on `/speak` or `/agent/voice` is counted in both
      sections, as the voice reason `screen` or `busy` and as the screen
      outcome; the two counts are reported separately. A screen counter
      that cannot get the store within 50 ms is dropped and logged on
      `nested_worlds.moderation`, so these counts are a lower bound too.
      It exits 1 when the window holds a voice provider, screen or
      busy failure, a shared-text screen failure on any surface, the voice
      is not configured, or the model configuration
      has a hard problem (the check `models` and the boot run); add `--probe`
      for the tiny live call `models --probe` makes. A counted failure lasts
      for its UTC day, as a voice failure already does: once one is counted,
      `voice-health` keeps exiting 1 until 00:00 UTC, or until the day leaves
      the `--days` window. Nothing clears it, and a passing `--probe` does
      not. So whatever schedules it (checklist B3) should alert at most once
      per UTC day, with the full `voice-health` output in the alert, not on
      every exit 1 (decided 2026-11-05 under the owner's delegation; no
      threshold, no separate exit code). The cost of that rule: a second
      failure later the same day does not alert again, so read the printed
      counts and the ERROR log or Sentry for anything newer. A player can
      provoke `undecided`: escalated text goes to the classifier as is, and
      text that knocks it off its one-word reply is undecided. A red result
      with only `undecided` counts may be model drift or injection; the
      per-user `moderation:u:` rows in `cost_budget` count each key's
      classify calls (at most 60 a day each). Revisit if more than
      3 of the first 14 scheduled days alert on screen failures alone, if
      `undecided` reaches 1% of classifier screens on a day, or at the first
      key traced to 5 or more `undecided` in one day.
      Every quiet line also logs `voice_fallback surface=... reason=...` on
      `nested_worlds.voice`, at ERROR (a Sentry event) for failures and WARNING
      for limits. Store errors are logged, not counted, and a counter write
      that cannot get the store within 50 ms is dropped (and logged), so the
      counts are a lower bound under heavy write contention. Where the scheduled
      check runs, and who it pages, is the P5 monitoring decision; `/health`
      and the `/guide` ping cannot see a quiet voice.
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
| Roll back to the previous image, same schema | `fly releases --image`, then `scripts/deploy.sh --rollback <image>` ([§7](#same-schema-release-rollback)) |
| Incident: kill switch, revoke, redact | [incident-response.md](incident-response.md) |
| See current machine status | `fly status` |
| Restart the machine | `fly machine restart <id>` |
| Inspect the volume | `fly volumes list` |
| Restore from a backup | `python main.py restore --from <file>` then restart (§7) |
| Adjust a runtime cap | Set the neutral name and the legacy name to the same integer in one `fly secrets set` (it accepts multiple `NAME=VALUE` pairs and restarts once). Example: `fly secrets set NESTED_WORLDS_VOICE_DAILY_CALLS=1000 NESTED_WORLDS_ANTHROPIC_DAILY_CALLS=1000`. Do the same for the image pair and for both `_PER_USER` pairs. A leftover lower legacy value is a warning, not a crash, and requests enforce that lower integer. Removing the legacy name is a separate `fly secrets unset NAME`. To apply the set and the unset in one restart, pass `--stage` on each and then run `fly secrets deploy`. There is no command that sets and unsets together. |
| Bound slow HTTP reads, response writes, or handler threads | `fly secrets set NESTED_WORLDS_HTTP_READ_TIMEOUT=30 NESTED_WORLDS_HTTP_WRITE_TIMEOUT=30 NESTED_WORLDS_MAX_HANDLER_THREADS=160` |
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

- **The configured provider's request-rate headroom shrinks (currently Anthropic)** → set
  `NESTED_WORLDS_VOICE_DAILY_CALLS` and `NESTED_WORLDS_ANTHROPIC_DAILY_CALLS`
  to the same new integer in one `fly secrets set`, and raise
  `NESTED_WORLDS_ANTHROPIC_CONCURRENCY`; no infra change needed. Leaving a
  lower legacy secret set keeps that lower integer. Removing the legacy
  name is `fly secrets unset`, staged and then `fly secrets deploy` when it
  should share the restart. `busy` in
  `python main.py voice-health`, in the voice section or the shared-text
  screens, while the provider answers normally is the concurrency signal:
  calls waited out the slot bound and were not made.
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
$2-5/month at the 20-user beta scale. Usage of the configured provider
(currently Anthropic) and fal.ai is separate and bounded by the daily call
caps you set in env.
