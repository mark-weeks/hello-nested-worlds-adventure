# ADR-020: Coherent delayed scale actions

**Status:** Proposed for development-team review, 2026-09-08. These are the
bounded choices implemented by M2. ADR-013's broader situation contract remains
Proposed; M0 must define actual opposing interventions before M5 implements them.

## Context

M1 (#94, `09317c35c5d07beafe2bbe93b9233fd2fba9a8bf`) makes acceptance and
delivery atomic but preserves absolute patches. Two real HTTP kindles at density
418 promise 438 twice and land at 438. All four delayed verbs combine repeatable
repair/growth with a one-time flag. None is an exclusive intervention.

## Decision

Use the existing SQLite acceptance and per-item delivery transactions. New
delayed operations use semantics version 2 and a separate frozen interpreter;
they never call the current `Verb.effect`. Pin which components were accepted
(`adjust`, `mark`), the verb/version, due time, origin, and actor identity. A
mark-only request cannot become a growth request if circumstances later change.

| Action | Contribution at acceptance and maturity | Saturation / acceptance no-op | Shared one-time transition |
|---|---|---|---|
| attune | One stability rung: collapsing → fraying → stable, against live state at maturity. | Stable: no further repair. Unknown/missing stability: precondition no-op. | Set `attuned` if not already set. |
| calibrate | Move ratio by 0.05 toward 0.5, rounded to two decimals, only if strictly closer. | Within 0.01 or no strictly closer rounded step: no adjustment. Missing/nonfinite/out-of-range ratio: precondition no-op. | Set `calibrated` if not already set. |
| kindle | Add max(1, current density // 20), capped at 999. | Density 999: no growth. Missing/noninteger/out-of-range density: precondition no-op. | Set `kindled` if not already set. |
| align | Multiply current tilt by 0.9, rounded to one decimal, only if strictly smaller. | Tilt ≤ 0.05 or rounding plateau (e.g. 0.4 → 0.4): no adjustment. Missing/nonfinite/negative tilt: precondition no-op. | Set `aligned` if not already set. |

The flags are existing property transitions, not new situation phases. When an
adjustment is possible, each distinct request is a contribution, even if another
is pending. Its missing flag can accompany it. When **only the flag** remains,
join the earliest pending v2 operation for that node/verb carrying that flag;
otherwise accept one mark-only operation. SQLite serializes this decision.
Joining creates no new work, origin, pressure, credit, or earlier due time.
Repeated contributions remain distinct; duplicate delivery is the same queue ID
and is fenced by M1's retained completed row. HTTP request retries have no
idempotency key and remain distinct contribution requests.

Admission requires valid live inputs and an available adjustment or flag. An
already saturated/marked request returns `noop` without an origin or work row.
At landing, apply only the accepted components against current state. Valid
intervening changes are respected: no stale absolute overwrite. Invalid live
inputs close the operation as `precondition_changed`; saturation or an already
set flag closes it as `already_satisfied`. These are explicit terminal no-ops,
with an existing `SCALE_ACT_MATURED` history row, no material delta/version, and
in-fiction explanation. Applied work records only the actual delta. Acceptance
does not reserve capacity or guarantee a numerical result; racing contributions
can saturate before later ones arrive. No-op maturation adds no extra ripple.

Both clients receive pending summaries on authoritative reads, personal
acceptance flavor with an approximate wait, and terminal history/notification
flavor. Shared responses use the existing outcome's remaining due time, never a
fresh full wait. Public summaries group by node/verb across versions; two legacy
and new pending rows count as two changes, without collapsing either row.
No private queue payload, credential hash, or diagnostic error is exposed.
Broadcasts stay outside transactions; reload recovers missed notifications.

`GET /node` resolves one canonical born node and reads its live properties,
pressure, activity and pending summary. It is gated and read-rate-limited like
`/world`, but omits topology and transient renderer IDs. Both clients retain
their existing passages and selection. A late act/read response cannot navigate
back or write another place's response panel. Socket notices refresh shared
state without clearing personal interaction text; acceptance broadcasts omit
second-person flavor. Terminal narration remains in the shared feed/history.

The acceptance response and broadcast expose the same existing origin event ID.
A bounded client cache (128 events) coalesces the redundant authoritative read
for an HTTP response and its socket echo. Landing work IDs use a separate phase;
shared/no-op responses still read fresh state. This is read deduplication only:
it does not turn another act request into the same accepted contribution.
Older overlapping reads cannot replace a newer response, and failed reads are
retryable. Notifications remain best-effort; a page reload recovers missed ones.

Immediate verbs (including the zero-delay override) first check live state
without reserving SQLite's writer lock. An observational no-op returns there;
an intended change re-reads and rechecks inside M1's atomic acceptance boundary.
Delayed admission, including saturation and shared-outcome selection, remains
serialized under the writer lock.

### Exclusive interventions: future contract only

Recommend first valid commitment wins within an authored situation instance:
atomically validate phase/preconditions and reserve one branch; same-branch
requests join its existing outcome, incompatible requests are explicitly
declined before acceptance. Once committed, never switch branches by overwriting
pending work. If changed circumstances invalidate it, record an explicit failed
closure and explain whether a new choice is available. Define cancellation,
coordination window, late-arrival role and narrative stakes in M0; adopting any
of these for real content requires M5 review. No generic conflict engine,
artificial exclusive action, or situation instance is added here.

### Compatibility and operations

Migration 0019 adds an operation JSON column and actor-identity column with null
defaults plus a pending lookup index. It rewrites no old payload or history.
The default enqueue API remains v1. Legacy absolute maturation patches (including
identical distinct patches), causal pre-law strength and `_hop` law behavior,
completed deduplication fences and stored historical deltas retain their M1
interpretation. V1 and v2 pending work can coexist; legacy patches can still
overwrite newer changes because that was their accepted meaning. V2 mark-only
coalescing never joins or collapses legacy work. Unknown versions/operations
remain pending with diagnostic backoff, never run through a fallback effect.

Stop all writers and take a whole-database backup before upgrade. Mixed M1/M2
workers are unsupported: M1 cannot deliver v2 and can still accept stale v1
patches; pre-M1 workers can also consume completed rows. Restart only compatible
workers and check pending/terminal counts. Preserve both interpreters in future
releases. Binary rollback requires stopped writers and the matching pre-upgrade
database/binary, abandoning any intervening history; prefer forward repair once
play continues. No in-place downgrade or deployment is authorized by this PR.

## Trade-offs accepted

Live contributions retain the original tuning rather than reserve a fixed
benefit at acceptance. This permits explicit no-ops under saturation and avoids
undoing intervening changes. Shared flags avoid promising repeated one-time
transitions but confer no participant credit or durable join roster. Admission
is bounded by existing HTTP pacing and cast tick budgets; this is not a new
resource economy or global contribution quota. CLI remains operator-paced.
Frozen v2 arithmetic costs a small amount of deliberate duplication; future
tuning must add another interpreter rather than changing accepted work.

## Revisit when…

- M0 identifies an actual incompatible choice: review its commitment rule and
  outcomes before M5 adds persistence or content.
- Saturated attempts or numerical plateaus harm play: version a new opportunity
  or tuning policy; do not silently retune queued v2 work.
- Reliable HTTP retries or participant credit become necessary: add explicit
  request identity or participation semantics, distinct from delivery identity.
- Measured contention or pending volume grows: optimize the bounded SQLite
  queries before considering another delivery system.

## Rejected alternatives

- Recompute with the latest verb function despite a version column.
- Convert/collapse legacy patches, reserve stale absolute outcomes for v2, or
  claim every accepted attempt guarantees growth despite saturation.
- Treat all attunements as one permanent action: its existing repair rungs are
  repeatable contributions; only its flag is a one-time transition.
- General situation engine, new geography, inventory, identity or rankings.
