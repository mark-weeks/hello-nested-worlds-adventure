# Ensemble Action Plan (2026-07-19)

The execution plan for the findings and recommendations of
`docs/evaluation/2026-07-19-expert-ensemble-evaluation.md`, restructured
around the project owner's challenge to the freeze-at-launch stance
(ADR-006). Living document, phase-2-scale style: edit in place as items
land; when one ships, fold it into the CHANGELOG entry and strike it here.

Governing decision: **ADR-006 ratified 2026-07-19 — Option A (materialize
before launch), and the pivot has shipped.** Track 0 is complete; items
formerly gated on it (⚑) are unblocked.

---

## Track 0 — The evolution decision ✅ RESOLVED

| # | Item | Status |
|---|------|--------|
| 0.1 | ~~Ratify ADR-006~~ | **Option A ratified by the owner, 2026-07-19** |
| 0.2 | ~~Re-word the freeze covenant~~ | **Shipped** — CLAUDE.md's permanent-world section and the freeze-suite docstring now describe the materialized world (banks govern births only) |
| 0.3 | ~~Materialize the world~~ | **Shipped as the full Option A pivot** (`multiverse/store.py`, migration 0013, all read paths swapped; equivalence + bank-edit immunity pinned; suite 800 green, E2E 3/3). See CHANGELOG "The world is data now" |

## Track 1 — Pre-launch gates (blockers; order matters)

| # | Item | Size | Finding |
|---|------|------|---------|
| 1.1 | ~~**Fix `/register`**: externalize the inline script to `static/register.js`; add `/register` to the Playwright smoke suite~~ **Shipped 2026-07-19** (see CHANGELOG) — e2e-verified in real Chromium under the production CSP | hours | Eval §top, §5.1 — the one broken front door; confirmed by execution |
| 1.2 | **Set `FLY_API_TOKEN` + verify one dispatched backup run** — ADR-005's hourly-backup decision is paper until this exists | minutes + verify | Eval §6.1; runbook §8 already lists it |
| 1.3 | **Run the ADR-005 staging rehearsal** (onboarding watch, WS soak, live-voice probe on `claude-opus-4-8`, restore rehearsal) on the disposable twin | scheduled | Eval §6.1; ADR-005 §2 |
| 1.4 | Track 0 items 0.1–0.2 (and 0.3 if B ratified in time; 0.3 may also land launch-week — it is additive) | — | — |

## Track 2 — Launch-window senses batch (small, low-risk, high felt impact)

The convergent finding: the infrastructure has outrun the presentation —
the game's best material is behind an alternate client, a mute toggle, and
a key. These keep the ADR-005 client posture and move the senses into the
default surface.

| # | Item | Status | Finding |
|---|------|--------|---------|
| 2.1 | ~~Hero-size the explorer's sigil~~ | **Shipped 2026-07-19** — sidebar 300→340px, sigil 268×140→308×232, the art leads the location panel | §4.1 |
| 2.2 | ~~Sound invitation + guide sound section~~ | **Shipped 2026-07-19** — once-per-session in-fiction offer ("The world hums, softly, in every place. Listen?"), click = the WebAudio gesture, e2e-verified; `/guide` gains "The world hums — listen" | §4.2 |
| 2.3 | ~~Capture the four pitch assets~~ | **Shipped 2026-07-19** — all four captured live from seed 42 in headless Chromium (`docs/pitch/assets/`), brief updated; the cascade GIF shows dampening in the feed numbers (+0.50 → +0.25) | §2.2 |
| 2.4 | ~~Tuck the engine-room header~~ | **Shipped 2026-07-19** — Seed/Depth/Breadth/Generate hidden behind a ⚙ affordance, e2e-verified | §5.1 |

## Track 3 — Early post-launch (first month)

| # | Item | Size | Finding |
|---|------|------|---------|
| 3.1 | ~~The pivot batch~~ **Shipped pre-launch with Track 0** (Option A) — note: Litestream (4.1) matters MORE now; the DB is the sole authority for world content | done | ADR-006 |
| 3.2 | **Open evolution mechanics**: design the evolution-event grammar first (kinds, cadence, operator-only triggers, rename lineage — ADR-006 "Revisit when"), then ship frontier growth / renewal-epoch families / chronicled `WORLD_EVOLVED` change. The store makes these possible today; each new chronicle write path stays a one-way door under the merge gate | ~1 wk | ADR-006; supersedes the era-gated escape hatch |
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
