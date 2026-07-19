# Working in Enfolded

Enfolded is a persistent multiverse — eleven nested scales inhabited at once by
human players and Claude-powered agents — built by directing fresh Claude Code
sessions, roughly one per PR. Because each session starts cold, the hard-won
rules of this repo are otherwise unknowns you'd rediscover (or violate) every
time. This file is the standing map. It is distilled from `docs/CHANGELOG.md`,
the ADRs, the roadmap, and test docstrings; when in doubt, the enforcing file
named beside each rule is the territory.

Read this before planning. The rules below are not stylistic preferences —
several are permanent, one-way doors.

---

## World covenants (the rules that never made it into a spec)

These are house taste, encoded once at a point of use and easy to break by a
well-meaning change. Honour them; a reviewer would catch a violation, so catch
it first.

- **The seal never imprisons.** A locked (sealed) subtree never traps someone
  already inside it. `puzzles/gates.py` (`# already inside — the seal never
  imprisons`).
- **Difficulty is per-node, never a depth curve.** Traversal is non-linear —
  players drop in at any scale — so scale sets a puzzle's *flavour*, never how
  hard it is; each node draws its own 1–4 difficulty from its identity.
  `puzzles/generators.py` (`node_difficulty`), README puzzle row.
- **Failure stays in fiction — on every authored surface.** Anything a player
  reads as the world's voice speaks in fiction: AI/budget/kill-switch paths
  return HTTP 200 with `ai: false` and an authored line of silence
  (`consciousness.LEVEL_FALLBACKS`, `fallback_voice`,
  `guard.QUIET_RESPONSE`), image failures answer the authored quiet line with
  `images: false` (`handlers._IMAGE_QUIET_LINE` — never "FAL_KEY not set" or
  a raw upstream error), and rate-limit denials carry the pace line
  (`handlers._PACE_LINE`) because both clients render `error` text verbatim.
  Transport-level refusals sit *outside* the fiction by scoped decision
  (2026-07-18 evaluation §4): the invite-gate 403, payload 413, malformed-body
  400, and WS-cap 503 are plumbing a browser client never surfaces — they may
  stay mechanical, but must be clean JSON. What is never acceptable: a stack
  trace, or a 5xx for a client-shaped mistake (malformed bodies and non-string
  answers are the client's 400/200, guarded by
  `tests/test_guard.py::TestBodyShapeRobustness`).
- **The chronicle blurs; live presence may distinguish.** Whether a *trace*
  was left by human or agent is deliberately left open — one ledger voices
  them the same way, and `/chronicle` carries no actor-type flag. Live
  presence is the scoped exception, decided when the travelers panel shipped
  (PR #59) and made explicit on 2026-07-18: the panel persona-tags the
  walking cast and routes presences to `/agent/voice` vs `/speak`, because
  addressability needs an addressee. Don't extend taxonomization into the
  chronicle, history feeds, or node voices. README concept,
  `docs/evaluation/2026-07-04-deep-evaluation.md` G1.
- **Agent solves don't count as human progress.** An ambient/FSM agent standing
  on a puzzle never claims a co-op session, opens a seal, or lights a
  constellation. `persistence/__init__.py` (`Agent solves … carry "agent"`),
  CHANGELOG constellations entry.
- **The chronicle is append-only; three sanctioned mechanisms, no more.**
  Never delete or rewrite `world_mutations` rows in application code. Abuse is
  handled by content-level redaction (`python main.py redact`, runbook §7 —
  mechanical fields survive so counters and epochs stay intact); pruning
  exists but is double-gated behind `NESTED_WORLDS_MUTATION_TTL_DAYS` *and*
  `NESTED_WORLDS_ALLOW_HISTORY_PRUNE=1` (and `prune_mutations()` must never
  be called directly); whole-DB restore (`python main.py restore`) is the
  disaster path, not an edit path. `persistence/__init__.py` redaction
  section, `fly-deployment.md` §7.

---

## The permanent world (one-way doors — treat with care)

**The world is data now** (ADR-006, Option A, ratified 2026-07-19): the
generator runs ONCE per seed as a *birthing* tool (`multiverse/store.py`,
`world_nodes` table, migration 0013), and from birth on the **stored row is
the node's identity**. Node names still key all durable history (mutations,
saved positions, property overlays, ripple scores, art activity counts) —
but those names now live in the store, not in the banks.

