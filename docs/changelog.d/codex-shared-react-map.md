Section: Added
Status: Roadmap D7: record the in-session World map in /app alongside the living scene. The public entry switch and the legacy /map alias follow in X2.
Status: Watch entry requirement 2: record X1 as the first client change for the Map switch. The requirement still needs X2 and evidence against the selected build.

- **Travel on the world map inside the React client.** For owner item 2, the
  World map control in the passage navigation opens the served tree beside
  the same Speak, Puzzle, Act and Travelers panel. Arrow keys browse places,
  and activating a marker travels there. Reload restores the view and position
  (`MapView.jsx`, `SceneView.jsx`, `App.jsx`, `static/navigation.js`).
  A late read of the previous place's deeper passages can no longer move a
  traveler back after they have left.
  A side-effect import of the vendored D3 left its global undefined in the
  production build. The map reads the module exports there and the browser
  global in development. Its 95 kB gzipped script loads on first use.
  **Verified:** Ruff, 4,329 Python tests (one skip), 256 client unit tests,
  bundle freshness and the installed-wheel check passed after the rebase on
  #185. The 215 Chromium cases covered keyboard travel, reconnect, reload and a failed
  map download. At 320 px with 200% text, the current marker fit the viewport.
  Switching views preserved the Speak draft and WebSocket session.
  **Irreversibility check:** none. The diff changes client rendering and travel
  on the existing movement path. Birth, schema, chronicle writes, world-meta
  pins and era banks are unaffected.
