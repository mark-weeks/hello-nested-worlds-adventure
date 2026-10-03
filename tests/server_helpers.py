"""Python adapter for the same disposable entry point used by Playwright's server.js."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request


def _read_port(child, errors, timeout):
    deadline, output = time.monotonic() + timeout, b''
    reason = 'Server startup timed out'
    while time.monotonic() < deadline:
        if not select.select([child.stdout], [], [], max(0, deadline - time.monotonic()))[0]:
            break
        chunk = os.read(child.stdout.fileno(), 4096)
        if not chunk:
            child.wait(timeout=5)
            reason = f'Server exited before port announcement (exit {child.returncode})'
            break
        output += chunk
        if b'\n' in output or len(output) > 128:
            line = output.split(b'\n', 1)[0]
            if line.isdigit() and 0 < int(line) < 65536:
                return int(line)
            reason = f'Invalid server port: {line[:128]!r}'
            break
    errors.seek(0, os.SEEK_END)
    errors.seek(max(0, errors.tell() - 8000))
    raise AssertionError(f'{reason}\n{errors.read().decode(errors="replace")}')


@contextmanager
def server(database, *, startup_timeout=15):
    # A file avoids a full stderr pipe blocking a child before the port handshake.
    with tempfile.TemporaryFile() as errors:
        child = subprocess.Popen([sys.executable, '-u', 'scripts/e2e_server.py', '0',
                                  '--database', str(database)],
            cwd=Path(__file__).resolve().parents[1], stdout=subprocess.PIPE,
            stderr=errors, env={**os.environ,
                'NESTED_WORLDS_CANONICAL_SEED': '382', 'NESTED_WORLDS_DISABLE_AI': '1',
                'NESTED_WORLDS_DISABLE_IMAGES': '1', 'NESTED_WORLDS_HEARTBEAT': '0',
                'NESTED_WORLDS_CAUSAL_PUMP': '0'})
        try:
            port = _read_port(child, errors, startup_timeout)
            def request(path, key='', body=None):
                req = urllib.request.Request(f'http://127.0.0.1:{port}{path}',
                    data=json.dumps(body).encode() if body is not None else None,
                    headers={'X-Beta-Key': key, 'Content-Type': 'application/json'})
                try:
                    response = urllib.request.urlopen(req, timeout=10)
                except urllib.error.HTTPError as exc:
                    response = exc
                with response:
                    return response.status, json.load(response)
            yield request
        finally:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=10)
            child.stdout.close()
