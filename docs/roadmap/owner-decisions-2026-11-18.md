# Owner decisions — 18 November 2026

*Recorded 2026-11-18 against `main` at `7d39ddf` for the owner, Mark Weeks. On
that day the owner worked through the open decision list with Claude Code,
amended five recommendations in his own words, and then wrote: "With those
clarifications, I believe we can now adopt answers to the outstanding questions
and formalize these decisions." This page is that formal record.*

**Provenance.** The decisions were given in a Claude Code working session, which
cannot be verified from the repository. The owner's merge of the pull request
that adds this page is the verifiable act, as with the working rules adopted in
#176. Quoted text is the owner's, copied from that session. Everything else is
the recommendation the owner adopted, written by the agent, except the text
marked *Added after review* (see below).

**What this page is not.** It builds nothing, deploys nothing, recruits nobody
and approves no spend, provider account or merge beyond its own. Where an
adopted answer needs a value only the owner can give (a name, an amount, an
account), the last column says so, and the answer does not take effect until
the value exists. It changes no working rule: `AGENTS.md` and the guides change
only in a pull request of their own.

**Revised after review, 2026-11-18 and 2026-11-19.** Codex and Grok Bot
reviewed the first version of this page at `4e88ed5`. Nine checking agents then
verified the first revision (`f7b933f`) against the sources it cites, and Codex
reviewed the second (`402dd5d`), the third (`80a08ad`) and the fourth
(`9875bfb`). The five rounds changed items 3, 5, 6, 8, 9, 12, 13, 14, 16, 19,
20, 22, 23, 25, 26, 28, 29, 30, 34, 38, 40 and 44. Two markers show what the
owner has not yet seen or decided:

- *Added after review* marks wording the agent wrote after the session. It has
  not been put to the owner. The owner's merge adopts it; anything unwanted
  should be struck before merging. Section 5 lists these in one place.
- **Open for the owner** marks a question that a merge of this page does not
  answer. Section 5 lists each one.

Everything unmarked is the recommendation the owner adopted in the session,
corrected only where review showed it to be wrong about a source.

## 1. Decisions in the owner's words

Five recommendations were changed by the owner. These quotes override the
recommendation wherever the two differ.

**D-A. The newcomer watch runs with AI on.** The recommendation had been an
AI-off watch.

> What do we mean by "AI is off in the test"? We need AI to power much of what
> makes Enfolded interesting, such as agent players, node voices, etc. We need
> to test this functionality.

**D-B. Names are natural and unique, with no appended characters.** The
recommendation had been to keep the twelve cast names as they were.

> Re: cast names, or any names for that matter, I do not want weird appended
> characters like "-9" in "Cartographer-9". Names of cast and nodes must be
> unique as well as natural, in the sense that "Cartographer" is much more
> natural than "Cartographer-9".

Asked to choose between changing what a world is born with and hiding the
suffix at display time, the owner wrote: "I agree with separating the name from
the address". Asked for the approval the golden-pin rule requires for that
change, the owner answered: "approved".
[ADR-041](../decisions/ADR-041-natural-unique-names.md) records the decision,
what the re-pin covers and why it is safe before any world is born. Under
`AGENTS.md` that approval is used in the task it was given in and does not
travel through a record: the naming pull request restates it and shows the
exact pin diff for the owner's read.

**D-C. Puzzles must be challenging and interesting; quality is a design
decision made before the kept world is born.** The recommendation had been no
generator change before the pilot.

> Regarding "many puzzles are solved by reading a property of the place", that
> sounds like a very weak puzzle. The goal is to provide players with
> challenging and interesting puzzles.

The owner then wrote: "Adopt the recommendation on puzzle quality improvement".
That recommendation is item 23 below.

**D-D. The first cohort should be able to engage with agent players.** The
recommendation had been no agents in chat before the cohort starts.

> Regarding agents in chat, ideally the first cohort would be able to engage
> with agent players in collaborative and/or competitive ways.

**D-E. What collaboration and competition with agents mean.**

> agents don't solve puzzles, so rivalry would come in other ways such as
> discovering new nodes or adjusting properties through interactions with
> competing goals

