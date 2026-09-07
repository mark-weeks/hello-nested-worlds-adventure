# ADR-013: Versioned Situations and Reliable Consequences

**Status:** Proposed implementation contract, 2026-09-07. Preservation of the
shared world is endorsed product direction; transaction design, migrations, and
new event kinds require review in their implementing PRs. No runtime behavior
or persistent write path is introduced by this document.

## Context

ADR-006 materialized world identity; ADR-009 records actual material deltas.
The [assessment](../evaluation/2026-09-07-concept-and-implementation.md)
demonstrated a failure window between deleting queued work and applying it,
and overlapping delayed actions that overwrite with stale absolute outcomes.
Neither fix requires regenerating the world. Both matter before new situations
depend on durable, delayed consequences.

ADR-006's evolution-mechanics trigger now applies. Define the minimum contract
needed by ADR-012's experience, preserving earlier decisions and existing work.

## Decision

### Preserve identity and introduce change as recorded events

- Keep the canonical world, born node rows, canonical names, pinned hinge,
  and past deltas intact. Situation state and material changes use additive
  storage and explicit events, not edits to birth properties.
- Identify a situation instance, its definition version, affected existing
  nodes, current phase, source cause, preconditions, and allowed transitions.
  Record the actual outcome and delta when a transition lands.
- Start with operator-authored definitions and rule-governed transitions.
  A language model may propose text or an allowed action, not invent persistent
  canon, grant permissions, or execute arbitrary state changes.
- Do not add renames, reparenting, new scales, era-bank changes, or new geography
  to this first contract. Those still need their own continuity decisions.

### Make accepted work recoverable

- Give work a durable identity and distinguish acceptance, pending work, and
  a recorded terminal outcome. Accepting an action and scheduling its initial
  work must not leave an unrecorded failure gap.
- Commit effects, their historical deltas, and required continuation work
  atomically wherever they share the database boundary. A claim alone must
  never acknowledge successful application.
- Where work spans transactions, use recoverable claims and idempotent retry.
  Reclaim interrupted work; do not silently discard it after an exception or
  retry limit. Isolate a persistently failing item with an observable outcome.
- Keep external calls and client broadcasting outside database transactions.
  Clients must recover authoritative state after a missed notification; a
  successful transport send is not the commit point for the world.
- Retain SQLite. Choose exact transaction boundaries, claim representation,
  retry policy, and ordering through failure tests before adding a broker.
  The required outcome is no lost accepted work and no duplicated material
  effect under the tested failure model, not an unqualified transport guarantee.

### Declare action semantics by type

| Type | Acceptance and landing rule |
|---|---|
| Contribution, such as repeated growth or tending | Each distinct accepted contribution runs once against current state at maturity under its pinned operation version. Bound opportunities and define saturation; report an explicit no-op if preconditions no longer permit a change. |
| One-time transition | Expose one shared pending outcome. Joining it is a contribution only if a defined rule gives that contribution meaning; do not promise a second transition. |
| Mutually exclusive intervention | Define an explicit commitment/coordination rule for the situation. Reject or explain incompatible requests before implying acceptance; never rely on accidental last-writer-wins behavior. |

Legacy pending absolute outcomes must retain an explicit legacy interpretation
or complete under a tested transition plan. Do not silently reinterpret them
as newly composable operations. A handler guard fix needs endpoint tests; the
assessment's direct queue probe may legitimately keep its old observation.

### Preserve active work across a rule update

- Pin active puzzle/situation identity, content, rules, accepted-answer policy,
  and necessary evidence references. Answers stay server-side. New instances
  can use a new version while existing work remains resolvable.
- Pin the rule interpretation needed by pending actions and causal work,
  including applicable law semantics. Alternatively drain old work under its
  old rules before switching; do not let deployment timing choose its meaning.
- If changing circumstances make an active task impossible, retain accessible
  evidence or record an explicit closure/transition. Do not silently change its
  answer, erase contributions, or count closure as a successful solve.
- History reconstruction continues to fold stored deltas, never execute a
  newer effects function. Corrections use explicit compensating events.

## Trade-offs accepted

Version compatibility and recoverable delivery add state to maintain, but keep
updates from breaking promises made to players. Keeping the first grammar
limited to existing places avoids premature topology and general authoring tools.
Condition-driven phases give the world life without requiring every absence to
produce damage or every deploy to add an entirely new location.

## Revisit when…

- Two or more successful situations expose a repeated transition pattern:
  extract the smallest reusable authoring support.
- Multiple processes or measured contention require new coordination:
  reconsider the delivery mechanism using observed load and recovery needs.
- Old versions become costly to retain: design a visible retirement/migration
  policy that preserves active work before removing their interpreter.

## Rejected alternatives

- Delete-on-claim followed by application: permanently loses interrupted work.
- Silent coalescing or stale absolute overwrites as a universal action policy.
- Replaying current rules to reconstruct old state, rewriting born rows, or
  rebuilding the shared world to simplify content releases.
- An external queue or unrestricted evolution engine before bounded tests
  establish that the existing database cannot satisfy the contract.
