# ADR-007: One Shared Canonical World at Launch

**Status:** Accepted 2026-08-03 — ratified by the project owner

---

## Context

The project's social premise is cumulative co-presence: humans and agents
affect one another directly through chat, encounters, and shared puzzles, and
indirectly through remembered speech, causal changes, artifacts, and the
chronicle. Those effects become meaningful because every participant inherits
the same past and changes the same place.

The implementation still exposed a seed input in both browser clients and
accepted arbitrary seeds on HTTP and WebSocket routes. Since ADR-006 made each
seed a lazily materialized, persistent world, entering a new number was no
longer a harmless procedural preview: it permanently birthed a parallel world
with a separate room, history, state, puzzles, agents, and heartbeat activity.
That fractures the population and defeats the interaction premise before
cohort size or retention can be measured honestly.

## Decision

The initial hosted release contains **one shared canonical world**.

- The operator chooses it once with `NESTED_WORLDS_CANONICAL_SEED`; committed
  launch configuration selects seed 382, the top-scoring candidate in the
  pre-launch 512-seed quality census (`docs/evaluation/2026-08-03-launch-world-census.md`).
- When the setting is absent, the server fails closed to seed 382. Empty,
  `off`, or `none` explicitly enables multi-world mode for local development
  and tests only.
- Every public seed-bearing boundary — REST reads, REST writes, SSE,
  WebSocket join, saved-position restore, autonomous heartbeat selection, and
  the background causal/maturation queues — resolves or filters through the
  same boundary. A missing seed selects the canonical world; the matching seed
  is accepted for old-client compatibility; a mismatch is rejected before
  lookup or materialization. Queued work from a local alternate world remains
  durable but paused on a canonical deployment.
- `/worlds` and saved-position reads expose only canonical-world state when the
  boundary is active. A stale position from another development world cannot
  redirect a hosted client.
- Neither browser client offers seed or breadth selection. View depth remains
  a presentation choice: every depth is a prefix view of the same materialized
  world. Clients learn the canonical seed from `/world` and carry it only as
  internal identity for subsequent requests, deterministic art, and sound.
- CLI seed selection remains available for operator curation, generator
  evaluation, and isolated local development. It is not a player-facing hosted
  capability.

## Consequences

- All launch players and autonomous agents accumulate one history and can
  encounter one another's consequences.
- A request cannot accidentally or maliciously birth a durable parallel world.
- Selecting the final launch seed is now an explicit content-curation and
  operations decision. Changing the configured seed after launch does not
  transform the world; it points the service at another persistent world and
  therefore requires a new ADR and migration/continuity plan.
- Existing multi-seed storage and generator flexibility are retained instead
  of destructively deleting development worlds.
- Horizontal scale must preserve this logical shared-world boundary and solve
  room coordination separately; it must not shard players by giving them
  different seeds.

## Rejected alternatives

- **Player-created worlds.** Rejected for launch because they fragment every
  interaction and persistence loop the project is designed to compound.
- **Hide the seed input but trust clients.** Rejected because old or custom
  clients could still materialize parallel worlds.
- **Hard-code 42 throughout the codebase.** Rejected because the final launch
  world still needs pre-launch curation and staging without a code change.
- **Delete all noncanonical stored worlds.** Rejected as destructive and
  unnecessary; the public boundary is sufficient, while local evaluation
  still benefits from reproducible alternate seeds.

## Revisit when…

- the project intentionally introduces a second communal realm with a designed
  relationship to the first, population thresholds, traversal semantics, and
  a continuity plan; or
- a staging/preview environment needs a separate canonical seed (configure one
  per deployment; do not enable player selection).
