# Ensemble Action Plan (2026-07-19)

The execution plan for the findings and recommendations of
`docs/evaluation/2026-07-19-expert-ensemble-evaluation.md`, restructured
around the project owner's challenge to the freeze-at-launch stance
(ADR-006). Living document, phase-2-scale style: edit in place as items
land; when one ships, fold it into the CHANGELOG entry and strike it here.

Governing decision: **ADR-006 (evolving world with memory) is Proposed and
awaiting ratification.** Track 0 gates the items marked ⚑. Everything else
proceeds regardless of which option is ratified.

---

## Track 0 — The evolution decision (gate)

| # | Item | Size | Notes |
|---|------|------|-------|
| 0.1 | **Ratify ADR-006** (options A–D; recommendation is B: freeze-as-scaffolding, materialize post-launch) | decision | The one architecture-changing question; everything ⚑ below assumes B until ratified otherwise |
| 0.2 | **Re-word the freeze covenant** in CLAUDE.md + freeze-suite docstrings: temporary scaffolding with a named successor, not a permanent door | ~1 hr | Do before launch in every branch except D — the permanent-freeze *language* is itself about to freeze. Replaces the evaluation's rec 3 ("ceiling decision memo") with the stronger form |
| 0.3 ⚑ | **Land the mirror**: additive `nodes` table (seed, path, name, level, properties_json, born_at, generator_version), birthed per seed on first use; behavior test asserts mirror ≡ generation at both depths | 1–2 days | Additive migration; nothing reads it yet; zero launch risk. The freeze suite now also guards the mirror |

## Track 1 — Pre-launch gates (blockers; order matters)

| # | Item | Size | Finding |
|---|------|------|---------|
| 1.1 | **Fix `/register`**: externalize the inline script to `static/register.js` (CSP `script-src 'self'` currently blocks the whole self-service invite flow); add `/register` to the Playwright smoke suite | hours | Eval §top, §5.1 — the one broken front door; confirmed by execution |
| 1.2 | **Set `FLY_API_TOKEN` + verify one dispatched backup run** — ADR-005's hourly-backup decision is paper until this exists | minutes + verify | Eval §6.1; runbook §8 already lists it |
| 1.3 | **Run the ADR-005 staging rehearsal** (onboarding watch, WS soak, live-voice probe on `claude-opus-4-8`, restore rehearsal) on the disposable twin | scheduled | Eval §6.1; ADR-005 §2 |
| 1.4 | Track 0 items 0.1–0.2 (and 0.3 if B ratified in time; 0.3 may also land launch-week — it is additive) | — | — |

## Track 2 — Launch-window senses batch (small, low-risk, high felt impact)

The convergent finding: the infrastructure has outrun the presentation —
the game's best material is behind an alternate client, a mute toggle, and
a key. These keep the ADR-005 client posture and move the senses into the
default surface.

| # | Item | Size | Finding |
|---|------|------|---------|
| 2.1 | **Hero-size the explorer's sigil** — the generative art as the panel's lead element, not a sidebar thumbnail | ~½ day | §4.1 |
| 2.2 | **Sound invitation**: once-per-session in-fiction line ("the world hums — listen?") whose click is the WebAudio gesture; plus a sound section in `/guide` (currently zero mentions) | ~½ day | §4.2 |
| 2.3 | **Capture the four pitch assets** from a live seed-42 run (drop-in, cascade GIF, 11-family art grid, heartbeat wanderer) into `docs/pitch/assets/` | ~½ day | §2.2 |
| 2.4 | **Tuck the explorer's Seed/Depth/Breadth header behind an "advanced" affordance** — stop handing first-timers the engine room | ~½ day | §5.1 |

## Track 3 — Early post-launch (first month)

| # | Item | Size | Finding |
|---|------|------|---------|
| 3.1 ⚑ | **The pivot batch**: swap read paths to the stored world; `resolve_node_by_name` becomes a lookup; generator retires to birthing; re-scope the freeze suite to birth-digest + migration invariants. Schedule beside/after the Litestream batch (both raise the DB to sole-authority status) | ~1 wk | ADR-006 §B step 3 |
| 3.2 ⚑ | **Open evolution**: banks unfreeze for new growth (new seeds, renewal-epoch content, frontier growth ≤9 children/node); deliberate change to existing nodes ships as chronicled `WORLD_EVOLVED` events — operator-triggered only at first | ~1 wk | ADR-006 §B step 4; supersedes the era-gated escape hatch |
| 3.3 | **Cohort rhythm**: extend runbook §8's one-time shared LOCK expedition into a recurring weekly gathering; read `beta_metrics.py` weekly, returning-visitor number governs phase-2 pulls | ~hrs + standing | §5.2 |
| 3.4 | **Since-you-left recap**: personal delta on resume ("since you left: Tessera passed your room; the Wastes renewed their puzzle") — the chronicle can already answer it | 1–2 days | §5.2 |
| 3.5 | **Close the FSM-agent renewal-epoch mismatch** (agents roll epoch-0 puzzles post-renewal while their solves feed the re-arm condition) | ~½ day | §3.1 |
| 3.6 | **Per-node deep links** ("meet me here" as a URL) | ~1 day | §5.1 |

## Track 4 — Scheduled / trigger-driven (existing commitments + new)

| # | Item | Trigger / schedule | Finding |
|---|------|--------------------|---------|
| 4.1 | Litestream continuous replication | already scheduled first post-launch batch (ADR-005) — pairs with 3.1 | — |
| 4.2 | `/app` mobile pass + depth parity + parity-harness completion | ADR-005 revisit trigger | §4.1 |
| 4.3 | **World-speaks-first experiment**: one budgeted call/world/day — a node with fresh history composes an opening line for its next visitor | after a month of voice transcripts | §2.3, §3.3 |
| 4.4 | Sonnet 5 A/B on live transcripts | ADR-005 §4 | §2.3 |
| 4.5 | `server/handlers.py` split (~1,700 lines: routing / WS loop / co-op / constellations) | before the next multi-endpoint feature | §6.1 |
| 4.6 | Constellation-style arcs at a third scale pair; numeric answer-tail rework | post-pivot, as evolution content (3.2 makes this possible for existing nodes) | §3.1, §3.2 |
| 4.7 | Display-name treatment for deep-scale suffixes | post-pivot (a rename-grammar question — fold into 3.2's event design) | §2.1, §3.3 |
| 4.8 | Publish the cost-engineering case study | whenever | §2.3 |

## Explicitly deferred / declined

- **Pitch video** (§8 split, unresolved): revisit only when outreach is
  concrete; the four reproducible captures come first.
- **EFFECT_THRESHOLD tuning** (§8 split): recorded as a tuning question,
  no change planned.
- **Client posture change**: explorer stays the default (ADR-005); Track 2
  is the compensation, not a reversal.

---

## Mapping: evaluation recommendations → plan items

| Eval rec | Plan item(s) |
|----------|--------------|
| 1. Fix `/register` | 1.1 |
| 2. Walk the procedural gates | 1.2, 1.3 |
| 3. Frozen-ceiling decision in writing | **superseded by ADR-006 / Track 0** (challenge accepted rather than documented) |
| 4. Default surface leads with the senses | 2.1, 2.2 |
| 5. Capture pitch assets | 2.3 |
| 6. Cohort rhythm | 3.3 |
| 7. Agent epoch mismatch | 3.5 |
| 8. Post-launch experience batch | 3.4, 3.6, 4.2, 4.3, 4.5 |
