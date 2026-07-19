# Enfolded — Critical Repo Evaluation (2026-07-18)

Method note: this is an adversarial audit of the repo's structure, content,
consistency, continuity, and cohesiveness — the successor to the 2026-07-04
deep evaluation, aimed at the repo *as a record* as much as the game. Five
parallel audit passes (determinism/freeze, covenants, server security,
frontend drift, docs cross-consistency) read the load-bearing code in full;
the Python suite and Vitest suite were executed; the frontend was rebuilt
from source and diffed against the committed bundle; the canonical world was
regenerated to check pinned counts; individual defects were confirmed by
execution where claimed. Two things could not be verified from this sandbox:
the live deployment (outbound network is policy-blocked) and the "~12k
worst-case full-depth tree" figure (single-sourced in the CHANGELOG).

> **Second addendum (2026-07-19, later): four residuals this audit left
> outside its top ten are also resolved** — in the pre-launch hardening
> batch at the top of `docs/CHANGELOG.md`: the §4 reconnect edge (the WS
> join now resumes the key's saved position; `/position` validates and
> seal-checks at write time), the §3 P3 prompt-injection seam (recorded
> speech is folded and framed as testimony in both bibles), the §7
> `describeMutation` drift + missing `locked` badge + walk-through
> mechanism split (one canonical module, executed parity), and two §3
> nitpicks (RFC 6455 control-frame limits; rate-limiter/touch-cache
> eviction). Still open from this audit, by scope decision: the seal
> gates only movement, agent solves feed the re-arm epoch, and FSM
> agents roll against epoch-0 puzzles post-renewal.

> **Addendum (2026-07-19): the ten recommendations below are resolved** —
> in the follow-up batch recorded at the top of `docs/CHANGELOG.md`
> ([Unreleased], "The 2026-07-18 evaluation's ten recommendations,
> resolved"). The bundle is rebuilt with a CI freshness gate (rec 1),
> `busy_timeout` is set (2), the GET limiter + `max_nodes` clamp exist (3),
> moderation NFKC-folds homoglyphs (4), credentials are hashed at rest (5),
> renewal-epoch puzzles and verb overlay keys are pinned (6), the doc-drift
> census is swept (7), both covenants are re-scoped in CLAUDE.md with the
> perimeter 500s fixed (8), a dated release boundary is cut (9), and ruff
> runs in CI (10). The findings sections below are preserved verbatim as
> the audit that drove that batch — read them as history of 2026-07-18
> HEAD, not current state.

The one-line verdict up front: **the engineering is better than the
documentation says, and the documentation is the best thing in the repo —
both at once.** The determinism contract, the freeze pins, the covenant
mechanics, and the WS/concurrency plumbing substantially survive adversarial
reading. What does not survive is the repo's implicit claim that its record
*stays* true: every document that "testifies" — the README matrix, the beta
brief, two ADRs, the architecture overview — has drifted from the code within
days of being verified, and one shipped artifact (the committed `/app`
bundle) is provably stale against the PR that claims it isn't. The repo's
method verifies at write time and then trusts; nothing re-verifies.

---

## 1. What holds up under attack (verified, not taken on faith)

- **The determinism contract is real and consistently executed.** Every RNG
  in generation, puzzle selection, renewal epochs, laws routing, verbs, eras,
  banter, agent solve-rolls, and both JS art/sound modules is
  content-addressed (`multiverse/generator.py:457-461`,
  `puzzles/generators.py:245-254,770-773`, `causality/laws.py:62-79`,
  `multiverse/verbs.py:87-90`, `multiverse/chronicle.py:51`,
  `agents/banter.py:213`, `agents/agent.py:75-78`, `static/nodeart.js:15-31`,
  `static/nodesound.js:84-86`). A repo-wide sweep found zero unseeded
  `random.*`/`Math.random`/wall-clock calls in any frozen surface.
- **The freeze pins genuinely cover both depths, behaviorally.**
  `tests/test_continuity_freeze.py` regenerates and digests the 293-node
  depth-6 world *and* the 4,439-node full world (names, properties, epoch-0
  puzzles, landmarks per deep level, breadth profile) — real behavior pins,
  not greps. All 12 pass here under Python 3.11.15.
- **Three covenants hold cleanly at every surface checked**: per-node
  difficulty (`puzzles/generators.py:65-75`, no depth term, behavior-tested
  at both extreme scales); agent-solves-don't-count (single chokepoint
  `persistence.get_puzzle_solve` skips `"agent"` rows — verified at the co-op
  session, seal, and constellation surfaces); additive-only migrations (all
  twelve read in full: no DROP, no destructive ALTER).
