# ADR-031: Model Authorship Under Ratification — the model proposes, code validates, a ledger ratifies, the chronicle records

**Status:** Proposed draft, 2026-10-03, written at the owner's request after the
[ambition-and-boundaries assessment](../evaluation/2026-10-03-ambition-and-boundaries.md)
(decision D2) and its review corrections. Not ratified. This document introduces
no runtime behavior, migration, or write path. It depends on
[ADR-029](ADR-029-evolution-grammar.md) for structural events and their
validator, and on [ADR-030](ADR-030-render-contract.md) for art-direction
versions; on ratification it narrows, rather than repeals, the clause in
[ADR-013](ADR-013-versioned-situations-and-delivery.md): "A language model may
propose text or an allowed action, not invent persistent canon, grant
permissions, or execute arbitrary state changes." The model still never
executes a state change. It may now *propose* canon, and a deterministic
pipeline decides whether canon is made.

---

**2026-10-04 selection clarification:** Provider/model choices follow
[ADR-034](ADR-034-provider-and-model-optionality.md). The dated comparison below
is historical context, not a standing Opus preference or current pricing evidence.
This clarification does not ratify the authorship proposal.

## Context

The model is called in exactly four places today: node voice
(`consciousness/__init__.py:1044`, `max_tokens=256`), inhabitant voice
(`:1177`, `max_tokens=200`), the moderation classifier (`:1260`, Haiku), and
the intention interpreter (`consciousness/interventions.py:37-78`), whose
JSON schema confines `op` to the scale's four verbs and `amount` to 1. It
authors prose and classifies. It never writes a name, a property, a puzzle, an
event, an art direction, a melody, or an era. Ambient life has no model in it
(`agents/behaviors.py`, 44 lines). The default model is one generation behind
the current Opus and more expensive (`claude-opus-4-8` at $5/$25 per million
tokens against Opus 5.5 at $4/$20 with cache reads at $0.20).

