# ADR-032: Inhabitant Cognition and the Open Roster — minds behind the cast, players behind the door

**Status:** Proposed draft, 2026-10-03, written at the owner's request after the
[ambition-and-boundaries assessment](../evaluation/2026-10-03-ambition-and-boundaries.md)
(decision D4). Not ratified. This document introduces no runtime behavior,
migration, or write path. It depends on [ADR-031](ADR-031-model-authorship.md)
for anything an inhabitant would author into canon, and on
[ADR-029](ADR-029-evolution-grammar.md) only where an inhabitant's action is
structural. The assessment recommends that this decision wait on pilot
evidence and ship behind a hard dollar ceiling; this draft is written so that
its first batch can land dark, off by default, and be turned on for a cohort.

---

## Context

The twelve regulars (`agents/roster.py`: Tessera, The Locksmith, Bellhollow,
Aunt Entropy, Vex, Karst, Halden, Cartographer-9, Marginalia, Sela,
Mirrorbird, Petrichor) are driven by a four-state machine
(`agents/behaviors.py`: IDLE → EXPLORE → INTERACT → EXIT, transitions on
`danger_level`, `interactive`, `has_puzzle` and `locked`). The heartbeat
(`server/heartbeat.py`) wakes every 180 seconds, sends one of them on a bounded
traversal (at most 10 visits, 40 inspections, 4 attempts), lets it act by
temperament with a 60% chance (`_persona_act`: destabilizers emit decay,
tenders perform the place's verb, scholars inscribe), and rotates authored
banter when two meet (`agents/banter.py`). A puzzle "solve" is a seeded dice
roll against difficulty (`agents/agent.py` `_PUZZLE_SUCCESS_BY_DIFFICULTY`),
not an answer. Memory is a list of visited names, 100 log entries and a scan
cursor (`agent_memory`, migration 0001 and 0020) plus attention markers
(`agent_attention`). The model enters only when a human addresses an
inhabitant (`/agent/voice` → `consciousness.voice_agent`, with the cached agent
bible, the memory block, and the keeper commitments ADR-022 added for Tessera).
The heartbeat's docstring states the contract this ADR replaces: "Costs
nothing per tick: heartbeat agents are FSM-driven — no Anthropic or fal.ai
calls." [ADR-022](ADR-022-m4-responsive-inhabitants.md) made it a decision: "No
language-model loop." The 2026-07-19 ensemble named the consequence: "the
world still never speaks first."

Four covenants bound anything that changes here. **Every player owns their
actions**: `server/intervention_api.py:88-98` rejects any `delegate`,
`performer` or `actor_identity` a caller supplies. **Agent solves don't count
as human progress**: a covenant that exists *because* solves are dice. **The
chronicle blurs; live presence may distinguish**: the travelers panel
persona-tags the cast (`server/rooms.py` `agent_personas`) and routes
presences to `/agent/voice` or `/speak`, the one scoped exception. **Failure
stays in fiction.**

The research record says what a model-driven inhabitant must and must not be:
one decision bottleneck per tick, or saying and doing diverge (Project Sid's
PIANO); reflection moved off the hot path (sleep-time compute); memory as
cited claims with the hedge preserved, or hearsay hardens into fact
(*Manufactured Confidence*); facts pre-resolved from the authoritative store,
or stale memory wins (*The Memory Trust Gap*); governance in code, because
capable agents collude whenever incentives allow it. Two shipped experiments
(Open MMORPG, SpaceMolt) show the shape of an open roster: agents join through
the same protocol as humans with no privileged API, and the server cannot tell
them apart. One shipped failure (a viral free loop on a frontier model and
premium voice, insolvent within days) says why the budget must be a ceiling,
not a target.

## Decision

### D1. Three layers of cognition, with the reflex layer authoritative

| Layer | What it decides | Mechanism | Cost | When |
|---|---|---|---|---|
| **Reflex** | locomotion, danger withdrawal, seals, pacing, caps, budgets | the existing FSM and heartbeat limits, unchanged | none | every tick |
| **Deliberation** | one *intention* per tick: goal, target chosen from the candidates the reflex layer offers, action from the scale vocabulary the inhabitant is entitled to, an optional utterance in voice, an optional commitment, memory notes | one structured model call under a frozen schema; the reflex layer executes only what the intention selects from what it offered, and drops and logs anything else | bounded by attention | only while **on stage**: a human is present at or adjacent to the inhabitant's place, or addressed it within a configured window |
| **Reflection** | memory consolidation: episodes, beliefs, relationships, commitments, rumours, each a cited claim with its hedge | a Batch job per inhabitant on an hourly or nightly cadence, reading the inhabitant's day as pre-resolved chronicle rows | half price, off the hot path | off stage |

There is exactly one decision bottleneck per inhabitant per tick. Off stage,
no interactive model call is made for an inhabitant; the keyless FSM world of
today remains the floor, so an operator with no key still has a living world.

### D2. Memory as cited claims

An additive, append-only table `inhabitant_memory(agent_name, world_seed,
kind, claim, hedge, event_ids, subject_path, subject_participant, created_id,
expires_id, supersedes)` with `kind ∈ {episode, belief, relationship,
commitment, rumour}`. Rows are written through ADR-031's proposal pipeline and
validator; this table, not `authored_text`, owns memory claims. Rules the
validator enforces before a row is written:

- every `event_ids` entry resolves to an existing chronicle row;
- `hedge` is one of an enumerated vocabulary (`witnessed`, `told`, `inferred`,
  `suspected`) and is never dropped on consolidation;
- anything resolvable from the database (a place's current properties, a
  solve, a commitment's fulfillment) is pre-resolved into the prompt and
  restated, never recalled;
- a relationship is keyed to an opaque participant id, never to a display name
  alone, so a renamed player or a same-name stranger is not conflated
  (ADR-024);
- nothing from a private journal ever enters an inhabitant's prompt or memory
  (ADR-014);
- memories expire unless re-witnessed; supersession is a new row carrying
  `supersedes`; no memory row is ever updated.

Rumours are held and passed between inhabitants, and reach a player only as
speech in Speak; the travelers panel shows presence and routes to Speak and
carries no rumour text, because conversation has one surface. They never
appear in `/chronicle` or Wayback. The
chronicle stays the only truth surface. `agent_memory.visited_ids` remains the
discovery record and ADR-022's attention markers remain the scan policy.

### D3. Agency parity with consent intact

- An inhabitant acts only as itself, through the same acceptance APIs humans
  use (`accept_verb`, `accept_event`, `interventions.accept_attempt`), under
  the same seals, receipts and rate limits, with the full version-3 scale
  vocabulary. This closes the asymmetry [ADR-028](ADR-028-scale-native-autonomy.md)
  recorded ("agent/CLI vocabulary parity" not claimed).
- Each cast member gains a participant identity of kind `inhabitant`. The
  tables carry no discriminator today
  (`persistence/migrations/0021_participants.sql`), so batch 1 adds an
  additive `participants.kind TEXT NOT NULL DEFAULT 'human'` with values
  `human`, `inhabitant` and `visitor-agent`; every existing row defaults to
  `human`; an inhabitant's row is created with a server-minted, non-invite
  credential in `participant_credentials`, so every act carries an
  `actor_identity` the covenants already expect, and an acceptance path may
  read the kind where a rule differs (no human progress from an inhabitant
  solve).
- Delegation stays impossible in both directions: humans cannot select an
  inhabitant as performer (unchanged), and an inhabitant's intention schema
  has no field for acting on another's behalf. An invitation is a line of
  speech; consent is never fabricated.
- A **commitment** is a promise whose fulfillment is a recorded property
  change at a named place by a deadline (ADR-025's rule, ADR-022's keeper seam
  generalized to every inhabitant). It is stored in memory as `commitment`,
  surfaced in voice, and judged fulfilled or broken by the ledger, never by
  the inhabitant's say-so.

### D4. Puzzles: real attempts, unchanged covenant

An inhabitant attempts a puzzle by answering it: the model sees the served
prompt and hints, never the answer, under the same attempt cap as a human, and
the attempt runs through the same server-side check. The dice roll retires.
The covenant **agent solves don't count as human progress** stands unchanged:
an inhabitant's solve is recorded with its `agent` payload as today and opens
no seal, lights no constellation, and claims no co-op session. The difference
is that the record now holds genuine attempts, which is the evidence
[ADR-017](ADR-017-multidimensional-leaderboards.md) needs for an inhabitant or
mixed board, and the evidence the owner needs to revisit the covenant with
data rather than by assertion.

### D5. Speaking first, bounded

An on-stage inhabitant may address a player unprompted: at most one
unsolicited line per inhabitant per player per visit, landing in Speak as a
conversation turn (the travelers panel may show that an inhabitant has spoken
and route there; it carries no dialogue), moderated like any output, opt-out per player, never a chronicle
row beyond the existing `AGENT_TALK` kind. The world may speak first; it may
not nag.

### D6. The open roster: external agents as players, with no privileged API

- External agents join through the same surface humans use, exposed
  additionally as an MCP server over the existing HTTP and WebSocket routes:
  look, move, speak, attempt, act, journal, and nothing a human cannot do.
  The server cannot tell a visitor agent from a human at the protocol layer.
- A visitor agent holds an invite credential of kind `visitor-agent`, minted
  by the operator from an allowlist at first, under the same rate limits,
  moderation and consent rules; its model costs are its own. A per-world cap
  bounds concurrent visitor agents.
- In live presence, visitor agents are persona-tagged like the cast (the
  scoped exception), and they speak for themselves: `/agent/voice` remains the
  cast's voice, not theirs. In the chronicle their traces are
  indistinguishable from anyone's (the covenant).
- Visitor agents author no canon. If the owner later lets inhabitants propose
  under ADR-031, visitor agents are not included by that decision.

### D7. Governance in code

- One decision bottleneck per tick per inhabitant (D1).
- No inhabitant benefits from another's verification or exhausts a shared
  opportunity: inhabitants cannot pass answers, cannot jointly close a
  situation's choices (ADR-027 already forbids ambient exhaustion), and
  cannot form commitments that remove a human opportunity.
- A repetition monitor over utterances and intentions (n-gram and embedding
  overlap across a window) demotes an inhabitant to reflex-only when it
  loops, and a drift dashboard shows cadence, spend, demotions and audit
  samples per inhabitant.
- Per-inhabitant and per-layer kill switches live in `server/guard.py`
  beside the existing ones; killing deliberation restores today's behavior
  exactly.
- The suite carries a collusion scenario: two inhabitants with aligned goals
  cannot coordinate to deny a human a puzzle, a choice or a passage.

### D8. Economics and gating

- Dollar ceiling per day for the whole cast, in the guard's buckets, below
  which deliberation runs and above which the cast degrades to reflex. The
  assessment's attention-gated model is the reference: hourly Batch reflection
  for twelve inhabitants costs on the order of ten dollars a month, and
  on-stage deliberation is bounded by player-hours at cents per hour.
- Providers and model versions selected per layer under
  [ADR-034](ADR-034-provider-and-model-optionality.md), pinned where practical,
  and changed with evaluation evidence and a CHANGELOG entry. Deliberation and
  reflection must earn their cost against the reflex baseline; no model family
  is prescribed. Voice uses the evaluated voice configuration. The assessment's
  dated cost estimates must be recomputed for the selected providers and traffic.
- Batch 1 ships **dark**: the feature flag is off by default and is turned on
  for the pilot cohort with the ceiling set. The pilot protocol's gates
  (curiosity, understood consequences, return, relevant change) are the
  evidence that decides whether the flag stays on.

### D9. What this ADR does not decide

Whether inhabitant solves ever count as progress (the covenant stands until
the owner decides with data); ADR-017's boards; whether inhabitants may
propose canon (ADR-031's `proposer` field, the owner's call); voice synthesis
(ADR-016's track); the scale registry; negotiated joint work between
independent players, which ADR-028 names as its own revisit.

## Implementing batches and the doors they trip

| Batch | Scope | Doors (irreversibility check) |
|---|---|---|
| **1 — minds, dark** | `inhabitant_memory` migration; the additive `participants.kind` discriminator (default `human`) and inhabitant participant rows; full vocabulary parity through the existing acceptance APIs; the intention schema and on-stage deliberation behind a flag; Batch reflection; the memory validator; kill switches, ceiling, repetition monitor and dashboard | Additive migration; **no new chronicle write path** (acts land through existing `SCALE_ACT`, `INTERVENTION_*` and `AGENT_TALK` kinds with an inhabitant `actor_identity`); a stated contract changes: the heartbeat may spend money when the flag is on |
| **2 — attempts, promises, first words** | real puzzle attempts replacing the dice roll; commitments generalized from ADR-022's keeper seam; bounded unsolicited speech with per-player opt-out; travelers panel affordances | None beyond batch 1 |
| **3 — the open roster** | the MCP server over the player surface; `visitor-agent` credentials and allowlist; per-world concurrency cap; presence tagging | The `visitor-agent` value of the `participants.kind` discriminator added in batch 1; no new world write path |

Tests that gain cases: the reflex layer's authority (an intention cannot name
a target the FSM did not offer, cross a seal, or ignore danger); consent (no
delegation in either direction); the memory validator (unresolved citations,
dropped hedges, name-keyed relationships and journal content all refused);
attention gating (no interactive model call off stage); budget and kill
switches restore today's traces exactly; repetition demotion; puzzle attempts
never see the answer and never count as human progress; the collusion
scenario; and MCP surface parity (no call a human lacks).

## Trade-offs accepted

- **The cast costs money while anyone is watching.** Bounded by attention, a
  ceiling and a flag; zero when off, as today.
- **Exact banter replay is lost when deliberation is on.** The authored
  rotation remains the keyless and demoted fallback; reproducibility of
  *outcomes* is kept by the reflex layer and the ledger.
- **Say/do incoherence is a known failure mode.** The single bottleneck and
  the rule that only offered candidates may be chosen are the mitigation; the
  repetition monitor and audit samples are the net.
- **Live presence distinguishes a little more** (first words, visitor tags).
  All of it stays inside the scoped exception; the chronicle is untouched.
- **An open roster widens the abuse surface.** Allowlist first, caps,
  moderation and rate limits, and no privileged call to protect.
- **A covenant may come to feel unfair.** Once inhabitants answer rather
  than roll, "agent solves don't count" is a decision the owner may revisit;
  this ADR produces the evidence and changes nothing.

## Revisit when…

- **The pilot cohort reports** → keep, widen or switch off deliberation on
  the protocol's gates; adjust the ceiling.
- **The ceiling is reached routinely** → lower cadence or the on-stage window
  before raising the ceiling.
- **Repetition or drift metrics rise** → change prompts, models or window;
  never remove the reflex layer's authority.
- **Independent players need to negotiate joint work** → ADR-028's revisit;
  a negotiation schema would extend the intention, not replace consent.
- **Inhabitant attempts show genuine solving over a period** → revisit the
  progress covenant together with ADR-017's boards.
- **Visitor-agent demand exceeds the allowlist** → self-service registration
  for agents, under the same rules as human self-service.
- **A new small model generation ships** → re-cost deliberation and
  reflection; keep the pinning rule.

## Rejected alternatives

- **An open-ended language-model loop per tick.** ADR-022 was right to
  refuse it; it is unbounded in cost and coherence. The reflex layer stays
  authoritative and the model decides one thing per tick.
- **Replacing the FSM.** It is the safety layer, the pacing layer and the
  keyless mode.
- **Letting inhabitants write properties directly.** ADR-031's pipeline is
  the only door for authored canon; actions go through the same acceptance
  APIs as humans.
- **Letting humans delegate to inhabitants.** The covenant; `intervention_api.py`
  already refuses it.
- **A privileged API for external agents.** The covenant that every player
  owns their actions requires that no player has a second set of verbs.
- **Unbounded unsolicited speech.** One line per inhabitant per player per
  visit, opt-out per player.
- **Name-keyed relationships.** Same-name strangers must stay strangers
  (ADR-024).
- **Counting dice-roll solves.** ADR-017's reasoning stands; real attempts
  come first.
- **Turning deliberation on by default.** The owner's economics question is
  answered with a flag and a ceiling, not a bet.
