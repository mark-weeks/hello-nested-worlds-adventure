# Enfolded: Nested World Adventure

Both browser clients offer **Speak | Puzzle | Act** in one shared world. Act has
four actions at each of eleven scales, optional ordered combinations, and an
intention entry. A clear submission commits an attempt; consequences emerge from
the conditions when it settles. There is no consequence preview or compulsory
scripted route. Accepted retries recover the original receipt.

`/journal` holds private notes, a home bookmark, return recaps, and a selectively
published profile. Invited participants can submit, support, and withdraw feedback
at `/ideas`. Personal invites and credential rotation preserve participant ownership.
Existing scripted situations and earlier accepted work remain readable/recoverable;
new scripted choices are retired and opening a situation is not beta onboarding.

See the [action contract](docs/decisions/ADR-028-scale-native-autonomy.md),
[current pilot protocol](docs/evaluation/2026-09-12-pilot-protocol.md), and
[beta readiness record](docs/evaluation/2026-10-03-beta-readiness.md).
Human pilot evidence, hosted recovery, and live-model quality remain launch gates.

**A shared persistent multiverse inhabited simultaneously by human players and AI agents.**

*The title "Enfolded" derives from David Bohm's [implicate order](https://en.wikipedia.org/wiki/Implicate_and_explicate_order) — the idea that every part of the universe enfolds the whole, and what we perceive as separate objects are unfolded projections of a deeper connected reality. This game is a playable version of that idea.*