> To clarify, when I stated "agents don't solve puzzles" I mean that they do
> not solve puzzles by themselves. However, if a human player engages an agent
> and asks for help solving a puzzle, the agent may choose to cooperate and
> help if its goals are aligned with the human player. If the agent player has
> conflicting goals, then it can choose to decline assisting the human player.

## 2. Adopted answers

Item numbers are those of the list the owner worked on 2026-11-18. "Owner
words" marks an answer that comes from section 1. The last column is what the
answer still needs before it takes effect.

### Before the newcomer watch

| # | Question | Adopted answer | Still needed |
|---|---|---|---|
| 1 | Fly account and staging twin | The owner creates the account and dispatches the staging deploy, aiming for Friday 20 November. The twin is the watch venue. | Owner action: account, billing, token |
| 2 | Map view switch (entry requirement 2) | Directed as a client batch: `/` serves the shared React Map view, the current map stays reachable at a named path until the cohort read-out, and ADR-005 records the result. Assignment follows the default concern (the player journey in `/app`) unless the owner assigns it otherwise. | The client pull request |
| 3 | Watch with AI on or off | **Owner words (D-A): on.** Place voices, agent voices, free-text intentions and moderation run live. This moves items 24 to 27 ahead of the watch. *Added after review:* if the accounting stop latches on the twin, its live routes stay off. Nothing clears a stop today: there is no command for it, a restart does not, and a re-created twin must not be used as one, because the provider has already billed that day (ADR-039; `docs/development/model-policy.md`). Voices then fall silent, and shared lines the local screen cannot clear are held (ADR-004 section 2). The AI-on watch ends there, unless item 28's clearing procedure has been written and rehearsed first. | Items 24 to 27 |
| 4 | Chat and Report in the watch | On, with one session in which two testers overlap, so chat, co-solving and the report path are exercised once. | A community policy file for the twin |
| 5 | Watch particulars | The owner is lead, facilitator and operator. Two or three adults on desktop Chromium. The twin is destroyed within seven days of the last session. *Added after review:* this replaces "after watch reports are exported". The twin is destroyed only once every report from the watch is closed. An open or acknowledged report holds the twin, with the chat lines it cites, until the owner closes it (`docs/development/community-reporting.md`). Exporting reports does not keep that evidence, and no tool moves a case elsewhere. | Tester names and session dates; a runbook teardown change |
| 6 | Notice values for the twin | A contact address the owner reads daily; the destroy date from item 5; a data-use statement that names the model provider and says tester text is sent to it to run the game and is not used to train models. *Added after review:* the notice also says that an open complaint can extend the destroy date (item 5), what happens to the twin's backups and other copies (item 12), and how long reports are kept: a closed report until its original 90-day deadline (ADR-040) or until the twin is destroyed, whichever comes first; an open or acknowledged complaint, with the lines it cites, until it is closed. Closing a complaint does not restart its 90 days and does not delete the lines it cited: they stay, like other chat, until a tester asks for deletion or leaves the study, or the twin is destroyed. | The contact address; the provider from item 24 |
| 7 | Invite gate at deploy | The first key is minted as a step of the deploy, on staging and in the production runbook, so the gate is never open after a deploy. | A runbook change |
| 8 | Watch kit | Refreshed once items 2 to 6 and 12 are settled; it still says the honesty rule does not exist. *Added after review:* its teardown section is rewritten to match items 3, 5 and 12. | The refresh |

### Before the first cohort invite: world and recovery

