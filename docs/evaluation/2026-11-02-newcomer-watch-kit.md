# Newcomer watch: facilitator kit (draft)

**Date:** 2026-11-02, against `main` at `23b8830`. **Status:** a draft that is
**contingent on the owner's venue ruling**
([decision packet, decision 2](../roadmap/decision-packet-2026-11.md#2-newcomer-watch-venue)).
If the ruling is to wait for the Fly staging twin, this kit does not apply as
written; follow [runbook section 3a](../infrastructure/fly-deployment.md#3a-staging-rehearsal--before-the-permanent-world-begins)
instead. The watch also waits on the
research basics that protocol 2 requires before anyone is approached
(facilitator, observation dates, devices, client, consent wording, and the
retention and deletion date: [protocol 2](2026-09-12-pilot-protocol.md), "Scope
and venue"), and on the S2 question below if live voice is on. This kit
recruits nobody, records no decision, and promises no persistence.

## What this watch is

The first 2 to 3 newcomer sessions of [protocol 2](2026-09-12-pilot-protocol.md),
script steps 1 to 3 only: entry, navigation, acceptance and
consequence recognition, observed with a facilitator present. It is not the
seven-day return cohort, so the return fields in the observation record stay
unknown. Each participant plays on the facilitator's machine, in a world that
exists for that session only and is deleted on the stated date.

## Setup facts, verified against the code

Each fact was read at `23b8830`. "Executed" means it was also run against a
scratch database outside the repository on 2026-11-02.

| Fact | Evidence | What it means for the session |
|---|---|---|
| `python main.py serve` binds 127.0.0.1, port 8080, by default. | `main.py:532-533` | The participant uses the facilitator's machine at `http://localhost:8080`. Do not pass `--host 0.0.0.0` unless the owner authorizes the network exposure (plain HTTP, the key in the URL, and a model credential if live voice is on). |
| The world database is `$HOME/.nested-worlds/worlds.db`, with no override. | `persistence/__init__.py:28` | A fresh scratch `HOME` per session is **mandatory**. Without one, the session's rows land in the facilitator's own database. The server and every CLI command for that session must use the same `HOME`. |
| With `NESTED_WORLDS_CANONICAL_SEED` unset, the server hosts seed 382. | `server/guard.py:133-135`, `multiverse/generator.py:30`; executed | Leave the variable unset. |
| `invite mint --name X` prints the key once and a share line of the form `<BASE>/?key=nw_…&name=X`, which lands on the explorer and never visits `/register`. | `main.py:318-328`, `main.py:354-366`; executed | Replace `<BASE>` with `http://localhost:8080`. The participant never sees `/register`'s consent line (`static/register.html:49-52`), which in any case promises permanence. Consent is verbal or written. |
| Minting the first key closes the invite gate; revoking the only key reopens it. | `server/guard.py:290-303`; executed (a keyless request got 403 after the mint and 200 after the revoke) | Never revoke the session key while its server runs. Stop the server instead. This stays true until the integrity PR in this batch lands. |
| Act requires a live personal invite, and derives request IDs with `crypto.subtle.digest` and `crypto.randomUUID`. The journal calls `crypto.randomUUID` when it loads. | `persistence/participants.py:33-48`, `static/intents.js:7`, `static/intents.js:32`, `static/interventions.js:86`, `static/journal.js:6` | Use `http://localhost`, which browsers treat as a secure context. A plain-http LAN address is not one, so Act commits and the journal would fail there. This is web-platform behaviour, not executed for this kit; the pre-session check below confirms it on the actual machine. |
| `NESTED_WORLDS_DISABLE_AI=1` makes `/speak` and `/agent/voice` answer the authored quiet line with HTTP 200 and `"ai": false`. | `server/handlers.py:1158-1160`, `server/handlers.py:1405-1408`; executed for `/speak` | The no-model option stays in fiction. |
| Chat lines the local screen clears are shared. A line it cannot clear needs the classifier and is held, in fiction, if the classifier cannot run. | `server/moderation.py:177-199`, `server/moderation.py:208-229` | With no working classifier, expect some ordinary chat lines to be held with the authored hold line. Record a held line as an observation, not a fault. |
| The heartbeat cast walks and talks unless `NESTED_WORLDS_HEARTBEAT=0`, and their conversation renders like human chat. | `server/heartbeat.py:22`, `server/heartbeat.py:71`, `static/explorer.js:1190-1195` against `static/explorer.js:1227-1236` | Say aloud that the named inhabitants are AI characters, not other people, until live labels ship. |
| The browser keeps the key and Act receipts in local storage. | `static/journal.js:4`, `static/intents.js:11-13`, `static/intents.js:29-34` | Use a fresh browser profile or a private window for each participant. |

## Decide before session one

1. **Venue.** The owner's ruling (packet decision 2).
2. **Research basics.** Recorded in the restricted research record
   (`docs/evaluation/2026-09-12-pilot-protocol.md:27-31`): facilitator,
   dates, the machine and browser used, client (the explorer is the invite
   default), consent wording, and the deletion date.
3. **Voice mode.**
   - *AI disabled* (recommended unless the owner rules otherwise): set
     `NESTED_WORLDS_DISABLE_AI=1` and keep provider credentials out of the
     session's environment. Places and inhabitants answer the authored quiet
     line. Speak can then be observed as an action, not as a conversation.
     The flag does not stop the classifier, which never reads it
     (`server/moderation.py:160-229`); leaving the credentials out is what
     keeps text from the provider in this mode.
   - *Live voice*: only with the owner's scoped S2 ruling for this disposable
     watch (packet decision 10). A participant's words to places and
     inhabitants, and chat lines at a node, are quoted into later prompts to
     the provider (`consciousness/__init__.py:868-873`). An intention they
     describe in Act is sent to the provider to be read
     (`consciousness/interventions.py:57-81`). Any shared text the local
     screen cannot clear goes to the provider's classifier
     (`server/moderation.py:184-224`), from every screened surface: chat
     lines (`server/websocket.py:227-228`), words to places and inhabitants
     (`server/handlers.py:1188-1189`, `server/handlers.py:1424-1425`), an
     incorrect puzzle guess the attempt will store
     (`server/handlers.py:1915-1918`), Ideas submissions
     (`server/ideas_api.py:80`), and profile text saved as published
     (`server/participant_api.py:33-37`). Disclose all of these in consent.
     The provider keeps its own copies under its own terms, which deleting
     the scratch world and the research archive does not reach: record the
     provider's current retention and deletion terms for API inputs in the
     research basics, read from its published terms before the first
     session, and state them in consent. Set low caps on every text-model
     budget the session can spend: voice and intention with
     `NESTED_WORLDS_ANTHROPIC_DAILY_CALLS` and
     `NESTED_WORLDS_ANTHROPIC_DAILY_CALLS_PER_USER` (`server/guard.py:43`,
     `server/guard.py:50`), and classifier calls with
     `NESTED_WORLDS_MODERATION_DAILY_CALLS` and
     `NESTED_WORLDS_MODERATION_DAILY_CALLS_PER_USER`, whose defaults are
     2,000 and 60 a day (`server/guard.py:80-86`).
4. **Display names.** The facilitator assigns each participant a neutral world
   name: not their real name, not their P-code, not one of the twelve cast
   names (`consciousness/__init__.py:309-313`), and not Observer or Scout,
   the names the agent endpoints default to (`server/handlers.py:1042`,
   `server/handlers.py:1591`; packet decision 7). The map from display name to
   P-code is kept only in the restricted record, outside the repository and
   outside the world database (`docs/evaluation/2026-09-12-pilot-protocol.md:57-60`).
5. **Consent.** Verbal or written, as the research basics specify, because a
   minted key skips `/register`.

## Pre-session check

Run it in a throwaway `HOME`, never the participant's, so the participant's
world contains no check traces.

1. In a new terminal, follow "Session setup" below with a throwaway `HOME`, a
   check name, and the voice mode the sessions will use. Its server and key
   checks must pass.
2. Open the share URL in a private window. The explorer loads, the place panel
   shows a place, and the connection is live.
3. Speak to the place, then confirm the voice mode from the server's answer,
   not from the words: the explorer shows only the words
   (`static/explorer.js:768`). In the same terminal:

   ```bash
   curl -s -X POST http://localhost:8080/speak -H "X-Beta-Key: $KEY" \
     -H 'Content-Type: application/json' \
     -d '{"node_name": "<the place in the panel>", "message": "Hello?"}'
   ```

   - *AI disabled*: `"ai": false` with "The worlds are quiet today. Try again
     tomorrow." (`server/handlers.py:1158-1160`, `server/guard.py:786`).
     That answer comes from the flag alone, so also run
     `.venv/bin/python main.py models` in the same terminal: it must print
     `provider not configured` (`main.py:239-247`). If it does not, a
     credential is in the environment and the classifier can still receive
     text (voice-mode item 3): remove it before any session.
   - *Live voice*: `"ai": true` (`server/handlers.py:1227`). Here
     `"ai": false` means `NESTED_WORLDS_DISABLE_AI=1` is still set, the
     provider is not configured or failed, or a cap is spent
     (`server/handlers.py:1193-1195`, `server/handlers.py:1228-1246`). Fix it
     before any session; a live-voice session does not run on the quiet line.
     Executed on 2026-11-02 with the setup block below: in AI-disabled mode
     the answer was the quiet line with `"ai": false`; in live-voice mode
     with an inherited `NESTED_WORLDS_DISABLE_AI=1` cleared but no
     credentials, it was an authored line that reads like a reply, also with
     `"ai": false`.
4. **Commit one Act** and see its pending or arrived state.
5. **Open the journal** (History & journal, then Journal) and save a note
   containing a marker word, such as `checkmarker`.
6. Send one chat line.
7. Run "After each session" step 1 and the scrub in step 2 on this check
   world, but do not move the copy to the restricted store.
   `grep -c checkmarker "$HOME/session-raw.db"` must print `0`. Any other
   count means private text would reach the research archive: fix the step
   before any session.
8. Stop the server with `kill "$SERVER_PID"`, close the window, and delete the
   throwaway `HOME`.

If step 4 or 5 fails, check the address bar first: it must read
`http://localhost:8080` (`http://127.0.0.1:8080` is also a secure context),
not a LAN address such as `http://192.168.…`.

## Session setup

One dedicated terminal per participant. Every command below runs in that
terminal so that it uses the same `HOME`.

```bash
export HOME="$(mktemp -d "${TMPDIR:-/tmp}/enfolded-watch.XXXXXX")"
unset NESTED_WORLDS_CANONICAL_SEED       # the world falls back to seed 382
export NESTED_WORLDS_DISABLE_AI=1        # AI-disabled mode
# Live-voice mode only (the S2 ruling): replace the line above with
#   unset NESTED_WORLDS_DISABLE_AI       # an inherited =1 would silence voice
cd /path/to/the/checkout
.venv/bin/python main.py serve > "$HOME/serve.log" 2>&1 &
SERVER_PID=$!                            # stop this process, and only this one
.venv/bin/python main.py invite mint --name "<neutral display name>"
KEY='nw_…'                               # paste the key the mint just printed
sleep 3
kill -0 "$SERVER_PID" && echo "server running"
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8080/worlds
curl -s -o /dev/null -w '%{http_code}\n' -H "X-Beta-Key: $KEY" http://localhost:8080/worlds
```

Open the share URL only when all three checks pass: `server running` is
printed, the keyless request returns `403`, and the keyed request returns
`200`. Together they show that the server on port 8080 is the process just
launched against this scratch world: only this world holds the new key, and
minting it closed this world's invite gate (`server/guard.py:290-303`). A
`000` means the server is still starting; wait and repeat the checks. If port
8080 is taken, `main.py serve` exits with an `Address already in use` error in
`$HOME/serve.log` (`[Errno 98]` on Linux), but `invite mint` still succeeds
against the scratch database, and the share URL would reach whichever server
owns the port. Do not open it: stop the other server, or start this one with
`--port <free port>` (`main.py:533`) and use that port wherever this kit says
8080. Executed on 2026-11-02 in scratch `HOME`s: with the port held, `serve`
exited with status 1 and the mint succeeded; with another Enfolded server
holding its own key on the port, both requests returned 403; with the
intended server, 403 then 200, and `kill "$SERVER_PID"` stopped it.

Write the share URL with `<BASE>` replaced by `http://localhost:8080`. Record
the scratch path, the display name and the P-code in the restricted record,
not in the repository.

## Facilitator script (protocol 2, steps 1 to 3)

Open with protocol 2's explanation
(`docs/evaluation/2026-09-12-pilot-protocol.md:35-37`), then say:

- "This world is temporary. This world, and everything the research team keeps
  from this session, will be deleted on <date>." Protocol 2 requires this
  (`docs/evaluation/2026-09-12-pilot-protocol.md:10-11`).
  If the participant opens the guide, its permanence lines (the opening,
  `static/guide.html:37-40`, and the "Nothing is lost" section,
  `static/guide.html:159-167`) do not apply to this session.
- "The named inhabitants you may meet are AI characters, not other people."
- Live voice only: "Places and inhabitants answer through an AI model. What you
  type to them and an intention you describe in Act are sent to that model's
  provider. Chat lines can be sent to it too, because a place quotes chat said
  there when someone speaks to it. Chat lines, wrong puzzle guesses, Ideas you
  submit and a profile you publish may also be sent to the same provider for
  a safety check. The provider keeps its own copies under its own terms,
  which are <the terms recorded in the research basics>; deleting this world
  does not delete them."
- "Participation and observation are voluntary."

Then follow script steps 1 to 3
(`docs/evaluation/2026-09-12-pilot-protocol.md:39-48`):

1. Observe the first two minutes without supplying an objective. If help is
   needed afterwards, use the protocol's prompt and record that you used it.
2. After the participant chooses to act, ask what they tried to do. Once an
   outcome is visible, ask what happened and where they found the evidence. A
   pending consequence is unknown, not a failure.
3. Observe optional journal and Ideas use. Do not ask to see private notes. Ask
   what, if anything, they would want to revisit.

Stop there. Steps 4 and 5 belong to the seven-day cohort.

## What to capture, and where

Everything below goes in the restricted research record, outside the
repository and outside the world database. Nothing goes in `docs/` or in any
commit.

- The display-name to P-code map; the consent record; machine, browser and
  client; prior familiarity.
- Step 1: whether an unprompted question appeared in the first two minutes,
  and whether and when the prompt was used. Protocol 2's window is two
  minutes; checklist O1 says five, so record the time either way.
- Time from opening the link to the first place (checklist O3), by the
  facilitator's timer.
- Step 2: the participant's account of the attempt, of the outcome, and of
  where they found the evidence.
- Context the report schema does not take: a spoken 1-to-5 answer to "was it
  interesting?" after each solve, with the puzzle's kind (checklist C2c);
  observed hint use, meaning whether the participant read a hint the puzzle
  showed them (`Hint: …` under the puzzle after a wrong attempt,
  `static/explorer.js:949`) and whether their next guess used it. The
  chronicle shows only which hints were offered, never whether one was used
  (checklist C2c). The
  end-of-session answer to "where are you, and how would you go back?"
  (checklist O4); any failed puzzle or sealed room, noted as a confusion.
- A confusion list in the four buckets Q4 step P7 allows: entry, navigation,
  acceptance, and consequence recognition.

The observation file for `scripts/pilot_report.py` holds protocol 2 fields
only, one row per participant: `curiosity`, `acted`, `understood_action` and
`understood_consequence`, with `return_window_complete` false and the return
fields null
(`docs/evaluation/2026-09-12-pilot-protocol.md:70-75`). Keep it outside the
repository and run
`python scripts/pilot_report.py /absolute/path/to/observations.json`
(`docs/evaluation/2026-09-12-pilot-protocol.md:97-103`). Never put invite keys,
private journal text or identifying details in it.

## After each session

1. While the server is still running, in the same terminal, snapshot the
   session database inside the scratch `HOME`, not yet in the restricted
   store: `.venv/bin/python main.py backup --to "$HOME/session-raw.db"`
   (`main.py:551-555`). The snapshot is a self-contained copy of the whole
   database (`persistence/__init__.py:2728-2749`), so it includes every
   journal note in plain text (`persistence/migrations/0021_participants.sql:26-34`).
2. Remove private text from that copy before it leaves the scratch `HOME`.
   Protocol 2 keeps private journal text out of the report input and says
   journal access is not research consent
   (`docs/evaluation/2026-09-12-pilot-protocol.md:57-59`). The step deletes
   every journal note and blanks profile text that was never published
   (`persistence/migrations/0021_participants.sql:16-25`), then rewrites the
   file with `VACUUM`, because an SQLite build without secure delete leaves
   deleted text in free pages:

   ```bash
   .venv/bin/python - "$HOME/session-raw.db" <<'EOF'
   import sqlite3, sys
   c = sqlite3.connect(sys.argv[1])
   c.execute("DELETE FROM journal_notes")
   c.execute("UPDATE participant_profiles SET bio='', goals='' WHERE published=0")
   c.commit()
   c.execute("VACUUM")
   print(c.execute("SELECT (SELECT COUNT(*) FROM journal_notes), (SELECT COUNT(*)"
                   " FROM participant_profiles WHERE published=0 AND bio||goals<>'')").fetchone())
   c.close()
   EOF
   ```

   It must print `(0, 0)`. The pre-session check's marker test shows, on the
   facilitator's own machine, that the text is gone from the file itself.
   Then move the copy to the restricted store:
   `mv "$HOME/session-raw.db" /restricted/store/<session>.db`. This only
   edits the archived copy, never a running world. Executed on 2026-11-02
   against a scratch database: the raw snapshot held a journal marker and an
   unpublished-profile marker; after this step `grep -c` found neither, a
   published profile's text remained, and `PRAGMA integrity_check` returned
   `ok`. With secure delete off, a deleted row's text stayed in the file
   until `VACUUM` removed it.
3. Stop the server you launched: `kill "$SERVER_PID"`, then confirm that
   `kill -0 "$SERVER_PID"` now fails. Do not revoke the key first.
4. Delete the scratch `HOME` once the archive is confirmed, and close the
   private window or discard the browser profile.
5. Keep the archive only until the deletion date in the research record, then
   delete it with the rest of the raw notes. This deletes the research team's
   copies only. In live-voice mode, the provider's copies follow the terms
   disclosed in consent.
6. Never restore an archived session into a running world to repair it. Restore
   is the disaster path, not an edit path. If a puzzle fails and seals a room
   (packet decision 3), note it as a confusion and let the participant go
   elsewhere.
7. Never tell a participant their history will persist. The archive exists for
   the research record only.
