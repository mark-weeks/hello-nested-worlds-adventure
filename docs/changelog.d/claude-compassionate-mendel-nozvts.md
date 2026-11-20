Section: Fixed

- **A co-viewer's Act panel shows another player's delayed action while it is still
  pending** (`static/interventions.js`, `static/explorer.js`, `frontend/src/App.jsx`,
  `frontend/e2e/delivery.spec.js`, `frontend/src/__tests__/interventions.test.js`,
  rebuilt `static/app/`). Owner direction (2026-11-20): make the `delivery.spec.js`
  co-viewer test reliable under CPU load without loosening it. The cause was a client
  defect, not the pump. The shared composer re-read `/interventions` only when the
  node's `senses.revision` changed. A delayed (v3) acceptance changes no served
  property, and `pending_actions` reports only the legacy `verb_maturation` queue, so a
  co-viewer saw nothing until the first arrival landed: 18.7 s in the test, 5 min at
  Galaxy scale and 30 min at Multiverse scale in production. Instrumented runs showed
  pump ticks punctual (gap 5.00–5.08 s, work ≤1.7 s) and arrivals 15–19 s after
  commit. The second Kindle, though, always came 0.5–8 s after the first *arrival*,
  because `click()` on "Actions still echoing" waited for the panel's first recent
  entry. The test therefore serialized two maturations and used 42.5 s of its 45 s
  budget with no load. Under load (8 busy loops on 4 cores, 4 workers) it hit the
  45 s test timeout; the poll's "438" was its last value, not a slow arrival.
  Both hosts now announce each `intervention_changed` broadcast. The composer re-reads
  `/interventions` for its own node as a background read: no `/node` read, one extra
  GET per co-viewer per broadcast on that node. Codex's review of the first version
  (PR #185) found four more defects, all reproduced in Chromium and fixed here:
  - With a control focused, the first record never appeared, because `renderRecent()`
    had no `.recent` container to fill. The disclosure is now added in place, keeping
    focus and any draft.
  - A failed background read (one 429 from the per-IP read limiter) replaced the
    viewer's own receipt and was never retried. Background failures now stay out of
    the status line and retry at 8 s, 16 s and so on, up to 60 s.
  - Re-rendering the history dropped keyboard focus from an "Observed" button. Focus
    is now restored by arrival event id.
  - The test still passed when visibility came only after the arrival, because the
    row stays after landing and the 10 s bound started at Ada's reply.
  The test now gives Bea's Kindle focus before Ada acts. It requires the disclosure
  within 10 s with that focus kept, Ada's row "Consequences pending" with zero
  "Observed" arrivals, and the galaxy still at 418. Against the first version's
  composer it fails at the 10 s disclosure wait, deterministically. Measured: one test
  went from ~39 s to ~21 s unloaded. Before PR #184 merged, the `/` route failed with
  its `"world":1` read-count race (9/20 here). With #184 and the review fixes, 2 of 40
  `/app` runs at the load above still hit the 45 s test budget: both had already
  reached 459 and were in the final per-page checks. That budget left ~5 s at the
  slowest load (page entry up to ~19 s, then 15 s maturation and up to 5 s pump). The
  co-viewer test's overall budget is now 60 s. Its 25 s delivery poll and 10 s
  visibility bound are unchanged.
  **Verified:** Vitest `interventions.test.js` 14/14; the three new review-driven cases
  fail on the reviewed head `b9f15f8`. Frontend rebuilt. Co-viewer stress at the load
  above 40/40 with the 60 s budget (Node 20.19.0, Python 3.11, system Chromium via
  `PW_CHROMIUM_PATH`). The first version's `ENFOLDED_E2E=1 ./scripts/check.sh` was
  green on `41ab14e`: Ruff clean; 4,329 Python tests passed, 1 skipped; 242 Vitest
  tests in 20 files; frontend build and bundle freshness passed; installed wheel
  verified; 212 Playwright tests passed. The canonical gate on the review-fix head is
  recorded in PR #185.
  **Irreversibility check:** none — client refresh wiring and one E2E/unit test; no
  generator, bank, golden pin, migration, chronicle write path, `world_meta` pin, era
  bank or endpoint change. The Act surface stays the single interaction surface (no
  new pane), and no player can act for another.
