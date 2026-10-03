# ADR-030: The Render Contract — recorded, state-addressed senses

**Status:** Proposed draft, 2026-10-03, written at the owner's request after the
[ambition-and-boundaries assessment](../evaluation/2026-10-03-ambition-and-boundaries.md)
(decision D3) and its review corrections. Not ratified. This document introduces
no runtime behavior, migration, or write path. On ratification it supersedes
the generation-backend and caching sections of
[ADR-002](ADR-002-image-generation.md), adopts the six production conditions of
the [beta scene-art strategy](../design/beta-scene-art.md) as binding, and
answers the revisit clauses of [ADR-009](ADR-009-chronicled-deltas.md)
("store rendered parameters at write time") and
[ADR-011](ADR-011-wayback-surface.md) ("generated imagery… may join the archive
only with a deterministic, state-addressed contract") without versioning the
procedural renderers.

---

## Context

What the player sees and hears today is produced by four mechanisms that share
one input and no contract:

1. **One sensory description.** `multiverse/senses.py` (`VERSION = 3`,
   `describe`) derives material, texture, atmosphere, light, tension and a
   `revision` digest from the served node; `revision` hashes the senses *and
   the current properties* (`multiverse/senses.py:68`), so it changes on every
   material delta. Four curated plates are keyed to exact born names with
   identity anchors (`PLATES`, `PLATE_SHAPES`); provenance is in
   `docs/media/expressive-world.md` and `static/media/manifest.json`.
2. **A free procedural layer.** `static/sensory.js` (109 lines of 2D canvas,
   frame-counted, entropy-free) draws the scene; `static/score.js` sequences
   eleven sampled forms (`SCORE_PROFILES`, VSCO samples under
   `static/media/score/`); `static/nodeart.js` serves the explorer and Wayback.
   `tests/test_frontend_contract.py:273-291` forbids `Math.random`, `Date.now`
   and `performance.now` in all three.
3. **A paid image wash.** `server/handlers.py:966` (`_do_image`) calls
   `fal-ai/fast-sdxl` synchronously inside the request thread with a 30-second
   timeout, keys the result on `f"{seed}:{name}:sensory-v1:{style_signature}"`
   where `style_signature` (`server/imageprompt.py:146-176`) already excludes
   nested state and keys on baseline, history-derived modifiers, the first six
   scalar properties and the aspect, and stores the **provider URL** in
   `node_images(node_key, image_url)` (migration 0001). Budgets are daily call
   counts (`guard.consume_fal`, per-user sub-cap), the kill switch is
   `NESTED_WORLDS_DISABLE_IMAGES`, and failure answers the authored quiet line
   with `images: false` (`_IMAGE_QUIET_LINE`). `SceneView.jsx` fetches once per
   `(seed, node.name, plated)` and passes the URL to `startSensory`.
4. **An archive that omits imagery.** `/wayback` reconstructs state and
   returns `"lens": "the node as it was, seen with today's eyes"`
   (`server/handlers.py:672`); the image layer is left out because its key
   folds in present history (ADR-011).

The constraints this creates were measured in the assessment and its review:
a renderer keyed on `revision` bills on every delta; a renderer keyed on a
provider URL expires (ADR-002's own revisit trigger); nothing owns the assets;
generation blocks a request thread; the curated plates set a quality bar the
automatic path has not met (`beta-scene-art.md`); and the determinism contract,
written for *generation*, is applied to *presentation*, which blocks every
renderer that samples, including the ones that are production-grade today
(persistent splat worlds at about $1.20 per generation, reference-conditioned
image models, generated music cues). ADR-027 already left the door open:
"A different world model demonstrates better controllability → prototype it
behind the same sensory description."

What must stay true: failure stays in fiction on every authored surface; scale
is meaning, expressed through form and timbre, with within-scale differences
grounded in state; Wayback is reinterpretation, never period playback, unless a
retained asset exists for exactly that state; every viewer of the same state at
the same deploy sees the same thing; the chronicle never records a pixel; the
procedural layer stays keyless, free, and deterministic.

## Decision

### D1. One description, many renderers, one contract

`multiverse/senses.py::describe` remains the single server-derived
interpretation of a place (ADR-027). Every renderer consumes it and the scale's
art direction, and nothing else. A **renderer** is registered with: an `id`, a
`version`, a key coarseness (D2), a cost class (`free` or `paid`), a latency
class (`sync` or `async`), and its fallback, which is always the procedural
layer. The initial registry:

| Renderer | Output | Key coarseness | Cost | Latency |
|---|---|---|---|---|
| `canvas` (`static/sensory.js`), `score` (`static/score.js`), `nodeart` | procedural scene, music, explorer art | `revision` | free | sync |
| `plate` | a 2D scene image, reference-conditioned on the curated plates of its family | `material` | paid, cents | async |
| `cue` | a generated music bed layered under the procedural score | `material` | paid, cents | async |
| `volume` | a Gaussian-splat scene (`.spz`/`.ply`) viewed in an MIT WebGL2 splat layer | `structural` | paid, about $1.20 per generation | async |
| `ephemeral` (reserved) | a per-player, uncached, non-canon vision from a real-time world model | none | per viewer-hour | stream |

The `ephemeral` class is defined now so that nothing else is mistaken for it:
it never writes an asset, never appears in Wayback, never changes world state,
leaves no trace, and is framed in fiction as a vision. It ships only when a
provider's cost falls to a level the owner accepts; this ADR adds none.

### D2. The render key, with declared coarseness

`describe` gains an additive `render_keys` object with three digests, computed
on the server so clients and Wayback address assets without recomputation:

- **`revision`**: the existing digest of senses plus properties. Changes on
  every material delta. Only `free` renderers may key on it.
- **`material`**: a digest of the identity-bearing, slowly changing inputs:
  level, art-direction version, `material`, `texture`, `geometry`, `condition`,
  `lighting`, `terrain`/`biome` and their scale equivalents, the `aspect`, and
  the plate anchors of `PLATE_SHAPES`. It excludes counters, `echo`, `energy`,
  `polarity`, `woven`, `memory`, `scar`, `last_wave`, ripple, and every
  history-derived count. It generalizes today's `style_signature`, from which
  the history-derived modifiers are removed: history is drawn by the canvas,
  not bought from a provider. Beta-scene-art condition 5 is the rule for what
  belongs here: a destroyed bridge, changed terrain or fractured object changes
  the key; weather, transient motion and small live effects do not.
- **`structural`**: the node's path plus its structural epoch, which counts
  the structural events of [ADR-029](ADR-029-evolution-grammar.md) recorded on
  it (rename, re-aspect, retirement); before ADR-029 lands it is the path plus
  the born aspect. A volume regenerates when the place itself changes, never
  when its weather does.

The full asset identity is `(world_seed, path, renderer_id, renderer_version,
direction_version, render_key)`. Bumping a renderer or direction version is how
art is revised; it is never done by overwriting.

### D3. Canonical by cache, recorded by provenance

- The first **accepted** render for an asset identity is the render for every
  viewer, at every later visit, until a version bump. Generation may sample;
  canonicity does not depend on reproducibility. This is the pattern that works
  in shipped generative products (generate once per canonical key, cache
  forever) and it is what keeps N viewers in one place agreeing.
- Every asset row records provenance: provider, model, prompt hash, provider
  seed when one exists, the reference asset ids it was conditioned on, cost
  charged, content hash, creator (job id), and `direction_version`. The
  **determinism contract is restated as a recording contract**: procedural
  renderers stay entropy-free and the existing test keeps its scope; any
  renderer that samples must record how, and is canonical by cache.
- Assets are immutable and append-only. Supersession is a new row carrying
  `supersedes`; an operator may mark a render `rejected` (condition 2's
  review hook), which routes viewers to the next accepted render or the
  procedural layer. Nothing is overwritten. Purging retired renderer versions
  is an explicit operator maintenance command recorded in the CHANGELOG; it is
  not a chronicle mechanism, because assets are derived caches like
  `ripple_score`, not chronicle rows. The chronicle never records a pixel.

### D4. First-party asset store

An additive table `render_assets(world_seed, path, renderer_id,
renderer_version, direction_version, render_key, status, uri, content_hash,
bytes, width, height, duration_ms, provenance JSON, supersedes, created_at)`
plus first-party object storage, content-addressed, with the delivery sizes
beta-scene-art condition 4 names. Delivery is same-origin (`/media/<hash>`) or
one configured media host, so the CSP is not widened per provider.
`node_images` becomes legacy and read-only; its provider URLs are not copied
forward, because they expire (ADR-002 "fal.ai URL expiration observable" has
effectively fired). The four curated plates are imported as the first `plate`
assets of their places with their recorded provenance and become the
family references for conditioning.

### D5. Generation is a bounded background job, never a request

- A durable job queue, sharing the existing delivery machinery's claim and
  completion discipline (ADR-019), deduplicates by asset identity, prioritizes
  the place a player is standing in, prefetches only places reachable from the
  current passage surface within a bounded budget, persists retries, and never
  reveals sealed content by prefetching past a seal (condition 3).
- Model and provider I/O runs outside every SQLite transaction (ADR-013). The
  live view shows the procedural layer immediately and receives `asset_ready`
  over the existing WebSocket when a render lands; a result for a superseded
  key is retained as an asset but is not pushed to a live view that has moved
  on (ADR-027's late-result rule, kept).
- Budgets are dollars per day per renderer, with the per-credential sub-cap
  kept, replacing call counts; `NESTED_WORLDS_FAL_DAILY_CALLS*` remain as
  aliases for the `plate` renderer during the transition. Each renderer has a
  kill switch. Default policy is lazy: nothing is generated for a place no one
  has visited, except the entry coverage beta-scene-art recommends preparing
  before a cohort arrives.

### D6. Failure stays in fiction

No asset, budget exhausted, provider down, kill switch on, or key rejected:
the player gets the procedural layer and, where a surface speaks, the authored
quiet line with `images: false`. No provider string ever reaches a client.
These states are indistinguishable to the player by design.

### D7. Scale is meaning, in every renderer

Each renderer's conditioning takes scale identity from the art direction
(today `server/imageprompt.py::HIERARCHY_STYLES` and `static/score.js::SCORE_PROFILES`,
whose parity with the voice is test-pinned; later the scale registry) and the
place's material class. A paid renderer becomes a default layer only after it
passes the differentiation gate ADR-028 set for sound: blinded identification
of scale across places, and recognizability of the same place across material
changes. The molecule and atom baselines that favor diagrams are revised under
a `direction_version` bump, recorded, never silently.

### D8. Composition in the client

Layers compose in a fixed order: procedural canvas (always present, drawn from
`revision`), then `plate` if an accepted asset exists for the current
`material` key, then `volume` if an accepted asset exists for the current
`structural` key and the device can run the WebGL2 splat layer, then live
transients; the procedural score plays, with `cue` layered under it when
present. Imagery contains no interface text; the identity block remains the
accessible description; reduced motion freezes the canvas and disables volume
camera motion; nothing hashes identity into a theme (visual language). The
splat layer is three.js-based; the currently unused PixiJS dependency is
neither required nor forbidden by this contract.

### D9. Wayback: an asset may join the archive only when it matches exactly

For a historical cursor, the server computes `render_keys` from the
reconstructed state and returns, per renderer, whether an accepted asset
exists for that exact key, with its renderer and direction versions. The
client shows the procedural layer through today's senses, as now, and
additionally any asset whose key matches exactly, labelled with its versions.
The honesty line gains a second clause when an asset is shown: "rendered for
this state on <date>, renderer <id>@<version>". No paid render is ever
generated for a historical state by default. Procedural renderers remain
unversioned; a renderer edit still reinterprets every past state exactly as it
does the present. This is ADR-009's "store rendered parameters at write time"
realized as the retained asset itself, without the per-edit archival cost
ADR-009 rejected.

### D10. What this ADR does not decide

Which provider or model renders plates and cues (chosen per beta-scene-art
condition 2, against the accepted examples, and recorded in provenance); the
scale registry; model authorship of art direction; any `ephemeral` renderer;
voice synthesis, which keys per utterance rather than per place and is covered
by ADR-016's track.

## Implementing batches and the doors they trip

| Batch | Scope | Doors (irreversibility check) |
|---|---|---|
| **1 — the contract and the plate** | `render_keys` in `describe` (senses `VERSION` 4); migration 0028-series `render_assets`; object storage and `/media`; job queue; the `plate` renderer replacing the synchronous fast-sdxl call; `node_images` read-only; curated plates imported with provenance; dollar budgets per renderer | Additive migration; no chronicle write path; no golden re-pin; env aliases kept; CSP unchanged if same-origin |
| **2 — volume** | the `volume` renderer with export-on-generation, the splat layer, the `structural` key (path plus born aspect until ADR-029) | None beyond batch 1; provider risk noted below |
| **3 — cue and the archive** | the `cue` renderer; Wayback asset lookup and the second honesty clause; direction-version bump for molecule and atom baselines | None beyond batch 1 |

Tests that gain cases: `tests/test_frontend_contract.py` (scope of the
no-entropy test stays `nodeart.js`, `sensory.js`, `score.js`; a new assertion
that `render_keys.material` ignores every excluded field and changes on every
anchor), `tests/test_wayback.py` (exact-key match only; no generation on
history), `tests/test_guard.py` (dollar budgets, kill switch per renderer,
quiet line on every failure path), a new `tests/test_render_assets.py`
(canonical-by-cache under concurrent requests, immutability, supersession,
rejected routing, same-origin delivery), and the ADR-028 differentiation gate
extended to `plate` and `cue`.

## Trade-offs accepted

- **The generated layer lags the exact present by design.** Plates and
  volumes show what kind of place this is; the canvas shows its exact state.
  The `material` key's inclusion list is the only lever, and condition 5
  governs it: a plate is reused only while it remains true.
- **The first accepted render locks a key's look.** Quality control is
  therefore a review hook, not a retry loop: rejection and supersession exist,
  deletion does not.
- **Paid media is a recurring line, bounded by policy, not by player-hours.**
  Plates and cues cost cents per material-class change; volumes about $1.20
  per structural event. The budget per renderer must state the regeneration
  rate it accepts; the assessment's D3 row says so.
- **Provider dependence.** The splat provider is under acquisition; export on
  generation and first-party storage are the mitigation. Prompt and model
  choice for plates is recorded, so a provider change is a version bump.
- **Storage grows and is never pruned by default.** Cheap, and the archive
  needs it.
- **Two sources of art direction until the scale registry lands.** The
  `direction_version` key component makes the later move mechanical.

## Revisit when…

- **ADR-029 lands** → the `structural` key becomes path plus structural
  epoch; a rename, re-aspect or retirement regenerates the volume.
- **The scale registry lands** → `direction_version` and the per-scale
  conditioning move into the registry record.
- **A real-time world-model renderer costs under roughly $0.50 per
  viewer-hour** → specify the `ephemeral` class: per-player, uncached,
  non-canon, trace-free, in fiction a vision.
- **Playtests show a plate contradicting a changed place** → widen the
  `material` inclusion list; never cover a false plate with particles.
- **Period-faithful rendering becomes a product goal** → the retained asset
  already is the stored rendering; extend retention and surface versions, do
  not version the procedural renderers.
- **A provider URL or model is withdrawn** → re-render under a new version
  through the queue; the old asset rows stay as record.
- **Storage or budget thresholds are reached** → tighten lazy policy and
  prefetch bounds before touching retention.

## Rejected alternatives

- **Keeping the URL-only cache.** Provider URLs expire; nothing is owned.
- **Regenerating paid media per `revision`.** Bills on every delta; the review
  of the assessment's D3 established the correction.
- **Letting a model choose the art per request.** Viewers of one state would
  disagree; keys must derive from state alone.
- **Client-side generation.** No browser runs a video or diffusion world model
  at scale; viewing splats client-side is the exception and is adopted.
- **Screenshots or audio as the archive.** ADR-011's rejection stands; the
  retained asset is addressable by state, not by moment.
- **Versioning the procedural renderers.** ADR-009's rejection stands.
- **A neural engine as the substrate.** The assessment's §5 verdict: minutes of
  consistency, no shared state, no API at tolerable cost; the generative layer
  renders chronicled state, it is not the world.
- **Pre-rendering the whole world up front.** Spends on unvisited places and
  states that will change; entry coverage plus lazy expansion instead.
- **Keeping generation inside the request thread.** Blocks play on provider
  latency and violates the external-I/O rule.
