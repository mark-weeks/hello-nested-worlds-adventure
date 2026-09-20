# Expressive world: implementation and acceptance evidence

> **Superseded review result:** The owner rejected this build’s interaction and sound design. Its test results are historical engineering evidence, not product acceptance. See the [scale-native correction](2026-09-20-scale-native-correction.md) and [ADR-028](../decisions/ADR-028-scale-native-autonomy.md).

**2026-09-20 · local review build · base `f87968b`**

The owner authorized implementation of a demanding cinematic experience spanning
connected scales, correcting the incomplete agency implementation behind PR #93
and ADR-017. This build gives players a compositional vocabulary, persistent
created structures, competing signal directions, delegated enactment, and a
shared visual/musical interpretation. It does not claim artistic acceptance,
retention, production deployment, or unrestricted text-to-world generation.

The concrete contract is [ADR-027](../decisions/ADR-027-expressive-world.md).

## Play the connected experience

Start a disposable world with `.venv/bin/python scripts/preview_expressive_world.py`.
Use the local link it prints. This script binds to localhost, creates a temporary
database and invite, installs the existing signal investigation, and disables
paid model/image calls. Recorded music, generated plates and every compositional
operation work without an API key. Stopping the preview removes this test world;
ordinary hosted worlds retain their existing durable database behavior.

1. Begin at **Emberlit Orchard Terraces**. Turn on the score and adjust its volume.
   Enter **Broken Ember Gallery**, then **Elder River Instrument**, then
   **Distant River Chain**. Notice the shared material and musical identity as
   the scale changes, with pollen, dew, frost and static grounding each place.
2. At the chain, choose **A memory that can travel** and inspect the ordered
   operations. Edit them freely, up to four steps. Preview explains the structure,
   energy cost, polarity, regional risk and actual route before commitment.
