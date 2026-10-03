# Ambition and boundaries — where Enfolded is boxed in, and what a model-forward Enfolded looks like (2026-10-03)

**Status:** strategic assessment for the owner and development team. It records
findings and a decision agenda; it ratifies nothing, changes no covenant, and
authorizes no implementation. Baseline: `main` at `20c3f10` (PR #107 merged).

**Method.** Read-only audit of the code (18,935 lines of Python, ~7,800 lines
of client JavaScript, 27 migrations), all 28 ADRs, every roadmap/design/pitch
document, the ten most recent evaluations, and the CHANGELOG; plus a same-day
web survey of neural game engines, generative media, agent-society research,
shipped AI-native games, and current Claude pricing. Epistemic status is marked
once per section: **confirmed** means read in code, docs, or an official page
today; **secondary** means a press or search summary of a source this sandbox
could not open; **inferred** is this document's judgment.

---

## 0. Verdict

1. **The permanence architecture is not the box.** The sacred layer is small and
   correct: an append-only chronicle (plain traces append through
   `record_mutation`; every substance change goes through one atomic delta API),
   immutable born rows as identity, write-time deltas with a per-node version
   cursor, one canonical seed, one pinned hinge. Every serious 2026 multiplayer world-model
   result (Odyssey's Agora-1, the MASS and Magpie papers, Nvidia's Gamma-World)
   converged on the same shape: a canonical state server with per-client
   rendering. Enfolded already owns the hard part.
2. **The box is three early choices the sacred layer does not depend on**, plus
   a process posture that outlived its reason. (a) *Content is code*: eleven
   scales enumerated in ~25 literal tables, a strict tree, property-only deltas,
   and node identity equal to the display name. (b) *The model is kept at the
   edge*: four call sites, prose and enum classification only, a previous-
   generation default model, and ambient life that is a 44-line finite-state
   machine with zero model involvement. (c) *The senses are a pure function of a
   property vector*, elevated from a rendering choice into a covenant. (d) The
   merge rituals, "bounded" and "minimum contract" language, and daily call caps
   were tuned to protect a production history that has never existed: the
   product is not deployed, the chronicle is empty, and there are zero players
   after 28 ADRs.
3. **Do not adopt a neural game engine as the world's substrate in the next 12
   months. Do adopt neural rendering of chronicled state and model authorship
   under ratification, now.** Frame-generating world models have no developer
   API (Genie), cost about $72 per viewer-hour (Decart), drift after roughly a
   minute, and cannot share state across viewers. What is production-grade today
   is persistent generative 3D (World Labs Marble at ~$1.20 per generation, rendered
   in-browser by MIT-licensed splat renderers), cheap model cognition (an
   attention-gated living world at Enfolded's scale has a fixed floor of about
   $60–210 per month plus $0.18–0.86 per player-hour; $700–3,500 per month is
   the always-on ceiling), structured outputs, 1M-token context, and commodity
   voice. The ambitious move is to make the model a sanctioned *author* of the
   world and the renderer a *function of recorded state*, not to replace the
   world with pixels.
4. **One thing must precede first production history; everything else can be
   an event.** By ADR-009's own logic ("an archive is only as complete as its
   earliest recording"), the identity/lineage and provenance schema must land
   before launch, because a rename or merge cannot be represented retroactively.
   Then launch a pilot cohort. Perpetual pre-launch is now the largest risk in
   the project, larger than any architectural one.

---

## 1. State of play (confirmed)

| Fact | Evidence |
|---|---|
| Production has never been deployed; the chronicle is empty | `docs/pitch/beta-brief.md:28` "pre-release; production is not deployed"; `docs/roadmap/pre-launch-window.md` "Nothing is deployed"; CHANGELOG head: `v0.1.1-qa.2` running at `127.0.0.1:8080` against an isolated QA database |
| Zero external players; three GitHub issues, all by the owner | `docs/evaluation/2026-09-12-pilot-protocol.md` "No participant research has been conducted"; M7 unrun; issue list #87–#89 |
| 28 ADRs; ADR-012 through ADR-022 and ADR-013/018 remain Proposed while their code is merged | `docs/decisions/`, `docs/roadmap/discovery-and-return.md` decision register |
| The model is called in exactly four places | `consciousness/__init__.py:1105` (node voice, `max_tokens=256`), `:1206` (agent voice, `max_tokens=200`), `:1266` (moderation classify, Haiku), `consciousness/interventions.py:58` (intent → enum-bounded JSON schema) |
| Default voice model is one generation behind and more expensive than the current Opus | `consciousness/__init__.py:37` `claude-opus-4-8` ($5/$25 per MTok) vs `claude-opus-5-5` ($4/$20, cache reads $0.20) |
| Ambient agents involve no model at all | `agents/behaviors.py` is 44 lines; `grep -rl anthropic agents/` returns nothing; `server/heartbeat.py` "FSM-driven — zero API spend" |
| Eleven scales are enumerated by name in ~20 source modules (25 literal tables) | `multiverse/generator.py:32` `LEVELS`; verbs, interventions v2/v3, description, senses, wrap, quality, consciousness (`LEVEL_VOICES`, `LEVEL_LORE`, `LEVEL_FALLBACKS`, `_SCORE_FORMS`), puzzles (`CANONICAL_LEVELS`, banks, `_TOTAL_SCALES = 11`), `server/imageprompt.py`, `server/world_mechanics.py`, `agents/roster.py`, `interface/__init__.py`, `static/{nodeart,score,explorer,clientlogic}.js`; clients hard-code `MAX_WORLD_DEPTH = 11` (`frontend/src/App.jsx:21`) |
| Node identity is the display name string, path-suffixed; nothing reads history by path | `multiverse/store.py:145` `resolve_node_by_name` parses digits from the name; every durable table keys on `node_name`; `world_nodes.path` exists but no reader joins history through it |
| The scene is 2D canvas; PixiJS is a dependency but constructs nothing | `frontend/package.json:19`, `frontend/src/main.jsx:5` import for CSP only; `frontend/src/components/SceneView.jsx` (39 lines) drives `static/sensory.js` (109 lines); no `Application(` anywhere in `frontend/src` |
| Imagery is a 4-step SDXL wash with URL-only caching; four curated plates exist | `server/handlers.py:1025` `fal-ai/fast-sdxl`; `node_images` stores provider URLs; `multiverse/senses.py` keys plates to four exact born names |
| Material consequence reaches the origin and about one ring | `multiverse/effects.py:42` `EFFECT_THRESHOLD = 0.3`; 2026-09-07 probe: 16 propagated events, one material change |

The 2026-07-19 ensemble evaluation said it in one sentence that is still true at
HEAD: *"Claude never acts, initiates, or persists as an agent. Every Anthropic
call in the codebase is a human-pulled request/response."* The README's concept
paragraph ("Nodes are animated by Claude… whether you're speaking to a world node
or an AI agent who has settled into one is a question the system leaves
deliberately open") describes a product the routing table does not implement.

---

## 2. What is actually frozen, and what the owner fears (confirmed)

The owner's concern is that the history/replay design makes the world "frozen in
time." The audit separates the mechanisms that are genuinely one-way from those
that merely feel that way.

| Mechanism | Where | What it protects | Verdict |
|---|---|---|---|
| Append-only `world_mutations`; redaction edits only free text; pruning double-gated | `persistence/__init__.py:755-828`, `:2118-2195` | The memory thesis; accountability | **Keep.** Evolution needs *more* events, never rewrites |
| Chronicled deltas written atomically with a per-node version cursor | `persistence/__init__.py:1275-1379` | State-at-T without replaying code | **Keep.** This is what makes change *representable* |
| Immutable born rows (`save_world_nodes` refuses overwrite) | `persistence/__init__.py:1966` | Identity stability; "a bank edit cannot silently rewrite the world" | **Keep for identity; incidental for content.** New rows (births) and new event kinds (rename, re-aspect, retire) are fully compatible |
| One canonical seed | `server/guard.py:96-138` | No parallel durable histories | **Keep** |
| Pinned wrap hinge | `multiverse/wrap.py`, `pin_world_meta` | A monument's continuity | **Keep** (a second hinge is a new key plus a chronicled crossing) |
| Era names computed at read time from frozen banks | `multiverse/chronicle.py:22-52` | Already-displayed names | **Incidental, acknowledged debt.** Materialize eras |
| Identity == display name with path digits | `multiverse/store.py:145-177`; every `node_name` column | Cheap resolution, forgery refusal | **Incidental, became load-bearing.** This, not the chronicle, is why renames and merges are "impossible" |
| Depth == level == index in an 11-item list | `generator.py:457-459`, `store.py:43,159`, clients | Prefix-stable addressing | **Incidental** |
| ~25 per-level literal tables | listed in §1 | "Scale is meaning" | **Incidental.** The covenant survives a registry; the tables do not need to be code |
| Strict tree; cascades, forecast, and seals walk `parent`/`children` only | `causality/__init__.py:141-177`, `forecast.py`, `gates.py` | Finite cascades, honest augury, liveness | **Partly real.** The wrap already proves traversal edges can live outside containment |
| Property patches are the only chronicled change kind; Wayback folds one name's properties | `persistence/__init__.py:1693-1807` | Honest state-at-T | **Real invariant, incidental scope.** Add structural event kinds with their own fold |
| Art, sound, and senses are entropy-free pure functions; a test forbids `Math.random`/`Date.now` | `static/sensory.js`, `static/score.js`, `tests/test_frontend_contract.py:280-282` | Co-op reproducibility; Wayback "today's eyes" | **Incidental choice elevated to covenant.** ADR-009 and ADR-011 already define Wayback as *reinterpretation, not playback*, which means renderers may change freely. What history needs is state-addressability, not determinism |
| The model may author prose and classify intent only | `consciousness/interventions.py:8-18` (enum schema, `amount` fixed to 1), ADR-013 "may propose text or an allowed action, not invent persistent canon" | Consent, auditability, 2025 budgets | **Real in spirit, closed enum in practice.** Two reasons are braided: consent/append-only (keep) and distrust of model judgment (decaying) |
| FSM agents at zero spend; agents have no participant identity | `agents/agent.py`, `heartbeat.py:383-583` | Budget; "agent solves don't count" | **Incidental (cost).** The one real rule, that simulated solves earn no human progress, exists *because* solves are dice rolls |
| Golden pins cover puzzle-generator output for epochs 0–2 | `tests/test_continuity_freeze.py:233-300` | Solved state keyed on puzzle name | **Pre-store artefact.** `puzzle_instances` (migration 0022) already pins served definitions; the generator pin is now redundant with it |

**The decisive finding is historical, not technical.** ADR-006 was written to
*unfreeze* the world. Its own text: "the freeze is not a design goal. It is the
integrity mechanism forced by using code as storage… Store the world as data…
and the banks are free." Option B promised "Open evolution, in the world's own
grammar… frontier growth… a rename, a re-aspect, a terrain shift — becomes a
chronicled world event." The trigger fired on 2026-09-07 and was answered by
ADR-013, which defines "the minimum contract" and states: "Do not add renames,
reparenting, new scales, era-bank changes, or new geography to this first
contract." The world is rigid by *policy*, not by data model. The data model was
built precisely so that this policy could be lifted.

---

## 3. Where we boxed ourselves in (confirmed unless marked)

### 3.1 Content is code

Every scale is a hand-authored content vertical: name forms, property
generator, breadth, one verb plus three v2 operations, voice register, lore,
fallback line, puzzle banks, art family, musical form, image style, roster home.
Adding a twelfth scale or a new *kind* of place costs the full vertical plus a
golden re-pin ceremony. ADR-008 forecloses a twelfth depth ("below the particle
is the whole"), which is a sound Bohmian reading; but it also means the only way
the world can gain *new kinds of thing* is breadth within the existing eleven,
and even breadth growth has no event kind. `GENERATOR_VERSION` is a stamp that
no code reads back, so later births cannot even use newer rules per row.

Topology is a strict tree rebuilt per request from path rows; portals, tangled
hierarchies, or places that belong to two parents are unrepresentable except as
the single wrap passage, which lives in the traversal layer by deliberate design
and proves the pattern works.

### 3.2 The model is kept at the edge

The model writes 256 tokens of node prose, 200 tokens of agent prose, an 8-token
moderation verdict, and a JSON object whose `op` field is an enum of at most
four verbs. It never authors a name, a property, a puzzle, an event, an image
prompt, a melody, or an era. It never speaks first (the ensemble's proposed
experiment was "one budgeted call per world per day"). Rule changes are made by
accreting frozen interpreters (v1, v2, v3 interventions; `semantics_version` 1
and 2) because "recompute with the latest function" was the only alternative
considered.

Every one of these choices rests on a 2025 economic premise that no longer
holds: Opus at $5/$25, a 500-call daily cap for 20 users, an 8-way semaphore
"so a synchronized burst can't trip org-level RPM," SDXL at $0.003 per image,
and a 4,096-token caching floor. Today (confirmed, platform pricing page
2026-10-03): Opus 5.5 $4/$20 with cache reads at $0.20; Sonnet 5.5 $2/$10;
Haiku 4.5 $1/$5 with Haiku 5.5 announced for the coming weeks; batch at 50%;
1M-token context at flat rate; structured outputs GA; a client-side memory
tool GA. The run-rate of a *fully* model-driven Enfolded at current scale:

| Workload (list prices, cached prefixes, before the ~1.3× tokenizer correction on non-Haiku models) | Haiku 4.5 | Sonnet 5.5 | Opus 5.5 |
|---|---|---|---|
| 12 ambient inhabitants thinking once per minute, 24/7, per month | $674 | $1,348 | $2,385 |
| Re-narrating 50 places per hour via Batch, per month | $50 | $101 | $191 |
| One-hour player session, 40 exchanges | $0.10 | $0.19 (+thinking ≈ $0.31) | $0.34 (+thinking ≈ $0.58) |
| Whole living world, always on: 12 inhabitants, ~4,200 places, 1,000 sessions/month | ≈ $700–900 | ≈ $1,600–2,000 | ≈ $2,900–3,500 |
| **Attention-gated (the §6.2 design): inhabitants reflect hourly via Batch, 50 places/hour via Batch, cognition on stage only while a player is present** | fixed ≈ $60/month + ≈ $0.18 per player-hour | fixed ≈ $110/month + ≈ $0.35–0.47 per player-hour | fixed ≈ $210/month + ≈ $0.62–0.86 per player-hour |

The always-on rows are the ceiling, not the recommendation. Gating cognition on
attention moves nearly all spend onto player-hours, where a subscription can
carry it (a subscriber at $8–12 per month playing 5–15 hours costs $1–13 to
serve on Opus and under $3 on Haiku), and leaves a fixed floor in the low
hundreds of dollars per month. Output tokens dominate once caching is on (77% of
the Haiku ambient bill is the 200 output tokens); a 60-token structured "thought" halves it, and nightly
reflection via Batch halves it again. The per-session cost is small enough that
model choice for Speak should be decided by latency and quality, not cost.
(Arithmetic reproducible from the research scratch script; inferred totals.)

### 3.3 The senses are a pure function of a property vector

What the player sees is a 2D canvas gradient with bands, particles, rings and
scars, optionally washed by a 4-step SDXL image keyed to a coarse style
signature, or one of four curated plates for four named places. What the player
hears is eleven sampled forms sequenced by properties. Both are forbidden
entropy by test. This was adopted so Wayback could redraw past states, but
ADR-009/011 define Wayback as "the node as it was, seen with today's eyes," so a
renderer edit *already* reinterprets the past. The honest contract was always
"state is historical, presentation is current." That contract is satisfied by
any renderer whose output is addressable by `(node id, senses.revision, renderer
version)` and cached, including a diffusion model, a Gaussian-splat volume, or a
video loop. Determinism of the renderer is not required by history; recorded
provenance is.

### 3.4 The process posture

The house rules are optimized against a threat that has not materialized: a
careless change rewriting a precious production history. In their service the
project produced reference-quality continuity engineering, 1,358 Python tests
(collected on this branch) plus about 120 Vitest tests, and a decision record of
unusual honesty, while the owner's own playtesting
found the experience wanting twice in September (the universal composer,
delegation, gallery pane and undifferentiated sound; then the preview). The
instructions reward "bounded," "minimum," "no new write paths," and interpreter
accretion. They do not reward widening the world's expressive range. A team of
the strength the owner describes, with models improving quarterly, should spend
its caution on the five covenants that protect players and history, and its
ambition on everything else.

---

## 4. Where gaming and generative technology stand, and where they are going (secondary unless marked)

### 4.1 Neural game engines and world models

| Technology | Access today | Cost | Consistency | Verdict for Enfolded |
|---|---|---|---|---|
| Google Genie 3 / Project Genie | Consumer only, $200/mo AI Ultra; **no API** | n/a | 720p, 60-second session cap; drift past ~1 min | Not adoptable |
| Decart Oasis 3 Preview (promptable world model, gRPC SDK) | Public API | $0.02/s ≈ **$72 per viewer-hour** | Degrades over long sessions; driving-sim tuned | Demo-grade; watch |
| Decart Lucy 2.5 / MirageLSD (realtime video-to-video) | Public API | $0.01–0.02/s | Restyles a live feed, <40 ms | Could neural-restyle our canvas per player at $36–72/hr; paid feature only |
| Odyssey-2 / Agora-1 (four players in one generated world) | API by request, private pricing | ~$1–2/user-hr (estimate) | Minutes; **state model + per-view renderer** | The architecture lesson, not a vendor |
| Runway GWM Worlds 2 | Research preview, no API | n/a | — | Announced-only |
| Skywork Matrix-Game 3.0 (Apache 2.0) | Open weights | A/H-class GPU; ≈$2–3 per viewer-hour on a rented H100 | 720p @ 40 fps, "minute-long" memory | Q2 2027 candidate for an engine-authoritative render of one scale |
| Tencent HY-World 1.5 / GameCraft-2 | Open weights, licence excludes EU/UK/KR | 24–80 GB VRAM | 480p | Research |
| Microsoft Muse/WHAM, Nvidia Cosmos 3, ByteDance spatial model | Lab demo / robotics / announced | — | — | Not relevant yet |
| **World Labs Marble 1.1 + World API** | Public REST API (confirmed) | **≈ $1.20 per generated world**, exportable `.spz`/`.ply` splats and meshes | **Persistent asset** | **Adopt.** AMD acquisition pending (closing year-end); export on generation |
| Spark 2.0 (World Labs, MIT) / SuperSplat 3.0 (PlayCanvas, MIT) | Open source (confirmed) | Free | WebGL2 / WebGPU splat renderers with LoD streaming | **Adopt** beside or instead of the Pixi dependency |
| TRELLIS.2 (MIT), Hunyuan3D, Meshy/Tripo/Rodin | Open weights / hosted APIs | $0.01–1.50 per asset | Static GLB with PBR | Props and objects per place |
| StreamDiffusionV2, Krea Realtime 14B (non-commercial licence) | Research code | 4×H100 / B200 | Rolling KV cache | Not for a 3-person team yet |

Two operational facts: Fly.io removed all GPU machines after 2026-08-01, so any
self-hosted renderer lives on Modal, RunPod, Lambda or fal, not Fly; and no
real-time generative video model runs client-side in a browser today.

**The field converged on Enfolded's architecture.** Agora-1 got four players
into one generated world by splitting a learned *state model* from a per-view
renderer. MASS claims 1,024 players by advancing one authoritative typed global
state and rendering each view on demand. Magpie keeps a real engine
authoritative and renders white-box frames into imagery. The "Programmable World
Model" and "From Pixels to States" papers argue the same decoupling. In every
case the generative layer is a *renderer of state*, and the pixel models' memory
horizon is minutes with explicit 3D memory as the only lever. Nothing credible
claims hours of pixel-level persistence. Enfolded's differentiator is memory
measured in months; a pixel model cannot carry it.

### 4.2 What shipped, and what players said

Commercial AI-NPC integrations (PUBG Ally, inZOI Smart Zoi, Fortnite's Vader)
were received as mixed to scathing; Ubisoft's Teammates is still a closed
playtest. The AI-native titles that worked made language *the* mechanic inside
a verifiable loop (Suck Up!, AI2U, Death by AI), and the persistent-world
products that survived moved the model *out* of ownership of state: Latitude's
Voyage ("the engine simulates, the AI turns it into story"), Hidden Door
(engine-tracked cards filled from curated tropes), 1001 Nights (words become
only items the game already knows), Infinite Craft (generate once per
canonical pair, cache forever, credit the first discoverer). Dreamworld, a
generative sandbox MMO, was pulled from Steam within four months. Player
sentiment is conditional and skeptical: roughly 77–85% of surveyed players are
negative on AI-generated quests and dialogue specifically, and GenAI-disclosed
games draw lower recommendation rates than procedural ones because players read
GenAI as low investment. Enfolded's covenants ("failure stays in fiction," "the
chronicle blurs," engine-owned state) are commercially well-aimed. Disclosure of
which surfaces are model-authored is the right posture, not concealment.

### 4.3 Agent societies: what works and what breaks

Project Sid's PIANO architecture ran a thousand Minecraft agents through a
single cognitive bottleneck and observed specialization, voted tax rules and a
spreading religion; its named failures were repetitive loops, hallucination
cascades, and say/do incoherence that grows with independent output streams.
Stanford's 1,052-person study showed rich specific biography beats persona
templates by 14–15 points, which is exactly what stored rows plus the chronicle
provide for free. Letta's sleep-time compute moves reflection off the hot path.
Two 2026 memory results should shape any design: *Manufactured Confidence*
(hedged remarks rewritten into memory become flat facts the agent obeys; keep
the hedge in the store) and *The Memory Trust Gap* (agents over-trust stale
memory over an authoritative tool; pre-resolve facts from the database before
prompting). Collusion among capable agents emerged in 94% of long-horizon
mutual-verification trajectories; governance at deployment, not prompting,
controls it. Anthropic's own multi-agent system used ~15× chat tokens and won
by explicit effort rules, delegation briefs and checkpoints.

### 4.4 Claude specifically (confirmed)

Text and image in, text out; **no realtime audio API** (pair ElevenLabs or
Inworld TTS-2 around a streamed Messages call, per Anthropic's own cookbook).
Structured outputs enforce shape and enum membership but **not numeric bounds**,
so property-delta limits must be validated in code. Forced tool choice is a 400
on the 5.5 models; use `auto` with `strict: true` or `output_config.format`.
Mid-conversation `role: "system"` messages preserve the cached prefix. The
memory tool and Managed Agents memory stores exist. Fable 5.1 text carries a
statistical watermark; it adds no visible characters.

---

## 5. Should Enfolded adopt a neural game engine? (inferred)

Three distinct things hide under that phrase. They deserve three different
answers.

**Tier 1 — neural *rendering* of authored state.** The world decides what a
place *is*; a model decides what it *looks and sounds like*, keyed to the
served state. **Adopt now, in parts.** The seam already exists:
`multiverse/senses.py` produces a versioned sensory description with a
`revision` digest, and `startSensory(canvas, node, {imageUrl})` consumes it.
Define a render contract: `(node id, render key, renderer id, renderer
version) → asset`, cached in first-party storage, with provenance, where each
renderer declares how coarse its key is. `senses.revision` hashes the current
properties (`multiverse/senses.py:68`), so a renderer keyed on it regenerates
on every material change. That is right for the free procedural canvas and
wrong for paid media, which would otherwise bill per delta. Paid renderers key
on a coarser material class (the existing `style_signature` pattern) or on
structural events only, and the procedural layer draws the fine-grained state
over them. That is the asset-reuse policy and its fidelity trade-off: generated
layers show what kind of place this is; the canvas shows its exact present.
Then plug in, in order of maturity: (i) a current image model with reference conditioning
to the four curated plates, replacing the SDXL wash with *the* scene; (ii) a
Marble splat volume per visited place, viewed in Spark, giving the "character
movement within a node" that neither client has; (iii) short image-to-video
ambient loops; (iv) later, engine-authoritative video rendering of one flagship
scale when a distilled open model runs at ~$0.50 per viewer-hour. Wayback uses
the same contract against historical state and keeps its honesty line.

**Tier 2 — neural *simulation*: the model decides what happens.** This is the
thesis the README has promised since the first commit and the codebase has
never implemented. **Adopt now; it is the core of the ambitious Enfolded.** The
pattern that works everywhere (Voyage, inZOI, PIANO, Infinite Craft, Enfolded's
own ADR-009) is proposal → deterministic validation → ratification → append-only
event. The model becomes a sanctioned author with a provenance kind; the engine
remains the authority on what is admissible. Section 6 describes it.

**Tier 3 — a neural *engine* as the substrate: a world model generates frames
and physics from actions in real time, and that *is* the world.** **No, not for
a shared persistent world in the next 12 months**, for four reasons that are
independent of taste: consistency horizons are minutes; no vendor offers shared
state across viewers except as research; the only self-serve API is $72 per
viewer-hour and tuned for driving; and Enfolded's entire value is a memory that
outlasts any session, which pixel models structurally lack. The right use of a
Tier 3 model, when one becomes available at tolerable cost, is a per-player
*vision*: "enter the plate" from a place, explore a generated moment seeded by
the canonical render, framed in fiction as a dream, leaving no trace in the
chronicle. That respects every covenant and gives players the thing that only
these models can do without letting them touch the truth.

**What it would look like concretely.** A Place is the born row plus its
chronicled deltas. From that, the server derives one sensory description. From
that description, any number of renderers produce addressable, cached,
provenance-stamped assets: the procedural canvas (always available, keyless),
an image plate, a splat volume, a video loop, a music cue, a spoken voice. The
browser composes whichever it can run. Everyone standing in the same place at
the same revision sees the same canonical render. Wayback renders a historical
revision through today's renderers. The chronicle never records a pixel.

---

## 6. The model-forward Enfolded (inferred; the ambitious picture)

### 6.1 The World Mind: a sanctioned author

A model-driven world process runs on the existing heartbeat with a dollar
budget, not a call cap. It reads the chronicle with 1M-token context behind a
cached world bible, and it *proposes events in a typed grammar*: a new child at
a frontier (birth is already lazy and idempotent), a re-aspecting, a rename
with lineage, an era turning, weather of meaning across a region, a situation
seeded from what players actually did last week, a migration of an inhabitant,
a law shifting in one universe. A deterministic validator enforces the
constitution (the five covenants, per-scale numeric bounds the schema cannot
express, sealed-lineage liveness, uniqueness, rate limits); a cheap second model
reviews prose fields only; ratified proposals become chronicled events with
provenance kind `world`, every one of them visible in Wayback by construction.
Rejected proposals are kept in an append-only proposal ledger for audit. The
model never touches `world_nodes` rows; it only ever *adds* rows and events.

This is ADR-006 Option B's promise delivered with a 2026 author. It makes the
world speak first. It makes the chronicle the thing the world *reads* as well as
writes, which is what "every part enfolds the whole" should mean mechanically.

### 6.2 Inhabitants with minds, and an open roster

Tiered cognition: the FSM keeps locomotion and safety (cheap, reproducible);
a model forms intentions at a cadence (every tick for the cast member on
stage, every N ticks otherwise), through a single decision bottleneck per tick
in the PIANO sense; nightly Batch reflection writes structured memory as cited
claims with hedges preserved (`{claim, hedge, event_ids, expires}`), and facts
resolvable from the database are pre-resolved before prompting. Inhabitants
gain full vocabulary parity with humans (today agents use the original verb
path only), make and keep promises (ADR-022 already has the commitment seam),
hold and pass rumours that surface only in Speak and never in the chronicle,
and are addressable as participants.

Then open the roster. Expose the world to external agents through the same
protocol humans use, with no privileged API: an MCP server and a documented
agent credential under the same covenants, the same consent rules, the same
rate limits. Two 2026 precedents (Open MMORPG, SpaceMolt) show the pattern; none
has Enfolded's memory. "A shared consciousness space inhabited by humans and
agents" becomes literally true and becomes a growth loop: other people's agents
live here. The covenant that agent solves do not count as human progress was
written for dice rolls; once agents actually read the world and answer, the
owner should decide whether it becomes a separate board (ADR-017's intent) or a
shared one.

### 6.3 Scale charters as data

Replace the ~25 literal tables with one versioned `Scale` registry record per
scale: name forms, property schema, breadth, verb vocabulary with physical
semantics, voice register and lore, fallback line, art direction, musical form,
image style, roster homes. Every surface consumes the registry. A new scale or
a new *kind* within a scale is one record plus tests, authorable by the World
Mind under ratification rather than by a Python batch and a golden re-pin. This
preserves "scale is meaning" (the registry *is* the meaning) and makes lateral
richness possible without a twelfth depth, which ADR-008 rightly forecloses.

### 6.4 Senses

The render contract of §5, implemented in three steps: first-party asset
storage keyed by `(id, render key, renderer, version)`; a current image model
with reference conditioning replacing the wash, keyed on material class so it
regenerates at cents per class change rather than per property delta; Marble
splats for visited places with Spark in the client, keyed per place and
regenerated only on a structural event (rename, re-aspect, retirement), at about
$1.20 per generation (World Labs bills per generation, not per place), lazily on
first visit, so a first pass over the whole world is roughly $5k and the
recurring line is the structural-event rate times $1.20. Music: Stable Audio 3
(open weights, commercial under $1M revenue) or Lyria 3.5 cues conditioned on
the scale's musical form and the place's state, generated once per form-and-
state class and cached, so "scale is meaning" is expressed by conditioning
rather than by eleven hand-sampled forms. Media therefore carries a recurring
line of its own, bounded by the reuse policy rather than by player-hours; the
budget for D3 must state the regeneration rate it accepts. Voice: ElevenLabs or Inworld TTS-2 for places and
inhabitants, at cents per spoken minute; speech input stays explicit-submission
per ADR-016.

### 6.5 Time

Materialize eras (an additive table stamped on first display, as ADR-006
already sketches), and let the World Mind *turn* them as chronicled events with
annals that cite event ids (extending ADR-021's evidence-bound narration, never
duplicating it). World speed becomes a law the World Mind may propose to change
per universe. Seasons emerge from the ledger, not from a cron schedule.

### 6.6 Puzzles as instruments

`puzzle_instances.definition` is already a stored, versioned JSON object.
A `definition_version` 2 whose definition is model-authored at first use would
be served identically to today's. Validating it is new work, not a reuse: the
existing gate (`puzzles/quality.py`) is a census of family balance and
prompt/answer uniqueness over the procedural population, and leak screening
(`puzzles/generators.py:329`) lives inside the procedural generator; neither
proves an arbitrary authored definition solvable. Before any authored
definition is pinned, a runtime validator must (a) run the leak screen against
the node's and its ancestors' current properties, (b) check answer format,
determinism and the per-node difficulty and attempt limits, (c) establish
solvability independently, by a deterministic check where the family's answer
is computable and otherwise by a second model solving from prompt and hints
alone without the answer, and (d) on any failure fall back to the procedural
version-1 definition. An unvalidated definition must never be pinned, because
seals and constellations key on puzzles and a broken one becomes a durable
gate. Per-node difficulty, server-held answers, and seals all survive; the
ecology census keeps running over the mixed population. Referential puzzles (ADR-015) and situations
seeded from real history follow. The Causal Augury's purity claim (ADR-010)
must be re-stated once lineages can change; that is a revisit the ADR already
names.

### 6.7 Covenants, re-worded

Keep five covenants exactly as written: every player owns their actions; the
seal never imprisons; difficulty is per-node; failure stays in fiction; the
chronicle is append-only with three maintenance mechanisms. Keep the chronicle
blur as the chronicle's rule while allowing provenance *kinds* (`player`,
`inhabitant`, `world`) that are not actor-type flags on traces. Replace
"deterministic" with **"recorded"**: any generation that samples must record its
seed and provenance so it can be reproduced or at least attributed; birth
identity stays a pure function of `(seed, path)` under a dispatchable generator
version. Add one covenant the house rules currently lack: **every batch must
widen the world's expressive range or deepen a player's agency, not only harden
what exists.**

### 6.8 Infrastructure that follows

Move the default voice model to Opus 5.5 (cheaper and better than 4.8) with
Sonnet 5.5 or Haiku for ambient cognition; budgets in dollars per day with the
existing in-fiction degradation. First-party media storage (Tigris or S3) with a
job queue for generative assets; Litestream, which ADR-005 already called the
right end-state. The stdlib threaded server and hand-rolled WebSocket are fine
for text at beta scale; a media or voice channel needs a separate async
transport, and GPU work runs on Modal/fal, not Fly. None of this is a rewrite of
the world; all of it is a transport layer around the same database.

---

## 7. Obstacles to eliminate (inferred, with the code they touch)

1. **Identity is the display name.** Add a stable node id (the existing `path`
   or a surrogate) as the foreign key for history, with an alias table so names
   can change and old rows keep the old name. This is the single change that
   must precede first production history; everything after it is an event.
2. **ADR-013's exclusion clause.** Ratify the evolution grammar ADR-006
   promised: births at a frontier, rename with lineage, re-aspect, traversal-
   layer reparenting (portals, like the wrap), merge/retire with forward
   pointers, era turns, law shifts. Each is a chronicled event kind the Wayback
   fold understands.
3. **"No entropy in renderers" as covenant.** Replace with the render contract
   (recorded, addressable, versioned); keep the procedural canvas as the
   keyless, deterministic fallback.
4. **"The model may not author canon."** Replace with "the model may author
   under ratification, with provenance," enforced by a validator and a ledger.
5. **Zero-spend FSM as a stated contract.** Replace with budgeted cognition.
6. **Eleven literal scales.** Replace with the registry.
7. **Daily call caps as design.** Replace with dollar budgets; keep the
   in-fiction degradation.
8. **Two browser clients.** Promote `/app` to the default and retire the
   explorer as a surface, per ADR-012's direction and the ADR-005 update it
   requires; one client halves every future UX batch.
9. **Golden pins over puzzle-generator output.** Pin births; let stored
   instances carry puzzle continuity.
10. **The default model and the semaphore.** Opus 5.5; concurrency tuned to
    measured rate limits.
11. **Process.** Keep the merge gate proportional to irreversibility (it already
    says so); strike "bounded" and "minimum contract" as default adjectives;
    allow a batch to be ambitious when it adds only events.
12. **Perpetual pre-launch.** After item 1 lands, run the M7 pilot on the hosted
    world and let the chronicle begin. The owner's September playtests were the
    only external signal the project has ever had; it needs eight more people.

---

## 8. Decision agenda (for the owner; each with a recommendation)

| # | Decision | Recommendation | What it unblocks | Opportunity cost |
|---|---|---|---|---|
| D1 | Ratify an evolution grammar covering births, renames, re-aspect, traversal reparenting, merge/retire, era turns, law shifts, as chronicled events | **Yes, all of them**, operator- and World-Mind-triggered under ratification | The world can change shape, not only properties | Displaces M5/M6 situation and journal polish for roughly one batch |
| D2 | May the model author persistent canon under ratification, with provenance? | **Yes**, with a deterministic validator, proposal ledger, human audit sample, and disclosure | The World Mind; model-authored puzzles, situations, charters | Governance work, and a correction mechanism that must ship with the first authored change: redaction scrubs five text fields and never repairs applied deltas, born rows or pinned definitions, so a ratified but wrong change is reversed by a new chronicled compensating event carrying its reason (ADR-013 already names this), and a bad authored definition or charter is superseded by a new version with a forward pointer; a player who already acted on wrong canon is recorded, not undone |
| D3 | Replace renderer determinism with a recorded, addressable render contract | **Yes** | Image models, splats, generative music, future video; Wayback unchanged | Asset storage, a job queue, and a recurring media line set by the reuse policy (per structural event for splats, per material-class change for plates and cues), which the decision must budget explicitly |
| D4 | Budgeted inhabitant cognition and an open agent roster via MCP | **Yes, after pilot evidence**; attention-gated with a hard dollar ceiling (fixed floor ≈ $60–210/month, variable ≈ $0.18–0.86 per player-hour) | The README's thesis; a growth loop | The only decision with ongoing model-cognition spend (D3 carries the media regeneration line); collusion/drift governance; re-examining the agent-progress covenant |
| D5 | Scale registry and lateral kinds; no twelfth depth | **Yes** to the registry; **keep ADR-008** | New kinds without new verticals | A refactor across ~20 modules; golden re-pin for births only |
| D6 | What must precede first production history? | **Only** the identity/alias and provenance schema | Launch | None; it is additive |
| D7 | One client | **`/app` primary**; explorer retired after the device gates | Every future UX batch | A deliberate ADR-005 update |
| D8 | Budget posture | **Dollars per day**, not calls per day | Honest tuning | None |
| D9 | Process re-tune | Keep five covenants; demote the rest to guidance; add the ambition covenant | Velocity | Re-reading CLAUDE.md with the team |

Decisions D1–D5 each warrant an ADR in house style; this document does not
pre-write them because their *scope* is the owner's call. Once direction is set,
they can be drafted in one session.

---

## 9. Sequencing (inferred; 90 days, three people)

**Phase 0 (two weeks): make evolution representable, and stop paying 2025
prices.** Additive migration for node ids, aliases and provenance kinds;
readers join through id. Default model to Opus 5.5; caps to dollars. Materialize
eras. Draft ADR-029 (evolution grammar), ADR-030 (render contract), ADR-031
(model authorship), ADR-032 (inhabitants and roster), ADR-033 (scale registry).
Then the pilot cohort can begin; the chronicle starts complete.

**Phase 1 (four weeks): the first authored change and the first real
sense.** World Mind v1 on the heartbeat: era turns with cited annals, weather of
meaning across one region via Batch, frontier births at one scale under
ratification. Inhabitant reflection via nightly Batch; one inhabitant keeps a
promise it made in its own words. Render contract plus first-party asset
storage; image model with reference conditioning for the top 200 visited
places; Marble splats for 50 of them, viewed in Spark.

**Phase 2 (six weeks): make the world authorable.** Scale registry refactor
behind the existing tests; model-authored puzzle instances at `definition_
version` 2 behind the new runtime validator with procedural fallback (§6.6);
agent participant identity and the MCP server; generative music cues per
form-and-state class; promote `/app`. Read the pilot
evidence and decide D4's budget ceiling from it.

Opportunity cost, stated plainly: this sequence displaces the remaining
discovery-and-return milestones (M5 situation expansion, M6 identity polish,
ADR-017 leaderboards, ADR-018 collectibles) by about one quarter. The case for
displacing them is that each of those milestones is *content inside a world
that cannot yet change*, and the pilot that would validate them has no players
until Phase 0 ships.

---

## 10. Where this assessment pushes back

- **A neural engine is the wrong substrate for this product in this window.**
  The evidence is unusually one-sided: no API, minute-scale drift, no shared
  state, $72 per viewer-hour. Enfolded's moat is memory; pixel models do not
  have one. Use them as renderers and as non-canon visions.
- **The fear is aimed at the wrong layer.** The chronicle and the born rows are
  not what froze the world; they are what will let it change *honestly*. The
  freeze is name-as-identity, content-as-code, and a policy clause in ADR-013.
- **Player sentiment is real.** Roughly four in five surveyed players dislike
  AI-generated quests and dialogue. The products that won did not hide the
  model; they constrained it to a loop the player could verify and kept the
  engine honest. Enfolded's covenants already do this. Keep them and disclose.
- **Agent societies need governance, not just prompts.** Collusion and drift
  are measured phenomena. The constitution must be code: single decision
  bottleneck, no agent gains from another's verification, repetition monitors,
  a kill switch the guard already has.
- **Interpreter accretion is not an evolution grammar.** Freezing v1/v2/v3
  forever protects accepted promises, which is right, but a living world needs
  rule *lineage* (this law changed, here, because of this) more than it needs
  five parallel physics.
- **The biggest risk is not architectural.** Zero players after 28 ADRs. The
  returning-visitor metric has no data points. The owner is the only playtester
  on record. Ship Phase 0 and let people in.

---

## Appendix A — evidence index

Code: `multiverse/store.py:41,52-91,145-177`; `persistence/__init__.py:686-714,
755-828, 1236-1402, 1693-1807, 1966-1998, 2058-2081, 2118-2195`;
`multiverse/generator.py:32-44, 457-459`; `multiverse/effects.py:42`;
`multiverse/senses.py`; `multiverse/chronicle.py:22-52`; `multiverse/wrap.py`;
`causality/__init__.py:141-177`; `causality/wiring.py`; `causality/staging.py`;
`consciousness/__init__.py:37, 1080-1116, 1206, 1266`;
`consciousness/interventions.py:8-78`; `agents/behaviors.py`; `agents/agent.py`;
`server/heartbeat.py:383-583`; `server/handlers.py:635-673, 839-916, 966-1044`;
`server/guard.py:42-96`; `frontend/src/App.jsx:21`; `frontend/src/main.jsx:5`;
`frontend/src/components/SceneView.jsx`; `static/sensory.js`; `static/score.js`;
`static/nodeart.js`; `tests/test_continuity_freeze.py`; `tests/test_world_store.py`;
`tests/test_wrap_passage.py`; `tests/test_frontend_contract.py:280-282`.

Decisions and evaluations: ADR-006 (Option B text and revisit note),
ADR-008, ADR-009, ADR-011, ADR-013 (exclusion clause), ADR-022, ADR-027
(revisit: "a different world model demonstrates better controllability"),
ADR-028; `docs/evaluation/2026-07-19-expert-ensemble-evaluation.md` §2.3;
`docs/evaluation/2026-08-10-recursion-and-time.md`;
`docs/evaluation/2026-09-07-concept-and-implementation.md`;
`docs/evaluation/2026-09-12-pilot-protocol.md`; `docs/pitch/beta-brief.md`;
`docs/roadmap/pre-launch-window.md`; `docs/roadmap/discovery-and-return.md`.

## Appendix B — external sources consulted (same-day; secondary unless confirmed)

Confirmed by opening the page: Anthropic pricing and models pages
(platform.claude.com, 2026-10-03); structured outputs and memory tool docs;
Anthropic engineering posts on multi-agent systems, context engineering, and
long-running harnesses; GitHub repositories for Tencent HY-WorldPlay and
HY-World 2.0 (licence), SkyworkAI Matrix-Game 3.0, nv-tlabs Gamma-World,
krea-ai realtime-video (licence), microsoft TRELLIS.2, shengshu-ai Vidu-S1 and
minWM, altera-al project-sid, sparkjsdev spark.

Secondary (press or search summaries; the primary domains were blocked from
this sandbox): DeepMind Genie 3 and Project Genie coverage (The Register,
PYMNTS, Android Central); Decart Oasis 3 and pricing (docs.platform.decart.ai
via search, ai-tldr); Odyssey Agora-1 and Odyssey-2 (aitoolly, therundown);
World Labs Marble pricing and the AMD acquisition (radiancefields, CNBC, Tom's
Hardware); Runway GWM Worlds 2 (alphasignal); Nvidia Cosmos 3 and DLSS 5
(Nvidia IR, GDC 2026 page); MASS, Programmable World Model, Magpie, Manufactured
Confidence, Memory Trust Gap, Colosseum (arXiv abstracts via search); PlayCanvas
SuperSplat 3.0 blog; Fly.io GPU sunset (bex.co, Hacker News); Latitude Voyage
(TechCrunch, latitude.io); Hidden Door (Variety, Publishers Weekly, Bicking
design review); Death by AI (Inworld case study); Suck Up!, 1001 Nights,
Whispers from the Star (Steam, Metacritic); Infinite Craft (FlowingData);
Dreamworld (MassivelyOP); Roblox Cube 4D (Roblox newsroom); Open MMORPG and
SpaceMolt (Inven, PC Gamer); Stanford Generative Agents and the 1,052-person
study (Stanford HAI); Letta sleep-time compute; Steam GenAI disclosure and
sentiment studies (VGC, GamesRadar, arXiv 2608.11539); RimWorld apophenia
(Stanford GDT); Dwarf Fortress, Caves of Qud, Wildermyth, EVE (PC Gamer and
others).
