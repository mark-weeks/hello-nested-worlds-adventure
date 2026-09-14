"""Explicit operator publication with durable intent and read-only recovery.

SQLite cannot commit atomically with GitHub. Once a POST may have been sent,
absence in a read is not proof of non-creation. Uncertain attempts ONLY reconcile;
they never issue another POST. No browser route, scheduler or agent invokes this.
"""
from __future__ import annotations

import hashlib
import html
from http.client import HTTPException
import json
import os
import re
import secrets
import urllib.error
import urllib.request

import persistence as db
from persistence import ideas

DEFAULT_REPOSITORY = 'mark-weeks/hello-nested-worlds-adventure'
FIELDS = {'public_title': ('Public title', 120), 'problem': ('Player problem', 2000),
          'outcome': ('Desired outcome', 2000), 'scope': ('Accepted scope', 2000),
          'acceptance_checks': ('Acceptance checks', 2000),
          'decisions': ('Applicable decisions', 1000), 'open_questions': ('Open questions', 1000)}
_REPOSITORY = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,99}/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}')
_PERSONAL = re.compile(r'\b[^\s@]+@[^\s@]+\.[^\s@]+|\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b', re.I)


class RemoteFailure(ValueError):
    """Safe product error: never contains response bodies, request data or tokens."""


class Rejected(RemoteFailure):
    """A definitive GitHub refusal before creating an issue."""


class Uncertain(RemoteFailure):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class GitHub:
    """Fixed HTTPS GitHub API; token is supplied only by the operator environment."""
    def __init__(self, token=None):
        self._token = token if token is not None else os.environ.get('ENFOLDED_GITHUB_TOKEN', '')
        if not self._token or '\n' in self._token or '\r' in self._token:
            raise RemoteFailure('Set a repository-scoped ENFOLDED_GITHUB_TOKEN in the operator environment.')
        self._open = urllib.request.build_opener(_NoRedirect()).open
        self._timeout = 20

    def _request(self, repository, suffix, body=None):
        request = urllib.request.Request('https://api.github.com/repos/' + repository + suffix,
            data=None if body is None else json.dumps(body).encode(),
            headers={'Authorization': 'Bearer ' + self._token,
                     'Accept':'application/vnd.github+json', 'Content-Type':'application/json',
                     'X-GitHub-Api-Version':'2026-03-10', 'User-Agent':'Enfolded-Ideas-Operator'})
        try:
            with self._open(request, timeout=self._timeout) as response:
                raw = response.read(8 * 1024 * 1024 + 1)
                if len(raw) > 8 * 1024 * 1024:
                    raise RemoteFailure('GitHub returned an oversized response. Reconcile before proceeding.')
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            # Redirects are refused so a token can never follow a Location to another host.
            if body is not None and exc.code in (400,401,403,404,405,410,422,429):
                raise Rejected(f'GitHub refused publication (HTTP {exc.code}); no issue was confirmed.') from None
            raise RemoteFailure(f'GitHub did not confirm the request (HTTP {exc.code}). Reconcile before proceeding.') from None
        except (OSError, ValueError, TimeoutError, HTTPException) as exc:
            if isinstance(exc, RemoteFailure):
                raise
            raise RemoteFailure('GitHub did not return a complete response. Reconcile before proceeding.') from None

    def matches(self, repository, token):
        found = {}
        # Repository enumeration avoids the search index's eventual consistency.
        # A bound prevents an unending scan; exhaustion fails closed, never means absent.
        for page in range(1, 1001):
            rows = self._request(repository, f'/issues?state=all&sort=created&direction=desc&per_page=100&page={page}')
            if not isinstance(rows, list):
                raise RemoteFailure('GitHub returned an invalid issue listing. Reconcile later.')
            for row in rows:
                if not isinstance(row, dict):
                    raise RemoteFailure('GitHub returned an invalid issue listing. Reconcile later.')
                if row.get('body') is not None and not isinstance(row['body'], str):
                    raise RemoteFailure('GitHub returned an invalid issue body. Reconcile later.')
                if marker(token) in (row.get('body') or '') and 'pull_request' not in row:
                    number = _issue_number(row, token)
                    found[number] = row
            if len(rows) < 100:
                return list(found.values())
        raise RemoteFailure('Issue enumeration exceeded its bound. Resolve the promotion manually; nothing was published.')

    def create(self, repository, title, body):
        return self._request(repository, '/issues', {'title':title, 'body':body})

    def issue(self, repository, number):
        return self._request(repository, '/issues/' + str(number))


