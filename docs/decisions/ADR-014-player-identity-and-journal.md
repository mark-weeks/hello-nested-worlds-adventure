# ADR-014: Player Identity, a Private Journal, and Public Relationships

**2026-09-12 implementation scope:** [ADR-024](ADR-024-participants-and-active-content.md)
provides the previously assumed durable participant identity, private journal,
selectively published profile, private home bookmark and four preset avatars.
Profiles render the chosen avatar; live-presence avatar parity is still deferred.
Operator credential rotation preserves ownership. Rankings, disposition,
journal sharing, guilds, uploaded avatars and self-service recovery remain
proposals, not implied by this implementation.

**Status:** Proposed (owner-endorsed product direction), 2026-09-07;
pending development-team review and ratification. Implementation pending.
The owner requested a journal and ways for players to form and broadcast an
identity. Bio, badges, home, disposition, guilds, and avatar creation/upload were
raised as possibilities. Their staging and defaults below are recommendations
for team review, not a claim that every possibility was approved for the pilot.
Multidimensional leaderboards and competitive human/agent participation are
covered by ADR-017. Dynamic disposition meters describe independent tendencies,
including orderly and chaotic play. The axes and update rules below are proposals
for review, not accepted morality or scoring formulas.

## Context

A persistent world should remember a participant as more than a name beside
an event. Players need a personal thread through discoveries and relationships,
and a deliberate way to express that identity to other humans and agents.

Private reflection, chosen public identity, and observed public actions have
different meanings. Combining them into one public activity feed would break
the usefulness of a journal and confuse intention with inferred behavior.
Existing passage badges and agent persona profiles are not player achievement
badges or editable player profiles; these capabilities are planned work.

## Decision

Establish four distinct surfaces:

1. **Private journal:** questions, notes, bookmarked places, discoveries,
   personal commitments, and a relevant return recap.
2. **Public profile:** fields the player chooses to publish to participants in
   the shared world, separate from private notes and live location.
3. **Shared world record:** actual contributions and consequences under the
   existing chronicle policy. Profile edits do not rewrite those facts.
4. **Derived recognition:** optional badges, behavioral descriptions, and
   multidimensional contribution leaderboards with explicit evidence and rules,
   introduced after useful contributions have been demonstrated in play.
   [ADR-017](ADR-017-multidimensional-leaderboards.md) governs competitive
   standings; they are distinct from personal disposition or alliance.

### Recommended first scope and later stages

| Capability | Recommended contract | Stage |
|---|---|---|
| Journal | Owner-only by default, editable notes plus history-linked observations and pending consequences. Return recap selects relevant changes without inventing events. | First discovery-and-return experience. |
| Bio and stated goals | Optional, separately publishable fields. Goals are self-description, not mechanically accepted commitments or inferred allegiance. | Basic profile alongside the return loop. |
| Home node | One optional bookmark to an existing visited place, private unless published. It expresses attachment, not ownership, exclusive access, teleportation, or a change to resume/seal rules. Multiple players may share it. | Basic profile. |
| Chosen avatar | Select a preset or configure a simple in-world visual identity. Use consistent presentation in profiles and live presence without changing historical actor identity. | Basic profile. |
| Created/uploaded avatar | Extend the same profile field with a creation tool and then controlled image upload; exact generation provider and upload implementation remain open. | After basic identity is useful; separate implementation. |
| Contribution badges | Evidence-backed recognition for meaningful contributions, with player-selected public display. Preserve cooperative credit; no power advantages or global ranking by raw activity. | After pilot evidence defines meaningful achievement. |
| Contribution leaderboards | Separate standings by accomplishment, with comparable scored opportunities for eligible humans and agents. Recognize legitimate preservation and disruption; no overall engagement total or ranking by alignment extremity. See ADR-017. | Bounded ranking experiment after the first pilot, with Stewardship and Disruption proposed first. |
| Alliance/disposition | Self-declared affiliation is separate from opt-in, explainable observations of recent public play. Proposed bipolar meters describe independent tendencies, not achievement, morality, or faction allegiance. | Experiment after the action/evidence model is tested; axes and formula remain proposed. |
| Guilds | Voluntary associations around shared interests or projects, with explicit join/leave and shared goals. No private copy of the world or exclusive gate on the core experience. | Later, if recurring cooperation demonstrates demand. |

### Private/public boundary

Journal ownership must be enforced by the server using authenticated identity,
including API reads, search, exports, recaps, and updates; hiding a panel is not
access control. Do not return another player's notes in a public profile payload.
Other players and autonomous agents do not receive private journal content.
Agent speech/context and public badge calculations must not read it implicitly.

If sharing is added, let the owner publish a selected excerpt or explicit goal
as a separate public item, with a preview and a clear audience. Do not turn on
sharing for the whole journal. Unpublishing removes that profile item; it cannot
make other participants forget something they already read.

Store editable journal/profile data separately from the append-only world
chronicle. Deleting a private note or replacing an avatar should not require a
history rewrite. Public world actions retain their existing recording policy;
a private journal is not a retroactive promise that existing conversations or
actions are private. Do not import whole conversation transcripts by default.

Use the existing durable account identity internally, not mutable display names
as keys. Expose an opaque public profile identifier rather than invite credentials
or authentication-derived identifiers. The implementation must preserve history
when names or profile fields change and test authorization across two accounts.

[ADR-018](ADR-018-collectibles-and-inventory.md) proposes a separate collection
of keepsakes and usable items, with optional selected profile display. A private
journal entry or published item image grants no inventory ownership or ability.
The collection proposal does not change the home bookmark's access contract.

