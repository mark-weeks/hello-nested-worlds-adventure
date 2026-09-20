# Scene artwork for beta

**2026-09-20 · recommendation, not an implemented production pipeline.**
This strategy accompanies [the visual language](visual-language.md).

## Recommendation

Pre-generate and review the first-impression scenes before beta. Generate the wider
world as exploration approaches it, reusing approved references and shared assets.
The quality bar should be consistent across both paths; generation timing differs.

| Moment | Recommended behavior |
|---|---|
| Before beta | Prepare likely entry locations, nearby alternatives and a connected reference set spanning all eleven scales. Explore multiple routes; the art budget must not become a compulsory player itinerary. |
| While exploring | Queue visible, accessible neighboring places ahead of likely navigation within a bounded budget. Prepare what players might see without choosing where they must go. |
| First unprepared arrival | Present an intentional, scale-native local scene immediately; generate the richer image in the background. Movement and actions remain available. |
| Later visits | Reuse the shared approved image for the same material state and art-direction version. |
| Meaningful evolution | Preserve recognizable landmarks and regenerate or edit the scene when its defining physical properties change. |

Generating everything up front delays learning about the visual language and
spends effort on unvisited places and states that may change. Pure first-visit
generation makes the crucial first encounter depend on provider latency and an
unreviewed image. Combining reviewed entry coverage with asynchronous expansion
addresses both costs. Set the initial coverage after choosing actual beta entry
points and adjacent routes; there is no justified fixed image-count target yet.

## What exists today

Inspected at local implementation `df4fe5c`:

- Four curated local images cover a connected region, room, object and molecule.
  They were generated during this session, with references linking the images;
  [provenance and briefs](../media/expressive-world.md) record the details.
- `/app` uses a local image while its eligibility anchors match. Otherwise it
  requests `/image` on arrival and sensory revision, with a local canvas scene
  available while imagery is unavailable. Late responses cannot replace the next
  place's scene. The local review server currently disables paid image calls.
- `/image` resolves canonical node state, checks its cache, then synchronously
  calls `fal-ai/fast-sdxl` with a structured text prompt when configured and within
  its call budget. It stores a provider URL in SQLite. Its current cache key is a
  node/seed/style signature, without the old five-history-event bucket.
- The on-demand endpoint is a different generation workflow from the curated
  images. Its quality has not been validated against those images. Existing
  molecule/atom prompt baselines still favor diagrams and schematics.
- There is no durable artwork job queue, generation deduplication across requests,
  adjacency prefetch, automated reference-conditioned production workflow,
  first-party image archive or comprehensive visual-state acceptance check here.
  The current local material-field fallback is functional but is not yet a
  cinematic scene for each scale.

[ADR-002](../decisions/ADR-002-image-generation.md) contains historical architectural
and price estimates. Its automatic-generation quality assumptions need revisiting;
old prices are not a current provider quote or a beta budget.

## Production conditions to establish

1. **Use one art brief per place and represented state.** Derive subject, scale,
   material, geometry, atmosphere, landmarks and consequential changes from
   authoritative world state. Combine this with versioned art direction and
   relevant family/neighbor references. Artwork interprets reality; it does not
   create unrecorded geography, inhabitants or player actions.
2. **Validate the workflow against the accepted examples.** Compare candidates
   for each scale and for materially changed states before choosing a provider,
   model and settings. Review identity, physical correspondence, cross-scale
   relationships, crop, continuity after an edit, latency and actual cost per
   accepted image, including rejects and retries. A provider key alone is not
   evidence of quality parity.
3. **Run bounded background jobs.** Deduplicate jobs for the same node, represented
   state and direction version; persist retries and completion. Coalesce superseded
   states, discard obsolete results for the live view and retain provenance. Apply
   budgets, access rules and priority without blocking play or revealing sealed
   content. Prefetch is bounded by reachable possibilities, not the whole tree.
4. **Own the resulting assets.** Keep durable first-party copies, thumbnails and
   appropriate delivery formats, with hashes and source/revision metadata. A
   provider URL alone is not a durable world-image archive. All viewers should
   share a consistent approved representation of the same state.
5. **Separate fast state from scene identity.** Lighting, weather, transient motion
   and small live effects can change immediately in the renderer. A destroyed
   bridge, changed terrain or fractured object requires an updated base image or
   a capable local representation. Do not cover a materially false image with
   particles and call it current. Reuse a prior image only while it remains true.
6. **Preserve evolution without freezing art direction.** Version generated media
   and their state associations. Keep original birth and event history intact.
   A later renderer may reinterpret recorded state; presenting an exact visual
   archive additionally requires retaining the actual asset and its version.
   Label reinterpretation honestly when an old rendering is unavailable.

These conditions require implementation and measured evaluation before the
proposed service is production-ready. They do not require pre-rendering every
possible future state or waiting for full 3D/neural-world rendering.

## Beta acceptance

A new player should arrive in a finished scene immediately at supported entry
points, discover more than one worthwhile route, and recognize the same place
after a material change. A surprise destination must remain attractive, meaningful
and fully playable while its art is prepared. An outage must not impede play.

Measure first-visit image readiness, job latency, duplicate generation, rejected
images, spend per accepted scene, and player recognition across visits and scales.
Set operational targets after testing candidate pipelines; do not substitute
unverified price or latency assumptions for the beta gate.
