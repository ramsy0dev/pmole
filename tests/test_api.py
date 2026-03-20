"""Integration tests for the pmole public API."""

import os
import tempfile
from pathlib import Path

import pmole
from pmole import (
    ArchiveEntry,
    ALGO_LZW, ALGO_LZW_ZLIB, ALGO_ZLIB, ALGO_LZMA, ALGO_NAMES,
)
from pmole.compression import compress_with_algo, decompress_with_algo, compress_auto


# ---------------------------------------------------------------------------
# Compression layer
# ---------------------------------------------------------------------------

def test_all_algos_roundtrip():
    data = b"hello world " * 500
    for algo in (ALGO_LZW, ALGO_LZW_ZLIB, ALGO_ZLIB, ALGO_LZMA):
        compressed   = compress_with_algo(data, algo)
        decompressed = decompress_with_algo(compressed, algo)
        assert decompressed == data, f"roundtrip failed for {ALGO_NAMES[algo]}"


def test_all_algos_binary_roundtrip():
    data = os.urandom(4096)
    for algo in (ALGO_LZW, ALGO_LZW_ZLIB, ALGO_ZLIB, ALGO_LZMA):
        assert decompress_with_algo(compress_with_algo(data, algo), algo) == data


def test_compress_auto_returns_smallest(tmp_path):
    data = b"aaabbbccc" * 2000  # highly repetitive → LZMA or zlib should win
    algo, compressed = compress_auto(data)
    assert algo in ALGO_NAMES
    # Verify it's actually the smallest
    for other_algo in ALGO_NAMES:
        other = compress_with_algo(data, other_algo)
        assert len(compressed) <= len(other), (
            f"compress_auto chose {ALGO_NAMES[algo]} but {ALGO_NAMES[other_algo]} is smaller"
        )


def test_compress_auto_roundtrip():
    data = os.urandom(8192)
    algo, compressed = compress_auto(data)
    assert decompress_with_algo(compressed, algo) == data


def test_algo_name_strings_accepted():
    for name in ("lzw", "lzw+zlib", "zlib", "lzma"):
        archive_path = None
        with tempfile.TemporaryDirectory() as tmp:
            archive_path = pmole.compress("./pmole", output=f"{tmp}/out.pm", algo=name)
            assert Path(archive_path).exists()
            entries = pmole.list_files(archive_path)
            assert all(e.algo_name == name for e in entries)


def test_algo_auto_allows_mixed_algorithms(tmp_path):
    archive = pmole.compress("./pmole", output=str(tmp_path / "out.pm"), algo="auto")
    entries = pmole.list_files(archive)
    # All algos should be valid
    for e in entries:
        assert e.algo in ALGO_NAMES


# ---------------------------------------------------------------------------
# Archive API
# ---------------------------------------------------------------------------

def test_compress_directory_returns_path(tmp_path):
    archive = pmole.compress("./pmole", output=str(tmp_path / "out.pm"))
    assert archive == str(tmp_path / "out.pm")
    assert Path(archive).exists()


def test_list_files_returns_archive_entries(tmp_path):
    archive = pmole.compress("./pmole", output=str(tmp_path / "out.pm"))
    entries = pmole.list_files(archive)

    assert len(entries) > 0
    for e in entries:
        assert isinstance(e, ArchiveEntry)
        assert e.original_size > 0
        assert e.compressed_size > 0
        assert e.algo in ALGO_NAMES
        assert e.algo_name in ALGO_NAMES.values()
        assert 0.0 <= e.compression_ratio


def test_extract_single_file_roundtrip(tmp_path):
    archive = pmole.compress("./pmole", output=str(tmp_path / "out.pm"))
    out = pmole.extract(archive, "pmole/globals.py", output_dir=str(tmp_path / "ex"))

    assert Path(out).exists()
    assert open("pmole/globals.py", "rb").read() == open(out, "rb").read()


def test_decompress_returns_all_paths(tmp_path):
    archive = pmole.compress("./pmole", output=str(tmp_path / "out.pm"))
    entries = pmole.list_files(archive)
    paths   = pmole.decompress(archive, output_dir=str(tmp_path / "decomp"))

    assert len(paths) == len(entries)
    for p in paths:
        assert Path(p).exists()


