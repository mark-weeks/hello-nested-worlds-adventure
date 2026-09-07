# Enfolded: concept, implementation, and the path to a compelling game

**Assessment date:** September 7, 2026. **Reviewed revision:** `87a7cf24bba67505c11aaf4c19a2f562db3d4289`, verified against GitHub `main`; no open PRs at verification. This is an evaluation and proposed direction, not a ratified design decision or implementation change.

## Recommendation

Keep the core architecture. Concentrate the next development cycle on a small, authored chain of discoveries that makes persistence, cross-scale consequences, and other presences matter to the player. Prove that experience before expanding the world or adding more general-purpose systems.

Enfolded has built much of the machinery its concept needs. Its weakest layer is turning that machinery into situations players care about. The recurring gap is between **something changed** and **something I understand and care about changed because of what I did**. More nodes, longer history, richer prose, and additional puzzle variants will not reliably close that gap by themselves.

The assumption that launch broadly freezes development is outdated. ADR-006 already replaced regeneration at runtime with a stored world; ADR-009 records material changes as historical deltas. Those were good decisions. What remains missing is a controlled way to introduce new situations and evolve existing content while preserving identity, history, and work already in progress.

I would position the next playable version as **a shared mystery world where you learn how places affect one another, intervene, and encounter the consequences later**. That is a proposed focus within the existing vision. Quiet observation and conversation remain valid ways to participate.

## Evidence and limits

The assessment combines the README, game design, ADRs, roadmap, earlier evaluations, direct implementation inspection, existing tests, and new bounded probes. Earlier evaluations were treated as historical context and their assertions were checked against current code.

- **908 Python tests passed**, in 80.63 seconds, using Python 3.11.15. An initial restricted run hit local socket permissions; the full run passed with local socket access. All tests used isolated databases.
- **95 Vitest tests passed** across nine files; this supplemental run used the installed Node 24.2.0, not the repository's pinned Node 20. Ruff passed. This was not a fresh execution of the full canonical build/wheel/Playwright release gate.
- World census passed: **4,208 nodes**, 100% readable and unique names under its checks. Puzzle ecology passed: **4,208 puzzles**, 65.61% classified as world-reading, 33.72% decode, 99.90% unique prompts, 54.06% unique answers; largest family 19.94%.
- Inspected both `/` and `/app` in a fresh local seed-382 database. Entered as `AuditVisitor`, inspected the arrival puzzle, seeded a planet, and examined the resulting presentation and history. This was one sampled entry, not a user study.
- Live AI and external images were disabled for that walkthrough; ambient heartbeat was disabled to keep the opening reproducible, while the causal pump ran. Therefore an empty cast in that walkthrough is not evidence of normal production inactivity. Live voice quality, latency, and the added value of generated images were **not evaluated**. The agent findings below come from code and separate executable probes.
- No existing player database, production environment, or QA history was changed. There is no measured retention result here. Claims about player motivation are design hypotheses informed by the user's experience and the inspected mechanics.

Reproduction materials: [portable probes](2026-09-07-concept-and-implementation/probes.py), [measured baseline results](2026-09-07-concept-and-implementation/probes.json), and [verification record](2026-09-07-concept-and-implementation/verification.md).

Run from the repository root:

```bash
.venv/bin/python docs/evaluation/2026-09-07-concept-and-implementation/probes.py
```

The probes create and remove their own temporary databases, make no network calls, and print observations rather than asserting that the defects should persist. The baseline JSON is dated evidence, not a regression-test golden. Subsequent fixes should change the relevant observations; add regression tests for the desired behavior in their implementation PRs.

## Alignment with the vision

| Intended experience | What is implemented | Assessment |
|---|---|---|
| Places persist and remember | Materialized nodes, append-only mutations, property deltas, conversations, resume, Wayback | Strong foundation. Memory needs relevance, retrieval, and consequences to become attachment. |
| Every scale changes your perspective | Eleven content registers, art/sound families, one verb per scale, nesting puzzles, universe laws, wrap passage | Strong identity and flavor. Most action outcomes have limited strategic differentiation. |
| My actions matter elsewhere | Staged cascades, pressure, effects, constellations, entanglement | Real but uneven. Scale verbs affect substance at their origin; their remote effects are pressure/history. |
| Other inhabitants have lives and intentions | Recurring cast, personalities, memory, FSM traversal, banter, voice | Convincing ingredients. Persistent projects, changed-place revisits, and conversation-driven commitments are missing. |
| Discovery continually deepens | Renewable puzzles, accumulating history, evolving properties and senses | Existing renewal varies familiar mechanics. No general situation/content evolution path exists. |
| Entry immediately invites participation | Intro, deterministic drop-in, navigation, guide, sound invitation, two clients | The player is given tools and a place; a compelling question or situation is not reliably provided. |

