"""Thread-safety test for consciousness._get_client (T-2)."""
from __future__ import annotations

import sys
import threading
import types
from unittest.mock import MagicMock


def test_get_client_thread_safety():
    """Anthropic() must be called exactly once even with concurrent initialisation."""
    mock_instance = MagicMock()
    call_count = [0]
    count_lock = threading.Lock()

    def counting_anthropic():
        with count_lock:
            call_count[0] += 1
        return mock_instance

    # Inject a fake `anthropic` module so that `from anthropic import Anthropic`
    # inside _get_client resolves to our counting stub — works whether or not
    # the real package is installed.
    fake_anthropic = types.ModuleType("anthropic")
    fake_anthropic.Anthropic = counting_anthropic  # type: ignore[attr-defined]

    import consciousness

    original_module = sys.modules.get("anthropic")
    sys.modules["anthropic"] = fake_anthropic
    consciousness._client = None

    try:
        n_threads = 10
        barrier = threading.Barrier(n_threads)
        results: list = []
        errors: list = []

        def worker():
            try:
                barrier.wait()
                client = consciousness._get_client()
                results.append(client)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    finally:
        if original_module is None:
            sys.modules.pop("anthropic", None)
        else:
            sys.modules["anthropic"] = original_module
        consciousness._client = None

    assert not errors, f"Unexpected errors: {errors}"
    assert call_count[0] == 1, (
        f"Anthropic() called {call_count[0]} times; expected exactly 1"
    )
    assert len(results) == n_threads
    assert all(r is mock_instance for r in results)
