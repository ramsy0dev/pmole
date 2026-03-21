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

__all__ = [
    "Pmole"
]

import contextlib
import os
import re
import struct
import tempfile
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path

import pathspec
from loguru import logger

from pmole.compression import (
    ALGO_NAMES,
    compress_auto,
    compress_with_algo,
    decompress_with_algo,
)
from pmole.crypto import _ENC_MAGIC, decrypt_archive, encrypt_archive
from pmole.globals import (
    EXCLUDE_DIRECTORIES,
    EXCLUDE_EXTENSIONS,
    EXCLUDE_FILENAMES,
    MAX_FILE_SIZE_BYTES,
)
from pmole.utils import list_files_in_directory, measure_time

# ── Format constants ────────────────────────────────────────────────────────
PM_MAGIC       = b"PM\x03\x00"
PM_HEADER_SIZE = 16

_FILE_SECTION_HEADER_SIZE = 18
_FILE_SECTION_HEADER_FMT  = "<QQBB"   # orig, compr, is_binary, algo

_INDEX_ENTRY_FIXED_SIZE = 28
_INDEX_ENTRY_FMT        = "<QQQBBH"  # data_offset, orig, compr, is_bin, algo, path_len


# ── Ignore-spec loading ──────────────────────────────────────────────────────

def _load_ignore_spec(directory: str):
    """
    Load ``.pmignore`` (preferred) or ``.gitignore`` from *directory*.
    Returns a ``pathspec.PathSpec`` or ``None`` if neither file exists.
    """
    for name in (".pmignore", ".gitignore"):
        ignore_file = Path(directory) / name
        if ignore_file.exists():
            try:
                lines = ignore_file.read_text(encoding="utf-8", errors="ignore").splitlines()
                spec = pathspec.PathSpec.from_lines("gitignore", lines)
                logger.info(f"ignore spec  '{ignore_file}'")
                return spec
            except Exception as exc:
                logger.warning(f"Could not parse '{ignore_file}': {exc}")
    return None


# ── Encrypted-archive helper ────────────────────────────────────────────────

@contextlib.contextmanager
def _open_pm(file_path: str, password: str | None):
    """
    Context manager that yields the effective archive path to operate on.

    * Non-encrypted archives: yields *file_path* unchanged.
    * Encrypted archives: decrypts to a temp file, yields its path, deletes it
      on exit.  The temp file persists for the entire ``with`` block so that
      worker threads opened inside the block remain valid.
    """
    with open(file_path, "rb") as f:
        magic = f.read(4)

    if magic == _ENC_MAGIC:
        if password is None:
            raise ValueError("Archive is password-protected. Provide a password.")
        with open(file_path, "rb") as f:
            raw = f.read()
        plain = decrypt_archive(raw, password)
        fd, tmp_path = tempfile.mkstemp(suffix=".pm")
        try:
            os.close(fd)
            with open(tmp_path, "wb") as f:
                f.write(plain)
            yield tmp_path
        finally:
            with contextlib.suppress(OSError):
                os.unlink(tmp_path)
    else:
        yield file_path


# ── Module-level task functions ──────────────────────────────────────────────

def _compress_file_task(fp: str, algo: int | None) -> tuple:
    """
    Read and compress one file.
    Returns ``(fp, orig_size, is_binary, chosen_algo, compressed_bytes)``.
    Runs in a thread pool; zlib/lzma release the GIL so threads parallelize.
    """
    orig_size = os.path.getsize(fp)
    with open(fp, "rb") as fh:
        is_binary = b"\x00" in fh.read(8192)
    data = Path(fp).read_bytes()

    if algo is None:
        chosen_algo, compressed = compress_auto(data)
    else:
        chosen_algo = algo
        compressed  = compress_with_algo(data, algo)

    logger.info(
        f"pack  {fp}  {orig_size} B → {len(compressed)} B  [{ALGO_NAMES[chosen_algo]}]"
    )
    return (fp, orig_size, is_binary, chosen_algo, compressed)


