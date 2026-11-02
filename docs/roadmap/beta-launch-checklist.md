# Enfolded Beta Launch Checklist

*Living checklist carried by the [roadmap index](README.md). Statuses below
are as of 2026-11-01, `main` at `38fbe6e`. Thresholds marked as proposals are
not decided. Decisions held for the owner are listed in this page and are not
made by recording it. It ratifies no ADR and authorizes no deployment.*

**Status as of 2026-11-01, main at 38fbe6e**

> Living document. Statuses are derived from reading the repo and are updated by PRs; thresholds marked as proposals are not yet decided.

What must be true before 8 to 12 invited people play Enfolded. Each item has a testable exit criterion and a status grounded in the repo at main `38fbe6e`, as of Nov 1, 2026 (PT).

## Contents

- [At a glance](#at-a-glance)
- [Mark's seven criteria](#marks-seven-criteria)
- [First session and onboarding](#first-session-and-onboarding)
- [Retention and return](#retention-and-return)
- [Content depth and variety](#content-depth-and-variety)
- [AI players and agent policy](#ai-players-and-agent-policy)
- [Safety and moderation](#safety-and-moderation)
- [Economy, budgets and cost](#economy-budgets-and-cost)
- [Performance and reliability](#performance-and-reliability)
- [Observability and feedback](#observability-and-feedback)
- [Model agnosticism](#model-agnosticism)
- [Accessibility](#accessibility)
- [Legal and policy](#legal-and-policy)
- [Deployment and ops](#deployment-and-ops)
- [Community and beta cohort](#community-and-beta-cohort)
- [Community governance and self-policing](#community-governance-and-self-policing)
- [Distinctiveness: why players return](#distinctiveness-why-players-return)
- [Mark's held decisions](#marks-held-decisions)
- [Go/no-go gate](#gono-go-gate)
- [Open questions for Mark](#open-questions-for-mark)
- [Glossary](#glossary)
- [How this was verified](#how-this-was-verified)

## At a glance

95 items in 16 categories. 54 block beta, and 42 of them are still open.

| Status | Count |
|---|---|
| Done | 13 |
| Partial | 32 |
| Not started | 43 |
| Unknown | 7 |

### By category

| Category | Items | Done | Partial | Not started | Unknown |
|---|---|---|---|---|---|
| Mark's seven criteria | 9 | 0 | 5 | 4 | 0 |
| First session and onboarding | 4 | 0 | 3 | 1 | 0 |
| Retention and return | 5 | 1 | 2 | 1 | 1 |
| Content depth and variety | 5 | 2 | 2 | 1 | 0 |
| AI players and agent policy | 4 | 0 | 2 | 1 | 1 |
| Safety and moderation | 5 | 1 | 2 | 2 | 0 |
| Economy, budgets and cost | 5 | 2 | 0 | 3 | 0 |
| Performance and reliability | 7 | 1 | 2 | 3 | 1 |
| Observability and feedback | 5 | 2 | 2 | 1 | 0 |
| Model agnosticism | 6 | 1 | 2 | 3 | 0 |
| Accessibility | 6 | 2 | 2 | 1 | 1 |
| Legal and policy | 5 | 1 | 1 | 1 | 2 |
| Deployment and ops | 6 | 0 | 2 | 4 | 0 |
| Community and beta cohort | 4 | 0 | 1 | 3 | 0 |
| Community governance and self-policing | 12 | 0 | 1 | 10 | 1 |
| Distinctiveness: why players return | 7 | 0 | 3 | 4 | 0 |

> **Biggest gaps:** The core loop is built and tested locally, but no one except Mark has played it. Blocking, reporting, alignment and tangible rewards don't exist yet, puzzle fun is unmeasured, and every hosted gate (Fly, backups, live models) waits on Mark's account and decisions.

**Legend.** *Gate*: **Blocks beta** or **Can follow** (nice-to-have for the first cohort); "Mark decides" marks a held decision. *Basis* of evidence: Code (read in the repo), Docs (ADRs, runbooks, records), Ran (script executed), Inference (proposal, not a repo fact).

## Mark's seven criteria

| ID | Item | Exit criterion | Status | Evidence | Gate |
|---|---|---|---|---|---|
| C1 | Node properties broad enough to feel like distinct personalities, histories, art and sound | `world_quality.py` gate holds on seed 382, and in a blinded test 10 testers tell two same-scale nodes apart by voice and scene at 80% or better. | Partial | (Ran) `multiverse/generator.py` has 5 to 7 properties per scale plus a composed aspect (about 420k combinations). Ran `world_quality.py`: PASS, 4,208 nodes, siblings 99.67% distinct. Felt personality is untested: no live model run. | **Blocks beta** |
| C2a | Puzzles are interesting and every solve gives visible feedback | Every solve shows at least one effect within 2 s (passage opens, node settles, solver credited). Whether puzzles are interesting is measured in C2c. | Partial | (Code) `puzzles/gates.py` unseals locked rooms world-wide. `multiverse/effects.py` PUZZLE_SOLVED stabilizes the node and calms its region. `server/rooms.py` PuzzleSession credits the solver and contributors. Interest has not been measured. | **Blocks beta** |
| C2c | Puzzle depth and fun measured in playtesting | In the pilot and cohort, every puzzle attempt is logged with solved or abandoned, time to solve and hints used, and testers rate each solve 'Was it interesting?' from 1 to 5. Proposed bar: solve rate between 40% and 85% for each family, median rating 3.5 or higher, and no family below 3. Players judge this, not the D2 ecology gate. | Not started | (Inference) Not measured. D2 checks variety and the world-reading share only. The 2026-09-07 evaluation ([docs/evaluation/2026-09-07-concept-and-implementation.md](../evaluation/2026-09-07-concept-and-implementation.md)) says the world-reading label counts reading and transforming properties but not investigative depth. Only 54% of answers are unique. Whether hint use is logged today was not checked. The bar is my proposal. | **Blocks beta** |
| C2b | Tangible rewards: points, player token budget, inventory items | A solve grants a reward the player can see and spend later, persisted per participant and covered by tests. | Not started | (Code) No points, inventory or collectible code found. ADR-017 (leaderboards) and ADR-018 (collectibles) are Proposed. | Can follow |
| C3 | Art and soundscape thematically tied to neighboring nodes | Nodes under the same Region or Planet share a tonal family and palette motif. Listeners group siblings versus strangers at 70% or better. | Partial | (Code) `multiverse/senses.py` derives `family` from the nearest Region or Planet ancestor, and `static/score.js` uses it for the root note. `server/imageprompt.py` has no ancestor or neighbor term, and fal.ai scene art is per node. | Can follow |
| C4 | Players experience other players' and agents' effects | A returning player's recap shows at least one change made by someone else, labeled human or agent. Player B's act is visible to player A live and after a reload. | Partial | (Code) Append-only chronicle, `participants.recap()`, Wayback, ripple propagation in `causality/`, heartbeat agents acting in `server/heartbeat.py`, and delayed v3 attempts. Implemented locally. No human has observed it yet. | **Blocks beta** |
| C5 | Actions dynamically adjust alignment scores | Every committed act maps to one or more documented axes. The player sees the change and the reason in the same session. The mapping is pinned by tests. | Not started | (Code) No alignment code: 'alignment' appears only as an orbital property in `interventions_v3.py`. ADR-014 proposes independent disposition meters, explicitly not an alignment axis, and ADR-017 rules out ranking by alignment extremity. | Can follow · Mark decides |
| C6 | Players communicate, collaborate and compete | Two testers can find each other, chat, co-solve a puzzle with shared credit, and pursue opposing goals in the first situation. | Partial | (Code) WebSocket `chat` in `server/websocket.py` is moderated, rate-limited, 256 chars, broadcast world-wide and persisted as PLAYER_CHAT. Puzzle co-op is pooled, and ADR-025 has opposing choices. No direct messages, groups or competitive standings. | **Blocks beta** |
| C7 | Players can disengage from or block other players | A player can mute or block someone from chat or presence. The block persists per participant, hides that player's chat and presence, and is covered by tests. A report goes to an operator queue. | Not started | (Code) No block, mute or report in `server/` or `frontend/src/components/TextPanel.jsx`. Chat reaches every connected player in the world. | **Blocks beta** |

**On puzzles:** world-reading means the answer comes from the node itself, from its own properties and its place in the hierarchy, not from a generic anagram, cipher or number pattern (the decode family). The seven world-reading families in `WORLD_READING_FAMILIES` (`puzzles/quality.py`) are sealed_lock, lineage, bond, enfold, keeper_witness, ancestral_compass and causal_augury. The D2 gate proves puzzles are tied to nodes, not that they are deep or fun, so C2c measures that with players.

## First session and onboarding

| ID | Item | Exit criterion | Status | Evidence | Gate |
|---|---|---|---|---|---|
| O1 | Time to first delight | In 2 to 3 observed newcomer sessions, curiosity appears within 5 min and the first understood consequence within 10 min. Protocol gate: 8 of 10 show curiosity. | Not started | (Docs) Protocol 2 ([2026-09-12-pilot-protocol.md](../evaluation/2026-09-12-pilot-protocol.md)) and `scripts/pilot_report.py` are ready. No newcomer has been observed. | **Blocks beta** |
| O2 | Curated entry with an unresolved question | A new arrival lands in the first situation and can state what is contested without help. | Partial | (Code) ADR-025: arrivals enter the Orchard Terraces and the Broken Ember Gallery mystery. Opening it is an operator step (`main.py situation --seed 382`). Comprehension is unobserved. | **Blocks beta** |
| O3 | Invite to first place in under 2 minutes | A tester goes from invite link to first place unaided in under 2 min. | Partial | (Code) `static/register.html`, `guide.html`, per-person invite keys (migrations 0004 and 0012). Only rehearsed locally. | **Blocks beta** |
| O4 | Orientation: no one gets lost | At most 1 in 10 newcomers cannot say where they are or how to go back. | Partial | (Docs) Named passages and an eight-place return trail (#107). Issue #87's blinded scale test has not been run. | **Blocks beta** |

## Retention and return

| ID | Item | Exit criterion | Status | Evidence | Gate |
|---|---|---|---|---|---|
| R1 | A daily reason to return | Protocol gates: 1 of 2 return unprompted, and 7 of 10 returns are useful. | Partial | (Code) `persistence/participants.py::recap`, journal, Wayback. The seven-day return metric has no data point. | **Blocks beta** |
| R2 | Weekly rhythm and renewal | Something new or re-armed exists each week, and a cohort gathering runs on schedule. | Partial | (Code) Renewal epochs re-arm sealed-room puzzles (`puzzles/gates.py`). The cohort rhythm (roadmap 3.3) has not started. | Can follow |
| R3 | Persistent consequences | No world reset after the world status is declared. The chronicle survives a restore. | Done | (Code) ADR-004 never-wipe covenant, append-only `world_mutations`, and local restore rehearsal in `tests/test_beta_rehearsal.py`. | **Blocks beta** |
| R4 | Discovery pacing | Median tester reaches a new scale each session and has unvisited reachable places on day 7. | Unknown | (Inference) 4,208 nodes and sealed rooms suggest enough room. Pacing is unmeasured, and Hyperleap (#88) is deferred. | Can follow |
| R5 | World that changes shape (eras, renames, frontier) | At least one era turn visible in Wayback during the cohort. | Not started | (Docs) ADR-029 to ADR-033 are Proposed drafts. No write paths exist. | Can follow · Mark decides |

## Content depth and variety

| ID | Item | Exit criterion | Status | Evidence | Gate |
|---|---|---|---|---|---|
| D1 | Property space distinctness test | 100% unique fingerprints, 99% or more unique aspects, re-run before birth. | Done | (Ran) Ran `scripts/world_quality.py --seed 382`: PASS, score 99.60, names 100%, categories 99.28%. | **Blocks beta** |
| D2 | Puzzle ecology variety | No family above 25%, and world-reading puzzles at 55% or more (the floor the repo's test gate enforces). | Done | (Ran) Ran `scripts/puzzle_quality.py`: PASS, 4,208 puzzles, largest family 19.94% (keeper_witness), world-reading 65.61%, decode 33.75%. Only 54.06% of answers are unique. This gate measures variety, not depth or fun (see C2c). | **Blocks beta** |
| D3 | Node and inhabitant voice quality live | Per-task rubric scores meet the bar on the chosen provider (node, inhabitant, intent, moderation). | Not started | (Docs) `evals/harness.py` accepts only fixture and anthropic. No live eval has been run (2026-10-05 model evaluation doc). | **Blocks beta** · Mark decides |
| D4 | Scene art quality and consistency | The owner accepts art for 20 sampled nodes across all 11 scales. | Partial | (Docs) `imageprompt.py` style matrix is live. The art-quality gap was noted at the expressive-world checkpoint, and ADR-030 is Proposed. | Can follow |
| D5 | Soundscape variety by scale | Each scale's form is recognizable in a blind listen. | Partial | (Code) `static/score.js` defines eleven musical forms, one per scale. Artistic acceptance is unverified. | Can follow |

## AI players and agent policy

| ID | Item | Exit criterion | Status | Evidence | Gate |
|---|---|---|---|---|---|
| A1 | Agent disclosure | Every agent line, presence and effect is labeled as an agent wherever a human sees it. | Partial | (Code) 12 scripted personas in `agents/roster.py`, with persona shown in presences (`Interact.jsx`). A full labeling audit has not been done. | **Blocks beta** |
| A2 | Fairness between humans and agents | Agents use the same surfaces, limits and seals, and get no credit for simulated puzzle solves. | Unknown | (Docs) This is policy in ADR-017 and ADR-032 (Proposed). Enforcement in code was not verified. | Can follow |
| A3 | External AI-agent players via API | Visitor-agent credential minted from an allowlist, with rate limits and a kill switch, tested. | Not started | (Docs) ADR-032 D6 `visitor-agent` is Proposed. There is no `participants.kind` column yet. | Can follow · Mark decides |
| A4 | Agents cost no model spend by default | With the heartbeat on, the model call counter stays flat. | Partial | (Inference) `agents/banter.py` composes lines deterministically. ADR-032 says the heartbeat may spend only when flagged. No zero-spend test was found. | Can follow |

## Safety and moderation

| ID | Item | Exit criterion | Status | Evidence | Gate |
|---|---|---|---|---|---|
| S1 | Shared text fails closed | When moderation errors or is out of budget, no other player sees the text. | Done | (Code) ADR-004 amendment (2026-10-25), `server/moderation.py`, `tests/test_shared_text_fail_closed.py`. | **Blocks beta** |
| S2 | Destinations that may receive player text | A written allowlist of the providers that can receive player text, enforced in config. | Not started | (Docs) Held for Mark. It gates any second provider. | **Blocks beta** · Mark decides |
| S3 | Report and abuse handling | A report reaches an operator within 24 h, and redaction is rehearsed on staging. | Partial | (Code) `main.py redact` (ADR-004 redaction and break-glass delete) exists. No player report flow. | **Blocks beta** |
| S4 | Minors and age policy | A minimum age is stated in the invite and terms. | Not started | (Docs) No age policy found in ADRs, runbook or README. | **Blocks beta** |
| S5 | Chat and notes privacy | Testers consent to chat being kept in the permanent chronicle, or chat is kept out of it. | Partial | (Code) Chat is written as PLAYER_CHAT under the never-wipe rule. Notes are private (rehearsal test). Logs hash IPs (`observability.py`). | **Blocks beta** |

## Economy, budgets and cost

| ID | Item | Exit criterion | Status | Evidence | Gate |
|---|---|---|---|---|---|
| E1 | Daily call caps, global and per user | Caps are sized to cohort x exchanges x cost and enforced. | Done | (Code) `server/guard.py`: text 500 per day and 150 per user, fal 200 and 60, moderation 2,000 and 60, rate limit 20 per minute. | **Blocks beta** |
| E2 | Dollar spend ceiling | A hard monthly dollar ceiling that degrades in fiction when reached. | Not started | (Docs) D8 dollar budgets are planned. The ceiling is held for Mark. | **Blocks beta** · Mark decides |
| E3 | Budget-bucket rename | Neutral bucket names with the old `NESTED_WORLDS_ANTHROPIC_*` names still accepted. | Not started | (Code) The `anthropic` bucket is unchanged in `guard.py`. Held. | Can follow · Mark decides |
| E4 | Abuse resistance | One key cannot exhaust the global budget, and the invite gate closes after the first key. | Done | (Code) Per-user caps, the invite gate (`guard.py`), `NESTED_WORLDS_DISABLE_AI` and `DISABLE_IMAGES` kill switches. | **Blocks beta** |
| E5 | Player token budget as a game resource | Rewards cannot raise anyone's real spend above the ceiling. | Not started | (Inference) No player-facing budget exists. It couples game rewards to real cost. | Can follow |

## Performance and reliability

| ID | Item | Exit criterion | Status | Evidence | Gate |
|---|---|---|---|---|---|
| P1 | Latency targets | On staging, move and act p95 under 300 ms, and speak p95 under 6 s. | Not started | (Inference) No targets are written. The numbers here are proposals. | **Blocks beta** |
| P2 | Load | `ws_soak.py` with 12 or more clients on staging, with no drops. | Partial | (Docs) Local 12-client burst and a backlog of 64 (readiness record). Not hosted. | **Blocks beta** |
| P3 | Hosted backups | `backup_health.py` exits 0 on a real artifact. | Not started | (Docs) The artifact check returns missing. Needs Fly credentials. | **Blocks beta** |
| P4 | Hosted restore rehearsal | A downloaded artifact is restored into staging, with checksum and timing recorded. | Not started | (Code) Local cold restore passes (`tests/test_beta_rehearsal.py`). | **Blocks beta** |
| P5 | Freshness alerting | A stale or missing backup triggers a notification. | Partial | (Code) Script and workflow exist. The scheduler and notification destination are not configured. | **Blocks beta** |
| P6 | Additive migrations | Every migration is additive, and the schema version is pinned. | Done | (Code) `persistence/migrations` 0001 to 0028. | **Blocks beta** |
| P7 | SQLite single-writer limits known | Measured writer ceiling recorded, with headroom 5x over the cohort. | Unknown | (Docs) Litestream replication (roadmap 4.1) is post-launch. | Can follow |

## Observability and feedback

| ID | Item | Exit criterion | Status | Evidence | Gate |
|---|---|---|---|---|---|
| B1 | Error reporting | `SENTRY_DSN` set on production, and a test error arrives. | Partial | (Code) `server/observability.py` is wired. The DSN is unset. | **Blocks beta** |
| B2 | Privacy-respecting beta metrics | `beta_metrics.py --days 1` is read daily during the cohort. | Done | (Code) `scripts/beta_metrics.py` reads the chronicle, with no third-party analytics. | **Blocks beta** |
| B3 | Uptime ping | A `/guide` ping alerts within 5 min. | Not started | (Docs) Runbook step P9. | **Blocks beta** |
| B4 | In-game feedback channel | Testers can post ideas, and the owner reviews them weekly. | Partial | (Code) Ideas board (`static/ideas.html`, ADR-026). Not hosted. | Can follow |
| B5 | Model provenance | Every generated line records provider and model. | Done | (Code) Migration `0028_model_provenance.sql`. | Can follow |

## Model agnosticism

| ID | Item | Exit criterion | Status | Evidence | Gate |
|---|---|---|---|---|---|
| M1 | Provider registry and model per task | Provider selected by config, with startup refusing unusable ids. | Done | (Code) On main at `38fbe6e`: `NESTED_WORLDS_PROVIDER`, `model_for(task)`, `UnusableModelId` (#130 to #132). | **Blocks beta** |
| M2 | Second text adapter (openai_compatible) | Merged with offline contract tests, and ADR-035 Accepted. | Partial | (Docs) PR #133 (ADR-035 Proposed) and #134 (adapter) are in review. | Can follow · Mark decides |
| M3 | Eval harness for every adapter | The harness runs any registered provider against the rubric. | Not started | (Code) `evals/harness.py` accepts fixture and anthropic only. | Can follow · Mark decides |
| M4 | Live quality bar per task | Live probes for success, clarification and refusal pass on the beta provider. | Not started | (Docs) No live credential has been used. Probes are runbook P4. | **Blocks beta** · Mark decides |
| M5 | Provider fallback | A provider outage degrades in fiction, with no failover required for beta. | Partial | (Code) One provider per process, no failover. Fallbacks are logged by exception class (#132). | Can follow |
| M6 | Scene art provider choice | The art provider is selectable like text. | Not started | (Code) Hard-wired to fal.ai. | Can follow |

## Accessibility

| ID | Item | Exit criterion | Status | Evidence | Gate |
|---|---|---|---|---|---|
| Y1 | Reduced motion | `prefers-reduced-motion` stops animation in both clients. | Done | (Code) `static/sensory.js`, `frontend/src/App.jsx`, `Wayback.jsx`. | **Blocks beta** |
| Y2 | Audio off and volume | Sound is off by default or one control away, and nothing requires audio. | Done | (Code) `soundOn` and `scoreVolume` in `TextPanel.jsx`. Sound is optional per the readiness record. | **Blocks beta** |
| Y3 | Keyboard-only play | The full loop (move, speak, puzzle, act) works by keyboard on every cohort device. | Partial | (Code) Playwright focus and keyboard coverage in `frontend/e2e`. Chromium only. | **Blocks beta** |
| Y4 | Screen reader | Main loop usable with VoiceOver or NVDA in one recorded session. | Partial | (Code) aria-labels exist in components. No assistive-technology session recorded. | Can follow |
| Y5 | Cohort device matrix | Each cohort device passes browser, keyboard and fallback checks, or is excluded. | Not started | (Docs) Runbook P5. Only desktop Chromium is exercised. | **Blocks beta** |
| Y6 | Text alternative for sound and visual meaning | State carried by music or art is also stated in text. | Unknown | (Inference) Senses produce a text description, but no captions were found. | Can follow |

## Legal and policy

| ID | Item | Exit criterion | Status | Evidence | Gate |
|---|---|---|---|---|---|
| L1 | Open-source license and notices | License, NOTICE and third-party notices ship in the build. | Done | (Code) Apache-2.0 `LICENSE`, `NOTICE`, `THIRD_PARTY_NOTICES.txt`, ADR-023. | **Blocks beta** |
| L2 | Terms of use and content policy | Linked from the invite and register page, and accepted at registration. | Not started | (Code) No terms page in `static/`. | **Blocks beta** |
| L3 | Player-facing privacy notice | States what is kept forever, what can be redacted, and the retention date. | Partial | (Docs) ADR-004 data policy and protocol consent exist. No player-facing page found. | **Blocks beta** |
| L4 | Third-party provider terms reviewed | A data use note for each provider that receives player text or prompts. | Unknown | (Inference) Tied to S2. Not checked. | **Blocks beta** · Mark decides |
| L5 | AI-generated content disclosure | The guide and UI say which text and art is generated. | Unknown | (Inference) Not audited. | Can follow |

## Deployment and ops

| ID | Item | Exit criterion | Status | Evidence | Gate |
|---|---|---|---|---|---|
| F1 | Fly staging twin | `/health` ok, invite gate closed, `/speak` returns ai true. | Not started | (Docs) Needs Mark's Fly account, billing, flyctl and token ([docs/infrastructure/fly-deployment.md](../infrastructure/fly-deployment.md)). | **Blocks beta** · Mark decides |
| F2 | Release candidate | Version bumped from `0.1.1rc2`, tag cut, release workflow green, wheel smoke passes. | Not started | (Docs) The last tag, `v0.1.1-qa.2`, is far behind main. | **Blocks beta** |
| F3 | Secrets via a secure channel | Secrets set only with `fly secrets` and never in the repo. | Not started | (Docs) Runbook. Only after Mark confirms. | **Blocks beta** · Mark decides |
| F4 | Rollback | A previous release is redeployed on staging in under 10 min. | Partial | (Docs) `scripts/deploy.sh` and runbook. Unrehearsed. | **Blocks beta** |
| F5 | Incident response | One-page playbook: kill switches, redaction, who decides. | Partial | (Code) Kill switches exist in `guard.py`. No incident doc found. | Can follow |
| F6 | Production deploy | Staging torn down, first production backup verified, one key per person minted. | Not started | (Docs) Runbook P9. | **Blocks beta** · Mark decides |

## Community and beta cohort

| ID | Item | Exit criterion | Status | Evidence | Gate |
|---|---|---|---|---|---|
| K1 | Research lead and consent | Lead named, dates fixed, consent wording and deletion date written. | Not started | (Docs) Runbook P5. The lead is a role, not a named person. | **Blocks beta** |
| K2 | Cohort of 8 to 12 with overlapping windows | Seven days each, one protocol-2 row per person. | Not started | (Docs) Invite keys work. No one has been recruited. | **Blocks beta** |
| K3 | Tester docs | A one-page guide that a newcomer reads in under 3 min. | Partial | (Code) `static/guide.html`, README, `docs/community/maintaining-the-community.md`. | Can follow |
| K4 | Feedback loop closed | Each weekly read publishes what changed because of feedback. | Not started | (Inference) Ideas board promotion exists (ADR-026). No cadence yet. | Can follow |

## Community governance and self-policing

| ID | Item | Exit criterion | Status | Evidence | Gate |
|---|---|---|---|---|---|
| G1 | Precondition: personal block, mute and report exist | C7 and S3 are Done before any community consequence ships. | Not started | (Code) No block, mute or report in `server/` or `TextPanel.jsx` (see C7). | **Blocks beta** |
| G2 | Report with a reason and optional evidence | Any player can report another with one reason category from a fixed list and optional evidence (chat lines or chronicle entries). The report is stored per reporter and confirmed to them, and it is never shown to the reported player as coming from a named person. | Not started | (Code) No report flow exists. Chat is stored as PLAYER_CHAT, which could serve as evidence. | **Blocks beta** |
| G3 | Corroboration before any consequence | A case opens only after reports from N distinct established players. A test proves one report alone never triggers a consequence. | Not started | (Inference) Proposed design. N and the meaning of established are Mark's. | Can follow · Mark decides |
| G4 | Graduated consequences | The ladder is written and enforced in code with tests: personal mute (instant), then a temporary suspension, then a permanent ban only after a recorded review. | Not started | (Inference) Proposed design. Who can suspend or ban is Mark's. | Can follow · Mark decides |
| G5 | Owner can suspend or ban (sole reviewer early in beta) | Mark can suspend a player for a set time or ban them, effective within 1 min, recorded with a reason, and reversible. | Unknown | (Inference) Per-person invite keys exist (migrations 0004 and 0012). Whether a key can be revoked to suspend someone was not checked. | **Blocks beta** |
| G6 | Rotating random jury | Jurors are drawn at random from the trusted pool for each case, see only the evidence, and vote independently. There is no open vote by all players. | Not started | (Inference) Proposed design. Open voting is easy to brigade. Jury size is Mark's. | Can follow · Mark decides |
| G7 | Trust standing for jurors and reporters | Standing is computed from account age, fair-play record and past reports that were upheld, and it is pinned by tests. | Not started | (Inference) No standing or reputation data exists. Thresholds are Mark's. | Can follow · Mark decides |
| G8 | Notice and appeal | The accused is told what was decided and why, and can appeal once to a different reviewer within a set window. | Not started | (Inference) Proposed design. Appeal rules are Mark's. | Can follow · Mark decides |
| G9 | Anti-brigading limits | Report weight is capped per reporter per day and per target. False or coordinated reports lower the reporter's standing. Tests cover a coordinated burst. | Not started | (Inference) Proposed design. Chat already has a per-user rate limit (`server/guard.py`). | Can follow |
| G10 | Consistent rules for humans and AI agents | New accounts and AI agents cannot serve on juries. Human and AI-agent players can be reported and face the same ladder. | Not started | (Docs) Agents are labeled personas (`agents/roster.py`). ADR-032's `participants.kind` column doesn't exist yet. How agents are treated is Mark's. | Can follow · Mark decides |
| G11 | Hard-rule violations skip the jury | Reports of illegal content, threats or doxxing go straight to central moderation and reach an operator within 24 h, with redaction available. | Partial | (Code) Moderation fails closed (`server/moderation.py`) and `main.py redact` exists. No report routing. | **Blocks beta** |
| G12 | Action log and owner override | Every report, vote, consequence and appeal is logged append-only, and Mark can overturn any outcome with a recorded reason. | Not started | (Code) The append-only `world_mutations` pattern exists. No governance records. | Can follow |

Proposed from Mark's idea of community self-policing. Personal block and mute stay instant. Community consequences need corroborated reports, a jury and an appeal path. Until there are enough trusted players to staff juries, Mark is the sole reviewer. Jury size, thresholds, who can suspend or ban, appeal rules and how AI agents are treated are Mark's held decisions.

## Distinctiveness: why players return

| ID | Item | Exit criterion | Status | Evidence | Gate |
|---|---|---|---|---|---|
| U1 | Cross-scale consequence chains | A player can trace one of their acts across 2 or more scales in Wayback. | Partial | (Code) Ripples with dampening (`causality/`). The trace UI is unverified. | Can follow |
| U2 | Cross-scale co-op | At least one puzzle needs two players at different scales acting together. | Not started | (Inference) A new idea that fits the nested premise. | Can follow |
| U3 | Places that remember you | A node mentions a tester's past visit (with consent) on return. | Partial | (Code) `get_node_history` feeds `consciousness.speak()`. The live effect is unmeasured. | Can follow |
| U4 | Lasting legacy marks | A tester's inscription is still visible to others a week later. | Partial | (Code) The Room `inscribe` and Object `engrave` verbs exist. Persistence to others was not verified. | Can follow |
| U5 | Seasonal mysteries | A second situation opens after the first resolves, in familiar geography. | Not started | (Docs) ADR-013 versioned situations. Only one situation exists (ADR-025). | Can follow · Mark decides |
| U6 | Agents with goals players can sway | A tester changes an agent's plan through play, and it is recorded in the chronicle. | Not started | (Docs) ADR-032 inhabitant cognition is Proposed. | Can follow · Mark decides |
| U7 | Assembled artifacts from several scales | One assembly in the first mystery grants a real ability. | Not started | (Docs) ADR-018 Proposed. A small assembly is reviewed first. | Can follow · Mark decides |

## Mark's held decisions

| Decision | State | Unblocks |
|---|---|---|
| Destinations that may receive player text | Held | S2, L4, any second provider in use |
| Spend ceiling (dollars, global and per player) | Held | E2, M4, the cohort budget sizing |
| Budget-bucket rename | Held | E3 |
| ADR statuses: 012 to 022, 029 to 033 and 035 Proposed; decisions A to H | Held | C5, R5, U5 to U7, M2 |
| New provider adapters and live evals (Google/Gemini on the candidate list) | Held | M2 to M4, D3 |
| Fly account, billing, flyctl and token | Held | F1, F3, F6, P2 to P5 |
| World status: retained research or production | Held | R3, K2 (never-wipe starts here) |
| Community governance: jury size, report thresholds, who can suspend or ban, appeal rules, AI-agent treatment | Held | G3, G4, G6 to G8, G10 |

## Go/no-go gate

### Blocks beta (status as of Nov 1, 2026)

- [x] Shared text fails closed (S1)
- [x] Content variety gates pass on seed 382 (D1, D2)
- [ ] Player-text destinations and spend ceiling decided (Mark)
- [ ] Block, mute and report shipped (C7, S3, G1, G2)
- [ ] Owner can suspend or ban; hard-rule reports reach an operator (G5, G11)
- [ ] Puzzle depth and fun measured in the pilot (C2c)
- [ ] Terms, privacy notice and age policy published (L2, L3, S4)
- [ ] Staging twin up; live-model probes pass (F1, M4)
- [ ] Hosted backup, downloaded restore and stale alert exercised (P3 to P5)
- [ ] Release candidate tagged; check.sh green with ENFOLDED_E2E=1 (F2)
- [ ] 2 to 3 newcomers observed; confusion fixes merged (O1 to O4)
- [ ] Cohort devices verified or excluded (Y3, Y5)
- [ ] World status declared (Mark)
- [ ] Production deploy with Sentry, uptime ping and per-person keys (F6, B1, B3)

### Can follow the first cohort

- Alignment or disposition meters (C5)
- Points, inventory, token rewards (C2b)
- Neighbor-linked scene art (C3)
- Competitive standings (ADR-017)
- Second provider live, eval harness (M2, M3)
- External agent players (A3)
- World that changes shape (ADR-029 to 033)
- Hyperleap (#88), seasonal mysteries (U5)
- Community juries, consequence ladder and appeals (G3 to G10)

## Open questions for Mark

1. Alignment: one alignment score as in your criterion 5, or ADR-014's independent disposition meters, which deliberately avoid an alignment axis? Which axes?
2. Chat reaches the whole world and is stored forever as PLAYER_CHAT. Should it be place-local with direct messages, and should it stay out of the never-wipe chronicle?
3. Does a block hide only chat and presence, or also the blocked player's effects on shared places? Hiding effects would split the shared world.
4. Which reward ships for beta: points, inventory (ADR-018) or a player token budget? A token budget ties game rewards to real spend.
5. Are external AI-agent players in scope for beta, are they ranked alongside humans, and can they be reported and suspended like humans? (Proposal: yes to reporting, never jurors.)
6. What dollar ceiling for the beta, and what daily cap per player?
7. Self-policing: how big is a jury, how many distinct reports open a case, who can suspend or ban (you only, or juries too), and what are the appeal rules?
8. Puzzle fun: do the proposed playtest bars in C2c (solve rate 40% to 85%, median rating 3.5) match what you want, and should duplicate answers (54% unique) be fixed before beta?
9. Cohort basics: who is the research lead, which devices and dates, and what is the minimum age for testers?

## Glossary

| Term | Meaning |
|---|---|
| World-reading puzzle | A puzzle whose answer comes from the node's own properties and its place in the hierarchy, not a generic word or number puzzle. |

## How this was verified

- Code: read and grepped a clean clone of main at `38fbe6e` (generator, senses, score, gates, effects, rooms, websocket, moderation, guard, participants, migrations).
- Ran: `scripts/world_quality.py` and `scripts/puzzle_quality.py` on seed 382, and both passed. Nothing else was executed.
- Docs: ADR-004, 012 to 018, 024, 025, 029 to 034, the 2026-10-03 readiness record, the Q4 next-steps plan and the Fly runbook.
- Inference: items marked Inference, and the latency and percentage thresholds, are my proposals, not repo facts.
- Puzzles: `WORLD_READING_FAMILIES` in `puzzles/quality.py`, the 55% world-reading test gate, and [docs/evaluation/2026-09-07-concept-and-implementation.md](../evaluation/2026-09-07-concept-and-implementation.md).
- Governance (G1 to G12) is a proposed design from Mark's feedback on Nov 1, 2026, not repo code.
- Not verified: live model quality, hosted anything, real players, and the in-review PRs #133 and #134.