- **The server layer is more careful than "hand-rolled stdlib server"
  suggests.** RFC 6455 framing rejects unmasked frames, bounds reassembly,
  handles control frames mid-fragment; the writer-thread/outbox broadcast
  model is race-free with eviction instead of blocking; SQL is fully
  parameterized; path traversal is guarded with `resolve().relative_to`;
  client-IP handling prefers the non-spoofable header and never trusts
  left-most XFF; credentials never reach the access log.
- **The ops story matches its documentation exactly**: `scripts/deploy.sh`
  really refuses to deploy over an unbacked chronicle; the daily off-host
  backup workflow, fly.toml sizing, and restore path are as described.
- **Suite health**: 750 Python tests collected and passing, 69/69 Vitest —
  both matching the README's claims exactly. (An early "747" reading during
  this audit turned out to be an audit-environment artifact — a PATH pytest
  without the `websockets` dev extra silently dropping the three RFC 6455
  conformance tests — which is itself a small vote for the suite's honesty.)

The 2026-07-04 evaluation's recommendations have, verifiably, shipped —
including several its own addendum forgets to claim (rec 2's roster/backfill
fix, rec 9's CLI repairs, rec 8's JS test infrastructure). The repo fixed
more than it recorded fixing, which is a novel failure direction for it.

---

## 2. The headline defect: the committed bundle is stale, and nothing can notice

PR #67 added `chat_declined` handling to `frontend/src/dispatch.js:19` and
claimed ("rendered by both clients so the message doesn't silently vanish")
it reaches players. It does not reach `/app` players on any non-Docker
deployment: the committed `static/app` bundle was last rebuilt in PR #61
(`git log -- static/app`), contains **zero** occurrences of `chat_declined`,
and a fresh `npm run build` produces different hashes for **all 11** asset
files. The three mechanisms that should have caught this each miss it by
construction:

- CI's frontend job builds and **discards** the output; the e2e job rebuilds
  fresh before Playwright runs. CI never exercises the committed bundle.
- `tests/test_frontend_contract.py` checks the bundle only for a fixed list
  of #61-era strings — all present in the stale artifact — while its own
  comment (line 46-47) states the contract being violated: "The committed
  bundle is what the server actually serves at /app."
- The Dockerfile rebuilds the frontend at deploy time, so production hides
  the staleness — which also means the committed bundle is *tested* but not
  *shipped*, and the freshly built bundle is *shipped* but never tested
  against the contract suite. The two artifacts can drift in opposite
  directions indefinitely.

This is the exact failure class the repo's own history warns about (deploy
files that existed only as fenced code; grep tests that passed while behavior
was broken), recurring in its newest seam: a build artifact that must be
**regenerated**, where the freeze-and-trust method has no pin. Fix is
mechanical: rebuild and commit, then add a CI step that builds and fails on
`git diff --exit-code static/app` — or stop committing the bundle and let
`/app` 404 in no-Node dev environments honestly.

## 3. Correctness and security findings (ranked)

- **P1 — no SQLite `busy_timeout`.** `persistence/__init__.py:78` sets WAL
  but leaves the busy timeout at 0, so a second concurrent writer gets an
  immediate `database is locked` instead of waiting — and there are always
  concurrent writers (request threads, heartbeat, causal pump). In the WS
  loop, the move/chat `record_mutation` calls sit outside the
  `except (OSError, ProtocolError)` arms, so an `OperationalError` tears the
  connection down. The repo demonstrably knows this class — PR #66 refactored
  minting specifically to avoid `SQLITE_BUSY`, and phase-2-scale lists
  "any `database is locked`" as the Postgres trigger — but a trigger is not a
  defense. `PRAGMA busy_timeout=5000` in `_connect()` is one line and
  absorbs essentially all real beta-cohort contention.
