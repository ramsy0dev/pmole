# MIT License

# Copyright (c) 2025 ramsy0dev

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""
pmole public API
================

Quick start::

    import pmole

    # Compress (auto-selects best algorithm per file)
    archive = pmole.compress("./myproject")
    archive = pmole.compress("./myproject", output="out.pm", algo="lzma")
    archive = pmole.compress("./myproject", password="secret")

    # List contents without decompressing
    for entry in pmole.list_files(archive):
        print(entry.path, entry.original_size, entry.algo_name)

    # Search inside the archive (no decompression to disk)
    for hit in pmole.search(archive, r"def \\w+"):
        print(f"{hit['path']}:{hit['line_no']}  {hit['line']}")

    # Verify archive integrity
    results = pmole.verify(archive)

    # Extract a single file
    pmole.extract(archive, "myproject/main.py", output_dir="/tmp/out")

    # Full decompress
    paths = pmole.decompress(archive, output_dir="/tmp/restored")

    # Raw LZW access
    codes = pmole.lzw_compress(b"hello world")
    data  = pmole.lzw_decompress(codes)
"""

__all__ = [
    "ArchiveEntry",
    "compress",
    "decompress",
    "list_files",
    "extract",
    "verify",
    "search",
    "stats",
    "is_encrypted",
    "lzw_compress",
    "lzw_decompress",
]

from dataclasses import dataclass
from pathlib import Path

from pmole.pmole import Pmole
from pmole.lzw import LZW
from pmole.compression import ALGO_LZW, ALGO_LZW_ZLIB, ALGO_ZLIB, ALGO_LZMA, ALGO_NAMES
from pmole.crypto import _ENC_MAGIC
from pmole.globals import (
    EXCLUDE_EXTENSIONS,
    EXCLUDE_DIRECTORIES,
    EXCLUDE_FILENAMES,
    MAX_FILE_SIZE_BYTES,
)

# Map string names accepted by the public API to internal algorithm IDs.
_ALGO_BY_NAME: dict[str, int] = {
    "lzw":      ALGO_LZW,
    "lzw+zlib": ALGO_LZW_ZLIB,
    "zlib":     ALGO_ZLIB,
    "lzma":     ALGO_LZMA,
    "auto":     -1,   # sentinel: auto-select
}


def _resolve_algo(algo: int | str | None) -> int | None:
    """Convert a user-supplied algo value to an internal ID or ``None`` (auto)."""
    if algo is None or algo == "auto" or algo == -1:
        return None
    if isinstance(algo, int):
        if algo not in ALGO_NAMES:
            raise ValueError(f"Unknown algorithm id {algo!r}. Valid ids: {list(ALGO_NAMES)}")
        return algo
    if isinstance(algo, str):
        key = algo.lower()
        if key not in _ALGO_BY_NAME:
            raise ValueError(
                f"Unknown algorithm {algo!r}. Valid names: {list(_ALGO_BY_NAME)}"
            )
        val = _ALGO_BY_NAME[key]
        return None if val == -1 else val
    raise TypeError(f"algo must be int, str, or None, got {type(algo).__name__!r}")


@dataclass
class ArchiveEntry:
    """Metadata for a single file stored inside a ``.pm`` archive."""
    path:             str
    original_size:    int
    compressed_size:  int
    is_binary:        bool
    algo:             int
    data_offset:      int

    @property
    def compression_ratio(self) -> float:
        """Ratio of compressed to original size (lower = better compression)."""
        if self.original_size == 0:
            return 0.0
        return self.compressed_size / self.original_size

    @property
    def algo_name(self) -> str:
        """Human-readable name of the compression algorithm used."""
        return ALGO_NAMES.get(self.algo, f"unknown({self.algo})")


# ── Core operations ──────────────────────────────────────────────────────────

def compress(
    path: str,
    output: str | None = None,
    algo: int | str | None = None,
    threads: int = 3,
    password: str | None = None,
    exclude_extensions: list[str] | None = None,
    exclude_directories: list[str] | None = None,
    exclude_filenames: list[str] | None = None,
    max_file_size_bytes: int | None = None,
) -> str:
    """
    Compress a file or directory into a ``.pm`` archive.

    Parameters
    ----------
    path:
        File or directory to compress.
    output:
        Destination ``.pm`` path. Defaults to ``<name>.pm``.
    algo:
        Compression algorithm — ``ALGO_*`` constant, name string
        (``"lzw"``, ``"lzw+zlib"``, ``"zlib"``, ``"lzma"``), or ``"auto"``
        (default). ``"auto"`` benchmarks every algorithm per file.
    threads:
        Parallel worker threads (default 3).
    password:
        If provided, the archive is AES-256-GCM encrypted with this password.
        Use the same password for all read operations.
    exclude_extensions / exclude_directories / exclude_filenames / max_file_size_bytes:
        Override the default exclusion filters.  Defaults come from
        ``pmole.EXCLUDE_*`` and ``pmole.MAX_FILE_SIZE_BYTES``.

    Returns
    -------
    str
        Path of the created archive.

    Raises
    ------
    FileNotFoundError
        If *path* does not exist.
    ValueError
        If *algo* is not a recognised name or id, or *password* is empty.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Path not found: {path}")

    resolved_algo = _resolve_algo(algo)
    exc_ext   = exclude_extensions   if exclude_extensions   is not None else list(EXCLUDE_EXTENSIONS)
    exc_dir   = exclude_directories  if exclude_directories  is not None else list(EXCLUDE_DIRECTORIES)
    exc_names = exclude_filenames    if exclude_filenames    is not None else list(EXCLUDE_FILENAMES)
    max_size  = max_file_size_bytes  if max_file_size_bytes  is not None else MAX_FILE_SIZE_BYTES

    pmole_obj = Pmole()
    kwargs = dict(
        output_path=output,
        algo=resolved_algo,
        threads=threads,
        password=password,
        exclude_extensions=exc_ext,
        exclude_directories=exc_dir,
        exclude_filenames=exc_names,
        max_file_size_bytes=max_size,
    )
    if p.is_file():
        return pmole_obj.compress(file_path=str(p), **kwargs)
    return pmole_obj.compress(directory_path=str(p), **kwargs)


