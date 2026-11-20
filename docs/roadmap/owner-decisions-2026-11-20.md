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
   shows (18 November record, items 10, 37 and 39, and section 3). O17 records
   the defaults to bring to the read-out.

It changes no working rule, ADR status line or status document. It builds,
deploys and spends nothing.

## Takeaway

The watch runs on the staging twin on 8 and 10 December, with AI on through the
incumbent provider's Chat Completions-compatible endpoint if Grok Bot's check
and the live probe pass. Spend is bounded at $15 a day, $3 to $5 a day per
participant, and $150 at the provider. The voice model is chosen by a stated
reservation rule, not by default. Pull requests that need the owner's
one-way-door read reach him at most three at a time.

The owner's critical path:
- the Fly deploy by 24 November;
- the route, data note and model ids by 25 November;
- the second operator and accounts by 27 November;
- G3 merged by 2 December;
- deploy-time checks and rehearsals by 4 December.

## Adopted decisions

"Agent judgment" marks a value the 18 November record did not already carry.
"Departs from item N" marks a value that changes an answer of that record; the
reason is given each time. Both are recommendations the owner adopted with the
sentence above.

### O1. Batch go, ADR-036 batch 1b and the review queue

**Adopted.**

- **Go.** The batch runs as planned: C0, C1 and C2 (Claude Code); X1 then X2
  (Codex); G1, G2, G3 and G4 (Grok Bot). G4, which keeps the backup job's
  token in a main-only environment, was added after Codex's review of the
  first version (O7).
- **ADR-036 batch 1b goes to Codex** (agent judgment). 1b is more than a
  Puzzle-surface change. ADR-036 lists:
  - the fold;
  - the away checks in both handlers;
  - `warned` receipts;
  - the daily cap;
  - marking `PUZZLE_FAILED` inside the attempt's transaction;
  - that kind's other readers;
  - the runbook's rollback floor;
  - the away state in both clients.

  Two reasons send it to Codex:
  - Its client half needs the bundle, and Codex holds the bundle queue.
  - Claude Code's next batch already carries naming, the salt and the puzzle
    design record.

  `AGENTS.md` lets an explicit owner assignment override the default that the
  server-side rule's concern owns the pull request. 1b takes the client bundle
  after L5: X1, X2, L5, then 1b. Claude Code does the executing review. Item 21
  (wrong-guess text, Claude Code) rebases after 1b, because both change the
  attempt handler.
- **Review queue** (agent judgment, narrowing item 45). At most three pull
  requests that need the owner's one-way-door read wait on him at a time.
  Pull requests with no door and only a merge to wait for (C0, X1) are outside
  the limit. Item 45's "at most three pull requests wait on the owner" becomes a
  working rule only through the working-rules pull request (O16(d)), which can
  settle the wider reading. The batch's own dependencies give two waves:
  - Wave 1: C1, C2 and G1.
  - G4 joins wave 1 as soon as a slot clears, because it must merge before the
    twin collects participant text.
  - Wave 2: X2 (after X1), G2 (after G1) and G3 (after C1), as wave-1 slots
    clear.

  Agents still prepare and mark ready on their own schedule.

**Unblocks:** every agent prompt; the bundle queue after X2.

### O2. Fly staging twin and check key

**Adopted.** By **Tuesday 24 November**, four days after item 1's aim of
20 November, which has not happened, the owner completes these steps of
`fly-deployment.md` §3a:

1. **Step 1:** the Fly account and billing.
2. **Step 2:** the `enfolded-staging` app and its `enfolded_data` volume.
3. **Step 3:** `fly tokens create deploy -a enfolded-staging`, stored in a
   main-only GitHub `staging` environment as `FLY_API_TOKEN_STAGING`.
4. **Step 4:** the first terminal deploy. As that step requires, it is a
   disposable world with AI and images disabled and no provider keys; AI is
   turned on later through the approved policy (O12).
5. **Step 5, first half:** the check key, minted from a terminal and never in
   CI.

