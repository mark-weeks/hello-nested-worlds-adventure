# Scale-native action and sound correction

**2026-09-20 · local review build · correction to `52c8b6c`**

The owner rejected the first milestone experience. That judgment is the acceptance
result: successful durability tests did not compensate for repetitive sound,
duplicated interaction, a prescriptive sidebar, or forced agent actions.
[ADR-028](../decisions/ADR-028-scale-native-autonomy.md) records the correction.

## What changed

Both browser clients extend the existing Speak | Puzzle | Act surface. Act starts
without a selected plan and offers four actions native to the current scale,
including the original verb. There are 44 supported transitions, with sequences
of up to four actions. Preview displays real material changes; combination,
free-form intention, downstream timing and previous consequences are optional
expanded details. Conditions are collapsed; duplicate sidebar passage and sound
controls are removed. The scene's passage buttons remain keyboard accessible.
The gallery controller is removed, and its public choice endpoint refuses new
choices. Previously accepted receipts and pending work remain readable/recoverable.

The server derives the actor from the authenticated participant and rejects a
caller-selected delegate, performer or actor identity. No human or model proposal
can commit an action on behalf of a different human or AI player. Suggestions do
not constitute consent. The contributor rules and PR checklist now state both
independent agency and the extend-or-replace interaction requirement explicitly.

Current examples include cultivation/overgrowth/channeling in a region,
illumination/shading/ventilation in a room, engraving/fracture/polishing of an
object, and cleavage/folding/branching of a molecule. Wrong-scale actions,
unsupported instructions, no-op steps and cancelling sequences are rejected.
Model proposals have the same bounded vocabulary and validation as direct actions.
The guide describes these possibilities without presenting eleven verbs as a cap.

## Sound evidence

The old common backing score is replaced by eleven forms: membrane tides, wind
chorales, a stellar procession, orbital polyrhythms, planetary horn phrases,
regional flute calls, enclosed harp echoes, close material gestures, molecular
hockets, atomic bells and isolated particle sparks. Each has its own register,
articulation, spacing, pan and room response. Node properties alter the form;
family motifs preserve continuity. Five additional CC0 recordings extend the six
existing samples. A seeded diffuse reverb replaces the old pitched impulse.
Scale changes fade the previous voices and begin the new form within 80ms;
within-scale changes enter at the next phrase boundary.

`scripts/render_score_audition.mjs` renders eleven 16-second WAV excerpts through
the complete browser audio graph and creates an A–K listening page with optional
identity reveals. The local run produced finite, non-silent audio with peak
amplitudes **0.1651–0.4698**, RMS **0.0223–0.0879**, and quiet fractions
**0.0104–0.7711**. These measurements establish rendering and dynamic separation,
not scale recognition, musical excellence, or professional production quality.
A blinded listening session on ordinary speakers remains the acceptance test.
See [media sources and direction](../media/expressive-world.md) for exact provenance.

## Recovery and correction evidence

New actions reuse the intervention delivery mechanism with a version 2 interpreter.
Version 1 remains available to deliver old accepted work and recover its original
receipts, including truthful historical actor attribution. New cosmic actions use
the established scale clocks, meet current conditions at maturation and record a
single no-material-change outcome if their prerequisites have disappeared. Such
an outcome cannot produce a phantom downstream wave. Born orbital resonance
ratios remain strings; arriving acoustic state uses a separate property.

Verification exercises both served clients, real HTTP and WebSocket paths,
independent co-viewers, actual process death/restart, missed notifications,
lost-acknowledgement recovery after reload, stale previews, navigation during late
responses, unavailable arrival saves, inaccessible recovery storage, historical
state and reduced/mobile layouts. Model proposal tests use fixtures; no live model
quality has been established. Browser inspection confirmed that region actions
are replaced by room actions on navigation and no plan is selected on arrival.

During verification, older browser tests still expected the removed buttons and
scripted gallery controller. They were rewritten around the replacement UX while
retaining old accepted-work recovery. An arrival-failure assertion accidentally
matched explanatory preview prose; it now targets the save status. Restart fixtures
were trying to mint existing credentials again; they now reuse them. The co-viewer
check exposed redundant reads: refreshing a node triggered a second property
refresh from the action panel. Only fallback polling now requests properties when
it discovers a missed outcome; node-triggered action reads do not echo the refresh.

**Final gate:** `ENFOLDED_E2E=1 ./scripts/check.sh` passed: Ruff; **1,297 Python
tests** in 228.40 seconds; **120 Vitest tests**; byte-fresh production bundle;
installed-wheel smoke; and **60 Playwright tests** in 1.8 minutes. Both co-viewer
checks passed with bounded node reads and no world reloads. All 15 packaged media
hashes, local document links and diff whitespace checks pass. The local preview
and listening page were inspected in the in-app browser. These are implementation
checks, not a substitute for the owner's product acceptance.

The original local preview was paused briefly and copied through SQLite backup.
All **39 tables** compared identically before restart, including **133 history
events**. The updated server resumes the preserved database; original birth rows
and all prior history rows still match. Browser inspection resumed the existing
Distant Bloom Wastes position and displayed Ward, Cultivate, Overgrow and Channel
in the sole Act surface. No action was submitted in the owner’s review world.

## Remaining limits

Forty-four transitions widen physical expression but do not implement arbitrary
player-authored structures, negotiated group projects or new laws of physics.
Legacy CLI and ambient actor paths still use their original verbs. The browser
surface and public versioned proposal endpoint support the expanded vocabulary;
a claim of full agent capability parity would be premature. Generated artwork
and live language-model quality were not re-certified by this sound/action fix.
No merge, deployment or publication is part of this correction.

## Irreversibility check

Scope: the correction after `52c8b6c`, including new files. No migration, generator
change, golden re-pin, world-meta pin or era-bank edit. The owner's explicit
correction authorizes bounded version 2 material actions and closing new forced
agent choices. `persistence/interventions.py::_record` adds ordinary chronicle rows
for pending acceptance and no-material outcomes to the existing versioned action
path; actual substance changes remain on `record_substance_change`. Transactions
retain exactly-once receipts, append-only history and completion fences. Previously
accepted semantics and recorded performers are preserved, not reinterpreted.
