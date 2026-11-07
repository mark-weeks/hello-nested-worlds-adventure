# Incident response

One page for the pilot. Mark Weeks is the sole maintainer and the sole
operator. He decides kill switches, throttling, revocation, suspension,
bans, redaction, and whether an incident is a release rollback or a
restore. This page records no policy. Minimum age, chat permanence,
external destinations, world status, and backup retention stay open
owner decisions (checklist S4, S5, S2/L4, world status, and Q4 decision I).

Community juries are not active. Corroboration (G3), the consequence
ladder (G4), rotating juries (G6), trust standing (G7), and notice and
appeal (G8) remain open owner decisions. The working tools are the owner
commands below (G5). Telling a player what was decided is G8, not this page.

`fly secrets set` and `fly secrets unset` restart the one machine. Expect
about 10–30 seconds of downtime. Live WebSockets drop; browsers reconnect.
In-flight cascades sit in `causal_queue` and resume. See
[fly-deployment.md §9](fly-deployment.md#9-day-2-operations).

## Stop the bleeding

Set these on the app (`-a enfolded-beta`, or `-a "$FLY_APP"`). Clear a
switch with `fly secrets unset` of that name. That restarts again.

| Switch | Effect |
|---|---|
| `NESTED_WORLDS_DISABLE_AI=1` | `/speak` and `/agent/voice` return HTTP 200 `{"response":"The worlds are quiet today. Try again tomorrow.","ai":false}` before the screen, so that line is not classified. An Act intention the local parser can read still commits. One it cannot read is not sent; the player hears "That intention needs a clearer shape. Choose actions below, or name them in order, separated by commas." Chat, ideas, profiles, and puzzle guesses still go through moderation. |
| `NESTED_WORLDS_DISABLE_IMAGES=1` | `/image` returns `{"url":null,"error":"image generation disabled"}`. |
| `NESTED_WORLDS_DISABLE_MODERATION=1` | Shared text is held before any classifier call. Nothing is published. |

A hold is HTTP 200 with `"held":true` and "The worlds hold those words for now. They are not shared. Say it another way, or try again later." A block is `"declined":true` and "The worlds decline to carry those words. Say it another way." Chat sends that line only to the speaker (`chat_declined`); the client puts the line back in the empty input. No chronicle row and no broadcast. The same hold covers a moderation budget, a per-user cap, a timeout, a provider error, no free slot, the moderation kill switch, or an undecided verdict (`server/moderation.py`).

Defaults, if you need to tighten spend or pace for the rest of the UTC day (`server/guard.py`): text calls `NESTED_WORLDS_ANTHROPIC_DAILY_CALLS` 500 and `NESTED_WORLDS_ANTHROPIC_DAILY_CALLS_PER_USER` 150; images `NESTED_WORLDS_FAL_DAILY_CALLS` 200 and `NESTED_WORLDS_FAL_DAILY_CALLS_PER_USER` 60; moderation classifies `NESTED_WORLDS_MODERATION_DAILY_CALLS` 2,000 and `NESTED_WORLDS_MODERATION_DAILY_CALLS_PER_USER` 60; moderation actions `NESTED_WORLDS_MODERATION_ACTIONS_PER_USER` 600; model actions `NESTED_WORLDS_MODEL_ACTIONS_PER_USER` 200; writes `NESTED_WORLDS_RATE_LIMIT_PER_MIN` 20; reads `NESTED_WORLDS_RATE_LIMIT_GET_PER_MIN` 120. This binary also reads `NESTED_WORLDS_VOICE_*` and `NESTED_WORLDS_IMAGE_*` and enforces the lower integer when both names are set. An older binary reads only the legacy names. Setting those four legacy variables tightens both. A write over the limit is HTTP 429 with "the world asks for a quieter pace — a breath, then try again". Per-user moderation `0` refuses credentialed classify calls. These caps are not a dollar ceiling. No dollar amount is decided here.

```bash
fly secrets set -a enfolded-beta NESTED_WORLDS_DISABLE_AI=1
fly secrets set -a enfolded-beta \
  NESTED_WORLDS_ANTHROPIC_DAILY_CALLS=50 \
  NESTED_WORLDS_RATE_LIMIT_PER_MIN=5
```

Use numbers you mean for this incident. The examples are not a new policy.

## A person

| Need | Command | Comes back? |
|---|---|---|
| End access for good | `fly ssh console -a enfolded-beta -C "python main.py invite revoke nw_<key>"` | No. The name cannot be minted again. |
| Time out | `python main.py sanction suspend <name> --hours N --reason '…'` | At expiry, or `sanction lift <id> --reason '…'` |
| Until lifted | `python main.py sanction ban <name> --reason '…'` | Only `sanction lift` |

Run them on the machine (`fly ssh console`, then `cd /app`). Prefer `--reason -` from that shell so the reason is not in your local history. Full steps, including what a player sees: [fly-deployment.md §6](fly-deployment.md#suspending-or-banning-a-player).

HTTP is refused at once (`403 {"error":"forbidden"}`, no reason shown). An open socket closes at once on a move or chat its rate limit admits. Any other open socket, including one that only listens, stops receiving within about 5 seconds and is closed and leaves within about 1 second more. A chat already being screened is not delivered; its close waits for that screen (one classify attempt under a 3 second timeout; a reply trickled in pieces can take longer). No restart.

Sanction rows are not chronicle rows. `redact` does not reach them, and every backup keeps the reason. How long those backups are kept is decision I, not decided. Erasing a reason is the break-glass procedure in §6, not a delete of the row.

## Words already shared

```bash
fly ssh console -a enfolded-beta -C "python main.py redact --find 'the text'"
fly ssh console -a enfolded-beta -C "python main.py redact --id 12345 --scrub-name --reason 'ToS' --yes"
```

Redaction tombstones the words. The row, its type, and its actor stay. Puzzle names and correctness flags stay. Older machine-local backups, off-host objects, and Fly's 5-day volume snapshots still hold the original until you follow [backup-bucket.md](backup-bucket.md#retention-and-deletion). Do that only after a new validated snapshot exists.

## Release incident or data incident

**Same schema, bad release.** The process boots, `/health` is wrong, or the new code misbehaves, and the script's schema check passes.

```bash
fly releases -a enfolded-beta --image
scripts/deploy.sh --rollback 'registry.fly.io/enfolded-beta:deployment-…'
curl https://enfolded-beta.fly.dev/health
fly logs -a enfolded-beta
```

The script backs up first and refuses if that backup fails. It redeploys only when the image ships the live `schema_version`. Steps and the crash-loop case: [fly-deployment.md](fly-deployment.md#same-schema-release-rollback).

**Stop and restore** when the script says the image is older than the chronicle, when you must discard history, or when the data itself is wrong. Restoring abandons everything after that backup. Keep a binary that can open the current file, restore with it, then deploy the image that matches the restored schema. Deploying the older image first exits before listen (`chronicle schema_version N is newer`) and can leave you without a shell. There is no in-place downgrade. Procedure: [fly-deployment.md §7](fly-deployment.md#restoring-from-a-backup) and [delivery-recovery.md](delivery-recovery.md#upgrade-and-rollback).

## After

`/health` returns `{"status":"ok"}`. `fly logs` shows the process staying up, with no schema refusal. `fly ssh console -C "python main.py voice-health"` if voices or shared text were involved. Write down the image ref, the backup path, and what you changed. Do not mark the staging rollback drill done from this page; that live run is still checklist F4, and it waits on a Fly app.