### Recognition, disposition, and relationships

Badge criteria should identify a contribution and its effect, not reward repeated
clicking. Derive awards from authorized evidence, version their rules, preserve
cooperative credit, and define how corrections/redaction affect public evidence.
Merely viewing Wayback must not gain a new chronicle write as a badge shortcut.

### Proposed dynamic disposition meters

Keep **disposition** (the approaches a participant has demonstrated),
**achievement** (verified accomplishments), and **relationships** (a particular
inhabitant's or faction's response) distinct. Do not convert every leaderboard
dimension into an alignment axis: ignorance is not a useful opposite of Discovery,
and lack of ingenuity is not a play style to cultivate. Cooperation can serve
both preservation and disruption; a group of rebels is still cooperating.

| Candidate axis | One pole | Other pole |
|---|---|---|
| Change | Preservation: sustain or restore an existing arrangement. | Disruption: destabilize, dismantle, or replace an arrangement. |
| Working with others | Coordination: pursue an objective through agreed joint action. | Independence: choose and pursue an objective autonomously, including explicit competing goals. |
| Uncertainty | Caution: favor understood, predictable consequences. | Daring: choose an explicitly uncertain experiment or intervention. |

These are proposed, independent descriptors; neither end is inherently better.
Independence does not mean hostility, coordination does not imply order, and
disruption need not be altruistic. An authored action can express several facets,
one, or none. Do not force solo play, silence, absence, or an ambiguous action into
a negative category. Only score a facet when the situation provides evidence for
that distinction. No single axis claims to explain all kinds of chaos or rivalry.

Recommend a readable slider for each supported axis, with the underlying evidence
for **both** poles retained. A bounded balance derived from recent eligible choices
is a candidate, not a committed formula. A participant who often preserves and
often disrupts must be distinguishable from someone with no qualifying history.
Show mixed evidence as mixed; show insufficient evidence as unknown. Do not label
either automatically neutral, moderate, or morally balanced.

Derive movement from authored, contextual classifications of executed public
choices, with transparent explanations. A generic verb such as `mend` or `break`
does not establish intent: dismantling a mechanism might preserve a larger
system. The authoring rule must state the reference arrangement and perspective.
Do not infer actual motives, personality, morality, or loyalty from a score,
private notes, dialogue sentiment, or an opaque model judgment.

Bound weight per eligible situation opportunity; deduplicate retries and propagated
effects so repetition cannot push a meter to its extreme. Let subsequent meaningful
choices change a disposition without wiping history. Specify the evidence window,
minimum support, weighting, and classification version before testing. If evidence
ages out, confidence can fall to unknown; inactivity must not manufacture movement
toward the opposite pole or award achievements. Public display remains opt-in.
Disposition need not wait for successful achievement: an executed risky attempt
can evidence daring even when it fails, if its authored rule says so. Leaderboard
credit still requires the qualifying outcome under ADR-017.

Never reward a participant simply for being maximally aligned. For example, a
profile might read **disruptive, coordinated, daring**, with strong Discovery and
Ingenuity achievements. Another might show mixed preservation/disruption evidence
and high achievement in both. Neither profile receives a global virtue score.

Relationships can respond differently to the same event: a keeper may resent
a mechanism's destruction while another inhabitant welcomes it. Any such response
must use authorized events the character could know, with explicit authored
consequences, not omniscient access to a private profile or journal. Self-declared
alliance and actual guild membership remain separate. Mechanical access/power
rewards for alignment extremes are outside the first experiment.

Use a compatible vocabulary of names, homes, goals, and public contributions for
humans and agents. Preserve existing live-presence addressability and the
chronicle's lack of human/agent taxonomy. Do not add profile classifications to
Wayback or grant agent puzzle attempts human solve/constellation credit.

Uploaded avatars require bounded formats and sizes, safe image decoding and
metadata removal, replacement/removal behavior, and moderation before public
display. Public bios/goals need the existing input-boundary discipline. These
are implementation criteria for the requested publishing surfaces, not reasons
to delay a private journal or preset avatars.

## Trade-offs accepted

- Selected public expression gives less ambient social data than publishing
  everything, but lets players adopt a meaningful identity without exposing
  private reflection.
- Recognition can support belonging but also distort play toward farming;
  defer criteria until valuable contributions are visible in the pilot.
- A home can create attachment without the scope and exclusion costs of land
  ownership, housing construction, or fast travel.
- Guilds can deepen relationships but fragment a small cohort; start with
  shared situations and personal goals before organization mechanics.

## Revisit when…

- Players repeatedly want to share particular discoveries: add selected journal
  sharing before considering any broader visibility model.
- Players recognize each other's contributions and request persistent groups:
  define guild governance, agent membership, and group permissions explicitly.
- A disposition experiment changes behavior through labeling or encourages
  farming: revise or remove that display rather than treating it as identity.
- Account recovery/credential rotation ships: migrate profile and journal keys
  through the existing durable identity contract, never by matching names.

## Rejected alternatives

- A public journal/activity feed by default or private notes stored in public
  chronicle rows.
- A universal good/evil, trustworthiness, or allegiance rating generated from
  dialogue or hidden heuristics.
- Badges that confer puzzle authority, erase cooperative credit, or make early
  arrival the only path to recognition.
- Mandatory guilds, property ownership, uploads, or a full avatar generator as
  prerequisites for the first meaningful identity experience.
