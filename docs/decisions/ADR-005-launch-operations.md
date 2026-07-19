# ADR-005: Launch-Window Operations Policy

**Status:** Accepted 2026-07-19

---

## Context

The first production deploy is the repo's largest cluster of one-way doors:
the content banks freeze permanently, and under the continuity covenant
(ADR-004 §3) whatever the first players do becomes history the project
carries forever. Four operational decisions sat unmade in the gap between
"the code is deployment-ready" (every automated gate green as of the
pre-launch hardening batch) and "the launch is ready." Each is cheap to
decide now and expensive to regret after the doors close.

This ADR was produced by interviewing the human (the "interview-me"
practice in `CLAUDE.md`), presenting each decision with its options and
trade-offs; the human ratified all four recommendations on 2026-07-19.

---

## Decisions

### 1. Backups: hourly off-host now; continuous replication is the first post-launch batch

The continuity covenant promises "a bad migration is a restore, not a lost
epoch," but the protection at decision time was one off-host copy per day
(inactive — `FLY_API_TOKEN` unset, 13 scheduled runs no-opped) plus Fly's
5-day volume snapshots. A 24-hour loss window on a permanent world
contradicts the covenant more than any documentation drift ever did.

**Decided:** `backup.yml` moves to an hourly cadence (one-line cron change,
hour-stamped artifacts, the already-rehearsed backup/restore path — loss
window 24h → 1h), and **Litestream-style continuous WAL replication to
object storage is scheduled as the first post-launch infrastructure batch**
(loss window → seconds), recorded in `phase-2-scale.md`. Continuous
replication is deliberately not a launch-week change: it is a new external
seam (it wants to own WAL checkpointing while the server checkpoints on
SIGTERM; the Docker entrypoint and the restore procedure both change) and
gets its own blind-spot pass and restore rehearsal.

### 2. The permanent world begins after a staging rehearsal

Launch day writes the most confused history the world will ever record —
first-time users fumbling, operator mistakes, and any still-undiscovered
write-path bug (phantom moves, truncated records, and double-counted acts
were all found *pre*-launch; the next such bug gets found *post*, and its
rows are forever). The §8 onboarding watch had no stated venue.

**Decided:** a disposable staging twin (`enfolded-staging`, own volume)
hosts the onboarding watch, the WS soak, the live-voice probe, and a
restore rehearsal, then is destroyed before launch (runbook §3a). The
production first-deploy happens after the rehearsal, deliberately.
ADR-004's "the current DB is pre-launch; there is no throwaway pre-launch
data worth protecting" makes this fully covenant-compatible — the
throwaway phase simply never touches the production volume.

### 3. Beta client posture: explorer default, `/app` the named alternate

Two feature-complete clients are a real maintenance tax under a
launch-window deploy freeze, and the executed parity harness (entry,
badges, event narration) still covers only part of the ~350-400
hand-mirrored explorer lines.

**Decided:** invites keep landing on `/` (the D3 explorer — no WebGL
dependency, works first-click on any device), and the guide names `/app`
as **"the scene view"** to try once oriented — an alternate, not an
"experimental" build (it is E2E-tested; the invite key carries over via
localStorage). Completing the parity harness is post-launch debt paydown,
not a launch gate.

### 4. Voice model: Opus-class stays; bump to `claude-opus-4-8`; Sonnet is a post-launch A/B

At beta scale the whole voice path costs single-digit dollars per day
(bibles are cache-read at the ~10x discount; replies cap at 256 tokens),
so model economics barely bear on launch. Verified figures: Opus-class
$5/$25 per MTok; Sonnet 5 $3/$15 — ~1.7x cheaper, and a quality risk at
exactly first-impression time.

**Decided:** stay Opus-class for launch and move the default from
`claude-opus-4-7` (now previous-generation) to **`claude-opus-4-8`** —
same price, same API surface (no request-shape changes; verified), same
4096-token prompt-cache minimum, so the `_OPUS_CACHE_MIN_TOKENS` guard
and both bibles stand unchanged. The live-voice spot-check on the new
default rides the staging rehearsal's live-voice probe (§3a). The
CLAUDE.md claim that voice quality is bottlenecked by context, not model,
becomes a real experiment **after** launch: A/B Sonnet 5 against live
transcripts, and switch only if quality holds.

---

## Trade-offs accepted

- **Hourly ≠ continuous.** Up to an hour of a permanent world can still be
  lost until the Litestream batch lands — accepted to keep launch week free
  of new external seams.
- **24 artifacts/day** at 90-day retention is a bulky trail — accepted;
  each copy is small at beta scale, and the cadence is revisited when
  continuous replication lands.
- **A staging twin costs a few hours and a few dollars**, and its config
  can drift from production — mitigated by using the same `fly.toml` and
  `deploy.sh` with only `FLY_APP` overridden.
- **De-emphasizing `/app`** hides the product's visual half from first
  impressions — accepted for the beta; the guide names it rather than
  burying it.
- **A model bump days before launch** carries nonzero voice-drift risk even
  at identical API surface — accepted because it is one env-swappable
  default, and the staging live-voice probe exercises it before any
  invite goes out.

## Revisit when…

- **The Litestream batch lands** → shrink the loss window to seconds;
  reconsider the hourly artifact cadence (a daily artifact may suffice as
  the second net).
- **The staging rehearsal surfaces a launch-blocking defect** → fix, then
  re-run the rehearsal; the production first-deploy waits.
- **The parity harness reaches the remaining duplicated explorer logic**
  → re-advertise `/app` as a co-equal surface if the cohort's devices
  support it.
- **A month of real transcripts exists** → run the Sonnet 5 A/B; if voice
  quality holds, take the ~1.7x saving (and note Sonnet's lower cache
  minimum makes the 4096 guard conservative-but-harmless, not wrong).
- **The DB outgrows a quick sftp pull** → the hourly workflow's download
  step is the bottleneck; that is a Litestream trigger, not a cadence one.

## Rejected alternatives

- **Litestream before launch** — right end-state, wrong week: a new
  external seam under deploy-freeze pressure is how this repo's worst
  defects shipped. Scheduled instead of skipped.
- **Onboarding rehearsal on production (with or without a sanctioned
  pre-launch restore)** — either writes fumbling into permanent history or
  normalizes restore-as-reset; the disposable twin costs almost nothing
  and also rehearses the deploy path itself.
- **Advertising both clients equally at launch** — doubles the surface
  where a cohort-facing bug bites during the window when nothing ships.
- **Finishing the parity harness pre-launch** — days of delay to prevent a
  drift class that executed parity already covers at the highest-traffic
  surfaces.
- **Switching to Sonnet 5 now** — saves single-digit dollars a day at the
  cost of voice drift at first-impression time; deferred to an evidence-
  based A/B.
- **A per-endpoint model hybrid** (Sonnet agents, Opus nodes) — requires
  code for savings that don't register at this scale.