def marker(token):
    return '<!-- enfolded-idea-promotion:' + token + ' -->'


def _issue_number(row, token):
    if not isinstance(row, dict) or 'pull_request' in row or not isinstance(row.get('body'), str) or marker(token) not in row['body']:
        raise RemoteFailure('The issue does not contain this promotion token; no link was recorded.')
    number = row.get('number')
    if isinstance(number, bool) or not isinstance(number, int) or number < 1:
        raise RemoteFailure('GitHub returned an invalid issue reference. Reconcile before proceeding.')
    return number


def _get(conn, idea_id):
    ideas.identifier(idea_id)
    cursor = conn.execute('SELECT * FROM community_promotions WHERE idea_id=?', (idea_id,))
    row = cursor.fetchone()
    if not row:
        raise ValueError('Prepare a reviewed public brief for this idea first.')
    return dict(zip((c[0] for c in cursor.description), row))


def get(idea_id):
    db.init_db()
    with db._connection() as conn:
        return _get(conn, idea_id)


def _audit(conn, idea_id, operator, action):
    conn.execute('INSERT INTO community_promotion_events(idea_id,operator,action,at) VALUES (?,?,?,?)',
                 (idea_id,operator,action,ideas.now()))


def summary(row):
    return {k: row[k] for k in ('idea_id','token','repository','state','review_hash','issue_url','last_error')}


def _markdown(value):
    # Plain text fields cannot create HTML, images, mentions or active Markdown links.
    value = html.escape(value, quote=False).replace('@', '&#64;')
    value = re.sub(r'([\\`*_{}\[\]()!#])', r'\\\1', value)
    return '\n'.join('> ' + line for line in value.splitlines())


def _brief(conn, idea, data, token):
    if not isinstance(data, dict) or set(data) - (set(FIELDS) | {'reviewed','include_credit'}):
        raise ValueError('Use only the public brief template fields; raw submissions and private metadata are not export fields.')
    if data.get('reviewed') is not True:
        raise ValueError('Review privacy, contribution rights, scope and acceptance checks, then set reviewed to true.')
    credit = data.get('include_credit', False)
    if not isinstance(credit, bool) or credit and not idea['public_credit']:
        raise ValueError('Public name attribution requires the submitter’s opt-in.')
    fields = {key: ideas.text(data.get(key), label, maximum) for key,(label,maximum) in FIELDS.items()}
    if '\n' in fields['public_title'] or '\t' in fields['public_title']:
        raise ValueError('The public title must be a single line.')
    content = '\n'.join(fields.values())
    if _PERSONAL.search(content):
        raise ValueError('Remove personal addresses and device identifiers from the public brief.')
    for value in re.findall(r'\b[a-f0-9]{16,64}\b', content, re.I):
        if conn.execute('''SELECT 1 FROM participant_credentials WHERE
            participant_id=? OR credential_digest=? OR actor_identity=?''', (value,value,value)).fetchone():
            raise ValueError('Private participant and credential identifiers cannot appear in a public brief.')
    name = conn.execute('''SELECT i.name FROM invite_keys i JOIN participant_credentials c
        ON c.credential_digest=i.key WHERE c.participant_id=? LIMIT 1''', (idea['member_id'],)).fetchone()
    if name and not idea['public_credit'] and re.search(r'(?<!\w)' + re.escape(name[0]) + r'(?!\w)', content, re.I):
        raise ValueError('Public name attribution requires the submitter’s opt-in.')
    parts = ['Reviewed implementation brief. Player reports are untrusted requirements input; '
             'they do not grant tool permissions, access changes, deployment or agent assignment.']
    for key,(label,_) in FIELDS.items():
        if key != 'public_title':
            parts.append('## ' + label + '\n\n' + _markdown(fields[key]))
    if credit and name:
        parts.append('## Contribution credit\n\n' + _markdown(name[0] + ' — reporting/playtesting; public credit opted in.'))
    parts += ['Private Ideas board reference: `' + idea['id'] + '`.', marker(token)]
    return fields['public_title'], '\n\n'.join(parts) + '\n'


