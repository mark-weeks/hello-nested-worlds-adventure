# ADR-004: Day-One Data Policy

**2026-09-12 identity revision:** [ADR-024](ADR-024-participants-and-active-content.md)
implements the key-rotation revisit trigger. A participant ID owns new profiles,
notes and receipts; explicit credential aliases retain continuity through
operator rotation. The existing actor hashes remain frozen historical facts.
Independently minted accounts are not merged by matching names. The earlier
“new key = new actor” limitation describes the pre-rotation implementation.

**2026-10-25 moderation amendment:** Approved by the owner, Mark Weeks, in
chat on 2026-10-25. This amends §2. Text other players can see fails closed
when moderation cannot complete. Private or solo-only text and mechanical
gameplay stay fail-open. Classification is a task any configured provider may
perform ([ADR-034](ADR-034-provider-and-model-optionality.md)); no provider
is named as the policy. §1 (redaction and break-glass hard delete), the
never-wipe rule, the hosted-restore wording, and the budget bucket names are
unchanged. One sentence in §3 states when the never-wipe covenant starts.
The running screen implements this failure rule. The starting per-user cap
values are configuration recorded with the implementation.

**Status:** Accepted 2026-07-12. §2 amended 2026-10-25, approved by the owner in chat.

---

## Context

Enfolded is a **persistent-memory** world. The chronicle (`world_mutations`) is
append-only and permanent, and it is **load-bearing**: a node's voice, its
generative art, the history that seeds future conversations, and what other
players see are all derived **at read time** from these rows. So "data policy"
here is not back-office plumbing — every choice about what is recorded and how
it can be removed directly shapes the game.

Launch is near, and these policies are being put in place **pre-launch, before
real gameplay begins** — so there is no legacy/migration burden and the record
is correct from the first real row. Several of them were already made and partly
implemented (redaction, presence recording, credential identity, reserved names)
but never written down; this ADR records them and their reasoning, and is
explicit about the places where the *intended* policy is not yet fully built.

This ADR was produced by interviewing the human (the "interview-me" practice in
`CLAUDE.md`), one architecture-changing question at a time.

---

## Decisions

### 1. Append-only chronicle; content-level redaction is the removal mechanism

Rows are never deleted or rewritten. Inappropriate content is removed by
**content-level redaction** (`python main.py redact`, runbook §7): the
human-authored words (message, reply, text, guess, answer_given) are tombstoned
to `[redacted]`; the row, its node, type, timestamp, mechanical fields, and
durable `actor_identity` all survive. `persistence/__init__.py` (redaction
section), `docs/infrastructure/fly-deployment.md` §7.

**Why content-level is the right fit — the crux.** Because voice, art, and
conversation-context are all derived *at read time* from the history text,
tombstoning the words neutralizes their downstream influence **everywhere at
once** (future derivations regenerate from the scrubbed history), while the
content-agnostic mechanical fields (co-op counters, renewal epochs, art activity
counts) stay intact and the **accountability trail** (`actor_identity`, which
lets us identify a repeat abuser and revoke their invite) is preserved.

**Motivation is proactive, not incident-driven:** a permanent-memory world
cannot launch with an *undefined* path for abuse; the mechanism is designed
ahead of the "what if."

**Hard delete is reserved as a narrow, documented break-glass** for a true
"must leave zero trace" case (e.g. a legal erasure), never the default — its
cost is precisely the loss of mechanical integrity and accountability that
content-level redaction avoids.

### 2. Input moderation *(amended 2026-10-25; shared text fails closed)*

Player-authored text is screened before it becomes visible to other players.
The screen covers `/speak`, `/agent/voice`, WebSocket chat, and the player
line of a reply before a chronicle row or a model call; a name before the
registry (`/register`, `invite mint`, `play --name`); a profile bio and
goals when `published` is set (`server/participant_api.py`); Ideas
(`persistence/ideas.py`, local tier first, then the same classifier and
budgets); and the free text of a puzzle attempt when it would be stored in
shared history. Private notes (`/journal/note`) and unpublished profile
text are not screened and do not enter the chronicle. Two tiers,
cheapest first (`server/moderation.py`, `content_screen.py`):

