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

### 2. Input moderation is planned for launch (the tax is manageable)

Screening player text *before* it enters the chronicle is desirable, and a
blind-spot pass against the current model docs found the cost/latency tax
**manageable**, so it is planned for launch rather than deferred behind a
trigger. The cheap shape: a **local filter first** (wordlist/heuristic,
in-process, zero API cost/latency) catches the obvious cases; only *ambiguous*
inputs escalate to a **Haiku-tier classification call** (`claude-haiku-4-5`,
$1/$5 per 1M tokens — ~5× cheaper than the Opus voice model; a short classify
costs a fraction of a cent per input). There is no dedicated moderation
endpoint — moderation is a single Messages-API call. **Fail-open** — if the
check errors or times out, allow the content (redaction stays the backstop),
consistent with "failure stays in fiction." Taxes to account for: it adds a
model call to *chat*, which today costs zero LLM; the calls draw on the
daily/per-user caps and the concurrency semaphore, so moderation gets its own
budget line / relaxed cap; and it adds sub-second latency on a real-time
surface. Do **not** prompt-cache the moderation system prompt — it sits below
the 4096-token cache minimum, so a `cache_control` marker would be a silent
no-op (the trap this repo has hit twice). Redaction remains the backstop for
whatever slips through.

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
This is a **pre-launch requirement** (enforced before real gameplay); it is
recorded here and to be built as its own change — larger than this ADR's PR
should carry.

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

- **Moderation cost/latency proves heavier than measured** → drop to the
  local-filter-only tier, or move the classification call to an async/batch path.
- **Persisted activity becomes noise/cost without shaping the world** → rebalance
  the write-path (which events earn a permanent row).
- **A "start over" or key-rotation use case emerges** → design account-level
  identity that survives credential rotation (today a new key = a new actor with
  no link to past history).
- **The history-render budget widens** → revisit the 128/200 render clip in
  `consciousness._history_block`.
- **(Pre-launch build)** → implement §7 (unique-name enforcement at selection +
  removal of the anonymous path) and §2 (local-filter-first + Haiku moderation,
  fail-open).

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
