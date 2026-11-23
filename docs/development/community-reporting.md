# Private traveler chat and operator reports

This batch prepares the owner's [Version 4 private-chat and reporting direction](https://github.com/mark-weeks/hello-nested-worlds-adventure/pull/174#issuecomment-6896201907).
Chat is retained until deletion; report windows are 90 days for a disposable
watch and 180 days for a retained cohort. These are documented operating
decisions, not deployment defaults or checked-in policy selections. The guide
does not ratify ADR-040, select a data destination or deploy a policy. The additive
migration `0033_private_chat_reports` follows schema 32 provisionally; its number
is assigned at merge and needs human review there.

The first schema-33 deployment is restricted to the throwaway
`enfolded-staging` world. Rehearse private storage, reporting, deletion and restore
there before any later cohort rollout. This preparation does not authorize a
deployment or migration of a retained or production world.

## Activation and data boundaries

All new human WebSocket traveler chat uses a private operational log in hosted
and local modes. It is broadcast live to the permitted recipients, then available
only to operator tools while retained. It is not written to `world_mutations`,
public history, place or inhabitant memory, or art activity. There is no permanent
event, even a wordless trace, and no player chat-history scrollback. Live
room-wide delivery is unchanged. With no configured community policy, new chat
and reports are disabled; other gameplay remains available, subject to its
existing gates.

Before the next deployment, the owner must choose how that behavior is rolled
out. A chat-enabled watch needs the selected until-deleted policy, report window,
contact and backup wording supplied before tester access. The owner can instead
explicitly choose a deploy or watch with chat/report collection off. Missing
policy disables both in **every mode, production included**; that default does
not choose the off rollout on the owner's behalf. This guide activates no
running policy or deployment mode.

The operator supplies the strict immutable community policy. No numeric chat,
report or backup retention is supplied by the code.
Check the intended file offline before configuring a server to load it:

```sh
python main.py community-policy --check --policy /private/community-policy.json
```

Set `NESTED_WORLDS_COMMUNITY_POLICY` to the approved file path. A policy has
`schema_version: 1`, a `policy_id`, and `chat` and `reports` objects. A disabled
capability is exactly `{"enabled": false}`. Selected chat retention is exactly
`{"enabled": true, "retention_mode": "until_deleted"}`; its expiry and retention-day
columns are null. Enabled reports use `{"enabled": true, "retention_days": ...}`
with the operator's explicit integer duration. A numeric chat TTL is not an
accepted policy form: chat is either disabled or explicitly `until_deleted`.
Enabled collection also requires top-level `contact` and `backup_notice`. The checked-in
`config/community-policy.disabled.json` supplies neither durations nor contacts.
Unknown or duplicate fields and invalid configured files refuse startup. Optional
`NESTED_WORLDS_DISABLE_CHAT=1` and `NESTED_WORLDS_DISABLE_REPORTS=1` can deny an
already-permitted capability; clearing them cannot grant what the frozen policy
disabled.

The check neither activates that policy nor opens a database or calls a provider.
A running server keeps its frozen policy until restart. A command's policy output
describes that command process, so match it to release and restart evidence.
After the selected policy is loaded by deployment/restart, inspect `GET /community`
and match its revision, enabled capabilities, retention, contact and
backup wording to the selected release state. For an explicitly chosen off
state, both enabled flags must be false. The offline check and `/health` do not
prove which policy the running server loaded.
The model policy remains a separate boundary: retaining a private chat log does
not authorize a model destination, cost or new agent conversation capability.

The scope is human messages sent through the existing traveler-chat composer.
Place exchanges (`PLAYER_SPEAK`), addressed inhabitant exchanges (`AGENT_VOICE`)
and authored ambient cast exchanges (`AGENT_TALK`) remain recorded under their
existing rules. This is not a promise that all speech is private. It does not
implement ADR-037's proposed agents answering players in chat.

Existing `PLAYER_CHAT` chronicle rows stay untouched. Normal public and model
history reads exclude them before limits, counts and pagination. Operator
history/redaction tools retain access. Legacy aggregate art wear and the
metadata-only legacy image-style calculation stay stable; the new private log
does not feed either, so deletion cannot fade established art.

## Watch policy template