- **Local filter** — in-process. Only the unambiguous word-boundary
  blocklist can block on its own; watch words/phrases (including sexual-content
  cues), bounded harm/target and death-threat shapes, evasion-shaped
  sequences (spaced/leet slurs or threats), and long digit runs (doxxing shape) mark
  the input *ambiguous* instead, so a heuristic can never censor a player
  ("sniggering", the river Niger). The earlier filter measured **12–38 µs per
  call**; that measurement predates the expanded signals. Clean input still
  makes **zero API calls**. The target rule allows only a short sequence of
  determiners/modifiers before a person reference, plus explicit passive,
  death and retribution shapes. It does not join arbitrary harm words and
  pronouns across a message: "Can you kill the dragon for me?" stays clean,
  while "I will kill the real person using this account" escalates. Quoted
  threats, reports and educational sexual-content language can still escalate.
  Registered names use this local tier only, and evasion sequences hard-block
  there (`name_allowed`) because a short name has no prose context.
- **Configured classifier** — ambiguous inputs may make one short
  classification call. Moderation is a task any configured provider may
  perform ([ADR-034](ADR-034-provider-and-model-optionality.md)). No
  provider, model, or vendor is the policy. The call is charged to
  moderation's own budget line (`NESTED_WORLDS_MODERATION_DAILY_CALLS`,
  bucket `moderation`, default 2000) so screened chat cannot drain the
  voice budget. Bucket names stay as they are. Prompt caching is not part
  of this policy. The shipped call's model id, prompt size, token cap,
  timeout, and arithmetic cost are implementation facts in
  `consciousness.classify_content` and the
  [routing evaluation](../evaluation/2026-10-10-moderation-routing.md), not
  requirements on the next provider.

False escalations are a budget and latency cost even when the classifier says
ALLOW: the handler waits inline, and classification shares model-call
concurrency with voice work. Six authored gameplay controls now use zero
calls, compared with six calls under the first whole-message co-occurrence rule.
That is a regression measurement, **not an expected live escalation rate**:
representative traffic, latency, classifier quality and cost remain unmeasured.
The vocabulary/intent shapes are bounded English heuristics, not comprehensive
semantic detection. See the routing evaluation for the tested cases and
limitations. The shared budget setting, the disable switch
(`NESTED_WORLDS_DISABLE_MODERATION=1`), and the hot-tunable block and watch
lists (`NESTED_WORLDS_MODERATION_{BLOCK,WATCH}_EXTRA`) remain. The failure
rule below replaces "Fail-open everywhere" for shared text.

**Shared text fails closed** (amendment 2026-10-25, approved by the owner,
Mark Weeks, in chat). This replaces the 2026-07-12 rule that a classify
error, a timeout, an exhausted moderation budget, or disabled moderation
allowed the text everywhere. For player-authored text that becomes visible
to other players — messages, replies, ideas, and anything written into the
shared world or chronicle — each of these fails closed:

- a moderation timeout
- a provider outage
- disabled moderation
- an exhausted moderation budget

The text is held or declined. It is not written where others can see it: no
chronicle row, no broadcast, no visible idea, and no published profile. On
the world's surfaces the author gets a clear in-fiction message, HTTP 200,
in the same pattern as today's content decline ("The worlds decline to carry
those words. Say it another way.") and the quiet budget line. The
implementation authors the hold line; this amendment does not invent it. A
content decline still leaves no trace and does not charge the voice budget.
WebSocket senders keep a private decline. The Ideas board stays a
non-fictional community surface: a hold or decline there is clear product
language, and the text is still not published. A name the screen does not
accept is not registered; registration keeps a clear "choose another" refusal.
The author's own session degrades gracefully. Movement, puzzles, private
notes, and other play that does not publish the held text continue.