def decompress(
    pm_file_path: str,
    output_dir: str = ".",
    threads: int = 3,
    password: str | None = None,
) -> list[str]:
    """
    Decompress all files from a ``.pm`` archive.

    Returns
    -------
    list[str]
        Paths of every file written to disk.
    """
    if not Path(pm_file_path).exists():
        raise FileNotFoundError(f"Archive not found: {pm_file_path}")
    return Pmole().decompress(
        file_path=pm_file_path,
        output_dir=output_dir,
        threads=threads,
        password=password,
    )


def list_files(pm_file_path: str, password: str | None = None) -> list[ArchiveEntry]:
    """
    List all entries in a ``.pm`` archive without reading any compressed data.
    """
    if not Path(pm_file_path).exists():
        raise FileNotFoundError(f"Archive not found: {pm_file_path}")
    return [ArchiveEntry(**e) for e in Pmole().list_files(pm_file_path, password=password)]


def extract(
    pm_file_path: str,
    target: str,
    output_dir: str = ".",
    password: str | None = None,
) -> str:
    """
    Extract a single file from a ``.pm`` archive.

    Returns
    -------
    str
        Path of the extracted file on disk.

    Raises
    ------
    FileNotFoundError
        If the archive or *target* does not exist.
    """
    if not Path(pm_file_path).exists():
        raise FileNotFoundError(f"Archive not found: {pm_file_path}")
    return Pmole().extract(
        pm_file_path=pm_file_path,
        target_path=target,
        output_dir=output_dir,
        password=password,
    )


# ── Codebase-specific operations ─────────────────────────────────────────────

def verify(
    pm_file_path: str,
    threads: int = 3,
    password: str | None = None,
) -> list[dict]:
    """
    Verify archive integrity by decompressing every file in-memory and
    checking the decompressed size against the stored index value.
    Nothing is written to disk.

    Returns
    -------
    list[dict]
        One ``{path, ok, error}`` dict per archived file.
        ``ok`` is ``True`` if the file decompresses cleanly and the size
        matches; ``False`` with a description in ``error`` otherwise.
    """
    if not Path(pm_file_path).exists():
        raise FileNotFoundError(f"Archive not found: {pm_file_path}")
    return Pmole().verify(pm_file_path, threads=threads, password=password)


def search(
    pm_file_path: str,
    pattern: str,
    threads: int = 3,
    password: str | None = None,
) -> list[dict]:
    """
    Search for a regex *pattern* in all text files stored in the archive.
    Binary files are skipped.  Nothing is written to disk.

    Returns
    -------
    list[dict]
        Flat list of ``{path, line_no, line}`` dicts ordered by file then
        line number.
    """
    if not Path(pm_file_path).exists():
        raise FileNotFoundError(f"Archive not found: {pm_file_path}")
    return Pmole().search(pm_file_path, pattern=pattern, threads=threads, password=password)


def stats(pm_file_path: str, password: str | None = None) -> dict:
    """
    Return compression statistics for a ``.pm`` archive, grouped by file
    extension.

    Returns
    -------
    dict with keys:

    ``total_files`` : int
    ``total_original`` : int
    ``total_compressed`` : int
    ``by_extension`` : dict[str, dict]
        Keys are extensions (``".py"``, ``".md"``, ``""`` for no extension).
        Each value is ``{files, original, compressed}``.
    """
    entries = list_files(pm_file_path, password=password)

    by_ext: dict[str, dict] = {}
    for e in entries:
        ext = Path(e.path).suffix.lower() or "(no ext)"
        bucket = by_ext.setdefault(ext, {"files": 0, "original": 0, "compressed": 0})
        bucket["files"]      += 1
        bucket["original"]   += e.original_size
        bucket["compressed"] += e.compressed_size

    return {
        "total_files":      len(entries),
        "total_original":   sum(e.original_size   for e in entries),
        "total_compressed": sum(e.compressed_size for e in entries),
        "by_extension":     by_ext,
    }


def is_encrypted(pm_file_path: str) -> bool:
    """Return ``True`` if the archive is AES-256-GCM encrypted."""
    if not Path(pm_file_path).exists():
        raise FileNotFoundError(f"Archive not found: {pm_file_path}")
    with open(pm_file_path, "rb") as f:
        return f.read(4) == _ENC_MAGIC


# ── Raw algorithm access ──────────────────────────────────────────────────────

def lzw_compress(data: bytes) -> list[int]:
    """Compress raw bytes with LZW. Returns the uint16 code list."""
    return LZW().compress(data=data)


def lzw_decompress(codes: list[int]) -> bytes:
    """Decompress a code list produced by :func:`lzw_compress`."""
    return LZW().decompress(compressed_data=codes)
