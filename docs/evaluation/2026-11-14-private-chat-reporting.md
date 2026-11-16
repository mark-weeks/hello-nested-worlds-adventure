# Private chat and operator reporting implementation

Originally prepared against merged `main` at `ecebdedf` (schema 32), 2026-11-14;
revised for the owner's [Version 4 direction](https://github.com/mark-weeks/hello-nested-worlds-adventure/pull/174#issuecomment-6896201907)
on 2026-11-15. [ADR-040](../decisions/ADR-040-private-chat-and-reporting.md) remains
Proposed. The documented study choices do not deploy a policy, establish a live
reviewer commitment or ratify the broader conversational-agent design.

## 16 November restore follow-up

The follow-up to [comment4580180938](https://github.com/mark-weeks/hello-nested-worlds-adventure/pull/174#discussion_r4580180938)
was committed as `98d2a716563daa869753e8136578c9e85cfb54e5`, following
published `80734f8`. A database file can be a newly initialized
replacement volume or the result of an older restore, so existence and an empty
local ledger do not prove that all deletion requests are represented.

Every source backup containing `private_chat_messages` now requires an explicit
`--deletions` record, including an empty private-chat table and an existing
destination. The guard runs before any live-store read or path creation. The
current ledger is still merged with the supplied record and replayed in the
candidate before live replacement. A genuine pre33 source without that table
remains restorable without the argument; it cannot waive the requirement for a
later private-chat backup.

Regression coverage exercises a fresh `init_db()` on the replacement path, a
pre33-then-private restore both before and after boot, an intact destination,
empty private backups and merging current proof with an explicit record. Refused
restores preserve live data; recovery with the independently preserved latest
record keeps the deleted line absent. Schema33 test callers now provide actual
exports, and synthetic pre33 fixtures genuinely omit the private tables.
Runbooks distinguish routine intact-store exports from lost/recreated recovery:
a fresh-boot empty export must never replace the latest independent record.

Focused verification passed **47 deletion/CLI cases**, the **236-case** caller
suite and **22 restore-path cases** rerun under the final guard. Document links,
whitespace and the ignored-build migration inventory passed; this correction
changes no migration or application bundle. The verification record below is
for `98d2a71`:

| Run | Result |
| --- | --- |
| Fresh local `ENFOLDED_E2E=1 ./scripts/check.sh` | **Exited 1**. Ruff passed; **4,324 Python passed / one historical skip** (837.26 seconds); **241 Vitest passed** in 20 files; bundle freshness and installed-wheel smoke with schema **33** passed. Playwright finished with **211 passed / one failed** (6.8 minutes). |
| Focused browser diagnosis after that failure | The exact `/app` inhabitant-blocking case passed once alone, then **six of six** repeats with two workers. All seven runs passed; captured block/unblock requests returned HTTP 200. The original failure's cause remains unproven. No source or test change was made to suppress it. |
| [PR CI run 43788028440](https://github.com/mark-weeks/hello-nested-worlds-adventure/actions/runs/43788028440) | Green; **212 browser cases passed without retries**. |
| [Push CI run 43788020584](https://github.com/mark-weeks/hello-nested-worlds-adventure/actions/runs/43788020584) | Green; a different journal case needed a retry. |

The local canonical invocation did not exit 0; focused reruns and green CI are
separate evidence. The earlier full results below remain historical evidence
for `80734f8`. Verification used disposable stores; no live-database operation,
merge or deployment was performed.

### Final verification-record and CLI corrections

The final review replaces the former pending statements with the measured
`98d2a71` outcomes above. Restore now catches `ValueError`, which includes
`community.CommunityError`, and prints one `error: <message>` line on stderr
before exiting 1. Missing, malformed or omitted deletion exports retain the live
store and never expose their contents or a traceback; a valid export keeps the
existing success and restart output.

The three refusal regressions failed against the previous command and passed
after correction. **175 tests passed** across the community CLI, chat deletions,
persistence and deployment-rollback suites; Ruff passed. A combined rerun with
the checklist, changelog, agent-instruction and staging-workflow readers passed
**307 tests, one historical skip**; fragment and whitespace checks passed. These
are checks of the CLI correction, separate from the historical full run above. Current-head CI
evidence is recorded in the PR description. This correction changes no migration,
application bundle, restore authorization or world-history behavior.

## Historical 15 November review follow-up (`80734f8`)

The follow-up addresses [review5912009287](https://github.com/mark-weeks/hello-nested-worlds-adventure/pull/174#pullrequestreview-5912009287)
on published `a47e88e`. That head is preserved locally; the candidate is rebased
onto merged `main` at `def0f541` (#177) before the fixes, with its escaping changes
preserved. The checks below ran before publication of these fixes.

Admission now requires the current notice and affirmative 18+ whenever test-world
mode is on **or** the permanent invite latch is active, independently of chat or
report collection. Collection-off deployments still need the TEST_* notice
values. Tests default to the real no-policy configuration; actual collection
tests opt in. The unreachable legacy credential branch is removed in favor of
one live-credential/notice check, with real default-off and collection-on
revocation, rotation, sanction, read-failure and sweep behavior covered.

Completed chat deletion and its text-free proof commit atomically. Only actually
deleted opaque references and UTC timestamps enter the new ledger; held rows and
future messages are excluded. Restore reconciles current and explicitly exported
records in a candidate before copying live, including over a backup's stale
open-case state and into schema32. Startup replays before listening. Lost-store
private-chat recovery requires a separately preserved export, and malformed
records leave live data unchanged. Operators stop writers and reconcile before
restart; exported records remain private and independent of the restored snapshot.

The undeployed chat contract accepts only disabled or until-deleted policy;
numeric chat TTL is rejected. Delete commands neither create nor migrate a
missing store, resolve normalized names, distinguish unknown and ambiguous
names, and report zero retained messages for a known unused invite. All new
community command bodies now live outside `main.py`. Missing report evidence has
the neutral status `unavailable`. The probe distinguishes storage failures from
moderation. Both clients construct accessible chat descriptions from current
state, avoiding hidden or duplicate unavailability announcements.

The runbooks require the first schema33 deployment to go only to the throwaway
staging twin, report-queue checks at least twice daily and a second operator
before the cohort. Report windows remain documented 90/180-day choices, not
deployed policy. Focused verification passed 17 ledger/startup cases, four prior
restore cases, 80 persistence cases, 168 policy/CLI/metrics/projection/startup
cases, 783 admission/auth integration cases, 45 soak cases, 52 reporting unit and
28 reporting browser cases.

### Review follow-up verification

The final-source check began on 2026-11-15 at **19:19:19 UTC**, with Python
**3.11.14**, Node **20.19.0**, a dedicated pytest temporary directory and the
shared browser lock. Ruff passed; **4,318 Python tests passed / one existing
historical release-tag check skipped** in **868.70 seconds**; **241 Vitest tests**
passed in **20 files**; and the rebuilt `index-CxUBmRb2.js` bundle was byte-fresh.

That `check.sh` invocation **did not exit 0**: installed-wheel preflight found
the earlier `a47e88e` migration 0033 bytes in ignored `build/lib`. The generated
build was preserved at
`/tmp/enfolded-pr174-generated-build-before-ledger-39d70b8e`; no live database or
product source was changed for this cleanup. Fresh
`.venv/bin/python scripts/verify_wheel.py` then exited **0**, verifying the
installed `enfolded-0.1.2rc1` wheel with schema **33**. The remaining full browser
gate ran separately under the same mutex and exited **0**: **212 Playwright
tests passed** in **6.4 minutes**, observed complete at **19:41:57 UTC**. Thus all
canonical components passed, with package/browser checks resumed after generated
cache cleanup; this is not reported as one uninterrupted successful script run.

The initial full Python inventory had seven failures: an unnecessary restore
initialization-cache invalidation broke five older-schema fallback cases, and
two fixtures needed a real startup store or the strict chat policy. Removing
that extra invalidation and updating those fixtures preserved existing fallback
behavior; the affected suites passed **37** and **34** checks before the final
full Python run above. No affected feature check was skipped, and no paid call,
live database operation, deployment or release was performed.

## Historical Version 4 candidate (`a47e88e`)

The revised candidate starts from merged `main` at `4b3d8c4` and retains the old
PR #174 work for comparison. Its private human-chat policy is `until_deleted`,
with nullable chat expiry and no timed deletion. Operators can delete one line by
evidence reference or all chat for one tester across rotated credentials. Open
and acknowledged complaints hold their case, actions and cited lines until
closure; deletion skips held lines, deletes eligible lines and reports the count
and reason. Closure releases the hold without restarting the recorded deadline.
Study departures, deletion requests and outstanding holds need end-of-study
review. Deleting the disposable watch world also deletes its log.

The owner selected report retention of 90 days for the disposable watch and 180
days for the retained cohort. These are documented operating decisions, not
checked-in deployment settings. The notice states operator-only access, complaint
investigation and understanding study interaction, deletion on request or study
departure, the contact, and that backup copies disappear when their backups are
deleted. Both registration and operator-invited access require affirmative age
18 or older and the same current notice revision. The stable study condition is
test-world mode, or configured collection with the permanently latched invite
gate; emergency collection switches and revoking the final key cannot remove it.

The map client remains available with its Report, notice and chat-off behavior.
Live room-wide delivery, the existing composer, place/inhabitant exchanges and
ambient agent speech keep their existing roles. New traveler chat creates no
permanent history event, even a wordless trace, and no player scrollback. The
candidate carries forward #171's continuous P3 snapshot-start freshness bound,
including upload time and the still-proposed rehearsal duration.

Review fixes also cover chat-off soak probes, NUL/unpaired-surrogate refusal
before moderation, self reports, report drafts crossing to a different person,
initial community loading, retention of the last valid community response on a
transient refresh failure, and keyboard focus after Send.

Version 4 changes migration 0033 before its first deployment. The older validation
counts, bundle digests and byte-identical migration statements below remain
historical; the fresh candidate results are recorded here.

### Version 4 verification

`ENFOLDED_E2E=1 PW_CHROMIUM_PATH=/usr/bin/chromium ./scripts/check.sh` exited
**0** on the uncommitted candidate on 2026-11-15, observed **16:24:06–16:44:07
UTC**, with Python **3.11.14** and Node **20.19.0**. Ruff passed; **4,258 Python
tests passed**, with one existing historical release-tag check skipped
(**802.46 seconds**); **231 Vitest tests** passed in **20 files**; the production
bundle was byte-fresh (`index-C9uVKA2U.js`); the isolated installed
`enfolded-0.1.2rc1` wheel passed with schema **33**; and **208 Playwright tests**
passed across both clients in **6.4 minutes**. The deployment-history case was
skipped because `v0.1.1-qa.2` or the historical schema-guard commit is missing
from this checkout; no affected feature check was skipped.

The first Version 4 Python inventory found **16 failures and one setup error**
alongside **4,241 passes** and the same skip. Normal invited-study fixtures now
acknowledge the actual current notice and age requirement, including before a
cold backup/restore. Integration checks also preserve the CLI's separation from
the HTTP runtime and the Ideas credential-failure limiter without enrolling an
unacknowledged participant. The initial full browser inventory found **19**
missing adult-enrollment fixtures; fresh affected checks passed **47/47**, then
the full canonical run above passed. Endpoint guards and raw refusal helpers
were preserved.

The final Markdown check covered **19** added local file targets and **six**
Markdown anchors in ten changed documents, with no errors; an earlier broader
check covered **174** relative links. No paid call, real-database migration,
deployment, release or external report notification was performed.

## Scope and observed behavior

Previously, each admitted human WebSocket chat message became a permanent
`PLAYER_CHAT` chronicle event. Reporting had no private intake. New messages now
commit to separate retained operational storage before live broadcast. Storage
or policy failure returns a private decline and preserves the client's draft.
There is no permanent-history fallback and no automatic resend on reconnect.
Existing moderation, consent, sanctions, blocking and fresh-credential fences
remain in place. Keyless local chat requires an explicit collection policy and
an open invite gate; a personal live invite is always required to report.

Both clients place Report beside the existing Block control and use one dialog.
The target is an opaque viewer handle or retained server-issued evidence
reference, never a name supplied by the client. Reports have four reason codes,
optional details up to 2,000 Unicode characters, and an opaque private receipt.
No report or its details go to a model, public feed, target or external service.
Operator commands list, inspect, acknowledge and close the queue; they do not
sanction automatically. Terminal output is escaped JSON and notes can use stdin.

Chat evidence is referenced, not copied. A new report needs retained evidence;
an accepted open or acknowledged complaint preserves its evidence until closure.
Report actions share the report's original deadline and pending-case hold. Reads
include no-expiry chat and held records while hiding eligible expired text,
startup prunes before listening, and a separate 60-second worker cleans up even
when collection and the world heartbeat are off. Whole-DB backups can retain
deleted or expired content beyond the live database, and some copies can survive
indefinitely. The disclosure must describe the operator's actual arrangements.

The immutable community policy has no duration, contact or backup defaults.
Absent policy leaves collection off in local and hosted modes while other
gameplay remains available. Invalid supplied configuration refuses startup before
migration or a listener. Emergency switches can only deny collection. The public
capabilities endpoint and participation notice derive wording from that same
snapshot; policy wording changes require renewed study acknowledgement and age
confirmation.

Legacy `PLAYER_CHAT` rows remain byte-for-byte. Public history and model queries
exclude them before limits, counts and cursors, with a second prompt defense.
Historical art activity totals and metadata windows remain stable. New private
chat is not an art input. Place and inhabitant exchanges and authored ambient
`AGENT_TALK` remain recorded; ADR-037's future conversational agents are separate.

## Findings corrected during implementation

- The report retry lookup runs before transient target/evidence resolution.
  The same authenticated reporter recovers the original receipt after restart
  or credential rotation, even if the live handle has disappeared. Changed
  payloads with the same id refuse; the guarantee ends when the report is no
  longer retained.
- The 8 KiB general request limit could reject a valid 2,000-character report
  containing escaped supplementary Unicode. Only `/reports` now permits 32 KiB;
  the detail limit remains 2,000 characters and the Ideas limit is unchanged.
- A browser connection could leave a report stuck at Sending. Reports now abort
  after 15 seconds and retain the exact request id and payload for explicit retry;
  public metadata has a five-second deadline. The first load shows a loading
  state; a later failed refresh preserves the last valid capability response.
- Independent review executed a disabled-chat draft reaching the moderation
  screen before the availability check. That check now precedes moderation,
  with a second check after screening and regressions for missing, invalid and
  emergency-disabled policy. No real provider was contacted in the reproduction.
- A pending browser report used a process-scoped viewer handle as its owner.
  Restarting the server changed that handle and prevented receipt recovery.
  Pending ownership now uses the unchanged authenticated endpoint in memory;
  changing credentials cannot replay another account's draft. Detail validation
  also counts Unicode code points rather than UTF-16 units.
- Default queue polling previously included old closed cases first. Fifty such
  retained cases could hide every new open report. The CLI now defaults to open
  cases; an explicit `--state all` retains the combined view.
- Compatibility assertions expected the removed permanent chat writer. They now
  check private evidence/storage alongside the original live-delivery, blocking,
  moderation, saved-position and authorization behavior. Tests of old history
  use explicit legacy SQL fixtures rather than recreating a removed application
  write path. The Ideas upgrade test also enumerates all nine `community_*`
  tables, including the new policy table, while retaining every old-data check.
- Browser server fixtures now declare a synthetic one-day policy explicitly.
  Those fixtures are test inputs, not deployment recommendations or defaults.

## Historical validation of the original implementation

The first canonical Python run completed with **4,155 passed / 17 failed** in
**804.45 seconds**. Two failures were the outdated eight-table Ideas inventory;
15 waited for permanent chat rows in moderation/reconnect tests. Those assertions
were updated to verify private evidence and zero new chronicle chat, preserving
their original behavior and data invariants. The affected files then passed in
full: **25 upgrade**, **213 moderation** and **19 movement** tests. The clean run of the original implementation
`ENFOLDED_E2E=1 PW_CHROMIUM_PATH=/usr/bin/chromium ./scripts/check.sh` run
exited **0**, observed 2026-11-14 **20:53:54–21:12:37 UTC**, with pinned
Python **3.11.14** and Node **20.19.0**: Ruff passed; **4,172 Python tests**
passed in **752.07 seconds** with no skips; **225 Vitest tests** passed across
**20 files**; the production bundle was byte-fresh; the isolated installed
`enfolded-0.1.2rc1` wheel passed with schema **33**; **201 Playwright tests**
passed across both clients in **6.0 minutes**. The final relative-file-link
check covered **209** links with no missing destinations, and whitespace
checks passed.

Visual inspection covered the report dialog in both clients, including mobile
viewport layout, accessible field focus and the private retention notice, using
synthetic names and content. No report was submitted to a hosted world.
No paid provider call, deployment, external notification, release tag or live
retention selection was performed.

## Historical PR review follow-up

The [review on PR #174](https://github.com/mark-weeks/hello-nested-worlds-adventure/pull/174#pullrequestreview-5907370992)
was checked against head `626dd953`. The implementation follow-up:

- Reuses one pure canonical UUID rule for API and persistence. Invalid request
  ids refuse before receipt lookup/storage; exact-payload fingerprinting remains.
- Makes ordinary registration/guide retention wording conditional on availability
  and tests rendered public copy with collection enabled and disabled.
- Gives disabled/invalid chat policy a world-unavailable line and keeps retry
  wording for transient storage failures, preserving both policy/auth fences.
- Makes the next-deploy rollout decision explicit in the runbook: configure
  approved collection or choose an explicitly chat-less deploy/watch. It also
  requires checking capabilities and revisiting the changed test-world notice;
  interrupted submissions must not replay automatically.
- Records the separate one-way consequence of removing the chat chronicle writer
  in ADR-040, the prospective ADR-004 amendment, this record and the CHANGELOG.

The metrics JSON contract changes with this batch: `chat_lines` is an integer or
`null` when private storage is unavailable, and `chat_log.scope` is `retained_only`.
Retained rows include no-expiry chat and open-complaint holds. Fixed
`--since`/`--until` bounds and an immutable archive do not make chat counts
reproducible after deletion or eligible expiry. Consumers
must check availability/scope and treat unavailable history as unknown, not zero.
This is documented rather than retaining a permanent per-person chat counter.

The earlier follow-up did not select durations or deploy a policy. The Version 4
owner direction above supersedes its rolling-chat-expiry and no-hold assumptions;
ratification, merge and rollout remain separate actions.

Review validation: `ENFOLDED_E2E=1 PW_CHROMIUM_PATH=/usr/bin/chromium
./scripts/check.sh` exited **0**, observed **2026-11-14 14:11:04–14:30:07 PST**
(`America/Los_Angeles`), with Python **3.11.14** and Node **20.19.0**. Ruff passed;
**4,188 Python tests** passed in **770.88 seconds**, with no skips; **225 Vitest**
tests passed across 20 files; the production bundle was byte-fresh and unchanged;
the isolated installed `enfolded-0.1.2rc1` wheel passed with schema **33**;
**201 Playwright tests** passed in **6.0 minutes**. The focused API/persistence
pack passed **99** cases, WebSocket **11**, and public-copy browser **7** during
iteration. All **210 relative file links** checked resolve, and whitespace checks
passed. No paid call, rollout, merge or new tag was performed.

The review delta adds no migration or further writer change. All **33** migration
files remain byte-identical to `626dd953`; the full PR still has the separate
schema and future-chat recording consequences documented below.

### Historical integration with other open work

Read-only `git merge-tree` checks used `main` at `ecebdedf`, #171 at `be8454b`,
#173 at `54870242`, and this PR's reviewed head `626dd953`. #171 and #174 each
merge cleanly with that main; #173 already conflicts in the checklist.
Combining #171/#174 conflicts in the checklist; #171/#173 conflicts in the
checklist and CHANGELOG. #173/#174 also conflict in handlers, the bundle/index,
the guide and modify/delete changes to the three retired map files.

The sequence proposed at that time, subject to separate merge instructions, was
**#171 → rebase/recheck #174 → rebase/recheck #173**. This PR does not depend on #173's
unresolved admission/rules/ADR decisions. These are integration checks and a
recommendation, not authorization to merge or edits to either other branch.

- After #171, keep its continuous 60-minute snapshot-start freshness bound,
  including upload time and the still-proposed rehearsal duration. Combine
  checklist evidence row by row and recount it.
- Version 4 retains the map client and both clients' Report controls, shared
  reporting assets/routes, private APIs, consent checks,
  retention worker and schema 33. Combine the wheel checks and regenerate the
  bundle from combined source rather than selecting one generated version.
- Preserve all CHANGELOG entries, #172's spend controls and this batch's privacy
  evidence. Do not restore stale schema-31 or permanent-new-chat descriptions.

The [#171 follow-up](https://github.com/mark-weeks/hello-nested-worlds-adventure/pull/171#pullrequestreview-5907369803)
approves its delta; the [#173 review](https://github.com/mark-weeks/hello-nested-worlds-adventure/pull/173#pullrequestreview-5907370350)
requests changes, owner decisions and fresh verification after rebase.

## Historical candidate inventory

The source package remains `enfolded-0.1.2rc1`; this batch advances the prepared
schema from 32 to provisional **33**. It creates no tag or published wheel.
A new immutable QA candidate must identify the reviewed commit after integration,
then be checked with the existing staging probes before any deployment claim.
The hosted world remains seed **382** with **`/app`** as the client under test.

The earlier inspected production bundle was:

| Asset | SHA-256 |
| --- | --- |
| `index-Dsa95nNg.js` | `7eba7f4ebfe6a079adee245e8dd34236952e07e9e9cc89c0b3f64768f6cb04ec` |
| `index-DGZaevXc.css` | `5154774713197c9cdc99dc23810a04e474a317ea6ce836b0830246a6affd4577` |

All 32 existing migration files and the birth/golden/wrap/era source files were
compared byte-for-byte with merged `main` and are unchanged. Migration 33 adds
only the four operational tables. Tagging, wheel publication, hosted backup,
restore, expiry and multiplayer observation remain separate release work;
use the [reporting guide](../development/community-reporting.md) and
[deployment runbook](../infrastructure/fly-deployment.md) for their procedures.

## Remaining release gates

The operator must load the selected until-deleted chat policy and appropriate
documented report window, contact and accurate backup wording, and assign and
rehearse private queue polling before tester
access. This implementation does not establish the 24-hour response workflow.
Hosted expiry/restore and multi-player rehearsal remain staging work. Model
destinations, prices and limits retain their separate approval gates. Historical
chat in operator tooling or backups is not erased by these projections.

**Irreversibility check:** additive provisional migration
`0033_private_chat_reports.sql` adds four private operational tables and removes
the new human `PLAYER_CHAT` writer within the requested session scope; the PR
retains the human schema and ADR-004 amendment gate. Separately, merging the
writer removal adopts new human chat permanently leaving the never-wipe
chronicle under the merged implementation. After deployment, rows not written
cannot later be restored as original chronicle history by rolling back code;
the private log is retained until deletion and is not permanent history. No existing mutation is
rewritten, no new `world_mutations` writer is added, and no birth/golden,
world-meta pin or era bank changes. Back up before deployment and retain a
schema-33 rollback binary; a schema-32 binary must refuse the newer database.
