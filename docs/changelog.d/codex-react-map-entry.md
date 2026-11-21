Section: Added
Status: Roadmap D7: record the shared React map at /, the living scene at /app and the original explorer at /map through the cohort read-out.
Status: Watch entry requirement 2: X1 and X2 implement the public Map switch. Selected-build, venue and access evidence still belongs to the Watch record.

- **New arrivals at the public root open the shared world map.** Invitations
  and registration open the living scene at `/app`. Map and scene share
  the traveler's session, place and interaction panel, and a reload restores
  the view they chose. The original explorer is available at `/map` through
  the cohort read-out (owner item 2, ADR-005 §3).
  The scene draws on a 2D canvas and the map uses D3. Removing PixiJS and
  its eleven transitive packages reduced the main script from 373,897 to
  250,234 bytes. The notice inventory now has five npm production packages.
  **Verified:** 266 focused Python tests, 258 client unit tests and 18
  focused Chromium cases passed. A fresh wheel installation served both
  HTML shells and their referenced scripts on all three routes. Chromium
  exercised consent, register and invite entry, keyboard travel, reload and
  the return from the Guide to the map at the player's saved place.
  **Irreversibility check:** The new public `GET /map` serves the static
  explorer shell. Game data still requires the configured invitation and
  participation checks. Changing the public entry is reversible and needs
  the owner's authentication review. The diff does not touch world births,
  migrations, chronicle writes, world-meta pins or era names.
