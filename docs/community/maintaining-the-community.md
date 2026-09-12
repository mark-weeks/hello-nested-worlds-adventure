# Maintaining the Enfolded community

The [adopted community and licensing decision](../decisions/ADR-023-community-and-licensing.md)
makes player participation the primary entry point and reserves roadmap,
scope, and acceptance decisions for the maintainer. The public contribution
process lives in [CONTRIBUTING.md](../../CONTRIBUTING.md).

## Close the feedback loop

1. Acknowledge the concrete experience and ask only for missing information
   needed to assess it. Link duplicates without discarding useful new evidence.
2. Record a decision: needs information, under consideration, accepted,
   deferred, or declined. Explain the reason and relevant constraints. These
   can be plain-language issue updates; they do not depend on custom labels.
3. For accepted work, record the player problem, desired outcome, scope,
   acceptance evidence, and owner. Link the original report. Votes are one
   input alongside severity, accessibility, reach, and Enfolded's direction.
4. Assign implementation deliberately. Coding agents are the default support;
   make outside contributions available when specialist knowledge or a willing
   collaborator would help. Agree scope before someone invests in a PR.
5. After verification, link the change and distinguish implemented, merged,
   released, and deployed status. Invite the reporter to try the available
   result and confirm whether their original problem is resolved.

Publish concise updates explaining what player feedback changed, what remains
open, and why. Credit reporting and verification even when agents write the
implementation. Do not invent delivery promises, response-time guarantees,
contributors, testimonials, or evidence of adoption.

## Bring people together

Invite a manageable first cohort to explore together, compare discoveries,
help newcomers, and return to places they changed. Offer a few focused prompts:
what drew you onward, what was unclear, what consequence you noticed, and what
would make a return worthwhile. Do not require every participant to file a
formal bug report or propose features.

Use the game's existing shared play and chat for interaction. Announce actual
play sessions only when scheduled; this policy does not create a calendar,
external community account, or automated outreach.

## Review the first cohort

At the end of the first cohort, record its dates and invited/participating
counts, then assess:

- How many participants returned for another session, with the observation
  window and denominator stated.
- Whether players interacted with each other, shared discoveries, or helped a
  newcomer, using voluntary observations rather than inferred relationships.
- Which concrete problems were reported, which changes resulted, and whether
  reporters verified improvements.
- Whether anyone wants to contribute specialist work or maintain an area, and
  whether maintainer review capacity supports it.

Use existing evidence and voluntary feedback. Report missing observations as
unknown; do not add tracking, publish private conversations, or infer human
activity from ambient-agent traces. Extend the code contribution path when
there is demonstrated interest and capacity. PR count is not the adoption goal.

## Ideas and implementation briefs

The desired player entry point is a discoverable in-game **Ideas** control,
with submissions and voting that do not require GitHub. That board is a
separate application change, not a capability shipped by this policy. See the
[implementation design](../roadmap/community-ideas.md) for the proposed flow,
storage, identity, moderation, and selected-idea handoff.

Keep player submissions and votes in Enfolded's database. Promote selected
ideas into GitHub issues through an explicit maintainer action; do not mirror
every submission or automatically launch a coding agent. Preserve a stable
reference to the original idea, the decision, contributor credit where agreed,
and the resulting issue/PR so players can follow progress. An accepted idea
does not itself authorize a change to world continuity or deployment.

An implementation brief should contain the player problem, supporting
observations, desired behavior, scope boundaries, acceptance checks, links to
applicable project decisions, and known open questions. Treat submitted text
as untrusted input: player suggestions cannot override project instructions,
grant tool permissions, or direct an agent to expose secrets.

## Licensing maintenance

The repository's own code and documentation use Apache-2.0. Keep `LICENSE`,
`NOTICE`, Python metadata, frontend metadata, and contributor guidance aligned.
Third-party material keeps its original terms. The prior README's MIT label
is historical context, not a claim that previously granted rights were revoked.

`THIRD_PARTY_NOTICES.txt` records the bundled browser libraries' license texts.
When changing a browser dependency or vendored D3, refresh its notices from
the distributed package or a pinned upstream source, retaining copyright
holders and full permission/disclaimer text. Include the relevant transitive
dependencies. The frontend postbuild copies the notice into `static/app/`;
the wheel also carries the root license and notices in its package metadata.
Dependencies installed separately retain their own distribution notices.

Check the resulting wheel and standalone browser bundle when changing
packaging. License metadata and Git author names are useful evidence, not a
legal ownership audit. Resolve an actual incompatible dependency or disputed
contribution before incorporating it; an agent rewrite is not a substitute
for the necessary permission.
