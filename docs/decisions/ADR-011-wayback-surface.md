# ADR-011: The Wayback Surface — past state through present senses

**Status:** Accepted 2026-08-29 — ratified by the owner's merge of the
implementing PR #81 (pre-launch batch 4). This is the player-facing payoff of
ADR-009's chronicled-delta discipline and the final product batch in the
pre-launch window.

---

## Context

The world already remembers two different things:

- `world_nodes` holds each node as born, immutably;
- `world_mutations` holds every later material delta, its per-node ordering
  version, and every causal strength.

ADR-009 made state-at-T reconstructible before any production history
existed. The remaining question is how to expose that record without quietly
turning an archive into another mutable system, rewriting old consequences
with current effects code, or revealing whether a trace belonged to a human
or an agent.

Wall-clock timestamps are not exact cursors: SQLite records to the second and
multiple non-commutative changes can share one timestamp. Returning a node's
unbounded history to the browser is not a scalable substitute. Period images
are not historical truth either: the local art and sound mappings are
deliberately tunable, while generated background images are cached from the
current prompt and current history.

## Decision

Ship a **read-only, node-scoped wayback surface**.

- **The exact cursor is a node-local event step.** Step 0 is the immutable
  born node. Step N is the state immediately after that node's Nth chronicled
  interaction, resolved to the row's monotonic global id; deltas still fold in
  their per-node `node_version` order. The API returns the selected step and
  total count, so a range input can address an arbitrarily long history
  without downloading it. The timestamp is a label, never the ordering key.
- **Historical properties are born properties plus stored deltas.** The fold
  begins with the born row and applies the RFC 7396 patches stored at write
  time. It never replays `effects.py`. Beginning with the born row matters:
  a `null` delta can remove a property that existed at birth, which an
  overlay-only fold would otherwise forget.
- **Historical pressure and wear are derived from the same cursor.** Ripple is
  `min(1, sum(strength) × RIPPLE_INCREMENT_PER_STRENGTH)` for rows through the
  selected step. Activity is the number of node interactions through that
  step. Together with reconstructed properties these are exactly the inputs
  the deterministic art and sound functions consume today.
- **The response carries no actor taxonomy.** A moment is only `birth`,
  `trace`, `ripple`, or `change`; a change may expose its mechanical delta and
  a ripple its strength. It carries no player name, durable identity, or
  human/agent flag. The archive shows that and how the node changed, not what
  class of being left the trace.
- **First witness is derived, not recorded anew.** It is the timestamp of the
  node's earliest existing chronicle row. A Wayback read or visual observation
  appends nothing. Existing participation rows remain governed by ADR-004's
  broad-recording decision; Batch 4 neither adds a second arrival/page-view
  row nor changes that established ledger. This closes the roadmap's open
  sub-decision at its default: looking at the archive is not an interaction.
- **Both browser clients scrub the same endpoint.** Manual scrubbing redraws
  the node with `nodeart.js`; when the player chooses to listen, the same
  reconstructed state retunes `nodesound.js`. Auto-play advances through the
  event steps and is absent when the operating system requests reduced
  motion. The surface says plainly: “the node as it was, seen with today's
  eyes.”
- **Historical frames use only the deterministic local senses.** The cached
  external background-image layer is omitted: its cache key and prompt use
  current history, so presenting it as a historical frame would be false.
  Nothing visual or audible is stored by this batch.
- **The endpoint stays inside existing boundaries.** It honors the canonical
  world guard, resolves node identity from born rows, is read-rate-limited,
  and rejects forged nodes or out-of-range steps. It adds only the additive,
  rollback-compatible cache-metadata migration 0016 and no `world_mutations`
  write path.

## Trade-offs accepted

- **Reinterpretation, not playback.** A renderer edit changes how every past
  state appears, just as it changes the present. State is historical;
  presentation is current. This is honest, deterministic for all players at a
  given deploy, and avoids renderer-version storage.
- **One read per scrub step.** The browser fetches the selected state instead
  of loading an unbounded timeline. Read limiting protects the server; client
  input coalescing keeps dragging responsive.
- **Interaction wear can change without substance changing.** A trace-only
  moment increments activity and therefore may add an art etching or audible
  wear even when the property delta is empty. That is the existing art/sound
  contract, not invented archive state.
- **The archive starts where faithful recording starts.** Pre-launch Batch 1
  landed before production, so the hosted world has no dark age. Local or
  imported databases with pre-ADR-009 history preserve their last observable
  legacy baseline, but cannot manufacture a missing delta or timestamp. That
  untimeable baseline is treated as pre-chronicle state: birth remains born,
  and the baseline first participates at the first recorded step.

## Revisit when…

- **Faithful period rendering becomes a product goal** → version renderers or
  persist their parameters; do not relabel reinterpretation as playback.
- **A node's event count makes ordinal lookup measurably slow** → add a
  read-optimized index or checkpoint table derived from the chronicle; do not
  change the cursor semantics.
- **History pruning is enabled** → the first available step is no longer birth
  continuity; the UI and API must expose the gap explicitly before pruning.
- **Generated imagery becomes reproducible from exact historical inputs** → it
  may join the archive only with a deterministic, state-addressed contract.

## Rejected alternatives

- **Wall-clock-only cursors.** Ambiguous when two changes share a second.
- **Replaying current effect logic.** A code edit would rewrite remembered
  state.
- **Stored screenshots, audio, or periodic state snapshots.** More permanent
  storage, less causal legibility, and unnecessary while the event stream is
  complete.
- **Returning every historical frame in one response.** Payload and render
  cost grow without bound with the world's age.
- **Recording archive views or a second Wayback-specific arrival.** Makes a
  read-only surface a recursive chronicle writer and turns attention telemetry
  into world truth. ADR-004's existing participation rows are a separate,
  already-ratified contract.