- **P2 — GET endpoints are never rate-limited.** `_rate_ok()` runs only in
  `_dispatch_post` (`server/handlers.py:707`). `/world` rebuilds and
  serializes the full tree per hit; `/agent` takes a client-supplied
  `max_nodes` that is never clamped (`handlers.py:637` —
  `validate_world_params` clamps depth only). An invited tester can pin the
  single VM's CPU without spending a cent of the meticulously guarded API
  budget.
- **P2 — invite keys and registration tokens are plaintext at rest**
  (`migrations/0004:7`, `0012:12`). Everything *derived* from the credential
  is hashed (`actor_identity`, cost buckets); the credential row itself is
  not, so every backup the continuity policy dutifully multiplies is a
  key-ring. Store `sha256(key)`, look up by hash.
- **P2 — moderation is defeated by Unicode homoglyphs.** `_words()`
  (`server/moderation.py:61-64`) strips non-ASCII before matching, so a slur
  written with one Cyrillic vowel matches neither the block tier nor any
  escalation trigger — it enters the permanent chronicle screened by nothing.
  This is not the documented fail-open posture (that covers classifier
  errors); it's a coverage hole in tier 1. NFKC + a confusables fold before
  `_words` closes most of it. Redaction remains the honest backstop either
  way.
- **P3** — second-order prompt injection: recorded player text re-enters
  future `/speak` calls inside the *system* context block
  (`consciousness/__init__.py:1009`) undelimited. Bounded blast radius (no
  tools, 256 tokens, dialogue-only output) but unacknowledged anywhere.
- Nitpicks worth a line each: `escHtml` doesn't escape quotes yet is used in
  attribute contexts (CSP-mitigated, `static/explorer.js:1131,1043`);
  negative `Content-Length` reaches `rfile.read` (`handlers.py:715`);
  `RateLimiter._counts` and `_touch_cache` never evict; control frames accept
  64KB payloads vs RFC's 125 bytes; DB reads happen under `room.lock`
  (`rooms.py:236-242`).

## 4. Covenant compliance — where the map and territory disagree

The covenants mostly hold at their core and fray at exactly the edges a
covenant exists to police:

- **"Failure stays in fiction" is violated at its perimeter.** The WS
  connection cap answers with a literal player-facing 503
  (`handlers.py:874-875`) against CLAUDE.md's flat "No player-facing 503".
  A valid-JSON *array* body, or a non-string puzzle `answer`, 500s through
  the catch-all (confirmed by execution). "rate limited — slow down",
  "forbidden", and "payload too large" are rendered verbatim in the
  explorer's speak/puzzle panels (`explorer.js:449,591`); `/image` 200s carry
  "FAL_KEY not set" and raw fal.ai exception text (`handlers.py:1079,1109`).
  None of these are stack traces; all of them are out of fiction.
- **The seal gates only movement.** `seal_check` is consulted by WS `move`
  and CLI descend, nothing else — from outside a sealed subtree you can
  `/act` on, `/speak` to, `/image`, and solve the puzzles of every node
  inside it, and `/world` ships the sealed subtree's full contents. Also the
  inverse-imprisonment edge: server position resets to root on reconnect
  (`handlers.py:908-910`), so a player standing legitimately inside a seal
  who disconnects is locked *out* of their own position until someone
  re-solves — untested, and silently divergent between the client's view and
  the server's ledger. "The seal never imprisons" holds; "every client meets
  the same doors" (`gates.py:24-25`) holds only for the movement ledger.
- **The blur covenant is contradicted by the shipped UI.** The travelers
  panel renders humans "◈" teal and agents "✦" gold with persona tags
  (`TextPanel.jsx:100-114`, `explorer.js:766-767`), and `Interact.jsx`
  routes presences to `/agent/voice` vs `/speak` by type. The 2026-07-04
  evaluation flagged "the presentation layer un-blurs what the ledger
  blurred" — and the travelers panel shipped *after* that finding. The
  chronicle/ledger blurs beautifully; live presence taxonomizes
  authoritatively. Either the covenant should be re-scoped in CLAUDE.md to
  "the chronicle blurs; live presence may not" (which is what the code
  believes) or the panel is a standing violation. Pick one in writing.
