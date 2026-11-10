# ADR-038: A deployment puzzle salt, so the hosted world has no offline answer table

**Status:** Proposed, 2026-11-10. **Owner:** Mark Weeks. Not ratified; it
writes no code, sets no secret, and authorizes no implementation, deployment
or merge. Cited ranges were read at `e8081c0`. Claims are *executed* (scratch
probes, described where they are used, nothing committed), *read*, or
*inferred*.

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
- The Causal Augury's content draw: `sha256(f"augury-content:{level}:{name}:{epoch}")`
  (`puzzles/generators.py:1166-1168`).
- Difficulty and Augury election: `sha256(f"difficulty:…")` and
  `sha256(f"augury-election:…")` (`:65-75`, `:988-991`).

Node names are public: every player reads the name of the place they stand
in. The seed is public too, because `/world` serves it
(`server/handlers.py:139`, `:168`). A different seed would give the world
different node names. The answer would then follow from those names exactly
as it follows from 382's today.

**2. Every answer of the hosted world can be computed offline today**
(read). The repository's own continuity test computes all 4,208 epoch-0
answers of seed 382 from public code (`tests/test_continuity_freeze.py:206-212`,
`_REF_SEED = 382` at `:67`), and the repository is public. Anyone can write
a complete answer table without touching the server, publish it once, and
everyone can use it.

**3. Puzzles become permanent from the first heartbeat tick** (read).
`puzzles/instances.py:46-68` (`get_puzzle`) pins a definition the first time
a puzzle is opened. `persistence/puzzle_content.py:13-17` inserts it with
`ON CONFLICT … DO NOTHING`, and no update path exists. The paths that pin:

- **Ambient agents.** They pin with no player present. The heartbeat is on
  unless `NESTED_WORLDS_HEARTBEAT=0` (`server/__init__.py:207-208`). Its
  agents are built without `pin_puzzles` (`server/heartbeat.py:355`), and
  that flag defaults to `True` (`agents/agent.py:44`). Each attempt calls
  `get_puzzle` (`:87-88`).
- **Players opening a puzzle.** `GET /puzzle` pins
  (`server/handlers.py:1929`).
- **Sealed rooms and entangled twins.** `puzzles/gates.py:85` and
  `server/world_mechanics.py:134` pin.

A pinned definition outlives any later change to the generator, a salt
included, until its node renews. The CHANGELOG records that no production
release has been cut and the hosted world is not deployed
(`docs/CHANGELOG.md:3-9`), so the window is still open.

**4. What a salt can hide, measured** (executed). A scratch prototype keyed
the three content draws in finding 1 with HMAC-SHA256 under a test salt. It
left difficulty and Augury election unkeyed, then rebuilt seed 382's 4,208
epoch-0 puzzles. Under three different test salts, **571, 584 and 574**
answers (13.6–13.9%) came out the same as the unkeyed answer. Those answers
depend on no random draw at all. The salt changes only how their question is
worded. Breakdown under the first test salt:

| Family (ecology-gate name) | Puzzles | Same answer with the salt |
|---|---:|---:|
| `causal_augury` | 396 | 321 (81.1%) |
| `sealed_lock` | 140 | 48 (34.3%) |
| `lineage` | 282 | 81 (28.7%) |
| `bond` | 250 | 30 (12.0%) |
| `keeper_witness` | 806 | 74 (9.2%) |
| `numeric_pattern` | 516 | 12 (2.3%) |
| `anagram` | 515 | 4 (0.8%) |
| `ancestral_compass` | 796 | 4 (0.5%) |
| `cipher`, `handwritten`, `enfold` | 507 | 0 |
| **Total** | **4,208** | **574 (13.6%)** |

The Augury's answer is the engine's own forecast
(`puzzles/generators.py:940-946`), so it stays computable from public code
and served state whatever is salted.

**5. What no salt can hide** (read and executed). Once a puzzle's prompt is
served, every family can be solved mechanically from the prompt, the public
code and the served world:

- **World-reading families: 65.6% of puzzles** (executed, `puzzles/quality.py`
  audit of seed 382: `world_reading_family_ratio` 0.6561). Their answers
  are property values of the node's ancestors, which `/world` serves, or the
  Augury's forecast.
- **Anagrams.** All 496 anagram answers in seed 382 are words in the
  public word banks (executed census).
- **Riddles.** All 47 riddle answers are in the public pool,
  `puzzles/data.py` (executed census).
- **Ciphers.** Caesar shifts of 1 to 9 (`puzzles/generators.py:390-397`).
- **Sequences.** Rules a solver can infer from the public rule set
  (inferred).

