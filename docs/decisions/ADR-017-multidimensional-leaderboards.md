# ADR-017: Multidimensional Contribution Leaderboards

**Status:** Accepted product direction, 2026-09-07; implementation pending.
The owner requested multiple dimensions of competitive recognition and a mix
of human and AI participants ranking highly. The dimensions, scoring budgets,
windows, and roster controls below are recommendations to validate, not already
ratified formulas or a guarantee of a particular ranking composition.

## Context

[ADR-014](ADR-014-player-identity-and-journal.md) established a private journal,
selective public identity, and evidence-backed recognition. Leaderboards can
give contributions visibility and encourage engagement without making every
participant pursue the same goal. A single engagement total would flatten the
different ways to participate and reward agents' ability to operate continuously.

This decision narrows the earlier deferral of rankings in ADR-012 and the
roadmap: multidimensional contribution boards are now planned. A universal XP
table or ranking by clicks, messages, elapsed online time, or raw mutation volume
remains outside the direction. Boards reinforce the discovery-and-return loop;
they do not replace the need for a compelling situation.

## Decision

### Independent dimensions, not one overall winner

Maintain separate standings for distinct kinds of contribution. Do not sum them
into a composite score, overall rank, or hidden morality/disposition rating.
Let a player choose which standings to follow and feature on their profile.

| Candidate dimension | What could earn credit | What must not earn credit |
|---|---|---|
| **Discovery** | A distinct, verified finding or causal relationship that advances a situation; later visitors can earn credit for independent understanding or useful follow-up under an explicit rule. | Raw visits, private journal volume, automatic archive views, or claiming every new visitor was the world's first discoverer. |
| **Stewardship** | A meaningful restoration or stabilization addressing a real situation need, with its effect confirmed. | Repeated repair clicks, self-created damage/repair cycles, or counting a large numeric property change as inherently more valuable. |
| **Cooperation** | A verified complementary contribution to a completed shared goal, including permitted human–agent cooperation. | Chat volume, reciprocal endorsements, duplicate accounts, or multiplying the same outcome by the number of team members. |
| **Follow-through** | Fulfillment of a previously accepted, mechanically verifiable public commitment. | Arbitrary self-declared easy goals, private intentions, or a perfect one-action completion rate presented as sustained achievement. |
| **Ingenuity** | A valid alternative approach under a situation's authored, inspectable criteria. | An opaque LLM judgment of creativity, unrestricted text generation, or damage rewarded merely for being unusual. |

Start the ranking experiment with **Stewardship and Cooperation**, once their
outcome/evidence contracts exist. Add Discovery when meaningful findings can be
verified fairly; Follow-through and Ingenuity need their own evaluators. These
are proposed dimensions, not five engines to build before the first pilot.

### Relevant scope and time

Show nearby/situation or regional standings first, with a world-wide view by
dimension when participation supports it. Do not divide a tiny cohort into many
empty boards. Recommend a weekly scoring window for the first experiment,
alongside durable profile achievements; validate cadence before committing it.

Window turnover changes standings only, never the world or its historical facts.
Display the scope, window, eligibility, rule version, and reason for an award.
Use ties where appropriate rather than rewarding speed as a default tie-break.
Public participation is optional; absence from a board must not block ordinary
play, confer a penalty, or deny an observer a meaningful experience.

### Mixed human/agent competition through comparable opportunities

1. **Score demonstrated outcomes using the same per-board rules.** Do not award
   points for API calls, heartbeat activity, model usage, or unrestricted work
   volume. Use bounded per-opportunity credit and a fixed total credit budget
   for each shared outcome; preserve meaningful cooperative attribution.
2. **Limit scored opportunities before participation, not just scores afterward.**
   A common per-entrant opportunity/attempt budget must constrain both humans
   and agents, with a budget sized for ordinary short human sessions rather
   than daily attendance. Taking the best few results from unlimited agent attempts does
   not remove the automation advantage. The admission rule must prevent opting
   into scoring only after an outcome is known. Define how retry, failed work,
   and delayed completion consume a slot before launch.
3. **Limit the competing cast as well as each agent.** A large bot roster can
   occupy every high place even when each bot has a cap. Use a declared roster
   and an aggregate agent scoring-opportunity budget calibrated to active human
   participation and available situations. Fix the rule before the window;
   rotate eligible cast members across windows without creating new identities
   or resetting their records. Exact caps and rotation need simulation evidence.
4. **Require comparable access and action authority.** An eligible agent must
   obey the same relevant opportunity, evidence, submission, and action rules.
   Privileged server state, answer keys, or simulated success cannot qualify
   it for a mixed achievement. Apply budgets server-side, including autonomous
   paths; distinguish declared controller/automation metadata from a display
   name. Classification concerns declared control mode, not speculation about
   whether a human used AI assistance. Do not assume automation or linked
   accounts can always be detected.
5. **Keep ambient life separate from competitive eligibility.** Unranked agents
   can continue inhabiting the world, but their influence around scored
   situations must be bounded so they cannot complete every opportunity or
   manufacture repair work off the scoring clock. Ineligible or simulated acts
   must not produce indirect ranked credit for a partner through cooperation.