- **"Redaction is the *sole* sanctioned exception" is overstated.** Pruning
  (`prune_mutations`) and whole-DB restore are two more write paths; the
  prune double-gate lives only on the env/init path while the function
  itself is ungated and its docstring invites direct calls
  (`persistence/__init__.py:840-842`). Migration 0009 also contains literal
  `UPDATE` backfills (self-documented, pre-production — but the covenant
  text doesn't carve them out). And CLAUDE.md's continuity list protects a
  **`node_interactions` table that does not exist** in any migration — the
  standing map names phantom territory.
- Two live mechanical edges: agent PUZZLE_SOLVED rows *do* count toward the
  re-arm epoch condition (`causality/wiring.py:73-77`), so ambient agents
  churn the puzzle content humans face even though they can't claim
  progress; and CLI solves are recorded with `player_name=None` and **no
  agent flag**, so an anonymous terminal solve opens seals for everyone —
  the one hole in the no-anonymous-progress story. Constellations are also
  never checked on CLI or entangled-twin solves, so a completing solve via
  those routes doesn't light the constellation.

## 5. Continuity: the freeze has two unpinned durable-history surfaces

- **Renewal-epoch puzzles.** Solved-state rehydration keys on the puzzle
  NAME including "· Renewal N" (`puzzles/generators.py:826-829`), but the
  freeze deliberately pins only epoch 0. A post-launch edit to the epoch>0
  branch (`generators.py:770-773`) or any family generator would rename
  renewed nodes' puzzles and silently reset their solved state — with every
  freeze test green. This is the same failure class the epoch-0 pin was
  built to prevent, one epoch later.
- **Verb overlay keys.** The overlay property names verbs write ("warded",
  "inscriptions", …) are unpinned; renaming one strands existing overlay
  rows.
- Lesser: `requires-python = ">=3.11"` is a floor where the contract says
  pin (the digests would catch drift loudly, but the metadata undersells);
  the heartbeat runs on an unseeded `random.Random()`
  (`server/heartbeat.py:247`) — legitimate scheduling entropy by the
  contract's own scoping, but it is the one entropy source feeding durable
  chronicle rows, and worth recording as a deliberate choice; FSM agents
  build the epoch-0 puzzle regardless of renewal (`agents/agent.py:74`), so
  post-renewal they roll against a puzzle that no longer exists.

## 6. Consistency: the documentation drift census

Measured against code on 2026-07-18. The pattern is uniform: the CHANGELOG
is nearly always right, and every document downstream of it is stale
somewhere.

- **README** (the most-read file): the Architecture §Frontend paragraph has
  the two clients **swapped** — "`static/app/` is a vanilla D3 tree
  explorer" is false (it's the built React bundle; the explorer is
  `static/explorer.js` at `/`), contradicting the README's own correct
  "Frontends: which is which" row. "across a full 3000-node world" is the
  pre-reshape figure (canonical world: 4,439, pinned in the freeze test).
  "both feature-complete … observe" — `/app` has no observe mode (no
  `/observe` reference anywhere in `frontend/src`). And §Agents still sells "Claude-powered entities"
  while the matrix's own heartbeat row says "FSM-driven — zero API spend";
  `agents/` contains no Anthropic call. The beta-brief's phrase
  "Claude-adjacent" is the honest one; the README never adopted it.
- **`docs/architecture/overview.md`** is the quietly rotten doc: the
  client swap appears twice (:91, :98), the REST list is missing `/act`,
  `/chronicle`, `/position`, `/client-error`, `/register`, and the data-flow
  diagram promises "Encounter agent → Claude-powered exchange" (banter is
  deterministic, zero API — by design).
- **`docs/pitch/beta-brief.md`** asserts "Nothing in this table is
  aspirational … re-verified against the code" and then ships 705/46 test
  counts (real: 750/69), a dead line reference (`handlers.py:719-721` no
  longer contains the 404 it cites), and "the four named test files" above a
  table naming six. The certainty of the framing outlived its verification
  by about a week.