`GET /puzzle` serves any born place's prompt by name, not only the place
where the player stands (`server/handlers.py:146-162`, `:1910-1930`). It sits
behind the invite gate when the gate is on (`:575-599`), and reads are
limited to 120 a minute per address by default (`server/guard.py:536-538`).
One invited key can therefore fetch every prompt in about 35 minutes
(inferred: 4,208 ÷ 120).

**6. Competitive integrity is already assigned elsewhere** (read).
ADR-017 (Proposed) handles automation with opportunity and attempt budgets
applied server-side. It warns: "Do not assume automation or linked accounts
can always be detected" (`docs/decisions/ADR-017-multidimensional-leaderboards.md:105-127`).

**Conclusion.**
- A non-public seed changes nothing about answer secrecy.
- A salt is a speed bump that leaves a name on the request, not secrecy.
- **What the salt removes:** the anonymous route to a complete answer table
  that needs no request at all. It covers about 86% of epoch-0 answers and
  every renewal draw.
- **What the salt adds:** an invited key is needed to spoil, and a crawl
  that can be seen in the logs.
- **What it does not stop:** an invited player with a script.
- **What it never hides:** the ~14% of answers the world itself determines.

## Decision

Proposed. Every item below waits on the owner's answer to open question 1.

### D1. Keep seed 382

The hosted world stays on seed 382, as `fly.toml:20` already sets and
`server/guard.py:145-164` falls back to. 382 is the world the continuity pins
and the puzzle ecology gate certify (`tests/test_puzzle_quality.py:192-202`
asserts 4,208 puzzles for it). It is also the staging twin's world, and the
reference for ADR-036's band measurements and the runbooks. Another seed
would need its own curation and certification and would buy no secrecy
(findings 1–2).

### D2. Salt the three content draws, and nothing else

With a salt configured, the three content draws in finding 1 use
`HMAC-SHA256(salt, <the existing domain string>)` in place of
`sha256(<domain string>)`. They take the first 8 bytes big-endian, as today.
The domain strings do not change.

**Left unkeyed on purpose:**
- **`node_difficulty`.** Difficulty is a trait of the node that players are
  shown as stars (`frontend/src/components/Interact.jsx:227-229`), and the
  agent success odds read it (`agents/agent.py:97`).
- **`_augury_elected`.** It keeps ADR-010's ~10% election, the share the
  ecology gate was tuned against. Keying it hides nothing once a player sees
  the prompt.
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

### D4. A marked deployment refuses to run without a salt

`canonical_seed()` falls back to 382 when unset, so a hosted deployment
cannot be told apart from local play by its seed. A non-secret marker,
`NESTED_WORLDS_PUZZLE_SALT_REQUIRED = "1"`, goes in `fly.toml`'s `[env]`.

**With the marker set**, a missing salt, or one shorter than 32 characters:
- the accessor raises;
- the server exits before the heartbeat starts, with a plain operator error.
  This is a transport-level refusal outside the fiction; no player can reach
  it.

So no path on a marked machine can pin an unsalted puzzle. On the first
deploy, `scripts/deploy.sh` also checks that `fly secrets list` names the
salt.

### D5. Staging and production get different salts

`enfolded-staging` and `enfolded-beta` each hold their own salt; local QA
homes hold none.

- **The cost:** staging serves different puzzle content at the same places.
  The twin rehearses mechanics, not answers.
- **The gain:** staging testers, staging backups and staging operators never
  hold production answers. (Default to veto.)

### D6. Losing or rotating the salt costs no continuity

Pinned definitions are the authority: `get_puzzle` reads the pinned row
first (`puzzles/instances.py:47-49`). So a new salt changes only puzzles not
yet pinned. A lost salt is replaced, and a suspected leak is answered by
rotation. A leak costs only the secrecy the salt bought, for the puzzles
pinned under it.

**The secret's lifecycle:**
- **Generation:** `openssl rand -hex 32`.
- **Before the first boot:** staged with `fly secrets set --stage`, the
  flow `docs/infrastructure/fly-deployment.md:1110-1125` describes.
- **Backups:** no copy needed. The backups carry the pinned definitions,
  which are the world's puzzles.

### D7. The ecology gate certifies salted worlds too

The gate (`puzzles/quality.py:40-51`) certifies the unsalted world.
Production would serve a salted one.

**Measured under three test salts** (executed), the gate passes with margin
on every metric:

| Metric | Limit | Under the test salts |
|---|---|---|
| decode-family ratio | ≤ 0.50 | 0.356–0.358 |
| world-reading ratio | ≥ 0.55 | 0.637–0.639 |
| largest family | ≤ 0.25 | 0.191–0.197 |
| unique prompts | ≥ 0.99 | ≥ 0.998 |
| unique answers | ≥ 0.45 | 0.535–0.548 |
| families | — | 11 |
| kinds | — | 9 |