Tester keys, the second half of step 5, are minted only once O8 names the
testers and O12's checks have passed. Minting the check key closes the gate,
and revoking keys later does not reopen it. The check key is revoked once O12's
checks pass. O13 uses its own key.

**Owner act:** all of the above. **Unblocks:** G3's live run, every rehearsal in
O13, and the hosted proof of the 18+ question at sign-up.

### O3. Watch model route, data-use note and models

**Adopted.**

- **Route.** The watch uses the incumbent text provider (Anthropic, whose model
  ids are the `anthropic` adapter's defaults) through its Chat
  Completions-compatible endpoint, under the `openai_compatible` adapter. This
  follows ADR-035 and item 24, and the choice ends with the disposable twin
  (item 24).
- **ADR-035 acceptance.** ADR-035 is accepted for that one endpoint when two
  records together show the five adapter requirements met: G1's endpoint-check
  record and the first live run of G3's probe on the twin (O13). A desk check
  cannot confirm the requirements that need a live response. The five are:
  1. structured outputs for intention and moderation;
  2. `store: false`;
  3. the max-tokens parameter;
  4. usage that includes the prompt, completion and cached-token counts
     (`prompt_tokens_details.cached_tokens`), so that calls settle instead of
     staying "uncertain" at their full reservation;
  5. a reported model for `resolved_models`.

  G3's live run counts toward acceptance only if every probed call settles
  (status `settled`) with usage counts and an approved reported model. One
  `uncertain` call is a failed requirement 4. If that evidence is consistently
  absent, the fallback below applies; a smaller model does not cure it. The
  next records or status pull request records the acceptance on the owner's
  instruction.
- **Fallback** (agent judgment). If the endpoint fails a requirement the adapter
  cannot work around, the owner chooses another vendor's compatible endpoint
  that passes the same checks. No new adapter or controlled native transport is
  built for the watch; that transport stays the cohort alternative on record.
- **Data-use note.** One note covers one account, under its named terms, at one
  exact endpoint (item 25).
  - **Data classes sent:**
    - Speak and agent-voice exchanges;
    - free-text intentions;
    - every shared Speak, Ideas and published-profile line, for classification
      (item 30);
    - chat lines and puzzle free text that the local screen marks ambiguous, for
      classification only;
    - world content in prompts: node names, properties and history.
  - **Never sent:** report text, private journal notes and unpublished profile
    text.
  - No Enfolded data trains any model. Where the account offers reduced provider
    retention, the owner requests it (agent judgment; *not verified* that this
    account offers it).
- **Models** (agent judgment). The `openai_compatible` adapter has no default
  model, so every id is set explicitly: `NESTED_WORLDS_MODERATION_MODEL`, and
  `NESTED_WORLDS_MODEL` or each task's own variable. Each id is pinned in the
  policy file with its resolved id (item 27).
  - **Moderation:** `claude-haiku-4-5`, the `anthropic` adapter's moderation
    id. It is a starting point, not an endorsement (`AGENTS.md`, "Provider and
    model optionality").
  - **Voice and intention:** the largest model of that vendor that passes the
    reservation rule in O4. The `anthropic` adapter's voice id,
    `claude-opus-4-8`, is tried first. At a full-context reservation it is
    *expected* to fail the rule, so the likely outcome is a smaller model
    (inferred from list prices; not verified live).

  *Not verified:* that these ids are served unchanged at the compatible
  endpoint. G1's check and G3's probe answer it.

**Owner act:**
- sign the note;
- set the staging-only key and the model variables with `fly secrets`;
- confirm the ids against G1's report.

These are due by **Wednesday 25 November**, or the day after G1's check record
is posted, whichever is later. **Unblocks:** filling G1's policy, G3's live run,
the provider name in the notice (O6), and L5's disclosure text.

### O4. Dollar amounts, ledger retention and the reservation rule

**Adopted.**

| Value | Adopted |
|---|---|
| Global ceiling | **$15 a day** (item 26) |
| Per-participant ceiling | **$3 a day**, which may rise to **$5** under the reservation rule below (agent judgment) |
| Provider console limit | **$150**, the outer bound (item 26) |
| `ledger_retention_days` | **35** (agent judgment): one monthly invoice reconciliation with margin. Destroying the twin ends the watch's ledger sooner |

**Reservation rule** (agent judgment). How spend is accounted:
- Each call reserves its full-context worst case, the provider's maximum input
  at the highest input price plus maximum output (`consciousness/model_policy.py`,
  `reserve_microusd`).
- A settled call is then charged its actual cost (`persistence/model_spend.py`,
  `settle`).
- A participant is refused once less than one reservation of their ceiling
  remains.

So the number that matters is the size of one reservation against the ceiling,
not how many reservations fit. A voice or intention model qualifies when one of
its reservations is **at most a third of the per-participant ceiling**: at most
$1.00 at $3, or at most $1.67 at $5. That leaves at least two thirds of the
ceiling usable.

The rule runs over the vendor's models that pass G1's endpoint check, separately
for voice and for intention:

1. Let A be the largest model that qualifies at $3, and B the largest that
   qualifies at $5.
2. If B is larger than A, or A does not exist, the ceiling is $5 and B is used.
3. Otherwise the ceiling stays at $3 and A is used.
4. If no model qualifies even at $5, that task's route is not enabled. The task
   runs AI-off under the authored fallbacks, and the owner decides again.
   Neither ceiling rises.

The per-participant ceiling is the higher of the two tasks' results. Calls that
stay "uncertain", charged at their full reservation, are an endpoint failure
under O3, not a model choice. The global
ceiling stays at $15, because three testers at $5 fit under it, and at most two
share a day. The ceilings do not rise beyond these values without a new owner
decision.

**Owner act:**
- Confirm the global and per-participant amounts and the chosen models in the
  policy file against G1's report.
- Separately, set the $150 spend limit on the provider account before the first
  paid probe or rubric run, and record its date in the private log. The policy
  file has no field for it (`consciousness/model_policy.py` accepts only the two
  daily limits), so the server neither knows nor enforces it.
- If the provider offers only alerts and no hard limit, record a replacement
  decision before any paid call.

**Unblocks:** committing and approving the policy file.

### O5. Call and cap integers (item 29)

**Adopted.** Each value is set as a deploy secret. A neutral name and its legacy
name are set to the same integer in one `fly secrets set`.

| Secret | Value |
|---|---|
| `NESTED_WORLDS_VOICE_DAILY_CALLS` and `NESTED_WORLDS_ANTHROPIC_DAILY_CALLS` | 1,000 |
| `NESTED_WORLDS_VOICE_DAILY_CALLS_PER_USER` and `NESTED_WORLDS_ANTHROPIC_DAILY_CALLS_PER_USER` | 150 |
| `NESTED_WORLDS_MODERATION_DAILY_CALLS` | 2,000 |
| `NESTED_WORLDS_MODERATION_DAILY_CALLS_PER_USER` | **120** |
| `NESTED_WORLDS_MODEL_ACTIONS_PER_USER` | 200 |

**The per-player classify cap is 120** (departs from item 29's default of 60).
Item 30 makes every shared Speak, Ideas and profile line a classify call, so a
long session would reach 60. The extra calls cost little on the moderation
model.

**Which cap binds first.** Among the call caps, the model-action cap of 200
does, at about 100 Speak exchanges (two model actions each). The dollar ceiling
may bind earlier; G1's report shows where.

The names above are those the code reads on `main` (`server/guard.py`).

**Images stay off for the watch** (agent judgment). The controlled policy does
not route images, so no image provider key is set and the image caps are left
unset.

**Owner act:** set the secrets before any tester is admitted. **Unblocks:** C1's
holds behaving as intended on the twin.

### O6. Notice and community-policy values (item 6)

**Adopted.**

- **Contact address.** A dedicated project address that the owner reads daily,
  not a personal inbox (agent judgment). *Owner value.*
- **Destroy date.** Seven days after the last watch session (item 5):
  - **Thursday 17 December 2026** with the sessions in O8;
  - Friday 18 December if the spare day is used;
  - Tuesday 15 December if only two testers are recruited and both sit on
    8 December.

  An open or acknowledged report extends it (item 5).
- **Provider.** The vendor of O3's route.
- **Admission.** Adults 18 or older in the owner's own country (item 36). *Owner
  value: the country.*
- **`backup_notice` wording.** The served notice renders it after "Copies in
  backups are removed when those backups are deleted." It reads:

  > Backup copies of this test world are kept in a private storage bucket. They
  > stay until the operator deletes them after the test world is destroyed; no
  > deletion date is promised. The host also keeps its own snapshots of the
  > world's disk for about five days, and the operator deletes any copy
  > downloaded for testing.

  No date or age limit is given: item 12 bars one until the erasure check in O7
  has been done and recorded. O7's 37-day lifecycle rule stays as an operator
  backstop and is not promised. Once the check passes, the notice may state the
  lifecycle limit and what the delete lock counts from.

**Unblocks:** C2's placeholders and the twin's first boot with chat and Report
on.

### O7. Backup bucket, lifecycle and the delete lock (items 11, 12)

**Adopted.**

- **Backend.** Cloudflare R2, the runbook's example backend
  (`docs/infrastructure/backup-bucket.md`): a private bucket with no public URL
  and no custom domain.
- **Retention.** `ENFOLDED_BACKUP_RETENTION_DAYS=30` (item 12).
- **Delete lock.** Seven days, counted from each object's upload (agent
  judgment; item 12 left it undefined).
- **Lifecycle rule:** 37 days on `offhost/`, retention plus 7, as the bucket
  runbook requires (**departs from item 12's "no lifecycle rule"**). The
  runbook asks for one, and it removes the twin's copies even if the hand
  deletion is missed. The cost is the runbook's warning: once the schedule
  stops, the rule also removes the last copy after 37 days.
- **Versioning.** None. A delete by key then leaves no older version (*not
  verified* for R2; see below).
- **Repository settings:**
  - variables: `ENFOLDED_BACKUP_APP=enfolded-staging` (unset, it backs up
    `enfolded-beta`) and `ENFOLDED_BACKUP_S3_REGION=auto`;
  - the bucket secrets: access key id, secret key, bucket and endpoint;
  - the read-only key pair for the health check;
  - `ENFOLDED_BACKUP_REQUIRED=true`, set as a **variable** only after a manual
    dispatch has stored a real object.
- **The backup job's Fly token.**
  - **Why it is sensitive.** The backup workflow reads `FLY_API_TOKEN`
    (`backup.yml:43`) and runs `flyctl ssh console` and `flyctl ssh sftp get`.
    A token that can do that can read testers' private chat and reports on the
    twin. A repository secret is readable by a workflow on any branch
    (`fly-deployment.md` §3a step 3), so it is never a repository secret while
    the twin holds participant data.
  - **This batch.** Grok Bot's G4 adds a main-only `backup` environment to the
    job, and the owner stores the token there. G4 touches deployment, so it
    waits for the owner's read.
  - **Which token.** A token with SSH and sftp but no deploy authority, if Fly
    provides one (*not verified*; G4 checks). Otherwise
    `fly tokens create deploy -a enfolded-staging`. Revoked when the twin is
    destroyed.
  - **Until G4 merges,** the twin runs without chat and Report, or without
    off-host backup.
- **Erasure check.** Before any notice gives a backup deletion date, the
  operator checks the erasure procedure on this bucket and records the result:
  delete after the lock expires, then confirm no copy can be retrieved. *Not
  verified:* that R2's lock counts from upload and that R2 keeps no hidden
  versions; the check settles both. Until then O6's wording stands.

**Owner act:** the R2 account, bucket and tokens; the settings above. **Unblocks:**
C2's teardown step, the backup proof and P3.

### O8. People and dates

**Adopted.**

- **Second operator.** One adult the owner trusts, named by **Friday
  27 November**, before any recruiting (item 31).
  - They read the queues and the log and can use the kill switches.
  - Sanctions, redaction and deletion stay with the owner.
  - *Owner value: the person.*
- **Testers.** Two or three adults who have not seen Enfolded before, on desktop
  Chromium (agent judgment). Lined up by **Tuesday 1 December**; invited and
  admitted only under O17's conditions. *Owner value: the names.*
- **Sessions** (agent judgment, within item 39's 11 December bound):
  - **Tuesday 8 December**: two testers overlapping, which exercises chat,
    co-solving and Report (item 4).
  - **Thursday 10 December**: the third tester, if there is one.
  - Friday 11 December is spare. If G3 has not merged by Wednesday 2 December,
    the 8 December session moves to the 10 and 11 December slots.
- **Read-out:** **Monday 14 December**.

**Unblocks:** the watch kit, the capacity rehearsal and recruiting.

### O9. Clearing the latched spend stop (items 3, 28)

**Adopted.**

- **For the watch twin:** G2's documented hand-SQL clear, run only after a
  fresh backup. It needs no migration.
- **Before any live route on a kept world:** an ADR-039 revision that adds an
  audited clear command and its migration (agent judgment). Hand SQL on a kept
  world's volume is not acceptable there. Grok Bot builds it after ADR-041
  naming's migration (0034) merges, because one migration pull request is open
  at a time and the plan gives naming the slot first.
- **A clear requires:**
  1. the provider console's spend for that UTC day, recorded;
  2. the latch reason;
  3. every `reserved` row resolved;
  4. a dated entry in the private operator log.

  A clear never refunds the day's spend and never shortens ledger retention. A
  restart or a re-created twin is not a clear.
- **After the SQL clear, the machine is restarted.** The settlement fault is
  also held in the running process (`_settlement_fault`,
  `consciousness/model_dispatch.py`) and survives a database clear, and the
  restart re-runs the startup check for unsettled rows. The clear is complete
  only when, after that restart, `python main.py models` and voice health report
  not stopped and one controlled call settles.
- **Rehearsal.** By **Friday 4 December**, before the first session (items 3,
  28), on a separate throwaway Fly app. It covers reservation, settlement, the
  stop, G2's hand-SQL clear with its four evidence items, the restart, and the
  settled call after it.
- **ADR-039 is accepted once that rehearsal passes.** The next records or
  status pull request records it on the owner's instruction.

**Unblocks:** G2's evidence rule and an AI-on watch that survives a latch.

### O10. The old map's path and the Map view reading (item 2)

**Adopted.**

- **The current explorer moves to `/map`** and stays there until the cohort
  read-out. It is frozen except for:
  - privacy, safety and correctness fixes;
  - changes in batches already ratified, such as ADR-036 batch 1b's away state
    in both clients.
- **"Shared React Map view"** means the world map rendered in React inside the
  `/app` client:
  - It shares `/app`'s session, notice gate, Travelers panel and the single
    Speak, Puzzle and Act surfaces.
  - It becomes the landing view at `/`.
  - It replaces SceneView's "World map" link rather than adding a second
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
6. G4
7. X2
8. G2
9. G3

C1 merges before G3. Each merge still needs the owner's instruction on that pull
request after reading its irreversibility check, and auto-merge is never
enabled.

### O12. Deploy-time steps on the twin

**Adopted.** By **Thursday 3 December**, once C1, C2 and G1 have merged:

1. Validate both approved files offline: `python main.py community-policy
   --check --policy <file>` and `python main.py model-policy --check --policy
   <file>`. The check alone loads nothing into the running server.
2. Place both files on the staging machine at a path that survives a restart.
   *Not verified:* which path; the volume is `/data`.
3. With `fly secrets set -a enfolded-staging`:
   - point `NESTED_WORLDS_COMMUNITY_POLICY` and `NESTED_WORLDS_MODEL_POLICY` at
     those paths;
   - keep `NESTED_WORLDS_REQUIRE_MODEL_POLICY=1` and
     `NESTED_WORLDS_DISABLE_IMAGES=1`;
   - set `NESTED_WORLDS_DISABLE_AI=0` (`fly-deployment.md`, "Approved live
     controlled text").

   Setting the secrets restarts the machine, and the restart loads both frozen
   policies.
4. Confirm that `printenv NESTED_WORLDS_DISABLE_AI` prints `0` and that
   `python main.py models` shows the controlled routes.
5. Check that `GET /community` matches the approved file: its revision, chat and
   reports enabled, retention, contact and backup notice.
6. Check that `GET /participation` shows the new revision as required and ready.
7. With the acknowledged check key, require `ai: true` on step 7's gameplay
   probe.
8. Revoke the check key.

The owner names the deployed commit to Claude Code, in the session or on the
deploy record. Claude Code then opens the F2 evidence record (selected-commit
evidence and the installed-wheel smoke).

**Owner act:** the deploy and the checks.

### O13. Operator rehearsals

**Adopted.** Before Friday 4 December, each logged with its date in the private
record.

**Rehearsal keys.** The owner mints rehearsal keys from a terminal:
- one one-word key for the single-identity rehearsals;
- three more, distinct, for the capacity rehearsal. They go one per line in a
  private key file outside the checkout, never on the command line.

Each rehearsal identity acknowledges the current notice before use, and all are
revoked afterwards. None is a tester's key, and a revoked name stays taken.

The rehearsals start once O12 is done; only G3's probes wait for G3's merge:

- G3's live probes (this is also O3's live run):
  - success, with a settled reservation;
  - the moderation hold: an unclassified shared line, the kill switch on, or the
    ceiling spent;
  - the quiet voice fallback: only the voice cap spent;
  - the honesty answer;
- the single-grader rubric run, recorded as a deviation from the two-grader rule
  (item 27). It runs isolated from the twin, on an operator workstation or a
  separate process with no `NESTED_WORLDS_MODEL_POLICY` and no twin database,
  because controlled mode refuses live eval wrappers
  (`docs/development/model-policy.md`). It uses `scripts/model_eval.py --live`
  against the same endpoint and pinned ids, with its own `--max-usd` set by the
  owner. The policy ledger does not count that spend; the $150 provider limit
  does;
- a capacity rehearsal with three simultaneous clients: `scripts/ws_soak.py
  --clients 3` with the three-key file, and `--no-chat` unless `/community`
  reports chat enabled;
- block and unblock;
- sanction suspend and lift;
- `python main.py redact`;
- an urgent-escalation drill with the second operator;
- the twice-daily checks of the open and acknowledged report queues;
- `fly machine stop` and restart;
- `python scripts/beta_metrics.py --days 1`;
- confirming that operator-key entry demands the 18+ acknowledgement.

### O14. Observability and alerts (items 11, 13)

**Adopted.**

- **Sentry** is on for the twin, with `SENTRY_ENVIRONMENT=staging` and frame
  locals off, and a line in the notice (item 13).
- **Alerts** go to O6's project address, with the second operator copied (agent
  judgment). They cover backup freshness, uptime (an external check on `/guide`)
  and voice health (item 13).
- **Backup dispatch** (agent judgment, chosen over a GitHub App as the smaller
  setup for a pilot):
  - a fine-grained GitHub token with Actions write on this repository only;
  - a 90-day expiry;
  - its rotation date in the operator log.
- **Freshness** is checked by a separately hosted heartbeat monitor. It alerts
  when no fresh backup has reported in for longer than the one-hour bound plus
  one check interval. One scheduler that both dispatches and checks cannot
  raise its own absence (item 13).
- **When the twin is destroyed, after its final snapshot,** the backup schedule
  is retired completely. With `ENFOLDED_BACKUP_REQUIRED=true` every later run
  would fail, and the workflow also runs on its own GitHub cron at :17 and :47
  each hour. The steps:
  1. Stop the scheduler's dispatch.
  2. Disable the "Off-host backup" workflow.
  3. Delete the `ENFOLDED_BACKUP_REQUIRED` and `ENFOLDED_BACKUP_APP` variables,
     so nothing falls back to `enfolded-beta` with a staging token.
  4. Revoke the backup token and delete its secret.
  5. Pause or delete the twin's heartbeat monitor.
- **Re-arming for production** is a separate owner act before the first
  production boot, in this order:
  1. Store a production token in the protected environment.
  2. Leave `ENFOLDED_BACKUP_APP` unset or set it to `enfolded-beta`.
  3. Re-enable the workflow.
  4. Run one manual dispatch and confirm a real object is stored.
  5. Only then set `ENFOLDED_BACKUP_REQUIRED=true`.
  6. Point a new heartbeat monitor at production.

**Owner act:** the DSN secret, the scheduler, uptime and heartbeat accounts, and
the token.

### O15. Records only the owner can supply

**Adopted.**

- **The 15 November decision page** (item 42) is committed verbatim as
  `docs/roadmap/owner-decisions-2026-11-15.md` in a records pull request. The
  owner supplies the text, and the agent formats it without rewording.
  `AGENTS.md`'s "not published in the repository" then changes in the
  working-rules pull request (O16(d)).
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
  read in the naming pull request. Approve if:
  - the pin diff is limited to ADR-041 D7's list;
  - D4's rewording of the dash and lineage hints applies only to worlds born
    under the new generator version, and on a world born under generator
    version 2 every prompt and hint is byte-identical;
  - the D4 comparison reports no family, answer or difficulty difference at both
    depths for epochs 0 to 2;
  - on the generator-v2 world it reports no family, answer, difficulty,
    prompt-text or hint-text difference.

  The pins alone cannot show a selection change (ADR-041 D4, D7).
- **(b) Puzzle design record (item 23).** Claude Code re-derives the draft in
  the repository from D-C, D-I and D-J:
  - ten sample puzzles for each of the four new kinds and for the first puzzle;
  - no look-ups;
  - A10, D6 and D10 held.

  The owner judges the samples in that pull request. If the owner still has the
  original draft, it is used instead and committed as given.
- **(c) ADR-037 question 5, second half** (agent judgment, taking ADR-037 D3's
  proposed default):
  - With AI on, an AI traveler's honesty answer is kept as that agent's chat
    lines are kept (D8).
  - It stays out of the history fed to other voices, as decided on 2026-11-10.
  - With AI off, nothing is stored.
  - A repeat from the same asker to the same agent within ten minutes is stored
    nowhere.

  This unblocks the ADR-037 chat batch.
- **(d) Working-rules pull request.** Requested. Claude Code prepares it after
  C0 merges, as a pull request of its own. It carries:
  - item 45's two rules and its queue limit, with the reading O1 uses;
  - the ADR-019 to ADR-022 pointer;
  - `AGENTS.md`'s sentence on the 15 November page, once O15 commits it;
  - the three wordings of the 18 November record's entry 17, for the owner's
    approval there.
- **(e) Puzzle salt (ADR-038).** The owner sets the staging salt as a
  `fly secrets` value before the first staging deploy that carries B1, and the
  production salt with the first-deploy secrets, B2 (item 22).

### O17. Recruiting, admission and the read-out

**Adopted.**

- **Invitations** go out only once:
  - the second operator is named (item 31);
  - protocol 2's pre-recruitment record is written in the restricted research
    record: facilitator or research owner, observation dates, supported devices,
    client, consent wording, and the retention and deletion date
    (`docs/evaluation/2026-09-12-pilot-protocol.md`, "Scope and venue");
  - the operator confirms the correct world and its recovery status.

  Testers can be lined up before then.
- **A tester is admitted, with a playable key minted,** only once every
  applicable Watch-column entry requirement (`beta-launch-checklist.md`,
  requirements 1 to 8) has dated evidence against the deployed commit O12 names,
  or a justified not-applicable decision that names the selected scope. That
  includes:
  - C1, C2, G1, G4, X2 (the `/` switch) and L5 merged and deployed;
  - O12's checks, and the F2 selected-commit and installed-wheel record;
  - O5's secrets set;
  - G3's live success, hold and failure probes;
  - every O13 rehearsal logged.
- **Playtest tripwire** (item 38), confirmed now as written there. This moves
  forward a confirmation the 18 November record placed at the read-out (agent
  judgment); the read-out may still change it.
  - A puzzle family with five or more attempted puzzles and none solved, or an
    overall median interest rating under 3, opens a fix before invitations go
    beyond the first cohort.
  - It is read at the watch read-out and at each cohort read.
- **Defaults to bring to the 14 December read-out** (not declared here):
  - **World status:** production for the cohort world, declared only if a
    downloaded backup restores into isolated staging and item 11's seven-day
    bound has passed (item 10).
  - **Exception list:** item 37's form.
  - **Cohort route:** O3's route continues if the watch showed no unexplained
    hold or failure.
  - **Cohort date:** the earliest date by which everything the 18 November
    record puts before the first invite or the first production boot has
    landed:
    - ADR-041 naming;
    - ADR-036 batches 1b and 2;
    - the puzzle redesign;
    - the puzzle salt (B1, and B2's production secret);
    - items 18, 21, 33 and 35;
    - ADR-037 batches 2 and 3a (agents in chat, authored), which land together.
      Batch 3b's flag and batch 4 do not hold the cohort (items 39, 40);
    - if O3's route continues for the cohort world, O9's audited clear command
      (the ADR-039 revision and its migration).
  - **Alignment:** answered there.
- **Terms page (item 36).** Claude Code drafts the combined terms-and-notice
  page in its next batch for the owner to edit. Cohort membership stays the
  owner's.

## Owner timeline

| By | Owner act | Item |
|---|---|---|
| Tue 24 Nov | Fly account, staging app and volume, deploy token, GitHub `staging` environment, first deploy, check key | O2 |
| Wed 25 Nov, or the day after G1's check record | Sign the data-use note; set the staging key and model variables; confirm model ids | O3 |
| Fri 27 Nov | Name the second operator; R2 bucket, tokens and repository settings; Sentry DSN; scheduler, uptime and heartbeat monitors | O7, O8, O14 |
| On G1's report | Confirm amounts and models in the policy file; set the cap secrets | O4, O5 |
| Tue 1 Dec | Line up two or three testers; invite once O17's invitation condition holds | O8, O17 |
| Wed 2 Dec | G3 merged (otherwise the 8 Dec session moves to 10–11 Dec) | O8, O13 |
| Thu 3 Dec | Deploy-time checks on the twin | O12 |
| Fri 4 Dec | Operator rehearsals; ADR-039 and clear rehearsal on a throwaway app; mint tester keys only once O17's admission condition holds | O9, O13, O17 |
| Tue 8 Dec, Thu 10 Dec | Watch sessions (Fri 11 Dec spare) | O8 |
| Mon 14 Dec | Read-out | O17 |
| Thu 17 Dec (see O6 for other dates) | Destroy the twin unless a report is open; retire its backup schedule (O14's five steps) | O6, O7, O14 |
| About Thu 24 Dec, once the 7-day lock allows | Delete the twin's backups by hand and confirm no copy remains | O7, item 12 |

Ongoing:
- read pull requests that need a one-way-door read three at a time, and merge
  in O11's order (O1);
- post the #89 note (O15);
- supply the 15 November page (O15).
