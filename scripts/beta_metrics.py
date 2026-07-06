#!/usr/bin/env python3
"""Beta health metrics, read straight from the chronicle.

The pre-mortem's cheapest prevention: make "did the beta work?" a number
instead of a feeling. The chronicle already records every event with a
durable actor_identity, so this script needs no instrumentation, no
third-party analytics, and no network — it answers the launch questions
from the world's own memory:

  * how many humans visited in the window, and how many CAME BACK
    (active on two or more distinct days — the single most honest
    beta-success signal for a contemplative world)
  * how much they actually did: conversations with places and agents,
    puzzle attempts and solves, scale verbs, chat
  * where they went (top nodes by human activity)
  * whether the world itself is alive (total chronicle size, first event)

Run against the live DB (read-only connection, safe alongside the
server), or against any backup file:

  python scripts/beta_metrics.py                     # live DB, last 7 days
  python scripts/beta_metrics.py --days 1            # launch-day check
  python scripts/beta_metrics.py --db offhost.db     # from a backup
  python scripts/beta_metrics.py --json              # machine-readable
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

# Make the repo importable when run as `python scripts/beta_metrics.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Event types a human can author. The ambient cast writes SCALE_ACT and
# puzzle rows too, so human-ness is (human type) AND (identity present)
# AND (identity is not a cast regular's name).
_HUMAN_TYPES = (
    "PLAYER_JOIN", "PLAYER_MOVE", "PLAYER_LEAVE", "PLAYER_CHAT",
    "PLAYER_SPEAK", "AGENT_VOICE", "PUZZLE_ATTEMPT", "PUZZLE_SOLVED",
    "PUZZLE_FAILED", "SCALE_ACT",
)

_CONVERSATION_TYPES = ("PLAYER_SPEAK", "AGENT_VOICE")


def _default_db() -> Path:
    import persistence
    return persistence._DB_PATH


def _cast_names() -> tuple[str, ...]:
    from consciousness import WANDERER_CAST
    return tuple(WANDERER_CAST)


def _connect_ro(db_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


def compute_metrics(db_path: Path, days: int = 7,
                    seed: int | None = None) -> dict:
    cast = _cast_names()
    conn = _connect_ro(Path(db_path))
    try:
        type_ph = ",".join("?" for _ in _HUMAN_TYPES)
        cast_ph = ",".join("?" for _ in cast)
        human_where = (
            f"mutation_type IN ({type_ph}) "
            f"AND actor_identity IS NOT NULL "
            f"AND actor_identity NOT IN ({cast_ph}) "
            f"AND recorded_at >= datetime('now', ?)"
        )
        args: list = [*_HUMAN_TYPES, *cast, f"-{int(days)} days"]
        if seed is not None:
            human_where += " AND world_seed = ?"
            args.append(seed)

        def q(sql: str, extra: tuple = ()):
            return conn.execute(sql, (*args, *extra)).fetchall()

        visitors = q(f"""SELECT actor_identity, COUNT(*),
                                COUNT(DISTINCT date(recorded_at))
                         FROM world_mutations WHERE {human_where}
                         GROUP BY actor_identity""")
        by_type = dict(q(f"""SELECT mutation_type, COUNT(*)
                             FROM world_mutations WHERE {human_where}
                             GROUP BY mutation_type"""))
        top_nodes = q(f"""SELECT node_name, COUNT(*) AS n
                          FROM world_mutations WHERE {human_where}
                          GROUP BY node_name ORDER BY n DESC LIMIT 10""")

        total_rows = conn.execute(
            "SELECT COUNT(*) FROM world_mutations").fetchone()[0]
        first_at = conn.execute(
            "SELECT MIN(recorded_at) FROM world_mutations").fetchone()[0]

        n_visitors = len(visitors)
        returning = sum(1 for _, _, d in visitors if d >= 2)
        conversations = sum(by_type.get(t, 0) for t in _CONVERSATION_TYPES)
        return {
            "window_days": days,
            "seed": seed,
            "visitors": n_visitors,
            "returning_visitors": returning,
            "return_rate": round(returning / n_visitors, 3) if n_visitors else None,
            "events_per_visitor": (
                round(sum(c for _, c, _ in visitors) / n_visitors, 1)
                if n_visitors else None),
            "conversations": conversations,
            "conversations_per_visitor": (
                round(conversations / n_visitors, 1) if n_visitors else None),
            "puzzle_attempts": by_type.get("PUZZLE_ATTEMPT", 0),
            "puzzle_solves": by_type.get("PUZZLE_SOLVED", 0),
            "puzzle_failures": by_type.get("PUZZLE_FAILED", 0),
            "scale_acts": by_type.get("SCALE_ACT", 0),
            "chat_lines": by_type.get("PLAYER_CHAT", 0),
            "events_by_type": by_type,
            "top_nodes": [{"node": n, "events": c} for n, c in top_nodes],
            "chronicle_total_rows": total_rows,
            "chronicle_first_event": first_at,
        }
    finally:
        conn.close()


def render(m: dict) -> str:
    scope = f"world {m['seed']}" if m["seed"] is not None else "all worlds"
    lines = [
        f"Beta health — last {m['window_days']} day(s), {scope}",
        "=" * 56,
        f"visitors:            {m['visitors']}",
        f"returning (2+ days): {m['returning_visitors']}"
        + (f"  ({m['return_rate']:.0%})" if m["return_rate"] is not None else ""),
        f"events/visitor:      {m['events_per_visitor'] or 0}",
        "",
        f"conversations:       {m['conversations']}"
        + (f"  ({m['conversations_per_visitor']}/visitor)"
           if m["conversations_per_visitor"] is not None else ""),
        f"puzzle attempts:     {m['puzzle_attempts']}"
        f"  (solved {m['puzzle_solves']}, failed {m['puzzle_failures']})",
        f"scale verbs:         {m['scale_acts']}",
        f"chat lines:          {m['chat_lines']}",
    ]
    if m["top_nodes"]:
        lines += ["", "most-visited ground:"]
        lines += [f"  {t['events']:>5}  {t['node']}" for t in m["top_nodes"]]
    lines += [
        "",
        f"chronicle: {m['chronicle_total_rows']} rows total, first event "
        f"{m['chronicle_first_event'] or '(none yet)'}",
    ]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", type=Path, default=None,
                    help="Database file (default: the live DB)")
    ap.add_argument("--days", type=int, default=7,
                    help="Window in days (default 7)")
    ap.add_argument("--seed", type=int, default=None,
                    help="Restrict to one world")
    ap.add_argument("--json", action="store_true",
                    help="Emit JSON instead of the text report")
    args = ap.parse_args()

    db = args.db or _default_db()
    if not Path(db).exists():
        raise SystemExit(f"no database at {db}")
    metrics = compute_metrics(db, days=args.days, seed=args.seed)
    print(json.dumps(metrics, indent=2) if args.json else render(metrics))


if __name__ == "__main__":
    main()