**Checks:**
- CI runs the gate under fixed test salts.
- Before staging the production salt, the operator runs the audit with it
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
- `main.py puzzle-audit`;
- the D8 clause, once approved;
- the `fly-deployment.md` steps;
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
  error.

**B2 — operations, before `scripts/deploy.sh --first-deploy` on production:**
1. Draw each salt and audit it.
2. Stage both secrets.
3. Deploy an image that contains B1.

Production must never be restored from a staging or QA backup. Their pins
are unsalted, and a restore would bring them into the canonical chronicle.

## Open questions for the owner

1. **Should the hosted world get a puzzle salt before its first boot?**
   *Recommended: yes.*
   - **Adopting can be undone:** unset the salt later, and future pins are
     unsalted while nothing stored changes.
   - **Declining cannot be undone** for every puzzle pinned while it holds,
     and the heartbeat starts pinning at the first tick (finding 3).
   - **The cost is one small PR and one secret.**
   - **What it buys is limited.** It ends the anonymous, zero-request answer
     table for about 86% of epoch-0 answers. It does not stop an invited
     player with a script (finding 5).
   - **When declining is reasonable:** if the world will stay a private,
     invite-only pilot with no standings. The pilot and the launch share one
     world (ADR-007; the DB is never wiped between cohorts), so pilot-era
     pins would carry into the launch.
2. **Different salts for staging and production?** *Recommended: different
   (D5).*
3. **Approve the D8 wording** for `AGENTS.md`. This needs approval, not
   only a veto.

**Defaults for the owner to veto:**
- a marked deployment refuses to run without a salt of 32 or more characters
  (D4);
- difficulty and Augury election stay unkeyed (D2);
- the operator audits the production salt once before staging it (D7);
- no per-pin record of which salt built a definition (Trade-offs).

## Irreversibility

None for this ADR: it is documentation only. Implementation opens no
migration, rewrites no stored row, changes no birth and needs no golden
re-pin.

**The door is the first production boot.** Puzzles pinned then are pinned
with or without a salt, permanently, until their node renews. That door is
already recorded as the launch's one-way door
(`docs/evaluation/2026-11-06-next-build.md`). This ADR adds one condition to
it: B1 and B2 must come before it.

## Trade-offs accepted

- **The certified world is not the served world.** Production's puzzles
  differ from the world the continuity pins and the ecology gate describe.
  D7's CI runs and operator audit cover the gap.
- **No reproduction from the repository.** A developer cannot rebuild a
  production puzzle from the repository alone and reads its pinned
  definition (`puzzle_instances`) instead. No pin records which salt built
  it. An operator who needs to know rebuilds the puzzle with the salt and
  compares.
- **Staging's puzzle content is not production's** (D5).
- **About 14% of epoch-0 answers stay offline-computable** (finding 4).
  Every answer stays mechanically solvable once its prompt is served
  (finding 5).
- **A missing secret now stops a deploy.** That is intended.

## Revisit when

- **Standings or any reward with value outside the game ship** (ADR-017).
  A speed bump is not enough then. The next levers are prompts served only
  where the player stands, per-player attempt budgets, or families a script
  cannot solve from served state.
- **The invite gate is removed.** Attribution weakens.
- **A salt leak is suspected.** Rotate (D6).
- **A puzzle family changes how its answer is drawn**, or ADR-015/ADR-036
  change what is served. Re-measure finding 4 and D7.
- **Production is ever restored from a non-production backup.**

## Rejected alternatives

- **A non-public production seed.** The seed enters no puzzle draw, and
  `/world` serves it (finding 1). It would cost 382's curation and
  certification, the staging twin's parity, and every 382-keyed measurement
  and runbook, for no secrecy.
- **Fresh entropy when a puzzle is first pinned.** Pinning would make the
  content durable, but this breaks the determinism contract's no-entropy
  rule and the tests' reproducibility. A keyed draw gives the same secrecy
  deterministically.
- **Keying difficulty and Augury election as well.** Difficulty is a trait
  players are shown, and the agent odds read it. A keyed election moves
  which nodes serve the Augury without hiding anything a prompt shows, and
  enlarges the change to ADR-010's gated share. The Augury's answers stay
  determined by the world either way.
- **Moving word banks and riddle pools out of the public repository.** This
  covers anagrams and riddles, about 13% of puzzles. It does nothing for the
  world-reading 66%. It cuts against ADR-023's open repository and the
  curation workflow.
- **Salting by concatenating into the `sha256` input.** It works in practice
  for this use. HMAC is the standard keyed construction and costs nothing
  more.