- **A born world is never re-born.** `birth_world` is idempotent and
  `persistence.save_world_nodes` refuses to overwrite — nothing in
  application code may regenerate or rewrite `world_nodes` rows for a seed
  that has them. Deliberate evolution of a born node is a *future,
  ADR-gated* write path (chronicled world events — see ADR-006 "Revisit
  when"); it does not exist yet, so today any code path that would mutate a
  stored node's name/level/base properties is a bug.
- **Content banks govern births only.** Editing `multiverse/generator.py`
  banks cannot touch any world that already exists — pinned by
  `tests/test_world_store.py::TestBankEditImmunity`. A bank edit changes
  what NEW worlds are born as: bump `GENERATOR_VERSION`
  (`multiverse/store.py`) for meaningful generator changes and consciously
  re-pin the golden digests, recording why in the CHANGELOG.
- **The golden pins now describe births.** `tests/test_continuity_freeze.py`
  (both depths — the depth-6 reference world AND the full 11-level world;
  five scales exist only below depth 6) pins what generator v1 births. A
  failing pin no longer means "you are rewriting the permanent world" — the
  store forbids that — it means "you changed what new worlds are born as":
  stop, confirm it's intended, bump the version, re-pin deliberately.
- **One read-time generative surface remains frozen: era names.**
  `multiverse/chronicle.py`'s two display banks are read at render time, so
  editing them retroactively renames every era already displayed. They stay
  frozen (exact strings pinned) until eras are materialized (ADR-006).
- **Continuity policy** (`docs/roadmap/phase-2-scale.md` "Continuity policy"):
  never wipe the DB between cohorts; migrations are **additive only** (new
  tables / new columns with defaults — no destructive rewrites of
  `world_mutations`, `agent_memory`, `puzzle_results`, `world_nodes`);
  back up before every deploy. Deploy via `scripts/deploy.sh`, which refuses to
  deploy over an unbacked chronicle. The DB is now the sole authority for
  world content — backups protect the world itself, not just its history.

---

## Determinism contract

**At birth**, every node is a pure function of `(seed, path)` under the
current `GENERATOR_VERSION`: name → properties → breadth all draw from that
node's own keyed RNG stream, so a fresh install birthing a reference seed
reproduces it exactly, and any depth view is a true prefix of the one stored
full-depth world. **After birth**, the stored row is authoritative, and
art/sound/puzzles derive deterministically from the node *as served* — so
co-op reproducibility and reproducible screenshots survive, and will follow
evolution when it exists. Consequences:

- No `Math.random()`, `Date.now()`, `time.time()`, or other wall-clock/entropy
  in generation, art, sound, or puzzle-selection code paths.
- Worlds must generate identically under the pinned interpreter — **Python
  3.11** (Dockerfile and CI both pin it; the freeze pins police this).

---

## Testing discipline

- **Behavior tests, not grep tests.** Assert what the code *does* (drive the
  endpoint, run the generator, inspect the built prompt), never that a string
  appears in a file. Two P0s shipped because substring/grep "tests" passed while
  behavior was broken; the fix each time was a real behavior test. See
  `tests/test_frontend_contract.py`'s own history and the CHANGELOG P0 entries.
- Run the suite before proposing merge: `pip install -e ".[dev]" && pytest tests/ -q`
  (plus `cd frontend && npm test` for the Vitest cross-client parity tests).
- The invariant suites are the crown jewels — keep them honest: puzzle no-leak /
  solvable / per-node-difficulty (`tests/test_puzzles.py`), continuity freeze
  (`tests/test_continuity_freeze.py`), causal wiring, staged-cascade equivalence,
  restart-proof co-op.

---

## The Claude runtime

- Model: `claude-opus-4-8` (env `NESTED_WORLDS_MODEL`). Voice quality is
  bottlenecked by the *context* the prompt carries, not the model — when a voice
  is flat, first ask what world-state the dynamic block is withholding, not
  whether the model is capable.
- **Prompt-cache minimum is 4096 tokens on Opus-class models, not 1024.**
  `cache_control` on a shorter prefix is a silent no-op — this shipped twice.
  Both bibles are deliberately sized past the minimum;
  `consciousness.cached_prefix_meets_minimum()` guards it and
  `warn_if_cache_ineffective()` fires at server startup if a future edit shrinks
  them. Don't trim the bibles below it.

---

## Working rules for this repo

- **One CHANGELOG entry per change, with measured evidence.** `docs/CHANGELOG.md`
  is the running deviation-and-surprise log the next session navigates by —
  quantify surprises ("+1 syllable renames 77/83 nodes"), don't just describe
  outcomes. Substantial audits/pre-mortems that drive a batch land as
  `docs/evaluation/YYYY-MM-DD-<name>.md` in the same PR.
- **Decisions get an ADR** in the `docs/decisions/` house style (Context /
  Decision / Trade-offs accepted / Revisit when… / Rejected alternatives).
  Prefer writing it *before* building — interview the human, front-loading the
  architecture-changing questions — so ADRs stop being post-hoc reconciliations.
  Each ADR's "Revisit when…" triggers are live; honour them.
- **Blind-spot pass at external seams.** Before touching an external contract —
  Anthropic API parameters, fly.io config, browser CSP, the WebSocket/RFC 6455
  handshake, PixiJS lifecycle — state your assumptions and verify them against
  live docs or a live run *before* implementing. The repo's three worst shipped
  defects all lived exactly here (the 1024-vs-4096 cache minimum, PixiJS dead
  under production CSP, deploy files that existed only as fenced code in a doc).
- **Gate merges by irreversibility, not by reflex.** After tests pass, write a
  2–3 line **irreversibility check** yourself and put it in the merge request:
  does this diff re-pin a golden world, add or alter a migration, or add a
  `world_mutations` write path / chronicle row? For most PRs the answer is
  "none, and here's why" — verify that from the diff and merge on green. Don't
  make the human answer what the diff already answers; comprehension checks the
  code makes for you are friction, not a gate. **Escalate to an actual quiz only
  when the check trips** a one-way door — then ask just the 1–2 questions that
  door raises (which pins and why safe; what the new row/migration/write path is;
  the matching launch-runbook §8 scenario), hardest first, and fold any missed
  answer into that PR's CHANGELOG entry. The human is the last un-automated gate
  on *irreversible* decisions — spend their attention there, not everywhere.

---

## Pointers

- `docs/CHANGELOG.md` — the batch-by-batch record; read it to learn what shipped.
- `docs/decisions/ADR-00{1,2,3,4,5,6}-*.md` — stack, image generation,
  persistence backend, the day-one data policy (permanence, redaction,
  continuity, identity, write-path scope), the launch-window operations
  policy (backup cadence, staging rehearsal, beta client posture, voice
  model), and the evolving-world decision (the world materialized as data;
  banks govern births only — Option A, ratified), each with its "Revisit
  when…" triggers.
- `docs/roadmap/phase-2-scale.md` — the continuity policy and the phase-2b/2c
  trigger list (living document — edit in place as triggers fire).
- `docs/infrastructure/fly-deployment.md` — the deploy runbook and §8 launch
  window checklist.
- `docs/evaluation/2026-07-04-deep-evaluation.md` — the deep map-vs-territory
  audit (see its dated addendum for what has since shipped).
- `README.md` — concept, architecture, and the current-state matrix.
