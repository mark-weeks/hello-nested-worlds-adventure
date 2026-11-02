"""Private S3-compatible storage for off-host world backups.

Object names keep the app and the UTC snapshot-start. A validation failure uses
the unvalidated prefix; that name never satisfies the freshness check. The
client shells out to a pinned AWS CLI and talks to whatever endpoint the
operator configured. Cloudflare R2 is the documented default, not a hardcoded
host. Credentials stay in the environment and are never printed.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import urllib.parse


PREFIX = 'offhost/'
VALIDATED_ROLE = 'worlds-backup'
QUARANTINE_ROLE = 'unvalidated-worlds-backup'
_STAMP = re.compile(r'\d{8}T\d{6}Z')
_APP = re.compile(r'[a-z0-9][a-z0-9-]{0,62}')
_BUCKET = re.compile(r'[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]')
_REGION = re.compile(r'[a-z0-9][a-z0-9-]{0,31}')
_CREDENTIAL_ENV = (
    'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN',
    'AWS_SECURITY_TOKEN', 'AWS_PROFILE', 'AWS_DEFAULT_PROFILE',
)


class StoreError(RuntimeError):
    """The object store could not be used. The message contains no credential."""


def validate_app(value):
    if not isinstance(value, str) or not _APP.fullmatch(value):
        raise ValueError('Use the exact Fly app name.')


def validate_stamp(value):
    if not isinstance(value, str) or not _STAMP.fullmatch(value):
        raise ValueError('Snapshot time must be YYYYMMDDTHHMMSSZ.')
    return datetime.strptime(value, '%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)


def validate_bucket(value):
    if (not isinstance(value, str) or not _BUCKET.fullmatch(value) or '..' in value
            or value.startswith('.') or '.-' in value or '-.' in value
            or re.fullmatch(r'(?:\d{1,3}\.){3}\d{1,3}', value)):
        raise ValueError('Bucket name is malformed.')


def validate_region(value):
    if not isinstance(value, str) or not _REGION.fullmatch(value):
        raise ValueError('Region must be a short lowercase name such as auto.')


def validate_endpoint(value):
    if not isinstance(value, str) or not value or len(value) > 256 or any(ch.isspace() for ch in value):
        raise ValueError('Endpoint must be an https URL.')
    parsed = urllib.parse.urlsplit(value)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username
            or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in ('', '/')):
        raise ValueError('Endpoint must be an https URL with no credentials, path, query, or fragment.')


def validate_credential(value):
    if (not isinstance(value, str) or not value or len(value) > 256
            or any(ch.isspace() or ord(ch) < 33 or ord(ch) > 126 for ch in value)):
        raise ValueError('Credential is malformed.')


def validate_retention(value):
    if type(value) is not int or value < 1 or value > 3650:
        raise ValueError('Retention days must be an integer from 1 to 3650.')


def gate_problems(env):
    """Shape checks for values that are present. Missing values are not errors here."""
    problems = []
    checks = (
        ('ENFOLDED_BACKUP_S3_BUCKET', env.get('ENFOLDED_BACKUP_S3_BUCKET', ''), validate_bucket,
         'ENFOLDED_BACKUP_S3_BUCKET is malformed.'),
        ('ENFOLDED_BACKUP_S3_ENDPOINT', env.get('ENFOLDED_BACKUP_S3_ENDPOINT', ''), validate_endpoint,
         'ENFOLDED_BACKUP_S3_ENDPOINT must be an https URL with no credentials, path, query, or fragment.'),
        ('ENFOLDED_BACKUP_S3_ACCESS_KEY_ID', env.get('ENFOLDED_BACKUP_S3_ACCESS_KEY_ID', ''),
         validate_credential, 'ENFOLDED_BACKUP_S3_ACCESS_KEY_ID is malformed.'),
        ('ENFOLDED_BACKUP_S3_SECRET_ACCESS_KEY', env.get('ENFOLDED_BACKUP_S3_SECRET_ACCESS_KEY', ''),
         validate_credential, 'ENFOLDED_BACKUP_S3_SECRET_ACCESS_KEY is malformed.'),
    )
    for _name, value, check, message in checks:
        if not value:
            continue
        try:
            check(value)
        except ValueError:
            problems.append(message)
    return problems


def object_key(app, stamp, *, quarantine=False):
    validate_app(app)
    validate_stamp(stamp)
    role = QUARANTINE_ROLE if quarantine else VALIDATED_ROLE
    return f'{PREFIX}{role}-{app}-{stamp}.db'


def classify(key, app):
    """Return (role, snapshot time). Quarantine is never reported as validated."""
    if not isinstance(key, str):
        return None
    validate_app(app)
    for role in (VALIDATED_ROLE, QUARANTINE_ROLE):
        prefix = f'{PREFIX}{role}-{app}-'
        if not key.startswith(prefix) or not key.endswith('.db'):
            continue
        try:
            taken = validate_stamp(key[len(prefix):-3])
        except ValueError:
            return None
        return ('quarantine' if role == QUARANTINE_ROLE else 'validated'), taken
    return None


def page_contents(page):
    if not isinstance(page, dict):
        raise ValueError('Invalid S3 listing page.')
    if 'Contents' in page:
        contents = page['Contents']
        if not isinstance(contents, list):
            raise ValueError('Invalid S3 listing page.')
        return contents
    if page.get('KeyCount') == 0 or 'Prefix' in page or 'Name' in page:
        return []
    raise ValueError('Invalid S3 listing page.')


def iter_objects(pages):
    if isinstance(pages, dict):
        pages = [pages]
    if not isinstance(pages, list) or not pages:
        raise ValueError('Expected S3 listing pages.')
    for page in pages:
        for item in page_contents(page):
            if not isinstance(item, dict):
                raise ValueError('Invalid S3 object metadata.')
            yield item


def assess_objects(pages, *, app, max_age_minutes=60, now=None):
    """Newest validated, nonempty object. Age uses the name's snapshot-start."""
    validate_app(app)
    if type(max_age_minutes) is not int or max_age_minutes <= 0:
        raise ValueError('max-age-minutes must be positive.')
    now = now or datetime.now(timezone.utc)
    best = None
    for item in iter_objects(pages):
        classified = classify(item.get('Key'), app)
        size = item.get('Size')
        if classified is None or classified[0] != 'validated' or type(size) is not int or size <= 0:
            continue
        taken = classified[1]
        if taken > now:
            continue
        if best is None or taken > best[0]:
            best = (taken, item['Key'], size)
    if best is None:
        return {'status': 'missing', 'app': app, 'max_age_minutes': max_age_minutes}
    taken, key, size = best
    age = (now - taken).total_seconds() / 60
    return {'status': 'fresh' if age <= max_age_minutes else 'stale', 'app': app,
            'key': key, 'snapshot_at': taken.isoformat(), 'age_minutes': round(age, 2),
            'max_age_minutes': max_age_minutes, 'size_in_bytes': size}


