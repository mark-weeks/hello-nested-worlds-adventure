# Next steps: October 2026 to January 2027

*Written 2026-10-04 against `main` at #110 (`5072f0f`). Status: a plan for the
owner. It ratifies no ADR and authorizes no implementation, deployment,
recruitment, tag, or merge; each step below still needs its own instruction.
Edit it in place as steps land; archive it under the
[archiving rule](../archive/README.md) once every step has shipped or been
superseded. The [roadmap index](README.md) carries it.*

## Thesis

Enfolded is code-complete for an invited beta and has never been run by anyone
but its owner. The last canonical gate on `main` passed (readiness record, #109:
**1,417 Python**, **131 Vitest**, **96 Playwright**), the hosted world has never
started, the chronicle is empty, and the returning-visitor metric has no data
point. Every remaining gate before the first cohort is human or operator work:
credentials, a staging twin, newcomers to watch, a world status to declare.

So the order for the next ninety days is:

1. **Open the doors that need hands, then run the M7 pilot** (October). Agents
   can prepare releases, probes and fixes; only the operator can activate
   backups and only a research lead can observe people.
2. **Read the pilot out and settle the owner's decision agenda** (end of
   October). The read-out, not the calendar, chooses what M8 builds.
3. **Make the world able to change shape** (November to January), in the
   batches ADR-029 through ADR-033 already sequence, exactly as far as the
   owner ratifies them.

A parallel maintenance track runs throughout, restricted to work that trips no
one-way door and adds no churn in the launch week.

One ordering disagreement with the
[2026-10-03 assessment](../evaluation/2026-10-03-ambition-and-boundaries.md)
is made explicit in decision C below: this plan runs the pilot *before* the
identity/alias migration, on the readiness record's argument, and asks the
owner to rule on it.

## Where we start (confirmed from the repository and GitHub on 2026-10-04)

- `main` is at #110. Shipped since `0.1.0-beta`: M1 to M4, the first situation
  and participants, the Ideas board, 44 scale-native actions, commit-then-discover,
  the unified exploration UX, beta readiness tooling. None of it is deployed.
- The only release tags are `v0.1.1-qa.1` and `v0.1.1-qa.2`, cut 2026-08-31 from
  `32af091`, roughly forty merged PRs behind `main`. `pyproject.toml` still reads
  `0.1.1rc2`; the release workflow enforces one tag per package version.
- Seven launch gates are open ([readiness record](../evaluation/2026-10-03-beta-readiness.md),
  "Remaining gates and owners"): hosted backup activation, hosted restore,
  freshness alerting, live models, hosted runtime and devices, first-session
  observations, the seven-day return. The read-only artifact check returns
  `missing`; no Fly or model credential exists in any checked environment.
