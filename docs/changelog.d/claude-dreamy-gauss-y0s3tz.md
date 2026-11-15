Section: Fixed

- **The map page keeps every traveler name as text, quotes included** (`static/explorer.js`,
  `frontend/e2e/blocking.spec.js`). The map page's HTML helper escaped `&`, `<` and `>` but
  not quotation marks, and it is used inside double-quoted attributes: the traveler list's
  "go to" title, the Block and Unblock labels and the feed's Block control. A registered
  name containing `"` therefore ended the attribute early. With the name `Bea "Q" O'Hara`
  the map page's Block control read "Block Bea " before this change. The helper now also
  escapes `"` and `'`. The scene at `/app` renders through React and was not affected; the
  new browser case runs on both clients. The map page is kept (owner decision, 2026-11-15)
  and frozen to privacy, safety and correctness fixes until the planned Map view replaces it.
  **Verified:** the new Playwright case fails on `/` without the fix ("Block Bea ") and passes
  on `/` and `/app` with it. `ENFOLDED_E2E=1 ./scripts/check.sh` exited 0 under Python 3.11
  and Node 22 (not the pinned 20.19): Ruff clean, 4,007 Python passed and 1 skipped, 189
  Vitest passed, bundle unchanged by the rebuild, installed `enfolded-0.1.2rc1` wheel
  verified, 183 Playwright passed.
  **Irreversibility check:** none — one client helper and one browser test; no migration,
  birth or golden change, chronicle writer, world-meta pin or era-bank edit.