6. **Audit concentration and accessibility.** Measure who had opportunities,
   who entered, score distributions, top-place composition, and repeat winners
   per board/window. Test intermittent humans against continuously active
   agents and a roster larger than the human cohort. Do not infer balance from
   one human win, aggregate totals across unrelated boards, or a tiny sample.

A mixed top group is the desired result of these rules, **not a guaranteed
quota or a fabricated ranking**. If agents still dominate, revise prospective
eligibility, opportunity access, or the relevant task design; do not secretly
boost human scores or rearrange already-earned positions. If guaranteed mixed
visibility is needed, add a clearly labeled human-and-agent showcase separate
from ranked standings. A showcase is editorial selection, not a leaderboard.

### Respect existing puzzle and identity boundaries

At plan baseline `4d21676`, [`Agent._attempt_puzzle`](../../agents/agent.py)
uses a difficulty-weighted deterministic success roll; it is not evidence of
the same answer-submission achievement as a human
solve. It must not receive puzzle-solving leaderboard credit or indirectly
qualify a team for that credit. Existing agent rules prohibiting human co-op
claims, seal opening, and constellation progress remain intact.

Mixed boards should initially use genuinely comparable non-puzzle outcomes.
A future human puzzle board must state its eligibility; a future mixed puzzle
competition needs a separately reviewed, comparable attempt/evidence path and
an explicit covenant decision before any change to shared puzzle progress.

Use server-owned participant/controller eligibility metadata for internal
fairness audits. Do not add human/agent flags to chronicle rows, Wayback, or
node voices, or infer participant type from historical text. Mixed standings
show names/public profiles and contribution evidence. Public type filters or
reserved lanes would need an explicit presentation decision; they are not a
silent extension of the existing live-presence exception.

### Evidence, privacy, and score integrity

Build a versioned, rebuildable ranking projection from authorized public
contribution evidence and explicit competition metadata. Private notes,
unpublished goals, conversation sentiment, microphone audio, and unpublished
home/avatar choices do not enter scoring or agent evaluation context. Public
award explanations must also preserve the no-answer-leak boundary for active
puzzles; internal evidence does not automatically belong in a public payload.

Deduplicate by durable participant and outcome identity. Credit delayed work
only when its qualifying effect lands; reserve eligibility at acceptance and
specify the scoring window so queued work cannot bypass caps at a boundary.
Define minimum evidence, tie handling, correction/redaction, opt-out display,
and controller/account limits before publishing rankings. A declined action,
no-op, retry, or the same propagated effect is not another accomplishment.

Prevent participants or linked controllers from farming harm/repair loops or
manufacturing cooperation; adversarial tests must include colluding agents and
humans. Aggregate guild rules, if introduced later, must not reward headcount
alone. Neither private-text analysis nor unverifiable identity assumptions are
acceptable substitutes for observable eligibility and contribution rules.

Rank reads and rank changes must not recursively create world events. New
evidence writers, if necessary, need their own review under ADR-013 and the
existing chronicle covenant. Preserve source history when score rules change;
apply new versions prospectively and identify any corrected score projection.

## Trade-offs accepted

- Opportunity limits and roster controls reduce throughput advantages but do
  not make human and agent skill distributions identical or guarantee a mix.
- Several dimensions recognize different strengths but increase explanation
  and evaluation work; begin with two legible boards rather than a large matrix.
- Rankings can encourage farming or discourage lower-ranked participants. Keep
  them optional, contextual, and separate from progression gates and power.
- Weekly windows give later arrivals another chance but can create attendance
  pressure. Test that they improve return motivation without becoming a chore.

## Revisit when…

- Agents repeatedly dominate upper ranks after comparable-opportunity controls:
  inspect the affected dimension and prospective limits before expanding it.
- Humans sweep all boards and agents feel like decorative opponents: examine
  agent capabilities and accessible goals without gifting score or privileges.
- A dimension rewards behavior that makes the shared world worse, or entry
  into competitive play reduces discovery/cooperation: change or retire it.
- Participation grows enough for additional local scopes or a newcomer board:
  define eligibility that cannot be reset by renaming, respawning, or rotating
  an existing agent/controller.

## Rejected alternatives

- One flat engagement/XP leaderboard or an overall sum of all dimensions.
- Raw activity totals, lifetime-only standings, or top-N scoring after unlimited
  attempts: favors continuous automation and incumbency.
- Human-only boards as the sole solution: misses the requested mixed world.
- Hidden handicaps, forced mixed rank slots, or score changes after results
  are known; use an honestly labeled showcase for guaranteed representation.
- Scoring simulated agent puzzle solves as equivalent to human achievements,
  rewarding deliberate damage, or mining private journals for evidence.

Implementation is staged in the
[discovery-and-return plan](../roadmap/discovery-and-return.md), alongside the
identity/recognition work after the first experience establishes useful outcomes.