def test_decompress_roundtrip(tmp_path):
    archive = pmole.compress("./pmole", output=str(tmp_path / "out.pm"))
    pmole.decompress(archive, output_dir=str(tmp_path / "decomp"))

    for entry in pmole.list_files(archive):
        src = Path(entry.path.replace("/", os.sep))
        dst = tmp_path / "decomp" / Path(*entry.path.split("/"))
        assert dst.exists(), f"{dst} missing"
        assert src.read_bytes() == dst.read_bytes(), f"{entry.path} roundtrip mismatch"


def test_lzw_compress_decompress_roundtrip():
    data = os.urandom(4096)
    codes = pmole.lzw_compress(data)
    assert isinstance(codes, list)
    assert pmole.lzw_decompress(codes) == data


def test_compress_missing_path_raises():
    try:
        pmole.compress("./nonexistent_path_xyz")
        assert False, "should have raised"
    except FileNotFoundError:
        pass


def test_extract_missing_target_raises(tmp_path):
    archive = pmole.compress("./pmole", output=str(tmp_path / "out.pm"))
    try:
        pmole.extract(archive, "does/not/exist.py")
        assert False, "should have raised"
    except FileNotFoundError:
        pass


def test_archive_entry_compression_ratio(tmp_path):
    archive = pmole.compress("./pmole", output=str(tmp_path / "out.pm"))
    for entry in pmole.list_files(archive):
        assert entry.compression_ratio == entry.compressed_size / entry.original_size


# ---------------------------------------------------------------------------
# Auto-exclusion
# ---------------------------------------------------------------------------

def test_exclude_filenames(tmp_path):
    (tmp_path / "keep.py").write_text("print('hi')")
    (tmp_path / ".env").write_text("SECRET=abc")
    (tmp_path / ".DS_Store").write_bytes(b"\x00" * 16)

    archive = pmole.compress(str(tmp_path), output=str(tmp_path / "out.pm"))
    paths = [e.path for e in pmole.list_files(archive)]

    assert any("keep.py" in p for p in paths)
    assert not any(".env" in p for p in paths)
    assert not any(".DS_Store" in p.lower() for p in paths)


def test_exclude_large_files(tmp_path):
    (tmp_path / "small.txt").write_bytes(b"x" * 100)
    (tmp_path / "big.bin").write_bytes(b"x" * (2 * 1024 * 1024))  # 2 MB

    archive = pmole.compress(
        str(tmp_path),
        output=str(tmp_path / "out.pm"),
        max_file_size_bytes=1024 * 1024,  # 1 MB limit
    )
    paths = [e.path for e in pmole.list_files(archive)]

    assert any("small.txt" in p for p in paths)
    assert not any("big.bin" in p for p in paths)


def test_exclude_lock_files(tmp_path):
    (tmp_path / "main.py").write_text("pass")
    (tmp_path / "poetry.lock").write_text("lots of lock content")

    archive = pmole.compress(str(tmp_path), output=str(tmp_path / "out.pm"))
    paths = [e.path for e in pmole.list_files(archive)]

    assert any("main.py" in p for p in paths)
    assert not any(".lock" in p for p in paths)


# ---------------------------------------------------------------------------
# Encryption
# ---------------------------------------------------------------------------

def test_encrypt_decrypt_roundtrip(tmp_path):
    archive = pmole.compress("./pmole", output=str(tmp_path / "enc.pm"), password="s3cr3t")
    assert pmole.is_encrypted(archive)
    paths = pmole.decompress(archive, output_dir=str(tmp_path / "out"), password="s3cr3t")
    assert len(paths) > 0
    for p in paths:
        assert Path(p).exists()


def test_encrypted_archive_requires_password(tmp_path):
    archive = pmole.compress("./pmole", output=str(tmp_path / "enc.pm"), password="pw")
    try:
        pmole.decompress(archive, output_dir=str(tmp_path / "out"))
        assert False, "should have raised"
    except ValueError:
        pass


def test_wrong_password_raises(tmp_path):
    archive = pmole.compress("./pmole", output=str(tmp_path / "enc.pm"), password="correct")
    try:
        pmole.decompress(archive, output_dir=str(tmp_path / "out"), password="wrong")
        assert False, "should have raised"
    except ValueError:
        pass