- **ADR-001** neither predicts nor justifies the actual primary client (the
  D3 explorer appears nowhere in it, not even as a rejected alternative),
  and two of its Revisit-when triggers have arguably fired without a
  recorded revisit: WS fragmentation/backpressure (hand-built in the RFC
  6455 batch instead of triggering the prescribed FastAPI migration) and
  "authentication/session management beyond presence" (per-user keys,
  registered names, tokens, cross-device positions — all shipped).
  `stack.md`'s "~55 lines" for protocol.py is now 138.
- **ADR-002** still says the seventh style-matrix row "waits on ripple_score
  being mutated" and persisted ripple "remains a future enhancement" — both
  false since the effects/wiring batch; `game-design.md` correctly says all
  seven rows are live. ADR-003's acceptance criterion 1 ("no source file
  outside persistence/ imports sqlite3") is violated by
  `scripts/beta_metrics.py:30` with no ADR update, against the ADR's own
  standing instruction. ADR-004 is the clean one: every implemented claim
  verified.
- **`docs/infrastructure/fly-deployment.md`** contradicts itself: §4 says
  96-cap/1GB (correct, matches fly.toml), the fenced fly.toml shows
  512MB/180/200, and the closing cost section asserts "512 MB machine" as
  current fact. The mint-URL contradiction the 2026-07-04 eval flagged in
  the CHANGELOG was fixed *in the CHANGELOG* and survives in two other docs
  (`fly-deployment.md:293`, `phase-2-scale.md:51` — both still say
  `/app?key=…`; code emits `/?key=…`).
- **`phase-2-scale.md`** defers "add per-user budgets" that already shipped
  (`guard.py:64-65`, README-documented) — violating its own "living
  document, edit in place" rule. **`phase-1-beta.md`** still defers animated
  ripples and the full map view to Phase 2; both shipped.
- **The 2026-07-04 addendum** under-claims (recs 2, 9, and half of 8 shipped
  unrecorded) and its "suite is now 700" is a week stale — a frozen
  correction document that itself needs correcting is the clearest possible
  demonstration that point-in-time verification does not compound.
- **CHANGELOG structure**: it claims Keep-a-Changelog form and is actually a
  single ~10-month `[Unreleased]` with duplicate `### Added`/`### Changed`
  headers (lines 9/141/205, 74/88/108/129/179/193), pseudo-sections named
  "(previous release)" living *under* Unreleased, and no dated release since
  2025-09-13. As session-to-session memory it is excellent — the entries'
  arithmetic (test-count deltas) all checks out — but release boundaries are
  unrecoverable and no entry is datable. At 96KB it is also the
  third-largest file in the repo, larger than any source module: the record
  of the work now outweighs any single piece of the work.

## 7. Structure and cohesiveness

- **The two-client tax is real, growing, and under-measured.** Roughly
  350-400 of `static/explorer.js`'s 1,222 lines duplicate `frontend/src`
  logic; the parity tests execute ~45 of them (entry hash, node marks).
  Live drift already exists in the unmeasured remainder: the React client's
  `describeMutation` is missing the `SCALE_ACT` and `AGENT_TALK` cases its
  two sibling copies have (four hand copies exist across `App.jsx:27-44`,
  `explorer.js:263-282`, `Chronicle.jsx:9-27`, `explorer.js:473`); the
  explorer lacks the `locked` badge that `badges.js` has (README:99's
  "parity-tested across clients" covers 5 of 6 rules); and the two clients
  implement sealed-room walk-through by *different mechanisms* (explorer:
  HTTP `correct` response; React: WS `puzzle_solved` broadcast — a
  disconnected-WS React player won't walk through where an explorer player
  would). The 2026-07-04 eval's rec 8 said "pick one client"; the repo
  explicitly chose both, which is defensible — but it then owes itself the
  parity harness it only 15%-built.
- **`server/handlers.py` is 1,642 lines** and carries routing, auth
  glue, WS session loop, co-op, constellations, entanglement, and every
  endpoint. The module split (`protocol`/`rooms`/`guard`) was done once in
  the project's youth and never revisited; handlers has since tripled.
- **CI has no linter and no type-checker.** For a repo whose method is
  "fresh session per PR, rules in CLAUDE.md," mechanical enforcement is
  cheap insurance against the exact class of drift this document catalogs.
  `ruff` alone would be a one-file addition.
