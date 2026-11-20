# Owner decisions — 20 November 2026: the owner's batch

*Recorded 2026-11-20 against `main` at `372d77f` (#181) for the owner, Mark
Weeks. Earlier that day Claude Code planned the next parallel batch for the
three coding agents ([batch plan](batch-plan-2026-11-20.md)). The plan's
section 6 lists seventeen items, O1 to O17, that only the owner can do or
decide. The owner then wrote:*

> For the Owner's Batch, make a reasonable recommendation for each item and
> formally adopt the decision.

**Provenance.** As with the [18 November record](owner-decisions-2026-11-18.md),
the instruction was given in a Claude Code working session, which cannot be
checked from the repository. The owner's merge of the pull request that adds
this page is the verifiable act. Every recommendation below was written by the
agent; the owner's sentence above adopts them. Anything unwanted should be
struck before merging.

**What this page is not.** A record cannot do six things, and this one does
not try:

1. **Merge.** `AGENTS.md` requires the owner's explicit instruction for each
   pull request. O11 fixes an order, not a merge.
2. **Approve a golden re-pin.** Approval is given in the task or pull request
   that changes the pins, after the owner reads the exact diff; a record does
   not pre-approve one (`AGENTS.md`, "The golden pins now describe births").
   O16(a) gives guidance for that read, not approval.
3. **Approve working-rule wording.** The three `AGENTS.md` wordings of the
   18 November record (section 5, entry 17) are approved in the working-rules
   pull request. O16(d) requests that pull request.
4. **Perform an act.** Creating accounts, setting secrets, deploying, minting
   keys, running rehearsals, posting on GitHub and recruiting stay the owner's
   acts. This page fixes how and by when.
5. **Supply a value only the owner holds.** Contact address, the names of the
   second operator and testers, the owner's country, account identifiers and
   secrets. Where one is needed, the page says so and says what form it takes.
6. **Make a read-out declaration in advance.** World status, the exception
   list, the cohort date and the alignment answer depend on what the watch
   shows (18 November record, items 10, 37, 39). O17 records the defaults to
   bring to the read-out.

It changes no working rule, ADR status line or status document. It builds,
deploys and spends nothing.

## Takeaway

The watch runs on the twin in the week of 7 December, with AI on through the
incumbent provider's Chat Completions-compatible endpoint if Grok Bot's check
passes. Spend is bounded at $15 a day, $3 to $5 a day per participant, and $150
at the provider. Six pull requests reach the owner's read in two waves of three.
The owner's critical path is the Fly deploy by 24 November, the route, data note
and model ids by 25 November, and the second operator by 27 November.

## Adopted decisions

"Agent judgment" marks a value the 18 November record did not already carry; it
is the recommendation the owner adopted with the sentence above.

### O1. Batch go, ADR-036 batch 1b and the review queue

**Adopted.**

- **Go.** The batch runs as planned: C0, C1 and C2 (Claude Code); X1 then X2
  (Codex); G1, G2 and G3 (Grok Bot).
- **ADR-036 batch 1b goes to Codex** (agent judgment). The per-player send-away
  is a Puzzle-surface change with a small server rule, and keeping it in one
  pull request with one author follows the "one feature, one pull request"
  rule. This assignment overrides the default that the server-side rule's
  concern owns the pull request; `AGENTS.md` lets an explicit owner assignment
  win. It takes the client bundle after L5: X1, X2, L5, then 1b. Claude Code does
  the executing review.
- **The owner reads at most three pull requests at a time**, applying item 45's
  limit to this batch now. Item 45 becomes a working rule only through the
  working-rules pull request (O16(d)). The batch's own dependencies already give
  two waves:
  - Wave 1: C1, C2 and G1.
  - Wave 2: X2 (after X1), G2 (after G1) and G3 (after C1), as wave-1 slots
    clear.

  Agents still prepare and mark ready on their own schedule. C0 and X1 have no
  one-way door and do not take a slot.

**Unblocks:** every agent prompt; the bundle queue after X2.

### O2. Fly staging twin and check key

**Adopted.** The owner completes `fly-deployment.md` §3a steps 1–5 by
**Tuesday 24 November**. That is four days after item 1's aim of 20 November,
which has not happened. It covers:

- the Fly account and billing;
- the `enfolded-staging` app;
- `fly tokens create deploy -a enfolded-staging`;
- a main-only GitHub `staging` environment holding `FLY_API_TOKEN_STAGING`;
- the first terminal deploy.

The check key is minted from a terminal, never in CI, and revoked once O12's
checks pass.

**Owner act:** all of the above. **Unblocks:** G3's live run, every rehearsal in
O13, and the hosted proof of the 18+ question at sign-up.

### O3. Watch model route, data-use note and models

**Adopted.**

- **Route.** The watch uses the incumbent text provider (Anthropic, the
  provider behind the `anthropic` adapter's defaults) through its Chat
  Completions-compatible endpoint, under the `openai_compatible` adapter. This
  follows ADR-035 and item 24. **ADR-035 is accepted for that one endpoint when
  G1's endpoint-check record shows the five adapter requirements met:**
  - structured outputs for intention and moderation;
  - `store: false`;
  - the max-tokens parameter;
  - usage counts for settlement;
  - a reported model for `resolved_models`.

  The choice ends with the disposable twin (item 24).
- **Fallback** (agent judgment). If the check fails on a requirement the adapter
  cannot work around, the owner chooses another vendor's compatible endpoint
  that passes the same check. No new adapter or controlled native transport is
  built for the watch. That transport stays the cohort alternative on record.
- **Data-use note.** One note covers:
  - one account, under its named terms, at one exact endpoint (item 25);
  - these data classes: Speak and agent-voice exchanges, free-text intentions,
    and shared lines sent for classification;
  - excluded classes, never sent: report text, private journal notes,
    unpublished profile text, and chat (item 30).

  No Enfolded data trains any model. Where the account offers reduced provider
  retention, the owner requests it (agent judgment; *not verified* that this
  account offers it).
- **Models** (agent judgment):
  - Moderation uses the adapter's current moderation default,
    `claude-haiku-4-5` (`docs/development/agent-runtime.md`).
  - Voice and intention use the current default, `claude-opus-4-8`, only if
    O4's reservation test passes at the per-participant ceiling. Otherwise they
    use a smaller model from the same vendor, chosen from G1's report.
  - G1 records the resolved ids, and the policy file pins them (item 27).

  *Not verified:* that these ids are served unchanged at the compatible
  endpoint; G1's check answers it.

**Owner act:** sign the note, set the staging-only key with `fly secrets`, and
confirm the ids against G1's report, by **Wednesday 25 November** or the day
after G1's check record is posted, whichever is later. **Unblocks:** filling
G1's policy, G3's live run, the provider name in the notice (O6), and L5's
disclosure text.

### O4. Dollar amounts and ledger retention

**Adopted.**

| Value | Adopted |
|---|---|
| Global ceiling | **$15 a day** (item 26) |
| Per-participant ceiling | **$3 a day**, which may rise to **$5** without a further decision if G1's reservation report shows that $3 admits fewer than 20 full-context voice reservations (agent judgment) |
| Provider console limit | **$150**, the outer bound (item 26) |
| `ledger_retention_days` | **35** (agent judgment): one monthly invoice reconciliation with margin. Destroying the twin ends the watch's ledger sooner |

The global ceiling stays at $15 in either case: three testers at $5 fit under
it. If $5 still admits fewer than 20 voice reservations, the voice model steps
down (O3). The ceilings do not rise further without a new owner decision.

**Owner act:** confirm the amounts in the policy file against G1's report.
**Unblocks:** committing and approving the policy file.

### O5. Call and cap integers (item 29)

**Adopted**, each set as a deploy secret. Each neutral name and its legacy name
are set to the same integer in one `fly secrets set`.

| Secret | Value |
|---|---|
| `NESTED_WORLDS_VOICE_DAILY_CALLS` and `NESTED_WORLDS_ANTHROPIC_DAILY_CALLS` | 1,000 |
| the two `_PER_USER` voice names | 150 |
| `NESTED_WORLDS_MODERATION_DAILY_CALLS` | 2,000 |
| `NESTED_WORLDS_MODERATION_DAILY_CALLS_PER_USER` | **120** |
| `NESTED_WORLDS_MODEL_ACTIONS_PER_USER` | 200 |

The per-player classify cap is 120 rather than item 29's default of 60 (agent
judgment). Item 30 makes every shared Speak, Ideas and profile line a classify
call, so a long session would reach 60. The cost is small on the moderation
model, and the model-action cap of 200 still binds first, at about 100 Speak
exchanges. The names above are those the code reads on `main`. Images stay off
for the watch: no image route is approved under O3, so no image provider key is
set and the image caps are left unset (agent judgment).

**Owner act:** set them before the twin admits a tester. **Unblocks:** C1's
holds behaving as intended on the twin.

### O6. Notice and community-policy values (item 6)

**Adopted.**

- **Contact address.** A dedicated project address that the owner reads daily,
  not a personal inbox (agent judgment). *Owner value.*
- **Destroy date.** Seven days after the last watch session. With the sessions
  in O8 that is **Thursday 17 December 2026**, or Friday 18 December if the
  spare day is used. An open or acknowledged report extends it (item 5).
- **Provider.** The vendor of O3's route.
- **Admission.** Adults 18 or older in the owner's own country (item 36). *Owner
  value: the country.*
- **`backup_notice` wording:** "Backup copies of this test world are kept in a
  private storage bucket. The operator deletes them after the test world is
  destroyed. No deletion date is promised." Item 12 bars any date until the
  erasure procedure has been checked (O7).

**Unblocks:** C2's placeholders and the twin's first boot with chat and Report
on.

### O7. Backup bucket and the delete lock (items 11, 12)

**Adopted** (agent judgment, within item 12):

- **Backend.** Cloudflare R2, the runbook's example backend
  (`docs/infrastructure/backup-bucket.md`): a private bucket with no public URL
  and no custom domain.
- **Retention.** `ENFOLDED_BACKUP_RETENTION_DAYS=30`. The lifecycle rule on
  `offhost/` is set to 37 days (retention plus 7), as the bucket runbook
  requires.
- **Delete lock.** Seven days, counted from each object's upload.
- **Versioning.** No object versioning, so a delete by key leaves no older
  version behind.
- `ENFOLDED_BACKUP_REQUIRED=true` is set as a repository **variable**.
- **Before any notice gives a backup deletion date**, the operator checks the
  erasure procedure on the chosen bucket and records the result: delete after
  the lock expires, then confirm no copy can be retrieved. *Not verified:* that
  R2's lock counts from upload and that R2 keeps no hidden versions. The check
  settles both. Until then O6's wording stands.

**Owner act:** the R2 account, bucket and token (as secrets); the variable.
**Unblocks:** C2's teardown step, the backup proof and P3.

### O8. People and dates

**Adopted.**

- **Second operator.** One adult the owner trusts, named by **Friday
  27 November**, before any recruiting (item 31). They read the queues and the
  log and can use the kill switches. Sanctions, redaction and deletion stay with
  the owner. *Owner value: the person.*
- **Testers.** Two or three adults who have not seen Enfolded before, on desktop
  Chromium, recruited by **Tuesday 1 December** (agent judgment). *Owner value:
  the names.*
- **Sessions** (agent judgment, within item 39's 11 December bound):
  - **Tuesday 8 December**: two testers overlapping, which exercises chat,
    co-solving and Report (item 4).
  - **Thursday 10 December**: the remaining tester, with Friday 11 December
    kept as the spare day.
- **Read-out:** **Monday 14 December**.

**Unblocks:** the watch kit, the capacity rehearsal and recruiting.

### O9. Clearing the latched spend stop (items 3, 28)

**Adopted.**

- **For the watch twin:** G2's documented hand-SQL clear. It needs no migration
  and is reversible.
- **Before any live route on a kept world:** an ADR-039 revision that adds an
  audited clear command and its migration (agent judgment). Hand SQL on a kept
  world's volume is not acceptable there. The revision is Grok Bot's next batch
  and needs the migration slot.
- **A clear requires:**
  1. the provider console's spend for that UTC day, recorded;
  2. the latch reason;
  3. every `reserved` row resolved;
  4. a dated entry in the private operator log.

  A clear never refunds the day's spend and never shortens ledger retention. A
  restart or a re-created twin is not a clear.
- **Rehearsal:** on a separate throwaway Fly app, by **Friday 4 December**,
  before the first session (item 28). **ADR-039 is accepted once that rehearsal
  passes.** The next records or status pull request records the acceptance on
  the owner's instruction.

**Unblocks:** G2's evidence rule and an AI-on watch that survives a latch.

### O10. The old map's path and the Map view reading (item 2)

**Adopted.**

- **The current explorer moves to `/map`** and stays there until the cohort
  read-out. It is frozen except for privacy, safety and correctness fixes.
- **"Shared React Map view"** means the world map rendered in React inside the
  `/app` client. It shares `/app`'s session, notice gate, Travelers panel and the
  single Speak, Puzzle and Act surfaces, and it becomes the landing view at `/`.
  It replaces SceneView's "World map" link rather than adding a second
  navigation surface.

The owner may still adjust either in X1's or X2's review.

**Unblocks:** X1 and X2.

### O11. Merge order

**Adopted as order only:**

1. C0
2. X1
3. C1
4. C2
5. G1
6. X2
7. G2
8. G3

C1 merges before G3. Each merge still needs the owner's instruction on that pull
request after reading its irreversibility check, and auto-merge is never
enabled.

### O12. Deploy-time steps on the twin

**Adopted as written in the plan.**

1. Install the approved private community policy (`--policy
   /private/community-policy.json`) and the approved model policy.
2. With the check key, verify `/community`, `/participation` and `ai: true`.
3. Revoke the check key.

The owner names the deployed commit in a comment on Claude Code's F2
evidence-record pull request (selected-commit evidence and the installed-wheel
smoke). **Owner act:** the deploy and the checks.

### O13. Operator rehearsals

**Adopted.** These run on the twin between G3's merge and Friday 4 December,
each logged with its date in the private record:

- G3's live probes: success, hold and failure;
- the single-grader rubric run, recorded as a deviation from the two-grader rule
  (item 27);
- a capacity rehearsal with three simultaneous clients;
- block and unblock;
- sanction suspend and lift;
- `python main.py redact`;
- an urgent-escalation drill with the second operator;
- the twice-daily checks of the open and acknowledged report queues;
- `fly machine stop` and restart;
- `beta_metrics.py --days 1`;
- confirming that operator-key entry demands the 18+ acknowledgement.

### O14. Observability and alerts (items 11, 13)

**Adopted.**

- **Sentry** is on for the twin, with `SENTRY_ENVIRONMENT=staging` and frame
  locals off, and a line in the notice (item 13).
- **Alerts** go to the O6 project address, with the second operator copied
  (agent judgment).
- **Backup dispatch** uses a fine-grained GitHub token with Actions write on
  this repository only and a 90-day expiry. Its rotation date goes in the
  operator log. This was chosen over a GitHub App as the smaller setup for a
  pilot (agent judgment).
- **Freshness** is checked by a separately hosted heartbeat monitor that alerts
  when no fresh backup has reported in for longer than the one-hour bound plus
  one check interval. One scheduler that both dispatches and checks cannot raise
  its own absence (item 13).

**Owner act:** the DSN secret, the scheduler and monitor accounts, and the
token.

### O15. Records only the owner can supply

**Adopted.**

- **The 15 November decision page** (item 42) is committed verbatim as
  `docs/roadmap/owner-decisions-2026-11-15.md` in a records pull request. The
  owner supplies the text, and the agent formats it without rewording.
- **Copilot:** item 46 stands. No budget is set, and work proceeds without
  Copilot review where it cannot run.
- **Issue #89 hold note.** The owner posts it (item 47). Draft, for the owner to
  edit:

  > Held until the first cohort has entered (`AGENTS.md`, "Current delivery
  > priority"). Scale-native actions shipped in #105, and puzzle consequences
  > now overlap ADR-036 and the puzzle redesign of the 18 November record
  > (item 23). This epic is re-scoped against them after the cohort read-out;
  > no work starts on it before then.

### O16. Setting up the next agent batch

**Adopted.**

- **(a) Naming re-pin (ADR-041).** Not approved here. Guidance for the owner's
  read in the naming pull request: approve if the pin diff changes only names
  (cast and node display names, with addresses moved to paths as ADR-041
  states) and no other birth field.
- **(b) Puzzle design record (item 23).** Claude Code re-derives the draft in
  the repository from D-C, D-I and D-J: ten sample puzzles for each of the four
  new kinds and for the first puzzle. It drops look-ups, and A10, D6 and D10 stay
  held. The owner judges the samples in that pull request. If the owner still
  has the original draft, it is used instead and committed as given.
- **(c) ADR-037 question 5, second half** (agent judgment, taking ADR-037 D3's
  proposed default):
  - With AI on, an AI traveler's honesty answer is kept as that agent's chat
    lines are kept (D8). It stays out of the history fed to other voices, as
    already decided on 2026-11-10.
  - With AI off, nothing is stored.
  - A repeat from the same asker to the same agent within ten minutes is stored
    nowhere.

  This unblocks the ADR-037 chat batch.
- **(d) Working-rules pull request.** Requested. Claude Code prepares it after
  C0 merges, as a pull request of its own. It carries:
  - item 45's two rules and its three-pull-request limit;
  - the ADR-019 to ADR-022 pointer;
  - the three wordings of the 18 November record's entry 17, for the owner's
    approval there.
- **(e) Puzzle salt (ADR-038).** The owner sets the staging salt as a
  `fly secrets` value before the first staging deploy that carries B1, and the
  production salt with the first-deploy secrets (item 22).

### O17. Recruiting and the read-out

**Adopted.**

- **Recruiting starts once all of these hold:**
  - the second operator is named;
  - C1, C2 and G1 have merged;
  - the twin is deployed with O12's checks passed.
- **Playtest tripwire** (item 38), confirmed now as written there:
  - a puzzle family with five or more attempted puzzles and none solved, or an
    overall median interest rating under 3, opens a fix before invitations go
    beyond the first cohort;
  - it is read at the watch read-out and at each cohort read.
- **Defaults to bring to the 14 December read-out.** These are not declared
  here:
  - **World status:** production for the cohort world, declared only if a
    downloaded backup restores into isolated staging and item 11's seven-day
    bound has passed (item 10).
  - **Exception list:** item 37's form.
  - **Cohort route:** O3's route continues if the watch showed no unexplained
    hold or failure.
  - **Cohort date:** the earliest date after which ADR-041 naming, ADR-036
    batches 1b and 2, the puzzle salt and the puzzle redesign have landed.
  - **Alignment:** answered there.
- **Terms page (item 36).** Claude Code drafts the combined terms-and-notice
  page in its next batch for the owner to edit. Cohort membership stays the
  owner's.

## Owner timeline

| By | Owner act | Item |
|---|---|---|
| Tue 24 Nov | Fly account, staging app, deploy token, GitHub `staging` environment, first deploy | O2 |
| Wed 25 Nov, or the day after G1's check record | Sign the data-use note, set the staging key, confirm model ids | O3 |
| Fri 27 Nov | Name the second operator; R2 bucket and token; Sentry DSN; scheduler and monitor | O7, O8, O14 |
| On G1's report | Confirm the amounts in the policy file; set the cap secrets | O4, O5 |
| Tue 1 Dec | Recruit two or three testers | O8, O17 |
| Fri 4 Dec | Deploy-time checks; operator rehearsals; ADR-039 rehearsal on a throwaway app | O9, O12, O13 |
| Tue 8 Dec, Thu 10 Dec | Watch sessions (Fri 11 Dec spare) | O8 |
| Mon 14 Dec | Read-out | O17 |
| Thu 17 Dec (Fri 18 Dec if the spare day is used) | Destroy the twin unless a report is open; delete its backups by hand | O6, item 12 |

Ongoing: read and merge pull requests in O11's order, three at a time (O1);
post the #89 note (O15); supply the 15 November page (O15).
