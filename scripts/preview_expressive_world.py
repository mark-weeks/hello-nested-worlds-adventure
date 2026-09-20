"""Run a local review world; optionally resume a previously saved preview."""
import argparse
import os
from pathlib import Path
import secrets
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('port', nargs='?', type=int, default=8201)
    parser.add_argument('--resume', type=Path, help='Existing preview database to preserve and resume')
    args = parser.parse_args()
    if args.resume and not args.resume.is_file():
        parser.error('--resume requires an existing preview database')
    import persistence
    from multiverse import store
    from multiverse.situation import NODES
    from server import run
    os.environ['NESTED_WORLDS_CANONICAL_SEED'] = '382'
    os.environ['NESTED_WORLDS_DISABLE_AI'] = '1'
    os.environ['NESTED_WORLDS_DISABLE_IMAGES'] = '1'
    os.environ['NESTED_WORLDS_HEARTBEAT'] = '0'
    os.environ['NESTED_WORLDS_CAUSAL_PUMP'] = '1'
    with tempfile.TemporaryDirectory(prefix='enfolded-expressive-preview-') as directory:
        persistence._DB_PATH = args.resume.resolve() if args.resume else Path(directory) / 'worlds.db'
        if not args.resume:
            store.ensure_born(382)
            key = 'nw_' + secrets.token_hex(16)
            persistence.mint_invite_key(key, 'Mark')
            persistence.save_player_position(key, NODES['region'], 382, 9, 1, 4)
            link = f'http://127.0.0.1:{args.port}/app?key={key}&name=Mark'
        else:
            link = f'http://127.0.0.1:{args.port}/app'
        print(f'Local preview: {link}', flush=True)
        print('Local review world; AI calls disabled. Recorded music and cinematic artwork are included.', flush=True)
        print('Existing history and invites preserved.' if args.resume else 'Disposable new preview; no scripted situation installed.', flush=True)
        run('127.0.0.1', args.port)


if __name__ == '__main__':
    main()
