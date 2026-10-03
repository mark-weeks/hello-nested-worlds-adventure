"""Read-only artifact freshness check; never downloads or restores world data.

Exit 0 means a nonexpired, nonempty backup artifact is recent enough, not that it
can be restored. Run from an independent scheduler to detect missed workflow runs.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess


def assess(pages, *, app, max_age_minutes=60, now=None):
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', app):
        raise ValueError('Use the exact Fly app name.')
    if max_age_minutes <= 0:
        raise ValueError('max-age-minutes must be positive.')
    now = now or datetime.now(timezone.utc)
    if isinstance(pages, dict):
        pages = [pages]
    if not isinstance(pages, list) or not pages:
        raise ValueError('Expected GitHub artifact response pages.')
    pattern = re.compile(r'worlds-backup-' + re.escape(app) + r'-(\d{8}T\d{6}Z)')
    candidates = []
    for page in pages:
        if not isinstance(page, dict) or not isinstance(page.get('artifacts'), list):
            raise ValueError('Invalid GitHub artifact response.')
        for artifact in page['artifacts']:
            if not isinstance(artifact, dict):
                raise ValueError('Invalid artifact metadata.')
            match = pattern.fullmatch(artifact.get('name', ''))
            if not match or artifact.get('expired') is not False or artifact.get('size_in_bytes', 0) <= 0:
                continue
            # Snapshot start, not upload time: a slow upload cannot freshen old data.
            try:
                taken = datetime.strptime(match[1], '%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)
                expires = datetime.fromisoformat(artifact['expires_at'].replace('Z', '+00:00'))
            except (KeyError, ValueError):
                continue
            if expires.tzinfo is None or expires <= now or taken > now:
                continue
            candidates.append((taken, artifact))
    if not candidates:
        return {'status': 'missing', 'app': app, 'max_age_minutes': max_age_minutes}
    taken, artifact = max(candidates, key=lambda pair: pair[0])
    age = (now - taken).total_seconds() / 60
    return {'status': 'fresh' if age <= max_age_minutes else 'stale', 'app': app,
            'artifact_id': artifact['id'], 'snapshot_at': taken.isoformat(),
            'age_minutes': round(age, 2), 'max_age_minutes': max_age_minutes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--repository', help='owner/repository; uses authenticated gh, read-only')
    source.add_argument('--artifacts', type=Path, help='saved GitHub artifact JSON, for offline checks')
    parser.add_argument('--app', required=True)
    parser.add_argument('--max-age-minutes', type=int, default=60)
    args = parser.parse_args()
    try:
        if args.repository:
            if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', args.repository):
                raise ValueError('Expected owner/repository.')
            raw = subprocess.run(
                ['gh', 'api', f'repos/{args.repository}/actions/artifacts?per_page=100',
                 '--paginate', '--slurp'], check=True, capture_output=True, text=True,
                timeout=120).stdout
        else:
            raw = args.artifacts.read_text()
        result = assess(json.loads(raw), app=args.app, max_age_minutes=args.max_age_minutes)
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError):
        parser.exit(2, 'Backup status unavailable: check input and GitHub read access.\n')
    print(json.dumps(result, indent=2))
    if result['status'] != 'fresh':
        parser.exit(1)


if __name__ == '__main__':
    main()