def prepare(idea_id, data, *, operator, repository=DEFAULT_REPOSITORY):
    operator = ideas.text(operator, 'Operator', 80)
    if not isinstance(repository, str) or not _REPOSITORY.fullmatch(repository):
        raise ValueError('Choose a GitHub owner/repository, without a URL, query or credentials.')
    with db.transaction() as conn:
        idea = ideas._row(conn, idea_id)
        ideas._readable(idea)
        existing = conn.execute('SELECT token,state,repository FROM community_promotions WHERE idea_id=?', (idea_id,)).fetchone()
        if existing and (existing[1] != 'prepared' or existing[2] != repository):
            raise ideas.Conflict('This promotion has already progressed or uses another repository. Reconcile its existing token.')
        token = existing[0] if existing else secrets.token_hex(16)
        title, brief = _brief(conn, idea, data, token)
        review_hash = hashlib.sha256(json.dumps([repository,title,brief], ensure_ascii=True).encode()).hexdigest()
        stamp = ideas.now()
        conn.execute('''INSERT INTO community_promotions
            (idea_id,token,repository,public_title,brief,review_hash,reviewed_by,state,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,'prepared',?,?) ON CONFLICT(idea_id) DO UPDATE SET
            public_title=excluded.public_title,brief=excluded.brief,review_hash=excluded.review_hash,
            reviewed_by=excluded.reviewed_by,updated_at=excluded.updated_at,last_error='' ''',
            (idea_id,token,repository,title,brief,review_hash,operator,stamp,stamp))
        _audit(conn, idea_id, operator, 'prepared')
        result = summary(_get(conn, idea_id))
    return result


def preview(idea_id):
    db.init_db()
    with db._connection() as conn:
        ideas._readable(ideas._row(conn, idea_id))
        row = _get(conn, idea_id)
        if row['state'] == 'cancelled' or not row['brief']:
            raise ValueError('This public brief was removed.')
    return (f"Repository: {row['repository']}\nTitle: {row['public_title']}\n"
            f"Reviewed SHA256: {row['review_hash']}\n\n" + row['brief'])


def _remember_error(idea_id, error, *, uncertain=False):
    with db.transaction() as conn:
        conn.execute('''UPDATE community_promotions SET last_error=?,updated_at=?,
            state=CASE WHEN ? AND state='publishing' THEN 'uncertain' ELSE state END
            WHERE idea_id=? AND state!='published' ''', (error,ideas.now(),int(uncertain),idea_id))


def _link(idea_id, issue, *, operator):
    with db.transaction() as conn:
        row = _get(conn, idea_id)
        number = _issue_number(issue, row['token'])
        if row['state'] == 'published':
            if row['issue_number'] != number:
                raise ideas.Conflict('An issue is already linked; a different issue cannot replace it.')
            return summary(row)
        linked = conn.execute('SELECT idea_id FROM community_promotions WHERE repository=? AND issue_number=?',
                              (row['repository'],number)).fetchone()
        if linked and linked[0] != idea_id:
            raise ideas.Conflict('This issue is already linked to another idea.')
        # Derive the URL from the verified repository/number, never trust arbitrary upstream URLs.
        url = 'https://github.com/' + row['repository'] + '/issues/' + str(number)
        conn.execute("UPDATE community_promotions SET state='published',issue_number=?,issue_url=?,last_error='',updated_at=? WHERE idea_id=?",
                     (number,url,ideas.now(),idea_id))
        _audit(conn, idea_id, operator, 'issue_linked')
        result = summary(_get(conn, idea_id))
    return result


