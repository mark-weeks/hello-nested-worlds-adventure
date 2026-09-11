# Working in Enfolded

Enfolded is a persistent multiverse inhabited by human players and agents. The
covenants below define correctness across agents and models. Use the referenced code
and decisions for the area being changed; unrelated work does not require a full
roadmap, CHANGELOG, or ADR review.

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

**The hosted launch is one shared canonical world** (ADR-007, ratified
2026-08-03). `NESTED_WORLDS_CANONICAL_SEED` is an operator-owned deployment
choice; every HTTP, SSE, WebSocket, position, and heartbeat path must stay
behind `server.guard.world_seed`, and browser clients must not expose seed
selection. The CLI and explicit local multi-world mode remain available for
curation and tests. Never turn a player-controlled integer into a new durable
world: under the materialized store, that is a permanent parallel history, not
a harmless view option.

- **A born world is never re-born.** `birth_world` is idempotent and
  `persistence.save_world_nodes` refuses to overwrite — nothing in
  application code may regenerate or rewrite `world_nodes` rows for a seed
  that has them. Existing state changes use overlays and chronicled deltas
  (ADR-009); they do not rewrite birth identity. The broader evolution grammar
  remains ADR-gated (ADR-006 "Revisit when", ADR-013). Any code path that would
  mutate a stored node's name/level/base properties is a bug.
- **The wrap hinge is pinned, not computed** (ADR-008, ratified at the
  batch-2 merge gate). The traversal loop's one root-ascent landing is
  selected once per world by a seed-pure rule (`multiverse/wrap.py`,
  constrained to a fully unsealed lineage — the liveness invariant) and
  pinned write-once in `world_meta` (migration 0015). From then on THE
  STORED HINGE IS THE HINGE: editing the selector changes what future
  worlds pin, never where an existing world's monument stands — enforced
  by `persistence.pin_world_meta` (no update/delete exists) and pinned by
  `tests/test_wrap_passage.py::TestSelectorEditImmunity`. Moving a pinned
  hinge is an ADR-level continuity decision. The loop itself lives in the
  traversal layer only: parent links stay a tree, causality does not wrap.
- **Content banks govern births only.** Editing `multiverse/generator.py`
  banks cannot touch any world that already exists — pinned by
  `tests/test_world_store.py::TestBankEditImmunity`. A bank edit changes
  what NEW worlds are born as: bump `GENERATOR_VERSION`
  (`multiverse/store.py`) for meaningful generator changes and consciously
  re-pin the golden digests, recording why in the CHANGELOG.
- **The golden pins now describe births.** `tests/test_continuity_freeze.py`
  (both depths — the depth-6 reference world AND the full 11-level world;
  five scales exist only below depth 6) pins what generator v2 births. A
  failing pin no longer means "you are rewriting the permanent world" — the
  store forbids that — it means "you changed what new worlds are born as":
  establish intent from the request and existing ratification, bump the version,
  and re-pin deliberately. Accidental birth changes require a code fix.
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
current `GENERATOR_VERSION`: the semantic name allocation, properties, and
breadth use separate keyed deterministic domains, so a fresh install birthing a reference seed
reproduces it exactly, and any depth view is a true prefix of the one stored
full-depth world. **After birth**, the stored row is authoritative, and
art/sound/puzzles derive deterministically from the node *as served* — so
co-op reproducibility and reproducible screenshots follow the served state.
Consequences:

- No `Math.random()`, `Date.now()`, `time.time()`, or other wall-clock/entropy
  in generation, art, sound, or puzzle-selection code paths.
- Worlds must generate identically under the pinned interpreter — **Python
  3.11** (Dockerfile and CI both pin it; the freeze pins police this).
- **Wayback reconstructs state; it never replays effects.** Historical
  properties are the born row plus stored RFC 7396 deltas in node-version
  order; pressure and wear fold through the same event cursor. The state is
  historical, but art and sound are today's deterministic interpretation —
  renderer changes reinterpret the past and must never be presented as
  period playback. `docs/decisions/ADR-011-wayback-surface.md`.

---

## Verification and completion