3. Commit. The created resonator and harmonic trace persist. The wave travels
   through the instrument, gallery and orchard over approximately 12, 24 and
   36 seconds (plus the pump's normal scheduling interval).
4. Follow the arrivals through **Your threads through the world**. Construct a
   receiving resonator before an arrival: it catches energy instead of letting
   all of the wave pass through. This is an interaction between independently
   composed acts, not another predefined story ending.
5. Compare `charge 3, release` with `charge 3, invert, release`. Inversion changes
   the direction and consequence. `unweave` releases bound energy and leaves a
   seam while removing the useful structure. The preview reports present costs;
   it does not promise to know other players' future interventions.
6. Ask a named traveler for an approach, edit the proposal, then explicitly
   entrust it. The actual performer is recorded. Agent enactment grants no human
   puzzle progress and creates no leaderboard reward.
7. Reload, visit the journal, and open **Replay History**. Birth and present show
   different recorded states. Replay uses today's sensory interpretation of
   those facts; it is not a recording of an earlier musical performance.

The previous gallery investigation remains playable with its existing preserve /
release commitment and aftermath. The new grammar is available at other accessible
places; four connected named places receive the curated cinematic treatment.
The explorer remains the default invite destination.

## Decision → behavior → consequence → evidence

| Intended product decision | Playable implementation | Observable consequence | Evidence / remaining acceptance |
|---|---|---|---|
| Consequential creation | Weave a persistent resonator; its capacity and receiving behavior differ from an unbound place | Future releases carry memory; arriving waves can be captured | Physics, HTTP and both-client tests; independent human novelty judgement still needed |
| Opposing purposes | Invert before release, or free a resonator by unweaving | Signed echoes, bounded danger changes, structure lost, persistent seams | Ordered-operation and receiving-state tests; no invented achievement score |
| Surprising combinations | Up to four ordered operations, then interactions with later receiving arrangements | Invert-before-release differs from invert-after-release; constructing a receiver changes an accepted wave's landing | Pure semantic tests and actual delayed delivery |
| Agent agency | Grounded proposals and explicit delegated enactment through the same commit path | Named performer, durable material delta, same recovery rules | Endpoint test; live model quality unverified |
| Cinematic continuity | Four generated plates with shared art direction and state overlays | Related motifs across scale; visible resonators, memory traces, seams, polarity and atmosphere | Desktop/mobile Chromium captures plus direct in-app browser inspection; broader device and human visual evaluation pending |
| Adaptive music | Five recorded orchestral instruments, authored motifs, environmental layers and a continuous clock | State changes alter orchestration; movement changes phrasing without destroying sounding voices | Browser decoding and transport checks plus pure musical-direction tests; professional listening evaluation pending |
| Evolving canon with dependable history | Current proposals separated from retained v1 interpretation; atomic receipts and durable arrivals | New receiver states participate; accepted work survives failure, duplicate requests and upgrades | Rollback, concurrent workers, SIGKILL, backup/restore, future-interpreter and Wayback tests |
| A meaningful return | Personal intervention threads and journal recap include source and arrivals | Players recover outcomes after a lost response, a reload, or absence | Both clients tested with an intentionally dropped acknowledgement; unprompted return remains a human pilot question |

## Implementation boundaries and trade-offs

- The grammar creates a **resonator arrangement at an existing place**. It does
  not create arbitrary born nodes, rewrite topology, or accept arbitrary model
  patches. An unsupported intention remains unsupported. New operators can be
  added through versioned semantics without rewriting prior promises.
- Both frontends use the same composer and sensory renderer. The scene uses
  accessible HTML passages over Canvas 2D rather than depending on a GPU scene
  graph for navigation. Failed or unavailable image generation leaves a local
  material-based scene. Generated imagery is an interpretation, not authoritative
  canon or evidence that geometry is physically simulated.
- Four local plates are intentionally a concentrated artistic test. Other places
  have semantic procedural scenes; this is not a claim that the whole multiverse
  now has bespoke cinematic production. No live video, 3D world model, or neural
  game engine is included. The sensory description is a replaceable presentation
  boundary for future renderers while consequences remain authoritative.
- The score is original runtime arrangement of CC0 recorded samples, not a
  generated imitation of a named composer. Musical phrases and source identities
  persist across navigation. Dynamic mixing is implemented; award-level quality
  has not been established. [Media sources and direction](../media/expressive-world.md).
- Local effects update immediately. Generated provider imagery is refreshed by
  material/style signature; raw history counts no longer force regeneration.
  Late responses from a previous place or revision cannot overwrite the current
  scene. Current Wayback senses replace live senses instead of inheriting them.
- Explicit invocations are budgeted and authenticated. Natural language uses a
  constrained model proposal when configured; the server validates it and the
  player still previews/commits. Offline explicit notation and the composer
  remain usable. Live Anthropic output quality was not tested in this run.

## Verification ledger

Final `ENFOLDED_E2E=1 ./scripts/check.sh` passed: Ruff, **1,293 Python tests**,
**117 Vitest tests**, byte-fresh production bundle, installed-wheel smoke, and
**65 Playwright tests**. Document links, ten media hashes and diff whitespace
were also verified. The final isolated preview was inspected in the in-app browser.

The first whole Python run found six old expectations: quote-specific image
request plumbing, the former renderer's function names, history-count cache
keys, two fixed latest-migration assertions, and the six-property image cutoff.
These were updated for the changed contracts; birth/causality/history/seal tests
were retained. Browser verification then corrected tests tied to the removed
renderer chunk and the old navigation label, isolated position-only credentials
from composition authentication, and made the arrival-outage fixture hold across
depth-triggered position saves. The actual no-canvas fallback remains navigable. The subsequent canonical gate is recorded in the CHANGELOG. Browser assets
(excluding the separately loaded plates and recordings) decreased from **777,653
to 348,370 bytes** against the base checkout. Four plates total about 10 MB;
only the current place is requested. This is a bundle-size measurement, not a
claim about real-device frame rate or download time.

New tests exercise actual HTTP submissions, competing operation order, stale
previews, duplicate acceptance, current receivers, rollback, concurrent delivery,
process death during an arrival, backup/restore, retained-v1 delivery, historical
senses, and a mocked structured model response. Five new browser scenarios cover
both clients with an intentionally dropped response and reload, refusal to submit
without a durable recovery copy, plus real sample
decoding, continuous audio transport and an actual offline render of the complete audio graph.
The 18-second render measured peak amplitude **0.202** and RMS **0.00491**
with six decoded recordings, finite samples and no clipping. These measurements
are technical audio evidence, not a listening-quality score. Captures are produced by
`frontend/e2e/expressive.spec.js` in the system temporary directory.

Automated evidence establishes mechanics and regression behavior. The final
creative bar requires people to compare the experience with the intended product,
recognize places from their sound/image, explain the costs of their own composition,
and choose to return without prompting. Follow the existing
[pilot protocol](2026-09-12-pilot-protocol.md), adding blind place/state comparisons
and professional visual/music critique. No results are asserted for those tests.

## Irreversibility assessment

The owner's 2026-09-20 instruction authorizes this implementation's new persistent
agency. Migration 0027 adds only `interventions`, `intervention_work` and indexes.
Acceptance adds `INTERVENTION_COMMITTED`; arrivals add `INTERVENTION_ARRIVED` using
existing atomic material-delta recording. Born identities, generator/golden pins,
world-meta/hinge pins and era banks are unchanged. No earlier history or accepted
work is rewritten. Completed fences remain retained. A deployment still requires
the normal backup/restore and explicit release decision; this local build has not
been merged, deployed, or used against the operator's world database.
