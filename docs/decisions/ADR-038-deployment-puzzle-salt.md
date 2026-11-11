# ADR-038: A deployment puzzle salt, so the hosted world has no offline answer table

**Status:** Proposed, 2026-11-10; revised 2026-11-11 after an adversarial
check of `7482379`. **Owner:** Mark Weeks. Not ratified; it writes no code,
sets no secret, and authorizes no implementation, deployment or merge. Cited
ranges were read at `e8081c0`. Claims are *executed*, *read* or *inferred*.
The executed measurements, with their source, salts and outputs, are in the
[salt-probe record](../evaluation/2026-11-11-puzzle-salt-probes.md).

## Context

**The question.** Before the first production boot, should the hosted world
move from seed 382 to a seed nobody outside the operator knows, so that
puzzle answers cannot be computed from the public repository? Both "switch to
a non-public seed" and "keep 382" were recommended in the 2026-11-10 session.
The owner asked for one decision.

**1. The seed is not an input to any puzzle** (read). Puzzle content is
drawn from the node's level and name. Neither the seed nor the world's other
properties seed the draw:

- `node_rng`, the epoch-0 content draw: `sha256(f"{level}:{name}")`
  (`puzzles/generators.py:245-254`).
- The renewal draw: `sha256(f"{level}:{name}:renewal:{epoch}")`
  (`puzzles/generators.py:1142-1145`).
- The Causal Augury's content draw:
  `sha256(f"augury-content:{level}:{name}:{epoch}")`
  (`puzzles/generators.py:1166-1168`).
- Difficulty and Augury election: `sha256(f"difficulty:…")` and
  `sha256(f"augury-election:…")` (`:65-75`, `:988-991`).

Node names are public: every player reads the name of the place they stand
in. A different seed would give the world different node names, and the
answers would follow from those names as they follow from 382's today. The
seed itself is in the `/world` payload (`server/handlers.py:1079-1089`),
which every client reads.

**2. Every answer of the world as born can be computed offline today**
(read). The repository's own continuity test computes all 4,208 epoch-0
answers of seed 382 from public code (`tests/test_continuity_freeze.py:206-212`,
`_REF_SEED = 382` at `:67`), and the repository is public. Anyone can write
a complete answer table without touching the server, publish it once, and
everyone can use it. The table describes the born world. A puzzle is pinned
from the live node, overlays applied (`puzzles/instances.py:24-37`, `:50-57`),
so a world-reading puzzle first opened after players change its evidence
(a Region's terrain or weather, a Molecule's geometry) follows the changed
properties instead. Every other puzzle matches the table.

**3. Puzzles become permanent from the first heartbeat tick** (read).
`puzzles/instances.py:46-68` (`get_puzzle`) pins a definition the first time
a puzzle is opened. `persistence/puzzle_content.py:13-17` inserts it with
`ON CONFLICT … DO NOTHING`, and no update path exists. Among the paths that
pin:

- **The cast's seal check.** As agents walk, the heartbeat's `_accessible`
  pins the puzzle of each sealing Room they pass (`server/heartbeat.py:239-252`,
  called at `:421`, `:439` and `:513`). No player needs to be present. The
  heartbeat is on unless `NESTED_WORLDS_HEARTBEAT=0`
  (`server/__init__.py:207-208`). This is the path the 2026-11-06 record
  names, and it remains if ADR-036 D5 ends ambient attempts.
- **Ambient attempts.** Heartbeat agents are built without `pin_puzzles`
  (`server/heartbeat.py:355`), the flag defaults to `True`
  (`agents/agent.py:44`), and each attempt calls `get_puzzle` (`:87-88`).
- **Players.** `GET /puzzle` (`server/handlers.py:1929`), `POST
  /puzzle/attempt` (`:2097`) and the evidence page every puzzle panel links
  to (`:1887`).
- **Sealed rooms on player moves** (`puzzles/gates.py:85`) and **entangled
  twins on a solve** (`server/world_mechanics.py:134`, called from
  `server/handlers.py:2147`).
- **The CLI.** `main.py:77`, `interface/__init__.py:174`.

A pinned definition outlives any later change to the generator, a salt
included, until its node renews. The CHANGELOG records that no production
release has been cut and the hosted world is not deployed
(`docs/CHANGELOG.md:3-9`), so the window is still open.