The owner turned chat and Report on for the newcomer watch on the disposable
`enfolded-staging` twin
([18 November, item 4](../roadmap/owner-decisions-2026-11-18.md#2-adopted-answers)).
The watch keeps chat until it is deleted and keeps reports for 90 days. The
template below is that policy with two owner values left open. It is a
template, not a checked-in policy: nothing under `config/` selects it, and
ADR-040 keeps the 90-day and 180-day windows as documented decisions rather
than defaults. Do not commit a filled copy to the repository.

```json
{
  "schema_version": 1,
  "policy_id": "watch-twin-2026-12",
  "chat": {"enabled": true, "retention_mode": "until_deleted"},
  "reports": {"enabled": true, "retention_days": 90},
  "contact": "<OWNER: contact>",
  "backup_notice": "<OWNER: backup_notice>"
}
```

Replace the two placeholders before the offline check:

- `<OWNER: contact>`: the dedicated project address the owner reads daily
  ([O6](../roadmap/owner-decisions-2026-11-20.md#o6-notice-and-community-policy-values-item-6)).
  It is shown after "Community questions and reports:".
- `<OWNER: backup_notice>`: O6's adopted wording, on one line. The served
  notice shows it after "Copies in backups are removed when those backups are
  deleted." Until the bucket's erasure check is recorded
  ([backup bucket, "Erasure check"](../infrastructure/backup-bucket.md#erasure-check)),
  the wording gives no date and no age limit:

```text
Backup copies of this test world are kept in a private storage bucket. They stay until the operator deletes them after the test world is destroyed; no deletion date is promised. The host also keeps its own snapshots of the world's disk for about five days, and the operator deletes any copy downloaded for testing.
```

Each value is one line of 1 to 1,000 characters, with no leading or trailing
space and no control characters; the check refuses anything else. The check
does **not** refuse a placeholder left in place: `<OWNER: contact>` is valid
text, so an unfilled file passes and would be served to testers. Search for
`<OWNER` in the filled file and find nothing before you run the check.
`tests/test_community_policy.py` and `tests/test_community_activation.py` read
the template and the wording from this section, fill in test text, and prove
the file loads and that the server it configures enables chat and Report.

### Activating the template on the twin

The steps follow
[O12](../roadmap/owner-decisions-2026-11-20.md#o12-deploy-time-steps-on-the-twin).
`--policy` feeds only the offline check. It loads nothing into a running
server; the environment variable and a restart do.

1. Fill the template in a private location outside the checkout, confirm no
   `<OWNER` text remains, and check it offline:

   ```sh
   python main.py community-policy --check --policy /private/community-policy.json
   ```

   Record `configuration.revision` from the output. The output must show
   `chat_retention_mode` as `until_deleted` and `report_retention_days` as
   `90`.
2. Place the same file on the staging machine at a path that survives a
   restart. The volume is mounted at `/data`; which path O12 uses is not
   verified, and no copy command was run from the session that wrote this.
3. Point `NESTED_WORLDS_COMMUNITY_POLICY` at that path with
   `fly secrets set -a enfolded-staging`, in the same secrets change as the
   model policy (runbook,
   ["Approved live controlled text"](../infrastructure/fly-deployment.md#approved-live-controlled-text)).
4. Setting the secret restarts the machine, and the restart freezes the file.
   A later edit to the file changes nothing until the next restart.
5. Check `GET /community` on the twin. Its `revision` must equal the revision
   from step 1; `chat.enabled` and `reports.enabled` must be `true`;
   `chat.retention_mode` must be `until_deleted` and `reports.retention_days`
   `90`; `contact` and `backup_notice` must be the filled text. Then check
   that `GET /participation` serves the new revision with `required: true` and
   `ready: true` (runbook,
   ["Participation notice and adult confirmation"](../infrastructure/fly-deployment.md#participation-notice-and-adult-confirmation)).

## Reporting in the existing interface

Report sits beside Block on traveler rows and live chat lines in both clients.
It opens a bounded form in that existing surface; the chat composer and draft
remain intact. Human and server-owned agent targets use the same controls.
The reporter's live personal credential determines ownership. The target handle
is opaque and viewer-scoped; a supplied name, credential or internal participant
ID is not an authority to report someone else.

The server stores a private receipt for a report with its reason, optional
explanation and evidence references. Retried submissions use their original
request ID rather than creating another report. The target is not told the
reporter's name, and there is no public report queue or evidence-reading API.
Reports do not invoke a model and must not depend on provider availability.
They do not automatically suspend, ban or redact anyone.

`GET /community` returns public capability and retention metadata, the contact
and backup statement, allowed report reasons and the detail-length bound. It is
not a chat history or report-list endpoint. `POST /reports` takes the exact fields
`request_id`, `participant`, `evidence_ref`, `reason` and `detail`. The participant
is a viewer-scoped handle or null; an evidence reference is an opaque chat-message
reference or null. A new submission needs a selectable target or retained evidence.
Keep the request ID and entire payload unchanged when retrying. The response
contains only `report_id` and the public status `received`.

Chat evidence references the original retained line without copying a quotation.
Open and acknowledged reports hold their cited messages until the complaint
closes, including across a recorded expiry or deletion request. Closing the
report releases its hold; it does not restart any deadline or automatically
delete an otherwise retained line. An explanation the reporter types or copies
is separately stored report content and follows report retention. Unknown or
unretained evidence is refused for a new report. Keep the draft, select a
current traveler and submit a new request without that reference if necessary;
do not silently discard evidence from an already-submitted payload. This bounded
flow does not provide a report-evidence route to hidden legacy chat. A report
without retained evidence remains a report, not proof that the conduct occurred.

## Operator queue

Only operator commands list or inspect reports. Their output is escaped JSON
(`ensure_ascii=True`), including names, text and notes, so terminal control
characters are not executed. Keep the output private; do not paste it into a
public issue or model prompt. Prefer notes from stdin so they do not appear in
shell history or process arguments:

```sh
python main.py report list
python main.py report list --state acknowledged
python main.py report list --state all --limit 200
python main.py report show REPORT_ID
python main.py report acknowledge REPORT_ID --operator OPERATOR_LABEL --note -
python main.py report close REPORT_ID --operator OPERATOR_LABEL --note -
python main.py chat-log delete EVIDENCE_REF
python main.py chat-log delete-tester TESTER_INVITE_LABEL
python main.py chat-log export-deletions /private/chat-deletions.json
python main.py chat-log replay-deletions /private/chat-deletions.json
python main.py community-status
python main.py community-prune
```

Assign an operator to check the private queue at least twice daily. Check both
`report list` and `report list --state acknowledged` so pending follow-up remains
visible. A second operator must be in place before the cohort begins; record
the assigned operators and coverage arrangement before tester access.
`report list` defaults to open reports so older closed records cannot fill the
polling result. Each list shows the oldest retained
matching reports, up to 50 by default; acknowledge or close reviewed reports and
poll again to drain a longer open queue. Use `--state acknowledged` or `--state
closed` for those queues, and `--state all` for a combined inspection; `--limit`
can increase the result bound to 200. Inspect each new report and acknowledge
or close it with a private note. The beta goal is operator attention within
24 hours, including hard-rule concerns; this code does not claim that a live
staffing or monitoring commitment exists. It sends no emails, Slack messages or
other notifications. Record the polling arrangement before tester access.

Use existing sanction commands for an independently reviewed consequence and
existing redaction for abusive words in permanent history. A queue status change
is not a sanction and is never a fictional chronicle event.
Acknowledgements, closure and their private notes share the report's original
deadline; triage never resets it. Open and acknowledged cases and their actions
remain available past that deadline until closure. A closed case whose original
deadline has passed is eligible for cleanup.

## Retention and backups

Only operators can read the private log, to investigate complaints and understand
how testers played together. Under `until_deleted`, messages remain available
without a timed expiry until the tester asks for deletion or leaves the study.
Use `chat-log delete` for one line's opaque evidence reference, or
`chat-log delete-tester` for all chat belonging to the participant resolved by an
unambiguous tester invite label, including chat written under rotated keys.
These commands operate on the configured live database, not backup copies.
Keep the separately exported deletion ledger for as long as a backup containing
those lines may be restored; its entries contain no message or name text.
After every completed deletion, export the current deletion record and keep a
private durable copy outside the database snapshot and the app's volume. The
record contains only actually deleted evidence references and UTC timestamps,
without message text, names or participant identities. Export writes an atomic
file with mode `0600`; protect transferred copies to the same standard. Held
messages are not recorded as deleted. Deleting one tester's current messages
does not target messages they send later.

Deletion skips messages cited by an open or acknowledged report, deletes other
eligible messages and returns matched, deleted and held counts with the hold
reason. It neither silently fails the whole batch nor force-closes a complaint.
Explain a remaining hold to the requester and revisit it when the complaint
closes. Closure releases the hold; rerun the deletion command for a still-pending
deletion request. Review requests, study departures and outstanding holds at
the end of each study. Deleting the disposable watch world also deletes its
private log; do not carry that log into a retained cohort world. Resolve pending
complaints and their evidence holds before disposing of that world.

Each timed record keeps its recorded deadline; changing policy does not silently
shorten it. Reads include rows without an expiry and pending case/evidence holds.
Eligible expired records are unavailable to normal reads and operational cleanup
removes them. Status/prune commands report cleanup without printing stored
messages. Rehearse deletion, holds, expiry and restored-backup behavior on the
disposable staging twin. When the server is stopped, cleanup remains an operator
task.

Copies in backups are removed when those backups are deleted. Whole-database
backups can retain private chat, reports and triage records beyond live deletion
or expiry. Ordinary backup pruning protects the newest validated backup even
past its retention period; without a newer valid copy or separate deletion that
exception can be indefinite. Machine-local, downloaded and volume-snapshot copies
also need their own treatment. There is no finite erasure guarantee for all
copies from deleting live rows alone. No backup duration is chosen here.

### Deletion records during restore

Stop the server and all private-log writers before exporting, restoring or
replaying deletions. Every backup containing the `private_chat_messages` table
requires an explicit `--deletions` file, even when the current database exists
or that table is empty. Current ledger records are still merged into the restore;
their presence does not waive the explicit file.

For routine recovery with the intact current database, export its latest ledger
before overwriting it, preserve a private durable copy outside the snapshot and
app volume, and pass that file to restore:

```sh
python main.py chat-log export-deletions /private/chat-deletions.json
python main.py restore --from /private/worlds-backup.db --deletions /private/chat-deletions.json --yes
```

For a lost or recreated database, retrieve the latest independently preserved
operator export and copy it into the maintenance environment. Skip the export
command above: initializing a fresh database with `init_db` on a replacement
volume still counts as lost-store recovery. Its new empty ledger or export must
not replace the independently preserved record. An older ledger inside the
backup cannot establish the latest deletion state either.

Keep the independent export after every deletion, not only when a restore is
planned. An explicit empty record is usable only after the operator verifies
that no outstanding deletions need to be applied for this restore. A fresh or
locally empty ledger is not that verification. An omitted required file or a
missing/corrupt supplied export aborts before the live database is overwritten.
Without the latest record or that verified empty state, keep service closed and
resolve the deletion evidence before restoring access.

A backup predating schema 33, with no `private_chat_messages` table, can be
restored without the file; current ledger records are still carried forward.
That exception does not waive the file on any later private-chat restore.
Restoring a pre-33 backup or initializing its replacement volume cannot be used
to make a subsequent schema-33 backup count as a restore without private chat.

If recovery replaces the database outside `main.py restore`, validate, merge and
replay the external record on the restored store before starting any writer:

```sh
python main.py chat-log replay-deletions /private/chat-deletions.json
```

Replay validates the entire file before an atomic merge/deletion. It preserves
only references proven to have been deleted: an old backup's stale open-report
state cannot resurrect those lines. Messages that were held when deletion was
requested have no deletion proof, so their complaint hold remains. Later
messages have different references and are unaffected. Complete deletion replay
and the other restore reconciliation before restarting or admitting traffic.

The participation notice must distinguish live chat, operator access, separately
retained report detail, both purposes, until-deleted retention, complaint holds,
the contact, the still-recorded exchanges and backup treatment. A changed notice
requires a new acknowledgement through the participation gate. All studies use
personal invites and require affirmative confirmation of age 18 or older.
Registration asks before redeeming its first key; an operator-minted key must
acknowledge that same current notice revision before play. Neither acceptance
path replaces research consent or approves external destinations or deployment.

The notice is required when `NESTED_WORLDS_TEST_WORLD` is on or the personal-invite
gate has ever been activated. This condition is independent of community
collection policy: a collection-off watch or invited study still requires
`NESTED_WORLDS_TEST_CONTACT`, `NESTED_WORLDS_TEST_RETENTION` and
`NESTED_WORLDS_TEST_DATA_USE` with the approved notice wording. The optional
`NESTED_WORLDS_TEST_MIN_AGE` accepts only `18`; it is not needed to select the
owner's minimum age. The invite gate is permanently latched: revoking the last
key does not reopen public access. Emergency chat/report switches affect
collection availability, not this required notice or its revision. Ungated
non-study local development is outside that study condition; an unrecognized
test-world flag or incomplete study notice fails ready checks. This boundary is
not a fixture bypass.

This release changes the notice on existing studies. Before continuing, verify
`GET /participation` serves the new revision with `required: true` and `ready: true`, and have each
existing tester read and acknowledge it and affirm their age themselves. Policy
wording changes need another acknowledgement. Do not carry forward old acceptance
or automatically replay an interrupted/refused chat, report or action after reconsent; a saved
draft remains the tester's choice to submit.
