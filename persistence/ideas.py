"""Private community operations. No world, puzzle, chronicle or agent writes."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import time

import persistence as db
from persistence import participants

STATUSES = {
    'considering': 'Under consideration', 'planned': 'Planned',
    'in_progress': 'In progress', 'implemented': 'Implemented — awaiting merge',
    'merged': 'Merged — awaiting release', 'available': 'Available to play',
    'deferred': 'Deferred', 'declined': 'Declined', 'duplicate': 'Duplicate',
}
HOUR = 3600 * 1_000_000
DAY = 24 * HOUR
PAGE_LIFETIME = HOUR // 4
SUBMISSIONS_PER_DAY = 5
VOTES_PER_HOUR = 60
IP_WRITES_PER_HOUR = 300
_SECRET = re.compile(r'nw[r]?_[A-Za-z0-9_-]+|gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+|[?&](?:key|invite|token)=[^\s]+', re.I)
_ID = re.compile(r'[a-f0-9]{32}')
_REQUEST = re.compile(r'[A-Za-z0-9_-]{8,80}')


class Missing(ValueError):
    def __init__(self):
        super().__init__('That idea is unavailable.')


class Conflict(ValueError):
    pass


class Limited(ValueError):
    pass


def now():
    return time.time_ns() // 1000


def identifier(value):
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError('Choose a valid idea link.')
    return value


def text(value, label, maximum, *, empty=False):
    if not isinstance(value, str) or len(value) > maximum or (not empty and not value.strip()):
        raise ValueError(f'{label} must contain {"0" if empty else "1"}–{maximum:,} characters.')
    if any(ord(c) < 32 and c not in '\n\t' for c in value) or _SECRET.search(value):
        raise ValueError('Remove credentials, invite links and control characters before saving.')
    return value.strip()


def _secret(conn):
    conn.execute('INSERT OR IGNORE INTO community_settings VALUES (?,?)', ('signing', secrets.token_hex(32)))
    return conn.execute('SELECT value FROM community_settings WHERE key=?', ('signing',)).fetchone()[0].encode()


def _key():
    db.init_db()
    with db._connection() as conn:
        row = conn.execute("SELECT value FROM community_settings WHERE key='signing'").fetchone()
    if row:
        return row[0].encode()
    with db.transaction() as conn:
        return _secret(conn)


def charge_ip(ip):
    """Independent of success; persistent and shared across server processes."""
    with db.transaction() as conn:
        stamp = now()
        digest = hmac.new(_secret(conn), ip.encode(), hashlib.sha256).hexdigest()
        conn.execute('DELETE FROM community_ip_writes WHERE at<?', (stamp - HOUR,))
        if conn.execute('SELECT count(*) FROM community_ip_writes WHERE ip_hash=?', (digest,)).fetchone()[0] >= IP_WRITES_PER_HOUR:
            raise Limited('Too many Ideas requests from this connection. Please try again later.')
        conn.execute('INSERT INTO community_ip_writes VALUES (?,?)', (digest, stamp))


def _row(conn, idea_id):
    identifier(idea_id)
    cursor = conn.execute('SELECT * FROM community_ideas WHERE id=?', (idea_id,))
    row = cursor.fetchone()
    if not row:
        raise Missing()
    return dict(zip((column[0] for column in cursor.description), row))


def _readable(row):
    if row['visibility'] != 'visible':
        raise Missing()


def _public(conn, row, me, *, detail=False):
    name = conn.execute('''SELECT i.name FROM invite_keys i JOIN participant_credentials c
        ON c.credential_digest=i.key WHERE c.participant_id=? ORDER BY i.revoked_at IS NULL DESC LIMIT 1''',
        (row['member_id'],)).fetchone()
    count, supported = conn.execute('''SELECT count(*), coalesce(max(member_id=?),0)
        FROM community_votes WHERE idea_id=?''', (me['id'], row['id'])).fetchone()
    result = {k: row[k] for k in ('id','title','status','created_at','updated_at')}
    result.update(status_label=STATUSES[row['status']], author=name[0] if name else 'Former player',
                  votes=count, supported=bool(supported), own=row['member_id'] == me['id'])
    link = conn.execute("SELECT issue_url FROM community_promotions WHERE idea_id=? AND state='published'", (row['id'],)).fetchone()
    result['issue_url'] = link[0] if link else None
    if detail:
        result.update(description=row['description'], response=row['response'], availability=row['availability'])
        target = conn.execute("SELECT id FROM community_ideas WHERE id=? AND visibility='visible'", (row['duplicate_id'],)).fetchone()
        result['duplicate_id'] = target[0] if target else None
        # Operator identities and internal visibility transitions never enter player data.
        result['decisions'] = [dict(zip(('status','explanation','at'), d)) for d in conn.execute('''
            SELECT status,explanation,at FROM community_decisions
            WHERE idea_id=? AND visibility='visible' ORDER BY id DESC LIMIT 50''', (row['id'],))]
        result['public_credit'] = bool(row['public_credit']) if result['own'] else None
    return result


def detail(key, idea_id):
    db.init_db()
    with db._connection() as conn:
        conn.execute('BEGIN')
        me = participants.identify(key)
        row = _row(conn, idea_id)
        _readable(row)
        return {'idea': _public(conn, row, me, detail=True)}


def submit(key, data):
    title = text(data.get('title'), 'Title', 120)
    description = text(data.get('description'), 'Description', 2000)
    request = data.get('request_id')
    credit = data.get('public_credit', False)
    if not isinstance(request, str) or not _REQUEST.fullmatch(request):
        raise ValueError('A stable submission identifier is required. Reload the page and try again.')
    if not isinstance(credit, bool):
        raise ValueError('Choose whether to receive public credit.')
    fingerprint = hashlib.sha256(json.dumps([title, description, credit], ensure_ascii=True).encode()).hexdigest()
    with db.transaction() as conn:
        me = participants.identify(key)
        existing = conn.execute('SELECT id,request_hash,visibility FROM community_ideas WHERE member_id=? AND request_id=?',
                                (me['id'], request)).fetchone()
        if existing:
            if existing[1] != fingerprint:
                raise Conflict('This submission identifier was already used for a different draft.')
            return {'id': existing[0], 'submitted': True, 'visible': existing[2] == 'visible'}
        stamp = now()
        count = conn.execute('SELECT count(*) FROM community_ideas WHERE member_id=? AND created_at>?',
                             (me['id'], stamp - DAY)).fetchone()[0]
        if count >= SUBMISSIONS_PER_DAY:
            raise Limited('You can share 5 new ideas in 24 hours. Please return later or support an existing idea.')
        # Persistent community text has a local-only screen. Ambiguous text is reviewed by operators.
        from server.moderation import _local_tier
        if _local_tier(title + '\n' + description) == 'block':
            raise ValueError('Please revise the idea to keep the board respectful.')
        idea_id = secrets.token_hex(16)
        conn.execute('''INSERT INTO community_ideas
            (id,member_id,request_id,request_hash,title,description,public_credit,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?)''', (idea_id,me['id'],request,fingerprint,title,description,int(credit),stamp,stamp))
    return {'id': idea_id, 'submitted': True, 'visible': True}


def vote(key, idea_id, supported):
    identifier(idea_id)
    if not isinstance(supported, bool):
        raise ValueError('Support must be true or false.')
    with db.transaction() as conn:
        me = participants.identify(key)
        row = _row(conn, idea_id)
        _readable(row)
        present = conn.execute('SELECT 1 FROM community_votes WHERE idea_id=? AND member_id=?',
                               (idea_id, me['id'])).fetchone() is not None
        if present != supported:
            stamp = now()
            # IDs are a commit-order cursor, retained across expiry of the event rows.
            maximum = conn.execute('SELECT coalesce(max(id),0) FROM community_vote_events').fetchone()[0]
            sequence = conn.execute("SELECT value FROM community_settings WHERE key='vote_sequence'").fetchone()
            revision = max(maximum, int(sequence[0]) if sequence else 0) + 1
            conn.execute('DELETE FROM community_vote_events WHERE at<?', (stamp - DAY,))
            count = conn.execute('SELECT count(*) FROM community_vote_events WHERE member_id=? AND at>?',
                                 (me['id'], stamp - HOUR)).fetchone()[0]
            if count >= VOTES_PER_HOUR:
                raise Limited('You can change support 60 times per hour. Please try again later.')
            if supported:
                conn.execute('INSERT INTO community_votes VALUES (?,?)', (idea_id, me['id']))
            else:
                conn.execute('DELETE FROM community_votes WHERE idea_id=? AND member_id=?', (idea_id, me['id']))
            conn.execute("INSERT OR REPLACE INTO community_settings VALUES ('vote_sequence',?)", (str(revision),))
            conn.execute('INSERT INTO community_vote_events(id,idea_id,member_id,delta,at) VALUES (?,?,?,?,?)',
                         (revision, idea_id, me['id'], 1 if supported else -1, stamp))
        result = {'idea': _public(conn, row, me)}
    return result


def _withdraw(conn, row, operator, explanation):
    from server.idea_promotion import withdraw_brief
    withdraw_brief(conn, row['id'])
    stamp = now()
    conn.execute("""UPDATE community_ideas SET title='',description='',public_credit=0,
        response='',availability='',visibility='withdrawn',updated_at=? WHERE id=?""", (stamp, row['id']))
    conn.execute('DELETE FROM community_votes WHERE idea_id=?', (row['id'],))
    # Preserve hourly limits without retaining the idea's voter association.
    conn.execute('UPDATE community_vote_events SET idea_id=NULL,delta=0 WHERE idea_id=?', (row['id'],))
    conn.execute('INSERT INTO community_decisions(idea_id,operator,status,visibility,explanation,at) VALUES (?,?,?,?,?,?)',
                 (row['id'], operator, row['status'], 'withdrawn', explanation, stamp))


def withdraw(key, idea_id):
    with db.transaction() as conn:
        me = participants.identify(key)
        row = _row(conn, idea_id)
        if row['member_id'] != me['id']:
            raise Missing()
        if row['visibility'] != 'withdrawn':
            _withdraw(conn, row, 'submitter', 'Withdrawn by the submitter; original content removed.')
    return {'withdrawn': True, 'id': idea_id}


def _cursor(payload, me, secret):
    raw = json.dumps(payload, separators=(',', ':')).encode()
    sig = hmac.new(secret, me['id'].encode() + raw, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(raw + sig).decode().rstrip('=')


def listing(key, *, sort='recent', q='', limit=20, cursor=''):
    if sort not in ('recent', 'supported', 'own'):
        raise ValueError('Choose recent, most supported or your submissions.')
    q = text(q, 'Search', 120, empty=True)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 50:
        raise ValueError('Choose a page size between 1 and 50.')
    if not isinstance(cursor, str) or len(cursor) > 1000:
        raise ValueError('This page link is invalid. Start again from recent ideas.')
    secret = _key()
    with db._connection() as conn:
        conn.execute('BEGIN')
        me = participants.identify(key)
        stamp = now()
        query_hash = hashlib.sha256((sort + '\0' + q).encode()).hexdigest()[:16]
        if cursor:
            try:
                raw = base64.urlsafe_b64decode(cursor + '=' * (-len(cursor) % 4))
                payload, sig = raw[:-32], raw[-32:]
                expected = hmac.new(secret, me['id'].encode() + payload, hashlib.sha256).digest()
                if not hmac.compare_digest(sig, expected):
                    raise ValueError
                asof, ceiling, vote_ceiling, score, last, query = json.loads(payload)
                if query != query_hash or asof > stamp or stamp - asof > PAGE_LIFETIME:
                    raise ValueError
            except (ValueError, TypeError, json.JSONDecodeError):
                raise ValueError('This page link expired or changed. Start again from recent ideas.') from None
        else:
            asof, ceiling = stamp, conn.execute('SELECT coalesce(max(seq),0) FROM community_ideas').fetchone()[0]
            vote_ceiling = conn.execute('SELECT coalesce(max(id),0) FROM community_vote_events').fetchone()[0]
            score, last = 2**60, ceiling + 1
        # A keyset and frozen support ranking survive insertions and vote changes between pages.
        # Current visibility is ALWAYS rechecked; a withdrawn/hidden result disappears immediately.
        pattern = '%' + q.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        rank = '''(SELECT count(*) FROM community_votes v WHERE v.idea_id=i.id) -
                  (SELECT coalesce(sum(delta),0) FROM community_vote_events e WHERE e.idea_id=i.id AND e.id>?)'''
        params = [vote_ceiling] if sort == 'supported' else []
        params += [ceiling, pattern, pattern]
        owner = 'AND i.member_id=?' if sort == 'own' else ''
        if owner:
            params.append(me['id'])
        params += [score, score, last, limit + 1]
        rows = conn.execute(f'''WITH ranked AS (
            SELECT i.id,i.seq,{rank if sort == 'supported' else '0'} AS score FROM community_ideas i
            WHERE i.visibility='visible' AND i.seq<=? AND (i.title LIKE ? ESCAPE '\\' OR i.description LIKE ? ESCAPE '\\') {owner}
        ) SELECT id,seq,score FROM ranked WHERE score<? OR (score=? AND seq<?)
        ORDER BY score DESC,seq DESC LIMIT ?''', params).fetchall()
        page = rows[:limit]
        next_cursor = _cursor([asof,ceiling,vote_ceiling,page[-1][2],page[-1][1],query_hash], me, secret) if len(rows) > limit else None
        return {'ideas': [_public(conn, _row(conn, row[0]), me) for row in page],
                'next_cursor': next_cursor, 'viewer': {'id': me['id'], 'name': me['name']}}


def moderate(idea_id, *, operator, explanation, status=None, visibility=None, duplicate_id=None, availability=None):
    operator = text(operator, 'Operator', 80)
    explanation = text(explanation, 'Decision', 2000)
    if status is not None and status not in STATUSES:
        raise ValueError('Choose a supported idea status.')
    if visibility is not None and visibility not in ('visible', 'hidden', 'withdrawn'):
        raise ValueError('Choose visible, hidden or withdrawn.')
    if availability is not None:
        availability = text(availability, 'Verified release/deployment evidence', 500)
    with db.transaction() as conn:
        row = _row(conn, idea_id)
        if row['visibility'] == 'withdrawn':
            raise Conflict('Withdrawn content cannot be restored.')
        next_status = status or row['status']
        next_visibility = visibility or row['visibility']
        if next_visibility == 'withdrawn':
            _withdraw(conn, row, operator, explanation)
            return
        if next_status == 'available' and not (availability or row['availability']):
            raise ValueError('Available to play requires verified release or deployment evidence.')
        target = duplicate_id if duplicate_id is not None else row['duplicate_id']
        if next_status == 'duplicate':
            if not target or target == idea_id:
                raise ValueError('Choose a different surviving idea.')
            survivor = _row(conn, target)
            if survivor['visibility'] != 'visible' or survivor['status'] == 'duplicate':
                raise ValueError('The surviving idea must be visible and not a duplicate.')
            if conn.execute("SELECT 1 FROM community_ideas WHERE duplicate_id=? AND visibility!='withdrawn'", (idea_id,)).fetchone():
                raise ValueError('Redirect existing duplicates before making this idea a duplicate.')
        else:
            target = None
        stamp = now()
        conn.execute('''UPDATE community_ideas SET status=?,visibility=?,duplicate_id=?,response=?,availability=?,updated_at=? WHERE id=?''',
                     (next_status,next_visibility,target,explanation,availability or row['availability'],stamp,idea_id))
        conn.execute('INSERT INTO community_decisions(idea_id,operator,status,visibility,explanation,at) VALUES (?,?,?,?,?,?)',
                     (idea_id,operator,next_status,next_visibility,explanation,stamp))


def operator_list(visibility='visible', before=2**63-1, limit=50):
    if visibility not in ('visible','hidden','withdrawn') or not 1 <= limit <= 50:
        raise ValueError('Choose a visibility and at most 50 records.')
    db.init_db()
    with db._connection() as conn:
        return [dict(zip(('seq','id','title','status','visibility'), row)) for row in conn.execute('''
            SELECT seq,id,title,status,visibility FROM community_ideas WHERE visibility=? AND seq<? ORDER BY seq DESC LIMIT ?''',
            (visibility,before,limit))]


def operator_detail(idea_id):
    db.init_db()
    with db._connection() as conn:
        row = _row(conn, idea_id)
        # Deliberate allowlist: no credential aliases, participant IDs or submission receipt hashes.
        return {k: row[k] for k in ('id','title','description','status','visibility','response','duplicate_id','availability','public_credit')}
