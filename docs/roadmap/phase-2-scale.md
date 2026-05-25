# Phase 2: Scale Plan (20 → 100 → beyond)

The hosted beta launches at **20 users**. This document records what's in
place now, what we'll do at the 100-user threshold, and what's deferred
behind explicit triggers beyond that. The whole philosophy is *trigger-
driven, not date-driven*: every deferred item lists the observable signal
that justifies pulling it forward.

The 20-user readiness work is shipped — see `[Unreleased]` in
[`docs/CHANGELOG.md`](../CHANGELOG.md). The two beyond-now sections below
describe future work.

---

## Phase 2a — Optimized for 20 users (shipped)

This is what is configured and running for the initial cohort. Everything
here is operational headroom; nothing on this list is speculative.

### Capacity headroom at 20 users

| Resource | Budget | Expected use | Utilization |
|---|---|---|---|
| Anthropic daily calls | 500 (`NESTED_WORLDS_ANTHROPIC_DAILY_CALLS`) | ~100/day (20 × 5) | 20% |
| fal.ai daily calls | 200 (`NESTED_WORLDS_FAL_DAILY_CALLS`) | ~100/day | 50% |
| Per-IP rate limit | 20/min (`NESTED_WORLDS_RATE_LIMIT_PER_MIN`) | well under | n/a |
| Anthropic concurrent calls | 8 (`NESTED_WORLDS_ANTHROPIC_CONCURRENCY`) | bursts to 5–8 | ~peak |

### What we built for this cohort

1. **Anthropic concurrency semaphore** (`consciousness/__init__.py`).
   `BoundedSemaphore(8)` wraps every `messages.create()` call. Bounds
   instantaneous concurrency so a synchronized burst can't trip Anthropic's
   org-level RPM and 429 the whole cohort simultaneously. Tunable via
   `NESTED_WORLDS_ANTHROPIC_CONCURRENCY`.

2. **Per-user invite keys** (`persistence/migrations/0004_invite_keys.sql`,
   `server/guard.py`, `main.py`). Each tester gets a unique key minted via
   `python main.py invite mint --name <Name>`. Keys are individually
   revocable (`invite revoke <key>`), and `lookup_invite_key` opportunistically
   touches `last_used_at` (throttled to 5-minute intervals to keep the auth
   path off the SQLite hot path). Coexists with the shared
   `NESTED_WORLDS_BETA_KEY` env var so ops scripts can still authenticate
   without a DB row.

### Operator workflow at 20 users

```bash
# Mint a key per tester (do once per cohort member)
python main.py invite mint --name Alice --note "design partner"
# → emits a URL: <BASE>/app?key=<KEY>&name=Alice

# Check who's still active (last_used_at reflects ~5-min-quantized activity)
python main.py invite list

# Revoke if needed
python main.py invite revoke nw_...
```

### Watch list (no action until triggered)

These are the metrics that will tell us when to start Phase 2b. All are
already emitted — read them from Sentry (uncaught exceptions) and the
`nested_worlds.access` JSON log.

| Metric | Source | Phase 2b trigger |
|---|---|---|
| Anthropic daily-call utilization | `cost_budget` table, bucket `anthropic` | > 60% of cap for 3 consecutive days |
| fal.ai daily-call utilization | `cost_budget` table, bucket `fal_ai` | > 60% of cap, OR monthly bill > $50 |
| SQLite write errors | server logs (`database is locked`) | any occurrence at p95 latency |
| Concurrent /speak in flight | semaphore wait time (add timing log if needed) | observed wait > 500ms p95 |
| Active testers | `invite_keys.last_used_at` | crosses 50 active in 7-day window |

---

## Phase 2b — 100 users (deferred, triggered)

Pull each item forward when its trigger fires, not on a calendar.

### Trigger: cost cap utilization > 60%

**Raise daily caps and add per-user budgets.**

* Bump `NESTED_WORLDS_ANTHROPIC_DAILY_CALLS=5000` and
  `NESTED_WORLDS_FAL_DAILY_CALLS=2000` as a first response.
