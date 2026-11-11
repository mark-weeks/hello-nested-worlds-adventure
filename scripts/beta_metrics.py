#!/usr/bin/env python3
"""Beta health metrics, read straight from the chronicle.

The pre-mortem's cheapest prevention: make "did the beta work?" a number
instead of a feeling. The chronicle already records durable actor_identity
attribution, so this script needs no instrumentation, no
third-party analytics, and no network — it answers the launch questions
from the world's own memory:

  * how many humans visited in the window, and how many acted on two or
    more distinct UTC days (an operational return count, not evidence of
    unprompted or useful return; the pilot measures those). Only a day that holds
    an action counts toward a return: presence cannot tell a person who
    came back from a tab that reconnected, so a visit that crosses
    midnight and only leaves after it, or an open tab that a deploy
    reconnects after midnight, is one day. The costs: a visitor who comes
    back only to look, with no step and no word, is a visitor but not a
    returning one; and one session with actions on both sides of 00:00
    UTC still counts as two days. A visitor is a
    participant: a rotated key's identities fold into one visitor through
    participant_credentials (migration 0021), read-only
  * how many of them did something beyond connecting: an action is any
    human row that is not presence, so an Act commit
    (INTERVENTION_COMMITTED) counts. Presence is the PLAYER_JOIN and
    PLAYER_LEAVE every socket writes, and a PLAYER_MOVE that goes nowhere
    (see _announced_moves)
  * how much they actually did: conversations with places and agents,
    Act commits, puzzle attempts and solves (an entangled twin that
    resolves with its partner's solve is reported apart, not as a second
    solve or a second action), failed puzzles (each failed
    pool once, in the window that holds its first non-agent failure row
    and only when that row's actor counts, however many
    wrong guesses followed it), scale verbs, chat
  * where they went (top nodes by human activity)
  * whether the world itself is alive (total chronicle size, first event)
  * whether the world could answer: voice lines answered vs. quiet, by
    surface and reason (the daily voice-outcome counters, never the
    chronicle), so "didn't talk" and "talked to silence" stay separable
  * whether shared text could be screened: screens by surface and
    outcome (the daily moderation-outcome counters; a locally clean line
    is not counted)
  * optionally, a per-participant timeline: seconds from first join to
    first move (not a connect-time announcement), first Act commit, first
    puzzle attempt and first solve, under ordinal pseudonyms (P1, P2, ...)
    only

Run against the live DB (read-only connection, safe alongside the
server), or against any backup file:

  python scripts/beta_metrics.py                     # live DB, last 7 days
  python scripts/beta_metrics.py --days 1            # launch-day check
  python scripts/beta_metrics.py --db offhost.db     # from a backup
  python scripts/beta_metrics.py --db watch.db \\
      --since 2026-11-10 --until 2026-11-12         # an archive, by UTC date
  python scripts/beta_metrics.py --exclude-identity Facilitator --timeline
  python scripts/beta_metrics.py --json              # machine-readable

Server-owned and agent-tagged actions never count as human progress.
--exclude-identity NAME drops a registered player by name, through every
credential their participant has held (the facilitator, a disclosed second
traveler), from the visitor counts and from the model-written rows. It
cannot reach the daily voice and moderation counters, which carry no
identity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# Make the repo importable when run as `python scripts/beta_metrics.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Event types a human can author. Ambient agents write SCALE_ACT and puzzle
# rows too; their identities and agent-tagged actions must stay out of the
# human counts. AGENT_VOICE is different: its actor is the asking player.
_HUMAN_TYPES = (
    "PLAYER_JOIN", "PLAYER_MOVE", "PLAYER_LEAVE", "PLAYER_CHAT",
    "PLAYER_SPEAK", "AGENT_VOICE", "PUZZLE_ATTEMPT", "PUZZLE_SOLVED",
    "PUZZLE_FAILED", "SCALE_ACT", "INTERVENTION_COMMITTED",
)

# AGENT_VOICE carries the addressed agent while its actor is the player.
# On action/puzzle rows, data.agent instead marks the acting ambient agent.
# Match Python's bool(data.get("agent")): null/false/0/""/[]/{} are false;
# nonzero numbers, nonempty strings (including "0") and containers are true.
# TestAmbientMetricsSafeguards pins both paths against that truth table.
_NO_AGENT_TAG = """(COALESCE(json_extract({data}, '$.agent'), '') IN ('', 0)
    OR (json_type({data}, '$.agent') IN ('array', 'object')
        AND NOT EXISTS (SELECT 1 FROM json_each({data}, '$.agent'))))"""
_PLAYER_ACTION = f"""(mutation_type NOT IN (
    'SCALE_ACT', 'INTERVENTION_COMMITTED', 'PUZZLE_ATTEMPT',
    'PUZZLE_SOLVED', 'PUZZLE_FAILED')
    OR {_NO_AGENT_TAG.format(data='data')})"""

# Rows every WebSocket connection writes on its own (server/websocket.py):
# presence, not an action. So is an announced move (_announced_moves).
# Everything else in _HUMAN_TYPES is something the player chose to do.
_PRESENCE_TYPES = frozenset({"PLAYER_JOIN", "PLAYER_LEAVE"})

# A solve at an entangled particle resolves its twin in the same commit
# (server/world_mechanics.py, resolve_entangled_twin): a second
# PUZZLE_SOLVED at the twin, under the solver's actor_identity, whose data
# names the partner in "entangled_with". It is the world answering one
# solve, not a second solve, an action, or a visit to the twin, so it stays
# out of the human rows and is counted apart.
_TWIN_SOLVE = ("(mutation_type = 'PUZZLE_SOLVED'"
               " AND json_extract(data, '$.entangled_with') IS NOT NULL)")

# How long after its PLAYER_JOIN a socket's connect announcement can still
# land. Both clients send it as the socket's first frame, as soon as it
# opens, and server/websocket.py closes a socket that sends nothing for
# 60 s, writing its PLAYER_LEAVE: a join not announced by then never is.
_ANNOUNCE_WITHIN_SEC = 60


def _announced_moves(conn: sqlite3.Connection, *, seed: int | None = None,
                     skip: tuple[str, ...] = ()) -> set[int]:
    """Ids of the PLAYER_MOVE rows that go nowhere: presence, not a step.

    Both shipped clients send a move for the node they show on every
    WebSocket (re)connect, with no player input (static/explorer.js in
    ws.onopen; frontend/src/App.jsx once connected), and the explorer sends
    one again when it reloads the view at another depth or the node it is
    on is selected again. server/websocket.py writes a PLAYER_MOVE for every
    move frame, including one to the node the socket already stands on.

    The rows name no socket (data is {}), and two tabs on one credential
    share one actor_identity, so their rows can interleave: JOIN, JOIN,
    MOVE, MOVE. So, per identity and world in row order, each PLAYER_JOIN
    owes one announcement. A move is announced when one is still owed as
    it arrives (the connect announcement, whichever node it names: a first
    visit can join at the root before the client's saved position lands),
    or when it names the same node as the identity's previous JOIN-or-MOVE
    row. Every move pays the oldest announcement still owed. A PLAYER_LEAVE
    cancels one announcement still owed (the newest), so a socket that
    closed before its announcement was recorded (closed early, or its
    announcement was turned away: a seal, no such place, the shared move
    bucket) leaves nothing for the identity's next visit. An owed
    announcement also lapses ``_ANNOUNCE_WITHIN_SEC`` after its join, so a
    socket lost to a restart or a deploy (neither writes a PLAYER_LEAVE)
    owes nothing a minute later. No count of open sockets is kept: a lost
    PLAYER_LEAVE would inflate it for good.

    Read over all time, so a join before the window still marks its
    announcement; the window filters the rows afterwards. Residual limits,
    without a stored socket id: a client that never announces (a raw
    socket) loses its first real move. A PLAYER_LEAVE does not say which
    socket left, so a tab that closes after announcing, between another
    tab's join and that tab's announcement, cancels the other tab's debt
    and its announcement reads as an action. An announcement recorded more
    than ``_ANNOUNCE_WITHIN_SEC`` after its join, naming another node than
    the join, reads as an action (both clients send it as the socket's first
    frame; their 20 s keepalive keeps a socket whose announcement was turned
    away open, which is harmless here). With two tabs open, a step
    one tab takes before the other's announcement is recorded reads as that
    announcement and the announcement as the step (the counts stay right;
    the timeline's first move can shift by the gap), and a reselect
    compares against the other tab's last row.
    """
    where = ("mutation_type IN ('PLAYER_JOIN', 'PLAYER_MOVE', 'PLAYER_LEAVE')"
             " AND actor_identity IS NOT NULL")
    args: list = []
    if skip:
        where += f" AND actor_identity NOT IN ({','.join('?' for _ in skip)})"
        args.extend(skip)
    if seed is not None:
        where += " AND world_seed = ?"
        args.append(seed)
    announced: set[int] = set()
    # (identity, world) -> [owed join times, last node]
    sockets: dict[tuple, list] = {}
    for row_id, identity, world, kind, node, at in conn.execute(
            f"""SELECT id, actor_identity, world_seed, mutation_type, node_name,
                       CAST(strftime('%s', recorded_at) AS INTEGER)
                FROM world_mutations WHERE {where} ORDER BY id""", args):
        state = sockets.setdefault((identity, world), [[], None])
        if kind == "PLAYER_JOIN":
            state[0].append(at)
            state[1] = node
        elif kind == "PLAYER_LEAVE":
            if state[0]:
                state[0].pop()
        else:
            # An unreadable time cannot lapse.
            owed = [joined for joined in state[0]
                    if at is None or joined is None
                    or at - joined <= _ANNOUNCE_WITHIN_SEC]
            if owed:
                announced.add(row_id)
                owed.pop(0)
            elif node == state[1]:
                announced.add(row_id)
            state[0] = owed
            state[1] = node
    return announced

_CONVERSATION_TYPES = ("PLAYER_SPEAK", "AGENT_VOICE")

# The --timeline milestones, in report order: (field, mutation type).
_MILESTONES = (
    ("first_move", "PLAYER_MOVE"),
    ("first_act", "INTERVENTION_COMMITTED"),
    ("first_puzzle_attempt", "PUZZLE_ATTEMPT"),
    ("first_solve", "PUZZLE_SOLVED"),
)

# server.observability.VOICE_OUTCOME_PREFIX and MODERATION_OUTCOME_PREFIX;
# read here as SQL so a backup file can be inspected without importing the
# server.
_VOICE_PREFIX = "voice_outcome:"
_MODERATION_PREFIX = "moderation_outcome:"

# recorded_at is SQLite's datetime('now'): UTC, 'YYYY-MM-DD HH:MM:SS', so a
# bound in the same form compares as text.
_STAMP = "%Y-%m-%d %H:%M:%S"


class _Window:
    """The time window, as SQL fragments for rows and for daily counters.

    ``--days N`` keeps the original behaviour: rows recorded in the last N
    days before now, counters for the last N UTC days including today.
    ``--since`` / ``--until`` fix the window in absolute UTC time, so an
    archived database reads the same whenever it is read.
    """

    def __init__(self, days: int | None, since: datetime | None,
                 until: datetime | None) -> None:
        self.days = days
        self.since = since
        self.until = until

    def rows(self, column: str = "recorded_at") -> tuple[str, list]:
        if self.days is not None:
            return f"{column} >= datetime('now', ?)", [f"-{int(self.days)} days"]
        clauses, args = [], []
        if self.since is not None:
            clauses.append(f"{column} >= ?")
            args.append(self.since.strftime(_STAMP))
        if self.until is not None:
            clauses.append(f"{column} < ?")
            args.append(self.until.strftime(_STAMP))
        return (" AND ".join(clauses) or "1"), args

    def counter_days(self) -> tuple[str, list]:
        if self.days is not None:
            return "day >= date('now', ?)", [f"-{max(1, int(self.days)) - 1} days"]
        clauses, args = [], []
        if self.since is not None:
            clauses.append("day >= ?")
            args.append(self.since.date().isoformat())
        if self.until is not None:
            # The last UTC day the exclusive upper bound still touches.
            clauses.append("day <= ?")
            args.append((self.until - timedelta(seconds=1)).date().isoformat())
        return (" AND ".join(clauses) or "1"), args

    def bounds(self, conn: sqlite3.Connection) -> dict:
        if self.days is not None:
            since = conn.execute("SELECT datetime('now', ?)",
                                 (f"-{int(self.days)} days",)).fetchone()[0]
            return {"since": since, "until": None}
        return {
            "since": self.since.strftime(_STAMP) if self.since else None,
            "until": self.until.strftime(_STAMP) if self.until else None,
        }


def parse_bound(text: str, *, end: bool = False) -> datetime:
    """An ISO date or date-time as naive UTC.

    Whatever ``date.fromisoformat`` reads is a date, in any ISO form it
    takes (2026-01-05, 20260105, 2026-W02-1, 2026W021), and means that
    whole UTC day: as ``--since`` it starts at 00:00:00, and as ``--until``
    (``end=True``) it runs through 23:59:59, so the exclusive bound is the
    next midnight. Anything else must be a date-time; one with an offset is
    converted to UTC, one without is UTC. recorded_at holds whole seconds,
    so a fractional bound widens to the second it falls in: ``--since``
    rounds down and ``--until`` rounds up, and a row stamped in that second
    stays inside the window.
    """
    raw = str(text).strip()
    try:
        day = date.fromisoformat(raw)
    except ValueError:
        pass
    else:
        moment = datetime(day.year, day.month, day.day)
        return moment + timedelta(days=1) if end else moment
    try:
        moment = datetime.fromisoformat(raw)
    except ValueError:
        raise ValueError(
            f"{raw!r} is not an ISO date (YYYY-MM-DD) or date-time") from None
    if moment.tzinfo is not None:
        moment = moment.astimezone(timezone.utc).replace(tzinfo=None)
    if moment.microsecond:
        moment = moment.replace(microsecond=0)
        if end:
            moment += timedelta(seconds=1)
    return moment


def _window(days: int | None, since: datetime | str | None,
            until: datetime | str | None) -> _Window:
    if isinstance(since, str):
        since = parse_bound(since)
    if isinstance(until, str):
        until = parse_bound(until, end=True)
    if since is None and until is None:
        return _Window(7 if days is None else int(days), None, None)
    if days is not None:
        raise ValueError("use --days, or --since/--until, not both")
    if since is not None and until is not None and since >= until:
        raise ValueError("--since must be earlier than --until")
    return _Window(None, since, until)


def _outcome_counts(conn: sqlite3.Connection, prefix: str,
                    window: _Window) -> dict:
    """``{surface: {outcome: count}}`` for one counter prefix, summed over the window's UTC days."""
    day_clause, day_args = window.counter_days()
    rows = conn.execute(
        f"""SELECT bucket, SUM(calls) FROM cost_budget
           WHERE substr(bucket, 1, ?) = ? AND {day_clause}
           GROUP BY bucket""",
        (len(prefix), prefix, *day_args),
    ).fetchall()
    out: dict = {}
    for bucket, calls in rows:
        # A row that is not <prefix><surface>:<outcome> is skipped, so one
        # stray bucket cannot take down the whole report.
        parts = bucket[len(prefix):].split(":")
        if len(parts) != 2 or not all(parts):
            continue
        surface, reason = parts
        out.setdefault(surface, {})[reason] = int(calls)
    return out


def _default_db() -> Path:
    import persistence
    return persistence._DB_PATH


def _cast_names() -> tuple[str, ...]:
    from agents.identities import SERVER_IDENTITIES
    return SERVER_IDENTITIES


def _connect_ro(db_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


def _has_table(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (name,)).fetchone() is not None


def _identity_owners(conn: sqlite3.Connection) -> dict[str, str]:
    """actor_identity → participant id, where exactly one participant owns it.

    Rotation (persistence.participants.rotate) records every credential a
    participant has held, each with its own actor_identity. An identity
    with no row, or one more than one participant claims, stays its own
    visitor, as ``participants.actor_aliases`` treats it. Older backups
    have no table: nothing folds.
    """
    if not _has_table(conn, "participant_credentials"):
        return {}
    owners: dict[str, set] = {}
    for identity, participant in conn.execute(
            "SELECT actor_identity, participant_id FROM participant_credentials"):
        owners.setdefault(identity, set()).add(participant)
    return {identity: next(iter(ps))
            for identity, ps in owners.items() if len(ps) == 1}


def _digest_of(stored_key: str) -> str:
    """The at-rest digest for an invite_keys.key value.

    Current databases store the sha256 digest. A backup from before the
    at-rest hashing still holds the plaintext ``nw_`` key; hash it here,
    in memory, without writing anything back.
    """
    if stored_key.startswith("nw_"):
        return hashlib.sha256(stored_key.encode("utf-8")).hexdigest()
    return stored_key


def resolve_excluded(conn: sqlite3.Connection,
                     names: tuple[str, ...] | list[str]) -> set[str]:
    """Every actor_identity belonging to the named players.

    A name matches a registered invite name under ``persistence.name_key``
    (revoked keys included: a facilitator's key may be revoked before the
    read). Each matching credential's participant contributes all of its
    credentials' identities, so a rotated key is excluded under every key
    it has had. A name with no registration is accepted only when the
    chronicle holds it as a keyless identity (ungated local play);
    otherwise it is an error, so a typo cannot silently exclude no one.
    """
    if not names:
        return set()
    from persistence import name_key
    invites = (conn.execute("SELECT key, name FROM invite_keys").fetchall()
               if _has_table(conn, "invite_keys") else [])
    has_credentials = _has_table(conn, "participant_credentials")
    excluded: set[str] = set()
    for name in names:
        wanted = name_key(str(name))
        digests = [_digest_of(key) for key, registered in invites
                   if name_key(registered) == wanted]
        if not digests:
            if conn.execute(
                    "SELECT 1 FROM world_mutations WHERE actor_identity = ? LIMIT 1",
                    (str(name),)).fetchone():
                excluded.add(str(name))
                continue
            raise ValueError(f"no registered player is named {name!r}")
        excluded.update(digest[:16] for digest in digests)
        if has_credentials:
            ph = ",".join("?" for _ in digests)
            excluded.update(identity for (identity,) in conn.execute(
                f"""SELECT actor_identity FROM participant_credentials
                    WHERE participant_id IN (
                        SELECT participant_id FROM participant_credentials
                        WHERE credential_digest IN ({ph}))""", digests))
    return excluded


def _seconds_between(start: str, end: str | None) -> int | None:
    if end is None:
        return None
    return int((datetime.strptime(end, _STAMP)
                - datetime.strptime(start, _STAMP)).total_seconds())


def compute_metrics(db_path: Path, days: int | None = None,
                    seed: int | None = None, *,
                    since: datetime | str | None = None,
                    until: datetime | str | None = None,
                    exclude: tuple[str, ...] | list[str] = (),
                    timeline: bool = False) -> dict:
    window = _window(days, since, until)
    cast = _cast_names()
    conn = _connect_ro(Path(db_path))
    try:
        excluded = sorted(resolve_excluded(conn, exclude))
        owners = _identity_owners(conn)
        type_ph = ",".join("?" for _ in _HUMAN_TYPES)
        skip = (*cast, *excluded)
        skip_ph = ",".join("?" for _ in skip)
        time_clause, time_args = window.rows()
        counted_where = (
            f"mutation_type IN ({type_ph}) "
            f"AND actor_identity IS NOT NULL "
            f"AND actor_identity NOT IN ({skip_ph}) "
            f"AND {_PLAYER_ACTION} "
            f"AND {time_clause}"
        )
        args: list = [*_HUMAN_TYPES, *skip, *time_args]
        if seed is not None:
            counted_where += " AND world_seed = ?"
            args.append(seed)
        # Same placeholders, so q() serves both.
        human_where = f"{counted_where} AND NOT {_TWIN_SOLVE}"

        def q(sql: str, extra: tuple = ()):
            return conn.execute(sql, (*args, *extra)).fetchall()

        # Classified in Python over the fetched rows, then looked up from
        # SQL; registering a function writes nothing.
        announced = _announced_moves(conn, seed=seed, skip=skip)
        conn.create_function("announced_move", 1, announced.__contains__,
                             deterministic=True)

        # Per identity, day, type and announced flag; folded into
        # participants below so a rotated key's days and actions add up
        # under one visitor.
        per_day = q(f"""SELECT actor_identity, date(recorded_at),
                               mutation_type, announced_move(id), COUNT(*)
                        FROM world_mutations WHERE {human_where}
                        GROUP BY 1, 2, 3, 4""")
        top_nodes = q(f"""SELECT node_name, COUNT(*) AS n
                          FROM world_mutations WHERE {human_where}
                          GROUP BY node_name ORDER BY n DESC LIMIT 10""")
        # A pool is one question at one node: the node's renewal epoch
        # (its PUZZLE_REARM count before the row) names it. Every wrong
        # guess after a pool fails writes another PUZZLE_FAILED until the
        # pool is renewed, so the rows overstate failures. A pool is
        # counted by its first non-agent failure row over all time, the attempt
        # that exhausted it: once, in the window that holds that row, and only
        # when that row's actor counts. A late guess today at a pool that
        # failed last week, or at one an excluded facilitator exhausted,
        # is not a failure in today's read. An ambient failure cannot exhaust
        # a human pool, so discard agent identities and payloads before finding
        # that first row. Facilitator exclusions still apply afterwards: they
        # must not transfer an exhausted pool to a tester's late retry. Legacy
        # untagged, unattributed failures also anchor their pool: absence of
        # attribution does not establish that an agent exhausted it.
        cast_ph = ",".join("?" for _ in cast)
        failed_pools = q(f"""SELECT COUNT(*) FROM world_mutations
                WHERE {human_where} AND id IN (
                    SELECT MIN(id) FROM (
                        SELECT f.id, f.world_seed, f.node_name,
                               (SELECT COUNT(*) FROM world_mutations r
                                WHERE r.world_seed = f.world_seed
                                  AND r.node_name = f.node_name
                                  AND r.mutation_type = 'PUZZLE_REARM'
                                  AND r.id < f.id) AS epoch
                        FROM world_mutations AS f
                        WHERE f.mutation_type = 'PUZZLE_FAILED'
                          AND (f.actor_identity IS NULL
                               OR f.actor_identity NOT IN ({cast_ph}))
                          AND {_NO_AGENT_TAG.format(data='f.data')})
                    GROUP BY world_seed, node_name, epoch)""", cast)[0][0]
        twins_resolved = q(f"""SELECT COUNT(*) FROM world_mutations
                               WHERE {counted_where} AND {_TWIN_SOLVE}""")[0][0]

        total_rows = conn.execute(
            "SELECT COUNT(*) FROM world_mutations").fetchone()[0]
        first_at = conn.execute(
            "SELECT MIN(recorded_at) FROM world_mutations").fetchone()[0]
        # Older backups have no side table. Absence is an empty count, not
        # a guessed provider, and this read must not migrate the file.
        # The cast and unattributed rows stay: this section has always
        # counted every caller. An excluded player's rows do not.
        model_provenance: list[dict] = []
        if _has_table(conn, "mutation_model_provenance"):
            m_clause, scope_args = window.rows("m.recorded_at")
            scope = ""
            if seed is not None:
                scope = " AND m.world_seed = ?"
                scope_args.append(seed)
            if excluded:
                scope += (" AND (m.actor_identity IS NULL OR m.actor_identity"
                          f" NOT IN ({','.join('?' for _ in excluded)}))")
                scope_args.extend(excluded)
            model_provenance = [
                {"provider": provider, "resolved_model": model, "rows": count}
                for provider, model, count in conn.execute(
                    f"""SELECT p.provider, p.resolved_model, COUNT(*)
                        FROM mutation_model_provenance p
                        JOIN world_mutations m ON m.id = p.mutation_id
                        WHERE {m_clause}{scope}
                        GROUP BY p.provider, p.resolved_model
                        ORDER BY COUNT(*) DESC, p.provider, p.resolved_model""",
                    scope_args,
                )
            ]

        by_type: dict[str, int] = {}
        visitors: dict[str, dict] = {}
        identities: set[str] = set()
        for identity, day, kind, announced, count in per_day:
            identities.add(identity)
            by_type[kind] = by_type.get(kind, 0) + count
            owner = owners.get(identity)
            key = f"participant:{owner}" if owner else f"actor:{identity}"
            v = visitors.setdefault(key, {"events": 0, "actions": 0,
                                          "days": set()})
            v["events"] += count
            # Only an action marks a day (see the module docstring): a
            # leave after midnight, or a reconnect's join and announcement,
            # is not a second visit.
            if kind not in _PRESENCE_TYPES and not announced:
                v["actions"] += count
                v["days"].add(day)

        n_visitors = len(visitors)
        returning = sum(1 for v in visitors.values() if len(v["days"]) >= 2)
        acting = sum(1 for v in visitors.values() if v["actions"])
        conversations = sum(by_type.get(t, 0) for t in _CONVERSATION_TYPES)
        metrics = {
            "window_days": window.days,
            "window": window.bounds(conn),
            "seed": seed,
            "excluded_identities": len(excluded),
            "visitors": n_visitors,
            "visitor_identities": len(identities),
            "returning_visitors": returning,
            "return_rate": round(returning / n_visitors, 3) if n_visitors else None,
            "acting_visitors": acting,
            "events_per_visitor": (
                round(sum(v["events"] for v in visitors.values()) / n_visitors, 1)
                if n_visitors else None),
            "actions_per_visitor": (
                round(sum(v["actions"] for v in visitors.values()) / n_visitors, 1)
                if n_visitors else None),
            "conversations": conversations,
            "conversations_per_visitor": (
                round(conversations / n_visitors, 1) if n_visitors else None),
            "act_commits": by_type.get("INTERVENTION_COMMITTED", 0),
            "puzzle_attempts": by_type.get("PUZZLE_ATTEMPT", 0),
            "puzzle_solves": by_type.get("PUZZLE_SOLVED", 0),
            "entangled_twins_resolved": twins_resolved,
            "puzzle_failures": failed_pools,
            "puzzle_failed_rows": by_type.get("PUZZLE_FAILED", 0),
            "scale_acts": by_type.get("SCALE_ACT", 0),
            "chat_lines": by_type.get("PLAYER_CHAT", 0),
            "events_by_type": by_type,
            "top_nodes": [{"node": n, "events": c} for n, c in top_nodes],
            "chronicle_total_rows": total_rows,
            "chronicle_first_event": first_at,
            "model_provenance": model_provenance,
            "voice_outcomes": _outcome_counts(conn, _VOICE_PREFIX, window),
            "moderation_outcomes": _outcome_counts(
                conn, _MODERATION_PREFIX, window),
        }
        if timeline:
            metrics["timeline"] = _timeline(
                q(f"""SELECT actor_identity, mutation_type,
                             announced_move(id), MIN(recorded_at), MIN(id)
                      FROM world_mutations WHERE {human_where}
                      GROUP BY 1, 2, 3"""),
                owners)
        return metrics
    finally:
        conn.close()


def _timeline(firsts: list, owners: dict[str, str]) -> list[dict]:
    """Seconds from each participant's first join to their first milestones.

    Only ordinal pseudonyms leave this function: no name, credential hash,
    node, or text. Participants are numbered by when they first appear in
    the window, so P1 is the earliest arrival; the numbering belongs to
    this read and is not stable across windows. A participant whose first
    row in the window is not a PLAYER_JOIN (an HTTP-only client, or a
    socket opened before the window began) is measured from that first row
    instead, and says so, so no offset is negative. An announced move
    (_announced_moves) can start the clock but is never the first move.
    """
    people: dict[str, dict] = {}
    for identity, kind, announced, at, row_id in firsts:
        owner = owners.get(identity)
        key = f"participant:{owner}" if owner else f"actor:{identity}"
        p = people.setdefault(key, {"first": (at, row_id), "kinds": {}})
        p["first"] = min(p["first"], (at, row_id))
        if announced:
            continue
        if kind not in p["kinds"] or at < p["kinds"][kind]:
            p["kinds"][kind] = at
    out = []
    ordered = sorted(people.values(), key=lambda p: p["first"])
    for ordinal, p in enumerate(ordered, start=1):
        start = p["first"][0]
        joined = p["kinds"].get("PLAYER_JOIN") == start
        row = {"participant": f"P{ordinal}",
               "measured_from": "join" if joined else "first event"}
        for field, kind in _MILESTONES:
            row[field] = _seconds_between(start, p["kinds"].get(kind))
        out.append(row)
    return out


def _clock(seconds: int | None) -> str:
    if seconds is None:
        return "—"
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return (f"+{hours}:{minutes:02d}:{secs:02d}" if hours
            else f"+{minutes}:{secs:02d}")


def _window_label(m: dict) -> str:
    if m["window_days"] is not None:
        return f"last {m['window_days']} day(s)"
    since = m["window"]["since"] or "the first event"
    until = m["window"]["until"] or "now"
    return f"{since} to {until} UTC"


def render(m: dict) -> str:
    scope = f"world {m['seed']}" if m["seed"] is not None else "all worlds"
    lines = [
        f"Beta health — {_window_label(m)}, {scope}",
        "=" * 56,
        f"visitors:            {m['visitors']}",
        f"returning (2+ days): {m['returning_visitors']}"
        + (f"  ({m['return_rate']:.0%})" if m["return_rate"] is not None else "")
        + "  (acted on each)",
        f"acting visitors:     {m['acting_visitors']}"
        "  (did more than connect)",
        f"events/visitor:      {m['events_per_visitor'] or 0}",
    ]
    if m["visitor_identities"] != m["visitors"]:
        lines.append(f"  ({m['visitor_identities']} credential identities "
                     "fold into these visitors)")
    if m["excluded_identities"]:
        n = m["excluded_identities"]
        lines.append(f"  (excluded: {n} credential "
                     f"{'identity' if n == 1 else 'identities'}; the daily "
                     "voice and screen counters carry no identity and "
                     "still include them)")
    lines += [
        "",
        f"conversations:       {m['conversations']}"
        + (f"  ({m['conversations_per_visitor']}/visitor)"
           if m["conversations_per_visitor"] is not None else ""),
        f"act commits:         {m['act_commits']}",
        f"puzzle attempts:     {m['puzzle_attempts']}"
        f"  (solved {m['puzzle_solves']}, failed {m['puzzle_failures']})",
        f"scale verbs:         {m['scale_acts']}",
        f"chat lines:          {m['chat_lines']}",
    ]
    if m["puzzle_failed_rows"] != m["puzzle_failures"]:
        lines.append(f"  (failed counts each puzzle once, where it first "
                     f"failed; {m['puzzle_failed_rows']} failure rows include "
                     "wrong guesses after a puzzle had failed)")
    if m["entangled_twins_resolved"]:
        n = m["entangled_twins_resolved"]
        lines.append(f"  ({n} entangled {'twin' if n == 1 else 'twins'} "
                     "resolved alongside a solve; not counted as solves)")
    if m["top_nodes"]:
        lines += ["", "most-visited ground:"]
        lines += [f"  {t['events']:>5}  {t['node']}" for t in m["top_nodes"]]
    lines += [
        "",
        f"chronicle: {m['chronicle_total_rows']} rows total, first event "
        f"{m['chronicle_first_event'] or '(none yet)'}",
    ]
    if m.get("voice_outcomes"):
        lines += ["", "voice (all callers, by UTC day; answered / quiet):"]
        for surface, counts in sorted(m["voice_outcomes"].items()):
            quiet = {r: n for r, n in counts.items() if r != "ok" and n}
            detail = ", ".join(f"{r} {n}" for r, n in sorted(quiet.items()))
            lines.append(
                f"  {surface:<12} {counts.get('ok', 0):>5} / {sum(quiet.values()):<5}"
                + (f"  ({detail})" if detail else ""))
    if m.get("moderation_outcomes"):
        lines += ["", "shared-text screens (by UTC day; screened / not allowed; locally clean lines not counted):"]
        for surface, counts in sorted(m["moderation_outcomes"].items()):
            held = {o: n for o, n in counts.items() if o != "allow" and n}
            detail = ", ".join(f"{o} {n}" for o, n in sorted(held.items()))
            lines.append(
                f"  {surface:<12} {sum(counts.values()):>5} / {sum(held.values()):<5}"
                + (f"  ({detail})" if detail else ""))
    if m.get("model_provenance"):
        lines += ["", "model-written rows in this window:"]
        lines += [
            f"  {item['rows']:>5}  {item['provider'] or '—'} / "
            f"{item['resolved_model'] or '—'}"
            for item in m["model_provenance"]
        ]
    if m.get("timeline") is not None:
        lines += ["", "first steps (from first join; — = not in this window):",
                  "  who   move      act       puzzle    solve"]
        for row in m["timeline"]:
            lines.append(
                f"  {row['participant']:<5} "
                + " ".join(f"{_clock(row[field]):<9}"
                           for field, _ in _MILESTONES).rstrip()
                + ("" if row["measured_from"] == "join"
                   else "  (from first event; no join)"))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", type=Path, default=None,
                    help="Database file (default: the live DB)")
    ap.add_argument("--days", type=int, default=None,
                    help="Window in days before now (default 7)")
    ap.add_argument("--since", default=None,
                    help="Window start, an ISO UTC date or date-time "
                         "(a date starts at 00:00:00); for archives")
    ap.add_argument("--until", default=None,
                    help="Window end, an ISO UTC date or date-time "
                         "(a date runs through that whole day)")
    ap.add_argument("--seed", type=int, default=None,
                    help="Restrict to one world")
    ap.add_argument("--exclude-identity", action="append", default=[],
                    metavar="NAME",
                    help="Leave out a registered player by name, under every "
                         "credential they have held (repeatable)")
    ap.add_argument("--timeline", action="store_true",
                    help="Add each participant's first steps, as P1, P2, ...")
    ap.add_argument("--json", action="store_true",
                    help="Emit JSON instead of the text report")
    args = ap.parse_args(argv)

    db = args.db or _default_db()
    if not Path(db).exists():
        raise SystemExit(f"no database at {db}")
    try:
        metrics = compute_metrics(
            db, days=args.days, seed=args.seed,
            since=parse_bound(args.since) if args.since else None,
            until=parse_bound(args.until, end=True) if args.until else None,
            exclude=tuple(args.exclude_identity), timeline=args.timeline)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    print(json.dumps(metrics, indent=2) if args.json else render(metrics))


if __name__ == "__main__":
    main()
