# Discovery and return pilot protocol

**Revision:** 2026-10-03, protocol 2. Supersedes the scripted signal-choice study;
old observations remain protocol 1 and must not be relabeled. No human research
has been conducted by this readiness batch. Hosted installation and recruitment
remain separate authorized steps.

## Scope and venue

First watch 2–3 newcomers on disposable staging. Tell them that its history is
temporary. Fix entry, navigation, acceptance, and consequence-recognition failures
before the larger study. This is not the seven-day return cohort.

Then invite 8–12 people to one continuing seed-382 world for seven days per person.
Declare whether this is a retained research world or the permanent production
world before the first session. Never promise persistence and subsequently wipe it.
Production begins only after the [operational gates](../infrastructure/fly-deployment.md#8-launch-window)
pass. Use the explorer as the invite default under ADR-005; record use of the scene
alternate. Record browser/device and prior familiarity. Local Chromium evidence
does not establish mobile Safari or assistive-technology support.

Test navigation, Speak, Puzzle, Act, journal/recap, and Ideas. Do not install the
retired signal situation, impose a shared decision window, force another player
to act, or require participants to forecast hidden consequences. Optional sound
is available; spoken input/playback and new progression systems are not required.

Before recruitment, record the facilitator/research owner, observation dates,
supported devices, chosen client, consent wording, and retention/deletion date in
the restricted research record. Arrange some overlap for encounters without
turning return reminders into evidence of voluntary return. Do not send invites
until the operator confirms the correct world and its recovery status.

## Session script

Explain: “You can explore, speak with places and travelers, solve puzzles, and
attempt changes. Clear actions commit when submitted; what happens can depend on
what others do. Participation and observation are voluntary.”

1. Observe the first two minutes without supplying an objective. Record whether
   the person finds or articulates a question. If they need help afterward, offer:
   “Find a place you are curious about, and decide whether you want to change it.”
   Record the prompt; do not count prompted curiosity as unprompted discovery.
2. After someone chooses to act, ask what they tried to do. Once an outcome is
   visible, ask what actually happened and where they found that evidence.
   A pending consequence is unknown, not a failed comprehension observation.
   A correctly recognized no-material outcome counts as understanding.
3. Observe optional journal/bookmark and Ideas use. Do not require private note
   contents to be shared. Ask what, if anything, they would want to revisit.
4. Let the seven-day return window run. Count voluntary returns separately from
   prompted ones. Arrange a return interview only after an independently observed
   return if it is to count as unprompted; otherwise record the reminder.
5. On return, ask what changed and what they want to do next. Separate observed
   behavior and the participant's explanation from the facilitator's interpretation.

## Observation record

Keep pseudonymous research outside the repository and world database. Store no
invite credentials, private journal text, or real-world identifying details in the
report input. Journal access is not research consent. Keep contextual evidence in
a separate restricted record with the same retention decision.

| Field | Evidence for true | Denominator |
|---|---|---|
| `curiosity` | Pursues or articulates a question in the first two minutes without an objective supplied by the facilitator. | Observed first sessions. |
| `understood_action` | Explains the attempt they submitted, without needing an outcome forecast. | Acting participants asked about their attempt (`acted: true`). |
| `understood_consequence` | Explains an actually observed consequence, including partial/no-material results, and identifies its evidence. | Acting participants with an outcome available and a comprehension observation. |
| `unprompted_return` | A second visit within seven days, `reminded: false`, and a participant-supplied reason. | Participants whose full seven-day window is complete. |
| `useful_return` | Recognizes a relevant change and identifies or performs something they want to do next. | Participants with an observed return session (`observed_return: true`). |

Use false for an observed negative, null/missing for unknown or ineligible. Keep
`unprompted_return` null until `return_window_complete` is true, even if an early
return is recorded in the evidence notes. Someone who only observes is not a failed
actor. A return without an interview has unknown useful-return evidence. A return
after a research reminder is not unprompted. “Active on two days” is an operational
count, not this product test.

Create one row per participant, not per session:

```json
{
  "protocol_version": 2,
  "participants": [{
    "participant": "P01",
    "curiosity": null,
    "acted": null,
    "understood_action": null,
    "understood_consequence": null,
    "return_window_complete": false,
    "unprompted_return": null,
    "reminded": null,
    "observed_return": null,
    "useful_return": null
  }]
}
```

Run `python scripts/pilot_report.py /absolute/path/to/observations.json`. It reads
only that file, reports yes/observed/unknown for each metric, and never reads notes
or changes the world. Protocol 2 rejects the old `understood_choice` field and
ineligible observations; legacy list input is still reported as protocol 1.
Protocol 2 also rejects extra top-level fields so evidence notes cannot be attached
to the report envelope. This does not replace the research owner's responsibility
to use pseudonyms and exclude identifying details. Do not pool the two protocols.

## Decision after the window

Agree the roadmap's proposed gates before recruitment: 80% initial curiosity,
70% observed-consequence comprehension among observed actors, at least half
returning unprompted, and 70% useful return among observed returners. Report action
understanding separately as a diagnostic. These are hypotheses, not benchmarks.
Always report actual counts and unknowns; a tiny return denominator cannot support
a broad claim. Do not collect extra participants selectively just to cross a threshold.

Fix observed confusion or reliability failures first. If participants can navigate
but find no reason to return, revisit the consequence/return experience before
adding rankings or crafting. If results are promising and operational gates hold,
recommend the next invitation wave; results do not themselves authorize it.
Target completion by October 24 if October 31 remains the desired beta date.
