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
the recommendation the owner adopted, written by the agent.

**What this page is not.** It builds nothing, deploys nothing, recruits nobody
and approves no spend, provider account or merge beyond its own. Where an
adopted answer needs a value only the owner can give (a name, an amount, an
account), the last column says so, and the answer does not take effect until
the value exists. It changes no working rule: `AGENTS.md` and the guides change
only in a pull request of their own.

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
what the re-pin covers and why it is safe before any world is born.

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
| 3 | Watch with AI on or off | **Owner words (D-A): on.** Place voices, agent voices, free-text intentions and moderation run live. This moves items 24 to 27 ahead of the watch. A disposable twin whose accounting stop latches can be re-created (*inferred*; not rehearsed), so item 28's procedure waits for the cohort. | Items 24 to 27 |
| 4 | Chat and Report in the watch | On, with one session in which two testers overlap, so chat, co-solving and the report path are exercised once. | A community policy file for the twin |
| 5 | Watch particulars | The owner is lead, facilitator and operator. Two or three adults on desktop Chromium. The twin is destroyed within seven days of the last session, after watch reports are exported. | Tester names and session dates |
| 6 | Notice values for the twin | A contact address the owner reads daily; the destroy date from item 5; a data-use statement that names the model provider and says tester text is sent to it to run the game and is not used to train models. | The contact address; the provider from item 24 |
| 7 | Invite gate at deploy | The first key is minted as a step of the deploy, on staging and in the production runbook, so the gate is never open after a deploy. | A runbook change |
| 8 | Watch kit | Refreshed once items 2 to 6 are settled; it still says the honesty rule does not exist. | — |

### Before the first cohort invite: world and recovery

| # | Question | Adopted answer | Still needed |
|---|---|---|---|
| 9 | When the one-way door closes | ADR-004 governs: never-wipe starts when the first cohort invite is redeemed. Until then a production volume may be booted, rehearsed and re-created. The runbook sentence that said the first deploy starts the permanent world is corrected in this batch. | — |
| 10 | World status | Production for the cohort world, declared at the watch read-out once a downloaded backup restores into isolated staging and item 11 passes. Staging and any local watch are disposable. | The declaration, at the read-out |
| 11 | Backup clock | An outside scheduler dispatches the backup every 30 minutes. The one-hour bound is proven over seven consecutive days on the twin. Continuous replication stays after the pilot and before a second cohort. | The scheduler service |
| 12 | Backup bucket and retention | The runbook's S3-compatible bucket, 30 days, a 7-day delete lock, no lifecycle rule; the deletion ledger under a separate prefix. The snapshot size is measured first. | The bucket account |
| 13 | Monitor, Sentry, tokens | The scheduler from item 11 also alerts one address on backup freshness, uptime and voice health. Sentry is on, with frame locals off and a line in the notice. Production tokens live in a main-only GitHub environment. | The alert address |
| 14 | Cast names | **Owner words (D-B).** "Cartographer-9" becomes "Cartographer". No cast name carries appended characters. A name used in production stays reserved forever. | The naming pull request (ADR-041) |
| 15 | Reserved names | Admin, Moderator, Operator, System, Enfolded and Traveler join the reserved list; retired cast names stay reserved. | An ADR-004 section 7 change with the code |
| 16 | Era names repeat | Accepted for the cohort. Eras are materialized before the week of 19 April 2027, when seed 382 first repeats a name. | — |
| 17 | Identity migration (D6) | Not before the pilot; before the first structural operation. This closes the ADR-029 conflict. The alias table stays additive because names are unique (ADR-041), not because a name encodes its position. | — |
| 18 | Presence rows | Kept. They are excluded from a place's ten-row memory, and reconnects are debounced. The notice says arrivals and movement are permanent. | The code change |

### Puzzles

| # | Question | Adopted answer | Still needed |
|---|---|---|---|
| 19 | Ratify ADR-036 | Ratified with its recorded answers as starting values: an unsolved puzzle never renews by itself; the longest send-away is four hours; each player climbs their own hint ladder; a send-away says when to return; twelve wrong guesses a day, not to be raised without re-running the band search. A helping agent is not named in the solve credit. "An annoyed player" is read as an annoyed puzzle. Ratification authorizes batches 2 and 1b only; batch 1a merged in #170. | — |
| 20 | Next puzzle batches | Both directed: the cast stops attempting puzzles, then per-player send-aways replace the shared pool. The kept database is born after the first of them. | The two pull requests |
| 21 | Wrong-guess text (ADR-036 question 6) | Only right or wrong is stored. It ships as a small change before the first invite. | The code change |
| 22 | Puzzle salt (ADR-038) | Adopted in principle, with separate staging and production salts. It does not gate the cohort; it is built after item 20 and before any open invitation. | — |
| 23 | Puzzle quality | **Owner words (D-C).** Replaces "duplicate answers". The generic kinds (anagram, cipher, number pattern, riddle, ordering: 1,445 of 4,208 puzzles on seed 382) are retired. Prediction is deepened. The look-up kinds are redesigned so a player must infer or experiment. Agent collaboration is designed with them (item 40). The work starts with a design record holding ten sample puzzles per proposed kind for the owner to judge, before any generator code. The watch is not held for it; the kept world is. | The design record |

### Models and spend

