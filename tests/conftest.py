"""Shared pytest configuration.

Provides a minimal `benchmark` fixture when pytest-benchmark is not
installed so that test_benchmark.py always runs (one iteration each,
no statistics).  When pytest-benchmark IS installed its plugin-provided
fixture takes precedence automatically.
"""

import time
import pytest

try:
    import pytest_benchmark  # noqa: F401 — real fixture injected by plugin
except ImportError:
    class _NullBenchmark:
        """Single-shot stand-in for the pytest-benchmark fixture."""
        elapsed: float = 0.0

        def __call__(self, fn, *args, **kwargs):
            t0 = time.perf_counter()
            result = fn(*args, **kwargs)
            self.elapsed = time.perf_counter() - t0
            return result

    @pytest.fixture
    def benchmark():
        return _NullBenchmark()