def keys_older_than(pages, *, app, cutoff):
    """Validated and quarantine keys whose snapshot-start is at or before cutoff."""
    chosen = []
    for item in iter_objects(pages):
        classified = classify(item.get('Key'), app)
        if classified is None or classified[1] > cutoff:
            continue
        chosen.append((classified[1], item['Key']))
    return [key for _taken, key in sorted(chosen)]


def expired_keys(pages, *, app, retention_days, now=None):
    validate_retention(retention_days)
    now = now or datetime.now(timezone.utc)
    return keys_older_than(pages, app=app, cutoff=now - timedelta(days=retention_days))


def load_object_pages(path):
    evidence = json.loads(Path(path).read_text())
    if isinstance(evidence, dict) and 'object_pages' in evidence:
        pages = evidence['object_pages']
    elif isinstance(evidence, list):
        pages = evidence
    elif isinstance(evidence, dict):
        pages = [evidence]
    else:
        raise ValueError('Expected S3 listing pages.')
    if not isinstance(pages, list) or not pages:
        raise ValueError('Expected S3 listing pages.')
    for page in pages:
        page_contents(page)
    return pages


def _target(env):
    bucket = env.get('ENFOLDED_BACKUP_S3_BUCKET', '')
    endpoint = env.get('ENFOLDED_BACKUP_S3_ENDPOINT', '')
    region = env.get('ENFOLDED_BACKUP_S3_REGION', '') or 'auto'
    validate_bucket(bucket)
    validate_endpoint(endpoint)
    validate_region(region)
    return bucket, endpoint, region


