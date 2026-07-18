# ADR-004: Day-One Data Policy

**Status:** Accepted 2026-07-12

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

### 2. Input moderation *(implemented — the measured tax matches the plan)*

Player text is screened *before* it enters the chronicle (`/speak`,
`/agent/voice`, WS chat) and before a name enters the registry
(`/register`, `invite mint`, `play --name`). Two tiers, cheapest first
(`server/moderation.py`):

- **Local filter** — in-process. Only the unambiguous word-boundary
  blocklist can block on its own; watch words/phrases, evasion-shaped
  sequences (spaced/leet slurs), and long digit runs (doxxing shape) mark
  the input *ambiguous* instead, so a heuristic can never censor a player
  ("sniggering", the river Niger). Measured: **12–38 µs per call, zero API
  calls for clean input** — the common case is free.
- **Haiku classify** — ambiguous inputs make one short uncached call
  (`consciousness.classify_content`, `claude-haiku-4-5`, ~166-token system
  prompt, `max_tokens=8`, hard 3 s timeout). Measured by arithmetic:
  **~$0.0003–0.0005 per escalated input**; its **own budget line**
  (`NESTED_WORLDS_MODERATION_DAILY_CALLS`, default 2000 → worst case
  <$1/day) so a burst of screened chat can never drain the voice budget.
  The prompt is deliberately **not** cache-marked — it sits far below the
  4096-token cache minimum, where a marker is a silent no-op (the trap this
  repo has hit twice).

**Fail-open everywhere**: classify error, timeout, exhausted moderation
budget, or the kill switch (`NESTED_WORLDS_DISABLE_MODERATION=1`) all
ALLOW — redaction stays the backstop, and a safety feature must never be
what breaks chat. A decline is HTTP 200 in the world's voice ("The worlds
decline to carry those words. Say it another way."), leaves **no trace** —
no chronicle row, no broadcast (WS senders get a private `chat_declined`),
no voice-budget charge — and blocklists are hot-tunable via env
(`NESTED_WORLDS_MODERATION_{BLOCK,WATCH}_EXTRA`). The CLI's own speak path
is deliberately unscreened: the local terminal is the operator themselves.
Real production latency/cost is visible from day one via the structured
`moderation_call` log line.

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
pre-launch data worth protecting, and no real history yet to lose). Recovery
from a bad state is **restore from backup, never a clean wipe**
(`scripts/deploy.sh` backs up before every deploy; the restore path is
rehearsed, runbook §7).

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
- **Fail-open moderation** means determined abuse can still land (an API
  outage, an exhausted budget, or a novel phrasing all allow) — accepted,
  because the inverted failure mode (a safety check that silences legitimate
  players when it breaks) is worse, and content-level redaction remains the
  backstop for whatever slips through.

## Revisit when…

- **Moderation cost/latency proves heavier than measured** → drop to the
  local-filter-only tier, or move the classification call to an async/batch path.
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
  moderation). The first trigger above governs §2's tuning from here.

## Rejected alternatives

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