[enfolded.world](https://enfolded.world) — the launch target. The hosted world is not yet deployed.

---

## Concept

Enfolded is an environment where the boundary between player, agent, and world is deliberately blurred.

The multiverse is always running. You enter and find it already in motion — other humans and AI agents traversing different scales, each leaving traces the world carries forward. You may never encounter another player directly, but you will feel the consequences of their presence through cross-scale causality: a destabilized atom cascading into a volatile region, a solved puzzle stabilizing a galaxy, an agent's curiosity reshaping a planet's danger over time.

Every node in the hierarchy is a perspective, not just a data structure. The Vault speaks from its history. The Mire remembers who passed through. Nodes are animated by Claude and respond in character — their voice seeded by accumulated properties and interaction history. Talking to a node is a way of learning what it *is*. Whether you're speaking to a world node or an AI agent who has settled into one is a question the system leaves deliberately open.

Interaction is multi-modal: natural language for depth, visual navigation for movement, ambient observation for those who want to watch the world evolve without directing it. The visual layer is a piece of generative art that responds to world state — causal events visible as ripples, other presences as signatures in the field.

---

## Where things stand

*Verified against `main` at #108, 2026-10-03.* Nothing is deployed and the
chronicle is empty; two QA prereleases (`v0.1.1-qa.1`, `v0.1.1-qa.2`) were cut
on 2026-08-31 for local QA. Everything in the matrix below is merged on `main`,
not deployed. The [roadmap index](docs/roadmap/README.md) says which plans and
decisions govern now; the [2026-10-03 assessment](docs/evaluation/2026-10-03-ambition-and-boundaries.md)
puts a decision agenda to the owner, with [ADR-029](docs/decisions/ADR-029-evolution-grammar.md)
through [ADR-033](docs/decisions/ADR-033-scale-registry.md) drafted as Proposed,
not ratified. The [discovery-and-return plan](docs/roadmap/discovery-and-return.md)
still carries the open product milestones: the M7 pilot cohort and M8. The
[beta readiness record](docs/evaluation/2026-10-03-beta-readiness.md) (#109)
separates completed local work from the hosted and human gates that remain.
---

## Next milestone: observed play and return

The next step is a small invited study of curiosity, comprehensible consequences,
and a meaningful return to the same world. The journal/profile and action systems
are implemented; their value to new players is not established by automated tests.
Rankings, optional spoken input/playback, crafting, guilds, Hyperleap, and expanded
agent cognition remain outside this beta-readiness batch. The
[delivery plan](docs/roadmap/discovery-and-return.md) retains their separate decisions.

---

## Architecture

### The Hierarchy

Eleven nested scales, each with its own aesthetic register and causal weight:

```
Multiverse → Universe → Galaxy → Planetary System → Planet → Region → Room → Object → Molecule → Atom → SubatomicParticle
```

### Core Systems

**World Model** (`multiverse/`)
The persistent spatial hierarchy. Nodes carry level-specific properties, accumulated interaction history, and causal state. The generator births a world once per seed; from then on the stored row is the node's identity (ADR-006) and everything after that is live: chronicled deltas, the wrap passage, scale-native actions, the first authored situation.

**Node Consciousness** (`consciousness/`)
The Claude-powered voice layer. Each node has a persona derived from its properties and history. Nodes respond in character to direct interaction, reference past visitors, and hold perspective on their place in the hierarchy. The same layer interprets a player's typed intention into bounded steps and never predicts outcomes. The line between animated world and inhabiting agent is intentionally porous.

**Causality Engine** (`causality/`)
A propagation system that carries effects up and down the hierarchy with dampening and delay. Actions register as causal events; the engine resolves their consequences across scales over time, through durable queues whose accepted work survives interrupted delivery. Players and agents shape each other's experiences without necessarily meeting.

**Agents** (`agents/`)
A named cast of twelve deterministic FSM travelers with distinct personas, goals, and relationships to specific nodes and scales — Claude-adjacent rather than Claude-driven: their traversal and in-character banter run at zero API spend, and they are voiced by Claude only when addressed directly (`/agent/voice`). Agents traverse the world, interact with nodes and each other, accumulate memory, keep one recorded commitment, and can be engaged in conversation. Some destabilize; some tend. Their behavior is driven by goals and shaped by world state.

**Persistence** (`persistence/`)
World state lives in a database. The multiverse exists between sessions. Interaction history, causal state, agent memory, participant ownership, stored puzzle content, delivery queues and community ideas persist across 27 additive migrations. Multiple participants can be present simultaneously.

**Server** (`server/`)
Real-time API layer. WebSocket-based synchronization for multi-participant presence and player chat, broadcasting causal events to all connected clients. REST endpoints for world state, observation, puzzles, node speech, scale-native actions, the journal, the situation and the Ideas board. Serves the map explorer at `/` and the bundled scene client at `/app`.

**Interface** (`interface/`)
The terminal interaction layer. Spatial navigation, conversational `speak`, ambient observation, and embedded puzzles in a single REPL.

**Frontend** (`frontend/`, `static/`)
Browser clients. `frontend/` is a React + PixiJS + Vite app for scene rendering, hotspot interaction, the Act surface and live multiplayer presence, built into `static/app/` and served at `/app`. The vanilla D3 map explorer (`static/index.html` + `static/explorer.js`) is served at `/` directly by the Python server. Both consume the same shared static modules for navigation, senses, score and receipts. AI-generated scene backgrounds are an optional wash produced via fal.ai (`fal-ai/fast-sdxl`) and cached in persistence.

**Puzzles** (`puzzles/`)
Embedded challenges that interact with the causal system. Solving a puzzle isn't just a local event — its resolution propagates. Puzzles are voiced by their containing nodes, mostly ask the player to read the world, and keep the question a node first served until it is renewed.

The [architecture overview](docs/architecture/overview.md) names every module.

---

## Interaction Modes

| Mode | Description |
|------|-------------|
| Conversational | Natural language exchange with nodes and agents |
| Spatial | Visual navigation through the hierarchy |
| Causal | Observing and triggering cross-scale effects |
| Active | Committing a scale-native action, then discovering what it set in motion |
| Ambient | Passive presence — watching the world evolve |

---

## What Makes This Different

Most games separate human players from AI. Most simulations exclude humans or treat them as inputs. Most interactive fiction is single-player and deterministic.

This is a **shared consciousness space** — always inhabited, always causal, where the distinction between player, agent, and world is part of the experience rather than a technical boundary to manage.

Human-to-human, human-to-agent, agent-to-human, agent-to-agent: all four interaction patterns occur naturally within the same environment, governed by the same world model and causal rules.

---

## Current State

*Matrix last verified against code: 2026-10-03 (`main` at #108). Merged, not deployed.*

| System | Status |
|--------|--------|
| World model (`multiverse/`) | Functional — named locations, variable branching, rich per-level properties across 11 scales. **One shared canonical launch world (ADR-007):** the hosted server serves curated seed 382 to every human and agent; arbitrary client seeds are rejected before they can birth a parallel persistent history. At birth every node is a pure function of (seed, path), then its stored row is authoritative; a depth-6 view is exactly the top of the same depth-11 materialized world. **Every node identity is readable and unique:** generator v2 assigns a collision-free three-word semantic name plus its path suffix, every node has a synthesized `aspect`, and property fingerprints do not repeat across the 4,208-node launch world (guarded by tests and the executable launch census). Causal events durably change node substance via `multiverse/effects.py`, persisted as a property overlay and chronicled as deltas. **The hierarchy closes into a traversal-layer loop (ADR-008):** descending below any SubatomicParticle surfaces at the Multiverse root; ascending beyond the root lands at the world's one hinge particle — selected once by a seed-pure rule constrained to a fully unsealed lineage, pinned write-once in `world_meta`, and never re-selected by code. Containment stays a tree; causality does not wrap. A world that changes *shape* (renames, reparenting, births) is the Proposed ADR-029, not shipped |
| Agent traversal (`agents/`) | Functional — a named roster of twelve (`agents/roster.py`: *Tessera, Halden, Mirrorbird…*) over four persona archetypes (*tender · destabilizer · scholar · wanderer*), FSM traversal, self-preservation, interaction logging, causal event emission, persistent memory across runs (keyed by node NAME; the visit budget counts fresh ground), agent-to-agent encounters whose banter rotates deterministically before it repeats (`agents/banter.py`). **Agents obey the puzzle rules**: they attempt the node's actual engine puzzle at its current epoch with difficulty-weighted odds and can fail — no free solves, and an agent solve never counts as human progress. **M4 attention (ADR-022):** known places are separated from relevant revisits, work per heartbeat tick is bounded, and useful memory is retained, so inhabitants stay responsive after exploration saturates. One inhabitant keeps a recorded commitment in the first situation. Danger alerts propagate upward with dampening |
| Puzzle engine (`puzzles/`) | Functional — node-voiced generators for all 11 levels (`puzzles/generators.py`) combine transforms with **world-reading mechanics**: contextual seals, lineage/bond/enfold puzzles, Keeper Witnesses that make readable ancestor names into landmarks, and Ancestral Compasses assembled from two enclosing scales. Ancestor names intentionally remain visible for orientation: gentle Keepers ask for one landmark, while 3–4★ Keepers compose a new answer from two or three named scales instead of presenting copyable answer text. Traversal is non-linear (drop in anywhere, move up or down), so **difficulty is a per-node property spread across the full 1–4 range at every scale — not a depth curve**. **The Causal Augury (ADR-010) teaches the world's dynamics**: 396 hash-elected nodes (9.41%, stable across renewal epochs) at Region and deeper serve prediction puzzles whose answers are the causal engine's own forecast (`causality/forecast.py`, pinned equivalent to the live bus) — count a rising cry's reach, name the scale where it dies, find where Fractal skies ring undimmed — with hints that teach each law's temperament in fiction. The executable ecology gate (`scripts/puzzle_quality.py`) prevents the generic decode families from retaking the world: in seed 382 decode families are 33.75%, world-reading families are 65.59%, no family exceeds 19.94%, prompts are 99.90% unique, and answers 54.06% unique. Puzzles carry graduated hints and server-side answers that never appear in their prompt, hints, or current node properties. **First-use content is durable (ADR-024):** the definition and original observational evidence a node first serves are stored, `/puzzle` carries an `epoch`, `/puzzle/evidence` shows the pinned evidence, and an answer to a superseded question is refused (409) without consuming an attempt. Identity remains deterministic across full-tree and direct stored-node resolution, so co-op and renewal epochs agree. Static pools remain a fallback for unknown levels. |
| Causality engine (`causality/`) | Functional — bidirectional event propagation (up + down) from any origin with configurable per-hop dampening under each Universe's law profile (`causality/laws.py`); events broadcast to all WebSocket clients carrying their REAL propagated strength (hop distance included, ancestors measured truthfully); persisted `ripple_score` accumulates atomically (concurrent participants compound, not overwrite); strong events change node properties via `multiverse/effects.py` and the change survives rebuilds (`causality/wiring.py` is the one standard wiring every surface uses). **Consequences travel at world speed** (`causality/staging.py`): only the origin's immediate ring fires inside the triggering request — farther rings are staged in a durable queue (`causal_queue`) and drained by a pump thread, one ring per hop delay (default 12s, `NESTED_WORLDS_HOP_DELAY`), each arrival broadcast live as it lands. **Accepted work survives interrupted delivery (M1, ADR-019):** claim and application are fenced atomically (`causality/delivery.py`); process death, duplicate delivery, concurrent workers and restart recovery are tested, and every queue is inspectable with `python main.py work-report`. **Delayed choices compose (M2, ADR-020):** contribution, shared one-time and explicit no-op policies with saturation made explicit; `multiverse/delayed_v2.py` is the frozen interpreter for accepted work |
| Persistence (`persistence/`) | Functional — SQLite store (WAL, 27 additive migrations) for world identity, agent runs, puzzle results and stored first-use puzzle content, agent memory, node interaction history, world mutations, chronicled deltas, staged causal hops and the other delivery queues, participant ownership with journal notes/profile/home (ADR-024), request-ID receipts, the first situation (ADR-025), community ideas and promotions (ADR-026), expressive interventions (migration 0027), cost budgets, and the scene-image cache. **The database is a continuous chronicle, not per-cohort scratch**: each new player (human or agent) builds on the traces of everyone before them — migrations are additive-only and the DB is never wiped between cohorts (policy in `docs/roadmap/phase-2-scale.md`). **State at any recorded moment is reconstructible (ADR-009/011):** born properties plus version-ordered stored deltas, with causal pressure and interaction wear folded through the same exact node-local cursor; effects code is never replayed. The chronicle is append-only: redaction (`python main.py redact`), double-gated pruning and disaster restore (`python main.py restore`) are the only sanctioned maintenance paths |
| Server (`server/`) | Functional — REST (`/health` `/worlds` `/world` `/node` `/agent` `/observe` `/puzzle` `/puzzle/evidence` `/players` `/history` `/chronicle` `/wayback` `/image` `/speak` `/puzzle/attempt` `/act` `/agent/voice` `/position` `/client-error`, plus the sub-APIs `/interventions` `/interventions/commit`, `/me` `/profile` `/profile/save` `/profile/home` `/journal/data` `/journal/note`, `/situation` `/situation/discover` `/situation/choose` `/situation/follow-up`, and `/ideas/{list,detail,search,submit,vote,withdraw}`), pages at `/` `/app` `/guide` `/register` `/journal` `/ideas`, WebSocket multiplayer at `/ws`, co-op puzzle sessions, security headers + CSP, body/frame size caps. **Canonical-world boundary:** `NESTED_WORLDS_CANONICAL_SEED` governs every HTTP, SSE, WebSocket, position, and heartbeat path; missing seed selects it, a mismatch is rejected before lookup/birth, and stale alternate-world positions cannot redirect a player. **Node identity is server-derived**: `/speak`, `/image`, `/agent/voice`, `/wayback`, `/node` and every write route resolve the named node against that world (404 for forged names). **Authenticated acts carry retry IDs:** a replay returns the original committed receipt and a changed intent under the same ID is refused (ADR-024/028). WebSockets retain strict RFC 6455 framing and non-blocking per-player writer queues; agents remain addressable through persisted memory and node-scoped history |
| World heartbeat (`server/heartbeat.py`) | Functional — the canonical world runs unattended: a daemon loop (default every 180s, `NESTED_WORLDS_HEARTBEAT*` env) sends the roster on paced traversals that persist history/ripple/effects and broadcast live to the shared room, bounded by M4 attention, and a pump thread drains the four durable queues (staged causal hops, matured cosmic verbs, situation consequences, expressive work). It cannot fall back to an old alternate seed when the hosted boundary is active. FSM-driven — zero API spend |
| Discovery and return (`persistence/participants.py`, `persistence/situations.py`, `multiverse/situation.py`) | Functional in bounded form (ADR-024/025, #100–#101) — an operator opens the one authored situation with `python main.py situation --seed 382`; new arrivals reach its entry in either client, read clues at eight existing places across four scales, take a preserve/release choice with a shared settlement window, and investigate the delayed aftermath. Participants own private notes, a published bio/goals/preset avatar and a home bookmark (`/journal`) separately from credentials, so `python main.py invite rotate` replaces a key without losing them. Notes never enter prompts. The pilot protocol and `scripts/pilot_report.py` keep research measurement outside world canon. **Human pilot evidence (M7) is still pending** |
| Community Ideas (`persistence/ideas.py`, `server/ideas_api.py`, `server/idea_promotion.py`) | Functional (ADR-026, #102–#104) — invited players open `/ideas` from either client to submit, search and support ideas without a GitHub account; one support vote per member with undo; drafts survive failures; operators moderate (`python main.py ideas …`) and publish reviewed briefs to GitHub explicitly, with read-only recovery of an interrupted publication. No world, puzzle, chronicle or agent writes. Not deployed |
| CLI (`main.py`) | Functional — `world`, `agent`, `puzzles`, `play`, `serve`, `speak`, `history`, `backup`, `restore`, `redact`, read-only `work-report` (all delayed-work queues), `situation` (installs the authored situation once), `invite {mint,list,revoke,rotate,create,tokens,cancel}` and `ideas {list,show,decide,prepare,preview,publish,reconcile,record-link}`; `--seed` remains accepted for operator curation, deterministic evaluation, and isolated local development. To act in the hosted world's history, operators use its configured canonical seed. Player-facing browser clients cannot choose or create worlds |
| Node consciousness (`consciousness/`) | Functional — Claude-powered node voices with per-scale registers (`LEVEL_VOICES`) AND deep per-scale lore (`LEVEL_LORE`: diction, how each scale senses its neighbors, pressure behavior, exemplar exchanges) for all 11 levels. Memory has content: nodes hear what you said and remember what they answered, per-(node, speaker) transcripts make conversations multi-turn (keyed on the invite credential, so same-name strangers stay strangers), and accumulated causal pressure colors the voice. A fourth call site (`consciousness/interventions.py`) interprets a typed intention into enum-bounded steps and never predicts outcomes. **Prompt caching genuinely fires**: both bibles exceed the real 4096-token minimum (guarded by tests), so after the first call in a 1h window the prefix bills at the cache-read discount. Without a key the world degrades in character: every scale has an authored fallback line and the intention path answers an authored quiet reply — never an HTTP 503 or SDK error. The default voice model is `claude-opus-4-8`; the 2026-10-03 assessment recommends moving it (decision open) |
| Interface (`interface/`) | Functional — interactive terminal session (spatial, conversational, ambient) with the original scale-native verbs |
| Frontend (`frontend/`, `static/`) | Functional — React + PixiJS + Vite scene client (`/app`) and vanilla-D3 map explorer (`/`) wired to the same server-owned world; neither exposes seed/world creation. **Since #107 both clients share one navigation vocabulary** (`static/interface.js`, `static/navigation.js`): named enclosing/within/wrap passages, an eight-place temporary return trail, one identity block (scale, name, position, evolving description), and Speak \| Puzzle \| Act directly below it, with secondary detail through disclosure and interface styling derived from each place's material, atmosphere, terrain, geometry and retained traces. **Act (ADR-027/028):** four scale-native actions at each of eleven scales (44 real property transitions), optional ordered combinations and a typed intention; the attempt commits directly and the world's response is discovered as it settles (`static/interventions.js`, `static/intents.js` receipts that survive lost replies and reloads). **Replay History (ADR-011; "Wayback" on the map view)** scrubs or animates any node from birth through its recorded event steps, rendered by today's deterministic senses — historical state through present senses, explicitly not period playback; the archive creates no trace and never classifies one as human or agent. **Senses:** the state-driven scene (`static/sensory.js`) and eleven sampled musical forms (`static/score.js`, CC0 VSCO 2 CE recordings) are shared by both clients and directed by each node's served senses; `static/nodeart.js` is the explorer's fallback renderer; four curated plates ship locally for the first situation's places (`docs/media/expressive-world.md`). In `/app` sound is the intended default once the browser has its activation gesture (an explicit mute persists); fal.ai imagery is an optional enhancement wash; WebGL failure degrades to a navigable text scene |
| Beta hardening (`server/guard.py`, `server/observability.py`) | Functional — per-user invite keys are the whole invite gate (`invite_keys` table; mint/list/revoke/rotate via `python main.py invite ...`; no shared key, so every gated session is a known, unique, named player — ADR-004 §7), **invite-gated self-service registration** (`invite create` mints a single-use token; the player picks their own unique name at `/register` and redemption atomically mints their play key — name taken → "choose another", token survives for the retry; `invite cancel` revokes a leaked link), **input moderation** (ADR-004 §2: fail-open two-tier screen on `/speak`, `/agent/voice`, WS chat, registered names and published profile text — a µs-scale local filter blocks only unambiguous slurs and escalates anything fuzzy to one uncached Haiku-tier classify on its own daily budget; declined input gets an authored in-fiction line and leaves no chronicle row, no broadcast, no voice-budget charge; `NESTED_WORLDS_DISABLE_MODERATION=1` kill switch), per-IP rate limiters for writes and reads plus an Ideas credential-failure limiter, Anthropic concurrency semaphore (env-tunable), daily Anthropic + fal.ai cost caps — both a global cap and a per-user (per-credential) sub-cap so one account can't drain the shared budget (all persisted), kill switches for AI / images, world-gen parameter bounds, optional Sentry, JSON access log, online SQLite backup CLI |
| Frontends: which is which | Two browser clients on one world. `/` (the map explorer) and `/app` (the scene client) are **both** feature-complete for the core loop — navigate, speak to nodes, solve puzzles, act, live multiplayer. Ambient observe (`/observe` SSE) is explorer-only. Invite URLs still land on `/` (ADR-005: no WebGL dependency, works first-click on any device) and the guide names `/app` as the scene view to try once oriented — the same world and key carry over via localStorage. Since the ADR-005 revision of 2026-09-12, `/app` is the primary development surface (the first situation, journal and Act landed there first); a public switch waits on the device/accessibility/onboarding gate, and decision D7 of the 2026-10-03 assessment proposes retiring the explorer after it. |
| Non-linear entry (both clients) | Traversal is non-linear, so there is no fixed root start. A first-time player drops into the middle of the shared world (the situation's curated entry when one is installed); a returning player resumes their last canonical-world node across devices via their invite-key position. `localStorage` remains a same-browser cache; a stale node that does not exist in the hosted world falls back to a fresh drop-in. A deep link selects its arrival once; later reloads resume actual travel. Entry, passage-badge, and chronicle-rendering rules are canonical in `static/clientlogic.js` and consumed by both clients |
| Tests | 1,358 Python tests across generator and stored-world continuity, agents, puzzle quality/ecology, effects and staged causality, delivery recovery, delayed choices, history narration, persistence, chronicled deltas, state-at-T/Wayback, the wrap passage, consciousness, heartbeat and M4 attention, HTTP/WebSocket conformance, canonical-world boundaries, node resolution, participants and the first situation, Ideas and promotion, expressive interventions and commit/discover, beta guards, deployment contracts, frontend↔endpoint contracts, and observability — plus 131 Vitest tests for canonical entry/resume/affordance/chronicle/wrap/Wayback/display-name behavior, WebSocket dispatch, the Act surface and receipts, and deterministic senses and score. CI also builds the production frontend, rejects a stale committed bundle, smoke-tests the installed wheel, and runs 96 Playwright cases against the real server under the production CSP (`ENFOLDED_E2E=1`). Counts are from the #107 gate run recorded in the CHANGELOG. |

---

## Help shape Enfolded

Enfolded is being built in the open. Play together, share discoveries, help a
newcomer, report a problem, or tell us what made you curious, confused, or want
to return. You do not need to write code to contribute.

[Share playtesting feedback or an idea](https://github.com/mark-weeks/hello-nested-worlds-adventure/issues/new?template=playtesting.yml),
[report a bug](https://github.com/mark-weeks/hello-nested-worlds-adventure/issues/new?template=bug_report.yml),
or read the [contribution guide](CONTRIBUTING.md). Invited players can use the
in-game Ideas board at `/ideas` for submissions, support,
withdrawal, and maintainer decisions. GitHub remains an external reporting route.
A reviewed idea or vote does not itself publish an issue or authorize implementation.

Maintainers use feedback to guide priorities, explain decisions, and invite
players to verify improvements. Coding agents support implementation; outside
PRs are welcome for work agreed with a maintainer in advance. Discuss the
problem and scope before investing in a patch.

## Setup

```bash
# Use the pinned runtimes, then install the locked Python and Node dependencies
nvm use
./setup.sh
source .venv/bin/activate

# Copy the environment template and fill in keys you need
cp .env.example .env
```

Environment variables (see `.env.example`):

| Variable | Required for | Default |
|----------|--------------|---------|
| `ANTHROPIC_API_KEY` | Node consciousness (`speak`, browser chat with nodes) and typed-intention interpretation in Act | — |
| `NESTED_WORLDS_CANONICAL_SEED` | The one shared world the hosted server serves (ADR-007); every HTTP, SSE, WebSocket, position and heartbeat path is bound to it. Set it empty, `off` or `none` only for explicit local multi-world curation. | `382` |
| `NESTED_WORLDS_MODEL` | Override the Claude model | `claude-opus-4-8` |
| `FAL_KEY` | AI-generated scene backgrounds (`fal-ai/fast-sdxl`) | optional |
| Invite gate (no env var) | Hosted beta: the gate is the per-user `invite_keys` table, not an env var — there is no shared key. Mint keys with `python main.py invite mint --name <player>`, or create a single-use self-service invite with `invite create` (the player picks their own unique name at `/register?invite=<token>`). Minting the first key closes the gate so every HTTP and WebSocket request needs a valid `?key=...` or `X-Beta-Key`, and every gated session is a known, unique, named player. Keys and registration tokens are stored hashed at rest (sha256): the plaintext credential appears once at mint/registration and cannot be recovered later — revoke and re-mint if lost (`invite list` / `invite tokens` show an 8-char hash prefix). Mint no keys for local dev. | open until first mint |
| `NESTED_WORLDS_ANTHROPIC_DAILY_CALLS` | Hosted beta: global cap on Anthropic calls per UTC day; once exceeded, `/speak` and `/agent/voice` return a fallback string instead of calling the API. | `500` |
| `NESTED_WORLDS_ANTHROPIC_DAILY_CALLS_PER_USER` | Hosted beta: per-credential daily Anthropic cap, so no single tester can consume the whole global budget and degrade the cohort. Enforced only when a request carries an invite credential. | `150` |
| `NESTED_WORLDS_FAL_DAILY_CALLS_PER_USER` | Hosted beta: per-credential daily fal.ai image cap. | `60` |
| `NESTED_WORLDS_ANTHROPIC_CONCURRENCY` | Hosted beta: max in-flight Anthropic calls per process. Bounds instantaneous concurrency so a synchronized burst can't trip the org-level RPM. | `8` |
| `NESTED_WORLDS_FAL_DAILY_CALLS` | Hosted beta: cap fal.ai image calls per UTC day. | `200` |
| `NESTED_WORLDS_HEARTBEAT` | Set to `0` to disable the ambient world heartbeat (background agent life). | on |
| `NESTED_WORLDS_HEARTBEAT_INTERVAL` | Seconds between heartbeat ticks. Heartbeat agents are FSM-driven — no API spend. | `180` |
| `NESTED_WORLDS_HOP_DELAY` | Seconds a staged causal cascade waits between rings — how fast consequences travel across scales. `0` makes staged hops due immediately (they still run through the queue). | `12` |
| `NESTED_WORLDS_CAUSAL_PUMP` | Set to `0` to disable the pump thread that drains staged causal hops, matured verbs, situation consequences and expressive work (accepted work waits durably until a compatible pump runs again). | on |
| `NESTED_WORLDS_MATURATION_SCALE` | Multiplier on the cosmic-scale verb maturation clocks (Multiverse 1800s, Universe 900s, Galaxy 300s, Planetary System 120s). For tests and impatient operators; `0` makes every verb instant. | unset (×1) |
| `NESTED_WORLDS_RATE_LIMIT_PER_MIN` | Hosted beta: per-IP requests/minute on the write routes — `/speak`, `/agent/voice`, `/image`, `/puzzle/attempt`, `/act`, `/interventions/commit`, `/journal/note`, `/profile/save`, `/profile/home`, `/situation/{discover,choose,follow-up}`, `/register`, `/client-error`. | `20` |
| `NESTED_WORLDS_RATE_LIMIT_GET_PER_MIN` | Hosted beta: per-IP API reads/minute, including `/puzzle/evidence` and future data routes by default. Static assets, `/health`, `/worlds`, `/players`, `/position`, and the separately guarded `/ws` upgrade are exempt. | `120` |
| `NESTED_WORLDS_IDEAS_AUTH_FAILURES_PER_MIN` | Hosted beta: failed Ideas credential checks per 60-second window/IP. Excess failures return `429`; valid credentials remain usable. Process-local; authentication still runs first. See [Ideas limits](docs/development/community-ideas.md#review-corrections-and-operational-boundaries). | `120` |
| `NESTED_WORLDS_MAX_WS_CONNECTIONS` | Hosted beta: max concurrent WebSocket connections process-wide. Excess upgrades get `503`. | `128` |
| `NESTED_WORLDS_MAX_WS_PER_IP` | Hosted beta: max concurrent WebSocket connections per client IP. | `8` |
| `NESTED_WORLDS_DISABLE_AI` | Set to `1` to disable `/speak` and `/agent/voice` without a redeploy. | unset |
| `NESTED_WORLDS_DISABLE_IMAGES` | Set to `1` to disable `/image` without a redeploy. | unset |
| `NESTED_WORLDS_DISABLE_MODERATION` | Set to `1` to turn off the input-moderation screen without a redeploy (ADR-004 §2). | unset |
| `NESTED_WORLDS_MODERATION_MODEL` | Model for the moderation classify call (ambiguous inputs only; clean input costs zero API calls). | `claude-haiku-4-5` |
| `NESTED_WORLDS_MODERATION_DAILY_CALLS` | Daily cap on classify calls — moderation's own budget line; when exhausted the screen fails open, never blocking chat. | `2000` |
| `NESTED_WORLDS_MODERATION_BLOCK_EXTRA` / `..._WATCH_EXTRA` | Comma-separated hot extensions to the block / watch term lists — react to live abuse without a redeploy. | unset |
| `NESTED_WORLDS_TRUST_PROXY` | Set to `1` only when running behind a trusted reverse proxy. The rate limiter then reads the real client IP from a proxy-set header (never the spoofable left-most `X-Forwarded-For`). | unset |
| `NESTED_WORLDS_CLIENT_IP_HEADER` | Trusted client-IP header consulted when `TRUST_PROXY=1`. Falls back to the right-most `X-Forwarded-For` entry. | `Fly-Client-IP` |
| `NESTED_WORLDS_MUTATION_TTL_DAYS` | Days of `world_mutations` retention. **Continuity-violating** — the mutation log is the world's permanent chronicle and feeds the generative art, so this is ignored (with a warning) unless `NESTED_WORLDS_ALLOW_HISTORY_PRUNE=1` is also set. | unset |
| `NESTED_WORLDS_ALLOW_HISTORY_PRUNE` | Explicit confirmation flag for the above. Do not set it casually. | unset |
| `SENTRY_DSN` | Optional. `sentry-sdk` ships as a default dependency; set the DSN to forward unhandled handler exceptions to Sentry. | unset |
| `SENTRY_ENVIRONMENT` | Tag for the Sentry environment field. | `production` |
| `ENFOLDED_GITHUB_TOKEN` | Operator-only: lets `python main.py ideas publish` open a GitHub issue from a reviewed Ideas brief. Never set it on the server; see the [Ideas operator guide](docs/development/community-ideas.md#explicit-github-promotion). | unset |

The browser frontend (`frontend/`) is a separate Vite project:

```bash
cd frontend
npm run dev    # dev server with hot reload
npm run build  # production bundle
```

## Running Locally

```bash
# Generate and explore the world hierarchy
python main.py world

# Run an agent traversal
python main.py agent --name Scout --danger-threshold 4

# Find and play puzzles (first 10 by default; 'skip' passes, Ctrl-D stops)
python main.py puzzles --limit 5

# Start an interactive session (spatial navigation + conversation + ambient)
python main.py play --name Ada    # give a name and the nodes remember you

# Start the REST API server (http://127.0.0.1:8080)
python main.py serve

# Speak to a node using Claude
python main.py speak --node "Vault-3" --message "What secrets do you hold?"

# View saved worlds and agent run history
python main.py history

# Inspect due work, failures, and predecessor waits without changing the DB
python main.py work-report --seed 382
python main.py work-report --db /backups/worlds.db --seed 382 --json

# Snapshot the SQLite store (safe while the server is running)
python main.py backup --to /backups/worlds-$(date +%Y%m%d).db

# Manage per-user beta invite keys (rotate keeps the participant's notes and profile)
python main.py invite mint --name Alice --note "design partner"
python main.py invite create            # single-use self-service registration link
python main.py invite list
python main.py invite rotate nw_...
python main.py invite revoke nw_...

# Open the one authored situation in a world (once; never automatic — use a disposable DB locally)
python main.py situation --seed 382

# Moderate and publish community ideas (see docs/development/community-ideas.md)
python main.py ideas list

# Restore from a backup or redact abusive content — the runbook's §7 is the procedure
# python main.py restore ...   python main.py redact ...

# Operator/dev commands accept --seed INT; the hosted clients do not
python main.py world --seed 7 --depth 6

# Audit the unborn launch world's visible variety and puzzle ecology
python scripts/world_quality.py --seed 382
python scripts/puzzle_quality.py --seed 382
```

The four design-partner captures are reproducible from an isolated temporary
database after Playwright Chromium and `ffmpeg` are installed:

```bash
cd frontend
npm run capture:pitch
```

For an isolated local review world with the four curated places, the sampled
score and the Act surface, run `.venv/bin/python scripts/preview_expressive_world.py`
(the printed link includes a disposable local invite; `--resume /path/to/preview.db`
keeps a saved review world). No model key is needed for labeled actions, images
or score. `node scripts/render_score_audition.mjs http://127.0.0.1:8201 /tmp/enfolded-audition`
writes eleven listening excerpts with concealed scale labels. Walkthrough and
acceptance evidence: [expressive world](docs/evaluation/2026-09-20-expressive-world.md),
[commit/discover](docs/evaluation/2026-09-20-commit-discover.md),
[UX and visual language](docs/evaluation/2026-09-21-ux-visual-language.md);
media provenance in [docs/media/expressive-world.md](docs/media/expressive-world.md).
None of this touches the production world or the invite destination.

## Running Tests

Start with [CONTRIBUTING.md](CONTRIBUTING.md) for the contribution process.
For coding agents, [AGENTS.md](AGENTS.md) routes to the shared engineering
contract and relevant procedures.

```bash
./scripts/check.sh

# Include the real-browser smoke tests after Playwright Chromium is installed
ENFOLDED_E2E=1 ./scripts/check.sh
```

---

## License

Enfolded's own code and documentation are licensed under the
[Apache License 2.0](LICENSE). Third-party components retain their original
terms; see [NOTICE](NOTICE) and [third-party notices](THIRD_PARTY_NOTICES.txt).
The [licensing decision](docs/decisions/ADR-023-community-and-licensing.md)
records the adoption and the earlier README's MIT label without claiming to
revoke previously granted rights.

## Author

**Mark Weeks** — [markweeks.dev](https://markweeks.dev) · [multilogue.io](https://multilogue.io) · [enfolded.world](https://enfolded.world)
