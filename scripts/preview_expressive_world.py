"""Run a disposable, locally bound milestone world; never use the operator DB."""
import os
from pathlib import Path
import secrets
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    import persistence
    from persistence.situations import install
    from multiverse.situation import NODES
    from server import run
    os.environ['NESTED_WORLDS_CANONICAL_SEED'] = '382'
    os.environ['NESTED_WORLDS_DISABLE_AI'] = '1'
    os.environ['NESTED_WORLDS_DISABLE_IMAGES'] = '1'
    os.environ['NESTED_WORLDS_HEARTBEAT'] = '0'
    os.environ['NESTED_WORLDS_CAUSAL_PUMP'] = '1'
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8201
    with tempfile.TemporaryDirectory(prefix='enfolded-expressive-preview-') as directory:
        persistence._DB_PATH = Path(directory) / 'worlds.db'
        install(382)
        key = 'nw_' + secrets.token_hex(16)
        persistence.mint_invite_key(key, 'Mark')
        persistence.save_player_position(key, NODES['region'], 382, 9, 1, 4)
        print(f'Local preview: http://127.0.0.1:{port}/app?key={key}&name=Mark', flush=True)
        print('Disposable world; AI calls disabled. Recorded music and cinematic artwork are included.', flush=True)
        run('127.0.0.1', port)


if __name__ == '__main__':
    main()