**4. What a salt hides offline, measured** (executed). The probe prototypes
D2: the three content draws in finding 1 become HMAC-SHA256 under a salt,
while difficulty and Augury election stay unkeyed. It rebuilds seed 382's
4,208 epoch-0 puzzles under 3 deployment salts and 100 attacker salts, and
scores an attacker who never sees a deployment salt.

| Offline, zero requests | Right for (3 deployment salts) |
|---|---:|
| The unsalted answer, as published today | 575–593 (13.7–14.1%) |
| The attacker's most frequent answer over 100 salts of their own | 975–1,031 (23.2–24.5%) |
| The attacker's top answers, as many as the node's attempt budget | 1,563–1,647 (37.1–39.1%) |
| An answer that is the same under every one of the 103 salts | 242 (5.75%) |

- **Most matches are chance.** The family draw and each family's own draws
  are keyed, so each salt matches a different set. A sealed lock picks one of
  three keys (`puzzles/generators.py:508`, `:893-898`), so roughly one lock
  in three matches the unsalted answer under any one salt (39 of 140 under
  the first test salt).
- **What no draw reaches.** The 242 answers that never change are all Causal
  Augury nodes with a single valid question form: every 1-star Augury and
  most 3- and 4-star ones (94, 6, 78 and 64 at difficulty 1 to 4). Where two forms
  are valid, the keyed draw picks one (`:1029-1030`). Election is unkeyed
  (D2), so which nodes serve the Augury is public.
- **Small candidate sets fit the attempt budget.** Each node's attempt budget
  follows its unkeyed difficulty (3 to 5). Within that budget the attacker's
  list holds the deployed answer for every sealed lock (140 of 140), every
  Augury (396 of 396) and every lineage, nearly every bond, 50–56% of keeper
  witnesses and 15–17% of numeric patterns. It holds almost no anagram,
  cipher, compass or hand-written pool answers: at most 9, 0, 6 and 1, of roughly 500,
  430, 825 and 50 puzzles.

**The salt therefore keeps about 61–63% of epoch-0 answers off any
zero-request list that fits the attempt budget, and about 76–77% off a
one-answer-per-node table.** Renewals draw the same way at each epoch
(inferred; the probe measures epoch 0).

**5. What no salt hides** (read and executed). Once a puzzle's prompt is
served, every family can be solved mechanically from the prompt, the public
code and the served world:

- **World-reading families: 65.6% of puzzles** (executed, `puzzles/quality.py`
  audit of seed 382: `world_reading_family_ratio` 0.6561). Their answers are
  read or derived from served state: ancestors' property values, or letters
  of them, and living names, the node's own name, or the Augury's forecast.
- **Anagrams.** All 496 anagram answers in seed 382 are words in the
  public word banks (executed).
- **The hand-written pool.** All 47 of its answers in seed 382 (24 riddles,
  the rest anagrams, patterns, sequences, navigation and one cipher) are in
  the public pools, `puzzles/data.py` (executed).
- **Ciphers.** Caesar shifts of 1 to 9 (`puzzles/generators.py:390-397`).
- **Sequences.** Rules a solver can infer from the public rule set
  (inferred).

**And no script is needed to get any single answer** (read). Once a node's
pooled 3–5 attempts are spent, every later wrong guess returns the answer
(`server/handlers.py:2173`, `:2228`). Both clients print it
(`frontend/src/components/Interact.jsx:259`, `static/explorer.js:995`), and a
correct guess after that still solves: attempts keep counting with no cap,
and a correct one claims the solve (`server/rooms.py:351-357`). ADR-036
records this as F10 and removes it in its batch 1a. Until then it is the
cheapest spoiler for any one puzzle, salt or no salt.

**Crawling is bounded per address, not per key** (read). `GET /puzzle`
serves any born place's prompt by name, not only the place where the player
stands (`server/handlers.py:146-162`, `:1910-1930`). It sits behind the
invite gate when the gate is on (`:575-599`). Reads are limited to 120 a
minute per address by default (`server/guard.py:536-538`), so one address
fetches every prompt in about 35 minutes (inferred: 4,208 ÷ 120). Several
addresses go faster. The access log records a hashed address, the path
without its query, and the status (`server/observability.py:325-341`). No
stored record ties a prompt read to an invite key.

