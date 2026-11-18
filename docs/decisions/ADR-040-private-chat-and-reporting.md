# ADR-040: Private traveler chat and operator reports

**2026-11-18 owner adoption:** Accepted as implemented in #174 (item 43 of the [2026-11-18 owner decisions](../roadmap/owner-decisions-2026-11-18.md)).
Adopted for a kept world, taking effect with the community policy file and the
bucket account: messages not under a complaint hold are deleted 30 days after
the cohort's last window (item 34), and backups are kept 30 days under a 7-day
delete lock, with the deletion ledger under a separate prefix (item 12). Still
to be named: the second operator (item 31).

**Status:** Accepted as implemented in #174 by the owner, 2026-11-18 (note
above).
Earlier status, kept as the record: Proposed for scoped implementation review, revised 2026-11-15.
The owner's [Version 4 direction on PR #174](https://github.com/mark-weeks/hello-nested-worlds-adventure/pull/174#issuecomment-6896201907)
selects operator-only chat retention until deletion, complaint evidence holds and
affirmative adult participation. The merge remains the human gate for the
additive operational schema and the prospective ADR-004 storage amendment. This
record does not deploy a policy, choose a model destination or ratify broader
agent-conversation proposals.

## Context

Human WebSocket chat was broadcast and appended as `PLAYER_CHAT` to the permanent
chronicle. Public history and voice prompts could expose its words. Reports had
no private intake or stable chat-evidence reference. Study operators need to
investigate complaints and understand how testers played together without making
that conversation permanent world history or model memory.

## Decision

Replace every new human WebSocket chat chronicle write with a private operational
append, committed before live room-wide broadcast. Create no permanent event,
even a wordless trace. Live delivery stays unchanged; players receive no history
scrollback. Keep moderation, authorization, participation and sender-only
`chat_declined` draft restoration. Explicitly enabled unkeyed, non-study local
chat uses its server session and displayed name; keyed chat resolves the current
credential to its stable participant atomically. Store no credential, credential
digest or IP in these operational records.

Removing the writer is a separate one-way recording decision from the additive
schema step. Once deployed, new human chat leaves the never-wipe chronicle. Rows
not written during that period cannot later be restored as original chronicle
history by rolling back code. The private log is not permanent-history storage.
Existing chronicle rows stay intact.

Require an immutable operator community policy in hosted and local modes.
Missing policy disables chat and reports; other gameplay keeps its existing
gates. The selected chat policy is `{"enabled": true, "retention_mode":
"until_deleted"}`. Its rows have no expiry and remain readable until deletion.
Numeric chat TTL policies are refused; schema33 has not been deployed and has
no legacy timed-chat contract to preserve. Enabled reports require explicit integer retention days. The
owner selected 90 days for the disposable watch and 180 days for the retained
cohort; these are documented operating decisions, not deployment defaults or
checked-in policy selections. Enabled collection also requires contact and
backup-treatment wording. Invalid configured policy refuses startup before
migrations/listeners. Emergency switches can deny collection but do not alter
the frozen participation policy or grant a new route.

Only operators can read the private log, for complaints and understanding study
interaction. Retain messages until the tester asks for deletion or leaves the
study, subject to the complaint hold below. Provide operator commands to delete
one message by evidence reference or all chat for one tester across rotated
credentials. Delete eligible rows, skip held rows and report the held count and
reason. Closing a complaint releases its hold; it does not automatically delete
an otherwise retained message. Review deletion requests, departures and holds at
the end of each study. Deleting a disposable watch world also deletes its private
log. Copies in backups disappear when those backups are deleted; live deletion
does not erase backup copies.

Add Report beside existing Block controls in both clients, using one dialog per
client and leaving the existing composer in place. A live personal invite is
required to file. The reporter comes from authentication, never the body; self
reports are refused. Opaque viewer-scoped handles select targets. Retained chat
evidence can identify its author after a live handle expires; displayed names
cannot select someone. The target is not told who reported them. The response
contains only an opaque receipt. Report text never goes to a model or public
history.

Chat frames carry an opaque evidence reference, not a database row id. A report
cites the original line without copying it. Open and acknowledged complaints,
their triage actions and cited messages remain available until the complaint
closes, even beyond a recorded expiry. Closure does not reset the original
deadline; closed expired cases and their actions become eligible for cleanup.
Unknown or unavailable evidence is refused for a new report. The UI keeps the
draft so the player can choose a current target and submit a new request without
that reference. Reporter-supplied detail has the report's retention and remains
identified as their statement.

Report request ids are random and retries preserve the exact payload. Persist
idempotency under stable reporter identity before resolving transient handles;
an exact retry can recover its receipt after restart while the report is
retained. Changing the selected person clears a report draft; choosing the same
person preserves it. Existing short chat draft references are correlation tokens,
not deduplication keys. Reconnect or renewed consent never auto-resends.

