# ADR-041: Names are natural and unique; the path is the address

**Status:** Accepted by the owner, Mark Weeks, on 2026-11-18, in a Claude Code
working session (quoted below and in the
[2026-11-18 owner decisions](../roadmap/owner-decisions-2026-11-18.md), D-B).
The session cannot be verified from the repository; the owner's merge of the
pull request that adds this record is the verifiable act. This record changes
no code. The implementation is its own pull request. The owner approved the
naming change and its re-pin in the same session; under `AGENTS.md` the pin
diff itself is approved in that pull request (D7).

## Context

**What a name is today.** Every node is born with a name of the form
`<qualifier> <motif> <form>-<path digits>`, for example
`Quiet Salt Anchorage-11111` (`multiverse/generator.py`, `_generate_name`). The
digits are the node's path from the root: the root is `1`, its second child
`12`, that child's first child `121`. At full depth the suffix is eleven digits
(`Cedar Anchor Quark-11111111111`).

**Where the suffix shows.** Both clients strip it in most feed lines
(`static/clientlogic.js`, `displayName`), so it is easy to miss. It is still the
stored name. The place voice is told the stored name. `/chronicle` and
`/history` serve it. Durable history is keyed on it. Puzzle prompts print it,
and one navigation hint tells the player that a place's "living name is
everything before the dash and digits" (`puzzles/generators.py`).

**What the suffix is for.** Not uniqueness. Executed for seed 382 at `7d39ddf`:
4,208 nodes, 4,208 distinct names, and 4,208 distinct names with the suffix
removed. That is by construction: each level assigns its three-word phrases
one-to-one, and each level has its own final words. The suffix lets code read a
node's position out of its name without a lookup: `multiverse/store.py`
(`resolve_node_by_name`), `puzzles/gates.py`, `server/world_mechanics.py`,
`server/handlers.py`, the CLI and both clients do so. A search on 2026-11-18
found 24 source files that depend on it, 44 Python test files and 17
JavaScript test files that use suffixed names.

**The cast.** Eleven of the twelve cast names are plain. One is not:
`Cartographer-9` (`agents/roster.py`).

**The owner's decision, 2026-11-18.**

> Re: cast names, or any names for that matter, I do not want weird appended
> characters like "-9" in "Cartographer-9". Names of cast and nodes must be
> unique as well as natural, in the sense that "Cartographer" is much more
> natural than "Cartographer-9".

Offered two ways to meet that, the owner chose: "I agree with separating the
name from the address".

**Why now.** A born world is never re-born (`AGENTS.md`, "The permanent
world"). Born names are the identity that durable history is keyed on. No world
has been born on staging or production, so the change is free today and would
need the unbuilt rename grammar of ADR-029 after the first kept world.

## Decision

### D1. A name is a label

A node's name is its three curated words and nothing else. No name, of a node
or of a cast member, carries appended characters.

### D2. Names are unique within a world

The generator already guarantees it. The implementation also checks it when a
world is born and enforces it with a unique index on `(world_seed, name)`, an
additive migration.

### D3. The path is the address

A node's position is its stored path, which `world_nodes` already holds in its
own column and primary key. Code that needs a position reads it from the node
or looks it up by name. The server sends the address to clients as its own
field. Clients may show it; they never derive it from a name.

The address has two written forms. The stored path is dot-joined (`1.2.1`).
The digits form is the same path with no separator (`121`), which is the
suffix a name carries today. Keys use the digits form (D4). The implementation
says which form the server sends.

### D4. Nothing else is meant to move

Every derivation keyed on a node's identity is keyed on the string
`f"{name}-{digits}"`, where `digits` is the undotted path digits that
`_path_suffix` produces today. That string is byte for byte the name stored
today, so every random input stays identical (*inferred* from reading each
keyed hash in `puzzles/generators.py`: difficulty, the node's random stream,
renewal and the Causal Augury election). A world born under generator version
2 or earlier already stores that string as its name, so its key is the stored
name alone and its hints keep today's wording (see Trade-offs). Other derivations keyed on a node's
name take the same key: cascade hop tokens (`causality/laws.py`), the cast's
attempt rolls (`agents/agent.py`), and client art and sound.

Three things in the puzzle generator read the suffix itself. Each is kept
working from the address:

- **The leak screen.** `_answer_leaks` rejects a candidate whose answer shows
  in what the player is served, and today that includes the suffix printed in
  prompts and hints. The address is still served (D3), so the screen keeps
  treating the address digits as shown text. Otherwise a place could be given a
  number pattern whose answer is its own address. With that, the screen's
  verdicts do not change. What dropping the digits would do was *executed* on
  2026-11-19, by stripping the suffix at the screen only. On seed 382 no place
  gets a different puzzle at depth 6 or depth 11 for epochs 0 to 2. On seed 212
  one place does at epoch 0, the case review found, and 9 of 280,152
  node-epochs do across seeds 1 to 400 at depth 6. Every one is a Universe
  given a number pattern whose answer equals its address digits, which is why
  the screen must keep them.
- **The enfold puzzles.** `_make_enfold` takes a place's depth and ordinal from
  the digits and declines when a name has none. The implementation gives it the
  address, so those puzzles and their answers do not move.
- **Wording.** Hints that refer to "the dash" or to a "lineage mark" are
  rewritten; 842 and 718 of seed 382's epoch-0 puzzles at full depth contain
  those words. New wording is screened as new text and could change a verdict.

So the implementation compares the old and new family, answer and difficulty
for every node, at both depths and for epochs 0 to 2, and reports every
difference. It runs the same comparison, with prompt and hint text, on a world
born under generator version 2. None is expected. Any that appears is shown to the owner with the pin diff (D7). The
pins alone cannot show a selection change, because every pinned line begins
with the place's name and so changes anyway.

### D5. The cast

`Cartographer-9` becomes `Cartographer`. A cast name used in production stays
reserved forever, including after a cast member retires. Derivations keyed on
the cast member's own name move with the rename: its puzzle-attempt roll
(`agents/agent.py`) and its banter phase. Its persona comes from the roster,
not from a hash of the name.

### D6. Player names

A taken name is refused, never altered. A search on 2026-11-18 found no code
that appends characters to a player's name (*inferred* from the search; the
implementation pins it with a test).