**6. Competitive integrity is already assigned elsewhere** (read).
ADR-017 (Proposed) handles automation with opportunity and attempt budgets
applied server-side. It warns: "Do not assume automation or linked accounts
can always be detected" (`docs/decisions/ADR-017-multidimensional-leaderboards.md:105-127`).

**Conclusion.**
- **A non-public seed protects nothing for long.** Behind the invite gate it
  would hold only until any invited client's first `/world` read. That read
  serves the seed, and the exact table for all 4,208 nodes follows offline.
- **A salt is a speed bump that needs an invited key, not secrecy.** It is
  never served, so an exact table needs every prompt fetched.
- **What the salt removes:** the anonymous, zero-request route to most
  answers: about 61–63% of epoch-0 answers against a list that fits each
  node's attempt budget, and about 76–77% against a one-answer table.
- **What it does not stop:**
  - an invited player with a script (finding 5);
  - the answer release, until ADR-036 batch 1a;
  - offline lists for families with small candidate sets: every sealed lock,
    lineage and Augury, and nearly every bond.

## Decision

Proposed. D1 stands either way. D2 to D8 apply only if open question 1 is
answered yes.

### D1. Keep seed 382

The hosted world stays on seed 382, as `fly.toml:20` already sets and
`server/guard.py:145-164` falls back to. ADR-007 chose it as the top-scoring
candidate of a 512-seed quality census
(`docs/evaluation/2026-08-03-launch-world-census.md`). It is the world the continuity pins
and the puzzle ecology gate certify (`tests/test_puzzle_quality.py:192-202`
asserts 4,208 puzzles for it). It is also the staging twin's world, and the
reference for ADR-036's band measurements and the runbooks. Another seed
would need its own curation and certification, and would buy only the
protection the Conclusion describes, until the first `/world` read.

### D2. Salt the three content draws, and nothing else

With a salt configured, the three content draws in finding 1 use
`HMAC-SHA256(salt, <the existing domain string>)` in place of
`sha256(<domain string>)`. They take the first 8 bytes big-endian, as today.
The domain strings do not change.

**Left unkeyed on purpose:**
- **`node_difficulty`.** Difficulty is a trait of the node that players are
  shown as stars (`frontend/src/components/Interact.jsx:227-229`), and the
  agent success odds read it (`agents/agent.py:97`).
- **`_augury_elected`.** This keeps ADR-010's per-node placement of the ~10%
  Augury share, the share the ecology gate was tuned against. The cost is the
  242 Augury answers that no draw reaches (finding 4). Keying the election
  too would remove those, but lowers the budget-sized list only from
  37.1–39.1% to 33.5–35.3% (Rejected alternatives).
- **`node_rng` in `puzzles/engine.py:36`.** That fallback serves only
  non-canonical test levels.
- **World birth.** `world_nodes`, names and properties are untouched.

**With no salt, or an empty one,** the code takes today's `sha256` path,
byte-identical. The continuity pins, local play, the CLI, tests and local
multi-world mode are unchanged. `GENERATOR_VERSION` does not move and nothing
is re-pinned.

### D3. One accessor feeds every build path, and nothing ever serves the salt

A single accessor reads `NESTED_WORLDS_PUZZLE_SALT` once. Every caller of
`build_puzzle` goes through it:

- `puzzles/instances.py:43`, `peek_puzzle`. Its unpinned progress checks
  must agree with what `get_puzzle` will pin.
- `puzzles/instances.py:57`, `get_puzzle`.
- `agents/agent.py:86`.
- `server/heartbeat.py:251`.
- `puzzles/engine.py:33`.
- `puzzles/quality.py:154`.
- `scripts/pitch_capture_server.py:37`, a local tool that normally runs
  without a salt.

**Never exposed:** the salt never appears in a served payload, log line,
error, chronicle row, evidence page, model prompt or Sentry event.