def test_is_encrypted_plain(tmp_path):
    archive = pmole.compress("./pmole", output=str(tmp_path / "plain.pm"))
    assert not pmole.is_encrypted(archive)


def test_is_encrypted_with_password(tmp_path):
    archive = pmole.compress("./pmole", output=str(tmp_path / "enc.pm"), password="x")
    assert pmole.is_encrypted(archive)


def test_list_files_encrypted(tmp_path):
    archive = pmole.compress("./pmole", output=str(tmp_path / "enc.pm"), password="pw")
    entries = pmole.list_files(archive, password="pw")
    assert len(entries) > 0


def test_extract_encrypted(tmp_path):
    archive = pmole.compress("./pmole", output=str(tmp_path / "enc.pm"), password="pw")
    out = pmole.extract(archive, "pmole/globals.py", output_dir=str(tmp_path / "ex"), password="pw")
    assert Path(out).exists()
    assert open("pmole/globals.py", "rb").read() == open(out, "rb").read()


def test_empty_password_raises(tmp_path):
    try:
        pmole.compress("./pmole", output=str(tmp_path / "enc.pm"), password="")
        assert False, "should have raised"
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------

def test_verify_clean_archive(tmp_path):
    archive = pmole.compress("./pmole", output=str(tmp_path / "out.pm"))
    results = pmole.verify(archive)
    assert all(r["ok"] for r in results)
    assert len(results) > 0


def test_verify_encrypted_archive(tmp_path):
    archive = pmole.compress("./pmole", output=str(tmp_path / "enc.pm"), password="pw")
    results = pmole.verify(archive, password="pw")
    assert all(r["ok"] for r in results)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def test_search_finds_matches(tmp_path):
    archive = pmole.compress("./pmole", output=str(tmp_path / "out.pm"))
    matches = pmole.search(archive, r"def compress")
    assert len(matches) > 0
    for m in matches:
        assert "path" in m
        assert "line_no" in m
        assert "line" in m
        assert "def compress" in m["line"]


def test_search_no_matches(tmp_path):
    archive = pmole.compress("./pmole", output=str(tmp_path / "out.pm"))
    matches = pmole.search(archive, r"XYZZY_NONEXISTENT_PATTERN_999")
    assert matches == []


def test_search_encrypted(tmp_path):
    archive = pmole.compress("./pmole", output=str(tmp_path / "enc.pm"), password="pw")
    matches = pmole.search(archive, r"def compress", password="pw")
    assert len(matches) > 0


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def test_stats_returns_correct_totals(tmp_path):
    archive = pmole.compress("./pmole", output=str(tmp_path / "out.pm"))
    entries = pmole.list_files(archive)
    s = pmole.stats(archive)

    assert s["total_files"] == len(entries)
    assert s["total_original"]   == sum(e.original_size   for e in entries)
    assert s["total_compressed"] == sum(e.compressed_size for e in entries)


def test_stats_by_extension_covers_all_files(tmp_path):
    archive = pmole.compress("./pmole", output=str(tmp_path / "out.pm"))
    s = pmole.stats(archive)
    total_from_ext = sum(b["files"] for b in s["by_extension"].values())
    assert total_from_ext == s["total_files"]


# ---------------------------------------------------------------------------
# .pmignore / .gitignore
# ---------------------------------------------------------------------------

def test_pmignore_excludes_files(tmp_path):
    (tmp_path / "keep.py").write_text("print('hi')")
    (tmp_path / "skip.log").write_text("log data")
    (tmp_path / ".pmignore").write_text("*.log\n")

    archive = pmole.compress(str(tmp_path), output=str(tmp_path / "out.pm"))
    paths = [e.path for e in pmole.list_files(archive)]

    assert any("keep.py" in p for p in paths)
    assert not any("skip.log" in p for p in paths)
    assert not any(".pmignore" in p for p in paths)


def test_gitignore_excludes_files(tmp_path):
    (tmp_path / "main.py").write_text("pass")
    (tmp_path / "secret.key").write_text("private")
    (tmp_path / ".gitignore").write_text("*.key\n")

    archive = pmole.compress(str(tmp_path), output=str(tmp_path / "out.pm"))
    paths = [e.path for e in pmole.list_files(archive)]

    assert any("main.py" in p for p in paths)
    assert not any("secret.key" in p for p in paths)
