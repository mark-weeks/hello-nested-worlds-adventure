"""Compare PR review heads: python review_hydration_probe.py CHECKOUT.

Disposable databases, 32 already-due root hops per trial, no notifications.
Reports measurements rather than asserting a machine-specific timing budget.
"""
import json
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

sys.path.insert(0, str(Path(sys.argv[1]).resolve()))
import persistence  # noqa: E402
from causality.staging import drain_due_hops  # noqa: E402
from multiverse import store  # noqa: E402

trials = []
with tempfile.TemporaryDirectory(prefix="enfolded-review-hydration-") as directory:
    for trial in range(3):
        persistence._DB_PATH = Path(directory) / f"trial-{trial}.db"
        root = store.world_tree(seed=382)
        for _ in range(32):
            persistence.enqueue_causal_hop(382, root.name, "DANGER_ALERT", 1, "up", {}, 0)
        calls = []
        hydrate = store.world_tree

        def measured_tree(*args, **kwargs):
            calls.append(getattr(persistence._transaction_state, "connection", None) is not None)
            return hydrate(*args, **kwargs)

        with patch.object(store, "world_tree", measured_tree):
            started = time.perf_counter()
            fired = drain_due_hops(limit=32)
            elapsed = time.perf_counter() - started
        trials.append({"delivered": fired, "seconds": round(elapsed, 4),
                       "world_tree_calls": len(calls), "tree_calls_inside_writer": sum(calls)})
print(json.dumps({"seed": 382, "hops_per_trial": 32, "trials": trials}, indent=2))
