# ADR-041: Names are natural and unique; the path is the address

**Status:** Accepted by the owner, Mark Weeks, on 2026-11-18, in a Claude Code
working session (quoted below and in the
[2026-11-18 owner decisions](../roadmap/owner-decisions-2026-11-18.md), D-B).
The session cannot be verified from the repository; the owner's merge of the
pull request that adds this record is the verifiable act. This record changes
no code. The implementation is its own pull request, and the golden re-pin it
needs was approved by the owner in the same session.

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

### D4. Nothing else moves

Puzzle draws, per-node difficulty, the Causal Augury election and any other
derivation keyed on a node's identity are keyed on the name together with the
address. That keeps every draw byte-identical to today's, so the re-pin is
limited to names and to text that prints a name. Puzzle wording that refers to
the dash or to a "lineage mark" is rewritten.

### D5. The cast

`Cartographer-9` becomes `Cartographer`. A cast name used in production stays
reserved forever, including after a cast member retires.

### D6. Player names

A taken name is refused, never altered. A search on 2026-11-18 found no code
that appends characters to a player's name (*inferred* from the search; the
implementation pins it with a test).

### D7. The re-pin

`GENERATOR_VERSION` becomes 3. The pins that move, at both depths: the names
digest, the world digest, the landmark names, and the puzzle pins for epoch 0
and renewal epochs 1 and 2, because prompts print place names. The era-name
pins do not move. The owner approved this re-pin on 2026-11-18 ("approved");
the approval covers this change and no other.

## Trade-offs accepted

- A position can no longer be read off a name. Code that held only a name now
  makes one indexed lookup.
- A local world born under generator version 2 keeps its suffixed names until
  it is re-created. No such world exists on staging or production.
- Every puzzle pin moves, although no draw does.
- Both clients change, so the implementation holds the client bundle.

## Revisit when

- A rename is wanted for a born node. Uniqueness must then hold across the
  rename, which belongs to ADR-029.
- Breadth above nine is wanted. Path digits are single digits today.
- A second world shares a database with the first. Uniqueness is per world.

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