def _credentials(env, purpose):
    if purpose == 'list' and (env.get('ENFOLDED_BACKUP_S3_LIST_ACCESS_KEY_ID', '')
                              or env.get('ENFOLDED_BACKUP_S3_LIST_SECRET_ACCESS_KEY', '')):
        access = env.get('ENFOLDED_BACKUP_S3_LIST_ACCESS_KEY_ID', '')
        secret = env.get('ENFOLDED_BACKUP_S3_LIST_SECRET_ACCESS_KEY', '')
        if not access or not secret:
            raise StoreError('A list-only backup credential is incomplete.')
    else:
        access = env.get('ENFOLDED_BACKUP_S3_ACCESS_KEY_ID', '')
        secret = env.get('ENFOLDED_BACKUP_S3_SECRET_ACCESS_KEY', '')
        if not access or not secret:
            raise StoreError('Bucket credentials are not configured.')
    try:
        validate_credential(access)
        validate_credential(secret)
    except ValueError as exc:
        raise StoreError('Bucket credentials are malformed.') from exc
    return access, secret


def _redact(text, secrets):
    redacted = text or ''
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, '[redacted]')
    return redacted


def run_aws(args, *, env=None, purpose='write'):
    source = os.environ if env is None else env
    bucket, endpoint, region = _target(source)
    access, secret = _credentials(source, purpose)
    child = dict(source)
    child.setdefault('PATH', os.environ.get('PATH', ''))
    for name in _CREDENTIAL_ENV:
        child.pop(name, None)
    child.update({
        'AWS_ACCESS_KEY_ID': access,
        'AWS_SECRET_ACCESS_KEY': secret,
        'AWS_DEFAULT_REGION': region,
        'AWS_EC2_METADATA_DISABLED': 'true',
        'AWS_PAGER': '',
        'AWS_REQUEST_CHECKSUM_CALCULATION': 'when_required',
        'AWS_RESPONSE_CHECKSUM_VALIDATION': 'when_required',
    })
    with tempfile.TemporaryDirectory() as directory:
        config = Path(directory) / 'config'
        config.write_text(
            '[default]\n'
            f'region = {region}\n'
            'request_checksum_calculation = when_required\n'
            'response_checksum_validation = when_required\n'
            's3 =\n'
            '    addressing_style = path\n'
        )
        child['AWS_CONFIG_FILE'] = str(config)
        child['AWS_SHARED_CREDENTIALS_FILE'] = str(Path(directory) / 'credentials')
        Path(child['AWS_SHARED_CREDENTIALS_FILE']).write_text('')
        try:
            result = subprocess.run(['aws', '--endpoint-url', endpoint, *args], env=child,
                                    check=False, capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired as exc:
            raise StoreError('Object storage command timed out.') from exc
        except OSError as exc:
            raise StoreError('AWS CLI is not available.') from exc
    if result.returncode != 0:
        detail = _redact(result.stderr, (access, secret)).strip()
        message = 'Object storage command failed.'
        if detail:
            message = f'{message}\n{detail}'
        raise StoreError(message)
    return result.stdout


def list_object_pages(env=None):
    source = os.environ if env is None else env
    bucket, _endpoint, _region = _target(source)
    pages = []
    token = None
    while len(pages) < 100:
        args = ['s3api', 'list-objects-v2', '--bucket', bucket, '--prefix', PREFIX,
                '--max-keys', '1000', '--output', 'json']
        if token:
            args += ['--continuation-token', token]
        try:
            page = json.loads(run_aws(args, env=source, purpose='list'))
        except json.JSONDecodeError as exc:
            raise StoreError('Object storage returned a response that was not JSON.') from exc
        page_contents(page)
        pages.append(page)
        if page.get('IsTruncated') is not True:
            return pages
        token = page.get('NextContinuationToken')
        if not isinstance(token, str) or not token:
            raise StoreError('Truncated listing without a continuation token.')
    raise StoreError('Object listing did not finish.')


def put_object(app, stamp, body, *, quarantine=False, env=None):
    key = object_key(app, stamp, quarantine=quarantine)
    path = Path(body)
    if not path.is_file() or path.stat().st_size <= 0:
        raise StoreError('Snapshot file is missing or empty.')
    source = os.environ if env is None else env
    bucket, _endpoint, _region = _target(source)
    run_aws(['s3api', 'put-object', '--bucket', bucket, '--key', key,
             '--body', str(path), '--output', 'json'], env=source, purpose='write')
    return key


def get_object(app, key, dest, *, env=None):
    if classify(key, app) is None:
        raise StoreError("Refusing to download a key outside this app's backup names.")
    path = Path(dest)
    if path.exists():
        raise StoreError('Refusing to overwrite an existing file.')
    source = os.environ if env is None else env
    bucket, _endpoint, _region = _target(source)
    try:
        run_aws(['s3api', 'get-object', '--bucket', bucket, '--key', key,
                 '--output', 'json', str(path)], env=source, purpose='list')
    except Exception:
        if path.exists():
            path.unlink()
        raise
    if not path.is_file() or path.stat().st_size <= 0:
        if path.exists():
            path.unlink()
        raise StoreError('Downloaded object was empty.')
    return path


def delete_object(app, key, *, env=None):
    if classify(key, app) is None:
        raise StoreError("Refusing to delete a key outside this app's backup names: " + key)
    source = os.environ if env is None else env
    bucket, _endpoint, _region = _target(source)
    run_aws(['s3api', 'delete-object', '--bucket', bucket, '--key', key, '--output', 'json'],
            env=source, purpose='write')
    return key


def _delete_many(app, keys, env):
    deleted = []
    for key in keys:
        delete_object(app, key, env=env)
        deleted.append(key)
    return deleted


def prune_objects(app, retention_days, *, env=None):
    source = os.environ if env is None else env
    return _delete_many(app, expired_keys(list_object_pages(source), app=app,
                                           retention_days=retention_days), source)


def delete_before(app, stamp, *, env=None):
    cutoff = validate_stamp(stamp)
    source = os.environ if env is None else env
    return _delete_many(app, keys_older_than(list_object_pages(source), app=app, cutoff=cutoff), source)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)

    put = commands.add_parser('put', help='upload one snapshot')
    put.add_argument('--app', required=True)
    put.add_argument('--stamp', required=True)
    put.add_argument('--body', required=True, type=Path)
    put.add_argument('--quarantine', action='store_true')

    get = commands.add_parser('get', help='download one backup object')
    get.add_argument('--app', required=True)
    get.add_argument('--key', required=True)
    get.add_argument('--dest', required=True, type=Path)

    delete = commands.add_parser('delete', help='delete one backup object')
    delete.add_argument('--app', required=True)
    delete.add_argument('--key', required=True)

    older = commands.add_parser('delete-before', help='delete this app\'s objects at or before a snapshot time')
    older.add_argument('--app', required=True)
    older.add_argument('--before', required=True)

    prune = commands.add_parser('prune', help='delete this app\'s objects past retention')
    prune.add_argument('--app', required=True)
    prune.add_argument('--retention-days', required=True, type=int)

    args = parser.parse_args()
    try:
        if args.command == 'put':
            print(put_object(args.app, args.stamp, args.body, quarantine=args.quarantine))
        elif args.command == 'get':
            print(get_object(args.app, args.key, args.dest))
        elif args.command == 'delete':
            print(delete_object(args.app, args.key))
        else:
            if args.command == 'delete-before':
                keys = delete_before(args.app, args.before)
            else:
                keys = prune_objects(args.app, args.retention_days)
            if not keys:
                print('No matching backup objects.', file=sys.stderr)
            for key in keys:
                print(key)
    except (StoreError, ValueError, OSError) as exc:
        parser.exit(1, f'{exc}\n')


if __name__ == '__main__':
    main()