| # | Question | Adopted answer | Still needed |
|---|---|---|---|
| 24 | First controlled model route | For the watch: ADR-035 is accepted for one named endpoint, and the choice ends with the disposable twin. For the cohort: decided from what the watch shows; the alternative on record is a controlled transport for the incumbent provider. | The endpoint and vendor. One check, not yet made: whether the incumbent provider's own Chat Completions-compatible endpoint satisfies the adapter |
| 25 | Data rules | Packet decision 10's operating rules 1 to 4 are accepted: one sign-off covers one provider account, under named terms, at one exact endpoint, for listed data classes. No Enfolded data trains any model during the pilot. | One data-use note for item 24's endpoint, signed |
| 26 | Dollar ceilings | Starting values: 15 dollars a day global and 3 dollars a day per participant, adjusted after a staging test shows what one full-context reservation costs. A 150-dollar provider spend limit is the outer bound. | The owner's confirmation of the amounts in the policy file |
| 27 | Models | The voice, intention and moderation models are pinned in the policy file. One live rubric run, with the owner as the single grader, recorded as a deviation from the two-grader rule. | The model ids |
| 28 | ADR-039 | Accepted after one staging rehearsal of reservation, settlement and the stop. A written procedure to clear the accounting stop exists before any live route on a kept world. | The rehearsal |
| 29 | Call caps | The global text cap rises to about 1,000 a day; 150 per player stays. Caps are set before day one. | — |
| 30 | Moderation coverage | Every line on a surface that stores words (Speak, agent voice, ideas, profiles) is classified when the classifier is up. Chat stays on its current screen, because chat is no longer permanent or quoted. | An ADR-004 section 2 change with the code |

### Safety, people and admission

| # | Question | Adopted answer | Still needed |
|---|---|---|---|
| 31 | Second operator | One adult the owner trusts, named before recruiting. They read the queues and the log and can use the kill switches. Sanctions, redaction and deletion stay with the owner. | The person |
| 32 | Governance | The owner alone suspends and bans. One report opens a case and triggers nothing automatically. The owner emails each sanction with its reason and an appeal address. Juries wait until reports outrun the owner's 24-hour reading. | — |
| 33 | Report path, remainder | Twice-daily manual queue checks stay. The reported traveler's recent retained lines are added to the operator's report view. | The code change |
| 34 | Chat log end date | Messages not under a complaint hold are deleted 30 days after the cohort's last window. The notice states the date. | — |
| 35 | Served history | Before the first invite, `/chronicle` and `/history` stop serving the `actor` field and the `agent` and `persona` keys. Stored rows are untouched. | The code change |
| 36 | Terms and notice | One combined page, served as the notice text. It names the owner as data holder, the host, bucket, monitor and model provider, and says an idea may be summarized publicly. The first cohort is adults in the owner's own country. | The page |
| 37 | Cohort exceptions | One dated list, signed at the watch read-out: later-improvement rows excused, measurement rows required only to be instrumented. | The list, at the read-out |
| 38 | Evidence gates | The four pilot gates are adopted as hypotheses reported with counts. A missed gate buys one fix-and-rerun round. Playtest bars are readings with one tripwire. | — |
| 39 | Dates | Watch sessions by 11 December 2026. The cohort start is set at the watch read-out. The earlier January targets are withdrawn, because the naming change, the puzzle redesign and agents in chat now precede the cohort. | — |
| 40 | Agents in the first cohort | **Owner words (D-D, D-E).** In scope. Agents never solve a puzzle by themselves. When a human asks an agent for help, the agent may help if its goals align with that player's, and may decline if they conflict. Rivalry is over aims, such as discovering places or shifting properties toward competing goals, never over solving. ADR-037's four batches are directed. Agents need stated goals; a design note sets them and the rivalry, written with item 23. ADR-037's standing answers: at most two lingering travelers; travelers in chat and Speak for places; agent chat lines stored as human chat is; an honesty answer goes to the asker alone. | The design note; ADR-037 refreshed against `main` |

### Records and process

| # | Question | Adopted answer | Still needed |
|---|---|---|---|
| 41 | Status pull request | Asked for by this adoption. Claude Code prepares it once this page has merged; it folds the waiting fragments and applies the `Status:` lines of the fragment that lands with this page. | This page, merged |
| 42 | The 15 November decision page | To be committed, so `main` carries the owner's words that ten records cite. | The page, from the owner |
| 43 | ADR status pass | ADR-019, ADR-020 and ADR-021 are accepted as implemented. ADR-022 is accepted as implemented except its puzzle-eligibility paragraph, which the owner's 2026-11-06 decision overruled. ADR-040 is accepted as implemented. ADR-035 and ADR-039 stay Proposed until items 24 and 28. | — |
| 44 | Covenant re-tune (D9) | Closed as stale. | — |
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
  record.
- The runbook sentence on when the permanent world starts (item 9).

**Not in this batch.**

- The status documents. The roadmap index, the checklist's held decisions and
  open questions, and the changelog are written only by the status pull
  request (item 41). Until it lands they still show these decisions as open,
  and this page governs.
- `AGENTS.md`. Its pointer still says ADR-019 to ADR-022 remain Proposed, and
  its covenant "live presence may distinguish" still stands. Both change in the
  working-rules pull request of item 45, with the covenant reworded when the
  labels go.
- Every build: the naming change, the Map view, the puzzle batches, the puzzle
  redesign, agents in chat, the model route, the backup scheduler. Each is its
  own pull request under the working rules.

## 5. What only the owner can supply

1. The Fly account, billing and token (item 1).
2. The model endpoint and vendor for the watch, and the signed data-use note
   for it (items 24, 25).
3. Confirmation of the dollar amounts when the policy file is written
   (item 26).
4. The contact address for the notice and the alert address for the monitor
   (items 6, 13).
5. The tester names and session dates for the watch (item 5).
6. The second operator (item 31).
7. The 15 November decision page (item 42).
8. The hold note on issue #89 (item 47).
