# Discovery/return interfaces

These routes use the existing canonical-seed guard and `X-Beta-Key` invite
credential. A private-data or situation-write route always requires a current
personal invite, even in local mode with the general game gate open. The server
owns participant identity; callers never choose it through a request body.
Private responses carry `Cache-Control: no-store`.

| Request | Contract |
|---|---|
| `GET /me` | Participant `{id,name}` and the caller's full profile. |
| `GET /profile?participant=<id>` | Published profile fields for another participant; owner sees their own draft and home. No journal content. |
| `POST /profile/save` | `{bio,goals,avatar,published}`; bio/goals up to 500 characters each; avatar `lantern`, `leaf`, `star` or `river`; published boolean. Published text passes existing moderation. |
| `POST /profile/home` | `{node}`; choose a previously visited canonical node, or empty string to clear. Private bookmark only. |
| `GET /journal/data` | Owner, profile, at most 100 notes and at most eight relevant recorded material changes. Recency is not falsely labeled “since you left.” |
| `POST /journal/note` | `{id,node,text}`; stable note ID of 8–80 characters, text up to 2,000 characters; empty text deletes that owner's note. A different owner cannot replace/delete it. |
| `GET /situation` | Public definition/state plus this participant's choices/discoveries. Null if no situation was installed. |
| `POST /situation/discover` | `{node}`; requires the caller's saved position there. Returns the authored clue and records operational discovery, not a chronicle visit. |
| `POST /situation/choose` | `{branch,request_id}`; preserve/release, after both required clues. One changeable preference per participant. |
| `POST /situation/follow-up` | `{request_id}`; after the outcome and Fold/chain discoveries. One reference-marker event per participant. |
| `GET /puzzle/evidence?node_name=<name>&epoch=<epoch>` | Escaped HTML showing public conditions pinned with that question. An unopened past epoch is unavailable; future epochs cannot be created through this parameter. |

Normal `/puzzle` responses now include `epoch`. `/puzzle/attempt` accepts
`puzzle_name`; a mismatch or a renewal racing acceptance returns 409 without
consuming an attempt. Old clients omitting the name still answer the current
question. Answer definitions stay server-side; public evidence is limited to
node/ancestor properties that players can otherwise examine.

`POST /act` accepts an optional `request_id` for authenticated callers. IDs have
8–80 characters from `[A-Za-z0-9_-]`, scoped to participant, world and operation.
The normalized material intent is fingerprinted. Same ID/same intent returns
the committed response; same ID/different intent returns 409. Receipt and effect
commit or roll back together. A network timeout is ambiguous: retry the **same**
ID. A deliberate later act needs a new ID. Legacy no-ID requests remain distinct
acts. Both clients persist IDs until an authoritative response, with an in-memory
fallback when browser storage is unavailable; that fallback cannot survive reload.

Situation choices/follow-ups require IDs. Notifications are best effort after
commit; reloading `/situation` and the current node recovers authoritative state.
Neither a missed notification nor rereading a receipt replays effects.

Operator commands:

- `python main.py invite rotate <key-or-unique-digest-prefix>` replaces one live
  credential, emits a new secret once and retains the participant, name, saved
  position, notes and explicit conversation aliases. It does not merge accounts,
  rewrite historical actor hashes or promise account-level budget accounting.
- `python main.py situation --seed 382` installs the authored instance once. This
  appends an opening event. It is intentionally absent from startup and deploy
  automation. Use a disposable DB for development, not the operator's normal DB.

The first-use puzzle store cannot recover definitions from releases predating
its installation. Preserve interpreters for stored versions during upgrades.
ADRs 024/025 and the deployment runbook define the compatibility boundary.
