Section: Added
Status: Checklist L5: mark Done when merged. Both clients and the Guide identify generated text and art. Provider-specific wording still depends on O3.

- **Players can see when AI supplied a reply or a scene background**
  (`static/clientlogic.js`, `static/sensory.js`, `static/guide.html`). Speak
  labels generated replies to places and inhabitants. Scene and replay captions
  follow what the canvas actually draws, including the four generated backgrounds
  shipped with the game. The Guide explains authored replies, traveler chat,
  free-text action interpretation and the effects drawn from world conditions.
  **Verified:** Ruff passed, 4,342 Python tests passed with one skip, and all
  262 client unit tests passed. The bundle rebuilt byte for byte and the
  installed-wheel smoke passed. Six focused Chromium checks covered late replies
  after changing speakers, failed image loads and accessible captions in both
  clients. The [PR verification record](https://github.com/mark-weeks/hello-nested-worlds-adventure/pull/194)
  covers the full 223-case Chromium suite.
  **Irreversibility check:** These reversible client and Guide edits read existing
  response flags and canvas state. They introduce no provider call, stored actor
  label, world-history write, migration, generator change or authentication change.
