"""Read-only schema probes shared by startup and ``scripts/deploy.sh``.

Stdlib only. The deploy script base64-encodes this file and execs it on
the running machine (applied version) and, over SSH, inside a candidate
image (known version). That encoded source does not import the rest of
the package, so an image built before this module existed can still be
probed. Importing it does not open a database. Executing it prints one
sentinel line and nothing else on stdout.

This is the one filename rule. A migration is ``NNNN_name.sql``. Anything
else in the directory is ignored.
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

DEFAULT_DB = "/data/.nested-worlds/worlds.db"
DEFAULT_MIGRATIONS = "/app/persistence/migrations"

APPLIED_SENTINEL = "ENFOLDED_SCHEMA_APPLIED"
KNOWN_SENTINEL = "ENFOLDED_SCHEMA_KNOWN"


def migration_files(root: Path) -> list[tuple[int, Path]]:
    """Well-named migration files under ``root``, sorted by filename."""
    if not root.is_dir():
        return []
    found: list[tuple[int, Path]] = []
    for path in sorted(root.glob("*.sql")):
        head, _, _ = path.name.partition("_")
        try:
            version = int(head)
        except ValueError:
            continue
        found.append((version, path))
    return found


def migration_versions(root: Path) -> list[int]:
    """Versions of well-named migration files under ``root``, sorted."""
    return [version for version, _path in migration_files(root)]


def known_version(root: Path) -> int | None:
    """Highest migration file in ``root``, or None when the image ships none."""
    versions = migration_versions(root)
    if not versions:
        return None
    return max(versions)


def applied_version(db: Path) -> int | None:
    """Highest applied schema_version, or None when it cannot be read.

    Opens the file read-only and does not create it. A missing file, a
    missing table, or an empty table is None. Other SQLite errors propagate.
    """
    if not db.exists():
        return None
    uri = f"{db.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        conn.execute("PRAGMA query_only=ON")
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_version'"
        ).fetchone()
        if not exists:
            return None
        row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
    finally:
        conn.close()
    if row is None or row[0] is None:
        return None
    return int(row[0])


def main() -> int:
    mode = os.environ.get("ENFOLDED_SCHEMA_PROBE", "").strip()
    if mode == "applied":
        db = Path(os.environ.get("ENFOLDED_SCHEMA_DB", DEFAULT_DB))
        try:
            version = applied_version(db)
        except sqlite3.Error as exc:
            sys.stderr.write(f"schema probe: cannot read chronicle: {exc}\n")
            return 1
        if version is None:
            sys.stderr.write(
                "schema probe: chronicle has no schema_version "
                f"({db})\n"
            )
            return 1
        print(f"{APPLIED_SENTINEL}={version}")
        return 0
    if mode == "known":
        root = Path(os.environ.get("ENFOLDED_MIGRATIONS_DIR", DEFAULT_MIGRATIONS))
        version = known_version(root)
        if version is None:
            sys.stderr.write(
                f"schema probe: no migrations in {root}\n"
            )
            return 1
        print(f"{KNOWN_SENTINEL}={version}")
        return 0
    sys.stderr.write(
        "schema probe: set ENFOLDED_SCHEMA_PROBE to applied or known\n"
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
