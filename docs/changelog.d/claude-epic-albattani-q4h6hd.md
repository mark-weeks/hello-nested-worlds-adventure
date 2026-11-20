Section: Fixed

- **The co-viewer delivery test waits for the explorer's world before it counts reads**
  (`frontend/e2e/delivery.spec.js`). Serves the launch gate's CI reliability: the `/`
  variant of "co-viewers keep their own action replies while the shared state updates"
  failed twice on documentation-only head `e391521` (PR #182, run 44779492619) with
  reads `[{"world":0,"node":6},{"world":1,"node":5}]`. `enter()` returned right after
  clicking Act, but the explorer's `boot()` awaits `/position` before `loadWorld()`
  fetches `/world`, so on a loaded runner the second viewer's `/world` read could land
  after the request counters were attached. `enter()` now waits, for the `/` route
  only, until the status line reads exactly "<n> nodes · shared world · depth <d>",
  which is set after the `/world` response is drawn. A first version matched any
  "shared world" text; Codex's review found that "Opening the shared world…" (set
  before the fetch) also matched, letting the first player act while the second
  viewer had zero nodes and no WebSocket. The assertion is unchanged; the `/app`
  branch is unchanged.
  Reproduced locally under CPU contention (8 busy loops on 4 cores, 4 workers): 3/20
  failures before, all with the CI signature; 20/20 passes with the first wait and
  39/40 with the exact one (the one failure was the density timeout below, not the
  race), and the whole delivery spec passes 17/17 unloaded. Surprise: at that
  same load the `/app` variant fails 19/20 both with and without this change, a 45 s
  timeout waiting for the second delayed arrival (star density stays 438, not 459); it
  is a separate load-budget limit, not this race, and is left alone. At moderate load
  (2 busy loops, 2 workers) both variants pass 15/15. Known gap: that load-budget
  limit (the 25 s density poll inside the 45 s test budget) will return as a CI flake
  on a busy runner; the likely fix is a scaled poll or test timeout, or a shorter
  maturation scale for this test.
  **Verified:** the repeated Playwright runs above (Node 20.19.0, Python 3.11, system
  Chromium via `PW_CHROMIUM_PATH`). `ENFOLDED_E2E=1 ./scripts/check.sh` green on
  `c8168ba`, before the exact-status wait: Ruff clean; 4,329 Python tests passed, 1
  skipped; 241 Vitest tests in 20 files; frontend build and bundle freshness passed;
  installed wheel verified; 212 Playwright tests passed. After the exact-status wait,
  `delivery.spec.js` 17/17 locally; current-head CI is recorded in PR #184.
  **Irreversibility check:** none — a test-harness wait in one E2E spec; no generator,
  store, migration, chronicle, endpoint or client-bundle source change.