Keep legacy chronicle rows byte-for-byte. Normal public/model projections omit
`PLAYER_CHAT` before limits, counts and cursors, with a defensive prompt filter.
Operator history tools and backups can still contain those old words. Preserve
historical aggregate art wear and metadata-only style windows. The new private
log feeds neither prompts nor art. Place exchanges (`PLAYER_SPEAK`), addressed
inhabitant exchanges (`AGENT_VOICE`) and authored ambient `AGENT_TALK` remain
recorded under their existing rules. ADR-037's proposed model-driven chat stays
outside this batch. No birth, golden, world-meta or era-name rule changes.

The study notice explains operator-only access, both purposes, retention until a
deletion request or departure, complaint holds, contact and backup copies. All
studies use personal invites. Both registration and operator-invited play require
affirmative confirmation of age 18 or older and acknowledgement of the same
current notice revision. The notice gate applies whenever test-world mode is on
or the permanent invite gate has latched, independently of collection policy. A
collection-off deployment still supplies the operator's TEST_* notice values. An
emergency collection switch or revoking the last key cannot remove that gate;
ungated non-study local development remains outside the study condition.

Operator commands list/show/acknowledge/close the private queue with escaped
terminal output and notes through stdin. No automatic sanction, jury,
notification or external messaging service is introduced. Existing sanctions and
redaction stay explicit operator actions. The 24-hour handling goal still needs
an assigned reviewer/workflow and staging rehearsal. Check the queue at least
twice daily; a second operator must be in place before the cohort starts. The
first deployment carrying schema33 goes only to the throwaway staging twin.

Reads include chat with no expiry and pending complaint holds. A
lifecycle-managed worker and operator prune command remove eligible expired rows
independently of gameplay and the heartbeat, including after startup/restore.
Every completed erasure atomically records only its opaque evidence reference
and UTC time in a deletion ledger. Held lines are omitted; future lines by the
same person are never selected. Startup replays these records before listening.
Restore carries current records into a candidate database and replays them
before replacing live data, including when restoring schema32. Completed erasure
proof overrides an old backup's stale open-case state. Stop writers before
restore and restart only after reconciliation.

Export the text-free ledger after each completed deletion to private durable
storage outside the restored snapshot and database volume. Every restore of a
backup containing `private_chat_messages` requires an explicit `--deletions`
record, regardless of whether the current database or private-chat rows exist.
Current ledger records are still merged. Routine recovery exports the intact
current store's latest ledger; lost-store recovery retrieves the latest
independently preserved operator record. Initializing a replacement volume does
not make its fresh empty ledger authoritative, and neither that export nor the
backup's older ledger may replace the independent record. An explicit empty
record is appropriate only after the operator verifies that no outstanding
deletions need to be applied for the restore; local emptiness is not proof.
Omitted required files or invalid supplied records abort without changing live
data. A pre-33 backup with no private-chat table can restore without the file,
but any later private-chat restore still requires it. Keep deletion records while
a backup containing those lines can still be restored.

Whole-DB backups retain copies beyond live deletion or expiry; newest-validated
and local/downloaded copies can survive until separately deleted. Their treatment
must be recorded accurately without promising a finite all-copies erasure time.

## Trade-offs accepted

- Until-deleted retention needs operator handling of requests, departures and
  end-of-study review; elapsed time alone does not delete those chat rows.
- Open complaints defer deletion of cited lines and pending case records.
  Commands make the hold visible rather than silently dropping evidence or
  failing an otherwise eligible bulk deletion.
- Old chat stays hidden from normal projections without rewriting history.
  Existing worlds and backups need honest legacy-data wording.
- Offline handles can expire. Evidence or a retained receipt can recover a
  submission; a client never guesses a target from a name.
- Additive private tables create a forward schema step. The migration number is
  assigned at merge, not reserved by this record.

## Revisit when

- A study ends: review deletion requests, departures, open complaints and backups.
- A complaint requires a different preservation rule or an external alert.
- Agent chat, place-local chat or a moderation path changes the data flow.
- Retention-scoped idempotency or legacy-data handling proves insufficient.

## Rejected alternatives

- Keep writing `PLAYER_CHAT` on log failure: it defeats the privacy choice.
- Leave a wordless permanent chat trace: it still records the private exchange.
- Broadcast before committing: recipients could see unreportable lost evidence.
- Copy chat into reports: references preserve original evidence without a second
  authoritative quotation.
- Resolve a target by displayed name: names are not ownership or stable identity.
- Delete cited evidence while a complaint is pending: it prevents review.
- Treat documented study windows as deployed configuration: the running process
  must load and expose the operator's selected policy.