Two reasons were braided into that boundary. One is a covenant and stays:
every player owns their actions; the chronicle is append-only; failure stays
in fiction; a model proposal is not another player's decision. The other was a
2025 judgment about model reliability and price, and it has decayed: structured
outputs are generally available (`output_config.format`, `strict` tools),
one-million-token context is flat-priced, prompt caching and the Batch API
halve or better the cost of non-interactive work, and the shipped products that
survived with generated worlds all converged on the same architecture: the
engine owns state and the model narrates or proposes into it (Latitude's
Voyage, Krafton's inZOI, Hidden Door's cards, 1001 Nights' bounded vocabulary,
Infinite Craft's generate-once-per-key). The research record is equally
specific about what breaks: say/do incoherence without a single decision
bottleneck, hedged remarks that harden into facts when rewritten into memory,
agents trusting stale memory over an authoritative tool, and collusion among
capable agents whenever incentives allow it. Governance at deployment, not
prompting, is what controls these.

Three house rules already point the way. ADR-009: "anything historical must be
stored at write time, never recomputed at read time." ADR-013: "Corrections
use explicit compensating events." ADR-021: narration is evidence-bound and
"never match[es] by name, verb, time proximity or topology." The owner's review
of the assessment added the two constraints this ADR must honor: redaction
scrubs five text fields and never repairs applied deltas, so a wrong ratified
change needs a correction mechanism; and the existing puzzle quality script is
an ecology census, not a solvability proof, so model-authored puzzles need a
new runtime validator with a procedural fallback.

## Decision

### D1. The authorship principle

The model never holds a write handle. Every model output that could become
persistent passes through one pipeline:

1. **Proposal.** The model returns a typed proposal under a frozen JSON
   schema, recorded as an append-only row in a proposal ledger (D3) before
   anything else happens.
2. **Validation.** Deterministic code checks the proposal: schema shape and
   enum membership (the schema's job), numeric bounds and cross-field
   invariants (code's job, because structured outputs do not express numeric
   limits), the world's covenants, and the tier's specific validators (D2).
   A validator is never a model.
3. **Ratification.** A policy decides: automatic for a tier that has earned it,
   an operator queue otherwise (D4).
4. **Commit.** Ratified proposals are applied only through the existing
   authoritative paths: the ADR-009 substance API for deltas, ADR-029's
   structural event kinds, `puzzle_instances` definitions (ADR-024), ADR-030's
   direction versions, and the authored-text store this ADR adds. The chronicle
   row or stored version carries `authority = {"kind": "ratified", "ref":
   <proposal id>}`, the authority ADR-029 reserved.

Nothing in this pipeline duplicates an existing door. It routes through them.

### D2. Three tiers of authorship, each with its own schema, validators and ratification policy

| Tier | What the model may propose | Where it lands | Validators (deterministic) | Default ratification |
|---|---|---|---|---|
| **0 — voice and classification** (exists) | replies in a place's or inhabitant's voice; intent classification into the scale's verbs; moderation | the `PLAYER_SPEAK` trace, the Act pipeline, nowhere | unchanged | automatic (unchanged) |
| **1 — interpretation** | the evolving description of a place (today rule-based in `multiverse/description.py`); era annals extending ADR-021; inhabitant reflections as outward prose (the memory claims they draw on belong to [ADR-032](ADR-032-inhabitant-cognition.md)'s `inhabitant_memory`, produced through this same pipeline and validator but stored there, never here); the sensory conditioning text ADR-030's paid renderers consume | a new versioned `authored_text` store for outward text; memory claims in ADR-032's `inhabitant_memory`; never `world_mutations`, never properties | every citation resolves to an existing chronicle row; the hedge vocabulary is enumerated and preserved; no sentence classifies a trace as human or agent; no participant is named beyond what the cited rows show; length caps; the moderation screen; and for memories, every fact resolvable from the database is pre-resolved into the prompt so the model restates rather than recalls | automatic after validation, with a sampled human audit (D4); on any failure, the rule-based text serves |
| **2 — bounded canon** | puzzle definitions at `definition_version` 2; situations seeded from real history in ADR-025's shape (existing places, clues, two interventions, an inhabitant promise fulfilled by a recorded property change); re-aspecting and renames through ADR-029; art-direction text per scale under an ADR-030 `direction_version` | `puzzle_instances`, the situation tables, ADR-029 events, ADR-030 versions | the assessment §6.6 runtime puzzle validator (leak screen against node and ancestor properties, format and determinism, per-node difficulty and attempt limits, independent solvability, procedural fallback); ADR-029's validator; numeric bounds in code; uniqueness; for art direction, the ADR-028 differentiation gate before it becomes a default | **operator queue**, graduating to automatic per proposal kind only after a measured audit rejection rate below a threshold the owner sets over a sample size the owner sets |
| **3 — structure and physics** | frontier births, passages, era turns; retirements and law shifts | ADR-029 events | ADR-029's validator plus per-world rate limits (so the world changes at world speed, not model speed) | **operator only**; births, passages and era turns may graduate under rate limits; retirement and law shift require a human decision permanently |

Tier membership is part of each proposal kind's schema version. A kind cannot
be promoted across tiers by prompt; it moves by changing this table.

### D3. The proposal ledger

Two additive, append-only tables outside the chronicle:
`proposals(id, kind, tier, schema_version, subject_path, model, prompt_hash,
input_digest, proposal JSON, validator_report JSON, created_at)` and
`proposal_decisions(proposal_id, decision, decided_by, reason, committed_ref,
decided_at)` with `decision ∈ {validated, rejected, ratified, committed,
refused, corrected, superseded}` and `decided_by ∈ {validator, auto,
operator:<id>, model-review}`. The ledger is operational data like the
community records, not the chronicle: it is never a `world_mutations` write.
Its retention is split: a proposal that committed canon, and every decision
on it, is retained at least as long as any canon row that references it,
which for chronicle-referenced proposals means indefinitely; only proposals
that never committed fall under a shorter operational policy. Every committed
canon row points back to its proposal; every proposal points forward to what
it became. The
`input_digest` makes Tier 1 and Tier 2 generation content-addressed: the same
inputs do not pay twice, and the first ratified output for a digest is the
canonical one.

### D4. Validators are code; ratifiers are policy; a second model may only reject prose

- Deterministic checks run first and are sufficient to reject.
- A second, cheaper model may review **prose fields only**, with a different
  system prompt, no access to the proposer's reasoning, and the power to
  reject but never to ratify. Shared incentives between proposer and reviewer
  are what the collusion results warn against, so the reviewer sees the
  proposal and the authoritative inputs, not the proposer's rationale.
- Human audit samples every automatic tier at a rate per tier. A tripwire
  demotes a tier to the operator queue when its audit rejection rate crosses
  the owner's threshold; the demotion is a guard flag, not a deploy.
- Every tier has a kill switch in `server/guard.py` alongside the existing
  AI and image switches; killing a tier serves the rule-based fallback.

### D5. How the proposer is prompted

- **Authoritative inputs, pre-resolved.** The prompt carries current state and
  cited chronicle rows fetched from the database for this proposal. The
  model's earlier statements are never supplied as facts. Where a memory is
  supplied, it is supplied with its hedge and its citations.
- **Frozen schemas.** Each kind's JSON schema is pinned per deploy, because
  changing a schema invalidates the prompt cache and its grammar; schema
  versions ride the proposal row.
- **Caching and batch.** The world and agent bibles keep their one-hour cache
  with the existing minimum-prefix guard (`consciousness.cached_prefix_meets_minimum`,
  `docs/development/agent-runtime.md`). Operator instructions that change
  mid-run go in mid-conversation system messages so the cached prefix survives.
  Tier 1 work that nobody is waiting for (annals, reflections, descriptions of
  unvisited places) runs through the Batch API at half price.
- **Models pinned per surface and changed only with a CHANGELOG entry.** The
  authorship surfaces move to the current Opus; reflection and review run on
  the current Sonnet or Haiku; low effort for ambient work. A model change on
  a voice surface first passes the comparative voice evaluation the runtime
  guide requires, because players notice a silent swap.
- **Refusals stay in fiction.** A `refusal` stop reason records the proposal
  as `refused` and serves the fallback; no classifier text reaches a client.
  Forced tool choice is not used; structured outputs are.

### D6. Correction: compensating events, never deletion

A ratified proposal that proves wrong is corrected by a new proposal of kind
`correction` whose commit reverses the original through the same door: an
inverse delta for substance, ADR-029's inverse kind for structure, a
superseding version with a forward pointer for authored text, puzzle
definitions and art direction. The correction row carries `corrects:
<proposal id>` and a reason; the original rows stay.

An inverse is never applied blindly, because an RFC 7396 inverse restores
old values rather than undoing one contribution: if the proposal changed a
field from A to B and a player then changed it to C, restoring A would erase
the player's result. A correction therefore commits only through the
state-dependent path (`record_substance_transition`, under the same writer
lock) with **transactional preconditions**: every field the correction
touches must still hold the value the original proposal wrote, every alias
it would revert must still be the current one, and no intervening structural
event may have touched the subject. If any precondition fails, the correction
is refused as a ledger decision (`decided_by = validator`, reason
`conflict`), nothing is written to the chronicle, and the case is routed to
an explicit **compensating decision against current state**: a new proposal
that takes the present values as input and describes the intended repair,
reviewed under the kind's tier. The same rule governs ADR-029 inverses (a
rename back checks the current alias; a reopening checks that nothing was
built on the retirement) and never applies to authored-text supersession,
which conflicts with nothing. Redaction remains content-level and is not a
correction mechanism. A player who acted on wrong canon is recorded, not
undone. An operator command (`python main.py proposals correct <id>`)
performs this, dry-run by default and printing the precondition check; the
model may propose a correction like any other kind, under the same tiers.

### D7. Covenants, restated against authorship

- **Every player owns their actions.** A proposal is never an action by a
  player or an inhabitant. Authority is `ratified`, not a participant. Whether
  inhabitants may themselves propose is the inhabitant decision's call; if it
  grants that, the proposal still passes this pipeline.
- **The chronicle blurs.** Authored text never classifies traces; the ledger
  is not surfaced in `/chronicle` or Wayback; a committed change renders as a
  mechanical change exactly as an operator's would under ADR-029.
- **Failure stays in fiction.** Every pipeline failure, budget exhaustion,
  kill switch or refusal yields the rule-based text or the authored quiet line.
- **Difficulty is per node; the seal never imprisons; scale is meaning.** The
  puzzle validator, ADR-029's validator and the ADR-028 gate enforce them on
  proposals exactly as on operator work.
- **No model judges a player's answer** (ADR-015) and **no opaque model
  judgment earns rank** (ADR-017). Those stand.

### D8. Disclosure and contest

A player-facing page states which surfaces are model-authored, by tier, and
how to contest an interpretation through the existing Ideas and reporting
routes. Disclosure is at the surface level; individual traces carry no
"model-written" tag, for the chronicle's reasons. The visual language already
requires that a player can understand and contest an interpretation; this
gives the route a home.

### D9. Budget, cadence and rate

Dollar budgets per tier per day in the guard's buckets (not call counts),
with the per-credential sub-cap kept for Tier 0. Proposals run on the heartbeat
and pump cadence and in Batch, gated by attention: places and inhabitants that
no one has visited recently are described and reflected on hourly, not every
minute. Committed canon is rate-limited per world per day by kind, so a
quiet week stays quiet. The assessment's attention-gated cost model is the
reference: a fixed floor in the low hundreds of dollars per month, the rest
scaling with player-hours.

### D10. What this ADR does not decide

Inhabitant cognition and whether inhabitants may propose; the scale registry;
external agents as players; player-authored canon; the exact audit rates,
thresholds, sample sizes and rate limits, which the owner sets at ratification
and may change by configuration.

## Implementing batches and the doors they trip

| Batch | Scope | Doors (irreversibility check) |
|---|---|---|
| **1 — the pipeline and Tier 1** | `proposals`, `proposal_decisions`, `authored_text` migrations; the validator framework (reusing ADR-029's where present); Tier 1 kinds: place descriptions, era annals, outward inhabitant reflections (memory claims land in ADR-032's store when that decision's batch 1 ships); provider and exact model/version selected for authorship under ADR-034, with task and voice evaluation on record; dollar budgets and per-tier kill switches; the disclosure page; `proposals list / approve / reject / correct` CLI | Additive migrations; **no chronicle write path** (Tier 1 writes none); a model-default change recorded in the CHANGELOG |
| **2 — Tier 2** | puzzle definitions at `definition_version` 2 behind the runtime validator with procedural fallback; situations seeded from history; re-aspect and rename through ADR-029 (requires its batches 1 and 2); art-direction proposals under ADR-030 versions | The chronicle write paths are ADR-029's, not new ones here; `puzzle_instances` gains a definition version (additive) |
| **3 — Tier 3 and graduation** | tripwires, audit sampling dashboards, per-kind graduation to automatic ratification where the owner allows; births, passages and era turns under rate limits | None beyond ADR-029's |

Tests that gain cases: a validator refusal matrix per kind (shape, bounds,
invariants, covenant violations, unresolved citations, actor-type words,
hedge loss); fallback on refusal, budget, kill switch and provider failure;
rate limits; correction creates inverse events and never deletes; the
second-model reviewer cannot ratify; content-addressed proposals do not pay
twice; and the ADR-028 gate extended to art-direction proposals.

## Trade-offs accepted

- **An operator queue costs attention until tiers graduate.** That is the
  price of letting a model author canon in a world that promises never to
  rewrite history; it is bounded by sampling and tripwires.
- **Canon can still be wrong.** The correction mechanism makes it loud and
  reversible by event, not silent and fixed by deletion.
- **Two models on prose tiers raise cost.** Review is prose-only and sampled;
  Batch halves the non-interactive share.
- **A model-default change changes the voice.** The comparative evaluation
  runs first and is recorded.
- **Disclosure may deter some players.** The evidence says acceptance is
  conditional on use; the products that hid the model fared worse than the
  ones that constrained it visibly.
- **The ledger grows.** It is operational data with its own retention policy,
  not chronicle.

## Revisit when…

- **A tier's audit rejection rate falls below the owner's threshold over the
  owner's sample size** → graduate that kind to automatic ratification.
- **A tier's rejection rate rises or players contest it** → the tripwire
  demotes it; review the kind's schema and validators before re-promoting.
- **The inhabitant decision lets inhabitants propose** → extend `authority`
  with a `proposer` field; the pipeline is unchanged.
- **Structured outputs gain numeric bounds** → move the bounds into the
  schema and keep the code check as the net.
- **A new model generation ships** → re-run the voice evaluation; keep the
  pinning rule.
- **Collusion or repetition is observed between proposer and reviewer** →
  change the reviewer's inputs or model; never remove the human sample.
- **External agents join as players** → they remain players under ADR-028;
  authorship stays with this pipeline.

## Rejected alternatives

- **Direct model writes to properties, names, topology or puzzles.** ADR-013,
  ADR-027 and ADR-028 rejected it; this ADR keeps the rejection and adds the
  door that was missing.
- **A model as validator.** Shape and enum membership belong to the schema;
  bounds and invariants belong to code; a model may only reject prose.
- **A model as judge of player answers or creativity.** ADR-015 and ADR-017
  stand.
- **Automatic Tier 3 from day one.** The world's shape changes at the rate a
  human can watch until the record shows the pipeline earns more.
- **Redaction as correction.** It scrubs five text fields; it cannot reverse a
  delta, a pinned definition or a born row.
- **One model proposing and reviewing its own work.** Shared incentives are
  the documented failure.
- **Per-trace "model-written" tags.** The chronicle blur covenant; disclosure
  belongs at the surface.
- **Unbounded cadence.** A world that changes at model speed is churn, not
  life; rate limits per kind per day keep it at world speed.