- **Easter-egg sprawl**: `puzzles/easter-eggs/konami.js` is byte-identical
  to the served `static/easter-egg/konami.js`; a third reworded Konami
  implementation lives inline in `explorer.js:1208-1222`; the
  `optical-illusion.html` pair differs by two characters. Nothing tests the
  lockbox chain. Harmless, but it's the duplication pattern in miniature.
- **Identity**: the 2026-07-04 eval called the codebase "three projects"
  (game engine / simulation / AI experiment). The intervening batches
  genuinely fused the first two — the world now runs unattended, events
  change substance, consequences travel at world speed, and the scales play
  differently; that critique is answered. The third remains marketing:
  agents are FSM walkers voiced by Claude only when a human dials
  `/agent/voice`. The honest current identity is "a deterministic living
  world with Claude-voiced *places* and hand-authored ambient *characters*"
  — which is a good product, and the README should say it plainly instead
  of "Claude-powered entities."

## 8. The meta-finding

The repo's distinguishing practice — measure, record, verify at write time —
works: it caught the 1024/4096 cache trap, the CSP-dead renderer, the
depth-divergence, and it produced the best CHANGELOG this auditor has read.
The systematic weakness is that **verification is an event, never an
invariant**. Everything verified-once drifts: the brief (7 days), the
addendum (7 days), ADR-002 (weeks), the committed bundle (2 PRs), the README
matrix (every batch). The things that *don't* drift are exactly the things a
machine re-checks on every push: the freeze digests, the behavior suites,
the deploy-config tests. The lesson the repo already half-knows (behavior
tests, not grep tests) generalizes: **claims worth writing down are worth
executing in CI, and prose that can't be executed should say when it was
last true.** A `verified: 2026-07-XX` stamp on the README matrix and brief,
a bundle-freshness CI step, and a ruff pass would convert most of §6 from
recurring toil into impossibility.

---

## 9. Recommendations, ranked by leverage

1. **Rebuild and recommit `static/app`; add a CI freshness gate** (build,
   then `git diff --exit-code static/app`) — or stop committing the bundle.
   Closes the only finding where a shipped PR's claim is currently false.
2. **`PRAGMA busy_timeout=5000`** in `persistence._connect()`. One line;
   defends the current cohort instead of waiting for the Postgres trigger.
3. **Rate-limit expensive GETs and clamp `/agent`'s `max_nodes`**
   (`handlers.py:637`).
4. **NFKC-normalize + confusables-fold moderation input** before `_words`.
5. **Hash invite keys and registration tokens at rest**; look up by digest.
6. **Pin renewal-epoch puzzle generation** (digest a sample of epoch-1/2
   puzzles across the reference world) and the verb overlay key names.
7. **One doc-drift sweep** killing §6's list: README client-swap +
   3000→4,439 + agent phrasing, overview.md (client swap ×2, REST list,
   data-flow), beta-brief counts/line-ref, ADR-001 revisit note, ADR-002
   ripple paragraphs, fly-deployment fenced-toml + cost section + mint URL,
   phase-2-scale mint URL + shipped sub-caps, phase-1-beta deferred list,
   eval-addendum shipped-recs list. Then add "last verified" dates to the
   README matrix and the brief.
8. **Re-scope two covenants in CLAUDE.md to what the code actually
   believes**: (a) fiction — either author in-fiction lines for 429/403/413/
   WS-cap/image-failure paths and fix the array-body/non-string-answer 500s,
   or scope the covenant to AI paths explicitly; (b) blur — "the chronicle
   blurs; live presence may taxonomize," or change the travelers panel.
   Also: name prune/restore as sanctioned exceptions alongside redaction,
   delete the phantom `node_interactions` reference, and decide whether CLI
   anonymous solves should open seals.
9. **Cut a dated release in the CHANGELOG** (the launch is the natural
   boundary) and start stamping sections; fix the duplicate headers.
10. **Add ruff (and optionally mypy) to CI.**

## 10. Irreversibility check (house rule)

This PR adds one evaluation document and one CHANGELOG entry. It re-pins no
golden world, adds no migration, and adds no `world_mutations` write path —
none, verified by the diff being docs-only.
