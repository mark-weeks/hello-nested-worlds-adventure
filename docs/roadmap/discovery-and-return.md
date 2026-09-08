# Discovery, Identity, and Return: Delivery Plan

**Date:** 2026-09-07. **Baseline:** `4d21676456389a4531438bd64cf8c01c8ea0272d`
(merged assessment PR #92). **Status:** product direction endorsed; planning
documents prepared for team review. No implementation milestone below has
shipped merely because this plan exists. No dates or staffing commitments are
assumed.

## Outcome and scope

Deliver one first session that gives a player something they want to investigate,
and one return to the same world that reveals a personally meaningful consequence.
Players should be able to develop an identity and relationships with places,
humans, and agents while keeping private reflection distinct from public identity.

This plan becomes the next product sequence after the four shipped pre-launch
batches. It does not undo them, waive staging/restore requirements, or treat
launch as a freeze on future development. Keep one canonical world, stable
identity, append-only historical facts, and additive change.

## Decision register and authority

All seven records are **Proposed**, pending review and ratification. Owner
endorsement or a requested direction is identified below separately from ADR
acceptance. Record the scope and date when a decision is ratified; leave unadopted
contracts and candidates marked Proposed. Each implementation still needs its
own review and compatibility evidence.

| Record | Status and what it settles |
|---|---|
| [ADR-012: discovery and return](../decisions/ADR-012-discovery-and-return.md) | Owner-endorsed product direction: investigation in an open world, a bounded first situation, responsive inhabitants, and a meaningful return. The example story, pacing, and scene-interface performance are testable hypotheses. |
| [ADR-013: versioned situations and delivery](../decisions/ADR-013-versioned-situations-and-delivery.md) | Proposed implementation contract: reliable accepted work, typed action semantics, preserved active instances, and changes to existing places through events. Exact persistence design and new write paths remain subject to implementing-PR review. |
| [ADR-014: player identity and journal](../decisions/ADR-014-player-identity-and-journal.md) | Identity/journal direction endorsed. First-release defaults and staging remain recommendations. The owner's opposing-meter idea is developed as a proposed multidimensional disposition model, distinct from achievement and faction relationships; badges, meters, guilds, and avatar creation/upload are not implied pilot requirements. |
| [ADR-015: referential puzzles](../decisions/ADR-015-referential-puzzles.md) | Owner-requested content direction: occasional relevant fictional/nonfictional references. No live bank allocation or active answer change is approved by this plan. |
| [ADR-016: optional spoken interaction](../decisions/ADR-016-optional-spoken-interaction.md) | Owner-requested capability direction: speech input and playback alongside text. The staged interaction is recommended; vendor, budget, and support choices need evidence. |
| [ADR-017: multidimensional leaderboards](../decisions/ADR-017-multidimensional-leaderboards.md) | Owner-requested recognition direction: multiple dimensions with humans and agents able to rank highly. The proposal includes legitimate disruptive goals, starting with Stewardship and Disruption. Dimensions, caps, admission, and windows remain experiments; alignment extremity is not achievement and a mixed top group is not a hidden quota. |
| [ADR-018: collectibles and inventory](../decisions/ADR-018-collectibles-and-inventory.md) | Exploratory proposal in response to the owner's collection idea: keepsakes, cross-scale components, and useful assembled artifacts. One small assembly is a candidate for M0 review, not an accepted M5 requirement; hyperleaping and shared projects are later candidates. |

The owner sets product direction; development-team review covers implementation
and persistent contracts. Each implementing PR must identify its applicable
decision, acceptance evidence, compatibility plan, and irreversibility check.
**No auto-merge.** An explicit instruction to merge one PR does not authorize
merging later PRs automatically.

## Milestones and dependency order

These are deliverable boundaries, not a requirement to put every milestone into
one large PR. Keep fixes and new write paths independently reviewable. Ownership
below is by role, not an assignment to unconfirmed individuals.

| Milestone | Work and dependency | Acceptance evidence | Accountable role |
|---|---|---|---|
| **M0 — Define and review the experience** | Refine ADR-012's working brief into actual existing places, clues, two interventions, shared conflict handling, an inhabitant commitment, and both aftermaths. Review ADR-013. Run alongside M1–M4. | A walkthrough explains the initial question, how clues support inference, what each intervention changes, and what late/returning visitors can do. Mark hypothesized content separately from shipped rules. | Product lead with engineering/design. |
| **M1 — Recover accepted consequences** | First reproduce process death, claim/application failure, duplicate delivery, concurrent workers, initial scheduling gaps, and restart recovery. Then harden both causal and maturation delivery. | No lost accepted work or duplicate effects in these cases; continuation scheduling and terminal outcomes remain inspectable. Rehearse pending work through backup/restore on disposable state. | Backend engineering. |
| **M2 — Make delayed choices coherent** | Build on M1. Define contribution/coalescing/exclusive policies, saturation, and explicit no-ops. Preserve legacy pending work and pin new operation semantics. | Endpoint tests with multiple participants prove acceptance and landing behavior. Direct queue probes are characterization, not the required endpoint regression. | Product lead and backend engineering. |
| **M3 — Make history intelligible** | Independent correction: preserve actor/origin and distinguish an action from an arriving effect across existing presentation surfaces. Can land during M1. | A player can trace a consequence to its actual source. Shared narration tests cover historical rows without rewriting them or adding actor taxonomy to Wayback. | Frontend engineering. |
| **M4 — Keep inhabitants responsive** | Separate known places from relevant revisits; bound total work; use current puzzle epochs; retain useful memory. Review how autonomous actions use M1/M2. | Partially/fully explored worlds, changed places, renewal, and repeated ticks produce appropriate bounded behavior. No memory clearing, empty-log dependence, or agent claim on human puzzle progress. | Agent/backend engineering. |
| **M5 — Build the first situation** | Requires M0 and the relevant M1–M4 contracts. Use 8–15 existing places at 3–4 scales, one inhabitant, one earlier trace, two interventions, and a visible delayed consequence. Implement only the versioned situation/commitment support required. | Both branches work end to end, disagreement/late requests have explicit outcomes, and a late visitor can investigate the aftermath. Validate navigation, keyboard, mobile, and rendering fallback in `/app` before changing the invite default. | Product lead with frontend/backend engineering. |
| **M6 — Return and basic identity** | Build the private journal/recap and the recommended basic profile: optional bio/goals, home bookmark, and preset/simple configurable avatar. Can develop its shell alongside M5, using real consequences for final validation. | Two-account tests enforce journal privacy and selected profile visibility; notes stay out of public/agent context. Return recap links to real changes; name/avatar/home edits preserve identity and access rules. An inhabitant honors one recorded commitment. | Frontend/backend engineering with product review. |
| **M7 — Pilot and continuity update** | Rehearse on disposable staging, then run 8–12 invited participants through the same continuing pilot world and one additive situation update. Declare its staging/production status before collecting history. | Measure motivation, causal understanding, return, relevant change, and update compatibility. Do not wipe a world promised to participants as persistent. Complete existing operational launch gates before production. | Product/research lead and operations. |
| **M8 — Expand only demonstrated value** | Use M7 evidence to choose the next situation, recognition experiments, or social capability. Generalize repeated authoring patterns after multiple useful examples. | A specific observed need justifies each addition; do not make every item in the identity idea list a prerequisite for launch. | Product lead with development team. |

M0 and M3 should not wait for infrastructure completion. M1 is the first
engineering task, beginning with failure tests. M2's semantic decisions should
inform M1's design early so the two PRs do not introduce incompatible contracts.
M5 must consume existing art, sound, history, puzzles, and navigation; it is not
a renderer rewrite, an unrestricted agent platform, or a new world generator.

## First-situation review checklist

Before implementing its permanent transitions, specify:

- Which existing nodes and relationships carry the mystery, and how a new
  visitor reaches them without violating seals or per-node difficulty.
- What is perceptibly unusual on arrival; what an observer, conversational
  player, and active investigator can each learn.
- The evidence for both interventions, their benefits/costs, preconditions,
  and handling of competing or already-resolved requests.
- The inhabitant's goal and one executable promise, with explicit acceptance,
  fulfillment, failure, and public/private information boundaries.
- An immediate acknowledgment, one within-session consequence, and a later
  question whose timing is a hypothesis to test.
- What changes for a returning participant and a first-time late arrival;
  neither needs a private reset or a false first-solver claim.

Review the quiet/redirect brief for a real difference between preserving an
arrangement and disrupting it. Give each route intelligible stakes, costs,
affected inhabitants, and conflict handling; both cannot simply be equivalent
ways to help the same keeper. Record enough contextual evidence to distinguish
the choice and outcome without building disposition meters in M5. If the story
cannot support legitimate opposing goals, revise it before any ranking experiment.

ADR-018 proposes a collection variation to review here: three discoveries from
different scales assemble into one instrument that helps explain and affect the
situation. Compare it with the simpler experience before adding it to M5. If it
does not strengthen the mystery, defer it until after M7. Specify item ownership,
late-entrant access, recipe continuity, and the artifact's actual benefit if chosen.
This does not move a general inventory/crafting engine ahead of M1 or add a pilot
gate. Travel abilities follow evidence of friction and review of existing jumps.

## Identity stages

The first release makes a person recognizable and gives them a private thread
through play. It does not need a reputation economy or guild administration.

1. **M6:** private journal; selective public bio/goals; optional home bookmark;
   chosen preset/simple configurable avatar. Publish only selected fields.
2. **After M7:** evidence-backed contribution badges and an ADR-017 ranking
   experiment, with Stewardship and Disruption proposed first, plus selected
   journal sharing if players need it. Define credit for opposing/shared goals,
   versioned award rules, and comparable human/agent opportunities before display.
3. **Later experiments:** explainable, opt-in disposition meters under ADR-014;
   avatar creation and upload; guilds with explicit membership and projects.
   Confirm demand and define each contract separately. Do not infer alliance from a private journal.

All ideas remain recorded in ADR-014/017 even when deferred. Disposition is a
description of observable play, not a global rating of character or trust.
Contribution standings do not collapse these identity dimensions into one score.
Proposed meters are Preservation–Disruption, Coordination–Independence, and
Caution–Daring. Retain evidence for both poles, distinguish mixed from unknown,
and test the labels before choosing a numerical formula. Extremity earns no rank.

### Ranking experiment after the first experience

Build only the outcome evidence needed by the first two boards. Keep rank
calculation outside permanent world facts and private journals. Before public
standings, run a simulation/replay and then a bounded opt-in cohort experiment:

- Compare intermittent human play with continuous agents, including human/agent
  roster ratios such as 1:1 and 1:5 and periods with very few humans. These are
  test scenarios, not predictions of the live population.
- Test precommitted scored-opportunity caps, aggregate agent-roster limits,
  retries, delayed outcomes across window boundaries, tied results, late entry,
  and controller-linked repair/cooperation farming. Top-N results from unlimited
  attempts are not a substitute for an opportunity budget.
- Require evidence that both classes can attain high ranks on the mixed boards
  under comparable constraints. Track top-group composition per dimension and
  window together with entrant/opportunity denominators; do not guarantee or
  secretly force a mix. Fix the top-group definition, minimum evidence, caps,
  and evaluation duration before running the experiment.
- Exclude simulated agent puzzle success and indirect credit from ineligible
  acts. Preserve existing human puzzle-progress rules and historical actor
  ambiguity.
- Include preserving and disruptive goals, coordinated rebels, independent
  caretakers, failed risky attempts, and mixed/insufficient disposition evidence.
  Check comparable opportunity access for both routes, contested transitions,
  late arrivals, and collusive destruction/repair. Neither fictional instability
  nor a high disruptive tendency alone is a failure or an achievement. Assess
  whether both styles produce legible, playable consequences without prohibited
  interference; do not require an equal number of winners from each style.
- Compare engagement and perceived fairness with the unranked experience. Pause
  expansion if rankings encourage chores, farming, or withdrawal from discovery.

Version prospective rule changes. If guaranteed mixed visibility is desired,
use a separately labeled showcase instead of rearranging earned rank positions.

## Separate content and interaction tracks

These owner-requested directions are recorded independently of the critical
discovery-and-return sequence. They may be tested alongside it when useful,
but neither is a prerequisite for M1 or automatically a launch gate.

| Track | First deliverable | Gate before broader release |
|---|---|---|
| **P — Referential puzzles** | Author a small candidate set from ADR-015's themes; test at least one reference with both familiar and unfamiliar players. Include a verified source and explicit answer/alias policy for each actual question. | Contextual relevance, ambiguity, optional access, no-answer-leak and per-node difficulty checks; retain ecology gates and preserve active instances through versioned rollout. |
| **V — Spoken interaction** | Compare bounded speech input and playback options on target devices; prototype editable transcript → existing text path → optional spoken response. | Measure recognition, correction, latency, costs, permissions, privacy/retention behavior, and text fallback; prove no unsubmitted utterance mutates the world. Choose providers from current official documentation and the live spike, not assumptions. |

## Proposed pilot decision gates

Agree these before recruiting; they are product targets, not validated industry
benchmarks. Report counts and denominators, prior familiarity, invitation timing,
reminders, and reasons for returning or not returning. A small cohort gives
directional evidence, not a statistically stable retention estimate.

| Question | Proposed gate |
|---|---|
| Does entry create curiosity? | At least 8 of 10 first-time participants can name something they want to investigate within two minutes without a facilitator supplying an objective. |
| Are consequences understood? | At least 7 of 10 participants who intervene can explain one consequence of their action. Report observers separately rather than forcing an action to count them. |
| Is there a reason to return? | At least half choose to return within seven days without a research reminder supplying their reason; capture what they came back to do. |
| Is return personally relevant? | At least 7 of 10 returning participants recognize a relevant change. If too few return, report the shortfall and collect more evidence rather than claiming this gate passed. |
| Can the world evolve safely? | No lost/duplicated effects in the specified failure cases; no stranded active puzzle, broken identity/access, exposed private note, or rewritten historical delta through the trial update. |

For cohorts other than ten, use the corresponding proportions and report actual
counts. Add lightweight research/operational measurement outside permanent world
canon; do not add a chronicle row for every page view or journal read.

## Deferred scope and reopening triggers

Defer additional scales, broad frontier growth, a universal quest engine, global
XP/composite rankings, land ownership, mandatory guilds, unbounded agent autonomy, bulk
generated trivia, and an infrastructure rewrite. Reopen each only when measured
experience, authoring effort, load, or participant demand identifies the need.

If players cannot explain a reason to return, revise the situation and its
consequences before adding these systems. If the experience works, introduce a
new situation in familiar geography and extract only the reusable parts it needs.