| # | Question | Adopted answer | Still needed |
|---|---|---|---|
| 9 | When the one-way door closes | ADR-004 governs: never-wipe starts with the first invited outside player. *Added after review:* this replaces "when the first cohort invite is redeemed. Until then a production volume may be booted, rehearsed and re-created". That player may enter with an operator-minted key or a redeemed registration invite. Rehearsals stay on staging, as ADR-004 section 3 requires for a disposable world. A production boot is itself a door: the world is born at the first heartbeat tick or `/world` request, and from that tick the cast starts pinning puzzles and writing rows. **Open for the owner:** the checklist's R3 bars a reset once the world's status is declared (item 10: at the watch read-out), which is earlier than ADR-004's boundary. Until the owner says which governs, a declared production world is not reset. The two runbook passages that said the first deploy makes history permanent are corrected in this batch. | The owner's answer |
| 10 | World status | Production for the cohort world, declared at the watch read-out once a downloaded backup restores into isolated staging and item 11 passes. Staging and any local watch are disposable. | The declaration, at the read-out |
| 11 | Backup clock | An outside scheduler dispatches the backup every 30 minutes. The one-hour bound is proven over seven consecutive days on the twin. Continuous replication stays after the pilot and before a second cohort. | The scheduler service |
| 12 | Backup bucket and retention | The runbook's S3-compatible bucket, 30 days, a 7-day delete lock, no lifecycle rule; the deletion ledger under a separate prefix. The snapshot size is measured first. *Added after review:* the backup workflow prunes only the app it is backing up and always keeps that app's newest copy, so once the twin is destroyed nothing prunes its snapshots, which hold private chat and reports. They are deleted from the bucket by hand (`scripts/backup_store.py delete-before`, then `delete` for the newest copy), as a step to be added to the runbook's teardown. Those commands and the workflow's own 30-day prune delete by key alone. On a bucket that keeps object versions, which a delete lock on Amazon S3 needs, that hides a snapshot and leaves its versions retrievable (the reviewer's reading of the provider's documentation; this session could not reach it to re-check). So no notice, for the twin or the cohort, states the 30 days or a deletion date until the chosen backend's erasure procedure has been checked, including deleting the retained versions and confirming they are gone. Until then the notice says backup copies stay until the operator deletes them, and promises no date (ADR-040). No document yet says what the 7-day delete lock counts from. If it is seven days from each upload, the last copy can go seven days after the twin's last backup. Once the procedure is checked, the notice states that rule. It also names the other copies: the host's own volume snapshots, which the runbook says are kept five days, and any copy the operator downloaded. | The bucket account; a definition of the delete lock; a checked erasure procedure; a runbook teardown change |
| 13 | Monitor, Sentry, tokens | The scheduler from item 11 also alerts one address on backup freshness, uptime and voice health. Sentry is on, with frame locals off and a line in the notice. Production tokens live in a main-only GitHub environment. *Added after review:* if one scheduler both starts the backups and checks their freshness, and it stops, nothing raises an alarm. So a second service is needed: it either runs the freshness check on its own timer or alerts when the check has not reported in, as the [backup cadence record](../evaluation/2026-11-11-backup-schedule-cadence.md) requires. Which of the two is chosen with the scheduler service. | The alert address; a second service for the freshness check |
| 14 | Cast names | **Owner words (D-B).** "Cartographer-9" becomes "Cartographer". No cast name carries appended characters. A name used in production stays reserved forever. | The naming pull request (ADR-041), where the owner approves the exact pin diff |
| 15 | Reserved names | Admin, Moderator, Operator, System, Enfolded and Traveler join the reserved list; retired cast names stay reserved. | An ADR-004 section 7 change with the code |
| 16 | Era names repeat | Accepted for the cohort. Eras are materialized before the week of 19 April 2027, when seed 382 first repeats a name. | A ratified design for materializing eras, and its build, before 19 April 2027 |
| 17 | Identity migration (D6) | Not before the pilot; before the first structural operation. This closes the ADR-029 conflict. The alias table stays additive because names are unique (ADR-041), not because a name encodes its position. | — |
| 18 | Presence rows | Kept. They are excluded from a place's ten-row memory, and reconnects are debounced. The notice says arrivals and movement are permanent. | The code change |

### Puzzles

