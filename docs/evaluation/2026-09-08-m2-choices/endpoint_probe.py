"""Compare real HTTP acceptance and landing on an explicit checkout.

Uses only temporary databases; run with Python 3.11 and the locked dependencies.
Pass the checkout to import, not a database. Queue clocks alone are advanced.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(Path(sys.argv[1]).resolve()))

import persistence
from multiverse import store
from server import _Handler, _ThreadedServer, heartbeat


def run():
    os.environ["NESTED_WORLDS_CANONICAL_SEED"] = "382"
    os.environ["NESTED_WORLDS_MATURATION_SCALE"] = "1"
    output = {}
    with tempfile.TemporaryDirectory(prefix="enfolded-m2-probe-") as directory:
        persistence._DB_PATH = Path(directory) / "world.db"
        root = store.world_tree(382)
        galaxy = root.children[0].children[0]
        server = _ThreadedServer(("127.0.0.1", 0), _Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_address[1]}"

        def post(name):
            req = urllib.request.Request(url + "/act", data=json.dumps({
                "node_name": galaxy.name, "player_name": name}).encode(),
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req) as reply:
                return json.load(reply)

        def world():
            with urllib.request.urlopen(url + "/world?depth=3") as reply:
                return json.load(reply)["world"]["children"][0]["children"][0]["properties"]

        def land():
            with persistence._connect() as conn:
                conn.execute("UPDATE verb_maturation SET due_at = '2000-01-01'")
            heartbeat.drain_matured_verbs()

        try:
            output["before"] = world()
            with ThreadPoolExecutor(2) as pool:
                output["overlap_replies"] = list(pool.map(post, ["Ada", "Bea"]))
            output["after_acceptance"] = world()
            land()
            output["after_landing"] = world()
            persistence.record_substance_change(382, galaxy.name, "TEST_CHANGE", None,
                {}, {"star_density": 999, "kindled": False})
            output["mark_only_replies"] = [post("Ada"), post("Bea")]
            land()
            output["saturated_reply"] = post("Ada")
            output["final"] = world()
            with persistence._connect() as conn:
                output["work"] = conn.execute(
                    "SELECT id, semantics_version, status, outcome FROM verb_maturation ORDER BY id").fetchall()
                output["landing_deltas"] = conn.execute(
                    "SELECT delta FROM world_mutations WHERE mutation_type = 'SCALE_ACT_MATURED' ORDER BY id").fetchall()
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
    return output


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