def _decompress_file_task(
    pm_file_path: str, entry: dict, output_dir: str
) -> str:
    """
    Decompress one archived file and write it to disk.
    Opens the archive independently so multiple threads can work in parallel.
    Returns the path written.
    """
    with open(pm_file_path, "rb") as f:
        f.seek(entry["data_offset"] + _FILE_SECTION_HEADER_SIZE)
        compressed_bytes = f.read(entry["compressed_size"])

    decompressed = decompress_with_algo(compressed_bytes, entry["algo"])

    path_parts = entry["path"].split("/")
    out_path   = Path(output_dir) / Path(*path_parts)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(decompressed)
    out_str = str(out_path)
    logger.info(f"unpack  {entry['path']}  →  {out_str}")
    return out_str


def _verify_file_task(pm_file_path: str, entry: dict) -> dict:
    """
    Decompress one file in-memory and verify the decompressed size.
    Returns ``{path, ok, error}``.
    """
    try:
        with open(pm_file_path, "rb") as f:
            f.seek(entry["data_offset"] + _FILE_SECTION_HEADER_SIZE)
            compressed_bytes = f.read(entry["compressed_size"])
        data = decompress_with_algo(compressed_bytes, entry["algo"])
        if len(data) != entry["original_size"]:
            return {
                "path":  entry["path"],
                "ok":    False,
                "error": (
                    f"Size mismatch: expected {entry['original_size']} B, "
                    f"got {len(data)} B"
                ),
            }
        return {"path": entry["path"], "ok": True, "error": None}
    except Exception as exc:
        return {"path": entry["path"], "ok": False, "error": str(exc)}


def _search_file_task(pm_file_path: str, entry: dict, pattern: str) -> list[dict]:
    """
    Search for *pattern* (regex) in one archived text file.
    Binary files are skipped.
    Returns a list of ``{path, line_no, line}`` match dicts.
    """
    if entry["is_binary"]:
        return []
    try:
        with open(pm_file_path, "rb") as f:
            f.seek(entry["data_offset"] + _FILE_SECTION_HEADER_SIZE)
            compressed_bytes = f.read(entry["compressed_size"])
        text = decompress_with_algo(compressed_bytes, entry["algo"]).decode(
            "utf-8", errors="replace"
        )
        matches = []
        compiled = re.compile(pattern)
        for line_no, line in enumerate(text.splitlines(), 1):
            if compiled.search(line):
                matches.append({
                    "path":    entry["path"],
                    "line_no": line_no,
                    "line":    line.rstrip("\r\n"),
                })
        return matches
    except Exception:
        return []


# ── Internal helpers ─────────────────────────────────────────────────────────

def _read_index(f) -> list[dict]:
    """Read and return the index from an open ``.pm`` file handle."""
    magic = f.read(4)
    if magic != PM_MAGIC:
        logger.error(f"invalid archive: expected magic {PM_MAGIC!r}, got {magic!r}")
        return []

    _file_count, index_offset = struct.unpack("<IQ", f.read(12))
    f.seek(index_offset)

    entry_count = struct.unpack("<I", f.read(4))[0]
    entries: list[dict] = []
    for _ in range(entry_count):
        data_offset, orig_size, compr_size, is_bin, algo, path_len = struct.unpack(
            _INDEX_ENTRY_FMT, f.read(_INDEX_ENTRY_FIXED_SIZE)
        )
        path = f.read(path_len).decode("utf-8")
        entries.append({
            "path":            path,
            "original_size":   orig_size,
            "compressed_size": compr_size,
            "is_binary":       bool(is_bin),
            "algo":            algo,
            "data_offset":     data_offset,
        })
    return entries


# ── PMFileWriter ─────────────────────────────────────────────────────────────

