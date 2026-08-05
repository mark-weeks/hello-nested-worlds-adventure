---
name: repin-goldens
description: Deliberately re-pin the golden freeze digests after a conscious generator change. Use ONLY when tests/test_continuity_freeze.py fails AND changing what new worlds are born as is the intent, ratified by the human — never to make CI green.
---

# Re-pinning the golden freeze

A failing pin in `tests/test_continuity_freeze.py` means **"you changed
what new worlds are born as"** — not "the test is stale." The store forbids
rewriting born worlds (`birth_world` is idempotent;
`persistence.save_world_nodes` refuses overwrites), so the pins guard
births: fresh installs reproducing the reference seed, and every world born
after your change.

## Before touching any pin

1. **Stop and confirm intent.** Is changing the birth output the point of
   this diff, or a side effect? A side effect (an accidental extra RNG draw,
   a reordered bank, a changed breadth range) is a bug — fix the code, not
   the pin.
2. **This is a one-way door under the merge gate.** The human ratifies the
   re-pin; present which pins change and why the change is safe (pre-launch
   vs post-launch matters — after first production birth, seed/name changes
   go through the ADR-007 continuity process).

## The procedure

1. Bump `GENERATOR_VERSION` in `multiverse/store.py` for any meaningful
   generator change — it keys the born-world store, so old worlds keep
   their version and new births carry yours.
2. Re-pin at **both depths** — the depth-6 reference world AND the full
   11-level world. Five scales (Room and deeper) exist only below depth 6;
   shallow pins alone are blind to their banks. Update every failing
   surface: node counts, names/world/puzzle digests, breadth profile,
   landmark canaries, and the renewal-epoch puzzle pins (epochs 1 and 2 —
   solved-state rehydration keys include "· Renewal N").
3. **Never re-pin the era-name pins.** The two display banks in
   `multiverse/chronicle.py` are read at render time — editing them
   retroactively renames every era already displayed. They stay frozen
   until eras are materialized (ADR-006 "Revisit when").
4. Record why in the batch's CHANGELOG entry, and name the re-pin as
   intentional in the irreversibility check (see the 2026-08-03 and
   2026-08-04 entries for the expected shape).
5. Run the full `./scripts/check.sh` — the freeze suite must pass green on
   the new pins, and nothing else may have moved.
