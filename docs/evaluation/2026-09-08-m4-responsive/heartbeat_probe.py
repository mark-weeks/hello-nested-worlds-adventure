"""Portable real-heartbeat comparison. Explicit checkout, disposable databases.

Run with Python 3.11: heartbeat_probe.py /absolute/checkout
Saturation is constructed, never a production-frequency estimate.
"""
import json
import os
from pathlib import Path
import random
import sys
import tempfile
import threading
from unittest.mock import patch
import urllib.request

# ruff: noqa: E402
sys.path.insert(0, str(Path(sys.argv[1]).resolve()))
import persistence
from agents.agent import Agent
from multiverse import store
from server import _Handler, _ThreadedServer, heartbeat


class Steady(random.Random):
    def choice(self, seq):
        return seq[0]

    def random(self):
        return 0.5


def walk(node):
    yield node
    for child in node.children:
        yield from walk(child)


def run():
    os.environ["NESTED_WORLDS_CANONICAL_SEED"] = "382"
    os.environ["NESTED_WORLDS_MATURATION_SCALE"] = "1"
    result = {"scope": "constructed fixtures; no production frequency claim"}
    with tempfile.TemporaryDirectory(prefix="enfolded-m4-probe-") as directory:
        for saturation in ("partial", "full"):
            persistence._DB_PATH = Path(directory) / (saturation + ".db")
            root = store.world_tree(382)
            nodes = list(walk(root))
            target = root.children[0].children[0]
            known = [n.name for n in (nodes if saturation == "full" else list(walk(target)))]
            context = [{"node": target.name, "level": target.level,
                        "state": "EXPLORE", "action": "explored", "persona": "tender"}]
            persistence.save_agent_memory("Tessera", 382, known, context)
            server = _ThreadedServer(("127.0.0.1", 0), _Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            stats = []
            original_connect, original_tree = persistence._connect, store.world_tree
            inspected = 0
            original_traverse = getattr(Agent, "_traverse", None)

            def visit(self, node):
                nonlocal inspected
                inspected += 1
                return original_traverse(self, node)

            def tick():
                nonlocal inspected
                reads, hydrations, inspected = [], [], 0
                def connect():
                    conn = original_connect()
                    conn.set_trace_callback(lambda sql: reads.append(sql) if sql.lstrip().upper().startswith(("SELECT", "WITH")) else None)
                    return conn
                def tree(*args, **kwargs):
                    hydrations.append(1)
                    return original_tree(*args, **kwargs)
                with patch.object(persistence, "_connect", connect), patch.object(store, "world_tree", tree):
                    summary = heartbeat.run_tick(382, Steady(1), max_nodes=4, pace=0)
                saved = persistence.load_agent_memory("Tessera", 382)
                stats.append({**summary, "selects": len(reads), "hydrations": len(hydrations),
                              "legacy_recursive_calls": inspected,
                              "known": len(saved["visited_ids"]), "context_rows": len(saved["log_entries"])})

            try:
                with patch.object(heartbeat, "WANDERER_ROSTER", ("Tessera",)), \
                        patch.object(heartbeat, "_drop_in", lambda *args: target), \
                        patch.object(Agent, "_traverse", visit) if original_traverse else patch.object(heartbeat, "_DEFAULT_PACE", 0):
                    for _ in range(3):
                        tick()
                    url = f"http://127.0.0.1:{server.server_address[1]}/act"
                    request = urllib.request.Request(url, data=json.dumps({"node_name": target.name, "player_name": "Ada"}).encode(), headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(request) as response:
                        acceptance = json.load(response)
                    with persistence._connect() as conn:
                        conn.execute("UPDATE verb_maturation SET due_at='2000-01-01' WHERE status='pending'")
                    heartbeat.drain_matured_verbs(world_seed=382)
                    tick()
                    # Each tick constructs a new Agent from durable memory.
                    tick()
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
            result[saturation] = {"world_nodes": len(nodes), "initial_known": len(known),
                                  "target": target.name, "player_acceptance": acceptance,
                                  "ticks": stats}
        # The cast-wide fixture repeats the original assessment's saturation
        # construction, without forcing a drop-in or altering agent clocks.
        persistence._DB_PATH = Path(directory) / "whole-cast.db"
        root = store.world_tree(382)
        names = [n.name for n in walk(root)]
        for name in heartbeat.WANDERER_ROSTER:
            persistence.save_agent_memory(name, 382, names, [])
        ticks = [heartbeat.run_tick(382, random.Random(i), pace=0) for i in range(12)]
        with persistence._connect() as conn:
            rows = conn.execute("SELECT COUNT(*) FROM world_mutations").fetchone()[0]
        result['whole_cast'] = {'ticks': ticks, 'chronicle_rows': rows,
                                'fresh': sum(t['fresh'] for t in ticks),
                                'acts': sum(t['act'] is not None for t in ticks)}

        persistence._DB_PATH = Path(directory) / "renewal.db"
        root = store.world_tree(382)
        from puzzles.generators import build_puzzle
        node = next(n for n in walk(root) if n.level == "Room" and n.properties.get('has_puzzle')
                    and not n.properties.get('locked'))
        server = _ThreadedServer(("127.0.0.1", 0), _Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            request = urllib.request.Request(f"http://127.0.0.1:{server.server_address[1]}/puzzle/attempt",
                data=json.dumps({'depth': 11, 'node_name': node.name, 'player_name': 'Ada',
                                 'answer': build_puzzle(node).answer}).encode(),
                headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(request) as response:
                solved = json.load(response)
            decay = heartbeat._persona_act(382, heartbeat.get_room(382), root, 'Vex', 'destabilizer',
                                            [node.name], Steady(1))
            epoch = persistence.count_node_mutations(382, node.name, 'PUZZLE_REARM')
            agent = Agent('Tessera')
            agent.world_seed = 382  # old baseline ignores this attribute
            attempt = agent._attempt_puzzle(node)
            result['renewal'] = {'human_endpoint_correct': solved['correct'], 'decay': decay,
                                 'epoch': epoch, 'current_puzzle': build_puzzle(node, epoch).name,
                                 'agent_puzzle': attempt[1], 'difficulty': attempt[2]}
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
    return result


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
