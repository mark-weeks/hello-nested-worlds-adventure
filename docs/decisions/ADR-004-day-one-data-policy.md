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

Launch is near and **the beta database already holds real player history**
(a decision recorded below), so these policies bind *now*, not from some future
clean-slate. Several of them were already made and partly implemented
(redaction, presence recording, credential identity, reserved names) but never
written down; this ADR records them and their reasoning, and is explicit about
the two places where the *intended* policy is not yet fully implemented.

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

### 2. Input moderation is planned but deferred behind an abuse trigger

Redaction is the **day-one backstop**. Screening player text *before* it enters
the chronicle is desirable but deferred: when triggered, start with a **cheap
local filter** (wordlist/heuristic, near-zero cost/latency) and escalate to
LLM-grade moderation only if that proves insufficient — LLM moderation adds a
model call to *every* player input (including chat, which today costs zero LLM),
bounded by the existing daily/per-user caps and the concurrency semaphore, plus
latency on a real-time surface. Precise cost must get a blind-spot pass (live
docs / measurement) before it is built.

### 3. Continuity: never wipe; the covenant is already in force

The database is **never wiped** — not between cohorts, not across the
beta→launch boundary. The world is **additively shaped by everyone**; a new
player (solo or a new tranche) always arrives into a world prior players have
already shaped, and their play adds to it. A reset would erase dedicated
players' contributions and read as "all my gameplay is gone" → real backlash.
Continuity is a **player-trust commitment**, not just an ops convenience.
`docs/roadmap/phase-2-scale.md` (Continuity policy).

The beta DB is treated as **real player history to preserve**, so the covenant
has *already started*. Recovery from a bad state is **restore from backup, never
a clean wipe** (`scripts/deploy.sh` backs up before every deploy; the restore
path is rehearsed, runbook §7).

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
*Rows written before this fix remain truncated; that tail is unrecoverable.*

### 7. Unique player names, no anonymous play *(intended policy — implementation gap)*

**Intended:** every player, human *and* agent, has a **unique name**, enforced
at name selection; nobody plays anonymously.

**Current state (the gap):** display names are *not* globally unique (duplicates
are silently disambiguated by the hidden credential), an anonymous / "unknown
presence" path exists (CLI; stripped names), and only the twelve cast names are
reserved (`agents/roster.py`; a WS join as a cast name is refused `403`, a
matching body name is stripped). Reserving the cast is driven by **narrative
integrity** — a node greets "Tessera" as a known regular, so a human posing as
Tessera would hijack that recognition and corrupt node memory — with an
anti-impersonation benefit.

Realizing the intended policy needs a **uniqueness constraint at name
selection** (pick a variant if taken) and **removal of the anonymous path**.
That is larger than this ADR should carry, so it is recorded here as the target
and **left to a follow-up PR**.

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
- **Deferring moderation** makes the day-one defense reactive (redaction) rather
  than preventive — accepted given no evidence of need yet and the real per-input
  cost of LLM moderation.

## Revisit when…

- **Repeated bad-actor content / abuse volume crosses a threshold** → introduce
  input moderation, cheap local filter first. *(Cross-list on the
  `docs/roadmap/phase-2-scale.md` trigger list.)*
- **Persisted activity becomes noise/cost without shaping the world** → rebalance
  the write-path (which events earn a permanent row).
- **A "start over" or key-rotation use case emerges** → design account-level
  identity that survives credential rotation (today a new key = a new actor with
  no link to past history).
- **The history-render budget widens** → revisit the 128/200 render clip in
  `consciousness._history_block`.
- **(Committed follow-up)** → implement §7: unique-name enforcement at selection
  and removal of the anonymous path.

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
