# ADR-005: Launch-Window Operations Policy

**2026-11-18 owner adoption:** The [2026-11-18 owner decisions](../roadmap/owner-decisions-2026-11-18.md) settle these points of launch operations.
The newcomer watch runs with AI on (D-A). The first key is minted as a step of
each deploy (item 7). The backup is dispatched by an outside scheduler, the
one-hour bound is proven over seven consecutive days on the staging twin, and
continuous replication follows the pilot (item 11). Sentry is on with frame
locals off (item 13). History becomes permanent with the first invited outside
player, by an operator-minted key or a redeemed registration invite, and
rehearsals stay on staging (ADR-004 section 3; item 9). By the owner's answer of
2026-11-19, a production world is not reset once the launch checklist's world
status is declared, which for the cohort world comes before that player
(item 9). The public map switch (item 2) is recorded in section 3 below.
Watch sessions are due by
11 December 2026, and the cohort date is set at the watch read-out (item 39).

**2026-11-15 study-entry amendment (owner-decided):** The owner
[adopted eight entry requirements for the newcomer watch](https://github.com/mark-weeks/hello-nested-worlds-adventure/pull/173#issuecomment-6896202913)
and directed #173 to contain study-admission work only. This amendment is limited
to entry requirements; it does not retire the explorer, redirect `/`, replace the
accepted client posture, or approve deployment/recruitment. Both clients remain.

**Context:** Study outcomes such as curiosity, puzzle interest and seven-day return
cannot be prerequisites to admit the participants needed to measure them. A short,
facilitated disposable watch has a narrower operating scope than the continuing
8–12 person cohort.

**Decision:** Use the [Watch column of the eight entry requirements](../roadmap/beta-launch-checklist.md#admission-gate)
for the 2–3 person newcomer watch, preserving applicable consent, access, safe shared
play, provider/spend and data-retention controls. Participants are **18 or older**,
asked affirmatively at sign-up. An AI-off watch disables external routes through
its frozen model policy, never through the moderation off-switch; unknown shared
text must retain the existing safe hold. A silent watch establishes no model-quality
result. The cohort starts only after the watch and its outcomes/fixes are recorded,
and must additionally meet its cohort-specific requirements and continuing-world
recovery/operation proof. The owner's version-4 decision page, supplied in the
working chat on 2026-11-15, requires a report to reach a person within 24 hours,
a same-day path for threats or doxxing, and someone named on duty each day; an
exact, labelled cohort release that passed every automated test; and every
full-checklist item to apply unless the owner excuses it in writing. Stage labels
and the narrower watch scope do not supply such an exception.

**Trade-offs accepted:** Historical inventory statuses remain evidence, not a blanket
watch veto or a claim that entry checks passed. Measurement and later-improvement
rows remain visible. No continuing-world recovery obligation is waived by a
successful disposable watch, and no temporary-world reset promise is silently
converted into permanence.

**Revisit when:** The admitted venue, devices, audience, enabled providers or world
status changes, or observed play identifies a safety/usability defect that prevents
the next session. Existing one-way-door decisions retain their separate approvals.

**Rejected alternatives:** Require study outcomes before study entry; treat a passing
local test as hosted recovery proof; use `NESTED_WORLDS_DISABLE_MODERATION` as an
AI-off switch; bundle client consolidation or agent-rule changes with this amendment.

**2026-11-04 pilot client revision (owner-approved):** The recommendation in
the preceding message was: "I’d build one coherent first-visit-and-return
experience next, using `/app` as the pilot client." Its bounded scope was
consistent invitations, registration, home bookmarks and recaps; verification
of arrival, exploration, action, consequence and return; narrow-screen,
keyboard and missing-artwork checks; and preservation of free exploration
through Speak | Puzzle | Act. The owner then instructed: "Proceed with the
recommended next batch."

That instruction authorizes the recommended implementation and scoped
pilot-client choice. It does not approve deployment, recruitment, map
retirement, or waive the device and human evidence named in the recommendation.
That revision moved minted invites, self-service registration and primary
return links to `/app` and kept the original world map at `/`. The later
public route switch in section 3 supersedes that map address. Physical-device,
accessibility, fallback and observed-newcomer checks remain required before
including those devices in the cohort.

**2026-09-12 client development revision (historical).** This revision made
`/app` the primary surface for the discovery/return slice. At that time the
explorer at `/` still received invites. The scene gained a responsive layout
and navigable text fallback. The revision called for device, accessibility,
fallback and human onboarding evidence. See ADR-025 and the implementation
evaluation.

**Status:** Accepted 2026-07-19

**Update (2026-11), backups only:** The off-host copy in decision 1 moved, in
#136 (`23b8830`), from GitHub Actions artifacts to a private S3-compatible
bucket. The operator notes are
[backup-bucket.md](../infrastructure/backup-bucket.md). The artifact approach
would have exposed unencrypted player chat on this public repository: the
old workflow uploaded a downloaded SQLite snapshot, player chat included,
with `actions/upload-artifact` when that download succeeded, and GitHub's
artifact list is available to anyone with read access. Nothing was deployed,
so no live database was ever uploaded. The workflow uploads nothing until
`FLY_API_TOKEN` and the `ENFOLDED_BACKUP_S3_*` secrets are set. Cloudflare
R2 is only an example of a vendor. 30 days is the job's placeholder default
when `ENFOLDED_BACKUP_RETENTION_DAYS` is unset
(`.github/workflows/backup.yml`, `scripts/backup_gate.sh`). Neither is a
chosen vendor or a chosen retention period. This note does not change the
Accepted status above or the decision text below.

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

### 3. Browser entry and the original explorer

On 2026-11-20 the owner adopted decision O10 for item 2. X1 added the shared
React map and X2 switches the public entry to it.
[Owner decision O10](../roadmap/owner-decisions-2026-11-20.md#o10-the-old-maps-path-and-the-map-view-reading-item-2) · [X1 (#190)](https://github.com/mark-weeks/hello-nested-worlds-adventure/pull/190) · [X2 (#191)](https://github.com/mark-weeks/hello-nested-worlds-adventure/pull/191)

A fresh visit to `/` opens the shared React world map. Invitations,
registration and journal return links open the living scene at `/app`.
The player can switch views at the same place with one session, one
participation notice and the same Speak, Puzzle, Act and Travelers controls.
The map uses D3. The scene uses a 2D canvas and offers text and passages
when drawing is unavailable. The client dropped its unused PixiJS shim.

The original D3 explorer is available at `/map` through the cohort read-out.
During that period it receives privacy, safety and correctness fixes and
changes from batches the owner already ratified. Its HTML shell can load
before a player supplies an invite key. World data and play still use the
invite and participation checks. The cohort's device, accessibility and
newcomer checks remain part of admission.

#### Original 2026-07-19 client decision (superseded)

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

### 4. Historical voice-model choice (selection policy superseded 2026-10-04)

**Revision:** [ADR-034](ADR-034-provider-and-model-optionality.md) supersedes this
section's Opus preference, Sonnet-only comparison and post-launch-only evaluation
sequence, including the related trade-offs and alternatives below. Evaluate suitable
providers, models and versions by task; none receives standing preference. The
current code default is retained pending evidence, not re-endorsed. The following
records the original decision and its then-stated assumptions; its model availability,
prices and cache claims are historical, not current verification.

#### Original decision: Opus-class at launch

At beta scale the whole voice path costs single-digit dollars per day
(bibles are cache-read at the ~10x discount; replies cap at 256 tokens),
so model economics barely bear on launch. Verified figures: Opus-class
$5/$25 per MTok; Sonnet 5 $3/$15 — ~1.7x cheaper, and a quality risk at
exactly first-impression time.

**Decided:** stay Opus-class for launch and move the default from
`claude-opus-4-7` (now previous-generation) to **`claude-opus-4-8`** —
same price, same API surface (no request-shape changes; verified). The
original text of this decision assumed a shared 4096-token prompt-cache
minimum, so the then `_OPUS_CACHE_MIN_TOKENS` guard and both bibles would
stand unchanged. That figure does not match the cache-size table in
`consciousness/anthropic_provider.py`, which records `claude-opus-4-8` at
1024 tokens — the same table
[`docs/development/agent-runtime.md`](../development/agent-runtime.md) cites
(Claude API reference checked 2026-10-05). `_OPUS_CACHE_MIN_TOKENS` is not
defined in the current code. The live-voice spot-check on the new
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
- **One pilot client and a retained explorer.** Players can switch between
  map and scene within the React session. Keeping the original explorer at
  `/map` preserves its ambient observation view and incurs the cost of
  maintaining a second client through the cohort read-out.
- *Historical trade-off from the July decision, superseded in November.*
  **De-emphasizing `/app`** hides the product's visual half from first
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
- **The cohort device checks or newcomer observations expose a client
  blocker** → fix and recheck it before using that device; revisit the pilot
  client choice if the blocker cannot be resolved. Any proposal to retire
  the original explorer after the cohort read-out needs its own decision
  and evidence.
- *Historical trigger from the July decision, superseded in November.*
  **The parity harness reaches the remaining duplicated explorer logic**
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
- **Retiring the world map in the pilot-client batch** — a consistent
  default does not establish that the alternate's uses can be removed.
- **Finishing the parity harness pre-launch** — days of delay to prevent a
  drift class that executed parity already covers at the highest-traffic
  surfaces.
- **Switching to Sonnet 5 now** — saves single-digit dollars a day at the
  cost of voice drift at first-impression time; deferred to an evidence-
  based A/B.
- **A per-endpoint model hybrid** (Sonnet agents, Opus nodes) — requires
  code for savings that don't register at this scale.
