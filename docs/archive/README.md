# Archived documents

Documents whose active content has fully shipped or been superseded. They are
kept verbatim (plus the banner at the top of each) as the record of what was
planned and decided at the time; nothing in this directory governs current
work. The live index is [`docs/roadmap/README.md`](../roadmap/README.md).

Evaluations stay in `docs/evaluation/` (dated by filename) and ADRs stay in
`docs/decisions/` (each carries its own status line); neither moves here.

| Document | Formerly | Archived | Why |
|---|---|---|---|
| [Phase 1 beta scope](roadmap-phase-1-beta.md) | `docs/roadmap/phase-1-beta.md` | 2026-10-03 | Every item shipped before `0.1.0-beta`; the file only listed strike-throughs. |
| [The pre-launch window](roadmap-pre-launch-window.md) | `docs/roadmap/pre-launch-window.md` | 2026-10-03 | All four batches shipped (PRs #77–#81); sequencing passed to the discovery-and-return plan on 2026-09-07. Its "Declined" list is restated in the roadmap index. |
| [Ensemble action plan](roadmap-ensemble-action-plan.md) | `docs/roadmap/ensemble-action-plan.md` | 2026-10-03 | Tracks 0–2 shipped; still-open items are carried into the roadmap index with current status. |

## Archiving rule

Archive a plan when every item it sequences has shipped or been superseded,
not when it is merely old. Move it with `git mv` into this directory under a
`<kind>-<name>.md` name, prepend a banner naming the former path, the date,
what still binds, and where the live content now lives, and rewrite relative
links so they resolve from here. Carry any still-open items into
`docs/roadmap/README.md` before archiving, so the plan can be retired
without losing a commitment. Record the move in the batch's CHANGELOG entry.