* If individual testers are skewing the distribution, add a per-key budget
  column to `invite_keys` (e.g. `daily_anthropic_quota`) and an
  `(invite_key, day)` row in `cost_budget` (or a new
  `cost_budget_per_key` table). Bound: ~half a day's work; the
  cost-tracking code is already centralized in `server/guard.py`.

### Trigger: fal.ai monthly bill > $50

**Put Cloudflare in front of `/image`.**

* `node_key` (the `cache_image` key) already includes seed, node id,
  history bucket, and style signature — it's deterministic and safe to
  cache by URL. A single Cloudflare Worker rule caching `/image`
  responses keyed on the request body hash collapses N players hitting
  the same node into one fal call.
* Estimated effort: an afternoon. Estimated savings: ~80% of fal spend at
  100 users (most nodes have repeat visitors).

### Trigger: any `database is locked` error OR write p95 > 50ms

**Postgres switchover.**

* Plan and seam are already documented in
  [`docs/decisions/ADR-003-persistence-backend.md`](../decisions/ADR-003-persistence-backend.md).
  The `--- SQL dialect seam ---` block in `persistence/__init__.py`
  concentrates the SQLite-isms so the port is mechanical.
* Estimated effort: half a day for the code, plus a one-time data copy
  via `pg_dump`-style export from the SQLite snapshot.

### Trigger: rolling deploys need to be lossless

**Move room state to Redis.**

* `_rooms: dict[int, Room]` in `server/rooms.py` is the single piece of
  process-local state that prevents both horizontal scale and zero-downtime
  deploys. Replace with `redis.Redis` plus pubsub for the broadcast path.
* This is the single change that unlocks the rest of phase 2c. Estimated
  effort: 1–2 days. ADR-001 has the original sketch.

### Trigger: thread count > 200 OR /speak p95 latency degrades

**Switch to ASGI (`uvicorn` + `asyncio`).**

* The current `ThreadingMixIn + http.server` spawns one OS thread per
  connection; at 100 concurrent WebSocket players plus burst HTTP load,
  this works but is wasteful and bounds total throughput by thread
  scheduling.
* Wrap the existing `Handler` in a thin ASGI shim, or rewrite the dispatch
  in `server/handlers.py` against `Starlette`/`FastAPI`. The WebSocket
  framing (`server/protocol.py`) can be retired in favor of the framework's
  built-in support.
* Estimated effort: 2–4 days, mostly testing.

---

## Phase 2c — Beyond 100 users (architectural, not yet planned)

These get a paragraph each because we don't have the signal to estimate
them yet. They're listed so future-us doesn't repaint the bike shed.

* **Multi-host horizontal scale.** Requires both Redis rooms (above) and
  ASGI (above). Add an L7 load balancer with sticky WebSocket sessions
  (Fly proxies do this natively). At this point the architecture is no
  longer "one box."

* **First-party image hosting.** fal.ai URLs expire eventually — see
  ADR-002 "Revisit when…" — so beyond a certain cumulative image count
  we'll need to push generated images to R2/S3 and cache the durable URL.

* **Per-tester sandboxes vs. shared multiverse.** Today every tester on
  the same seed is in the same room. At ~500 users the broadcast fan-out
  (every move broadcasts to every other player) becomes the bottleneck.
  Introduce a "shard within a seed" concept so a room holds at most ~50
  participants.

* **Background causality worker.** Causal events currently fire
  synchronously inside the request that triggered them. At high event
  rates this couples request latency to causality complexity. Move to a
  worker process consuming an event queue.

---

## What we are NOT doing

For clarity, these are explicitly *not* on any near-term roadmap and
shouldn't be pulled forward without a serious signal:

* GraphQL or alternative API layer.
* Account/login system (the invite key IS the credential).
* Mobile-native clients.
* Persistent game state across cohorts (each beta cohort gets a fresh DB).

---

## Living document

Edit this in place as triggers fire. When you start work on a Phase 2b
item, move it into a dated "In progress" section here and link the PR.
When it ships, fold the description into the `[Unreleased]` changelog
entry and delete the section. The goal is for this file to always
reflect *the next decision*, not historical state.