**Sentry needs one setting for that** (executed). `sentry_sdk.init` sets no
`include_local_variables` (`server/observability.py:58-62`), and the pinned
SDK (2.66.1) defaults it to true. Under those options, a capture test sent
the salt from an exception raised after a keyed draw. It also sent a
`Puzzle`'s answer from an exception in a frame that held the puzzle, which
is an exposure today, operator-side, to the operator's own Sentry. With
`include_local_variables=False` the same test sent neither. B1 sets it. (The
SDK also sends the source lines around each frame by default, which matters
only for a value written literally in the code; salts and generated answers
are not.)

### D4. A marked deployment refuses to run without a salt

`canonical_seed()` falls back to 382 when unset, so a hosted deployment
cannot be told apart from local play by its seed. A non-secret marker,
`NESTED_WORLDS_PUZZLE_SALT_REQUIRED = "1"`, goes in `fly.toml`'s `[env]`.

**With the marker set**, a missing salt, or one shorter than 32 characters:
- the accessor raises;
- the server exits before its port opens and before the heartbeat starts,
  with a plain operator error. This matches the existing schema, model and
  budget refusals in `server.run` (`server/__init__.py:159-204`). No
  player-facing surface exists yet to carry it, so the fiction covenant does
  not apply.

So no path on a marked machine can pin an unsalted puzzle. On the first
deploy, `scripts/deploy.sh` also checks that `fly secrets list` names the
salt.

**The staging rehearsal is affected.** It deploys the committed `fly.toml`
(`docs/infrastructure/fly-deployment.md:287-288`), so the marker applies
there too. Its runbook sets secrets at step 6 (`:321`), after the first
deploy at step 4 (`:302-305`). B1 moves the staging salt before step 4.

### D5. Staging and production get different salts

`enfolded-staging` and `enfolded-beta` each hold their own salt; local QA
homes hold none.

- **The cost:** staging serves different puzzle content at most places. The
  twin rehearses mechanics, not answers.
- **The gain:** staging testers, staging backups and staging operators hold
  nothing about production answers beyond what anyone can compute with a
  salt of their own. Two independent salts give the same answer at 575–615
  of 4,208 places (13.7–14.6%, three pairs measured). That is the same chance
  overlap as finding 4, and it includes the 242 Augury answers that are the
  same under every salt.

### D6. Losing or rotating the salt costs no continuity

Pinned definitions are the authority: `get_puzzle` reads the pinned row
first (`puzzles/instances.py:47-49`). So a new salt changes only puzzles not
yet pinned. A lost salt is replaced, and a suspected leak is answered by
rotation. A leak costs only the secrecy the salt bought, for the puzzles
pinned under it.

**The secret's lifecycle:**
- **Generation:** `openssl rand -hex 32`.
- **Before the first boot:** set with the other runtime secrets
  (`docs/infrastructure/fly-deployment.md:224`) before
  `scripts/deploy.sh --first-deploy` (`:244`). On an app that already runs,
  stage a change with `fly secrets set --stage` (`:1110-1113`).
- **Removal, if the salt is ever dropped:** remove the D4 marker from
  `fly.toml` and deploy that first, then unset the secret. Unsetting it alone
  makes a marked server refuse to start.
- **Backups:** no copy of the salt is needed. The backups carry the pinned
  definitions, which are the world's puzzles.

### D7. The ecology gate certifies salted worlds too

The gate (`puzzles/quality.py:40-51`) certifies the unsalted world.
Production would serve a salted one.

**Measured under 103 salts** (executed), every salt passes the gate:

| Metric | Limit | Unsalted | Under 103 salts |
|---|---|---|---|
| decode-family ratio | ≤ 0.50 | 0.337 | 0.332–0.368 |
| world-reading ratio | ≥ 0.55 | 0.656 | 0.626–0.660 |
| largest family | ≤ 0.25 | 0.199 | 0.188–0.211 |
| unique prompts | ≥ 0.99 | 0.9990 | 0.9969–0.9995 |
| unique answers | ≥ 0.45 | 0.541 | 0.524–0.563 |
| families | ≥ 10 | 11 | 11 |
| kinds | ≥ 8 | 9 | 8–9 |

Kinds is the tight metric. It sits at its floor of 8 under 7 of the 103
salts, which still passes.

