"""Startup is independent of reverse DNS and handles an arriving cohort before accept."""
from contextlib import ExitStack, closing
import socket
import subprocess
import sys

import pytest

from server import _Handler, _ThreadedServer
from tests import server_helpers


@pytest.mark.parametrize('host', ['127.0.0.1', '0.0.0.0'])
def test_listener_binds_with_broken_reverse_dns(monkeypatch, host):
    def unavailable(*args):
        raise OSError('DNS resolver unavailable')
    monkeypatch.setattr(socket, 'getfqdn', unavailable)
    with _ThreadedServer((host, 0), _Handler) as listener:
        assert listener.server_name == host
        assert listener.server_port > 0
        with socket.create_connection(('127.0.0.1', listener.server_port), timeout=1):
            pass


def test_cohort_connects_before_accept_loop_starts():
    # Queue requests before accepting anything. A successful client handshake can
    # precede an asynchronous overflow reset, so also prove each connection stays
    # open while its request waits. Linux can time out at connect instead of reset.
    with _ThreadedServer(('127.0.0.1', 0), _Handler) as listener, ExitStack() as clients:
        for _ in range(32):
            client = clients.enter_context(closing(socket.create_connection(listener.server_address, timeout=0.5)))
            client.sendall(b'GET /health HTTP/1.0\r\n\r\n')
            client.settimeout(0.02)
            with pytest.raises(TimeoutError):
                client.recv(1)  # No handler yet; a reset/EOF is a failed waiting connection.


@pytest.mark.parametrize('code,diagnostic', [
    ('import sys; sys.stderr.write("fixture startup error\\n"); sys.exit(3)', 'exit 3'),
    ('import sys; sys.stderr.write("fixture startup error\\n"); print(70000)', 'Invalid server port'),
    ('import sys,time; sys.stderr.write("fixture startup error\\n"); '
     'sys.stdout.write("123"); sys.stdout.flush(); time.sleep(10)', 'startup timed out'),
])
def test_child_startup_errors_include_stderr_and_are_cleaned_up(monkeypatch, tmp_path, code, diagnostic):
    real_popen, children = subprocess.Popen, []
    def launch(_command, **kwargs):
        child = real_popen([sys.executable, '-u', '-c', code], **kwargs)
        children.append(child)
        return child
    monkeypatch.setattr(server_helpers.subprocess, 'Popen', launch)
    with pytest.raises(AssertionError, match=diagnostic) as error:
        with server_helpers.server(tmp_path / 'world.db', startup_timeout=0.5):
            pytest.fail('Invalid child was reported ready')
    assert 'fixture startup error' in str(error.value)
    assert children[0].poll() is not None
