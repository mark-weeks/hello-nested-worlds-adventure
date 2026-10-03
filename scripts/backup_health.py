"""Read-only artifact freshness check; never downloads or restores world data.

Exit 0 means a recent, nonexpired, nonempty artifact from a successful backup.yml
run on main, not that it can be restored. Check independently after run completion.
"""
import argparse
from datetime import datetime, timezone
import json
from functools import cache
from pathlib import Path
import re
import subprocess

WORKFLOW = '.github/workflows/backup.yml'
BRANCH = 'main'


def trusted_run(source, run, workflow_id):
    """Names alone are not provenance; require the API's matching run and repository."""
    if not isinstance(run, dict):
        raise ValueError('Invalid workflow run metadata.')
    repository_id = source.get('repository_id')
    return (type(repository_id) is int and repository_id > 0
            and run.get('id') == source['id']
            and run.get('workflow_id') == workflow_id
            and run.get('path') == WORKFLOW
            and run.get('event') in ('schedule', 'workflow_dispatch')
            and run.get('status') == 'completed' and run.get('conclusion') == 'success'
            and run.get('head_branch') == source.get('head_branch') == BRANCH
            and isinstance(source.get('head_sha'), str) and bool(source['head_sha'])
            and run.get('head_sha') == source['head_sha']
            and source.get('head_repository_id') == repository_id
            and run.get('repository', {}).get('id') == repository_id
            and run.get('head_repository', {}).get('id') == repository_id)


def assess(pages, *, app, workflow, run_lookup, max_age_minutes=60, now=None):
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', app):
        raise ValueError('Use the exact Fly app name.')
    if max_age_minutes <= 0:
        raise ValueError('max-age-minutes must be positive.')
    if (not isinstance(workflow, dict) or workflow.get('path') != WORKFLOW
            or type(workflow.get('id')) is not int or workflow['id'] <= 0):
        raise ValueError('Expected trusted backup workflow metadata.')
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
            name, size = artifact.get('name'), artifact.get('size_in_bytes')
            match = pattern.fullmatch(name) if isinstance(name, str) else None
            if not match or artifact.get('expired') is not False or type(size) is not int or size <= 0:
                continue
            # Snapshot start, not upload time: a slow upload cannot freshen old data.
            try:
                taken = datetime.strptime(match[1], '%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)
                expires = datetime.fromisoformat(artifact['expires_at'].replace('Z', '+00:00'))
            except (KeyError, ValueError, AttributeError, TypeError):
                continue
            if expires.tzinfo is None or expires <= now or taken > now:
                continue
            candidates.append((taken, artifact))
    # Stop at the newest trusted candidate; do not make one API request per old
    # artifact in a 90-day archive. Failed/in-progress/foreign runs cannot qualify.
    for taken, artifact in sorted(candidates, key=lambda pair: pair[0], reverse=True):
        source = artifact.get('workflow_run')
        if not isinstance(source, dict) or type(source.get('id')) is not int or source['id'] <= 0:
            continue
        if not trusted_run(source, run_lookup(source['id']), workflow['id']):
            continue
        age = (now - taken).total_seconds() / 60
        return {'status': 'fresh' if age <= max_age_minutes else 'stale', 'app': app,
                'artifact_id': artifact['id'], 'run_id': source['id'], 'branch': BRANCH,
                'snapshot_at': taken.isoformat(), 'age_minutes': round(age, 2),
                'max_age_minutes': max_age_minutes}
    return {'status': 'missing', 'app': app, 'max_age_minutes': max_age_minutes}


def github_json(endpoint, *, paginate=False):
    command = ['gh', 'api', endpoint]
    if paginate:
        command += ['--paginate', '--slurp']
    return json.loads(subprocess.run(command, check=True, capture_output=True,
                                     text=True, timeout=120).stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--repository', help='owner/repository; uses authenticated gh, read-only')
    source.add_argument('--artifacts', type=Path,
                        help='offline JSON: workflow metadata, artifact_pages, and runs')
    parser.add_argument('--app', required=True)
    parser.add_argument('--max-age-minutes', type=int, default=60)
    args = parser.parse_args()
    try:
        if args.repository:
            if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', args.repository):
                raise ValueError('Expected owner/repository.')
            root = f'repos/{args.repository}/actions'
            workflow = github_json(f'{root}/workflows/backup.yml')
            pages = github_json(f'{root}/artifacts?per_page=100', paginate=True)
            @cache
            def run_lookup(run_id):
                return github_json(f'{root}/runs/{run_id}')
        else:
            evidence = json.loads(args.artifacts.read_text())
            workflow, pages = evidence['workflow'], evidence['artifact_pages']
            runs = {run['id']: run for run in evidence['runs']}
            run_lookup = runs.__getitem__
        result = assess(pages, app=args.app, workflow=workflow, run_lookup=run_lookup,
                        max_age_minutes=args.max_age_minutes)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, subprocess.SubprocessError):
        parser.exit(2, 'Backup status unavailable: check input and GitHub read access.\n')
    print(json.dumps(result, indent=2))
    if result['status'] != 'fresh':
        parser.exit(1)


if __name__ == '__main__':
    main()