**Private or solo-only text and mechanical gameplay stay fail-open.** A
private note, unpublished profile text, and other writing only the author
can read are not held because the classifier is down. Movement, puzzle
attempts, and scale actions continue when moderation cannot complete. A
puzzle attempt still counts and still records correctness; the raw guess
is omitted from the shared row when it was not judged. Existing chronicle
rows are not rewritten. A safety check must not become the thing that
stops the game. The local CLI `speak` path is the operator terminal in
local multi-world mode (`NESTED_WORLDS_CANONICAL_SEED` empty, `off`, or
`none`) and stays unscreened there. Speech into the configured canonical
world — including the launch default when that variable is unset — is
shared text and uses this rule. An unreadable canonical-seed setting is
treated as shared.

**Per-user caps.** One user must not be able to exhaust the shared moderation
budget or flood the classifier, and the same kind of cap applies to
model-calling actions. The caps are configuration. The starting values are
chosen to be measured, not tuned:

- `NESTED_WORLDS_MODERATION_ACTIONS_PER_USER` (default 600) counts
  moderation-triggering actions for a presented credential. Open when no
  credential is supplied.
- `NESTED_WORLDS_MODERATION_DAILY_CALLS_PER_USER` (default 60) caps classify
  calls per credential and is checked before the shared
  `NESTED_WORLDS_MODERATION_DAILY_CALLS` bucket (`moderation`, default 2000).
- `NESTED_WORLDS_MODEL_ACTIONS_PER_USER` (default 200) caps model-calling
  actions (voice, inhabitant voice, intention, and a moderation classify).
  It does not rename or touch the `anthropic` bucket or
  `NESTED_WORLDS_ANTHROPIC_*`.

Exceeding a cap holds shared text and returns a clear message. Mechanical
play continues. Credential-less local use stays open on these per-user
gates, as the existing voice sub-cap does.

**Backstop, unchanged.** Content-level redaction (§1) and the narrow
break-glass hard delete remain the way something that still lands is removed.
This amendment adds no chronicle mechanism.

The running screen implements this rule. Shared text is held when
moderation is disabled, when the moderation reserve is not `ok`, when
classification raises, and when the verdict is undecided. A local clean
verdict is a completed judgment and still publishes during a provider
outage; a local block still declines without a model call. Names are
refused when moderation is disabled, with a choose-another line. Ideas
use the same screen. `moderation_call` logs `outcome` (`allow`, `block`,
`undecided`, `error`, `disabled`, `budget`, `user_cap`) and does not log
player text or a raw address.

### 3. Continuity: never wipe; the covenant is already in force

The database is **never wiped** — not between cohorts, not across the
beta→launch boundary. The world is **additively shaped by everyone**; a new
player (solo or a new tranche) always arrives into a world prior players have
already shaped, and their play adds to it. A reset would erase dedicated
players' contributions and read as "all my gameplay is gone" → real backlash.
Continuity is a **player-trust commitment**, not just an ops convenience.
`docs/roadmap/phase-2-scale.md` (Continuity policy).

The current database is **pre-launch**; the never-wipe covenant governs real
player history from the first real player onward (there is no throwaway
pre-launch data worth protecting, and no real history yet to lose). The first
invited outside player starts the never-wipe covenant, and a world meant to be
disposable must be declared so and run on staging (2026-10-25 amendment).
Recovery from a bad state is **restore from backup, never a clean wipe**
(`scripts/deploy.sh` backs up before every deploy). The restore procedure
(runbook §7) has been rehearsed on local disposable databases: backup, then
mutate, then restore, and the cold-process rehearsal in
`tests/test_beta_rehearsal.py`. No Fly restore, and no restore from a
downloaded hosted artifact, is recorded in this repository; hosted restore
remains an open launch gate.

### 4. Write-path scope: record participation broadly

Because presence shapes the world, participation is recorded broadly:
`PLAYER_JOIN`, every `PLAYER_MOVE` (movement etches the generative art's
activity-wear — **"paths worn by traffic" is intended**, not a side effect),
every `PUZZLE_ATTEMPT`, and `AGENT_VOICE` exchanges. `server/handlers.py`.

### 5. Identity: durable `actor_identity` beside a mutable display name

