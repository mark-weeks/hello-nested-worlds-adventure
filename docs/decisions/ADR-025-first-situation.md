# ADR-025: The signal in the gallery

**Status:** Bounded implementation of the owner's 2026-09-12 request to implement
recommendations. This records the local review build; it does not authorize
production installation or establish that the experience is compelling to people.

## Context

Generated breadth and generic repair verbs do not by themselves give a visitor
an unresolved question. The discovery/return roadmap calls for one coherent
situation, meaningful opposing interventions, an executable commitment and a
useful aftermath for late entrants. The implementation uses eight existing
seed-382 nodes across Region, Room, Object and Molecule scales. It creates no
geography and rewrites no born identity.

## Decision

An operator explicitly opens the situation with `python main.py situation --seed
382`. Re-running it returns the existing instance. The stored version-1 definition
pins nodes, clues, choices, costs and timing. Merely loading a world does not
install it. New arrivals enter the Orchard Terraces; existing saved positions and
explicit deep links take precedence. Free exploration remains available.

The Broken Ember Gallery contains an Elder River Instrument and an Amber Ember
Mechanism. An unsigned inscription questions the keeper's exclusive control.
Its maker is unknown: it is explicitly authored situation evidence, never a
fabricated earlier player's trace. An observer can read clues, a conversational
visitor can ask Tessera, and an investigator can examine both objects before
recording a preference. The clue buttons require a server-saved visit. The nearby
sealed alcove is optional and preserves its ordinary seal.

| Intervention | Benefit | Cost and shared effect |
|---|---|---|
| Preserve Tessera's control | Steady gallery light; calmer terraces | The signal remains enclosed; regional danger decreases by one, bounded at 1. |
| Release the signal | Those beyond the keeper hear it | Gallery light flickers; regional danger increases by one, bounded at 10. |

Each authenticated participant has one changeable choice after discovering both
required clues. A 60-second shared decision window begins with the first preference;
a tie extends it by another window. At its end a majority commits one branch under
the SQLite writer lock. A late request cannot replace an accepted outcome. This
revisits the proposed first-valid-commitment race for this situation only; ordinary
scale verbs retain their existing rules. The window is a review-build hypothesis,
not evidence that people have enough time or that a cohort finds it fair.

Commitment changes the regulator's `signal_control` and schedules three effects:
gallery lighting/routing immediately, terrace danger/routing 20 seconds later,
and Tessera's lasting mark in the Elder Lantern Fold after another 20 seconds.
The times are measured from settlement, and overdue work runs in order after
recovery. The promise is fulfilled by a recorded property change, not generated
speech. Unsupported interpreters or failed writes leave work pending with bounded
retry diagnostics; effect and completion commit together. Notifications happen
after commit and are recoverable by rereading state. No finite delivery deadline
is promised during an outage.

A returning participant's journal recap includes recorded material changes in
investigations they joined, alongside their saved places. A first-time late
visitor sees the chosen route and can compare the Fold and chain, then leave one
persistent shared reference marker. This does not reopen the resolved choice,
reset the world, or award a fictitious first solve. Whether that follow-up is
meaningful enough is a pilot question, not a test-suite conclusion.

## Records and ownership

Migration 0023 adds a pinned situation instance, participant choices/discoveries,
fenced pending work and one follow-up per participant. Migration 0022 receipts
make choose/follow-up retry-safe. Four append-only event kinds are introduced:
`SITUATION_OPENED`, `SITUATION_COMMITTED`, `SITUATION_CONSEQUENCE`,
`SITUATION_FOLLOWUP`. Explicit source IDs connect opening, commitment and outcome.
The chronicle adds no human/agent taxonomy. Operational clue reads, notes and
profile edits are not chronicle events.

Tessera's voice receives at most three actual public commitment records even
when recent chatter displaces them. It never receives private notes, research
observations or an inferred private allegiance. Preset profile avatars are
visible on shared profiles; live-presence avatar rendering remains later work.
No model or provider configuration changes. Offline voice silence remains valid.

## Trade-offs accepted

This is an authored instance with one interpreter, not a general quest platform.
An early participant can settle a lightly populated world before others arrive;
a tie can remain open. The short clocks test the entire chain in one session and
do not demonstrate a next-day return motive. Do not infer retention, fair rankings
or useful general crafting from a passing scripted sequence.

## Revisit when…

Pilot observations expose unclear stakes, hurried decisions, weak consequences or
an uninteresting aftermath. Tune future definitions while preserving opened
instances. Generalize authoring only after multiple useful examples. Adopt a
longer-lived commitment only with evidence about return timing and recovery.

## Rejected alternatives

- Replace born properties or privately reset the shared world for each visitor.
- Let the first HTTP response win a contested decision without a decision window.
- Promise an agent action solely through unconstrained generated speech.
- Invent a previous player or expose journals to make a narrative feel personal.
