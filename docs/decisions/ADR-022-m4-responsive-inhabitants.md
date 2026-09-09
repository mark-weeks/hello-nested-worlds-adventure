# ADR-022: Bounded attention to familiar places

**Status:** Proposed for review, 2026-09-08. Implements bounded M4 only;
ADR-013's broader proposals and M0/M5 content remain Proposed.

## Context

Discovery memory is durable, but known nodes skip action and consume no walk
budget. Heartbeat persona actions depend on fresh-discovery logs, and quiet
runs erase recent context. Reusing those logs as a retry ledger would lose
fences when the hundred-entry context window rolls over.

## Decision

Keep discovered canonical names. Separate a bounded inspection of known and
unknown places, an actual visit, and permission to attempt an action. A saved
preorder cursor advances across the born world, including inaccessible places;
it never changes topology, the pinned hinge, or the player's navigation.
Up to two recently changed familiar places precede the fair scan; at least
one visit slot remains for fair progress. The priority read examines only the
latest 64 material/renewal rows, so heavy traffic can displace a change from
that fast path. The fair cursor still covers it. An inhabitant drops into the
next inspected area; causal arrivals do not move it.

A place without an attention marker has one initial persona opportunity.
Subsequently, only a new material event with external provenance renews that opportunity. Autonomous
cast effects, including their delayed landings, do not renew it. This bounds
both self-reaction and cast-to-cast tending/decay loops. A tender tries its
scale verb, a scholar only its existing documentary verbs, a destabilizer its
existing decay event. Saturated/no-op/shared outcomes consume the opportunity
without inventing an action. Quiet familiar ground need not produce movement.

Puzzle eligibility is independent: one deterministic difficulty-weighted attempt
per current renewal epoch, successful or not. Changed properties alone do not
refund a failed attempt. Renewal changes the puzzle and attempt seed, not its
per-node difficulty. Agent payloads remain tagged for human-progress exclusion;
no co-op session, seal, or constellation is claimed. Sealed subtrees and danger
withdrawal constrain visits; withdrawal records the observed danger without
raising it again. An inhabitant already inside may still leave; a ripple is
not passage through a seal.

Inspection, actual visits, puzzle/persona attempts, origin effects and initial
queue work have separate counters and caps. Read projections batch candidate
signals and attempt markers. One tree hydration per tick supplies immutable
topology; authoritative action admission still rechecks live state. SQL history
projection has a VM-instruction budget and fails quiet if exhausted, rather
than allowing historical growth to defeat the work bound. The whole tick also
has a two-million-step SQLite progress budget, sampled
every 1,000 VM instructions. Birth is separate one-time initialization. This
is a work cutoff, not a latency SLA; busy waits and Python work are not VM
instructions. No language-model loop or new causal law is introduced.

### Persistence, restart and compatibility

Migration 0020 adds a nullable scan cursor to `agent_memory` and a small
`agent_attention` table keyed by world, inhabitant and canonical place. Each
row holds only the consumed external-event ID and puzzle epoch. An additive
partial history index supports the latest-64 priority read. Discovery and
recent context retain their existing formats. Old memory starts without a
cursor/markers: at most one initial opportunity per place is available; names
are never cleared or rewritten. The markers grow at most with cast × born places.

Attempt markers commit in the same SQLite transaction as existing acceptance,
pressure, initial work and immediate effects. A failure rolls them back; a
post-commit notification failure cannot refund them. Shared and no-op attempts
commit only the marker. A scan cursor advances independently of action success;
failed opportunities become eligible on a later circuit. Recent context retains
the last hundred actual activity entries; inspection alone creates no memory
of movement. Existing M1/M2 pending work and completion fences are unchanged.

Back up with writers stopped before upgrading. Old binaries ignore these
additions but cannot enforce this attention policy; do not mix heartbeat
versions. Prefer forward repair. A rollback to M3 preserves its known inactivity
behavior and existing delivery compatibility, but cannot promise M4 opportunity
limits while that binary runs. A stopped-writer whole-database restore with its
matching binary retains the old operational trade-off of losing intervening
history. This PR authorizes neither deployment nor restore.

## Trade-offs accepted

Fair scanning is eventual, per inhabitant's actual ticks, not a wall-clock
guarantee. Only the bounded recent-change lane expedites responses.
Discovery/memory and one topology hydration still cost
O(born places); the bounded scan does not claim constant whole-tick cost across
arbitrarily large worlds. A quiet place is allowed to stay quiet. An unrecorded
overlay edit is not an external event. Missing legacy maturation provenance
does not invent a human trigger. Failed puzzle attempts wait for renewal.

## Revisit when…

- Measured time to revisit a changed place is too long → tune the bounded
  scan or priority window, preserving fair progress and fences.
- The history projection exhausts its budget in real play → add a reviewed
  materialized signal counter; do not silently remove the work limit.
- M0 requires a specific promise or conflicting goal → review its own M5
  contract; these attention markers are not commitments or a dialogue memory.

## Rejected alternatives

- Clearing discovery memory, synthetic movement logs, or unlimited known-node walks.
- Cooldown alone: it slows a self-sustaining autonomous loop without ending it.
- A bounded recent log as a durable attempt fence, or a process-local retry map.
- Reinterpreting accepted operations, changing causal laws, regenerating worlds,
  or implementing ADR-013's broader situation proposals.
