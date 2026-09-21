"""Disposable local browser fixture. Never open the operator's world database."""
import argparse
from contextlib import ExitStack
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import persistence  # noqa: E402
from server import _Handler, _ThreadedServer, heartbeat  # noqa: E402

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('port', nargs='?', type=int, default=0)
    parser.add_argument('--database', type=Path, help='Caller-owned disposable database')
    parser.add_argument('--preseed', type=int)
    parser.add_argument('--invite')
    parser.add_argument('--player', default='Browser traveler')
    parser.add_argument('--pump', action='store_true')
    args = parser.parse_args()
    with ExitStack() as stack:
        persistence._DB_PATH = args.database or Path(stack.enter_context(
            tempfile.TemporaryDirectory(prefix='enfolded-browser-world-'))) / 'worlds.db'
        if args.invite:
            persistence.mint_invite_key(args.invite, args.player)
        if args.preseed is not None:
            from multiverse import store
            store.ensure_born(args.preseed)
        server = _ThreadedServer(('127.0.0.1', args.port), _Handler)
        if args.pump:
            heartbeat.start_pump()
        print(server.server_address[1], flush=True)
        try:
            server.serve_forever()
        finally:
            server.server_close()