**ADR-036's band verdicts are unchanged** (executed). That record's band
searchers (`docs/evaluation/2026-11-07-puzzle-band-searchers.md`) were rerun
under two of the test salts. At the 12-miss cap, lineage's typo band names
+51 of 274 (18.6%) and +49 of 287 (17.1%) more than blind search, against
+54 of 301 (17.9%) unsalted and ADR-036's one-fifth bar. Bond and sealed lock
stay at +0, and compass still fails.

**Checks:**
- CI runs the gate under fixed test salts.
- Before setting the production salt, the operator runs the audit with it
  once. A new `python main.py puzzle-audit` command does this.
- A salt that fails the audit is discarded and a new one drawn.

### D8. The determinism contract gains one clause (needs the owner's approval)

`AGENTS.md` "Determinism contract" would read, in its **After birth**
sentence:

> … art/sound/puzzles derive deterministically from the node *as served* —
> puzzle content also from the deployment's puzzle salt (ADR-038), a
> per-deployment constant that is never served — so co-op reproducibility
> and reproducible screenshots follow the served state.

The salt is a constant, not entropy, so the no-entropy rule stands
unchanged. This ADR does not edit `AGENTS.md`.

### Batches

**B1 — one implementation PR:**
- the accessor, the keyed draws and the marked-deployment refusal;
- the `fly.toml` marker and the `deploy.sh` check;
- Sentry's `include_local_variables=False`, or a scrubber for the salt (D3);
- `main.py puzzle-audit`;
- the D8 clause, once approved;
- the `fly-deployment.md` steps, with the staging salt set before staging's
  first deploy (D4);
- one CHANGELOG entry.

**B1 behavior tests:**
- with no salt, every continuity pin stays green unedited;
- under a test salt, puzzles are deterministic and differ from the unsalted
  ones;
- `peek_puzzle` agrees with `get_puzzle`;
- difficulty and election are unchanged;
- the secrecy, solvability and per-node difficulty suites
  (`tests/test_puzzles.py`) pass, parametrized over a test salt;
- the ecology gate passes under the test salts;
- a marked process without a salt refuses to start;
- rotation changes no pinned puzzle and no solve;
- the salt is absent from every served payload, every log line and every
  error;
- an exception raised inside a keyed draw, under a capturing Sentry
  transport, sends no salt.

**B2 — operations, before `scripts/deploy.sh --first-deploy` on production:**
1. Draw each salt and audit it.
2. Set both secrets: staging's before staging's first deploy, production's
   with the first-deploy secrets.
3. Deploy an image that contains B1.

**Never restore production from a staging or QA backup.** Their pins were
built under another salt (staging) or none (QA, and any staging pins from
before B1). Their answers are known outside production, and a restore would
bring them into the canonical chronicle.

## Open questions for the owner

1. **Should the hosted world get a puzzle salt before its first boot?**
   *Recommended: yes, for a modest gain.*
   - **What it buys.** It keeps about 61–63% of epoch-0 answers off any
     zero-request list. It does not stop scripts, the answer release
     (until ADR-036 batch 1a) or small candidate sets (finding 4).
   - **Adopting can be undone for future pins.** Remove the D4 marker and
     deploy, then unset the secret (D6). Pins made under the salt stay as
     stored: readable in `puzzle_instances`, but not reproducible from the
     repository.
   - **Declining cannot be undone** for puzzles pinned while it holds. Their
     answers stay computable offline until their nodes renew, and the
     heartbeat starts pinning at the first tick (finding 3).
   - **The cost is one small PR and one secret.**
   - **When declining is reasonable:** if the world will stay a private,
     invite-only pilot with no standings. Even then, pilot-era pins reach
     the launch whenever the pilot world becomes the launch world. The
     initial hosted release is one canonical world (ADR-007), and the
     continuity policy never wipes the DB between cohorts
     (`docs/roadmap/phase-2-scale.md:226`). Whether the pilot world is
     production or retained research is still a held decision (decision
     packet 2026-11, item 4; `docs/roadmap/beta-launch-checklist.md:279`),
     and a research world "may be kept"
     (`docs/roadmap/decision-packet-2026-11.md:262-263`). So the answer is
     needed before the first production boot either way.
2. **Different salts for staging and production?** *Recommended: different
   (D5).*
3. **Approve the D8 wording** for `AGENTS.md`. This needs approval, not
   only a veto.

