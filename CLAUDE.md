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
- **Failure stays in fiction.** No player-facing `503` or stack trace. Every
  scale has an authored line of silence (`consciousness.LEVEL_FALLBACKS`,
  `fallback_voice`); AI/budget/kill-switch paths return HTTP 200 with
  `ai: false`, never an error. `server/handlers.py` `/speak` fallback,
  `server/guard.py` `QUIET_RESPONSE`.
- **The blur is the product; the presentation must not un-blur it.** Whether a
  visitor is human or agent is deliberately left open — one trace ledger voices
  them the same way. Don't add UI or prompts that authoritatively taxonomize
  actor type. README concept, `docs/evaluation/2026-07-04-deep-evaluation.md`.
- **Agent solves don't count as human progress.** An ambient/FSM agent standing
  on a puzzle never claims a co-op session, opens a seal, or lights a
  constellation. `persistence/__init__.py` (`Agent solves … carry "agent"`),
  CHANGELOG constellations entry.
- **The chronicle is append-only; redaction is the *sole* sanctioned
  exception.** Never delete or rewrite `world_mutations` rows. Abuse is handled
  by content-level redaction only (`python main.py redact`, runbook §7) —
  mechanical fields survive so counters and epochs stay intact.
  `persistence/__init__.py` redaction section, `fly-deployment.md` §7.

---

## The permanent world (one-way doors — treat with care)

The generated world is a **compatibility surface**: node names key all durable
history (mutations, saved positions, property overlays, ripple scores, art
activity counts). See `tests/test_continuity_freeze.py` — read its docstring in
full before any change to `multiverse/generator.py` content banks.

- **The freeze/re-pin protocol.** If a freeze pin fails, you are about to
  rewrite the permanent world. **Stop.** Pre-launch: either revert, or
  *consciously* re-pin after confirming the drift is intended (and record why
  in the CHANGELOG + PR body). **Post-launch there is no re-pinning — the banks
  are frozen.**
- **Pins cover BOTH depths.** The depth-6 reference world *and* the full
  11-level world. Five scales (Room and deeper) exist only below depth 6, so a
  depth-6-only pin is blind to their banks — this exact gap once let an
  Object-level edit silently delete ~170 deep nodes while every shallow pin
  passed. Never re-pin only the shallow digest.
- **Continuity policy** (`docs/roadmap/phase-2-scale.md` "Continuity policy"):
  never wipe the DB between cohorts; migrations are **additive only** (new
  tables / new columns with defaults — no destructive rewrites of
  `world_mutations`, `node_interactions`, `agent_memory`, `puzzle_results`);
  back up before every deploy. Deploy via `scripts/deploy.sh`, which refuses to
  deploy over an unbacked chronicle.

---

## Determinism contract

Every node is a pure function of `(seed, path)`: name → properties → breadth all
draw from that node's own keyed RNG stream, so any depth prefix of a world is
byte-identical to the full world, and art/sound/puzzles are reproducible for
co-op. Consequences:

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

- Model: `claude-opus-4-7` (env `NESTED_WORLDS_MODEL`). Voice quality is
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
- `docs/decisions/ADR-00{1,2,3,4}-*.md` — stack, image generation, persistence
  backend, and the day-one data policy (permanence, redaction, continuity,
  identity, write-path scope), each with its "Revisit when…" triggers.
- `docs/roadmap/phase-2-scale.md` — the continuity policy and the phase-2b/2c
  trigger list (living document — edit in place as triggers fire).
- `docs/infrastructure/fly-deployment.md` — the deploy runbook and §8 launch
  window checklist.
- `docs/evaluation/2026-07-04-deep-evaluation.md` — the deep map-vs-territory
  audit (see its dated addendum for what has since shipped).
- `README.md` — concept, architecture, and the current-state matrix.
