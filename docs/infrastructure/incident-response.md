# Incident response

One page for the pilot. Mark Weeks is the sole maintainer and the sole
operator. He decides kill switches, throttling, revocation, suspension,
bans, redaction, and whether an incident is a release rollback or a
restore. This page records no policy. Minimum age, chat permanence,
external destinations, and world status stay open owner decisions
(checklist S4, S5, S2/L4, and world status). Backup retention is 30 days,
recorded on 2026-11-20 (O7), with a 7-day bucket lock counted from upload
and a 37-day lifecycle backstop.

Community juries are not active. Corroboration (G3), the consequence
ladder (G4), rotating juries (G6), trust standing (G7), and notice and
appeal (G8) remain open owner decisions. The working tools are the owner
commands below (G5). Telling a player what was decided is G8, not this page.

`fly secrets set` and `fly secrets unset` restart the one machine. Expect
about 10–30 seconds of downtime. Live WebSockets drop; browsers reconnect.
In-flight cascades sit in `causal_queue` and resume. See
[fly-deployment.md §9](fly-deployment.md#9-day-2-operations).

## Stop the bleeding

Set these on the app (`-a enfolded-beta`, or `-a "$FLY_APP"`). Every app using
the committed Fly configuration, production included, requires controlled mode
and has `DISABLE_AI=1` and `DISABLE_IMAGES=1`. Unsetting one of those secrets
restores the committed `1`; it does not enable the route. A later explicit
`DISABLE_AI=0` override is allowed only after the
[live gates and value check](fly-deployment.md#approved-live-controlled-text).
Do not remove the policy requirement or change adapter/vendor during an incident.

| Switch | Effect |
|---|---|
| `NESTED_WORLDS_DISABLE_AI=1` | `/speak` and `/agent/voice` return HTTP 200 `{"response":"The worlds are quiet today. Try again tomorrow.","ai":false}` before the screen, so that line is not classified. One exception: a line that is only a sincere question whether the speaker is human ("are you human?", "r u a bot") gets its authored truthful answer with `"ai":false` (`consciousness/honesty.py`) after the local screen, and no chronicle row is written; if the local screen would send that line to the classifier, it gets the quiet line instead. An Act intention the local parser can read still commits. One it cannot read is not sent; the player hears "That intention needs a clearer shape. Choose actions below, or name them in order, separated by commas." Chat, ideas, profiles, and puzzle guesses still go through moderation. |
| `NESTED_WORLDS_DISABLE_IMAGES=1` | In controlled mode, `/image` returns HTTP 200 with the authored quiet line and `"images":false` before cache, quota or provider access. This build supports no controlled image adapter even if the switch is cleared. |
| `NESTED_WORLDS_DISABLE_MODERATION=1` | Shared text is held before any classifier call. Nothing is published. |

A hold is HTTP 200 with `"held":true` and "The worlds hold those words for now. They are not shared. Say it another way, or try again later." A block is `"declined":true` and "The worlds decline to carry those words. Say it another way." Chat sends that line only to the speaker (`chat_declined`); the client puts the line back in the empty input. No chronicle row and no broadcast. The same hold covers a moderation budget, a per-user cap, a timeout, a provider error, no free slot, the moderation kill switch, or an undecided verdict (`server/moderation.py`).

`DISABLE_AI` controls voice and intention only; it does not stop moderation.
Use `DISABLE_MODERATION=1` as well when classifier traffic must stop. Controlled
policy permissions still apply to every route, regardless of available keys.
The first controlled adapter/vendor remains an owner decision: live hosted voice
waits for ADR-035 acceptance or a controlled Anthropic path, plus approved
destinations, prices, amounts and retention. Plain `models` and `voice-health`
show the controlled policy and accounting stop. Their `--probe` is refused in
controlled mode; do not use it to test recovery.

An accounting stop differs from a daily allowance refusal. Keep external routes
off, inspect the status and ERROR/Sentry evidence, and reconcile provider spend
before restarting or restoring. A persistent stop is not cleared by midnight, a
policy change, a restart, or a new app. There is no automatic refund and no
unlatch command. The hand procedure for the disposable watch twin is
[Clearing the stop](#clearing-the-stop). Live ledger
expiry does not erase whole-database backups, whose newest validated copy can
remain indefinitely under the keep-newest exception.

Defaults, if you need to tighten spend or pace for the rest of the UTC day (`server/guard.py`): text calls `NESTED_WORLDS_ANTHROPIC_DAILY_CALLS` 500 and `NESTED_WORLDS_ANTHROPIC_DAILY_CALLS_PER_USER` 150; images `NESTED_WORLDS_FAL_DAILY_CALLS` 200 and `NESTED_WORLDS_FAL_DAILY_CALLS_PER_USER` 60; moderation classifies `NESTED_WORLDS_MODERATION_DAILY_CALLS` 2,000 and `NESTED_WORLDS_MODERATION_DAILY_CALLS_PER_USER` 60; moderation actions `NESTED_WORLDS_MODERATION_ACTIONS_PER_USER` 600; model actions `NESTED_WORLDS_MODEL_ACTIONS_PER_USER` 200; writes `NESTED_WORLDS_RATE_LIMIT_PER_MIN` 20; reads `NESTED_WORLDS_RATE_LIMIT_GET_PER_MIN` 120. This binary also reads `NESTED_WORLDS_VOICE_*` and `NESTED_WORLDS_IMAGE_*` and enforces the lower integer when both names are set. An older binary reads only the legacy names. Setting those four legacy variables tightens both. A write over the limit is HTTP 429 with "the world asks for a quieter pace — a breath, then try again". Per-user moderation `0` refuses credentialed classify calls. These caps are not a dollar ceiling. No dollar amount is decided here.

```bash
fly secrets set -a enfolded-beta NESTED_WORLDS_DISABLE_AI=1
fly secrets set -a enfolded-beta \
  NESTED_WORLDS_ANTHROPIC_DAILY_CALLS=50 \
  NESTED_WORLDS_RATE_LIMIT_PER_MIN=5
```

Use numbers you mean for this incident. The examples are not a new policy.

## Clearing the stop

The accounting contract is
[Clearing the stop](../development/model-policy.md#clearing-the-stop).
This section is the operator procedure.
[Owner decision O9](../roadmap/owner-decisions-2026-11-20.md#o9-clearing-the-latched-spend-stop-items-3-28)
(2026-11-20) adopts it for the disposable watch twin. ADR-039 stays Proposed.
There is still no unlatch command, no audit table, and no migration.

The stop is the single `model_spend_latch` row (`singleton = 1`, reason
`billing_anomaly`, `accounting_fault`, or `unsettled_startup`). Application
code only inserts that row and does nothing when it is already present.
A doc-only clear is hand SQL on the volume database,
`/data/.nested-worlds/worlds.db`. An `unsettled_startup` latch leaves
`status = 'reserved'` rows, and those rows latch again at the next boot
until they leave that status. `_settlement_fault` lives in the server
process and survives a database clear. The startup scan runs once per
process, including a boot with the kill switches on.

Use this procedure in two places only:

- A rehearsal, before the first watch session and by Friday 4 December 2026,
  on a throwaway Fly app that is neither the watch twin nor the kept world.
  The deployment runbook's twin is `enfolded-staging`. The kept world named
  in `fly.toml` is `enfolded-beta`. The throwaway app is a third name.
- A real latch on the disposable watch twin, after that rehearsal is recorded.

A kept world that will serve any live model route needs an audited clear
command first (an ADR-039 revision and a migration). Hand SQL on that volume
is not acceptable. Do not run the statements below against `enfolded-beta`
or any other kept world. The write script checks the machine before it opens
the database: Fly's `FLY_APP_NAME` must equal the app name you pass, that
name must not be `enfolded-beta`, and `NESTED_WORLDS_TEST_WORLD` must be on
(`1`, `true`, `on`, or `yes`). Do not assign `FLY_APP_NAME` yourself. Fly
sets it on the machine.

A clear never refunds the day's spend and never shortens ledger retention.
A restart is not a clear. A new app, a new volume, or a re-created twin is
not a clear: the provider has already billed that UTC day.

### Evidence before the write

Record every item below in a dated private operator entry kept outside the
world database and outside player-visible history. Name the app, the backup
path, and the UTC time. Do not write a chronicle row or a chat line. Items
1 to 4 are O9's evidence. Item 5 is required when the reason is
`billing_anomaly`.

1. The provider console's spend for every UTC day the read-only listing
   prints under `reconcile days`. That set is the UTC day of `latched_at`,
   every day that still has a `reserved` row, and every day that has an
   `anomaly` row. An anomalous settlement after midnight keeps the charge
   on the reservation's original day, so `latched_at` alone can miss it.
   Beside each day, the ledger sum of `accounted_microusd`. One USD is
   1,000,000 microUSD. Record both figures. Do not copy the console total
   into the ledger. If the console total is higher than this installation's
   calls explain, stop here, leave the latch, and keep the routes off.
2. The latch reason and `latched_at`.
3. Every `reserved` row, from the read-only listing below.
4. This entry, including the backup path, finished before the write.
5. When the reason is `billing_anomaly`, each `anomaly` row's
   `resolved_model`, `usage_json`, `reserved_microusd`, and
   `accounted_microusd`, and the cause. `settlement` in
   `consciousness/model_policy.py` flags an anomaly in four cases: the
   provider's resolved model is not in the route's `resolved_models`, the
   provider is not the route's adapter, the billing evidence is
   inconsistent, or a token count exceeds the route's bound. A priceable
   count above that bound can account more than `reserved_microusd`. That
   is the case where the ceiling does not hold. Leave the latch. Do not
   run the write until the owner has corrected the route's resolved-model
   list, token bounds, or prices in the policy on the machine, and that
   correction is in this entry. The checked-in watch example still leaves
   dollar amounts, prices, and call caps as unconfirmed placeholders.
   Editing that example does not change the policy on the machine, and
   this procedure does not fill it.
   [O4](../roadmap/owner-decisions-2026-11-20.md#o4-dollar-amounts-ledger-retention-and-the-reservation-rule)
   and
   [O5](../roadmap/owner-decisions-2026-11-20.md#o5-call-and-cap-integers-item-29)
   are the decision record for those amounts. They are not a checked-in
   setting. With the same deployed policy, the next confirming call
   latches again, or charges above the reservation again.

### 1. Quiesce dispatch

Set the app name in your own shell. For the rehearsal it is the throwaway
app. For a real latch it is the watch twin.

```bash
# Local shell. Not the kept world.
ENFOLDED_CLEAR_APP=throwaway-app-name
curl -fsS "https://${ENFOLDED_CLEAR_APP}.fly.dev/health"
```

`/health` returns `{"status":"ok"}` before you continue. Record the voice
and moderation switches before changing them. `printenv` prints the current
value. A command that prints nothing means that name is unset. Write both
results into the private entry. Step 5 restores these values. It does not
invent `0`.

```bash
fly ssh console -a "$ENFOLDED_CLEAR_APP" -C "printenv NESTED_WORLDS_DISABLE_AI"
fly ssh console -a "$ENFOLDED_CLEAR_APP" -C "printenv NESTED_WORLDS_DISABLE_MODERATION"
```

Then set both switches to `1` in one command. Confirm the image switch is
already `1`. Setting secrets restarts the machine. That restart is not a
clear.

```bash
fly secrets set -a "$ENFOLDED_CLEAR_APP" \
  NESTED_WORLDS_DISABLE_AI=1 \
  NESTED_WORLDS_DISABLE_MODERATION=1
curl -fsS "https://${ENFOLDED_CLEAR_APP}.fly.dev/health"
fly ssh console -a "$ENFOLDED_CLEAR_APP" -C "python main.py models"
```

Every route line reads `disabled (intentional)`. `model controls` may still
say `STOPPED`. Leave these switches on until step 5 has confirmed the
database. A process that is otherwise willing to dispatch will take a new
reservation as soon as the latch row is gone, and the next boot will latch
`unsettled_startup` again.

`fly ssh console -C` does not run a remote shell. Expand any `$(...)` in
your local shell, as the backup command below does.

### 2. Reconcile, then back up

On the machine, list the latch and the reserved rows. This opens the
database read-only.

```bash
fly ssh console -a "$ENFOLDED_CLEAR_APP"
```

At that remote shell, paste:

```bash
cd /app && python - <<'EOF'
import os
import sqlite3
from collections import defaultdict

since = os.environ.get("ENFOLDED_CLEAR_SINCE", "")
if since and (len(since) != 27 or since[10] != "T" or not since.endswith("Z")):
    raise SystemExit("ENFOLDED_CLEAR_SINCE must look like 2026-11-20T23:40:00.000000Z")

db = sqlite3.connect("file:/data/.nested-worlds/worlds.db?mode=ro", uri=True, timeout=5)
db.row_factory = sqlite3.Row
db.execute("BEGIN")
latch = db.execute(
    "SELECT singleton, latched_at, reason FROM model_spend_latch"
).fetchall()
print("latch:")
if not latch:
    print("  (no row)")
for row in latch:
    print(f"  singleton={row['singleton']} latched_at={row['latched_at']} reason={row['reason']}")
rows = db.execute(
    "SELECT day, status, accounted_microusd FROM model_spend_reservations"
).fetchall()
by_status = defaultdict(lambda: [0, 0])
by_day = defaultdict(lambda: [0, 0])
for row in rows:
    by_status[row["status"]][0] += 1
    by_status[row["status"]][1] += row["accounted_microusd"]
    by_day[row["day"]][0] += 1
    by_day[row["day"]][1] += row["accounted_microusd"]
print("by status:")
for status in sorted(by_status):
    count, accounted = by_status[status]
    print(f"  {status} count={count} accounted_microusd={accounted}")
print("by day:")
for day in sorted(by_day):
    count, accounted = by_day[day]
    print(f"  {day} count={count} accounted_microusd={accounted}")
print("reserved:")
reserved = db.execute(
    """SELECT id, day, task, reserved_microusd, accounted_microusd, abandoned_at,
              settled_at, retention_days, retain_until
       FROM model_spend_reservations WHERE status='reserved' ORDER BY created_at, id"""
).fetchall()
if not reserved:
    print("  (none)")
for row in reserved:
    print("  " + " ".join(f"{key}={row[key]}" for key in row.keys()))
print("anomaly:")
anomaly = db.execute(
    """SELECT id, day, task, reserved_microusd, accounted_microusd, settled_at,
              resolved_model, usage_json
       FROM model_spend_reservations WHERE status='anomaly' ORDER BY day, id"""
).fetchall()
if not anomaly:
    print("  (none)")
for row in anomaly:
    print("  " + " ".join(f"{key}={row[key]}" for key in row.keys()))
days = set()
for row in latch:
    stamp = row["latched_at"]
    if len(stamp) < 10 or stamp[4] != "-" or stamp[7] != "-":
        raise SystemExit("refusing: latched_at is not a UTC date")
    days.add(stamp[:10])
for row in list(reserved) + list(anomaly):
    days.add(row["day"])
print("reconcile days:")
if not days:
    print("  (none)")
for day in sorted(days):
    print(f"  {day}")
if since:
    print(f"created after {since}:")
    created = db.execute(
        """SELECT id, day, task, status, reserved_microusd, accounted_microusd, settled_at
           FROM model_spend_reservations WHERE created_at > ? ORDER BY created_at, id""",
        (since,),
    ).fetchall()
    if not created:
        print("  (none)")
    for row in created:
        print("  " + " ".join(f"{key}={row[key]}" for key in row.keys()))
db.execute("ROLLBACK")
db.close()
EOF
```

Copy that listing into the private entry. Then take a fresh backup and copy
it off the machine before any write. The file is the whole database,
including private chat. Keep it outside the checkout, and do not delete the
copy on the machine until the settled call in step 5 is recorded. A later
deploy prunes machine-local backups to the newest five
([§7](fly-deployment.md#7-backups)).

```bash
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
fly ssh console -a "$ENFOLDED_CLEAR_APP" -C "python main.py backup --to /data/backups/worlds-clear-${STAMP}.db"
umask 077
CLEAR_DIR="$(mktemp -d "${TMPDIR:-/tmp}/enfolded-clear.XXXXXXXX")"
cd "$CLEAR_DIR"
fly ssh sftp get "/data/backups/worlds-clear-${STAMP}.db" -a "$ENFOLDED_CLEAR_APP"
chmod 600 "worlds-clear-${STAMP}.db"
```

`mktemp -d` creates that directory at mode `0700`. flyctl 0.5.1 opens the
downloaded file with mode `0644`. The shell `umask 077` masks that creation
to `0600`, and `chmod 600` sets the same mode again. Do not use `mkdir -p`
under `/tmp`: with umask `022` that directory is `0755`, and other accounts
on a shared machine can then read the backup, including participant chat.
Keep the file out of the checkout.

Write the backup path into the private entry. If the write below has to be
undone, restore this backup with
[Restoring from a backup](fly-deployment.md#restoring-from-a-backup). A
restore abandons everything recorded after the backup.

### 3. Clear the latch

Still on the machine, from `cd /app`, and only after the evidence items
and the backup path are in the private entry. If the reason is
`billing_anomaly`, stop here until item 5 names the cause and the owner's
correction. The script opens `/data/.nested-worlds/worlds.db` and no other
file. It opens that file read-write and does not create it. A missing file
fails and leaves no empty database. It resolves each
`reserved` row to `uncertain` at the same `accounted_microusd`, sets
`settled_at`, clears `abandoned_at`, and deletes the latch row. It commits
only when no reserved row remains and no row's money, day, or retention
changed, and only when the reserved ids are exactly the ones from the
listing. The money, day, and retention comparison is against the rows this
transaction read, not against that listing. Any refusal rolls back. Replace
`throwaway-app-name` with this machine's app name, `2026-11-20` with the
comma-separated days from `reconcile days`, and `id1` with the reserved ids
from the listing. If that listing printed `(none)`, leave
`ENFOLDED_CLEAR_RESERVED` empty. Do not set `FLY_APP_NAME` on the command.

```bash
cd /app && ENFOLDED_CLEAR_APP=throwaway-app-name ENFOLDED_CLEAR_DAYS=2026-11-20 ENFOLDED_CLEAR_RESERVED=id1 python - <<'EOF'
import os
import sqlite3
from datetime import datetime, timezone

app = os.environ.get("FLY_APP_NAME", "").strip()
intended = os.environ.get("ENFOLDED_CLEAR_APP", "").strip()
if not app or app != intended:
    raise SystemExit("refusing: FLY_APP_NAME does not match ENFOLDED_CLEAR_APP")
if app == "enfolded-beta":
    raise SystemExit("refusing: the kept world named in fly.toml")
if os.environ.get("NESTED_WORLDS_TEST_WORLD", "").strip().casefold() not in {"1", "true", "on", "yes"}:
    raise SystemExit("refusing: NESTED_WORLDS_TEST_WORLD is not on")

path = "/data/.nested-worlds/worlds.db"
reasons = {"billing_anomaly", "accounting_fault", "unsettled_startup"}
db = sqlite3.connect("file:" + path + "?mode=rw", uri=True, timeout=5, isolation_level=None)
db.row_factory = sqlite3.Row
started = False
try:
    db.execute("BEGIN IMMEDIATE")
    started = True
    latch = db.execute(
        "SELECT singleton, latched_at, reason FROM model_spend_latch"
    ).fetchall()
    if len(latch) != 1 or latch[0]["singleton"] != 1 or latch[0]["reason"] not in reasons:
        raise SystemExit("refusing: expected one latch row with a known reason")
    before = db.execute(
        """SELECT id, day, status, reserved_microusd, accounted_microusd,
                  retention_days, retain_until
           FROM model_spend_reservations"""
    ).fetchall()
    listed = {part.strip() for part in os.environ.get("ENFOLDED_CLEAR_RESERVED", "").split(",") if part.strip()}
    seen = {row["id"] for row in before if row["status"] == "reserved"}
    if listed != seen:
        raise SystemExit("refusing: reserved ids do not match the listing: " + ",".join(sorted(listed ^ seen)))
    for row in before:
        if row["status"] == "reserved" and row["accounted_microusd"] != row["reserved_microusd"]:
            raise SystemExit("refusing: a reserved row's accounted total does not match")
    stamp = latch[0]["latched_at"]
    if len(stamp) < 10 or stamp[4] != "-" or stamp[7] != "-":
        raise SystemExit("refusing: latched_at is not a UTC date")
    needed = {stamp[:10]}
    for row in before:
        if row["status"] in {"reserved", "anomaly"}:
            needed.add(row["day"])
    given = {part.strip() for part in os.environ.get("ENFOLDED_CLEAR_DAYS", "").split(",") if part.strip()}
    missing = sorted(needed - given)
    if missing:
        raise SystemExit("refusing: reconcile these UTC days in the provider console first: " + ",".join(missing))
    now = datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
    db.execute(
        """UPDATE model_spend_reservations
           SET status='uncertain', settled_at=?, abandoned_at=NULL
           WHERE status='reserved'""",
        (now,),
    )
    after = db.execute(
        """SELECT id, day, status, reserved_microusd, accounted_microusd,
                  retention_days, retain_until, settled_at, abandoned_at
           FROM model_spend_reservations"""
    ).fetchall()
    by_id = {row["id"]: row for row in after}
    if len(after) != len(before):
        raise SystemExit("refusing: the reservation count changed")
    resolved = 0
    for old in before:
        new = by_id[old["id"]]
        if (new["accounted_microusd"] != old["accounted_microusd"]
                or new["reserved_microusd"] != old["reserved_microusd"]
                or new["day"] != old["day"]
                or new["retention_days"] != old["retention_days"]
                or new["retain_until"] != old["retain_until"]):
            raise SystemExit("refusing: money, day, or retention changed")
        if old["status"] == "reserved":
            resolved += 1
            if (new["status"] != "uncertain" or new["settled_at"] != now
                    or new["abandoned_at"] is not None):
                raise SystemExit("refusing: a reserved row did not resolve to uncertain")
        elif new["status"] != old["status"]:
            raise SystemExit("refusing: a terminal row changed status")
    if db.execute(
        "SELECT COUNT(*) FROM model_spend_reservations WHERE status='reserved'"
    ).fetchone()[0] != 0:
        raise SystemExit("refusing: a reserved row remains")
    db.execute("DELETE FROM model_spend_latch WHERE singleton=1")
    if db.execute("SELECT COUNT(*) FROM model_spend_latch").fetchone()[0] != 0:
        raise SystemExit("refusing: the latch row remains")
    db.execute("COMMIT")
    started = False
    print(f"cleared app={app} reason={latch[0]['reason']} latched_at={latch[0]['latched_at']} resolved={resolved} at {now}")
except BaseException:
    if started:
        db.execute("ROLLBACK")
    raise
finally:
    db.close()
EOF
```

Use the app's real name for `ENFOLDED_CLEAR_APP` on the watch twin as well,
and set `ENFOLDED_CLEAR_DAYS` to every day the read-only listing printed
under `reconcile days`. Do not set `FLY_APP_NAME` on this command. If the
script exits with `database is locked`, a writer still holds the file. Wait
until the switches are on and `/health` is ok, and run it again. Do not
delete the database file. A second successful clear is a new incident: the
script refuses when the latch row is already gone.

### 4. Restart

```bash
fly machine list -a "$ENFOLDED_CLEAR_APP"
fly machine restart <machine-id> -a "$ENFOLDED_CLEAR_APP"
curl -fsS "https://${ENFOLDED_CLEAR_APP}.fly.dev/health"
```

The new process runs the startup scan. Reserved rows or a latch row stop
dispatch again. This restart is the one that drops the server's
`_settlement_fault`. It is not, by itself, a clear. The restart replaces
the machine's ephemeral root filesystem. The volume at `/data`, including
the database and the backup taken above, stays.

### 5. Confirm, then one settled call

On the machine:

```bash
fly ssh console -a "$ENFOLDED_CLEAR_APP" -C "python main.py models"
fly ssh console -a "$ENFOLDED_CLEAR_APP" -C "python main.py voice-health"
```

Require these lines, and require the output not to contain `STOPPED`:

- `model accounting durable stop: no`
- `model accounting unresolved reservations: 0`
- `model controls: no recorded stop`

`voice-health: ok` is the accounting result when nothing else in the window
is wrong. Another failure in that window (a screen error, a missing
provider) still fails the command. The clear's accounting half is the three
lines above, and the absence of `controlled model dispatch is stopped`.
Record any other failure. Do not treat it as the latch, and do not ignore
a durable stop hiding behind it.

These commands read the database and their own process. They do not read the
server's memory. The restart in step 4 is what replaces that process.

Only then restore the voice and moderation values recorded in step 1.
Leave the image switch at `1`. Do not write `0` unless step 1 recorded `0`.
A secret set to `0` overrides `fly.toml`, whose
`NESTED_WORLDS_DISABLE_AI` is `1`. For a name that step 1 found unset, use
`fly secrets unset` with that name and no `=`. Unsetting
`NESTED_WORLDS_DISABLE_AI` restores the committed `1`.
`NESTED_WORLDS_DISABLE_MODERATION` is not in `fly.toml`; unsetting it leaves
the name absent, and an absent value does not disable moderation
(`fly-deployment.md` records the `unset` form). Restoring a voice value of
`1`, or unsetting it, means the confirming call will not dispatch. Leave it
that way. The clear stays incomplete until the owner records the live value
to restore. This set restarts the machine again and is not a clear. Re-read
the three lines after `/health` returns.

```bash
fly secrets set -a "$ENFOLDED_CLEAR_APP" \
  NESTED_WORLDS_DISABLE_AI="$RECORDED_AI" \
  NESTED_WORLDS_DISABLE_MODERATION="$RECORDED_MODERATION"
```

`$RECORDED_AI` and `$RECORDED_MODERATION` are the strings step 1 printed.
Omit a name that was unset, and unset that name instead:

```bash
fly secrets unset -a "$ENFOLDED_CLEAR_APP" NESTED_WORLDS_DISABLE_AI
```

Take a UTC stamp in the ledger's form (`2026-11-20T23:40:00.000000Z`) after
this restart and before the call. Then make one ordinary authenticated
gameplay call that is expected to dispatch: a place line, an agent line, or
an Act free-text intention. Do not ask whether the speaker is human. Do not
pass `--probe`. Controlled mode refuses those probes.

Run the step 2 read-only script again on the machine. Set
`ENFOLDED_CLEAR_SINCE` to that stamp on the same command
(`ENFOLDED_CLEAR_SINCE=2026-11-20T23:40:00.000000Z python - <<'EOF'`). Every
row under `created after` is `settled`, with `accounted_microusd` less than
or equal to `reserved_microusd`. The latch section is `(no row)`. At least
one such row exists. The clear is complete only then. Write the reservation
ids and statuses into the private entry.

If that is not what the listing shows, set both kill switches back to `1`
before another paid call:

```bash
fly secrets set -a "$ENFOLDED_CLEAR_APP" \
  NESTED_WORLDS_DISABLE_AI=1 \
  NESTED_WORLDS_DISABLE_MODERATION=1
```

What happens next depends on the rows.

An allowance refusal leaves no new row and no latch. Today's accounted
total had no room for one more full reservation. A row whose status is
`uncertain` also leaves no latch: a usable reply can settle that way when
usage is missing, and the full reservation stays. Record the rows.
Reconcile them, then restore the recorded switch values and make another
confirming call once the current UTC day can admit one reservation. Do not
substitute `0`. Until that call's rows are all `settled`, the clear is not
complete and the switches stay at `1`.

A `reserved` row does not stay unlatched. The `fly secrets set` above
restarts the machine, and that boot's startup scan writes a new
`unsettled_startup` latch while any `reserved` row remains. An `anomaly`
row does not stay unlatched either: settlement writes a `billing_anomaly`
latch as it settles. Another confirming call cannot succeed. Start again
from [Evidence before the write](#evidence-before-the-write). That is a new
incident. For `anomaly`, item 5's owner correction applies before the next
write.

### Rehearsal on a throwaway app

Do not run this rehearsal from the repository, against the twin, or against
a kept world. The owner brings the throwaway app up with its own volume, its
own approved policy, its own key, and `NESTED_WORLDS_TEST_WORLD=1` before
the first boot. Without that setting the write refuses. With it on, the
participation notice is required, so the ordinary calls below, and the
confirming call in step 5, need a credential that has accepted the current
notice. This page does not mint that key.

1. One ordinary call settles. The read-only listing shows that row
   `settled` and no latch row.
2. Start a second ordinary call and stop the machine before it returns, so
   a `reserved` row is left behind. Start the machine again. `python main.py
   models` reports a durable stop. A further call does not dispatch. If no
   reserved row was left, the application did not produce the stop. Do not
   insert a latch row by hand. Record that and try the interrupted call
   once more.
3. Run this procedure: the evidence items, the backup, the hand-SQL
   clear, the restart, and one settled call after it.
4. Record the result for the owner. ADR-039 is accepted only after this
   rehearsal passes, and only in the records or status pull request the
   owner names.

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

For new traveler chat and reports, use the private
[operator queue](../development/community-reporting.md#operator-queue):
`python main.py report list`, then `report show REPORT_ID`. Acknowledge or close
with `--note -` to keep the private note out of shell history. Output is escaped
JSON and remains operator data. Reporting reaches no provider, makes no automatic
sanction and sends no external notification. Arrange queue polling toward the
24-hour beta goal; this page does not establish a live staffing commitment.

Human chat follows its recorded policy, including retention until deletion.
Use `chat-log delete EVIDENCE_REF` for one line or `chat-log delete-tester NAME`
for one tester's lines across keys. Open or acknowledged reports hold cited
lines until closure; deletion removes eligible lines and reports the held count
and reason. It never closes a complaint. Reports reference the original line
without copying its quotation. Reporter explanations are separately retained report content. All
new human WebSocket chat uses this operational log in every mode; absent policy
disables it and reporting, not other gameplay. Authored ambient conversations
and place/inhabitant exchanges remain recorded separately. Use `community-status`
and `community-prune` for eligible timed expiry; pending complaints and cited
evidence remain held until closure. Stopped-server cleanup and backup
deletion remain operator responsibilities, including the potentially indefinite
newest-backup exception. None of these commands rewrite legacy chronicle rows.

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