| # | Question | Adopted answer | Still needed |
|---|---|---|---|
| 19 | Ratify ADR-036 | Ratified with its recorded answers as starting values: an unsolved puzzle never renews by itself; the longest patience send-away is four hours; each player climbs their own hint ladder; a send-away says when to return; at most twelve judged misses for one player at one puzzle in any rolling 24 hours, not to be raised without re-running the band search. A send-away that this cap binds lasts until at most ten of that player's judged misses at that puzzle lie in the last 24 hours (ADR-036's rule), which can be most of a day. A helping agent is not named in the solve credit. "An annoyed player" is read as an annoyed puzzle. Ratification authorizes batches 2 and 1b, and item 21's change, which ADR-036 lists in batch 3; batch 1a merged in #170. | — |
| 20 | Next puzzle batches | Both directed: the cast stops attempting puzzles, and per-player send-aways replace the shared pool. *Added after review:* this replaces "The kept database is born after the first of them". ADR-036 D8, which item 19 ratifies, puts the send-away batch (1b) before the batch that stops the cast (2) and says both should land before the first production boot, because each opens a write path. The kept database is born after both. | The two pull requests |
| 21 | Wrong-guess text (ADR-036 question 6) | Only right or wrong is stored. It ships as a small change before the first invite. | The code change |
| 22 | Puzzle salt (ADR-038) | The owner adopted the salt in principle, with separate staging and production salts. **Open for the owner (a first-boot door):** ADR-038's question 1, whether the hosted world gets the salt before its first boot. The first version of this page said the salt did not gate the cohort; review showed that this conflicts with ADR-038. A puzzle pinned without the salt stays computable from the public code until its place renews, the heartbeat starts pinning at the first tick, and under item 19 an unsolved puzzle never renews by itself. Recommended: before the first boot (ADR-038's B1 and B2). The salt's code (ADR-038's B1) can be built alongside item 20's batches. The kept boot then waits for whichever finishes last: those batches, the naming change, the puzzle redesign (item 23), or the salt's build and deployment (B1 and B2). ADR-038 has the salt probe and its audit rerun when the guess limit or a puzzle family changes, so the production salt is audited against the final generator. The cost is the B1 pull request, one secret on each app and the working-rules change that follows. **Also open:** approval of ADR-038's D8 wording for `AGENTS.md` (its question 3), which changes a working rule and so goes in the working-rules pull request (item 44). | The owner's answers |
| 23 | Puzzle quality | **Owner words (D-C).** Replaces "duplicate answers". The generic kinds (anagram, cipher, number pattern, riddle, ordering: 1,445 of 4,208 puzzles on seed 382) are retired. Prediction is deepened. The look-up kinds are redesigned so a player must infer or experiment. Agent collaboration is designed with them (item 40). The work starts with a design record holding ten sample puzzles per proposed kind for the owner to judge, before any generator code. The watch is not held for it; the kept world is. | The design record; then the owner's approval of the puzzle re-pin, in the redesign's own pull request |

### Models and spend

| # | Question | Adopted answer | Still needed |
|---|---|---|---|
| 24 | First controlled model route | For the watch: ADR-035 is accepted for one named endpoint, and the choice ends with the disposable twin. For the cohort: decided from what the watch shows; the alternative on record is a controlled transport for the incumbent provider. | The endpoint and vendor. One check, not yet made: whether the incumbent provider's own Chat Completions-compatible endpoint satisfies the adapter |
| 25 | Data rules | Packet decision 10's operating rules 1 to 4 are accepted. In addition, one sign-off covers one provider account, under named terms, at one exact endpoint, for listed data classes. No Enfolded data trains any model during the pilot. *Added after review:* that last sentence answers the packet's question about models that are not plainly frontier, and makes its rule 5 unnecessary. | One data-use note for item 24's endpoint, signed |
| 26 | Dollar ceilings | Starting values: 15 dollars a day global and 3 dollars a day per participant, adjusted after a staging test shows what one full-context reservation costs. A 150-dollar provider spend limit is the outer bound. | The owner's confirmation of the amounts in the policy file, and a spend-ledger retention period of two days or more, which the policy file must carry and ADR-039 asks the owner to approve |
| 27 | Models | The voice, intention and moderation models are pinned in the policy file. One live rubric run, with the owner as the single grader, recorded as a deviation from the two-grader rule. | The model ids |
| 28 | ADR-039 | Accepted after one staging rehearsal of reservation, settlement and the stop. A written procedure to clear the accounting stop exists before any live route on a kept world. *Added after review:* the stop is rehearsed on a separate throwaway app, or after the last watch session, because a latched stop keeps a twin's live routes off (item 3). | The rehearsal |
| 29 | Call caps | The global text cap rises to about 1,000 a day; 150 per player stays. Caps are set before day one. *Added after review:* the classify caps are set with them, because item 30 makes every shared line a classifier call and the defaults are 60 a player a day and 2,000 shared. | The exact integers, set as secrets at deploy |
| 30 | Moderation coverage | Every line of shared text on Speak, agent voice, Ideas and published profile fields goes to the classifier when it can be reached. Chat stays on its current screen, because chat is no longer permanent or quoted. *Added after review:* the first version said "a surface that stores words", which would have taken in private text. Today only a line the local screen marks ambiguous is sent, so this is a change. Registered names also stay on their current screen. Private journal notes and unpublished profile text are not screened, and report text is never sent to a model, as ADR-004 already says. **Open for the owner:** what happens to a shared line when the classifier cannot be reached, a cap is spent or AI is off. Today a line the local screen cannot clear is held and a locally clean line still publishes (ADR-004 section 2). Recommended: hold every shared line then, because otherwise a player who spends their classify cap can publish unclassified lines. The cost is that Ideas, profile publishing and stored Speak lines stop while the classifier is down. | An ADR-004 section 2 change with the code; classify caps sized for one call a line (item 29); the owner's answer |

