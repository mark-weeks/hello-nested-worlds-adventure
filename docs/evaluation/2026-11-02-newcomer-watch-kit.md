# Newcomer watch: facilitator kit (draft)

**Date:** 2026-11-02, against `main` at `23b8830`. **Status:** a draft.
**Venue, updated 2026-11-07:** the owner prefers the Fly staging twin
([runbook section 3a](../infrastructure/fly-deployment.md#3a-staging-rehearsal--before-the-permanent-world-begins))
and an expedited test build: "Let's expedite the test build, preferably in a
staging environment rather than local."
([decision packet, decision 2](../roadmap/decision-packet-2026-11.md#2-newcomer-watch-venue)).
This kit therefore runs the watch on the twin first. The local,
declared-disposable world on the facilitator's machine, which the owner
allowed on 2026-11-06 (option a), remains only as a fallback
("Fallback: a local, declared-disposable world" below). The watch still waits
on the twin itself, which needs the held Fly account (checklist F1), and on
the research basics that protocol 2 requires before anyone is approached
(facilitator, observation dates, devices, client, consent wording, and the
retention and deletion date: [protocol 2](2026-09-12-pilot-protocol.md),
"Scope and venue"). The watch runs in per-scale silence, with no provider
key, until the owner signs off the named provider's L4 data use note (voice
mode below). This kit recruits nobody, deploys nothing and promises no
persistence.

**2026-11-10 review update:** An owner-requested review of this kit at
`7eb5bc9` changed it as follows.

- **Voice.** The owner's 2026-11-07 policy may permit live voice
  (*inferred*), but it is a test a provider must pass, not the allowlist
  that checklist S2 asks for (still Partial), and ADR-034 §5 requires a
  scoped decision for each new data destination. So live voice with testers
  now waits for the owner's sign-off on the named provider's L4 data use
  note, which is how the owner makes that decision (proposed in packet
  decision 10, awaiting the owner's acceptance). Until then every session
  runs in per-scale silence. Earlier text below that leaves the voice mode
  to the operator's checks is superseded by this.
- **Twin bring-up.** Runbook section 3a, as it reads on `main`, sets a
  provider key before the first deploy and then probes the live voice, which
  sends Enfolded data before any L4 note exists. "Bringing the twin up for
  this watch" below sets no provider key until the note is written, and the
  operator checks that `FAL_KEY` is absent.
- **Return.** On this build a fresh browser shows the introduction and the
  name prompt before the loading line that never ends; the return step now
  says so and records any name the tester types.
- **Citations.** See the 2026-11-07 "Citations" note below, updated.

**2026-11-07 update:** The owner's two decisions of that day change this kit.

- **Venue.** The twin is the primary venue. Testers play on their own devices
  from invite links minted on the twin. The twin serves HTTPS only
  (`fly.toml:27`), so Act and the journal have the secure context they need
  in any device's browser, and the watch can give the device evidence
  (checklist Y5) that a session on the facilitator's machine cannot.
- **Voice.** The owner's provider policy (packet decision 10, recorded in
  [ADR-004](../decisions/ADR-004-day-one-data-policy.md)'s 2026-11-07
  amendment): "Information can only be shared with model providers to
  facilitate game play. Enfolded data must not be used to train frontier
  models." The policy may permit live voice (*inferred*); live voice with
  testers waits for the owner's sign-off on the provider's L4 note
  (2026-11-10 review update above).
  With no provider configured, places answer in per-scale silence, each
  scale's own authored line. That replaces the earlier pre-written-lines default, because
  `NESTED_WORLDS_DISABLE_AI=1` answers "Try again tomorrow", which tells a
  newcomer to leave ([2026-11-06 evaluation](2026-11-06-next-build.md),
  finding 8).
- **Script.** It gains a sound-on step and a scripted return in a fresh
  browser from a bookmark: the two additions the 2026-11-06 completeness
  critic named. The keyless-return change (branch
  `claude/keyless-return-line`; its PR number was not confirmed from this
  session, and it is not on this branch) changes what that return shows, so
  record the build the twin runs. The other two confounds the 2026-11-06
  evaluation found are now facilitator notes in the script.
- **Fallback.** The local setup is kept as the fallback, with per-scale
  silence as its no-provider mode. Executed on 2026-11-07 at `5d4b78c` on
  scratch worlds (pre-session check, step 3).
- **Citations.** On 2026-11-10 every `file:line` in this kit was printed
  and read at the branch head, whose code is `main` at `3200eed` (#153);
  the branch's own commits change only `docs/`. Three cited ranges (six
  occurrences) had not followed #153 and were corrected: two in
  `consciousness/__init__.py`, which moved two lines down (the node history
  that a voice prompt quotes, now `:870-875`, and the per-scale lines and
  `fallback_voice`, now `:742-797`), and `main.py`'s `provider not
  configured` report (now `:428-436`). The 2026-11-07 re-pointing after #153 had covered only
  `consciousness/runtime.py`, `server/guard.py` and `main.py`, and missed
  those. Runbook citations now name a section, not lines, because open PR
  #157 rewrites section 3a; each named section exists on `main` and on
  #157's branch (`claude/staging-deploy-workflow`). Earlier passes: at
  `5d4b78c`, the branch's merge of #152, six citations that #152 had moved
  in `main.py` and `persistence/__init__.py` were corrected. Protocol 2
  citations follow its text with the 2026-11-07 venue line. Fly commands
  below follow the runbook's and the repository's own usage; none was run
  from this session, and Fly's behaviour is unverified here.
- **#153.** `origin/main` at `3200eed` (#153, now merged into this branch)
  adds four per-task provider variables, `NESTED_WORLDS_NODE_PROVIDER`,
  `NESTED_WORLDS_INHABITANT_PROVIDER`, `NESTED_WORLDS_INTENT_PROVIDER` and
  `NESTED_WORLDS_MODERATION_PROVIDER`, and a set task variable wins over
  `NESTED_WORLDS_PROVIDER` for its task (`consciousness/runtime.py:550-575`
  at `3200eed`). A twin built from current `main` runs it. Both venues
  therefore unset all four, and `main.py models` must show
  `provider=anthropic provider_source=default` on every task row (voice mode
  below). This kit's provider and cap citations were re-read after that
  merge.

**2026-11-06 update:** The venue ruling above is recorded here and in protocol
2. The voice mode was **not** decided: both modes below stay, and the
AI-disabled mode (pre-written lines) stays the default because it needs no
further ruling. The owner also decided on 2026-11-06 that agents will not be
labeled and will answer truthfully when sincerely asked whether they are AI;
that work is not built yet, so the consent wording in the facilitator script
below describes today's build. File and line citations were refreshed to
`main` at `18e5bbd` by matching the cited text, except that citations of
protocol 2 follow its text with the 2026-11-06 venue line, so those after
that line sit 2 lines lower than at `18e5bbd`; the dated executions below
are unchanged evidence. Confounds the
[2026-11-06 evaluation](2026-11-06-next-build.md) found (the "Try again
tomorrow" Speak line with AI disabled, a reopened failed puzzle that releases
its answer, and a returning tester whose stored key is gone) are not yet
written up as facilitator notes in this kit. *(Superseded on 2026-11-07 in
part: the twin is now the primary venue, per-scale silence replaces the
AI-disabled default, and the confounds are now notes.)*

**2026-11-04 client update:** The owner selected `/app` for the pilot's first
visit and return ([ADR-005](../decisions/ADR-005-launch-operations.md)). The
operative invite and facilitator instructions below follow that default;
the 2026-11-02/03 executions remain dated evidence, not a rehearsal of this
updated client journey. The world map remains available at `/`. The venue,
device, consent and live-provider prerequisites above are unchanged.

## What this watch is

The first 2 to 3 newcomer sessions of [protocol 2](2026-09-12-pilot-protocol.md),
script steps 1 to 3 only: entry, navigation, acceptance and
consequence recognition, observed with a facilitator present, in person or
by screen share (the runbook allows screen share: section 8, "Launch
window", T-1 week). It is not the seven-day
return cohort, so the return fields in the observation record stay unknown;
the scripted return at the end of a session tests the way back, not voluntary
return. On the twin, each tester plays on their own device in one disposable
world that every watch session shares, and the twin is destroyed by the
stated deletion date. On the local fallback, each participant plays on the
facilitator's machine, in a world that exists for that session only and is
deleted on the stated date.

## Decide before session one

1. **Venue.** The Fly staging twin is preferred (2026-11-07). Falling back
   to the local world is a judgement the facilitator records, best confirmed
   with the owner first: for example, when the twin cannot be up in time for
   an expedited watch because the Fly account (F1) is still held. Record the
   venue and the reason in the research basics.
2. **Research basics.** Recorded in the restricted research record
   (`docs/evaluation/2026-09-12-pilot-protocol.md:41-45`): facilitator,
   dates, each tester's device and browser (on the twin) or the machine and
   browser used (local), client (`/app` is the pilot invite default; record
   any explicit use of the map alternate), voice mode, consent wording, and
   the deletion date. On the twin, also record the commit it runs and what
   else ran on it before the watch (check names, any soak or probe), because
   their traces stay in the shared world.
3. **Voice mode.** Per-scale silence unless the owner has signed off live
   voice. Record the mode in the research basics.
   - *Live voice*, which the owner's 2026-11-07 policy may permit
     (*inferred*). The policy is a test a provider must pass, not an
     allowlist (checklist S2 is still Partial), and ADR-034 §5 requires a
     scoped decision for each new data destination. So no tester's text goes
     to a provider until the owner has signed off that named provider's L4
     data use note: the sign-off is the owner's scoped decision (proposed in
     packet decision 10, awaiting the owner's acceptance). The operator
     prepares the note: (a) reads the configured provider's current terms
     for API inputs, checks them against both sentences of the policy,
     records them, with what they say about training and the provider's
     retention and deletion terms, in the research basics, and writes the
     provider's L4 data use note from them (the session that wrote this kit
     could not open them); if the terms let Enfolded data train a model that
     is not plainly a frontier model, the note says so for the owner (packet
     decision 10, still open); (b) confirms that the Enfolded provider
     account is in no training or data-sharing programme; (c) submits no
     feedback that contains Enfolded data; and (d) checks the consent line's
     training clause (facilitator script) against the recorded terms. Items
     (b) and (c) follow operating rules proposed in packet decision 10,
     which await the owner's acceptance. Then the owner signs the note off,
     or does not. With the sign-off recorded, use the default adapter:
     leave `NESTED_WORLDS_PROVIDER` unset
     (`consciousness/runtime.py:48-49`, `consciousness/runtime.py:595-596`),
     and on a build with #153 the four per-task provider variables too, so no
     `openai_compatible` base URL, which has not been checked against the
     policy, receives player text. On such a build `main.py models` must show
     `provider=anthropic provider_source=default` on every task row; a set
     task variable shows `provider_source=task env` (executed at `3200eed` on
     a scratch `HOME`, 2026-11-07).
     Those rows name the adapter, not the address it sends to. The default
     adapter builds the SDK client with no arguments
     (`consciousness/anthropic_provider.py:188-193`), so the pinned SDK
     (anthropic 0.120.2, `requirements.lock:7`) sends every call to
     `ANTHROPIC_BASE_URL` when it is set, and otherwise, when no API key or
     bearer token is set, to any `base_url` in the profile config that
     `ANTHROPIC_PROFILE` or `ANTHROPIC_CONFIG_DIR` selects
     (`anthropic/_client.py:224-232`, `anthropic/_client.py:261-267`). The
     operator's checks above test the default provider's terms against the
     owner's 2026-11-07 policy; a gateway at another address receives the
     same player text under terms nobody has checked. So, before the live
     credential is set, unset `ANTHROPIC_BASE_URL`, and with it
     `NESTED_WORLDS_OPENAI_COMPATIBLE_BASE_URL`
     (`consciousness/openai_compat_provider.py:55`), which only a task routed
     to `openai_compatible` uses, a routing the rows above rule out. Then
     confirm the destination where the server runs:
     `.venv/bin/python -c 'import anthropic; print(anthropic.Anthropic().base_url)'`
     must print `https://api.anthropic.com`. Executed at `7762bb4` on a
     scratch `HOME`, 2026-11-07, with a placeholder key and no request sent:
     with `ANTHROPIC_BASE_URL` set to a test address, `main.py models`
     printed the same four `provider=anthropic provider_source=default` rows
     as without it, and the probe printed the test address; with a scratch
     profile whose config named a `base_url` and no key, the probe printed
     that address; with `ANTHROPIC_API_KEY` also set, it printed
     `https://api.anthropic.com`.
     A participant's words to places and inhabitants, and chat lines at a
     node, are quoted into later prompts to the provider
     (`consciousness/__init__.py:870-875`). An intention they describe in Act
     is sent to the provider to be read
     (`consciousness/interventions.py:57-81`). Any shared text the local
     screen cannot clear goes to the provider's classifier
     (`server/moderation.py:190-236`), from every screened surface: chat
     lines (`server/websocket.py:621-622`), words to places and inhabitants
     (`server/handlers.py:1238-1239`, `server/handlers.py:1515-1516`), an
     incorrect puzzle guess the attempt will store
     (`server/handlers.py:2063-2066`), Ideas submissions
     (`server/ideas_api.py:80`), and profile text saved as published
     (`server/participant_api.py:33-37`). Disclose all of these in consent.
     The provider keeps its own copies under its own terms, which deleting
     the world and the research archive does not reach. Set low caps on
     every text-model budget the session can spend: voice and intention with
     `NESTED_WORLDS_VOICE_DAILY_CALLS` and
     `NESTED_WORLDS_VOICE_DAILY_CALLS_PER_USER` (`server/guard.py:55`,
     `server/guard.py:64`; the legacy names
     `NESTED_WORLDS_ANTHROPIC_DAILY_CALLS` and
     `NESTED_WORLDS_ANTHROPIC_DAILY_CALLS_PER_USER`, `server/guard.py:57`
     and `server/guard.py:66`, are still read, and when a neutral and a
     legacy value disagree the lower holds, `server/guard.py:909-920`), and
     classifier calls with
     `NESTED_WORLDS_MODERATION_DAILY_CALLS` and
     `NESTED_WORLDS_MODERATION_DAILY_CALLS_PER_USER`, whose defaults are
     2,000 and 60 a day (`server/guard.py:102-108`). Record the values.
   - *Per-scale silence* (no provider): the default, and the mode for every
     session until the owner has signed off the provider's L4 note. No provider
     credential is in the server's environment, no provider variable is set
     (on a build with #153, none of the four per-task ones either), and
     `NESTED_WORLDS_DISABLE_AI` is unset. A place answers its scale's
     authored line of silence with `"ai": false`
     (`server/handlers.py:1244-1248`, `consciousness/__init__.py:742-797`),
     an addressed agent answers that it does not answer
     (`server/handlers.py:1521-1524`, `server/handlers.py:1451-1462`), and an
     Act intention the local parser cannot read gets the authored "clearer
     shape" line (`server/intervention_api.py:34-37`). Speak can then be
     observed as an action, not as a conversation. The classifier cannot
     run, so a chat line or other shared text that the local screen cannot
     clear is held in fiction (setup facts in the fallback below). Do not use
     `NESTED_WORLDS_DISABLE_AI=1` for the watch: its line, "The worlds are
     quiet today. Try again tomorrow." (`server/handlers.py:1207-1210`,
     `server/guard.py:1193`), tells a newcomer to leave.
4. **Images.** Keep the image key (`FAL_KEY`, `server/handlers.py:1402`) off
   the twin for this watch, as the local setup does: no image provider's L4
   note is written, and none is signed off. On the twin, "Before the first
   session" unsets it if it is set and checks that it is absent.
   Without the key, `/image` answers the authored quiet line with
   `"images": false` (`server/handlers.py:1402-1406`). Image prompts carry
   no player text (`server/imageprompt.py:83-89`,
   `server/imageprompt.py:120-143`), but they carry the world's names and
   properties, which are Enfolded data, so the policy applies to the image
   provider as it does to the text provider (packet decision 10). If its
   terms let prompts train an image model, that is the owner's open question
   in decision 10.
5. **Display names.** The facilitator assigns each participant a neutral world
   name: not their real name, not their P-code, not one of the twelve cast
   names (`consciousness/__init__.py:309-313`), and not Observer or Scout,
   the server-owned agent walkers (`agents/identities.py`), which minting
   refuses since #139 (packet decision 7). The map from display name to
   P-code is kept only in the restricted record, outside the repository and
   outside the world database (`docs/evaluation/2026-09-12-pilot-protocol.md:71-74`).
6. **Consent.** Verbal or written, as the research basics specify, because a
   minted key skips `/register`. A tester on the twin gives it before their
   invite link is sent.

## Primary venue: the Fly staging twin

### Setup facts, twin

Read at `5d4b78c`. None was executed against a Fly app.

| Fact | Evidence | What it means for the watch |
|---|---|---|
| The twin is the production procedure under another app name: its own app and volume, deployed with `FLY_APP=enfolded-staging scripts/deploy.sh --first-deploy`, and destroyed before launch. ADR-005 already names it as the onboarding watch's venue. | Runbook section 3a, "Staging rehearsal — before the permanent world begins"; `docs/decisions/ADR-005-launch-operations.md:96-102` | Bringing the twin up is the operator's step under the runbook, and it waits on the Fly account (checklist F1). Read the warning and "Bringing the twin up for this watch" below the table before running it: for this watch the twin starts with no provider key. This kit deploys nothing. |
| The twin hosts seed 382 as its one canonical world, with `HOME=/data` on its volume. | `fly.toml:19-20` | Leave `NESTED_WORLDS_CANONICAL_SEED` as `fly.toml` sets it. Every watch session on the twin shares this world, and a later tester may meet an earlier tester's traces. |
| The twin serves HTTPS only. | `fly.toml:27` | Testers use their own devices. Act and the journal need a secure context (`static/intents.js:7`, `static/journal.js:6`), which an HTTPS page is. Web-platform behaviour, not executed for this kit. |
| `invite mint` prints the share line `<BASE>/app?key=nw_…&name=X` and shows the key once. | `main.py:529-537`, `main.py:585-587` | Replace `<BASE>` with the twin's origin, `https://<staging app>.fly.dev`, the form the runbook's smoke test uses (section 4, "Smoke test"). |
| Minting the first key closes the twin's invite gate for good. | `server/guard.py:312-333` | Mint the check key before the twin's address is shared anywhere (runbook section 6). |
| Invited players read each other's words: `/history` and `/chronicle` serve the world's rows, chat text included, to any invited player. | `server/handlers.py:961-975`, `server/handlers.py:977-993` | Consent says that other testers in this temporary world can read what a tester says. |
| `/app` removes `key=` and `name=` from the address after the first load, and afterwards reads the key from this browser's local storage only. | `frontend/src/auth.js:21-28`, `frontend/src/auth.js:31-37` | A bookmark holds neither the key nor the name. On this build a fresh browser (a private window or another browser, with no stored key, name or `nw_seen_intro`) that opens it first shows the introduction and then the name prompt (`frontend/src/App.jsx:576-590`), and then "Opening the shared world…", which never ends (`frontend/src/App.jsx:146-148`, `frontend/src/App.jsx:182-185`, `frontend/src/App.jsx:592-593`; [2026-11-06 evaluation](2026-11-06-next-build.md), finding 7, read, not run in a browser). A name typed there stays in that browser and registers nothing; opening the invite link there replaces it with the invite's name (`static/clientlogic.js:10-27`). Open PR #154 (branch `claude/keyless-return-line`, head `d55800b`, not on this branch) changes this for a keyless browser: it holds the loading line until the gate answers, then shows the invite line, "The world opens only to an invitation, and this browser holds none. To return, open the invite link you were sent, here on this device.", with no introduction or name prompt first. Record which build the twin runs; the scripted return records what the tester sees. |
| A keyed return resumes the saved place, on any device. | `persistence/__init__.py:2942-2944` (`save_player_position`) | Opening the invite link again in the fresh browser is the designed way back. |
| Sound starts by default on the first click or key press unless this browser has paused it; the "Sound & help" section's button reads "Listen to this world" while the score is paused and "Pause score" while it plays. | `frontend/src/App.jsx:97-102`, `frontend/src/App.jsx:513-524`, `frontend/src/components/TextPanel.jsx:56-58` | The sound-on step needs only the device's sound on. Whether a phone's silent switch mutes the score was not checked. |
| `fly secrets set` and `fly secrets unset` restart the one machine, and live WebSockets drop. | `docs/infrastructure/incident-response.md:15-16` | Change the voice mode or a cap only between sessions. |

**Warning: `scripts/deploy.sh` deploys to production unless told otherwise.**
With `FLY_APP` unset it targets `enfolded-beta`, the production app
(`scripts/deploy.sh:33`), and a misspelt name is deployed as written.
`--first-deploy` skips the chronicle backup and the schema check
(`scripts/deploy.sh:326-333`), so a slip there is the first production boot,
the one-way door in the [2026-11-06 evaluation](2026-11-06-next-build.md)
(finding 1). Run from the repository root, as the runbook's deploy commands
are (runbook section 3, "First deploy"):

- Keep `FLY_APP=enfolded-staging` inline on the same command line as
  `scripts/deploy.sh`, never set in an earlier step.
- Before it, run `fly status -a enfolded-staging` and confirm it names the
  twin's app (Fly's output is unverified here).
- Use `--first-deploy` only for the twin's very first deploy. Any later twin
  redeploy, for example to pick up the keyless-return change, is
  `FLY_APP=enfolded-staging scripts/deploy.sh` without the flag, which backs
  the twin's chronicle up first and checks its schema
  (`scripts/deploy.sh:335-372`).

Executed on 2026-11-07 at this branch's head with a stub `fly` in scratch:
with `--first-deploy`, `FLY_APP=enfolded-staging` ran
`fly deploy -a enfolded-staging`, `FLY_APP` unset ran
`fly deploy -a enfolded-beta`, and the misspelt `enfolded-stagng` ran
`fly deploy -a enfolded-stagng`, each with no backup and exit 0; without the
flag, the first call was the backup and the next the schema check, which the
stub failed, so nothing was deployed. A guard in the script itself is outside
this documentation batch.

### Bringing the twin up for this watch

Runbook section 3a, as it reads on `main`, sets `ANTHROPIC_API_KEY` ("+
FAL_KEY / SENTRY_DSN as desired") before the first deploy, and then runs the
section 8 live-voice probe. A live answer is built from the place's world
content, so the probe sends Enfolded data to the provider before any L4 data
use note exists, and none does yet (checklist L4). For this watch:

- Bring the twin up with no provider key: leave out `ANTHROPIC_API_KEY` and
  `FAL_KEY` from section 3a's `fly secrets set`, and skip the live-voice
  probe.
- Set `ANTHROPIC_API_KEY` only after the provider's L4 note is written, and
  for a session with testers only after the owner has signed that note off
  (voice mode, item 3 of "Decide before session one"). Checklist F1's exit
  criterion includes `/speak` answering `"ai": true`, so F1 cannot close
  before the key is set.
- Never set `FAL_KEY` for this watch (item 4); step 5 below checks that it
  is absent.
- Section 3a also offers `SENTRY_DSN`. Whether the twin reports errors to
  Sentry during a watch is an open observability question for the owner:
  the pinned sentry-sdk 2.66.1 (`requirements.lock:19`) defaults
  `include_local_variables` to true and `server/observability.py:58-63`
  does not change it, so the local variables on an unhandled error, which
  can hold a tester's text, would reach Sentry; leave `SENTRY_DSN` unset for
  the watch unless the owner decides otherwise.

Open PR #157 (branch `claude/staging-deploy-workflow`) rewrites section 3a
in the same direction: it moves the provider terms check ahead of the step
that sets the key, probes the live voice with its own one-word check key
(`Stagingcheck`), which it revokes before testers arrive, and adds
`node_name` to the probe's body. This kit does not edit the runbook. Under
either text, the order above holds for this watch.

### Before the first session (operator)

None of these commands needs the checkout: `-a` names the app, as the
playbook and the backup workflow do (`docs/infrastructure/incident-response.md:48`,
`.github/workflows/backup.yml:100`). Run the database download and scrub
("After the watch, twin") outside the checkout, never in it.

1. Confirm the twin answers: `curl -s https://<staging app>.fly.dev/health`
   returns `{"status": "ok"}` (runbook section 4, "Smoke test").
   Record the commit it was deployed from.
2. Set the voice mode. Per-scale silence, the default: no provider secret
   on the app (`fly secrets unset -a enfolded-staging ANTHROPIC_API_KEY` if
   the rehearsal set one under runbook section 3a). Live voice, only after
   the owner has signed off the provider's L4 note (item 3 in "Decide
   before session one"):
   `ANTHROPIC_BASE_URL` and `NESTED_WORLDS_OPENAI_COMPATIBLE_BASE_URL` are
   unset before the key is set (`fly secrets unset -a enfolded-staging
   <name>` for either one a secret sets; the `[env]` block in `fly.toml`
   sets neither, `fly.toml:18-23`); the key is set as `ANTHROPIC_API_KEY`;
   `NESTED_WORLDS_PROVIDER`, `NESTED_WORLDS_DISABLE_AI` and, on a build with
   #153, the four per-task provider variables are unset; and the low caps
   are set with `fly secrets set -a enfolded-staging …`. Either
   way, if `FAL_KEY` is set, run `fly secrets unset -a enfolded-staging
   FAL_KEY` (item 4 there).
3. Mint a check key under a one-word check name:
   `fly ssh console -a enfolded-staging -C "python main.py invite mint --name Watchcheck"`.
   `-C` is split into words and run without a shell (`scripts/deploy.sh:22`),
   so keep the name to one word.
4. Gate: `curl -s -o /dev/null -w '%{http_code}\n' https://<staging app>.fly.dev/worlds`
   returns `403`, and the same request with `-H "X-Beta-Key: $KEY"` returns
   `200`.
5. Voice: `fly ssh console -a enfolded-staging -C "python main.py models"`
   prints `provider not configured` in per-scale silence and does not in
   live voice (`main.py:428-436`). On a build with #153, every task row must
   also show `provider=anthropic provider_source=default`. Those rows read
   the same with a gateway set, so in live voice also run
   `fly ssh console -a enfolded-staging -C "printenv ANTHROPIC_BASE_URL NESTED_WORLDS_OPENAI_COMPATIBLE_BASE_URL"`,
   which must print nothing. With `ANTHROPIC_API_KEY` as the credential the
   SDK reads no profile's `base_url` (`anthropic/_client.py:261`), and
   `ANTHROPIC_BASE_URL` is the only address it reads from the environment
   (`anthropic/_client.py:224-225`), so these two are the address settings
   left to check. Executed locally on 2026-11-07: `printenv` printed nothing
   with both unset and the address with one set. Then send the
   `/speak` request in the pre-session check below to
   `https://<staging app>.fly.dev/speak`: live
   voice must answer `"ai": true`; per-scale silence answers the place's
   scale line with `"ai": false`. In live voice,
   `fly ssh console -a enfolded-staging -C "python main.py voice-health"`
   shows the day's answered lines and budget use (runbook section 8). In
   either mode, `fly secrets list -a enfolded-staging` lists the app's
   secret names, not their values (Fly's output is unverified here): it
   must not list `FAL_KEY`, and in per-scale silence it must not list
   `ANTHROPIC_API_KEY`. Record only the names.

### Pre-session check, twin

On a device of the facilitator's, never a tester's, with the check key:

1. Open the check share URL. `/app` loads, the place panel shows a place,
   and the status line reads "● Connected to the shared world"
   (`frontend/src/components/TextPanel.jsx:63`). With the device's sound on,
   the score starts after the first tap or key press.
2. Commit one Act and see its pending or arrived state.
3. Open the journal and save a note containing a marker word, such as
   `checkmarker`.
4. Send `Hello there` in chat; it appears under the check name. In
   per-scale silence, also send `Check 1234567`: it must be held, as in the
   fallback's step 6.
5. Bookmark the page, open the bookmark in a private window, and record
   what this build shows there. Then open the check share URL in that
   window: it returns to the saved place.
6. Run "After the watch, twin" steps 1 and 2 on this check world (step 1
   moves into its own scratch directory outside the checkout), but do not
   move the copy to the restricted store. `grep -c checkmarker ./watch-raw.db` on the
   scrubbed copy must print `0`; then delete the copy and its directory.
7. Revoke the check key:
   `fly ssh console -a enfolded-staging -C "python main.py invite revoke <key>"`
   (runbook section 6). Its rows stay in the twin's world; record them in
   the research basics.

Tester devices are not pre-checked. Record each tester's device and browser,
and any device failure as device evidence (checklist Y5), not as a
confusion.

### Inviting testers

- Mint one key per tester under their neutral display name, with item 3's
  command. Send each share URL privately to that tester only: it is their
  credential, and it is shown once. A leaked link is revoked with
  `invite revoke` (runbook section 6).
- Send no invite until the operator confirms that the key was minted on the
  twin (`docs/evaluation/2026-09-12-pilot-protocol.md:44-45`).
- Schedule sessions so that two testers are not in the world at once unless
  an encounter is intended, and record any overlap. Run no soak or probe
  during a session.

### After each session, twin

Revoke that tester's key, because their browser keeps it in local storage
(`frontend/src/auth.js:11`, `frontend/src/auth.js:31-37`):
`fly ssh console -a enfolded-staging -C "python main.py invite revoke <key>"`.
Never tell a tester their history will persist.

### After the watch, twin

1. In a new terminal, move into a fresh scratch directory outside the
   checkout, then snapshot the twin's database on the twin, download it
   there, and delete the copy on the machine:

   ```bash
   cd "$(mktemp -d "${TMPDIR:-/tmp}/enfolded-watch-twin.XXXXXX")"  # owner-only, outside the checkout
   fly ssh console -a enfolded-staging -C "python main.py backup --to /data/backups/watch-raw.db"
   fly ssh sftp get /data/backups/watch-raw.db -a enfolded-staging
   fly ssh console -a enfolded-staging -C "rm /data/backups/watch-raw.db"
   ```

   `main.py backup` is `main.py:942-946`; the download follows
   `.github/workflows/backup.yml:107-108`, which leaves the file in the
   current directory under its own name. The raw file holds every tester's
   chat, journal notes and unpublished profile text, and the repository
   does not ignore `watch-raw.db`, so it must never land in the checkout.
   `mktemp -d` creates the directory readable by its owner only.
2. In the same directory, scrub the copy with the script in the fallback's
   "After each session", step 2, run as
   `/path/to/the/checkout/.venv/bin/python - ./watch-raw.db <<'EOF' … EOF`
   in place of `.venv/bin/python - "$HOME/session-raw.db"`, and check that
   it prints `(0, 0)`. Then move it to the restricted store and delete the
   scratch directory.
3. The twin's database holds every tester's words, journal notes included,
   until the twin is destroyed. Destroy it by the deletion date in the
   research record (`fly apps destroy enfolded-staging --yes`,
   runbook section 3a). If P4 still needs a twin
   after that date, stand up a fresh one. Any copy taken from the twin,
   including the `worlds-*.db` copies a deploy writes to its volume
   (`scripts/deploy.sh:253-254`), follows the same date. Fly keeps volume
   snapshots of its own (`docs/decisions/ADR-005-launch-operations.md:74-75`);
   how long they outlive a destroyed app was not checked from this session.
4. In live-voice mode, the provider's copies follow the terms recorded in
   the research basics.

## Facilitator script (protocol 2, steps 1 to 3)

Before the session, ask the participant to turn their device's sound on, or
to wear headphones, at a comfortable level. Do not describe the score.

Open with protocol 2's explanation
(`docs/evaluation/2026-09-12-pilot-protocol.md:49-51`), then say:

- "This world is temporary. This world, and everything the research team keeps
  from this session, will be deleted on <date>." Protocol 2 requires this
  (`docs/evaluation/2026-09-12-pilot-protocol.md:18-19`).
  If the participant opens the guide, its permanence lines (the opening,
  `static/guide.html:39-42`, and the "Nothing is lost" section,
  `static/guide.html:161-169`) do not apply to this session.
- "Some travelers in Enfolded are AI characters, and you won't always be able
  to tell which." Then say what is true for this session. When no other
  tester is in the world: "No other people are in the world right now: every
  other traveler you meet here is an AI character." On the twin, when
  sessions overlap: "Another tester may be here too."

  This follows the world-level notice the owner accepted on 2026-11-06
  (guardrail b in the [2026-11-06 evaluation](2026-11-06-next-build.md)), with
  one part held back. That notice also says an AI traveler will answer
  truthfully if asked. Do not promise that on today's build: the honesty rule
  does not exist yet, the agent prompt still tells agents never to reveal
  that they are an AI (`consciousness/__init__.py:421`), and with no
  provider an addressed agent does not answer
  (`server/handlers.py:1521-1524`). If a participant
  asks whether someone is a person, answer for the session yourself. Today's
  build also still marks the cast in the Travelers panel while their
  conversation reads like human chat (setup facts in the fallback below).
- On the twin: "Other testers in this temporary world can read what you say
  in chat and to places."
- Live voice only: "Places and inhabitants answer through an AI model. What you
  type to them and an intention you describe in Act are sent to that model's
  provider. Chat lines can be sent to it too, because a place quotes chat said
  there when someone speaks to it. Chat lines, wrong puzzle guesses, Ideas you
  submit and a profile you publish may also be sent to the same provider for
  a safety check. It is sent only to run the game. <One sentence stating
  what the provider's terms, as recorded for this watch, say about training
  on what it receives.> The provider keeps its own copies under its own
  terms, which are <the retention terms recorded in the research basics>;
  deleting this world does not delete them." The operator's check (d) in
  "Decide before session one" confirms this wording against the recorded
  terms before the first session.
- "Participation and observation are voluntary."

Then follow script steps 1 to 3
(`docs/evaluation/2026-09-12-pilot-protocol.md:53-62`):

1. Observe the first two minutes without supplying an objective. If help is
   needed afterwards, use the protocol's prompt and record that you used it.
2. After the participant chooses to act, ask what they tried to do. Once an
   outcome is visible, ask what happened and where they found the evidence. A
   pending consequence is unknown, not a failure.
3. Observe optional journal and Ideas use. Do not ask to see private notes. Ask
   what, if anything, they would want to revisit.

Then two scripted steps, both outside protocol 2's measures:

- **Sound step.** Ask one open question: "What, if anything, did you notice about
   the sound?" Record the answer in the participant's words, and whether the
  score played and whether they paused it or changed the volume. Do not
  prompt about scales.
- **Return step.** Ask the participant to bookmark the page they are on,
  close that window, and open the bookmark in a fresh browser: a private
  window, or another browser on the same device. Do not say how to get back.
  Time it, and record what they see and do. On this build the fresh
  browser first shows the introduction and then a name prompt, and then a
  loading line, "Opening the shared world…", that never ends (setup facts,
  twin). A tester who types a fresh name there may think they are
  registering again: do not explain during the step, and record whether
  they typed a name and which. If the twin runs open PR #154's change
  (branch `claude/keyless-return-line`), a keyless browser instead holds
  the loading line until the gate answers and then shows the invite line,
  with no introduction or name prompt; check which build the twin runs
  before the session (research basics). If they cannot get back, tell them
  to open their invite link in that browser, record that you did, and
  record whether it brought them to their saved place.

Stop there. Protocol 2's steps 4 and 5 belong to the seven-day cohort.

Facilitator notes for today's build, from the
[2026-11-06 evaluation](2026-11-06-next-build.md):

- After a shared puzzle's attempts run out, it shows the answer, still
  accepts guesses, and the shown answer then solves it (finding 3:
  `server/handlers.py:2114`, `server/handlers.py:2169`). Record any
  confusion it causes; do not explain it during the session.
- In live voice, a spent cap answers the "Try again tomorrow" line
  (`server/handlers.py:1279-1281`). Record when it happens.

## What to capture, and where

Everything below goes in the restricted research record, outside the
repository and outside the world database. Nothing goes in `docs/` or in any
commit.

- The display-name to P-code map; the consent record; the venue; device,
  browser and client; prior familiarity.
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
  `frontend/src/components/Interact.jsx`) and whether their next guess used it. The
  chronicle shows only which hints were offered, never whether one was used
  (checklist C2c). The
  end-of-session answer to "where are you, and how would you go back?"
  (checklist O4); any failed puzzle or sealed room, noted as a confusion.
- The sound step: the answer, and whether the score played.
- The return step: what the fresh browser showed, any name typed into its
  name prompt, the time taken, whether the participant got back unaided,
  and whether the invite link restored their place.
- A confusion list in the four buckets Q4 step P7 allows: entry, navigation,
  acceptance, and consequence recognition. The return step's confusions are
  entry.

The observation file for `scripts/pilot_report.py` holds protocol 2 fields
only, one row per participant: `curiosity`, `acted`, `understood_action` and
`understood_consequence`, with `return_window_complete` false and the return
fields null
(`docs/evaluation/2026-09-12-pilot-protocol.md:84-89`). The return step is
not a return in that schema. Keep the file outside the
repository and run
`python scripts/pilot_report.py /absolute/path/to/observations.json`
(`docs/evaluation/2026-09-12-pilot-protocol.md:111-117`). Never put invite keys,
private journal text or identifying details in it.

## Fallback: a local, declared-disposable world

The owner prefers the twin (2026-11-07); this setup is the fallback. Each
participant plays on the facilitator's machine. The facilitator script and
the capture list above apply, except the twin-only lines. A session here
gives no device evidence (Y5).

### Setup facts, verified against the code

Each fact was read at `23b8830`. "Executed" means it was also run against a
scratch database outside the repository on 2026-11-02. Updated 2026-11-03:
the invite-gate fact and the display-name rule (step 4 below) changed when
#137 and #139 merged, and they cite the merged code. The invite destination
was updated from source on 2026-11-04 as noted above. On 2026-11-06 every
file and line citation was refreshed to `18e5bbd` (protocol 2's to its text
with the 2026-11-06 venue line); where the cited code had changed, the fact
was re-read there and still holds. On 2026-11-07 they were re-read at
`5d4b78c`, as the 2026-11-07 update says.

| Fact | Evidence | What it means for the session |
|---|---|---|
| `python main.py serve` binds 127.0.0.1, port 8080, by default. | `main.py:906-907` | The participant uses the facilitator's machine at `http://localhost:8080`. Do not pass `--host 0.0.0.0` unless the owner authorizes the network exposure (plain HTTP, the key in the URL, and a model credential if live voice is on). |
| The world database is `$HOME/.nested-worlds/worlds.db`, with no override. | `persistence/__init__.py:30` | A fresh scratch `HOME` per session is **mandatory**. Without one, the session's rows land in the facilitator's own database. The server and every CLI command for that session must use the same `HOME`. |
| With `NESTED_WORLDS_CANONICAL_SEED` unset, the server hosts seed 382. | `server/guard.py:155-157`, `multiverse/generator.py:30`; executed | Leave the variable unset. |
| `invite mint --name X` prints the key once and a share line of the form `<BASE>/app?key=nw_…&name=X`, which lands on the scene client and never visits `/register`. | `main.py::invite_share_url`, `main.py::cmd_invite`; read after the 2026-11-04 client amendment. The 2026-11-02 execution landed on `/`, now superseded. | Replace `<BASE>` with `http://localhost:8080`. The participant never sees `/register`'s consent line (`static/register.html:49-52`), which in any case promises permanence. Consent is verbal or written. |
| Minting the first key closes the invite gate for good. Revoking a key no longer reopens it (#137), and an open socket whose key is revoked is closed. | `server/guard.py:312-333` (`invite_gate_active`, `persistence.credentials_ever_issued`); on `23b8830` revoking the only key reopened the gate (executed 2026-11-02) | End a session by stopping the server. Revoking the key is not needed: the scratch `HOME` is deleted. |
| Act requires a live personal invite, and derives request IDs with `crypto.subtle.digest` and `crypto.randomUUID`. The journal calls `crypto.randomUUID` when it loads. | `persistence/participants.py:39-54`, `static/intents.js:7`, `static/intents.js:32`, `static/interventions.js:86`, `static/journal.js:6` | Use `http://localhost`, which browsers treat as a secure context. A plain-http LAN address is not one, so Act commits and the journal would fail there. This is web-platform behaviour, not executed for this kit; the pre-session check below confirms it on the actual machine. |
| `NESTED_WORLDS_DISABLE_AI=1` quiets three paths: `/speak` and `/agent/voice` answer the authored quiet line with HTTP 200 and `"ai": false` before the screen runs, and an Act intention that the local parser cannot read gets the authored "clearer shape" line instead of going to a model. It does not quiet the moderation classifier, which never reads the flag: a chat line, an incorrect puzzle guess the attempt will store, an Ideas submission or profile text saved as published that the local screen cannot clear still goes to the provider whenever one is configured, and a credential in the environment is enough. It does not stop images either. | `server/handlers.py:1207-1210`, `server/handlers.py:1475-1479`, `server/intervention_api.py:157-160`, `server/intervention_api.py:34-37`, `server/moderation.py:166-241`, `server/websocket.py:621-622`, `server/handlers.py:2063-2066`, `server/ideas_api.py:80`, `server/participant_api.py:33-37`, `server/handlers.py:1371-1372`, `server/handlers.py:1402-1406`; executed for `/speak`, and on 2026-11-03 for a held chat line | Only an environment with no configured provider keeps player text on the machine. Session setup unsets the credentials and the image key, and the pre-session check proves it. Since 2026-11-07 the watch does not set the flag (per-scale silence, "Decide before session one"). |
| With no provider configured and the flag unset, `/speak` answers the place's per-scale line of silence with `"ai": false` after the screen, `/agent/voice` answers that the agent does not answer, and an unreadable Act intention gets the "clearer shape" line. | `server/handlers.py:1244-1248`, `consciousness/__init__.py:742-797`, `server/handlers.py:1521-1524`, `server/intervention_api.py:34-37`; executed on 2026-11-07 for `/speak` and chat (pre-session check) | Per-scale silence keeps player text on the machine and does not tell the participant to come back tomorrow. |
| Chat lines the local screen clears are shared. A line it cannot clear needs the classifier and is held, in fiction, if the classifier cannot run. | `server/moderation.py:183-205`, `server/moderation.py:217-241` | With no working classifier, expect some ordinary chat lines to be held with the authored hold line. Record a held line as an observation, not a fault. |
| The heartbeat cast walks and talks unless `NESTED_WORLDS_HEARTBEAT=0`, and their conversation renders like human chat. The Travelers panel still marks the cast with `✦` and a persona. | `server/heartbeat.py:22`, `server/heartbeat.py:71`; scene `frontend/src/App.jsx:360-366`, `onAgentTalk`, puts named lines into the chat feed just as `onChat` does; `frontend/src/components/TextPanel.jsx:48` | Tell the participant that every other traveler in this session is an AI character (script above). Live labels will not ship: on 2026-11-06 the owner decided agents are not labeled, so the panel marks go when the structural-parity work lands. |
| The browser keeps the key and Act receipts in local storage. | `static/journal.js:4`, `static/intents.js:11-13`, `static/intents.js:29-34` | Use a fresh browser profile or a private window for each participant. |

### Pre-session check

Run it in a throwaway `HOME`, never the participant's, so the participant's
world contains no check traces.

1. In a new terminal, follow "Session setup" below with a throwaway `HOME`, a
   check name, and the voice mode the sessions will use. Its server and key
   checks must pass.
2. Open the share URL in a private window. `/app` loads, the place panel
   shows a place, and the connection is live. Complete this check on the
   actual session device; the client choice does not establish device support.
3. Speak to the place, then confirm the voice mode from the server's answer,
   not from the words: the scene displays the reply without the `ai` flag
   (`frontend/src/components/Interact.jsx`). In the same terminal:

   ```bash
   curl -s -X POST http://localhost:8080/speak -H "X-Beta-Key: $KEY" \
     -H 'Content-Type: application/json' \
     -d '{"node_name": "<the place in the panel>", "message": "Hello?"}'
   ```

   - *Per-scale silence*: `"ai": false` with the place's own scale line,
     such as a Room's "Dust settles where a voice should be. The room
     remembers footsteps, but it will not speak of them now."
     (`server/handlers.py:1244-1248`, `consciousness/__init__.py:742-797`).
     A configured provider that is busy or fails also answers that line
     (`server/handlers.py:1283-1311`), so also run
     `.venv/bin/python main.py models` in the same terminal: it must print
     `provider not configured` (`main.py:428-436`). If it does not, a
     credential is still in the environment and the classifier can still
     receive text: unset it and restart from step 1. Executed on 2026-11-07
     at `5d4b78c` with the setup block below, in scratch `HOME`s: `models`
     printed `provider not configured`, and the Multiverse root, a Galaxy, a
     Room and an Object answered their four different authored lines, each
     with `"ai": false`. Executed again on 2026-11-07 at 04:49Z at the branch
     head, whose code is `5d4b78c`'s, with the block as now written (the four
     per-task provider names added) after planting a fake
     `ANTHROPIC_API_KEY`, `NESTED_WORLDS_PROVIDER=openai_compatible`,
     `NESTED_WORLDS_DISABLE_AI=1`, two per-task provider variables and
     `FAL_KEY` in the terminal: the same results.
   - *Live voice*: `"ai": true` (`server/handlers.py:1316`). Here
     `"ai": false` means `NESTED_WORLDS_DISABLE_AI=1` is still set, the
     provider is not configured or failed, or a cap is spent
     (`server/handlers.py:1244-1248`, `server/handlers.py:1279-1311`). Fix it
     before any session; a live-voice session does not run on the quiet line.
     A gateway also answers `"ai": true`, so `"ai": true` counts only after
     the setup block's destination check printed `https://api.anthropic.com`.
   - Earlier evidence, dated: on 2026-11-02, and again on 2026-11-03 with the
     setup block as it then stood, in AI-disabled mode the answer was the
     quiet line with `"ai": false`; in live-voice mode with an inherited
     `NESTED_WORLDS_DISABLE_AI=1` cleared but no credentials, it was an
     authored line that reads like a reply, also with `"ai": false`.
4. **Commit one Act** and see its pending or arrived state.
5. **Open the journal** (History & journal, then Journal) and save a note
   containing a marker word, such as `checkmarker`. Journal and Ideas links
   navigate in the same tab; use Back to world to return to `/app` with the
   same identity and saved place before continuing these checks.
6. Send one chat line, such as `Hello there`. It appears in the feed under
   the check name.
   - *Per-scale silence*: then send `Check 1234567`. A run of seven or more
     digits, separators ignored, is harmless text that the local screen
     always sends to the classifier and never blocks on its own
     (`content_screen.py:200-203`, `content_screen.py:235-239`), so it
     tests the classifier path without typing anything offensive. With no
     provider configured the classifier cannot run, and the line must be
     held: only the sender sees `✕ The worlds hold those words for now.
     They are not shared. Say it another way, or try again later.`
     (`server/moderation.py:66-69`, `server/websocket.py:621-626`,
     `frontend/src/App.jsx`, `onChatDeclined`). If the line appears as an ordinary
     chat line, or is declined with "The worlds decline to carry those
     words", a classifier answered, so the text reached a provider: stop,
     unset the credential, and restart from step 1. A held line alone does
     not prove that nothing was sent, because a provider that is reached
     but fails also holds the line; the `models` check in step 3 is what
     shows that no provider is configured. Executed on 2026-11-03 in
     scratch `HOME`s, with fake values for `ANTHROPIC_API_KEY`,
     `ANTHROPIC_AUTH_TOKEN`, `NESTED_WORLDS_OPENAI_COMPATIBLE_API_KEY` and
     `FAL_KEY`, `NESTED_WORLDS_PROVIDER=openai_compatible`, and both base
     URLs pointed at a local recorder: the setup block as then written (with
     `NESTED_WORLDS_DISABLE_AI=1`) made
     `models` print `provider not configured`, shared `Hello there`, held
     `Check 1234567` with the hold line, and the recorder received
     nothing. With the AI-disabled `unset` removed and a fake key on the
     default adapter, `models` printed no such line and the digit line
     reached the recorder: held when the recorder answered with an error,
     shared when it answered ALLOW. Executed again on 2026-11-07 at
     `5d4b78c` with the per-scale silence block below, over a WebSocket
     client and without a recorder: `Hello there` was shared and
     `Check 1234567` was held with the hold line; the same at 04:49Z with
     the block as now written and the planted values of step 3.
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

### Session setup

One dedicated terminal per participant. Every command below runs in that
terminal so that it uses the same `HOME`.

```bash
export HOME="$(mktemp -d "${TMPDIR:-/tmp}/enfolded-watch.XXXXXX")"
unset NESTED_WORLDS_CANONICAL_SEED       # the world falls back to seed 382
unset FAL_KEY                            # no image provider, in either mode
export NESTED_WORLDS_DISABLE_IMAGES=1
unset NESTED_WORLDS_DISABLE_AI           # an inherited =1 answers "Try again tomorrow"
# Per-scale silence: no text-provider credential or selection in this terminal
unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN ANTHROPIC_PROFILE \
  ANTHROPIC_CONFIG_DIR ANTHROPIC_IDENTITY_TOKEN ANTHROPIC_IDENTITY_TOKEN_FILE \
  NESTED_WORLDS_PROVIDER NESTED_WORLDS_OPENAI_COMPATIBLE_API_KEY \
  NESTED_WORLDS_NODE_PROVIDER NESTED_WORLDS_INHABITANT_PROVIDER \
  NESTED_WORLDS_INTENT_PROVIDER NESTED_WORLDS_MODERATION_PROVIDER
# Live voice only (packet decision 10: the provider's L4 note written and
# signed off by the owner; see "Decide before session one", item 3): replace
# the unset above with
#   unset ANTHROPIC_BASE_URL NESTED_WORLDS_OPENAI_COMPATIBLE_BASE_URL \
#     NESTED_WORLDS_PROVIDER NESTED_WORLDS_OPENAI_COMPATIBLE_API_KEY \
#     NESTED_WORLDS_NODE_PROVIDER NESTED_WORLDS_INHABITANT_PROVIDER \
#     NESTED_WORLDS_INTENT_PROVIDER NESTED_WORLDS_MODERATION_PROVIDER
# keep the default provider's credential in this terminal, export the low
# caps ("Decide before session one", item 3), and, after the cd below, run
#   .venv/bin/python -c 'import anthropic; print(anthropic.Anthropic().base_url)'
# which must print https://api.anthropic.com before the server starts.
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

The per-scale silence `unset` removes each credential source that the code
and its pinned SDK read. The pinned Anthropic SDK (`requirements.lock:7`)
builds its client from `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, a named
profile or config directory (`ANTHROPIC_PROFILE`, `ANTHROPIC_CONFIG_DIR`) or a
workload-identity token, and the adapter counts each as configured
(`consciousness/anthropic_provider.py:157-165`,
`consciousness/anthropic_provider.py:192-193`). The fresh `HOME` already
hides the SDK's default profile directory, `~/.config/anthropic`. Unsetting
`NESTED_WORLDS_PROVIDER` keeps the default adapter selected
(`consciousness/runtime.py:49`, `consciousness/runtime.py:595-596`), so the
evaluation adapter, which needs no key for a loopback base URL, is not used
(`consciousness/openai_compat_provider.py:294-295`); its key,
`NESTED_WORLDS_OPENAI_COMPATIBLE_API_KEY`, goes too
(`consciousness/openai_compat_provider.py:56`). The four per-task provider
variables are read from #153 on (`consciousness/runtime.py:550-575` at
`3200eed`, now merged here); unsetting them keeps every task on the default
adapter. `FAL_KEY` is the image key
(`server/handlers.py:1402`), and `NESTED_WORLDS_DISABLE_IMAGES=1` makes
`/image` answer before it is read (`server/handlers.py:1371-1372`). Only
`/app` requests images; the explorer does not. A source this list misses
still shows in the pre-session check.

Open the share URL only when all three checks pass: `server running` is
printed, the keyless request returns `403`, and the keyed request returns
`200`. Together they show that the server on port 8080 is the process just
launched against this scratch world: only this world holds the new key, and
minting it closed this world's invite gate (`server/guard.py:312-333`). A
`000` means the server is still starting; wait and repeat the checks. If port
8080 is taken, `main.py serve` exits with an `Address already in use` error in
`$HOME/serve.log` (`[Errno 98]` on Linux), but `invite mint` still succeeds
against the scratch database, and the share URL would reach whichever server
owns the port. Do not open it: stop the other server, or start this one with
`--port <free port>` (`main.py:907`) and use that port wherever this kit says
8080. Executed on 2026-11-02 in scratch `HOME`s: with the port held, `serve`
exited with status 1 and the mint succeeded; with another Enfolded server
holding its own key on the port, both requests returned 403; with the
intended server, 403 then 200, and `kill "$SERVER_PID"` stopped it. On
2026-11-07 the per-scale silence block, with `--port` set to a free port,
printed `server running`, then 403 and 200, and did so again at 04:49Z with
the four per-task provider names added.

Write the share URL as `http://localhost:8080/app?key=nw_…&name=<check name>`
(the printed URL with `<BASE>` replaced by `http://localhost:8080`). Record
the scratch path, the display name and the P-code in the restricted record,
not in the repository.

### After each session

1. While the server is still running, in the same terminal, snapshot the
   session database inside the scratch `HOME`, not yet in the restricted
   store: `.venv/bin/python main.py backup --to "$HOME/session-raw.db"`
   (`main.py:942-946`). The snapshot is a self-contained copy of the whole
   database (`persistence/__init__.py:3001-3022`), so it includes every
   journal note in plain text (`persistence/migrations/0021_participants.sql:26-34`).
2. Remove private text from that copy before it leaves the scratch `HOME`.
   Protocol 2 keeps private journal text out of the report input and says
   journal access is not research consent
   (`docs/evaluation/2026-09-12-pilot-protocol.md:71-73`). The step deletes
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
   `kill -0 "$SERVER_PID"` now fails. Revoking the key is not needed.
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

Steps 6 and 7 apply on the twin too.
