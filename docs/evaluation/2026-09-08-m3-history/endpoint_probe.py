"""Real endpoints/CLI/cast on an explicit checkout; disposable DB, no external AI.

Run: .venv/bin/python <this file> <checkout>. Node on PATH renders that checkout's
shared client narrator. Only disposable delivery clocks are advanced.
"""
import contextlib
import io
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import threading
from unittest.mock import patch
import urllib.parse
import urllib.request

# Imports below deliberately target the explicitly selected checkout.
# ruff: noqa: E402

CHECKOUT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(CHECKOUT))

import consciousness
import persistence
from causality.staging import drain_due_hops
from interface import _do_scale_verb
from multiverse import store
from server import _Handler, _ThreadedServer, heartbeat
from server.rooms import get_room


def run():
    os.environ["NESTED_WORLDS_CANONICAL_SEED"] = "382"
    os.environ["NESTED_WORLDS_MATURATION_SCALE"] = "1"
    os.environ["NESTED_WORLDS_HOP_DELAY"] = "0"
    with tempfile.TemporaryDirectory(prefix="enfolded-m3-probe-") as directory:
        persistence._DB_PATH = Path(directory) / "world.db"
        server = _ThreadedServer(("127.0.0.1", 0), _Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_address[1]}"

        def get(path):
            with urllib.request.urlopen(url + path) as response:
                return json.load(response)

        def post(node, name):
            request = urllib.request.Request(url + "/act", data=json.dumps({
                "node_name": node, "player_name": name}).encode(),
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(request) as response:
                return json.load(response)

        notices = []
        output = {}
        try:
            tree = get("/world?depth=6")["world"]
            galaxy = tree["children"][0]["children"][0]
            planet = galaxy["children"][0]["children"][0]
            output["places"] = {"galaxy": galaxy["name"], "planet": planet["name"]}
            with patch("server.handlers.broadcast", side_effect=lambda room, msg: notices.append(msg)), \
                    patch("server.heartbeat.broadcast", side_effect=lambda room, msg: notices.append(msg)):
                output["http_seed"] = post(planet["name"], "Ada")
                output["http_kindles"] = [post(galaxy["name"], n) for n in ("Ada", "Bea")]
                root = store.world_tree(382)
                captured = io.StringIO()
                with contextlib.redirect_stdout(captured):
                    _do_scale_verb(root.children[0].children[0], 382, "CLIVisitor")
                output["cli"] = captured.getvalue()
                output["cast"] = heartbeat._persona_act(
                    382, get_room(382), root, "Tessera", "tender", [galaxy["name"]], random.Random(1))
                drain_due_hops(limit=64, broadcaster=heartbeat._pump_broadcaster, world_seed=382)
                output["before_landing"] = get("/history?node_name=" + urllib.parse.quote(galaxy["name"]))
                with persistence._connect() as conn:
                    conn.execute("UPDATE verb_maturation SET due_at='2000-01-01'")
                heartbeat.drain_matured_verbs(world_seed=382)
            output["history"] = get("/history")
            output["chronicle"] = get("/chronicle?limit=200")
            output["notices"] = notices
            with persistence._connect() as conn:
                output["recorded_facts"] = conn.execute(
                    "SELECT id, node_name, mutation_type, player_name, data, delta, node_version, "
                    "strength, actor_identity FROM world_mutations ORDER BY id").fetchall()
            output["speech_history"] = consciousness._history_block(
                persistence.get_node_history(382, root.children[0].name, limit=20))
            rows = output["history"]["mutations"]
            renderer = "require(process.argv[1]); let s='';process.stdin.on('data',d=>s+=d);process.stdin.on('end',()=>console.log(JSON.stringify(JSON.parse(s).map(m=>EnfoldedClient.mutationLine(m)))));"
            output["player_lines"] = json.loads(subprocess.check_output(
                ["node", "-e", renderer, str(CHECKOUT / "static/clientlogic.js")],
                input=json.dumps(rows).encode()))
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
    return output


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