- Complete the requested deliverable: advice or a plan ends with findings or decisions;
  a requested draft ends with a reviewable artifact and known gaps. Neither authorizes
  implementation or publication. Authorized implementation continues through the checks
  and corrections below; report exact blockers and finish independent work.
- For code changes, use behavior tests that exercise the affected endpoint, generator,
  prompt, or client; string-presence checks cannot verify these behaviors. Preserve puzzle
  answer secrecy, solvability, per-node difficulty, continuity, causal equivalence, and restart/co-op.
- Bootstrap the pinned Python 3.11 / Node 20 environment with `./setup.sh`. Use focused
  checks during iteration; run
  `./scripts/check.sh` before proposing merge. Its required Ruff, Python/Vitest, frontend
  build and bundle-freshness, and installed-wheel gates remain unchanged. Set
  `ENFOLDED_E2E=1` to include Playwright after installing Chromium.
- Finish requested implementation and relevant verification, inspect user-visible
  behavior when applicable, and fix failures introduced by the change. Re-run affected
  checks after fixes; do not repeat a passed full suite without a changed basis.
- Each change batch needs one measured `docs/CHANGELOG.md` entry. Record actual checks
  and unavailable verification honestly. Documentation-only work can finish with document
  validation; the canonical gate still applies before proposing merge.
- Produce the diff-based irreversibility check for the CHANGELOG and any PR. A tripped
  door retains the human gate; green tests alone are not approval. Existing approval of
  the same decision need not be requested again. Ask only about consequential unresolved
  scope, architecture, ownership, security, or irreversible decisions; block only dependent work.
- Prepare PRs for development-team review when publication is authorized. **Never enable
  auto-merge. Merge only on the owner's explicit instruction for that PR; authorization
  for one PR does not carry to another.** Deployment and other external changes require
  their own authorization; completion criteria do not supply it.

## Read when relevant

- **CHANGELOG or PR preparation:** `.claude/skills/changelog-entry/SKILL.md` and
  `.claude/skills/irreversibility-check/SKILL.md`. The latter defines every one-way-door
  check and the scoped human questions. Use the actual diff; ordinary edits do not require
  repeatedly running the merge procedure.
- **Intentional generator re-pin:** `.claude/skills/repin-goldens/SKILL.md`. Human
  ratification, both-depth coverage, and frozen era names remain required.
- **Architecture or continuity decision:** the applicable `docs/decisions/` ADR and its
  revisit triggers. New decisions use Context / Decision / Trade-offs accepted /
  Revisit when / Rejected alternatives. Resolve unsettled architectural questions before
  building; an already settled decision does not require another interview.
- **Discovery/return product work:** `docs/roadmap/discovery-and-return.md` for dependencies,
  acceptance gates, and the separate puzzle and speech tracks; ADR-012 through ADR-018
  for the relevant direction. Respect each record's status, including ADR-013's broader
  proposed contracts and ADR-018's exploratory proposal. Plans are not shipped capabilities;
  existing write-path and client-default gates still apply.
- **Delivery, delayed actions, history narration, or inhabitant attention:** ADR-019 through
  ADR-022 for the affected implementation and acceptance evidence. Preserve queue-version
  compatibility, atomic effect/completion fences, evidence-bound narration, and discovery memory.
- **Voice, model, or prompt caching:** `docs/development/agent-runtime.md`.
- **External contract change:** verify affected API/config/protocol assumptions against
  current official docs or a live run before implementation (including Anthropic, fly.io,
  CSP, WebSocket, and PixiJS contracts). Keep the check limited to the changed interface.
- **Deployment or launch work:** `docs/infrastructure/fly-deployment.md` (including §8),
  `docs/roadmap/pre-launch-window.md`, and the relevant continuity policy in
  `docs/roadmap/phase-2-scale.md`. Backups and deployment gates remain mandatory.
- **Substantial audit driving a batch:** record it in `docs/evaluation/YYYY-MM-DD-<name>.md`
  in that batch; read historical evaluations only when they inform the current question.

The SessionStart hook in `.claude/settings.json` handles remote toolchain bootstrap;
inspect `.claude/hooks/session-start.sh` when changing that behavior. When changing a
working rule, update its matching skill and PR template so the instructions agree.