### Safety, people and admission

| # | Question | Adopted answer | Still needed |
|---|---|---|---|
| 31 | Second operator | One adult the owner trusts, named before recruiting. They read the queues and the log and can use the kill switches. Sanctions, redaction and deletion stay with the owner. | The person |
| 32 | Governance | The owner alone suspends and bans. One report opens a case and triggers nothing automatically. The owner emails each sanction with its reason and an appeal address. Juries wait until reports outrun the owner's 24-hour reading. | — |
| 33 | Report path, remainder | Twice-daily manual queue checks stay. The reported traveler's recent retained lines are added to the operator's report view. | The code change |
| 34 | Chat log end date | Messages not under a complaint hold are deleted 30 days after the cohort's last window. The notice states the date. *Added after review:* the policy file cannot hold a chat expiry (ADR-040), so the operator runs the deletion on that date. A line the run skips because a complaint holds it has no expiry of its own. At that run the operator records the evidence references cited by each open or acknowledged report (`report show` lists them). Once the last hold on a line clears, the operator deletes that line by its reference (`chat-log delete`), not by tester: a tester-wide run would also delete what that tester wrote after the first run. The deletion record is exported again after each of those deletions and kept for restores (`docs/development/community-reporting.md`). | The cohort's last window date; the operator's deletion run, and a deletion by reference for each line a complaint held |
| 35 | Served history | Before the first invite, `/chronicle` and `/history` stop serving the `actor` field and the `agent` and `persona` keys. Stored rows are untouched. | The code change |
| 36 | Terms and notice | One combined page, served as the notice text. It names the owner as data holder, the host, bucket, monitor and model provider, and says an idea may be summarized publicly. The first cohort is adults in the owner's own country. | The page |
| 37 | Cohort exceptions | One dated list, signed at the watch read-out: later-improvement rows excused, measurement rows required only to be instrumented. | The list, at the read-out |
| 38 | Evidence gates | The four pilot gates are adopted as hypotheses reported with counts. A missed gate buys one fix-and-rerun round. Playtest bars are readings with one tripwire. *Added after review:* the first version did not say what the tripwire is. Proposed: a puzzle family with five or more attempted puzzles and none solved, or an overall median interest rating under 3, opens a fix before invitations go beyond the first cohort. It is read at the watch read-out and at each cohort read, and is not an entry requirement. Ratings are collected by the facilitator's question; no rating surface is built. | The owner's confirmation of the tripwire, at the read-out |
| 39 | Dates | Watch sessions by 11 December 2026. The cohort start is set at the watch read-out. The earlier January targets are withdrawn, because the naming change, the puzzle redesign and agents in chat now precede the cohort. | — |
| 40 | Agents in the first cohort | **Owner words (D-D, D-E).** In scope. Agents never solve a puzzle by themselves. When a human asks an agent for help, the agent may help if its goals align with that player's, and may decline if they conflict. Rivalry is over aims, such as discovering places or shifting properties toward competing goals, never over solving. ADR-037's batches are directed. Agents need stated goals; a design note sets them and the rivalry, written with item 23. ADR-037's standing answers: at most two lingering travelers (D2); travelers in chat and Speak for places (D1); agent chat lines stored as human chat is (D8); an honesty answer goes to the asker alone (D3). *Added after review:* the first version stated what is ratified only in the note on ADR-037. D1, D2, D4 and D5 are ratified, except D4's question about cast names (answered by D-B and ADR-041) and D5's proposed covenant text (item 44). D3, D6, D7 and D8 stay Proposed until the refresh, apart from the two answers above that fall under them. **Open for the owner:** who sees an agent's puzzle help, and whether it is stored (ADR-037 question 4). As ordinary chat a correct suggestion would reach everyone and be stored. ADR-037 recommends that it reach only the asker and not be stored, and says that needs private messages between people too, so that a private line does not mark the agent as an AI. This page leaves chat scope until after the cohort, so the owner's answer also settles that. Batch 4, the collaboration batch that ADR-036 and ADR-037 share, waits for this answer. The aim is to land it before the cohort enters; the cohort is not held for it. | The design note; ADR-037 refreshed against `main`; the owner's answer on puzzle help |