class PMFileWriter:
    """
    Context manager that writes a binary ``.pm`` archive in a single forward
    pass, then patches the header once all files are written.
    """
    def __init__(self, output_path: str) -> None:
        self.output_path = output_path
        self.entries: list[tuple] = []
        self._file = None

    def __enter__(self):
        Path(self.output_path).parent.mkdir(parents=True, exist_ok=True)
        self._file = open(self.output_path, "wb")
        self._file.write(PM_MAGIC)
        self._file.write(struct.pack("<I", 0))  # file_count — patched later
        self._file.write(struct.pack("<Q", 0))  # index_offset — patched later
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.finalize()
        self._file.close()

    def add_compressed(
        self,
        archived_path: str,
        orig_size: int,
        is_binary: bool,
        algo: int,
        compressed_bytes: bytes,
    ) -> None:
        """Write pre-compressed data for one file into the archive."""
        data_offset     = self._file.tell()
        compressed_size = len(compressed_bytes)

        self._file.write(
            struct.pack(_FILE_SECTION_HEADER_FMT, orig_size, compressed_size, int(is_binary), algo)
        )
        self._file.write(compressed_bytes)
        self.entries.append(
            (data_offset, orig_size, compressed_size, int(is_binary), algo, archived_path)
        )

    def finalize(self) -> None:
        """Write the index table and back-patch file_count + index_offset."""
        index_offset = self._file.tell()

        self._file.write(struct.pack("<I", len(self.entries)))
        for data_offset, orig_size, compr_size, is_bin, algo, path in self.entries:
            norm_path  = path.replace("\\", "/")
            path_bytes = norm_path.encode("utf-8")
            self._file.write(
                struct.pack(
                    _INDEX_ENTRY_FMT,
                    data_offset, orig_size, compr_size, is_bin, algo, len(path_bytes),
                )
            )
            self._file.write(path_bytes)

        self._file.seek(4)
        self._file.write(struct.pack("<I", len(self.entries)))
        self._file.write(struct.pack("<Q", index_offset))


# ── Pmole ────────────────────────────────────────────────────────────────────

