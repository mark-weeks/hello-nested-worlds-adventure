import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, sys.argv[1])
import persistence
from multiverse import store
from causality.staging import drain_due_hops
from server.heartbeat import drain_matured_verbs

if len(sys.argv) > 2:
    persistence._DB_PATH = Path(sys.argv[2])
    queue = sys.argv[3]
    drain = drain_due_hops if queue == 'causal_queue' else drain_matured_verbs
    seam = ('causality.staging.store.world_tree' if queue == 'causal_queue'
            else 'server.heartbeat.persistence.record_substance_change')
    with patch(seam, side_effect=lambda *a, **k: os.kill(os.getpid(), signal.SIGKILL)):
        drain()
else:
    result = {}
    with tempfile.TemporaryDirectory(prefix='enfolded-m1-baseline-') as directory:
        for queue in ['causal_queue', 'verb_maturation']:
            persistence._DB_PATH = Path(directory) / f'{queue}.db'
            root = store.world_tree(seed=382)
            if queue == 'causal_queue':
                persistence.enqueue_causal_hop(382, root.name, 'DANGER_ALERT', 1, 'up', {}, 0)
                drain = drain_due_hops
            else:
                persistence.enqueue_verb_maturation(382, root.name, 'attune', {'attuned': True}, 'Probe', 0)
                drain = drain_matured_verbs
            child = subprocess.run([sys.executable, __file__, sys.argv[1], str(persistence._DB_PATH), queue])
            with persistence._connect() as conn:
                remaining = conn.execute(f'SELECT COUNT(*) FROM {queue}').fetchone()[0]
                history = conn.execute('SELECT COUNT(*) FROM world_mutations').fetchone()[0]
            result[queue] = {'process_exit': child.returncode, 'queued_before': 1,
                'queued_after_kill': remaining, 'history_after_kill': history,
                'restart_recovered': drain()}
    print(json.dumps(result, indent=2))
