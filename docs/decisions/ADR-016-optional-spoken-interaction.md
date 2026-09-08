# ADR-016: Optional Spoken Interaction

**Status:** Proposed (owner-requested capability direction), 2026-09-07;
pending development-team review and ratification. Implementation pending.
The owner requested voice as an alternative to typing and reading. The initial
interaction design below is recommended; providers, operating budgets, and
supported-device commitments require a measured implementation proposal.

## Context

Enfolded already calls generated character text a node or agent's "voice" and
has an ambient sound system. Neither is speech input or spoken dialogue output.
Optional speech could make a place feel inhabited and reduce reading/typing
friction, while misrecognition could accidentally change persistent state.

## Decision

Add **optional speech input and spoken playback as independent capabilities**,
preserving complete text interaction. Speech carries the same conversation and
actions through the same authoritative rules; it does not create a second game
engine or allow model-generated commands to bypass acceptance checks.

### Recommended first interaction

1. The player explicitly starts microphone capture with push-to-talk/tap-to-talk.
   Show capture state, stop/cancel controls, and an editable recognized transcript.
2. The player submits that text through the existing node/agent conversation or
   appropriate action UI. Speaking an answer or command is not itself submission.
   Puzzle attempts and world-changing commitments require explicit submission.
3. The server validates and records the submitted interaction exactly as in the
   text path. Recognition retries or playback must not create duplicate actions.
4. The response remains visible as text. When enabled, spoken playback reads the
   canonical response, with stop/interruption and separate speech-volume controls.
   Coordinate with ambient audio so it does not obscure dialogue.

Allow listening without a microphone and speaking without playback. For the
first release, constrain speech to current node/inhabitant interactions and
explicit submissions; automatic narration of everything on screen and private
journal read-aloud are separate scope choices.

### Processing and persistence boundaries

- Start with a speech-to-text → existing text/rules → text-to-speech pipeline.
  Keep provider adapters replaceable. Do not choose a provider or rewrite the
  conversation engine before testing the actual device and latency constraints.
- Browser-native speech may simplify deployment but needs a support/privacy
  check; server-mediated services offer consistency with additional latency
  and cost. Do not promise either is local or private without verifying its
  processing behavior. A full real-time speech agent is a later option.
- Use explicit microphone permission, a visible recording state, and clear
  processing information. No always-on microphone or background capture.
- Recommend no application retention of raw microphone recordings by default.
  Submitted transcripts follow the same existing conversation/action policy as
  typed text; unsent drafts and audio must not enter public world history.
  Provider retention settings must be verified separately before release.
- Playback/audio generation adds no chronicle row. Use the same authentication,
  world guard, moderation, action limits, and submission identity as text, with
  explicit additional speech budgets and cancellation handling.
- Keep text available when permission, recognition, synthesis, connectivity,
  or budget fails. Microphone controls explain their state clearly; character
  fallback responses continue to follow the world's authored voice contract.

### Acceptance evidence

Test world names, short answers such as `42`, technical words such as `qubit`,
corrections, interruptions, denied permissions, unsupported browsers, muted
playback, duplicate submissions, and keyboard/screen-reader operation.
Measure capture-end to editable transcript, submission to first audible output,
correction frequency, cost per interaction, and whether players choose speech.
Set launch latency/cost targets after the feasibility run rather than presenting
untested service assumptions as a product promise.

No recognized-but-unsubmitted utterance may change the world, spend a puzzle
attempt, or create a public conversation row. Verify text and speech paths have
the same authoritative outcomes. Recorded session replay must not re-submit an
action. Do not require a specific accent, hearing ability, or microphone to play.

## Trade-offs accepted

Transcript review adds a step but makes permanent actions deliberate and provides
an accessible correction path. A staged pipeline may be less fluid than full
duplex conversation, but it preserves tested rules and makes failures observable.
Speech is an optional enhancement, not a prerequisite for proving the first
discovery-and-return experience.

## Revisit when…

- Players use speech but correction/submission friction dominates: evaluate a
  faster conversational mode while preserving explicit consequential actions.
- Latency, cost, or device support fails the measured target: switch adapters or
  narrow the supported voice path without degrading text interaction.
- Players need broader read-aloud/navigation access: design those capabilities
  with private-content boundaries and accessibility testing explicitly included.

## Rejected alternatives

- Voice-only play, mandatory microphones, or always-listening interaction.
- Speech recognition directly invoking mutations or changing answer validation.
- Saving all recordings in the permanent chronicle or cloning participant voices
  as a prerequisite for character identity.
- Choosing a real-time model architecture before a bounded speech experiment
  establishes value over the existing text experience.
