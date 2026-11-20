Section: Fixed

- **The co-viewer delivery test waits for the explorer's world before it counts reads**
  (`frontend/e2e/delivery.spec.js`). Serves the launch gate's CI reliability: the `/`
  variant of "co-viewers keep their own action replies while the shared state updates"
  failed twice on documentation-only head `e391521` (PR #182, run 44779492619) with
  reads `[{"world":0,"node":6},{"world":1,"node":5}]`. `enter()` returned right after
  clicking Act, but the explorer's `boot()` awaits `/position` before `loadWorld()`
  fetches `/world`, so on a loaded runner the second viewer's `/world` read could land
  after the request counters were attached. `enter()` now waits, for the `/` route
  only, until the status line reads "shared world", which is set after the `/world`
  response is drawn. The assertion is unchanged; the `/app` branch is unchanged.
  Reproduced locally under CPU contention (8 busy loops on 4 cores, 4 workers): 3/20
  failures before, all with the CI signature, and 20/20 passes after. Surprise: at that
  same load the `/app` variant fails 19/20 both with and without this change, a 45 s
  timeout waiting for the second delayed arrival (star density stays 438, not 459); it
  is a separate load-budget limit, not this race, and is left alone. At moderate load
  (2 busy loops, 2 workers) both variants pass 15/15.
  **Verified:** the repeated Playwright runs above (Node 20.19.0, Python 3.11, system
  Chromium via `PW_CHROMIUM_PATH`); full gate result in the pull request.
  **Irreversibility check:** none — a test-harness wait in one E2E spec; no generator,
  store, migration, chronicle, endpoint or client-bundle source change.