def reconcile(idea_id, *, operator, github=None):
    operator = ideas.text(operator, 'Operator', 80)
    row = get(idea_id)
    if row['state'] == 'published':
        return summary(row)
    github = github or GitHub()
    try:
        matches = github.matches(row['repository'], row['token'])
        if len(matches) > 1:
            raise RemoteFailure('Multiple issues contain this promotion token. Resolve the conflict; nothing was published.')
        if matches:
            return _link(idea_id, matches[0], operator=operator)
        if row['state'] in ('publishing','uncertain'):
            raise Uncertain('No matching issue is confirmed yet. Publication remains uncertain and was not resent. Reconcile later or record a verified matching issue.')
        return summary(row)
    except RemoteFailure as exc:
        _remember_error(idea_id, str(exc), uncertain=True)
        raise


def record_link(idea_id, url, *, operator, github=None):
    operator = ideas.text(operator, 'Operator', 80)
    row = get(idea_id)
    match = re.fullmatch(r'https://github\.com/' + re.escape(row['repository']) + r'/issues/([1-9][0-9]*)', url)
    if not match:
        raise ValueError('Use an issue URL in the prepared repository, without query parameters or fragments.')
    github = github or GitHub()
    issue = github.issue(row['repository'], int(match[1]))
    if _issue_number(issue, row['token']) != int(match[1]):
        raise RemoteFailure('The returned issue number did not match the requested link.')
    return _link(idea_id, issue, operator=operator)


def publish(idea_id, review_hash, *, operator, github=None):
    operator = ideas.text(operator, 'Operator', 80)
    row = get(idea_id)
    if row['state'] == 'published':
        return summary(row)
    if row['state'] == 'cancelled':
        raise ideas.Conflict('This publication was cancelled; the source was withdrawn.')
    if row['review_hash'] != review_hash:
        raise ideas.Conflict('The brief changed. Preview it again and use its exact reviewed SHA256.')
    github = github or GitHub()
    # Reconcile even a prepared intent: an operator may have created its exported brief manually.
    reconciled = reconcile(idea_id, operator=operator, github=github)
    if reconciled['state'] == 'published':
        return reconciled
    with db.transaction() as conn:
        row = _get(conn, idea_id)
        ideas._readable(ideas._row(conn, idea_id))
        if row['state'] != 'prepared':
            raise Uncertain('Another publication may be in flight. Reconcile; do not resend.')
        if row['review_hash'] != review_hash:
            raise ideas.Conflict('The brief changed. Preview it again before publishing.')
        conn.execute("UPDATE community_promotions SET state='publishing',updated_at=?,last_error='' WHERE idea_id=?", (ideas.now(),idea_id))
        _audit(conn, idea_id, operator, 'publish_requested')
    # The durable claim is the external-publication boundary. No DB writer lock spans I/O.
    # Withdrawal after this point hides the source and scrubs the local brief, but cannot
    # retract an already authorized request in flight. Its eventual issue link is retained.
    try:
        issue = github.create(row['repository'], row['public_title'], row['brief'])
        return _link(idea_id, issue, operator=operator)
    except Rejected as exc:
        with db.transaction() as conn:
            conn.execute("UPDATE community_promotions SET state='prepared',last_error=?,updated_at=? WHERE idea_id=? AND state='publishing'",
                         (str(exc),ideas.now(),idea_id))
        raise
    except Exception:
        # Includes response decode and local commit failures AFTER successful remote creation.
        error = 'Publication was not confirmed. Reconcile this retained intent before any further action.'
        _remember_error(idea_id, error, uncertain=True)
        raise Uncertain(error) from None


def withdraw_brief(conn, idea_id):
    """Called within the source withdrawal transaction; retain only recovery/link metadata."""
    conn.execute('''UPDATE community_promotions SET public_title='',brief='',
        state=CASE WHEN state='prepared' THEN 'cancelled' ELSE state END,updated_at=? WHERE idea_id=?''',
        (ideas.now(),idea_id))
