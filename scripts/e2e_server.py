"""Disposable local browser fixture. Never open the operator's world database."""
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import persistence  # noqa: E402
from server import _Handler, _ThreadedServer  # noqa: E402

if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='enfolded-browser-world-') as directory:
        persistence._DB_PATH = Path(directory) / 'worlds.db'
        server = _ThreadedServer(('127.0.0.1', int(sys.argv[1])), _Handler)
        try:
            server.serve_forever()
        finally:
            server.server_close()
