"""Private S3-compatible storage for off-host world backups.

Object names keep the app and the UTC snapshot-start. A validation failure uses
the unvalidated prefix; that name never satisfies the freshness check. The
client shells out to a pinned AWS CLI and talks to whatever endpoint the
operator configured. Cloudflare R2 is an example, not a chosen vendor, and a
30-day retention is the example used when the variable is unset. Neither is a
recorded decision. Credentials stay in the environment and are never printed.
Error text drops the endpoint, the bucket, and object keys.
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
    try:
        port = parsed.port
    except ValueError:
        raise ValueError('Endpoint must be an https URL with a valid port.') from None
    if (parsed.scheme != 'https' or not parsed.hostname or port == 0
            or parsed.netloc.endswith(':')
            or parsed.username or parsed.password or parsed.query or parsed.fragment
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


def newest_validated_key(pages, *, app, now):
    """Newest nonempty validated snapshot at or before now.

    Future stamps do not count. A missing, boolean, or non-positive ``Size``
    does not count either: health would not report that object, so prune and
    ``delete-before`` must not protect it while deleting an older good copy.
    """
    best = None
    for item in iter_objects(pages):
        classified = classify(item.get('Key'), app)
        size = item.get('Size')
        if (classified is None or classified[0] != 'validated' or classified[1] > now
                or type(size) is not int or size <= 0):
            continue
        if best is None or classified[1] > best[0]:
            best = (classified[1], item['Key'])
    return None if best is None else best[1]


def expired_keys(pages, *, app, retention_days, now=None):
    """Keys past retention, except the newest nonempty validated object.

    A quiet stretch longer than the retention period must not empty the bucket
    of the last good copy. Quarantine objects are not protected. ``delete`` of
    one named key can still remove the newest copy. ``delete-before`` keeps it.
    """
    validate_retention(retention_days)
    now = now or datetime.now(timezone.utc)
    expired = keys_older_than(pages, app=app, cutoff=now - timedelta(days=retention_days))
    keep = newest_validated_key(pages, app=app, now=now)
    if keep is None:
        return expired
    return [key for key in expired if key != keep]


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
            raise StoreError('A backup read credential is incomplete. Set both read variables or neither.')
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
    for secret in sorted((item for item in secrets if item), key=len, reverse=True):
        redacted = re.sub(re.escape(secret), '[redacted]', redacted, flags=re.I)
    return re.sub(r'offhost(?:/|%2[Ff])\S+', '[redacted]', redacted)


def _command_secrets(args, bucket, endpoint, access, secret):
    host = urllib.parse.urlsplit(endpoint).hostname or ''
    account = host.split('.')[0] if host else ''
    found = [access, secret, endpoint, host, account, bucket]
    for index, arg in enumerate(args):
        if arg in ('--key', '--prefix') and index + 1 < len(args):
            found.append(args[index + 1])
        elif arg == '--delete' and index + 1 < len(args):
            found.append(args[index + 1])
            try:
                payload = json.loads(args[index + 1])
            except json.JSONDecodeError:
                continue
            for item in payload.get('Objects', []):
                if isinstance(item, dict) and isinstance(item.get('Key'), str):
                    found.append(item['Key'])
    return found


def run_aws(args, *, env=None, purpose='write'):
    source = os.environ if env is None else env
    bucket, endpoint, region = _target(source)
    access, secret = _credentials(source, purpose)
    # AWS_FAKE_* is how the tests hand a page fixture to the stand-in CLI.
    # Every other AWS_* value belongs to the operator's shell. AWS CLI v2
    # prefers AWS_REGION over AWS_DEFAULT_REGION, so the configured region
    # has to be set, not merely left for the inherited one.
    child = {key: value for key, value in source.items()
             if not key.startswith('AWS_') or key.startswith('AWS_FAKE_')}
    child.setdefault('PATH', os.environ.get('PATH', ''))
    child.update({
        'AWS_ACCESS_KEY_ID': access,
        'AWS_SECRET_ACCESS_KEY': secret,
        'AWS_REGION': region,
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
                                    check=False, capture_output=True, text=True,
                                    timeout=_command_timeout(args, source))
        except subprocess.TimeoutExpired as exc:
            raise StoreError('Object storage command timed out.') from exc
        except OSError as exc:
            raise StoreError('AWS CLI is not available.') from exc
    if result.returncode != 0:
        detail = _redact(result.stderr, _command_secrets(args, bucket, endpoint, access, secret)).strip()
        message = 'Object storage command failed.'
        if detail:
            message = f'{message}\n{detail}'
        raise StoreError(message)
    return result.stdout


# 3,650 days at 48 snapshots a day is 175,200 keys. One thousand keys per page
# needs 176 pages for a single app prefix. 250 leaves margin past the old
# 100-page stop, which failed closed forever once a bucket crossed 100,000 keys.
MAX_LIST_PAGES = 250
_DELETE_BATCH = 1000


def app_prefixes(app):
    validate_app(app)
    return (
        f'{PREFIX}{VALIDATED_ROLE}-{app}-',
        f'{PREFIX}{QUARANTINE_ROLE}-{app}-',
    )


def list_object_pages(env=None, *, app, max_pages=MAX_LIST_PAGES):
    source = os.environ if env is None else env
    bucket, _endpoint, _region = _target(source)
    if type(max_pages) is not int or max_pages < 1:
        raise ValueError('max_pages must be a positive integer.')
    pages = []
    for prefix in app_prefixes(app):
        token = None
        for _page_number in range(max_pages):
            args = ['s3api', 'list-objects-v2', '--bucket', bucket, '--prefix', prefix,
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
                break
            token = page.get('NextContinuationToken')
            if not isinstance(token, str) or not token:
                raise StoreError('Truncated listing without a continuation token.')
        else:
            raise StoreError('Object listing did not finish.')
    return pages


def _command_timeout(args, env):
    """List and delete stay at 120 seconds. A download or upload is longer.

    ``ENFOLDED_BACKUP_S3_TIMEOUT_SECONDS`` overrides the transfer limit.
    ``0`` or ``none`` waits until the process ends. The workflow job still
    has its own 20-minute limit.
    """
    transfer = 'get-object' in args or 'put-object' in args
    if not transfer:
        return 120
    raw = str(env.get('ENFOLDED_BACKUP_S3_TIMEOUT_SECONDS', '') or '').strip()
    if raw == '':
        return 3600
    if raw.lower() == 'none' or raw == '0':
        return None
    if not raw.isdigit() or int(raw) > 86400:
        raise StoreError(
            'ENFOLDED_BACKUP_S3_TIMEOUT_SECONDS must be a whole number of seconds '
            'up to 86400, 0 for no limit, or unset.')
    return int(raw)


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
    temporary = path.with_name(path.name + '.partial')
    if temporary.exists():
        raise StoreError('Refusing to overwrite an existing file.')
    descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    try:
        run_aws(['s3api', 'get-object', '--bucket', bucket, '--key', key,
                 '--output', 'json', str(temporary)], env=source, purpose='write')
        if not temporary.is_file() or temporary.stat().st_size <= 0:
            raise StoreError('Downloaded object was empty.')
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    except BaseException:
        if temporary.exists():
            temporary.unlink()
        raise
    return path


def delete_object(app, key, *, env=None):
    if classify(key, app) is None:
        raise StoreError("Refusing to delete a key outside this app's backup names.")
    return _delete_many(app, [key], os.environ if env is None else env)[0]


def _delete_many(app, keys, env):
    if not keys:
        return []
    bucket, _endpoint, _region = _target(env)
    deleted = []
    for start in range(0, len(keys), _DELETE_BATCH):
        batch = list(keys[start:start + _DELETE_BATCH])
        for key in batch:
            if classify(key, app) is None:
                raise StoreError("Refusing to delete a key outside this app's backup names.")
        payload = json.dumps({'Objects': [{'Key': key} for key in batch], 'Quiet': True},
                             separators=(',', ':'))
        stdout = run_aws(['s3api', 'delete-objects', '--bucket', bucket, '--delete', payload,
                          '--output', 'json'], env=env, purpose='write')
        try:
            body = json.loads(stdout or '{}')
        except json.JSONDecodeError as exc:
            raise StoreError('Object storage returned a response that was not JSON.') from exc
        if not isinstance(body, dict):
            raise StoreError('Object storage returned an unexpected delete response.')
        errors = body.get('Errors') or []
        if errors:
            raise StoreError(f'Object storage refused to delete {len(errors)} objects.')
        deleted.extend(batch)
    return deleted


def prune_objects(app, retention_days, *, env=None, now=None):
    source = os.environ if env is None else env
    pages = list_object_pages(source, app=app)
    return _delete_many(app, expired_keys(pages, app=app, retention_days=retention_days, now=now), source)


def delete_before(app, stamp, *, env=None, now=None, dry_run=False, after=None):
    """Delete this app's objects at or before ``stamp``, keeping the newest good copy.

    A future cutoff is refused. ``--after`` limits the window to snapshots that
    can contain text written at that time. ``dry_run`` lists the keys and does
    not delete. The newest nonempty validated object is never included, so the
    command cannot empty the bucket of its last good copy.
    """
    cutoff = validate_stamp(stamp)
    now = now or datetime.now(timezone.utc)
    if cutoff > now:
        raise StoreError('Refusing a cutoff in the future.')
    after_time = validate_stamp(after) if after else None
    if after_time is not None and after_time > cutoff:
        raise StoreError('The lower bound is after the cutoff.')
    source = os.environ if env is None else env
    pages = list_object_pages(source, app=app)
    keys = keys_older_than(pages, app=app, cutoff=cutoff)
    if after_time is not None:
        keys = [key for key in keys if classify(key, app)[1] >= after_time]
    keep = newest_validated_key(pages, app=app, now=now)
    if keep is not None:
        keys = [key for key in keys if key != keep]
    if dry_run:
        return keys
    return _delete_many(app, keys, source)


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
    older.add_argument('--after', help='also require the snapshot time to be at or after this stamp')
    older.add_argument('--dry-run', action='store_true')

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
                keys = delete_before(args.app, args.before, dry_run=args.dry_run, after=args.after)
            else:
                keys = prune_objects(args.app, args.retention_days)
            if not keys:
                print('No matching backup objects.', file=sys.stderr)
            elif args.command == 'delete-before' and args.dry_run:
                print('Dry run: nothing was deleted.', file=sys.stderr)
            for key in keys:
                print(key)
    except (StoreError, ValueError, OSError) as exc:
        parser.exit(1, f'{exc}\n')


if __name__ == '__main__':
    main()
