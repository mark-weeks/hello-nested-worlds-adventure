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
  45 s test timeout; the poll's "438" was its last value, not a slow arrival. Both
  hosts now announce each `intervention_changed` broadcast, and the composer
  re-reads `/interventions` for its own node with `load()`. That re-read adds no
  `/node` read; it is one extra GET per co-viewer per broadcast on that node. The
  test's assertions are unchanged except one tightening: Bea must open "Actions still
  echoing" and see "Ada · Kindle" within 10 s, inside the 15 s maturation. Against the
  old composer it now fails deterministically (click timeout at 10 s) instead of
  passing slowly. Measured: one test went from ~39 s to ~21 s unloaded; under the
  load above, `/app` went from 1/20 to 19/20 passing (one 45 s timeout in setup). With
  PR #184's explorer wait applied locally, both routes passed 40/40: mean 26.3 s,
  slowest 39.9 s to the 459 landing; that tail is page entry under load (Ada's first
  reply up to 18.8 s). Without #184 the `/` route still fails with #184's
  `"world":1` read-count signature (9/20 here), so this branch rebases onto #184.
  Known gap: the 45 s budget keeps ~5 s of headroom at the slowest observed load.
  **Verified:** Vitest `interventions.test.js` 11/11, new case failing on the old
  composer; frontend rebuilt; the Playwright stress runs above (Node 20.19.0, Python
  3.11, system Chromium via `PW_CHROMIUM_PATH`). `ENFOLDED_E2E=1 ./scripts/check.sh`
  is in progress; its result is recorded in the next commit.
  **Irreversibility check:** none — client refresh wiring and one E2E/unit test; no
  generator, bank, golden pin, migration, chronicle write path, `world_meta` pin, era
  bank or endpoint change. The Act surface stays the single interaction surface (no
  new pane), and no player can act for another.
