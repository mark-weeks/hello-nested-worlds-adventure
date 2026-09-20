# ADR-027: Expressive interventions and a shared sensory world

**Status:** Implementation contract for the owner's 2026-09-20 instruction to
implement the endorsed cinematic, expressive-agency milestone. This adopts the
bounded contracts below; it does not ratify every candidate in ADR-012–018 or
claim production deployment, artistic acceptance, or live-model verification.

## Context

PR #93 and ADR-017 already endorse meaningful preserving and opposing purposes.
Restorative scale verbs and one preserve/release situation implement only part
of that direction. A new menu of predetermined endings would repeat the gap.
The sensory audit also found that unrelated aspects can produce identical local
art/audio, image refresh misses same-place changes, and sound restarts on every
state key. The next milestone must connect expressive acts to persistent,
perceptible consequences over several scales.

## Decision

- Add a reusable version-1 intervention grammar: weave, charge, invert, release,
  dampen, and unweave. A player composes up to four ordered operations at an
  existing place. Operations transform a small physical state (stored energy,
  polarity, coherence and a persistent resonator); ordering changes outcomes.
  Creation enables new behavior, inversion changes a signal's effects, and
  dismantling frees energy at a cost. Ordinary scale verbs remain available.
- Preview the complete plan with current-state preconditions and explicit
  trade-offs before submission. Natural-language interpretation may propose
  only these operations; ambiguous or unsupported requests must stay proposals.
  It cannot assert novel canon, grant access, or write arbitrary properties.
- Acceptance and the origin's actual delta, retained request receipt and delayed
  outward consequences commit atomically. Store the interpreted plan/version,
  actual emitted signal and route at acceptance. A stale preview is rejected.
  Existing identities, born rows, earlier accepted work and situation versions
  are preserved. New proposals may use new interpreters; pending v1 work may not.
- Consequences travel through up to three actual ancestors. They use current
  receiving state under a SQLite writer lock and record actual deltas. Retained
  completion fences prevent duplicate effects after retries, process death or
  concurrent workers. Notification follows commit and never defines truth.
- Agents can propose interventions grounded in present conditions. A delegated
  proposal executes through the same acceptance and validation rules with an
  explicit public commitment and durable outcome. It earns no ranking or human
  puzzle progress. Ambient agents cannot autonomously exhaust opportunities.
- A server-derived, versioned sensory description interprets real properties,
  material, atmosphere and intervention history for both visual and musical
  direction. Curated generated plates are tied to named born places, with local
  state-driven effects and reference/asset provenance. Other places retain a
  semantic procedural treatment. The scene refreshes by sensory revision and
  rejects late image results for previous places or revisions.
- Sample-based musical motifs, orchestral layers and environmental synthesis
  share a continuous musical transport. Place changes and state changes retune
  layers at phrase boundaries, with immediate bounded cues for consequences.
  User activation/volume, reduced motion and complete text interaction remain.
- History continues to reconstruct recorded state through current senses. Assets
  are versioned and retained, but this milestone does not promise exact recordings
  of past performances or silently change Wayback into media playback.
- Preserve the explorer's default invite destination and existing access rules.
  Both clients expose interventions and receive sensory state; the scene remains
  the primary cinematic experience. Use disposable local worlds for all tests.

## Trade-offs accepted

A constrained compositional grammar makes consequences inspectable while opening
many combinations; it is not unrestricted text-to-world execution. Recorded samples
and generated plates improve the local experience without requiring live vendors,
but artistic quality still needs human evaluation. New operational tables and
chronicled effects increase retained data. Authoritative world updates remain
independent of media availability. A bounded ancestor route preserves established
containment; arbitrary topology changes and alternate canonical worlds are outside
this implementation.

## Revisit when…

- Players express unsupported but coherent intentions → extend the grammar with
  a versioned, testable operator rather than silently map their words to a preset.
- Listening or playtesting finds repetition or weak correspondence → revise
  motifs, orchestration and property mappings against direct comparative evidence.
- A different world model demonstrates better controllability → prototype it
  behind the same sensory description, preserving authoritative world facts.
- Recognition becomes useful → implement ADR-017's separate outcome/evidence
  contracts; raw intervention volume and damage/repair loops earn no awards.

## Rejected alternatives

- Treat the approved breadth of agency as a new optional direction.
- Replace the existing situation or rewrite accepted work to simplify this one.
- Accept arbitrary model-written patches, manufacture actor history, or change
  node identities to attach prettier assets.
- Restart all music for every property update, regenerate pictures for raw
  interaction counts, or describe fixture checks as proof of artistic excellence.