class Pmole:
    """
    Compress files or directories into a binary ``.pm`` archive using
    selectable or auto-detected compression (LZW, LZW+zlib, zlib, lzma).
    Compression and decompression are parallelised across ``threads`` workers.
    Archives can optionally be AES-256-GCM encrypted with a password.
    """
    def __init__(self) -> None:
        pass

    @measure_time
    def compress(
        self,
        file_path: str | None = None,
        directory_path: str | None = None,
        exclude_directories: list[str] | None = None,
        exclude_extensions: list[str] | None = None,
        exclude_filenames: list[str] | None = None,
        max_file_size_bytes: int | None = None,
        threads: int = 3,
        output_path: str | None = None,
        algo: int | None = None,
        password: str | None = None,
    ) -> str:
        """
        Compress a file or directory into a binary ``.pm`` archive.

        If *password* is provided the archive is encrypted with AES-256-GCM
        (PBKDF2-HMAC-SHA256 key derivation, 260 000 iterations).

        Returns the path of the created archive.
        """
        exc_dirs = (
            exclude_directories if exclude_directories is not None else list(EXCLUDE_DIRECTORIES)
        )
        exc_exts = (
            exclude_extensions if exclude_extensions is not None else list(EXCLUDE_EXTENSIONS)
        )
        exc_names = (
            exclude_filenames if exclude_filenames is not None else list(EXCLUDE_FILENAMES)
        )
        max_size  = max_file_size_bytes if max_file_size_bytes is not None else MAX_FILE_SIZE_BYTES

        if directory_path is not None:
            files_paths = list_files_in_directory(
                directory=directory_path,
                exclude_directories=exc_dirs,
                exclude_extensions=exc_exts,
                exclude_filenames=exc_names,
                max_file_size_bytes=max_size,
            )
            # Apply .pmignore / .gitignore patterns
            ignore_spec = _load_ignore_spec(directory_path)
            if ignore_spec:
                base = Path(directory_path)
                files_paths = [
                    fp for fp in files_paths
                    if not ignore_spec.match_file(
                        Path(fp).relative_to(base).as_posix()
                    )
                ]
            logger.info(f"scan  {len(files_paths)} source files")
            default_name = Path(directory_path).name + ".pm"
        else:
            files_paths  = [file_path]
            default_name = Path(file_path).name.split(".")[0] + ".pm"

        output_file_name = output_path if output_path is not None else default_name

        # Compress all files in parallel, preserving input order
        task = partial(_compress_file_task, algo=algo)
        with ThreadPoolExecutor(max_workers=threads) as executor:
            results = list(executor.map(task, files_paths))

        # Write sequentially (file handle is not thread-safe)
        with PMFileWriter(output_file_name) as writer:
            for _fp, orig_size, is_binary, chosen_algo, compressed in results:
                writer.add_compressed(
                    archived_path=_fp.replace("\\", "/"),
                    orig_size=orig_size,
                    is_binary=is_binary,
                    algo=chosen_algo,
                    compressed_bytes=compressed,
                )

        # Encrypt in-place if a password was supplied
        if password is not None:
            with open(output_file_name, "rb") as f:
                plain = f.read()
            with open(output_file_name, "wb") as f:
                f.write(encrypt_archive(plain, password))
            logger.info("encrypt  AES-256-GCM")

        logger.info(f"wrote  {output_file_name}")
        return output_file_name

    @measure_time
    def decompress(
        self,
        file_path: str,
        threads: int = 3,
        output_dir: str = ".",
        password: str | None = None,
    ) -> list[str]:
        """
        Decompress all files from a ``.pm`` archive in parallel.
        Returns the list of paths written to disk.
        """
        with _open_pm(file_path, password) as effective_path:
            with open(effective_path, "rb") as f:
                entries = _read_index(f)
            if not entries:
                return []

            task = partial(_decompress_file_task, effective_path, output_dir=output_dir)
            with ThreadPoolExecutor(max_workers=threads) as executor:
                written = list(executor.map(task, entries))

        logger.info(f"restored  {len(written)} file(s)")
        return written

    def list_files(self, pm_file_path: str, password: str | None = None) -> list[dict]:
        """Return index metadata for all files (no data sections read)."""
        with _open_pm(pm_file_path, password) as effective_path, open(effective_path, "rb") as f:
            return _read_index(f)

    def extract(
        self,
        pm_file_path: str,
        target_path: str,
        output_dir: str = ".",
        password: str | None = None,
    ) -> str:
        """Extract a single file from the archive by its archived path."""
        with _open_pm(pm_file_path, password) as effective_path:
            with open(effective_path, "rb") as f:
                entries = _read_index(f)
            if not entries:
                raise FileNotFoundError(f"Archive is empty or invalid: '{pm_file_path}'")

            target_norm = target_path.replace("\\", "/")
            entry = next((e for e in entries if e["path"] == target_norm), None)
            if entry is None:
                raise FileNotFoundError(
                    f"'{target_path}' not found in archive '{pm_file_path}'."
                )

            out_path = _decompress_file_task(effective_path, entry, output_dir)

        logger.info(f"extract  {target_path}  →  {out_path}")
        return out_path

    def verify(
        self,
        pm_file_path: str,
        threads: int = 3,
        password: str | None = None,
    ) -> list[dict]:
        """
        Decompress every file in-memory and verify its size against the index.
        Returns a list of ``{path, ok, error}`` dicts — one per archived file.
        Does **not** write anything to disk.
        """
        with _open_pm(pm_file_path, password) as effective_path:
            with open(effective_path, "rb") as f:
                entries = _read_index(f)
            if not entries:
                return []

            task = partial(_verify_file_task, effective_path)
            with ThreadPoolExecutor(max_workers=threads) as executor:
                results = list(executor.map(task, entries))

        ok_count = sum(1 for r in results if r["ok"])
        logger.info(f"verified  {ok_count}/{len(results)} OK")
        return results

    def search(
        self,
        pm_file_path: str,
        pattern: str,
        threads: int = 3,
        password: str | None = None,
    ) -> list[dict]:
        """
        Search for a regex *pattern* in all text files in the archive.
        Binary files are skipped automatically.
        Returns a list of ``{path, line_no, line}`` match dicts.
        Does **not** write anything to disk.
        """
        with _open_pm(pm_file_path, password) as effective_path:
            with open(effective_path, "rb") as f:
                entries = _read_index(f)
            if not entries:
                return []

            task = partial(_search_file_task, effective_path, pattern=pattern)
            with ThreadPoolExecutor(max_workers=threads) as executor:
                per_file = list(executor.map(task, entries))

        matches = [m for file_matches in per_file for m in file_matches]
        logger.info(f"search  {len(matches)} match(es) for '{pattern}'")
        return matches
