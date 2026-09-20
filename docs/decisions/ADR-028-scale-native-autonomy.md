# ADR-028: Scale-native actions and independent players

**Status:** Implemented locally following the owner's explicit correction of the
September 20 review build; supersedes the proposal/UI/delegation portions of ADR-027.

## September 20 owner correction: commit, then discover

The owner rejects seeing material consequences before acting. The
[visual language](../design/visual-language.md#intention-and-recognition) now
requires committing to an attempted action and discovering consequences as the
shared world responds. A clarification may establish an ambiguous action, target
or scope; it must not forecast property deltas, future causal routes or scoring.
Clear actions do not require a mandatory preview/confirmation stage. Other players
remain independent, and delayed outcomes depend on conditions when they occur.

This supersedes the preview requirement in the implementation record below.
The runtime still exposes previews; its replacement is pending implementation.
Existing accepted actions, versioned semantics and recovery receipts stay intact.

## Context

The first milestone review failed product requirements. A universal six-operation
composer duplicated Act, prescribed charge/release everywhere, and let a human
force an agent to enact a plan. The gallery pane exposed a scripted controller as
play. A common orchestral backing track with small register changes failed to make
scale audible. Passing durability tests did not establish a coherent experience.

## Decision

- Extend the existing **Speak | Puzzle | Act** interaction. Act is the only action
  surface in each browser client. It has no selected plan on entry. Conditions,
  composition, downstream detail and previous consequences are disclosed on demand.
- Every player, human or AI, controls their own actions. Suggestions and invitations
  belong in conversation; they neither grant authority nor imply agreement. Reject
  caller-selected delegates/performers at acceptance. Never fabricate agent consent.
- Version 2 provides four physically different actions at each of eleven scales,
  including the original action and three additional possibilities. Players can
  combine up to four ordered actions and preview actual property changes. This is
  the current implementable vocabulary, not a permanent limit on creative intentions.
  The limit on sequence length bounds one acceptance/preview, not world evolution.
- Model proposals use only the current scale's vocabulary, are validated again on
  the server, and require the player's explicit commitment. Unsupported intentions
  remain unsupported instead of being approximated without consent. Offline explicit
  sequences and action selection use the same validator.
- Physical state changes retain born identity, append-only history, stale-preview
  checks, exactly-once receipts and delayed consequences. Cosmic acts mature on
  their existing scale clocks. A sequence whose prerequisites no longer hold at
  maturation records no material outcome and sends no false downstream wave. It
  does not retry forever or force outdated properties onto the receiving world.
- Retain version 1 delivery and receipt semantics for already accepted work,
  including truthful historical performer attribution. Public endpoints close v1
  to new work. New v2 work reuses the existing intervention tables; no migration.
- Retire the gallery controller UI and close its choice endpoint to new choices.
  Previously accepted receipts and queued outcomes remain recoverable. Existing
  history and personal notes remain readable; no retroactive world edit.
- Each scale has a musical form: instrument family, rhythm, register, articulation,
  spacing and room response. A family motif supplies continuity. Material properties
  vary that form within a scale. Scale changes introduce the new form immediately
  with a fade while retaining the musical transport. Media ship locally.

## Trade-offs accepted

Forty-four actions do not constitute arbitrary invention. Player-authored targets,
new structures and independently negotiated multi-player projects need additional
physical semantics and consent mechanisms. This correction removes the generic
resonator menu without erasing resonators already created in the reviewed world.
The retained `/act`/CLI and ambient actor paths still support the original verbs;
both browser clients use the wider versioned action surface. This asymmetry is
explicit, not a claim of agent capability parity.

We retain legacy situation data and workers for continuity, not as the recommended
experience. Their tested old behavior must not authorize a new public forced-agent
choice. Musical separation can be measured and listened to; automated tests cannot
prove aesthetic quality or a player's ability to identify every scale unaided.

## Revisit when

A proposed intention lacks a physical expression, recurring play reveals an absent
purpose, or independent agents need to negotiate and accept multi-player work.
Extend the versioned vocabulary and the same Act/conversation surfaces. Revisit
orchestration after blinded player listening and repeated visits, including hearing
on ordinary laptop speakers. No new parallel action panel.

## Rejected alternatives

Relabeling the six universal operations by scale; adding more dropdowns to the
sidebar; calling forced delegation an invitation; hiding an unchanged quest menu
behind a disclosure; or retaining a common backing score and changing pitch alone.
