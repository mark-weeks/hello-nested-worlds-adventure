# Private traveler chat and operator reports

This batch prepares the owner's [Version 4 private-chat and reporting direction](https://github.com/mark-weeks/hello-nested-worlds-adventure/pull/174#issuecomment-6896201907).
Chat is retained until deletion; report windows are 90 days for a disposable
watch and 180 days for a retained cohort. These are documented operating
decisions, not deployment defaults or checked-in policy selections. The guide
does not ratify ADR-040, select a data destination or deploy a policy. The additive
migration `0033_private_chat_reports` follows schema 32 provisionally; its number
is assigned at merge and needs human review there.

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
with the operator's explicit integer duration. Existing numeric chat policies
remain supported under their recorded terms. Enabled collection also requires
top-level `contact` and `backup_notice`. The checked-in
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
python main.py community-status
python main.py community-prune
```

Assign an operator to poll `report list`, which defaults to open reports so older
closed records cannot fill the polling result. Each list shows the oldest retained
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

The participation notice must distinguish live chat, operator access, separately
retained report detail, both purposes, until-deleted retention, complaint holds,
the contact, the still-recorded exchanges and backup treatment. A changed notice
requires a new acknowledgement through the participation gate. All studies use
personal invites and require affirmative confirmation of age 18 or older.
Registration asks before redeeming its first key; an operator-minted key must
acknowledge that same current notice revision before play. Neither acceptance
path replaces research consent or approves external destinations or deployment.

The notice is required when `NESTED_WORLDS_TEST_WORLD` is on, or when the frozen
community policy configures chat or reporting and the personal-invite gate has
ever been activated. The invite gate is permanently latched: revoking the last
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
