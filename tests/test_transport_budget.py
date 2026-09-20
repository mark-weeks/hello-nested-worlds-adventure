"""Transport budget: compressed tree reads and immutable content-versioned files."""
import gzip
import json
import re
import threading
import urllib.error
import urllib.request

import pytest

from tests.test_participant_contracts import accounts  # noqa: F401

IMMUTABLE = 'public, max-age=31536000, immutable'


@pytest.fixture
def raw(accounts, monkeypatch):  # noqa: F811
    monkeypatch.setenv('NESTED_WORLDS_CANONICAL_SEED', '382')
    from server import _Handler, _ThreadedServer
    server = _ThreadedServer(('127.0.0.1', 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    def request(path, **headers):
        req = urllib.request.Request(f'http://127.0.0.1:{server.server_port}{path}',
                                     headers={'X-Beta-Key': accounts[0], **headers})
        try:
            response = urllib.request.urlopen(req, timeout=10)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            return response.status, response.read(), dict(response.headers)
    try:
        yield request
    finally:
        server.shutdown()


def _without_ids(value):
    # Tree node ids are minted per request; the served content is what must match.
    if isinstance(value, dict):
        return {k: _without_ids(v) for k, v in value.items() if k != 'id'}
    return [_without_ids(v) for v in value] if isinstance(value, list) else value


def test_tree_reads_compress_only_for_accepting_clients(raw):
    status, plain, headers = raw('/world?depth=4')
    assert status == 200 and 'Content-Encoding' not in headers and headers['Vary'] == 'Accept-Encoding'
    status, packed, headers = raw('/world?depth=4', **{'Accept-Encoding': 'gzip, deflate, br'})
    assert status == 200 and headers['Content-Encoding'] == 'gzip'
    assert int(headers['Content-Length']) == len(packed)
    assert _without_ids(json.loads(gzip.decompress(packed))) == _without_ids(json.loads(plain))
    # The per-node prose folds several times over; the contract is unchanged.
    assert len(packed) * 4 < len(plain)
    status, small, headers = raw('/health', **{'Accept-Encoding': 'gzip'})
    assert status == 200 and 'Content-Encoding' not in headers and json.loads(small)


@pytest.mark.parametrize('encoding,compressed', [
    ('gzip;q=0, identity', False),
    ('gzip;q=0, *;q=1', False),
    ('br, *;q=0, identity;q=1', False),
    ('notgzip', False),
    ('GZip;Q=0.5', True),
    ('br, *;q=0.5', True),
    ('gzip;q=invalid', False),
])
def test_compression_respects_encoding_tokens_and_quality(raw, encoding, compressed):
    status, body, headers = raw('/world?depth=4', **{'Accept-Encoding': encoding})
    assert status == 200 and headers['Vary'] == 'Accept-Encoding'
    assert (headers.get('Content-Encoding') == 'gzip') is compressed
    content = gzip.decompress(body) if compressed else body
    assert json.loads(content)['world']['level'] == 'Multiverse'


def test_versioned_media_and_hashed_bundle_assets_are_immutable(raw):
    status, body, headers = raw('/media/places/orchard-v1.png')
    assert status == 200 and headers['Cache-Control'] == IMMUTABLE and body[:8] == b'\x89PNG\r\n\x1a\n'
    status, _, headers = raw('/media/score/harp.mp3')
    assert status == 200 and headers['Cache-Control'] == IMMUTABLE
    status, _, headers = raw('/media/places/../../index.html')
    assert status in (403, 404)
    status, html, headers = raw('/app')
    assert status == 200 and 'immutable' not in headers.get('Cache-Control', '')
    asset = re.search(rb'assets/[\w.-]+\.js', html)
    if asset:  # the built bundle is present
        status, _, headers = raw('/app/' + asset.group(0).decode())
        assert status == 200 and headers['Cache-Control'] == IMMUTABLE
    for page in ('/', '/guide', '/score.js'):
        status, _, headers = raw(page)
        assert status == 200 and 'immutable' not in headers.get('Cache-Control', '')


def test_missing_hashed_assets_are_404_and_routes_still_get_the_shell(raw):
    status, body, headers = raw('/app/assets/index-doesnotexist.js')
    assert status == 404 and 'immutable' not in headers.get('Cache-Control', '')
    assert json.loads(body)['error'] == 'not found'
    status, body, headers = raw('/app/some/client/route')
    assert status == 200 and 'text/html' in headers['Content-Type']
    assert 'immutable' not in headers.get('Cache-Control', '')