The game design document also needs reconciliation with the accepted architecture: it still describes a conceptually infinite, lazily rendered world and a point-and-click scene as the primary interaction. The hosted world is fully materialized at birth, finite, and entered through the D3 explorer by default. ADR-008 closes traversal into a loop; it does not create new content. These are valid choices, but the product specification should state one current promise.

## Decisions worth retaining

**World-as-data and historical deltas.** The stored identity prevents content-bank edits from silently severing memory. Historical properties are reconstructed from recorded results rather than rerunning today's effects. This is the right foundation for a world that can change. The bank-edit immunity and historical-fold tests passed in this evaluation. [Store](https://github.com/mark-weeks/hello-nested-worlds-adventure/blob/87a7cf24bba67505c11aaf4c19a2f562db3d4289/multiverse/store.py#L82), [delta writes](https://github.com/mark-weeks/hello-nested-worlds-adventure/blob/87a7cf24bba67505c11aaf4c19a2f562db3d4289/persistence/__init__.py#L937).

**Server-owned rules and bounded AI.** Keeping puzzle answers, authoritative effects, and shared state on the server protects coherence. Using deterministic agents for routine activity makes ambient life affordable and reproducible. The next step is to give them better behavior and grounded context; switching every agent to an open-ended LLM loop is unnecessary.

**Generative senses tied to state.** Shared local art and sound give the world an identity independent of paid image generation. Wayback can become a powerful tool for investigation. Its value will increase when historical differences help a player solve something or understand a relationship.

**Scale-specific interaction and asynchronous co-presence.** Seals, constellations, causal prediction, and entanglement are useful foundations for discoveries particular to Enfolded. A shared world that works without simultaneous players fits a small cohort. Traces can carry the social experience when real-time density is low.

**SQLite and a modest deployment shape.** Nothing observed justifies a database or platform rewrite to solve the current product problem. Maintain backups, continuity tests, and operational limits. Revisit scaling infrastructure when measured load warrants it.

## Where the experience is under-developed

### 1. The opening gives instructions before it gives a reason to act

