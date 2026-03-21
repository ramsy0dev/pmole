"""Performance benchmarks for pmole's compression algorithms and archive API.

Install pytest-benchmark for full statistics and histogram output:
    pip install pytest-benchmark
    pytest tests/test_benchmark.py -v --benchmark-sort=mean

Without pytest-benchmark the tests still run (single iteration each).
"""

import os
import random

import pytest

import pmole
from pmole.compression import (
    ALGO_LZW, ALGO_LZW_ZLIB, ALGO_ZLIB, ALGO_LZMA, ALGO_NAMES,
    compress_with_algo, decompress_with_algo, compress_auto,
)

# ---------------------------------------------------------------------------
# Data generators
# ---------------------------------------------------------------------------

def _repetitive(n: int) -> bytes:
    """Highly repetitive text — ideal case for LZW / LZW+zlib."""
    unit = b"the quick brown fox jumps over the lazy dog\n"
    return (unit * (n // len(unit) + 1))[:n]


def _source_code(n: int) -> bytes:
    """Realistic Python source code — typical archive workload."""
    snippet = (
        b"def fibonacci(n: int) -> int:\n"
        b"    a, b = 0, 1\n"
        b"    for _ in range(n):\n"
        b"        a, b = b, a + b\n"
        b"    return a\n\n"
        b"class Processor:\n"
        b"    def __init__(self) -> None:\n"
        b"        self.cache: dict = {}\n"
        b"    def run(self, key: str) -> list:\n"
        b"        return self.cache.get(key, [])\n\n"
    )
    return (snippet * (n // len(snippet) + 1))[:n]


def _json(n: int) -> bytes:
    """Structured JSON — repetitive keys, varied values."""
    rec = b'{"id":1234,"name":"Alice Smith","score":98.6,"tags":["python","dev"]}\n'
    return (rec * (n // len(rec) + 1))[:n]


def _random_bytes(n: int, seed: int = 0) -> bytes:
    """Random bytes — worst case (incompressible)."""
    rng = random.Random(seed)
    return bytes(rng.randint(0, 255) for _ in range(n))


# ---------------------------------------------------------------------------
# Module-scoped fixtures: pre-built 100 KB data blobs
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def repetitive_100k():
    return _repetitive(100_000)


@pytest.fixture(scope="module")
def source_code_100k():
    return _source_code(100_000)


@pytest.fixture(scope="module")
def json_100k():
    return _json(100_000)


@pytest.fixture(scope="module")
def random_100k():
    return _random_bytes(100_000)


# ---------------------------------------------------------------------------
# Source-tree fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def small_tree(tmp_path):
    """50 Python files ~2 KB each (~100 KB total) — typical source tree."""
    src = tmp_path / "src"
    src.mkdir()
    body = _source_code(2_000).decode("utf-8")
    for i in range(50):
        (src / f"mod_{i:03d}.py").write_text(body, encoding="utf-8")
    return str(src)


@pytest.fixture
def large_tree(tmp_path):
    """5 Python files ~20 KB each (~100 KB total)."""
    src = tmp_path / "src"
    src.mkdir()
    body = _source_code(20_000).decode("utf-8")
    for i in range(5):
        (src / f"large_{i}.py").write_text(body, encoding="utf-8")
    return str(src)


# ---------------------------------------------------------------------------
# 1. Raw compress throughput — parametrised by algorithm
# ---------------------------------------------------------------------------

ALL_ALGOS  = [ALGO_LZW, ALGO_LZW_ZLIB, ALGO_ZLIB, ALGO_LZMA]
FAST_ALGOS = [ALGO_ZLIB, ALGO_LZMA]  # safe for any data size


@pytest.mark.parametrize("algo", ALL_ALGOS, ids=lambda a: ALGO_NAMES[a])
def test_compress_repetitive(benchmark, algo, repetitive_100k):
    """Compress 100 KB of repetitive text."""
    out = benchmark(compress_with_algo, repetitive_100k, algo)
    assert len(out) > 0


@pytest.mark.parametrize("algo", ALL_ALGOS, ids=lambda a: ALGO_NAMES[a])
def test_compress_source_code(benchmark, algo, source_code_100k):
    """Compress 100 KB of Python source code."""
    out = benchmark(compress_with_algo, source_code_100k, algo)
    assert len(out) > 0


@pytest.mark.parametrize("algo", ALL_ALGOS, ids=lambda a: ALGO_NAMES[a])
def test_compress_json(benchmark, algo, json_100k):
    """Compress 100 KB of JSON data."""
    out = benchmark(compress_with_algo, json_100k, algo)
    assert len(out) > 0


@pytest.mark.parametrize("algo", FAST_ALGOS, ids=lambda a: ALGO_NAMES[a])
def test_compress_random(benchmark, algo, random_100k):
    """Compress 100 KB of random bytes (incompressible worst case)."""
    out = benchmark(compress_with_algo, random_100k, algo)
    assert len(out) > 0


# ---------------------------------------------------------------------------
# 2. Raw decompress throughput
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("algo", ALL_ALGOS, ids=lambda a: ALGO_NAMES[a])
def test_decompress_repetitive(benchmark, algo, repetitive_100k):
    """Decompress 100 KB of pre-compressed repetitive text."""
    compressed = compress_with_algo(repetitive_100k, algo)
    out = benchmark(decompress_with_algo, compressed, algo)
    assert out == repetitive_100k


@pytest.mark.parametrize("algo", ALL_ALGOS, ids=lambda a: ALGO_NAMES[a])
def test_decompress_source_code(benchmark, algo, source_code_100k):
    """Decompress 100 KB of pre-compressed Python source."""
    compressed = compress_with_algo(source_code_100k, algo)
    out = benchmark(decompress_with_algo, compressed, algo)
    assert out == source_code_100k


@pytest.mark.parametrize("algo", FAST_ALGOS, ids=lambda a: ALGO_NAMES[a])
def test_decompress_random(benchmark, algo, random_100k):
    """Decompress 100 KB of pre-compressed random bytes."""
    compressed = compress_with_algo(random_100k, algo)
    out = benchmark(decompress_with_algo, compressed, algo)
    assert out == random_100k


# ---------------------------------------------------------------------------
# 3. Auto-select overhead (tries all candidates, picks smallest)
# ---------------------------------------------------------------------------

def test_compress_auto_repetitive(benchmark, repetitive_100k):
    """Auto-select compress on 100 KB repetitive text."""
    algo, compressed = benchmark(compress_auto, repetitive_100k)
    assert decompress_with_algo(compressed, algo) == repetitive_100k


def test_compress_auto_source_code(benchmark, source_code_100k):
    """Auto-select compress on 100 KB Python source."""
    algo, compressed = benchmark(compress_auto, source_code_100k)
    assert decompress_with_algo(compressed, algo) == source_code_100k


def test_compress_auto_json(benchmark, json_100k):
    """Auto-select compress on 100 KB JSON."""
    algo, compressed = benchmark(compress_auto, json_100k)
    assert decompress_with_algo(compressed, algo) == json_100k


def test_compress_auto_random(benchmark, random_100k):
    """Auto-select compress on 100 KB random bytes."""
    algo, compressed = benchmark(compress_auto, random_100k)
    assert decompress_with_algo(compressed, algo) == random_100k


# ---------------------------------------------------------------------------
# 4. Archive creation — per algorithm
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "algo", ["lzw", "lzw+zlib", "zlib", "lzma", "auto"], ids=str
)
def test_archive_compress_small_tree(benchmark, small_tree, tmp_path, algo):
    """Archive 50-file tree with each algorithm."""
    out = str(tmp_path / f"small_{algo.replace('+', '_')}.pm")
    archive = benchmark(pmole.compress, small_tree, output=out, algo=algo)
    assert os.path.exists(archive)


def test_archive_compress_large_tree_zlib(benchmark, large_tree, tmp_path):
    """Archive 5-large-file tree with zlib."""
    out = str(tmp_path / "large_zlib.pm")
    archive = benchmark(pmole.compress, large_tree, output=out, algo="zlib")
    assert os.path.exists(archive)


def test_archive_compress_large_tree_lzma(benchmark, large_tree, tmp_path):
    """Archive 5-large-file tree with lzma."""
    out = str(tmp_path / "large_lzma.pm")
    archive = benchmark(pmole.compress, large_tree, output=out, algo="lzma")
    assert os.path.exists(archive)


# ---------------------------------------------------------------------------
# 5. Archive decompression
# ---------------------------------------------------------------------------

def test_archive_decompress_small_tree(benchmark, small_tree, tmp_path):
    """Decompress 50-file archive."""
    archive = pmole.compress(small_tree, output=str(tmp_path / "src.pm"))
    out = str(tmp_path / "out")
    paths = benchmark(pmole.decompress, archive, output_dir=out)
    assert len(paths) == 50


def test_archive_decompress_large_tree(benchmark, large_tree, tmp_path):
    """Decompress 5-large-file archive."""
    archive = pmole.compress(large_tree, output=str(tmp_path / "large.pm"))
    out = str(tmp_path / "out")
    paths = benchmark(pmole.decompress, archive, output_dir=out)
    assert len(paths) == 5


# ---------------------------------------------------------------------------
# 6. Thread-count scaling
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("threads", [1, 2, 4], ids=lambda t: f"{t}t")
def test_thread_scaling_compress(benchmark, small_tree, tmp_path, threads):
    """Compress 50-file tree with 1 / 2 / 4 worker threads."""
    out = str(tmp_path / f"t{threads}.pm")
    archive = benchmark(pmole.compress, small_tree, output=out, threads=threads)
    assert os.path.exists(archive)


@pytest.mark.parametrize("threads", [1, 2, 4], ids=lambda t: f"{t}t")
def test_thread_scaling_decompress(benchmark, small_tree, tmp_path, threads):
    """Decompress 50-file archive with 1 / 2 / 4 worker threads."""
    archive = pmole.compress(small_tree, output=str(tmp_path / "src.pm"))
    out = str(tmp_path / f"out_t{threads}")
    paths = benchmark(pmole.decompress, archive, output_dir=out, threads=threads)
    assert len(paths) == 50


# ---------------------------------------------------------------------------
# 7. Verify and search timing
# ---------------------------------------------------------------------------

def test_verify_throughput(benchmark, small_tree, tmp_path):
    """In-memory verify of 50-file archive."""
    archive = pmole.compress(small_tree, output=str(tmp_path / "src.pm"))
    results = benchmark(pmole.verify, archive)
    assert all(r["ok"] for r in results)


def test_search_throughput(benchmark, small_tree, tmp_path):
    """Regex search across 50-file archive."""
    archive = pmole.compress(small_tree, output=str(tmp_path / "src.pm"))
    matches = benchmark(pmole.search, archive, pattern=r"def \w+")
    assert len(matches) > 0