- Three issues are open (#87, #88, #89, all 2026-08-31 epics); the readiness
  record dispositions them. No pull request is open.
- Four implemented contracts are still marked Proposed: ADR-019 to ADR-022,
  plus the bounded parts of ADR-013/014 realised under ADR-024/025. ADR-024,
  ADR-025, ADR-027 and ADR-028 carry implementation-record status lines, not
  Proposed and not Accepted.
  Five new drafts (ADR-029 to ADR-033) are Proposed and introduce nothing.
  ADR-029 and ADR-030 both claim migration `0028`; ADR-033 also needs one.
- Operating posture: default voice model `claude-opus-4-8` (ADR-005 §4), budgets
  as daily call caps (`server/guard.py`), explorer the invite default with `/app`
  the alternate, `server/handlers.py` at 1,612 lines, migrations `0001`–`0027`.
- Pilot protocol 2 is runnable and `scripts/pilot_report.py` enforces it. The
  protocol names **October 24** for cohort completion if **October 31** stays the
  beta date.

## Part 1. The critical path to the pilot

Dates are a proposal that works backwards from October 24 and assumes the
operator steps start this week. They are not commitments. The "done" column is
the evidence the readiness record or runbook already asks for; nothing here
adds a new gate. The sequence carries no slack between the first deploy and
the beta date; the slip rule below says what moves when a step does.

| # | Step | Who | Needs | Done when | Target |
|---|---|---|---|---|---|
| P1 | **Activate hosted backups.** Set `FLY_API_TOKEN`, `ENFOLDED_BACKUP_APP`, then `ENFOLDED_BACKUP_REQUIRED=true`; dispatch `backup.yml`; inspect the artifact. | Operator | Fly app and token | `scripts/backup_health.py` exits 0 against a real app-specific artifact; a deliberately stale window exits nonzero (runbook §7–§8) | Oct 8 |
| P2 | **Stand up the staging twin and a staging model credential** (runbook §3a). Decide the staging model via `NESTED_WORLDS_MODEL`. | Operator | Fly account; Anthropic key | `/health` ok; invite gate closed by the first minted key; `/speak` returns `"ai": true` | Oct 8 |
| P3 | **Select and cut the release candidate.** Bump the package version, recheck dependencies (the `@xmldom/xmldom` advisory stays deferred only if the worker path stays unused), tag `v0.1.2-qa.1`. | Agent prepares the PR; owner cuts the tag | P-none | Release workflow green on the tag; wheel smoke passes; readiness record lists commit, bundle, schema, seed, client default | Oct 9 |
| P4 | **Staging rehearsal** (runbook §3a and §8 "current experience rehearsal"): invite gating and rotation, private notes, pinned puzzles, saved position, direct Act submission, overlapping delayed v3 attempts, lost acknowledgements and retries, reconnect, process death with pending work, `scripts/ws_soak.py`, live-voice and intention probes including clarification and refusal, restore of a **downloaded** artifact into isolated staging, freshness alert exercised on a stale/missing condition. | Operator runs; agent scripts the probe list and records results | P1–P3 | Each check recorded with checksum, release, timing; no credential or private text in evidence | Oct 9–13 |
| P5 | **Research prerequisites, before anyone is recruited** (protocol 2 "Scope and venue"; readiness record "Beta scope and promise"). Name the facilitator/research owner; fix observation dates; list the cohort's devices and complete the applicable browser, keyboard, accessibility and fallback checks for each one, excluding any device that cannot be verified; choose the client; write the consent wording and the retention/deletion date. | Research lead; agents run the device checks | None; precedes any invitation | All six protocol-2 fields are in the restricted research record, every included device has its checks recorded, and no newcomer has been approached | Oct 9–10 |
| P6 | **Watch 2–3 newcomers on staging** (protocol 2, script steps 1–3). Tell them the world is temporary. | Research lead | P4, P5 | Observations recorded pseudonymously outside the repo; confusion list written | Oct 12–14 |
| P7 | **Fix what confused them.** Only observed entry, navigation, acceptance and consequence-recognition failures; no new capability. Re-cut the tag if code changed. | Agents; owner reviews | P6 | Focused suites and `./scripts/check.sh` green; CHANGELOG entry; irreversibility check "none" | Oct 13–15 |
| P8 | **Production declarations.** World status (retained research or production, decision B), voice model default (decision D), ADR status pass (decision E), and the cohort device list confirmed against P5's verified set. The research declarations were made in P5. | Owner, research lead | P5–P7 | Written in the restricted research record and the readiness record | Oct 15 |
| P9 | **Tear the staging twin down, then first production deploy** (runbook §3a and §8: the staging chronicle must not linger as a second world) via `scripts/deploy.sh --first-deploy`; mint one key per person; verify the first production backup immediately; `SENTRY_DSN` set; uptime ping on `/guide`; daily budgets sized to `cohort × exchanges × cost` with headroom. | Operator | P4–P8 | Runbook §8 T-1 and launch-day boxes ticked; `backup_health.py` green against production | Oct 16 |
| P10 | **Cohort window.** 8–12 people onboarded in the same window, seven days each, with overlap; deploy freeze; `scripts/beta_metrics.py --days 1` read daily, the weekly read on day 7. | Research lead, operator | P9 | One protocol-2 row per participant; return windows complete | Oct 17–24, interviews to Oct 27 |
| P11 | **Read-out and decision meeting.** `scripts/pilot_report.py` on the record; counts and unknowns against the proposed gates (8/10 curiosity, 7/10 consequence, 1/2 unprompted return, 7/10 useful return); recommend a next wave or a revision. | Research lead reports; owner decides | P10 | A dated evaluation in `docs/evaluation/`; the M8 choice recorded | Oct 28–31 |

**Slip rule (proposed).** P1 and P2 are the only steps nobody but the operator
can move, and the dated sequence has no slack after them: a seven-day cohort
window, three days of return interviews and a four-day read-out fill October 17
to 31 exactly, so **P9 on October 16 is the cutoff for holding October 31**.
Each day P1, P2 or P9 slips moves every later date by the same number of days,
the read-out and the beta date included. Never recover a slip by shortening the
window, dropping interviews, compressing the read-out or trickling the cohort.
The beta date moves with the slip: a one-week slip lands on November 7, a
two-week slip on **November 14**; a longer one is re-planned, not absorbed. The
readiness record already says the calendar is not a substitute for recovery or
observed play.

## Part 2. Decisions the owner must make, and by when

Each is a yes/no the record cannot settle. Recommendations are marked as such;
none is a decision.

| | Decision | Needed by | Recommendation |
|---|---|---|---|
| A | Hold October 31 as the beta date, or reset it now | Oct 10, after P1/P2 have or have not moved | Decide on evidence of P1/P2 progress. October 31 holds only if P9 can still happen on October 16; otherwise reset by the slip (November 7 or 14) now, rather than compress the cohort, interviews or read-out later. |
| B | Is the cohort world retained research or permanent production? | Before P9 | **Production**, if P4's restore and freshness checks pass. A world promised to persist is never reset; a world labelled research can still be kept. The protocol forbids promising persistence and then wiping. |
| C | **D6 timing.** Must the identity/alias and provenance migration (ADR-029 batch 1) land before the first production history, or only before the first structural operation? | Oct 10: a migration-first answer needs the two weeks before P9 | **Before the first structural operation, not before the pilot.** The readiness record's argument holds: `world_nodes` is keyed by `(world_seed, path)` with the born name beside it, no code path renames a row, and an alias table seeded from born rows is additive. What cannot be retrofitted is provenance for a structural change, and no structural change is possible until ADR-029's write paths exist. Cost accepted: early history rows stay name-keyed, as all history is today. The assessment's Phase 0 ordering would delay a pilot already four weeks behind its protocol date. A migration-first ruling must carry, on the same date, ratification of ADR-029 batch 1's scope alone, because batch 1 cannot wait for F; see "What this plan displaces" for the re-dated schedule. |
| D | Voice model default for the pilot | Before P9 | Run P4's live probes on the current default and on the current Opus (`NESTED_WORLDS_MODEL` on staging); pick on observed quality, verify the model identifier and pricing against the official docs at that moment (CLAUDE.md external-contract rule), record the choice as an ADR-005 §4 revision. Changing the default after the pilot starts changes what the pilot measured. |
| E | Mark the four Proposed implemented contracts (ADR-019 to ADR-022, and the bounded ADR-013/014 parts realised under ADR-024/025) **Accepted as implemented**, or leave them Proposed with a reason. Separately and optionally: normalize the status wording of the implementation records ADR-024, ADR-025, ADR-027 and ADR-028, which are neither Proposed nor Accepted today | Before P9 | **Accept the four as implemented** in one documentation PR. Production history will rely on their delivery, fence and narration semantics; a Proposed status on live semantics invites relitigation from a cold start. The wording normalization is housekeeping; do it in the same PR only if the owner wants one status vocabulary. |
| F | D1–D5 (ADR-029 to ADR-033) ratification | At P11 or after | Ratify D1, D3, D5 at the read-out so November drafting can start; D2 with D1; **D4 only after pilot evidence**, as the assessment itself recommends. |
| G | D7 (one client), D8 (dollar budgets), D9 (process re-tune) | After P11 | D8 and D9 are cheap and reversible; schedule both in November. D7 waits for the cohort's device evidence and needs an ADR-005 revision. |
| H | Issue dispositions: revise #89's acceptance criteria (its per-response property-delta requirement conflicts with ADR-028's accepted/pending/partial/moot outcomes); keep #88 deferred; carry #87's unverified criteria into the pilot's orientation observations | Oct 15 (so #89 is not implemented against stale criteria) | Agent drafts the revised criteria as a comment; owner edits the issue. |

## Part 3. The parallel track: maintenance with no one-way door

Everything here is agent-executable, independently reviewable, and reversible.
Split by *when*, because a refactor in launch week is risk without reward.

**Ready now, before the cohort (small, pre-launch safe):**

- **Release preparation (P3).** Version bump, `npm audit --omit=dev` and `pip`
  dependency recheck, release notes from the `[Unreleased]` section.
- **4.9 hashed Python locks** from `pyproject.toml`, dev lock layered over the
  runtime lock. Reduces supply-chain exposure before the first deploy; no
  behavior change.
- **Probe checklist for P4** as a runbook appendix: the exact commands and the
  pass condition for each rehearsal item, so the operator's evidence is uniform.
- **Playwright device matrix**: mobile viewports, reduced motion, keyboard-only
  runs under the production CSP. Partial evidence for the 4.2 device gate;
  physical devices, Safari and assistive technology stay a human gate.
- **ADR status pass (decision E)** drafted for the owner to approve.
- **#89 criteria revision** drafted (decision H).
- **Name-keyed consumer inventory** for ADR-029 batch 1: every reader of a node
  name (history and Wayback, overlays, opened puzzles, saved positions, home and
  notes, agent memory and attention, every queue and frozen interpreter, receipt
  replay, generation from born identity). A document, not code; it is the test
  plan the readiness record requires before any alias migration.

**After the cohort window (November; avoid launch-week churn):**

- **4.5 routing extraction** from `server/handlers.py` (1,612 lines) along the
  pattern of `server/intervention_api.py`, `ideas_api.py`, `participant_api.py`,
  `situation_api.py`. Behavior-neutral, test-pinned, one module per PR.
- **D8 dollar budgets** in `server/guard.py`, keeping in-fiction degradation and
  the per-user caps; runbook §8's budget-sizing step changes with it.
- **4.1 Litestream-style continuous replication**, the first post-launch
  infrastructure batch ADR-005 names; it shrinks the loss window from one hour to
  seconds and lets the artifact cadence relax (ADR-005 "Revisit when").
- **D7 one client**: device gate evidence → ADR-005 revision → invite default to
  `/app` → explorer retirement plan. Each arrow is its own PR.
- **3.3 cohort rhythm**: a recurring gathering and the weekly `beta_metrics.py`
  read, once there is a cohort to read.
- **4.8** the cost-engineering case study, when the owner wants it.

## Part 4. After the read-out: November to January, as ratified

Nothing in this part starts without the corresponding decision in Part 2.
Dependencies are the ADRs' own; dates assume the pilot read-out on October 31.

| Order | Batch | Depends on | Doors it trips | Window |
|---|---|---|---|---|
| 0 | **Settle migration numbering.** ADR-029 and ADR-030 both claim `0028`; ADR-033 batch 1 also needs a migration and a write-once `world_meta` key. Rule: the first batch to merge takes the next free number; renumber the other drafts at ratification. | F | None | Nov, first week |
| 1 | **ADR-029 batch 1, identity.** Audit a representative authorized backup for missing born rows, duplicate names, legacy formats, orphans (readiness record); then `node_aliases` seeded from `world_nodes`, hot `node_path` columns, readers through aliases, the behavioral parity suite. | C; F for the rest of D1, or the early batch-1 ratification at C in the migration-first branch; the consumer inventory | Additive migration only; no new write path; no re-pin | Nov |
| 2 | **ADR-033 batch 1, the registry with no visible change.** `scale_charters` seeded from the literals; parity test registry ≡ literals; freeze suites prove set-1 births equal generator v2 at depths 6 and 11; `world_meta` pins the charter set version. Serial after batch 1 because both touch `multiverse/store.py` and `world_meta`. | F (D5) | Additive migration; one new write-once `world_meta` key; no re-pin | Nov–Dec |
| 3 | **ADR-030 batch 1, the render contract and the plate.** `render_keys` in `describe`, `render_assets`, object storage and `/media`, the job queue, the `plate` renderer replacing the synchronous image call, curated plates imported with provenance, dollar budgets per renderer. Absorbs the art-quality gap from the expressive-world checkpoint. | F (D3); D8 for the budget line; an explicit media budget | Additive migration; no chronicle write path; CSP unchanged if same-origin | Dec, in parallel with 4 |
| 4 | **ADR-029 batch 2, the first events.** `ERA_TURNED` with the `eras` table, `NODE_REASPECTED`, `NODE_RENAMED`, the `evolve` CLI, Wayback moments. The era-name freeze moves from read-time banks to stamped rows. | 1 | New `mutation_type` write paths through the atomic API: **covenant-level, reviewed once in the ADR**; additive `eras` migration | Dec |
| 5 | **ADR-031 batch 1, the proposal pipeline and Tier 1.** `proposals`, `proposal_decisions`, `authored_text`; validator framework reusing batch 1's; place descriptions, era annals, outward reflections; disclosure page; CLI. | F (D2); 1 | Additive migrations; **no chronicle write path**; a model-default change recorded | Dec–Jan |
| 6 | **ADR-032 batch 1, minds dark.** Only after pilot evidence and a hard dollar ceiling. | F (D4); P11 evidence | Additive migration; the heartbeat may spend money when flagged | Jan at the earliest |
| 7 | **M8: expand only demonstrated value.** The read-out chooses among a second situation in familiar geography, recognition experiments, or a social capability; #87's remainder and #88 are judged against the same evidence. | P11 | Per batch | Nov–Jan |
| 8 | **Second cohort wave**, if the gates held and the hosted gates still pass. | P11, B | None | Nov |

ADR-029 batch 3 (shape: frontier births, passages, law shifts, retirement),
ADR-030 batches 2–3, ADR-031 batches 2–3, ADR-032 batches 2–3 and ADR-033 batch
3 (kinds, the only one that is a golden re-pin) fall outside these ninety days.

### Week grid (proposed)

| Weeks | Operator and research | Agents |
|---|---|---|
| Oct 5–11 | P1, P2, P4 begins, P5 research prerequisites | P3 release PR, probe checklist, device checks for P5, hashed locks, E and H drafts |
| Oct 12–18 | P6 newcomers, P8 declarations, P9 first deploy | P7 fixes, re-cut tag, consumer inventory |
| Oct 19–25 | P10 cohort window, deploy freeze | Nothing ships; triage only |
| Oct 26–Nov 1 | Interviews, P11 read-out, decision meeting | Evaluation document, M8 brief |
| Nov | Second wave if warranted; Litestream | Routing extraction, D8, D9, ADR-029 batch 1, numbering |
| Dec | Device gate evidence, D7 ADR-005 revision | ADR-033 batch 1, ADR-030 batch 1, ADR-029 batch 2 |
| Jan | Read the chronicle's first quarter | ADR-031 batch 1; ADR-032 batch 1 only if D4 is taken |

## What this plan displaces, and what it costs

- **Pilot before migration** (decision C) rather than the assessment's Phase 0.
  Gain: people in the world two weeks sooner, on code that has not just changed.
  Cost: the first production rows are name-keyed; a later alias table seeds them
  from born rows, so nothing is lost, but the first rename needs its own chronicled
  event and alias interval before it is accepted. If the owner rules the other
  way, the dependency is re-ordered, not just delayed: ADR-029 batch 1 cannot
  wait for F, which sits at or after P11 and so behind P10 and P9. The
  migration-first ruling at C (October 10) therefore also ratifies batch 1's
  scope alone, leaving the rest of D1 to F. Batch 1 then takes about two weeks
  (the assessment's Phase 0 estimate) after the backup audit, run on the staging
  twin's downloaded artifact; P3 and P4 repeat on the migrated build; and the
  whole P9–P11 sequence shifts together: deploy about October 30, cohort
  October 31 to November 6, interviews to November 9, read-out November 10–13,
  beta date **November 14**.
- **No new capability before the read-out.** ADR-015 to ADR-018 (referential
  puzzles, spoken interaction, leaderboards, collectibles), #88 Hyperleap, M5
  expansion and ADR-032 all wait. The discovery plan's own gate says: if players
  can navigate but find no reason to return, fix the consequence/return
  experience before adding rankings or crafting.
- **Routing extraction after the cohort, not before.** A 1,612-line module is a
  maintenance cost, not a launch risk; a refactor in launch week is.
- **The evolution grammar is a quarter of engineering** and displaces M5/M6
  polish and ADR-017/018, as the assessment states. That trade is the owner's,
  at F.

## Risks and open questions

- **One operator is the critical path.** P1 and P2 are credential work nobody
  else can do; the whole October schedule hangs on them. Open question: who
  holds the Fly and Anthropic credentials, and when.
- **The research lead is a role, not a name.** The readiness record and the
  discovery plan assign by role. Open question: who observes P6 and P10.
- **The first deploy is of a build forty PRs past the last tag** with no
  production release ever cut. P4 on the staging twin is the only rehearsal of
  that; treat its restore as a required pass, not a checkbox.
- **Device evidence is Chromium-only.** The readiness record requires the
  applicable browser, keyboard, accessibility and fallback checks for every
  device on the cohort's list before recruitment. P5 records the list and the
  checks; a device that cannot be verified in time is excluded from the cohort,
  never admitted on written acceptance. Mobile Safari and assistive technology
  are the likely cases, and the Playwright matrix in Part 3 does not stand in
  for a physical device.
- **Model quality is unmeasured live.** Intention interpretation is
  fixture-tested only; P4's probes are the first live read. A poor result is a
  fix (prompting, model choice at D) before P9, not a reason to skip the pilot.
- **Small denominators.** With 8–12 people, one or two non-returns move the
  return gate by ten points or more. P11 reports counts and unknowns and does
  not recruit selectively to cross a threshold.
- **The 0028 collision** is trivial to fix and easy to forget; it is order 0 in
  Part 4 so no two batches are built against the same number.

## How to read this document against the others

The [readiness record](../evaluation/2026-10-03-beta-readiness.md) owns the
gates and their evidence; the [pilot protocol](../evaluation/2026-09-12-pilot-protocol.md)
owns the study; the [runbook](../infrastructure/fly-deployment.md) owns the
operator steps; the [assessment](../evaluation/2026-10-03-ambition-and-boundaries.md)
owns the decision agenda and its arguments; ADR-029 to ADR-033 own their own
batch tables. This plan only orders them and dates the order. Where it
disagrees with a source it says so (decision C). When a step lands, strike it
here and update the [roadmap index](README.md).
