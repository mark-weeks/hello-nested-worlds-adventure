# ADR-021: Evidence-bound history narration

**Status:** Proposed for review, 2026-09-08. Bounded M3 presentation policy;
ADR-013's broader proposals remain Proposed.

## Context

An original scale action, its traveling pressure and its delayed outcome use
two existing event kinds. Rendering every SCALE_ACT as a local choice invents
remote actions. M1's retained delivery references and source event IDs can
recover attribution without rewriting history; older rows have partial evidence.

## Decision

Project bounded pages of recorded facts into one narration shared by history,
chronicle, live notices and existing node/inhabitant speech context.

| Evidence | Narration |
|---|---|
| Original SCALE_ACT with recorded delta | An action at its original place; material completion is supported by the delta. |
| Original SCALE_ACT with a recorded delay (including zero seconds) | Acceptance for a delayed outcome, never a completed change. This remains an acceptance fact after landing. |
| Arrival with `_origin`, hop or causal delivery evidence | A ripple/effect reaching the receiving place, never the original verb being performed again. SCALE_ACT pressure does not change remote substance. |
| SCALE_ACT_MATURED | A delayed outcome; claim material completion only with a stored delta/legacy changed patch. Preserve explicit terminal-no-op flavor. |
| Shared pending outcome or admission no-op | Keep M2's personal response and shared counts. Joining creates no recorded action, actor credit or participant roster. |
| Missing/legacy provenance | Report only surviving labels, location and effect evidence. Say when the source or exact original action is unrecorded; never match by name, verb, time proximity or topology. |

Resolve only explicit source IDs and retained delivery IDs, scoped to the world,
receiving node and event kind. Reject conflicting references. An original event
supplies its recorded actor label and canonical location; labels are not unique
identities. Do not expose credential hashes, infer actor type, or consult live
profiles. Include node addresses and source event numbers so equal display names
do not collapse distinct places or actions. A source number addresses the existing
chronicle cursor (`before=source+1&limit=1`).

Use constant-count batched reads per bounded page, with no ancestry search,
full-world hydration, per-row lookup or new persistence path. Broadcasts carry
the same projection after commit, retaining existing IDs for M2 refresh deduplication.
Historical reload is authoritative when notices are missed. Wayback stays outside
this projection: it remains actor-blind and folds stored deltas.

## Trade-offs accepted

Current wording can improve without changing historical facts. Legacy rows may
identify a place and label without identifying an exact action; that gap is
visible rather than backfilled. No new durable join roster or missing-source
repair is justified for M3. Public narration contains bounded source facts, not
source conversation content or operation payloads.

## Revisit when…

- A real player cannot follow a source number and location → add focused source
  navigation using existing cursors, without changing identity or history.
- Missing provenance prevents a required new situation → document that specific
  persistence gap and review its write contract separately.
- Measured history volume makes the bounded lookup costly → optimize the read
  projection before adding a materialized event or memory system.

## Rejected alternatives

- Rewriting old rows or guessing actors from display names or nearby events.
- Replaying effects to explain history, or interpreting v1 as v2.
- Sending private acceptance text to co-viewers or adding attribution to Wayback.
- A general event engine, journal, profile, agent memory or dialogue system.