### Records and process

| # | Question | Adopted answer | Still needed |
|---|---|---|---|
| 41 | Status pull request | Asked for by this adoption. Claude Code prepares it once this page has merged; it folds the waiting fragments and applies the `Status:` lines of the fragment that lands with this page. | This page, merged |
| 42 | The 15 November decision page | To be committed, so `main` carries the owner's words that ten records cite. | The page, from the owner |
| 43 | ADR status pass | ADR-019, ADR-020 and ADR-021 are accepted as implemented. ADR-022 is accepted as implemented except its puzzle-eligibility paragraph, which the owner's 2026-11-06 decision overruled. ADR-040 is accepted as implemented. ADR-035 and ADR-039 stay Proposed until items 24 and 28. | — |
| 44 | Covenant re-tune (D9) | D9, the proposal to keep five covenants and demote the rest to guidance, is closed as stale; no covenant is demoted. **Open for the owner:** three wordings in `AGENTS.md` that work directed or recommended here will need. Each is approved in the working-rules pull request of item 45, not here. When ADR-037 D4 (no labels) ships, the sentence "live presence may distinguish" stops describing the product. ADR-036 batch 2 (item 20) changes the agent-solve covenant. ADR-038's D8 adds a clause to the determinism contract if the salt is adopted (item 22). | The owner's approval, in that pull request |
| 45 | Decision process | Two rules, to be written in a working-rules pull request of their own: reversible choices are listed as defaults and accepted by the owner's merge; an ADR asks the owner only door questions. At most three pull requests wait on the owner. | That pull request |
| 46 | Copilot | No budget is set. The merged rule lets work proceed without it. Every reviewer posts under a footer naming it. | — |
| 47 | Issues #87 to #89 | #89 gets a hold note that the owner posts; #88 stays deferred; #87 becomes one watch question (does a newcomer name the scale unprompted). | The note, posted by the owner |

## 3. Parked until the cohort starts

The delivery-priority rule in `AGENTS.md` already holds these. None needs a
decision now.

- **World evolution.** ADR-029, ADR-030, ADR-031 and ADR-033 are not ratified
  before the read-out. Then ADR-029 batches 1 and 2 only.
- **ADR-032.** Its solo puzzle attempts, persona tags and Speak delivery are
  superseded by the owner's decisions of 2026-11-06 and 2026-11-07 and by
  ADR-037. Budgeted cognition and the open roster wait for pilot evidence.
- **Alignment, rewards, external agents.** One yes-or-no on alignment at the
  read-out; no new reward for the first cohort; cohort keys are for people.
  Each needs a line in item 37's list.
- **No action.** ADR-015, ADR-016, the cooperative mystery, neighbor-linked
  art, the Python pin, juries, scene images and new provider adapters beyond
  item 24.
- **PixiJS.** Removed in the Map view client batch (item 2), after confirming
  that view does not need it.
- **Block scope.** Answered by the shipped behaviour: a block hides live speech
  and presence and never hides effects on shared places.

## 4. What lands with this page, and what follows

**In this batch.**

- [ADR-041](../decisions/ADR-041-natural-unique-names.md), new: names are
  labels, and the path is the address.
- A dated adoption note at the head of ADR-004, ADR-005, ADR-019, ADR-020,
  ADR-021, ADR-022, ADR-029, ADR-032, ADR-035, ADR-036, ADR-037, ADR-038 and
  ADR-040. Each note points here; the text beneath it is kept as the historical
  record. Where a note changes a record's status, its `Status:` line now leads
  with the new status and keeps the earlier text after it.
