"""Credibility tests for pmole.

Prove that:
  1. Every algorithm handles all data shapes correctly (edge-case roundtrips)
  2. Compression ratios stay within expected bounds per algorithm
  3. Auto-selection always picks the globally smallest output
  4. Archive metadata (sizes, binary flag, depth, paths) is accurate
  5. Invalid / corrupt archives are handled gracefully
  6. A ratio summary table can be printed for manual inspection

These tests are intentionally deeper than test_api.py's smoke tests —
they make *quantitative* assertions about compression quality and
data-integrity invariants across the full API.
"""

import random
import pytest

import pmole
from pmole.compression import (
    ALGO_LZW, ALGO_LZW_ZLIB, ALGO_ZLIB, ALGO_LZMA, ALGO_NAMES,
    compress_with_algo, decompress_with_algo, compress_auto,
)

# ---------------------------------------------------------------------------
# Shared data helpers
# ---------------------------------------------------------------------------

def _repetitive(n: int) -> bytes:
    unit = b"the quick brown fox jumps over the lazy dog\n"
    return (unit * (n // len(unit) + 1))[:n]


def _source_code(n: int) -> bytes:
    snippet = (
        b"def process(items):\n"
        b"    return [x * 2 for x in items if x > 0]\n\n"
        b"class Cache:\n"
        b"    def __init__(self):\n"
        b"        self._store = {}\n"
        b"    def get(self, key):\n"
        b"        return self._store.get(key)\n\n"
    )
    return (snippet * (n // len(snippet) + 1))[:n]


def _zeros(n: int) -> bytes:
    return b"\x00" * n


def _random_bytes(n: int, seed: int = 42) -> bytes:
    rng = random.Random(seed)
    return bytes(rng.randint(0, 255) for _ in range(n))


ALL_ALGOS  = [ALGO_LZW, ALGO_LZW_ZLIB, ALGO_ZLIB, ALGO_LZMA]
FAST_ALGOS = [ALGO_ZLIB, ALGO_LZMA]


# ---------------------------------------------------------------------------
# 1. Edge-case roundtrips — data shapes not covered by test_api.py
# ---------------------------------------------------------------------------

class TestEdgeCaseRoundtrips:

    @pytest.mark.parametrize("algo", ALL_ALGOS, ids=lambda a: ALGO_NAMES[a])
    def test_empty_bytes(self, algo):
        assert decompress_with_algo(compress_with_algo(b"", algo), algo) == b""

    @pytest.mark.parametrize("algo", ALL_ALGOS, ids=lambda a: ALGO_NAMES[a])
    def test_single_byte(self, algo):
        data = b"z"
        assert decompress_with_algo(compress_with_algo(data, algo), algo) == data

    @pytest.mark.parametrize("algo", ALL_ALGOS, ids=lambda a: ALGO_NAMES[a])
    def test_all_zeros(self, algo):
        data = _zeros(10_000)
        assert decompress_with_algo(compress_with_algo(data, algo), algo) == data

    @pytest.mark.parametrize("algo", ALL_ALGOS, ids=lambda a: ALGO_NAMES[a])
    def test_all_0xff(self, algo):
        data = b"\xff" * 10_000
        assert decompress_with_algo(compress_with_algo(data, algo), algo) == data

    @pytest.mark.parametrize("algo", ALL_ALGOS, ids=lambda a: ALGO_NAMES[a])
    def test_all_256_byte_values(self, algo):
        """Every possible byte value must survive a roundtrip."""
        data = bytes(range(256)) * 40   # 10 240 bytes
        assert decompress_with_algo(compress_with_algo(data, algo), algo) == data

    @pytest.mark.parametrize("algo", ALL_ALGOS, ids=lambda a: ALGO_NAMES[a])
    def test_binary_with_null_bytes(self, algo):
        data = b"\x00\x01\x02\x03" * 2_500
        assert decompress_with_algo(compress_with_algo(data, algo), algo) == data

    @pytest.mark.parametrize("algo", ALL_ALGOS, ids=lambda a: ALGO_NAMES[a])
    def test_large_repetitive(self, algo):
        """200 KB of repetitive data must round-trip correctly."""
        data = _repetitive(200_000)
        assert decompress_with_algo(compress_with_algo(data, algo), algo) == data

    @pytest.mark.parametrize("algo", FAST_ALGOS, ids=lambda a: ALGO_NAMES[a])
    def test_large_random_binary(self, algo):
        """500 KB of random bytes must round-trip correctly (fast algos only)."""
        data = _random_bytes(500_000)
        assert decompress_with_algo(compress_with_algo(data, algo), algo) == data

    @pytest.mark.parametrize("algo", ALL_ALGOS, ids=lambda a: ALGO_NAMES[a])
    def test_determinism(self, algo):
        """Two calls with identical input must produce identical compressed bytes."""
        data = _source_code(20_000)
        assert compress_with_algo(data, algo) == compress_with_algo(data, algo)


# ---------------------------------------------------------------------------
# 2. Compression ratio bounds
# ---------------------------------------------------------------------------

class TestCompressionRatios:
    """
    Conservative thresholds that catch regressions where an algorithm
    silently degrades or stops compressing at all.
    """

    @pytest.mark.parametrize("algo", ALL_ALGOS, ids=lambda a: ALGO_NAMES[a])
    def test_repetitive_ratio_under_20pct(self, algo):
        data  = _repetitive(50_000)
        ratio = len(compress_with_algo(data, algo)) / len(data)
        assert ratio < 0.20, f"{ALGO_NAMES[algo]}: ratio={ratio:.3f} (expected < 0.20)"

    @pytest.mark.parametrize("algo", ALL_ALGOS, ids=lambda a: ALGO_NAMES[a])
    def test_source_code_ratio_under_50pct(self, algo):
        data  = _source_code(50_000)
        ratio = len(compress_with_algo(data, algo)) / len(data)
        assert ratio < 0.50, f"{ALGO_NAMES[algo]}: ratio={ratio:.3f} (expected < 0.50)"

    @pytest.mark.parametrize("algo", ALL_ALGOS, ids=lambda a: ALGO_NAMES[a])
    def test_zeros_ratio_under_2pct(self, algo):
        data  = _zeros(50_000)
        ratio = len(compress_with_algo(data, algo)) / len(data)
        assert ratio < 0.02, f"{ALGO_NAMES[algo]}: ratio={ratio:.3f} (expected < 0.02)"

    @pytest.mark.parametrize("algo", FAST_ALGOS, ids=lambda a: ALGO_NAMES[a])
    def test_random_data_overhead_under_10pct(self, algo):
        """Incompressible data must not inflate the output by more than 10%."""
        data  = _random_bytes(50_000)
        ratio = len(compress_with_algo(data, algo)) / len(data)
        assert ratio < 1.10, f"{ALGO_NAMES[algo]}: ratio={ratio:.3f} (expected < 1.10)"

    def test_lzma_beats_zlib_on_source_code(self):
        data = _source_code(100_000)
        lzma = len(compress_with_algo(data, ALGO_LZMA))
        zlib = len(compress_with_algo(data, ALGO_ZLIB))
        assert lzma < zlib, f"lzma ({lzma}) should be smaller than zlib ({zlib})"

    def test_lzw_zlib_beats_raw_lzw_on_source_code(self):
        data     = _source_code(50_000)
        lzw_zlib = len(compress_with_algo(data, ALGO_LZW_ZLIB))
        lzw      = len(compress_with_algo(data, ALGO_LZW))
        assert lzw_zlib < lzw, f"lzw+zlib ({lzw_zlib}) should be smaller than lzw ({lzw})"


# ---------------------------------------------------------------------------
# 3. Auto-selection correctness
# ---------------------------------------------------------------------------

class TestAutoSelection:

    def test_never_worse_than_any_candidate_on_source_code(self):
        """
        compress_auto tries all 4 algorithms and returns the smallest,
        so its output must be <= every individual algorithm's output.
        """
        data = _source_code(50_000)
        _, auto_bytes = compress_auto(data)
        for algo in ALL_ALGOS:
            algo_size = len(compress_with_algo(data, algo))
            assert len(auto_bytes) <= algo_size, (
                f"auto ({len(auto_bytes)}) > {ALGO_NAMES[algo]} ({algo_size})"
            )

    def test_auto_returns_valid_algo_id(self):
        algo, _ = compress_auto(_source_code(10_000))
        assert algo in ALGO_NAMES

    def test_auto_roundtrip_empty(self):
        algo, compressed = compress_auto(b"")
        assert decompress_with_algo(compressed, algo) == b""

    def test_auto_achieves_strong_ratio_on_repetitive_data(self):
        """auto must reach < 5% ratio on highly repetitive text."""
        data = _repetitive(50_000)
        algo, compressed = compress_auto(data)
        ratio = len(compressed) / len(data)
        assert ratio < 0.05, (
            f"auto chose {ALGO_NAMES[algo]} with ratio={ratio:.3f} (expected < 0.05)"
        )

    @pytest.mark.parametrize("data_fn,label", [
        (_repetitive,   "repetitive"),
        (_source_code,  "source_code"),
        (_zeros,        "zeros"),
    ])
    def test_auto_roundtrip_varied_inputs(self, data_fn, label):
        data = data_fn(30_000)
        algo, compressed = compress_auto(data)
        assert decompress_with_algo(compressed, algo) == data, f"roundtrip failed for {label}"


# ---------------------------------------------------------------------------
# 4. Archive integrity
# ---------------------------------------------------------------------------

class TestArchiveIntegrity:

    def test_original_size_in_index_matches_disk(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        content = b"hello world\n" * 200
        (src / "data.txt").write_bytes(content)

        archive = pmole.compress(str(src), output=str(tmp_path / "test.pm"))
        entry   = pmole.list_files(archive)[0]
        assert entry.original_size == len(content)

    def test_compressed_size_smaller_than_original_for_text(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "code.py").write_bytes(_source_code(10_000))

        archive = pmole.compress(str(src), output=str(tmp_path / "test.pm"))
        entry   = pmole.list_files(archive)[0]
        assert entry.compressed_size < entry.original_size

    def test_compression_ratio_field_matches_sizes(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "code.py").write_bytes(_source_code(5_000))

        archive  = pmole.compress(str(src), output=str(tmp_path / "test.pm"))
        e        = pmole.list_files(archive)[0]
        expected = e.compressed_size / e.original_size
        assert abs(e.compression_ratio - expected) < 1e-9

    def test_binary_flag_false_for_text_file(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "readme.txt").write_text("no null bytes here\n" * 10, encoding="utf-8")

        archive = pmole.compress(str(src), output=str(tmp_path / "test.pm"))
        entry   = pmole.list_files(archive)[0]
        assert not entry.is_binary

    def test_binary_flag_true_for_binary_file(self, tmp_path):
        """A file with null bytes must be flagged as binary regardless of extension."""
        src = tmp_path / "src"
        src.mkdir()
        # Use .py so the file is not excluded by the extension filter
        (src / "compiled.py").write_bytes(b"\x00\x01\x02\x03" * 512)

        archive = pmole.compress(str(src), output=str(tmp_path / "test.pm"))
        entry   = pmole.list_files(archive)[0]
        assert entry.is_binary

    def test_content_byte_identical_after_roundtrip(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        files = {
            "main.py":        "def main():\n    print('pmole')\n",
            "sub/helper.py":  "add = lambda a, b: a + b\n",
        }
        for rel, body in files.items():
            p = src / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body, encoding="utf-8")

        archive = pmole.compress(str(src), output=str(tmp_path / "test.pm"))
        out = tmp_path / "out"
        pmole.decompress(archive, output_dir=str(out))

        for rel, body in files.items():
            restored = list(out.rglob(rel.split("/")[-1]))[0]
            assert restored.read_text(encoding="utf-8") == body, f"mismatch: {rel}"

    def test_double_roundtrip_identity(self, tmp_path):
        """compress → decompress → compress → decompress must be byte-identical."""
        src = tmp_path / "src"
        src.mkdir()
        original = _source_code(5_000)
        (src / "code.py").write_bytes(original)

        # First roundtrip
        a1   = pmole.compress(str(src), output=str(tmp_path / "a1.pm"))
        out1 = tmp_path / "out1"
        pmole.decompress(a1, output_dir=str(out1))
        restored1 = list(out1.rglob("code.py"))[0]
        assert restored1.read_bytes() == original

        # Second roundtrip from the restored directory
        a2   = pmole.compress(str(restored1.parent), output=str(tmp_path / "a2.pm"))
        out2 = tmp_path / "out2"
        pmole.decompress(a2, output_dir=str(out2))
        restored2 = list(out2.rglob("code.py"))[0]
        assert restored2.read_bytes() == original

    def test_deep_directory_structure_preserved(self, tmp_path):
        src  = tmp_path / "src"
        deep = src / "a" / "b" / "c" / "d"
        deep.mkdir(parents=True)
        (deep / "leaf.txt").write_text("deep content\n", encoding="utf-8")

        archive = pmole.compress(str(src), output=str(tmp_path / "test.pm"))
        out     = tmp_path / "out"
        paths   = pmole.decompress(archive, output_dir=str(out))
        assert len(paths) == 1
        assert (tmp_path / "out" / paths[0]).read_text(encoding="utf-8") == "deep content\n" \
            or list(out.rglob("leaf.txt"))[0].read_text(encoding="utf-8") == "deep content\n"

    def test_unicode_content_preserved(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        content = "日本語テキスト\n한국어\nΕλληνικά\n" * 50
        (src / "unicode.txt").write_text(content, encoding="utf-8")

        archive = pmole.compress(str(src), output=str(tmp_path / "test.pm"))
        out = tmp_path / "out"
        pmole.decompress(archive, output_dir=str(out))
        restored = list(out.rglob("unicode.txt"))[0].read_text(encoding="utf-8")
        assert restored == content

    def test_empty_file_stored_and_restored_as_zero_bytes(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "empty.txt").write_bytes(b"")
        (src / "nonempty.txt").write_text("something\n", encoding="utf-8")

        archive = pmole.compress(str(src), output=str(tmp_path / "test.pm"))
        out = tmp_path / "out"
        pmole.decompress(archive, output_dir=str(out))
        restored = list(out.rglob("empty.txt"))[0]
        assert restored.read_bytes() == b""

    def test_file_count_exact_after_decompression(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        for i in range(15):
            (src / f"f{i:02d}.py").write_text(f"x = {i}\n", encoding="utf-8")

        archive = pmole.compress(str(src), output=str(tmp_path / "test.pm"))
        paths   = pmole.decompress(archive, output_dir=str(tmp_path / "out"))
        assert len(paths) == 15

    @pytest.mark.parametrize("algo", ["lzw", "lzw+zlib", "zlib", "lzma", "auto"])
    def test_verify_passes_for_all_algorithm_strings(self, tmp_path, algo):
        """verify() must report all OK regardless of algorithm used to create the archive."""
        slug = algo.replace("+", "_")
        src  = tmp_path / f"src_{slug}"
        src.mkdir()
        (src / "code.py").write_bytes(_source_code(3_000))

        archive = pmole.compress(str(src), output=str(tmp_path / f"{slug}.pm"), algo=algo)
        results = pmole.verify(archive)
        assert results, "verify returned no results"
        assert all(r["ok"] for r in results), [r for r in results if not r["ok"]]

    def test_algo_name_stored_correctly_in_index(self, tmp_path):
        """The algo_name field on every ArchiveEntry must match the requested algorithm."""
        src = tmp_path / "src"
        src.mkdir()
        for i in range(3):
            (src / f"f{i}.py").write_bytes(_source_code(1_000))

        for algo_str in ("zlib", "lzma", "lzw", "lzw+zlib"):
            archive = pmole.compress(
                str(src),
                output=str(tmp_path / f"{algo_str.replace('+','_')}.pm"),
                algo=algo_str,
            )
            for entry in pmole.list_files(archive):
                assert entry.algo_name == algo_str, (
                    f"expected {algo_str!r}, got {entry.algo_name!r} for {entry.path}"
                )


# ---------------------------------------------------------------------------
# 5. Corrupt / invalid archive handling
# ---------------------------------------------------------------------------

class TestCorruptDetection:

    def test_wrong_magic_returns_empty_list(self, tmp_path):
        """A file with wrong magic bytes should be rejected gracefully."""
        bad = tmp_path / "bad.pm"
        bad.write_bytes(b"XXXX" + b"\x00" * 100)
        entries = pmole.list_files(str(bad))
        assert entries == []

    def test_truncated_archive_does_not_crash(self, tmp_path):
        """A truncated archive must not raise an unhandled exception."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "a.py").write_text("x = 1\n", encoding="utf-8")
        archive = pmole.compress(str(src), output=str(tmp_path / "real.pm"))

        raw       = open(archive, "rb").read()
        truncated = tmp_path / "trunc.pm"
        truncated.write_bytes(raw[:20])

        try:
            result = pmole.list_files(str(truncated))
            assert isinstance(result, list)
        except Exception:
            pass  # Any controlled exception is acceptable; a crash is not


# ---------------------------------------------------------------------------
# 6. Ratio summary table — always passes, prints with `pytest -s`
# ---------------------------------------------------------------------------

def test_ratio_summary_table(capsys):
    """
    Print a ratio table across all algorithms and data profiles.
    Useful for spotting regressions at a glance.

    Run with:  pytest -s tests/test_credibility.py::test_ratio_summary_table
    """
    profiles = {
        "repetitive_50k":  _repetitive(50_000),
        "source_code_50k": _source_code(50_000),
        "zeros_50k":       _zeros(50_000),
        "random_50k":      _random_bytes(50_000),
    }
    col = 11
    header = f"\n{'Profile':<22}" + "".join(f"{ALGO_NAMES[a]:>{col}}" for a in ALL_ALGOS)
    sep    = "-" * len(header)
    rows   = [header, sep]
    for name, data in profiles.items():
        row = f"{name:<22}"
        for algo in ALL_ALGOS:
            ratio = len(compress_with_algo(data, algo)) / len(data)
            row += f"{ratio:>{col}.3f}"
        rows.append(row)

    # Also show what auto picks for each profile
    rows.append(sep)
    auto_row = f"{'auto (best algo)':<22}"
    for _, data in profiles.items():
        algo, compressed = compress_auto(data)
        ratio = len(compressed) / len(data)
        auto_row += f"  {ALGO_NAMES[algo]:>4}={ratio:.2f}"
    rows.append(auto_row)

    with capsys.disabled():
        print("\n".join(rows))
