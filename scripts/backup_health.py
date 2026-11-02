"""Read-only freshness check of the newest validated off-host object.

Exit 0 means a nonempty validated object for this app whose snapshot-start is
inside the age limit. It does not download the database or prove a restore.
Quarantine names never qualify. Age comes from the object name, not from
LastModified, so a slow upload cannot freshen an old snapshot. Run it
independently of backup.yml: a run cannot certify its own conclusion, and it
cannot see that the schedule has stopped.
"""
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.backup_store import StoreError, assess_objects, list_object_pages, load_object_pages


def assess(pages, *, app, max_age_minutes=60, now=None):
    return assess_objects(pages, app=app, max_age_minutes=max_age_minutes, now=now)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--objects', type=Path,
                        help='offline JSON: one ListObjectsV2 page, a list of pages, or {"object_pages": [...]}')
    parser.add_argument('--app', required=True)
    parser.add_argument('--max-age-minutes', type=int, default=60)
    args = parser.parse_args()
    try:
        if args.objects:
            pages = load_object_pages(args.objects)
        else:
            pages = list_object_pages(os.environ, app=args.app)
        result = assess(pages, app=args.app, max_age_minutes=args.max_age_minutes)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, StoreError):
        parser.exit(2, 'Backup status unavailable: check input and bucket read access.\n')
    print(json.dumps(result, indent=2))
    if result['status'] != 'fresh':
        parser.exit(1)


if __name__ == '__main__':
    main()