**Defaults for the owner to veto:**
- a marked deployment refuses to run without a salt of 32 or more characters
  (D4);
- difficulty and Augury election stay unkeyed (D2);
- Sentry stops sending frame locals (D3);
- the operator audits the production salt once before setting it (D7);
- no per-pin record of which salt built a definition (Trade-offs).

## Irreversibility

None for this ADR: it is documentation only. Implementation opens no
migration, rewrites no stored row, changes no birth and needs no golden
re-pin.

**The door is the first production boot.** Puzzles pinned then are pinned
with or without a salt, permanently, until their node renews. That door is
already recorded as the launch's one-way door
(`docs/evaluation/2026-11-06-next-build.md:53`). This ADR adds one condition
to it: open question 1 must be answered before it. If the salt is adopted,
B1 and B2 must also come before it.

## Trade-offs accepted

- **The certified world is not the served world.** Production's puzzles
  differ from the world the continuity pins and the ecology gate describe.
  D7's CI runs and operator audit cover the gap. ADR-036's band measurements
  also describe the unsalted answers; their verdicts held under two test
  salts (D7).
- **No reproduction from the repository.** A developer cannot rebuild a
  production puzzle from the repository alone and reads its pinned
  definition (`puzzle_instances`) instead. No pin records which salt built
  it. An operator who needs to know rebuilds the puzzle with the salt and
  compares.
- **Staging's puzzle content is not production's** (D5).
- **Offline lists still reach about 37–39% of epoch-0 answers** within their
  attempt budgets, and 242 Augury answers exactly (finding 4). Every answer
  stays mechanically solvable once its prompt is served (finding 5).
- **No read is attributed to a key.** The salt makes spoiling need an
  invited key, but today's logs cannot say which key crawled (finding 5).
- **A missing secret now stops a deploy.** That is intended.

## Revisit when

- **Standings or any reward with value outside the game ship** (ADR-017).
  A speed bump is not enough then. The next levers are:
  - no answer release on failure (ADR-036 batch 1a);
  - prompts served only where the player stands;
  - per-key read attribution and a per-key read budget;
  - per-player attempt budgets;
  - more candidates for the small-set families (a lock has three keys);
  - families a script cannot solve from served state.
- **The invite gate is removed.** Anyone can crawl, and nothing ties a crawl
  to a person.
- **A salt leak is suspected.** Rotate (D6).
- **A puzzle family changes how its answer is drawn**, or ADR-015/ADR-036
  change what is served. Rerun the
  [salt probe](../evaluation/2026-11-11-puzzle-salt-probes.md) and D7. If
  ADR-036 is ratified, run its band searchers and pass bar under the test
  salts too.
- **Production is ever restored from a non-production backup.**

## Rejected alternatives

- **A non-public production seed.** The seed enters no puzzle draw, and
  `/world` serves it (finding 1). Behind the invite gate it would hold only
  until any invited client's first `/world` read, which hands over the whole
  exact table offline. It would cost 382's curation and certification, the
  staging twin's parity, and every 382-keyed measurement and runbook.
- **Fresh entropy when a puzzle is first pinned.** Pinning would make the
  content durable, but this breaks the determinism contract's no-entropy
  rule and the tests' reproducibility. A keyed draw gives the same secrecy
  deterministically.
- **Keying difficulty as well.** Difficulty is a trait players are shown,
  the agent odds read it, and the attempt budget it sets is served with every
  prompt.
- **Keying the Augury election as well** (measured). No answer then
  survives every salt. But the budget-sized list still reaches 1,409–1,486
  answers (33.5–35.3%), against 37.1–39.1% with election unkeyed, and the
  one-answer table 16.9–17.5%. It moves which nodes serve the Augury,
  enlarging the change to ADR-010's gated share, for a gain of about four
  points.
- **Moving word banks and the hand-written pools out of the public
  repository.** This covers anagrams and the hand-written pool, about 13% of
  puzzles, which an offline list
  barely reaches under a salt anyway. It does nothing for the world-reading
  66%. It cuts against ADR-023's open repository and the curation workflow.
- **Salting by concatenating into the `sha256` input.** It works in practice
  for this use. HMAC is the standard keyed construction and costs nothing
  more.