Every human write carries a durable `actor_identity` (a hash of the invite
credential) alongside the mutable display name — so a rename doesn't orphan
history and two players who both call themselves "Ada" stay distinct. The model
is **register once, one key, preserve history**; a username change is allowed
(subject to §7's uniqueness rule) and history carries over, because identity is
keyed on the credential, not the name. `persistence/__init__.py`,
`server/handlers.py` (`_actor_identity`).

### 6. The permanent record is never truncated *(implemented in this ADR's PR)*

The chronicle stores the **full** message and reply; content is clipped **only
at prompt-render time** for the token budget, never at storage. The prior
`[:128]`/`[:200]` *storage* truncation was an unendorsed expedient that
permanently lost the tail of every long message. Fixed here: `server/handlers.py`
stores full content at all three player-content sites (`/speak`, `PLAYER_CHAT`,
`/agent/voice`); `consciousness._history_block` clips to a render budget
(`_MEM_MSG_CHARS`/`_MEM_REPLY_CHARS`) so voice-call prompts are unchanged. The
multi-turn transcript passed to `speak()` is deliberately left unclipped — it is
the real conversation and is already bounded to a few recent exchanges.
*Because this fix lands pre-launch, no real player history is ever stored truncated.*

### 7. Unique player names, no anonymous play *(implemented)*

**Policy:** every player, human *and* agent, has a **unique name**, and there
is **no anonymous gameplay** — once the invite gate is active, every player is
authenticated by a per-user credential that carries a known, unique name.
Realized by binding the name to the **per-user invite credential** and removing
the shared key entirely:

- **Unique at registration.** `python main.py invite mint --name X` rejects a
  name already taken (case- and whitespace-insensitive) and the twelve cast
  names; a DB UNIQUE index on `lower(trim(name))` (migration 0011) is the
  atomic backstop, and `persistence.mint_invite_key` raises `NameUnavailable`.
- **Server-authoritative at runtime.** A request carrying a per-user invite key
  uses that key's registered name (`guard.registered_name`), ignoring any
  client-supplied `player_name` / `?name=` — so names can't collide or
  impersonate, and a keyed session is never anonymous
  (`server/handlers.py::_display_name`). Client-name normalization was unified
  (trim-then-cap), closing a whitespace bypass that let `" Tessera"` slip past
  the cast-name block.
- **No shared key.** The `NESTED_WORLDS_BETA_KEY` env gate was **removed**: a
  single shared credential let many players in under one identity — colliding
  names, merged transcripts and budget buckets, and no way to tell them apart
  — which is exactly the anonymity this policy forbids. The gate is now the
  per-user `invite_keys` table alone (`server/guard.check_invite_key`); minting
  the first key closes it, and from then on every request is a named player.
- **The one keyless path is ungated local dev.** With no key minted the gate is
  open (tests, a developer's own machine) and a session may be nameless — but
  it never touches real, gated play. The CLI `python main.py play` still
  **requires `--name`** so even a local session records a known actor, never an
  unknown presence, in the shared chronicle.
- **Self-service registration, invite-gated** *(implemented)*. An operator
  creates a **single-use registration token** (`python main.py invite create`,
  migration 0012) and shares `/register?invite=<token>`; the **player** picks
  their own name there. Redemption is one transaction
  (`persistence.redeem_registration_token`): it mints the per-user play key
  and consumes the token together, so a taken name replies 409
  "choose another" and leaves the token redeemable for the retry, while a
  successful redeem can never leave the token live. The token is the
  credential on the pre-account surface (`POST /register` is reachable
  without a play key — the registrant doesn't have one yet), so **no token,
  no account**: the beta stays a closed, known cohort. Operator-minted
  `invite mint --name` remains alongside for pre-named accounts; a leaked
  unredeemed link is `invite cancel <token>`. **Fully open registration**
  (anyone can self-register without an invite) is deliberately *not* decided
  now — it is deferred until we have real usage data to judge whether opening
  the doors is safe for spend, moderation load, and world integrity (see
  "Revisit when…").

---

## Trade-offs accepted

- **Broad recording** grows storage and prompt-context with activity — accepted,
  with the balance valve below.
- **Content-level redaction** leaves the row and a `[redacted]` marker rather
  than erasing all trace — accepted, because mechanical integrity and
  accountability matter more; hard delete remains as break-glass.
- **Not truncating storage** means larger `data` blobs — bounded by the input
  caps (`message[:1024]`, chat `[:256]`) and the reply's `max_tokens`, so
  acceptable.
- **Fail-closed shared text** means a timeout, a provider outage, disabled
  moderation, or a spent moderation budget can keep one player's words from
  other people until the screen can judge them. Accepted, because a permanent
  shared record must not publish what moderation could not judge. The author's
  own session continues. Private or solo-only text and mechanical play stay
  fail-open, so the check does not stop the game. Content-level redaction and
  break-glass hard delete remain the backstop for whatever still lands.
- **Starting cap numbers** are configuration chosen as ceilings to measure,
  not rates derived from live traffic. Accepted, so a policy record does not
  freeze an unmeasured rate. Change them when measurement says they are
  too tight or too loose.

## Consequences of the 2026-10-25 amendment

- Shared player text is held or declined, and not shown to others, when
  moderation times out, the provider is unavailable, moderation is disabled,
  or the moderation budget is spent. The author gets a clear message, and the
  rest of that session keeps working.
- Per-user caps on moderation-triggering and model-calling actions are
  required. The numbers are configuration, to be measured in the
  implementation PR. Budget bucket names do not change.
- §1 redaction and the break-glass hard delete are unchanged. The never-wipe
  rule is unchanged. The first invited outside player starts it, and a
  disposable world is declared and run on staging.
- Moderation stays a replaceable task under ADR-034. This amendment selects
  no provider.
- The running screen implements the failure rule and the starting caps
  above. This decision is behavior.

## Revisit when…

- **Moderation cost or latency proves heavier than measured** → hold
  ambiguous shared text without a classifier call, or move classification off
  the request path. Shared text the screen has not judged stays unpublished.
  Private or solo-only text and mechanical play stay available.
- **Measured use shows a per-user cap is too tight or too loose** → change
  the configuration. This ADR does not set those numbers.
- **Persisted activity becomes noise/cost without shaping the world** → rebalance
  the write-path (which events earn a permanent row).
- **A "start over" or key-rotation use case emerges** → design account-level
  identity that survives credential rotation (today a new key = a new actor with
  no link to past history).
- **Usage data supports opening the doors** → decide on **fully open
  registration** (self-register without an invite). Deferred today; registration
  stays invite-gated until the beta's real spend, moderation load, and
  world-integrity signals show it is safe to let anyone in without an operator
  in the loop.
- **The history-render budget widens** → revisit the 128/200 render clip in
  `consciousness._history_block`.
- ~~**(Pre-launch build)**~~ Both pre-launch builds have shipped: §7 (unique
  names / no anonymous play / invite-gated self-service) and §2 (input
  moderation). The 2026-10-25 amendment is what the running screen does for
  shared text, including the starting per-user caps. The triggers above
  govern later tuning.

## Rejected alternatives

- **Fail-open for shared text** (the 2026-07-12 sentence) — a timeout, an
  outage, a disabled screen, or a spent budget must not write player text
  where other players can see it. Fail-open remains the rule for private or
  solo-only text and for mechanical play.
- **Naming one provider as the moderator** — classification is a task.
  ADR-034 chooses a configured provider by evidence. A model id in the current
  program is an implementation fact, not this policy.
- **Hard row-delete as the default removal mechanism** — destroys the mechanical
  fields (counters, epochs, art counts) and the accountability trail; kept only
  as a narrow break-glass.
- **No removal mechanism (handle the first incident ad hoc)** — a
  permanent-memory world cannot launch with an undefined abuse path.
- **Fresh DB per cohort** (the earlier non-goal) — erases the additive shared
  world; to dedicated players it would read as "my gameplay is gone."
- **Storage-level truncation for token budgeting** — permanently loses the
  record's tail; the budget belongs at render time.
- **A shared beta key alongside per-user keys** — the original design kept the
  `NESTED_WORLDS_BETA_KEY` env gate as an operator/dev convenience. Rejected
  (removed) pre-launch: a shared credential collapses every holder to one
  identity, so it silently reintroduces exactly the anonymous, name-colliding
  play §7 exists to prevent. There is no throwaway pre-launch data and no key
  had been issued, so removing it costs nothing and the policy becomes absolute.