- The two runbook passages on when history becomes permanent (item 9).

**Not in this batch.**

- The status documents. The roadmap index, the checklist's held decisions and
  open questions, and the changelog are written only by the status pull
  request (item 41). Until it lands they still show these decisions as open,
  and this page governs.
- `AGENTS.md`. Its pointer still says ADR-019 to ADR-022 remain Proposed, and
  its covenant "live presence may distinguish" still stands. The pointer
  changes in the working-rules pull request of item 45. The covenant is
  reworded only with the owner's approval in that pull request (item 44).
- Every build: the naming change, the Map view, the puzzle batches, the puzzle
  redesign, agents in chat, the model route, the backup scheduler. Each is its
  own pull request under the working rules.

## 5. What is left for the owner

**Inputs only the owner can supply.**

1. The Fly account, billing and token (item 1).
2. The model endpoint and vendor for the watch, the signed data-use note for
   it, and the model ids (items 24, 25, 27).
3. Confirmation of the dollar amounts and the call caps when the policy file
   and the secrets are written (items 26, 29).
4. The contact address for the notice and the alert address for the monitor
   (items 6, 13).
5. The tester names and session dates for the watch (item 5).
6. The second operator (item 31).
7. The 15 November decision page (item 42).
8. The hold note on issue #89 (item 47).
9. The spend-ledger retention period, two days or more (item 26).
10. The bucket account and the scheduler service (items 11, 12).
11. A judgment on the sample puzzles in the design record (item 23).

**Open for the owner.** A merge does not answer these.

12. Whether the puzzle salt is in place before the kept world's first boot
    (item 22). Recommended: yes.
13. Which boundary bars a reset of a production world: the checklist's
    declaration of world status, or ADR-004's first invited outside player
    (item 9). Until answered, a declared production world is not reset.
14. Who sees an agent's puzzle help, and whether it is stored (item 40).
    ADR-037 recommends the asker alone, not stored, which needs private
    messages between people too.
15. What happens to a shared line when the classifier cannot be reached, a cap
    is spent or AI is off (item 30). Recommended: it is held.
16. The exact golden-pin diff of the naming change, approved in its own pull
    request (ADR-041, D7), and later the puzzle redesign's pin diff in its own
    (item 23).
17. Three wordings in `AGENTS.md`, approved in the working-rules pull request:
    "live presence may distinguish", the agent-solve covenant, and ADR-038's
    clause for the determinism contract (items 22, 44 and 45).

**At the watch read-out.** Declare the world's status (item 10). Sign the
exception list (item 37). Set the cohort date (item 39). Choose the cohort's
model route (item 24). Confirm or change the playtest tripwire (item 38). Give
the yes-or-no on alignment (section 3).

**Added after review.** The agent wrote these after the session. A merge adopts
them unless the owner strikes them:

- A latched spend stop ends the AI-on watch, and the stop is rehearsed away
  from the watch twin (items 3 and 28).
- An open report holds the twin (item 5).
- What the tester notice says about complaints, copies and reports (item 6).
- The watch kit's teardown section is rewritten (item 8).
- Who the first outside player is, and that a production boot is itself a door
  (item 9).
- The twin's backups are deleted by hand; the delete lock needs a definition,
  and no notice gives a backup deletion date until the erasure procedure is
  checked (item 12).
- A second service checks backup freshness (item 13).
- The kept database waits for both puzzle batches (item 20).
- The no-training sentence makes the packet's rule 5 unnecessary (item 25).
- Classify caps are sized with the call caps (item 29).
- Which text the classifier does and does not see (item 30).
- The operator runs the chat deletion, and later deletes by reference each
  line a complaint held (item 34).
- The proposed playtest tripwire (item 38).
- Batch 4 is an aim, not a condition of cohort entry (item 40).

**Values a merge adopts.** One reviewer asked that these agent-worded answers
be read as the owner's own before merging, because each sets a value reserved
for the owner: the dollar amounts (item 26), the dates (item 39), the vendor
path (item 24), backup retention and the delete lock (item 12), the chat
deletion date (item 34), the terms page and who is in the cohort (item 36), and
the change to the decision process (item 45).