The sampled entry landed on Quiet Moon World. Its first puzzle was a four-star Ancestral Compass requiring properties from a Universe and Galaxy. The difficulty was legitimate under the per-node contract, but the entry selector does not optimize for an understandable first discovery. The player has to invent their own purpose while also learning navigation and terminology. [Entry selection](https://github.com/mark-weeks/hello-nested-worlds-adventure/blob/87a7cf24bba67505c11aaf4c19a2f562db3d4289/static/clientlogic.js#L32).

Preserve non-linear exploration and difficulty by node. Choose first-entry locations with a legible nearby situation, offer progressive clues, and let players leave immediately if they prefer. A shared-world start can be curated without becoming a mandatory tutorial or a separate private world.

The default desktop explorer devotes most of the screen to a tree of places; the scene client gives more space to the place itself but still leads its sidebar with a property table. Both communicate the simulation more clearly than the immediate opportunity. Elevate a short description of what is unusual here, one useful clue, and the next available intervention. Keep the map and detailed properties accessible.

### 2. Actions rarely require a meaningful choice

One click on the barren planet created 10,000 lives, followed by a strong authored line. The implementation changes `inhabited` and `population`; it does not thereby create inhabitants with needs, a new relationship, a new passage, or a new local problem. This is a large fictional promise carried by a small mechanical consequence. [Planet action](https://github.com/mark-weeks/hello-nested-worlds-adventure/blob/87a7cf24bba67505c11aaf4c19a2f562db3d4289/multiverse/verbs.py#L166).

Most verbs have a single desirable direction and no resource, competing outcome, dependency, or persistent commitment attached. Some saturate; inscriptions count upward, and population can keep growing. The question is often whether to click again, rather than what kind of outcome to pursue.

Introduce a few situations with distinct interventions and legible consequences. A player might stabilize a signal immediately, redirect it to protect a neighboring place, or preserve it long enough to learn something. Meaningful choice can come from curiosity and competing values; it does not require combat, punishment, or an elaborate economy.

### 3. Causality needs more specific relationships

The engine propagates event kinds along ancestors and descendants. It does not generally model a particular object's function in a room or a population's effect on its region. Upward propagation also does not automatically turn around into sibling branches. Universe laws change how events travel, but only certain event kinds change material properties above the effect threshold. [Effects](https://github.com/mark-weeks/hello-nested-worlds-adventure/blob/87a7cf24bba67505c11aaf4c19a2f562db3d4289/multiverse/effects.py#L42), [routing](https://github.com/mark-weeks/hello-nested-worlds-adventure/blob/87a7cf24bba67505c11aaf4c19a2f562db3d4289/causality/__init__.py#L99).

The executable mend probe repaired Elder River Instrument from damaged to worn and fired **16 propagated events**, producing **17 chronicle rows**. Only **one node changed material properties**. This is intentional for `SCALE_ACT`, and remote pressure can change the sensory presentation. Nevertheless, it is substantially narrower than the player expectation that repairing something small can change what happens at a larger scale.

Add a small authored dependency layer above the existing propagation engine: this instrument sustains that room's signal; that room influences this region's phenomenon. Give the player evidence for the relationship and a way to test it. Keep generic ripples as ambient feedback; use specific relationships to carry the important discoveries.

### 4. Memory is durable but only shallowly selected

Node speech receives the latest ten local history rows and the latest three exchanges with that speaker. Agent voice receives local history, known-place memory, and recent movements; it does not receive a portable per-player relationship transcript. An agent conversation is stored locally, but it does not create a goal the agent will subsequently pursue. [History retrieval](https://github.com/mark-weeks/hello-nested-worlds-adventure/blob/87a7cf24bba67505c11aaf4c19a2f562db3d4289/persistence/__init__.py#L455), [node speech](https://github.com/mark-weeks/hello-nested-worlds-adventure/blob/87a7cf24bba67505c11aaf4c19a2f562db3d4289/consciousness/__init__.py#L1016), [agent speech](https://github.com/mark-weeks/hello-nested-worlds-adventure/blob/87a7cf24bba67505c11aaf4c19a2f562db3d4289/consciousness/__init__.py#L1149).

The result is persistent records with limited durable significance. Important older moments can leave the prompt while recent routine events occupy it. An NPC can discuss a situation without acquiring a mechanical obligation from the conversation.

Keep the ledger authoritative. Add small, inspectable memories of salient events and explicit commitments, each linked to its source rows. Retrieve by current place, relationship, and unresolved situation. Summaries should remain rebuildable interpretations; they should not silently rewrite history. Let an agent accept only commitments the rules engine can actually execute.

### 5. Progress and return need a personal thread

Global solves and permanent constellations make shared history real. They also allow earlier players to finish content before later players arrive. Renewal reopens challenges, but repeating a puzzle family after entropy is not automatically a new reason to care.

Give players a lightweight journal of places, questions, contributions, and pending consequences. On return, show a few changes connected to those interests, with evidence and a destination. Preserve opportunities to understand past discoveries and contribute to their consequences even after the original solution is known. Offer optional shared investigations to concentrate a small cohort, while keeping progress possible asynchronously.

## What is over-developed relative to current player value

- **Parallel presentation surfaces.** Two browser clients plus the CLI multiply integration and parity work. Shared helpers mitigate this, but the product still has two front doors and repeated interaction work. Choose one player surface to develop through the next experience slice; keep the other useful for inspection and support. Promote the scene client only after validating navigation, accessibility, and the target devices.
- **Breadth before a memorable place.** Eleven scales and 4,208 puzzles offer many combinations. The ecology gate is useful, but classification as “world-reading” includes reading and transforming properties; it does not measure investigative depth. Additional name banks or prompt uniqueness are unlikely to be the highest-value next investment.
- **Technical preservation ahead of experiential use.** Wayback, full history, and careful invariants have value because permanence is central to the concept. Further archive sophistication should now serve actual discoveries. There is enough foundation to test whether players care about a changed place.
- **Custom transport and large modules.** The bespoke HTTP/WebSocket stack and large persistence/handler modules impose maintenance costs. Avoid a wholesale rewrite now. Isolate domain changes behind existing seams and use a framework migration only when reliability, throughput, or development friction provides a concrete reason.

The issue is allocation, not that these systems should be removed. The next slice should consume what already exists.

## Concrete implementation findings

These are narrower than the product hypotheses above and are reproducible at the reviewed revision.

### Critical: claimed delayed work can be lost before application

Both due-work APIs use `DELETE … RETURNING` and commit the removal before their callers apply the consequence. Atomic claiming prevents duplicate claims; it does not guarantee successful delivery. A failure during hydration or application can permanently lose the claimed batch. [Causal claim](https://github.com/mark-weeks/hello-nested-worlds-adventure/blob/87a7cf24bba67505c11aaf4c19a2f562db3d4289/persistence/__init__.py#L293), [maturation claim](https://github.com/mark-weeks/hello-nested-worlds-adventure/blob/87a7cf24bba67505c11aaf4c19a2f562db3d4289/persistence/__init__.py#L345), [drain](https://github.com/mark-weeks/hello-nested-worlds-adventure/blob/87a7cf24bba67505c11aaf4c19a2f562db3d4289/causality/staging.py#L94).

The probes enqueue one due item, inject a failure immediately after claim, then retry normally. Both queues end empty, with **zero corresponding history rows and zero work recovered**. This establishes a crash/failure window; it is not a claim that routine restarts always lose queued work.

**Fix before permanent play:** durable claim/acknowledgment or an equivalent transactional design, stable work IDs, idempotent application, and atomic continuation scheduling. Repeated delivery must neither lose nor duplicate effects. Also examine the separate origin-event and initial-enqueue transactions as part of the same delivery contract.

### Material: the recurring cast exhausts its ability to act

Known nodes are traversed without re-acting or logging. `_persona_act` selects from that run's log, so revisiting familiar ground cannot produce tending or destabilization. State changes do not invalidate this skip. The agent's recent movement log is then overwritten with an empty run. [Traversal](https://github.com/mark-weeks/hello-nested-worlds-adventure/blob/87a7cf24bba67505c11aaf4c19a2f562db3d4289/agents/agent.py#L151), [persona acts](https://github.com/mark-weeks/hello-nested-worlds-adventure/blob/87a7cf24bba67505c11aaf4c19a2f562db3d4289/server/heartbeat.py#L130).

With every recurring agent's memory populated with the 4,208 stored names, **12 heartbeat ticks produced zero fresh visits, zero persona acts, and zero new chronicle rows**. A separate known-but-corrupted subtree also produced no traversal or causal events. This is a constructed terminal-state test, not a prediction of the number of days until production reaches it. Saturation may happen locally before the entire world is known.

**Fix before relying on unattended life:** separate “has discovered” from “should revisit”; budget total actions as well as new discoveries; revisit changed, relevant, or personally important places. Model pending intentions independently of a fresh-visit log. Keep memory rather than clearing it to restore motion. Agent puzzle attempts should also use the current renewal epoch; `_attempt_puzzle` currently builds epoch zero.

### Material: delayed actions store stale absolute outcomes

Two kindles scheduled against a galaxy with star density **418** both queue the absolute result **438**. Both later land, but the final density is **438**; sequentially applying the two intended increases would yield **459**. The queued data stores a destination state, not a composable operation. [Action scheduling](https://github.com/mark-weeks/hello-nested-worlds-adventure/blob/87a7cf24bba67505c11aaf4c19a2f562db3d4289/server/handlers.py#L1235), [landing](https://github.com/mark-weeks/hello-nested-worlds-adventure/blob/87a7cf24bba67505c11aaf4c19a2f562db3d4289/server/heartbeat.py#L408).

**Decide and implement explicit semantics:** either each accepted intervention contributes at maturity, or pending work deliberately coalesces and the UI explains that. For contributing actions, store a versioned operation or contribution and compute its result atomically against current state when it lands. For coalescing actions, expose pending state and avoid promising an additional contribution. Historical landed deltas can remain intact under either choice.

### Material: history narration turns echoes into actions

After the browser's planet-seeding action, the scene client's recent history included “someone chose to seed at Elder Reed Cosmos” and equivalent lines for objects. These are propagated `SCALE_ACT` rows, not actions performed at those places. `mutationLine` ignores `_origin` and `data.actor`, so the narrator loses both causal direction and attribution. [Narration](https://github.com/mark-weeks/hello-nested-worlds-adventure/blob/87a7cf24bba67505c11aaf4c19a2f562db3d4289/static/clientlogic.js#L186).

**Fix:** distinguish an origin action from an arriving consequence. Render, for example, “AuditVisitor's seeding at Quiet Moon World reached this place.” Keep actor type ambiguous while preserving who acted and where the event began. This is a presentation correction over existing history, requiring no reset.

## Does changing the game require rebuilding the world?

**Usually no.** The important boundary is between preserving identity and history, and freezing all future content and behavior. The current architecture already separates much of this.

| Change | Existing world reset? | Appropriate path |
|---|---|---|
| Navigation, layout, explanations, sensory rendering | No | Deploy presentation changes. Wayback already states that old state uses today's renderer. |
| New generation banks | No effect on existing world | They affect future births. Editing the generator alone will not improve existing places. |
| Tuning future effects, behavior, and rewards | No in principle | Specify when new rules apply; preserve landed deltas; handle pending work and active challenges explicitly. |
| New puzzle families | No in principle | Introduce through explicit future instances/renewals. Pin active puzzle identity and content/version so updates cannot orphan attempts or solves. |
| New situations or changes to existing place properties | No in principle | Add a versioned, chronicled evolution path with preconditions and a readable cause. The general path does not exist yet. |
| Additional children/frontiers | No in principle | Requires a deliberate append path, stable addresses, updated discovery/navigation, and historical topology semantics. Current birth API refuses additions after birth. |
| Rename, reparent, replace scales, or change historical meaning | Highest continuity cost | Keep existing identity stable; add display labels/aliases where sufficient. Structural changes need explicit identity/lineage migration and an ADR. A reset is a product choice, not the only technical option. |

Important residual constraints:

- Durable history still keys on canonical node names, and the resolver validates the numeric path suffix and exact name. The existing `(world_seed, path)` is useful stable identity for a fixed topology, but it does not make renames or reparenting safe automatically. Avoid changing canonical keys casually.
- Stored birth properties are immutable today; overlays carry ongoing substance. Preserve that foundation and add evolution events. Do not edit stored base rows to make the current generator appear retroactively correct.
- Puzzle generation and law profiles are still executable code. The materialized world does **not** pin every active puzzle or pending rule interpretation. A queued causal hop consults the current law on arrival. Versioning or controlled draining is needed when changing those rules.
- Era names remain derived from frozen display banks. Materialize/version them if their vocabulary is to change.
- The current wrap design ends the hierarchy at the particle and returns to the whole. Breadth growth is the compatible expansion direction under the accepted decision. A new dimensional hierarchy would reopen that product decision.

ADR-006's “evolution mechanics are wanted” trigger now applies to this discussion. The next artifact should be a proposed evolution contract for review, not another blanket freeze. A minimal contract defines stable affected identities, event/rule version, preconditions, actual deltas, source cause, idempotency, scheduling, and what a returning player can observe. Keep past facts intact; use compensating events when correcting state. Start with explicit authored/operator-controlled changes before giving a generative system authority to create persistent canon.

## How the world should continue to evolve

History accumulation is one source of depth. Sustainable discovery also needs changes to the player's understanding, relationships, and available choices.

1. **Familiar places develop.** A recurring inhabitant pursues a small goal, a player intervention changes the next state, and later visitors encounter the result. Revisits depend on current conditions and commitments.
2. **Relationships reveal new possibilities.** Players learn specific connections between scales. Mastery comes from predicting and using them, supported by readable evidence.
3. **New situations enter established geography.** Introduce authored, versioned situations using current inhabitants and places. Preserve completed history and avoid making every update a repair chore or reset of previous accomplishments.
4. **Geography grows when needed.** Open a bounded new pocket when the existing world has demonstrated meaningful return behavior and genuine spatial exhaustion. More geography is not the initial retention strategy.

Keep cumulative historical wear separate from present conditions. `ripple_score` only increases and caps at 1.0, so a busy place eventually loses that channel's ability to distinguish a fresh disturbance. A derived recent-pressure signal could coexist with permanent wear, using recorded event time and a defined simulation clock. This would require a deliberate extension to the current determinism contract, with historical queries evaluated at their requested time; it should not use arbitrary client wall clocks.

Renewal should produce a new question or affordance often enough to matter. Re-scrambling familiar answers is useful background variety. Return motivation should come from something the player has a relationship with undergoing an understandable change.

## Recommended development sequence

### First: secure the promise and define the slice

Resolve queue delivery and delayed-action semantics; add changed-place revisit behavior. Document which changes preserve existing state and which require an evolution event. Establish a restore test against a disposable copy with pending work. These are bounded continuity requirements, not a mandate to finish every possible future migration before play begins.

In parallel as product design work, specify one experience across roughly **8–15 connected places and 3–4 scales**, using the existing world. Include one recurring inhabitant, a trace left by a prior visitor, two materially different interventions, one visible delayed consequence, and an unresolved follow-up. Keep the rest of the world explorable.

### Next: make one first session compelling

Illustrative new design, not a description of shipped content: a room carries a recurring signal that unsettles its region. Its history points toward an instrument inside it. Investigation at a smaller scale reveals why the signal travels. One intervention quiets it; another preserves the signal while changing where it lands. An inhabitant has a reason to prefer one outcome. The world records the choice, and a later visitor can recognize what happened.

The first minute should present the anomaly; the next few minutes should let the player form and test an explanation; the first intervention should produce a perceivable result during that session. Longer consequences can remain pending if the player understands what they are waiting for. Use existing art, speech, puzzles, and Wayback in service of that sequence.

Develop this through one primary player surface, with large readable text, local navigation, and a clear next interaction. A new art engine is not a prerequisite.

### Then: demonstrate continuity through one update

Add a journal and a relevant return recap. Run the slice with a small invited cohort, let real history accumulate, deploy one additive situation change, and verify that players retain their identities, contributions, active work, and access. That rehearsal directly tests the launch-freeze assumption.

The initial goal is evidence from roughly **8–12 target players**, not statistical certainty. Proposed decision gates, to agree before testing:

- At least 8 of 10 can identify something they want to investigate within two minutes without a facilitator supplying an objective.
- At least 7 of 10 can accurately explain one consequence of their action after the first session.
- At least half choose to return within seven days without a research reminder supplying their reason. Ask what they returned to do and record the reason.
- At least 7 of 10 returning participants can recognize a personally relevant change. Collect more participants if too few return to interpret this measure.
- No lost or duplicated consequences under injected queue failures, no stranded active puzzle attempts under the trial update, and no historical delta rewritten.

These are proposed pilot gates, not industry benchmarks. Record denominators, invitation timing, prior familiarity, and reminders. The current `beta_metrics.py` counts people active on two calendar days within a window; that is useful activity reporting, but it is not cohort D1/D7 retention or evidence of causal understanding. Instrument the small number of missing observations separately from permanent world canon. [Current metrics](https://github.com/mark-weeks/hello-nested-worlds-adventure/blob/87a7cf24bba67505c11aaf4c19a2f562db3d4289/scripts/beta_metrics.py#L63).

If players admire the premise but still cannot name a reason to return, revise the situation and consequence design before expanding the content banks or infrastructure. If the slice works, generalize the smallest reusable parts and introduce further situations within the same continuing world.

## Decision proposed for review

Commit the next development cycle to **one demonstrably compelling discovery-and-return experience**, supported by the targeted continuity corrections above. Retain the existing architecture and single shared world. Treat new evolution rules as reviewable proposals, and keep all implementation PRs for development-team review without auto-merge.

This assessment PR adds documentation and an opt-in diagnostic script; it changes no application behavior, schema, world identity, or existing history. Its runtime probes use disposable databases only. Merging this assessment records the findings and proposal; it does not ratify new evolution rules or authorize their implementation. The development team reviews this PR without auto-merge. The unresolved product decision is whether the proposed shared-mystery focus captures the intended center of Enfolded; the evidence supports testing it before investing in further breadth.


## Next validation work

Before implementation PRs, validate the delivery failures with actual process termination, duplicate delivery, concurrent pending actions, and restart recovery. Extend the longevity probes to partially explored worlds, changed-place revisits, and renewal cycles; the terminal-state result does not establish frequency. Evaluate live AI conversations and observed first/return sessions to test the experience hypotheses. These checks refine the fixes and product choices; they are not prerequisites for reviewing this assessment.