### D7. The re-pin

`GENERATOR_VERSION` becomes 3. The pins that move:

- the names digest, the world digest and the landmark names, at both depths;
- the epoch-0 puzzle pin at both depths, and the renewal pins for epochs 1 and
  2 at depth 6, because every pinned line begins with the place's name;
- the launch hinge name in `tests/test_wrap_passage.py`, as a string only. The
  selector keys on the path, so the hinge stays on the same node.

The era-name pins do not move. A selection change (D4) would move the same
puzzle pins and cannot be told apart from the rename by a digest, which is why
D4 requires the comparison.

The owner approved the naming change and its re-pin on 2026-11-18
("approved"). `AGENTS.md` requires the owner's approval of the specific pin
change in the current task or pull request, and says a decision record does
not pre-approve a re-pin. So this record is not that approval, and a different
task or agent cannot rely on it. The implementation pull request shows the
exact pin diff and the D4 comparison, and the owner approves that diff there.

## Trade-offs accepted

- A position can no longer be read off a name. Code that held only a name now
  makes one indexed lookup.
- A world born under generator version 2 or earlier keeps its stored names,
  which already end in the path digits, until it is re-created. Its key is the
  stored name alone, and its hints keep today's wording. Appending the address
  again would change the difficulty of 3,213 of seed 382's 4,208 places
  (*executed*; the root moves from 3 to 4). Stored puzzle definitions would
  survive, but unopened puzzles and renewals would be drawn from the changed
  input. Each stored row records its generator version, but nothing reads it
  today. The implementation adds that read, and the server sends clients the
  key, so a client never joins a name and an address itself. As of 2026-11-19
  no such world exists on staging or production. A staging twin deployed
  before the implementation merges would be one; it is disposable.
- Every puzzle pin moves, because each pinned line carries the place's name.
  No random input moves, and no place is expected to get a different puzzle
  (D4).
- Both clients change, so the implementation holds the client bundle.

## Revisit when

- A rename is wanted for a born node. Uniqueness must then hold across the
  rename, which belongs to ADR-029.
- Breadth above nine is wanted. Path digits are single digits today.
- A second world shares a database with the first. Uniqueness is per world.
- A level's names approach its name space (`_NAME_SPACE`, 6,912 phrases a
  level). The generator fails loudly before it repeats a name.

## Rejected alternatives

- **Keep the suffix in storage and hide it wherever a player looks.** No
  re-pin and less work now. Permanent history would stay keyed on suffixed
  names forever, every new surface would have to remember to strip them, and
  the stored name would still break the rule. The owner chose against it.
- **Number duplicates only when two names collide.** There are no collisions
  to number, and a number is an appended character.
- **Invented single-word names.** Generator version 1 used invented syllables;
  version 2 replaced them because a person could not read, remember or repeat
  them.
