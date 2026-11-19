Section: Fixed

- **The browser tests that fail the first `/participation` request keep their route for the
  life of the page, so `Browser E2E smoke` no longer loses a request sent while
  interception is being switched off** (`frontend/e2e/notice-fixture.js`,
  `frontend/e2e/participation.spec.js`, `frontend/e2e/participation-pages.spec.js`).
  Owner-directed in the current task, after the job failed on a documentation-only pull
  request (#179, run 44417077688) and passed on the same commit when rerun. Five call sites
  stubbed the first request with a one-shot route (`{ times: 1 }`). When the last route on a
  page is used up, Playwright 1.61.1 sends Chromium `Fetch.disable`. These pages send their
  next request (`/ideas/search`, `/journal/data`, `/position`, `/world`) milliseconds after
  the stubbed failure, and one that reaches Chromium as `Fetch.disable` lands can be left
  unanswered for good; the test then waits 5 s for content that never appears. All five
  sites now call one helper, `failFirstNotice`, whose route stays installed, answers only
  the first request and hands later ones on with `route.fallback()`. No page or server code
  changed. Measured at `7d39ddf` with a temporary logging patch in the installed
  `playwright-core`, removed before the verification runs: before the change 5 of 216 runs
  of the 26 affected tests failed. In the 4 failures recorded with request outcomes, the
  request the page sent next was never answered and Chromium never reported it paused; in
  the 3 of those with a protocol trace it reached Playwright between 0.30 ms before and
  0.08 ms after the acknowledgement of `Fetch.disable`. That differs from the task brief in
  one detail: the brief attributed the hang to Playwright storing a paused request without
  continuing it, but the 10 requests in that state were all answered, so the lost request
  is one Chromium neither pauses nor continues. This was measured on the Chromium the
  session provides (revision 1243), not revision 1228 in the CI image. After the change the
  same 141 runs of the two files switch interception off 3 times instead of 99, all 3 in
  one test whose page is waiting for a click. Every other route removal in the suite was
  measured the same way and left alone: across 195 removals in 450 runs of the eight other
  spec files that remove a route, no page request reached Playwright before `Fetch.disable`
  was acknowledged, and `frontend/e2e/blocking.spec.js` keeps its one-shot route because
  its page sent nothing within 250 ms of it in 10 runs. Not checked: whether a later
  Playwright or Chromium release closes the gap.
  **Verified:** on the unpatched Playwright 1.61.1, `--repeat-each 20` passed 240 of 240 for
  `participation-pages.spec.js` and 700 of 700 for `participation.spec.js`, 520 of them runs
  of the 26 affected tests. `ENFOLDED_E2E=1 ./scripts/check.sh` exited 0 under Python 3.11.18
  and Node 20.19.0: Ruff clean, 4,329 Python passed and 1 skipped, 241 Vitest passed, bundle
  unchanged by the rebuild, installed `enfolded-0.1.2rc1` wheel verified, 212 Playwright
  passed. The same suite before the change, under the logging patch: 211 passed and
  `participation.spec.js:109` failed. Browser runs used the session's Chromium through
  `PW_CHROMIUM_PATH`.
  **Irreversibility check:** none — one new browser-test helper, two browser-test files and
  this fragment; no product code, migration, birth or golden change, chronicle writer,
  world-meta pin or era-bank edit, and `static/app` is unchanged.
