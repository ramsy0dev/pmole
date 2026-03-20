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

__all__ = ["run"]

import os
from pathlib import Path
from typing import Optional

import typer
from loguru import logger

from pmole.api import (
    compress as api_compress,
    decompress as api_decompress,
    list_files as api_list_files,
    extract as api_extract,
    verify as api_verify,
    search as api_search,
    stats as api_stats,
    is_encrypted as api_is_encrypted,
)
from pmole.compression import ALGO_NAMES
from pmole.globals import (
    CACHE_DIR,
    EXCLUDE_EXTENSIONS,
    EXCLUDE_DIRECTORIES,
    EXCLUDE_FILENAMES,
)
from pmole.utils import check_file_path, show_diff

cli = typer.Typer(no_args_is_help=True)

_VALID_ALGO_NAMES = ", ".join(f'"{n}"' for n in ["auto", *ALGO_NAMES.values()])

_PASSWORD_HELP = (
    "Encryption/decryption password. "
    "Can also be set via the PMOLE_PASSWORD environment variable."
)


def setup_cli_dir() -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)


def _fmt_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
    return f"{n:.1f} TB"


def _build_tree(paths: list[str]) -> str:
    """Render a sorted list of forward-slash paths as an ASCII directory tree."""
    root: dict = {}
    for path in sorted(paths):
        node = root
        for part in path.split("/"):
            node = node.setdefault(part, {})

    lines: list[str] = []

    def _render(node: dict, prefix: str = "") -> None:
        items = sorted(node.items())
        for i, (name, children) in enumerate(items):
            is_last   = i == len(items) - 1
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{name}")
            if children:
                extension = "    " if is_last else "│   "
                _render(children, prefix + extension)

    _render(root)
    return "\n".join(lines)


# ── Commands ─────────────────────────────────────────────────────────────────

@cli.command()
def compress(
    path: str = typer.Argument(..., help="File or directory to compress."),
    output: Optional[str] = typer.Option(None, "-o", "--output", help="Output .pm path."),
    algo: str = typer.Option("auto", "-a", "--algo", help=f"Algorithm: {_VALID_ALGO_NAMES}."),
    threads: int = typer.Option(3, "-t", "--threads", help="Parallel threads."),
    password: Optional[str] = typer.Option(
        None, "-p", "--password", envvar="PMOLE_PASSWORD", help=_PASSWORD_HELP
    ),
    exclude_ext: str = typer.Option("", "--exclude-ext", help="Comma-separated extra extensions to exclude."),
    exclude_dir: str = typer.Option("", "--exclude-dir", help="Comma-separated extra directories to exclude."),
    exclude_name: str = typer.Option("", "--exclude-name", help="Comma-separated extra filenames to exclude."),
):
    """Compress a file or directory into a .pm archive."""
    p = Path(path)
    if not p.exists():
        logger.error(f"Path '{path}' does not exist.")
        raise typer.Exit(1)
    if p.is_symlink():
        logger.error("Symlinks are not supported.")
        raise typer.Exit(1)

    exc_exts  = list(EXCLUDE_EXTENSIONS)
    exc_dirs  = list(EXCLUDE_DIRECTORIES)
    exc_names = list(EXCLUDE_FILENAMES)
    if exclude_ext:
        exc_exts.extend(s.strip() for s in exclude_ext.split(",") if s.strip())
    if exclude_dir:
        exc_dirs.extend(s.strip() for s in exclude_dir.split(",") if s.strip())
    if exclude_name:
        exc_names.extend(s.strip() for s in exclude_name.split(",") if s.strip())

    try:
        archive = api_compress(
            path=path,
            output=output,
            algo=algo,
            threads=threads,
            password=password,
            exclude_extensions=exc_exts,
            exclude_directories=exc_dirs,
            exclude_filenames=exc_names,
        )
        enc_note = " (encrypted)" if password else ""
        logger.info(f"Archive created: '{archive}'{enc_note}")
    except (FileNotFoundError, ValueError) as e:
        logger.error(str(e))
        raise typer.Exit(1)


@cli.command()
def decompress(
    archive: str = typer.Argument(..., help="Path to the .pm archive."),
    output_dir: str = typer.Argument(".", help="Directory to restore files into."),
    threads: int = typer.Option(3, "-t", "--threads", help="Parallel threads."),
    password: Optional[str] = typer.Option(
        None, "-p", "--password", envvar="PMOLE_PASSWORD", help=_PASSWORD_HELP
    ),
):
    """Decompress a .pm archive."""
    if not Path(archive).exists():
        logger.error(f"Archive '{archive}' does not exist.")
        raise typer.Exit(1)

    try:
        paths = api_decompress(archive, output_dir=output_dir, threads=threads, password=password)
        logger.info(f"Restored {len(paths)} file(s) to '{output_dir}'.")
    except (FileNotFoundError, ValueError) as e:
        logger.error(str(e))
        raise typer.Exit(1)


@cli.command(name="list")
def list_files(
    archive: str = typer.Argument(..., help="Path to the .pm archive."),
    password: Optional[str] = typer.Option(
        None, "-p", "--password", envvar="PMOLE_PASSWORD", help=_PASSWORD_HELP
    ),
):
    """List all files stored in a .pm archive without decompressing."""
    if not Path(archive).exists():
        logger.error(f"Archive '{archive}' does not exist.")
        raise typer.Exit(1)

    try:
        entries = api_list_files(archive, password=password)
    except (FileNotFoundError, ValueError) as e:
        logger.error(str(e))
        raise typer.Exit(1)

    if not entries:
        logger.info("Archive is empty or invalid.")
        return

    for e in entries:
        kind  = "bin" if e.is_binary else "txt"
        ratio = f"{e.compression_ratio:.2f}"
        print(
            f"[{kind}] [{e.algo_name:8s}] {ratio:>5}x  "
            f"{e.original_size:>10} B  {e.path}"
        )


@cli.command()
def extract(
    archive: str = typer.Argument(..., help="Path to the .pm archive."),
    target: str = typer.Argument(..., help="Archived path of the file to extract."),
    output_dir: str = typer.Argument(".", help="Directory to extract the file into."),
    password: Optional[str] = typer.Option(
        None, "-p", "--password", envvar="PMOLE_PASSWORD", help=_PASSWORD_HELP
    ),
):
    """Extract a single file from a .pm archive."""
    if not Path(archive).exists():
        logger.error(f"Archive '{archive}' does not exist.")
        raise typer.Exit(1)

    try:
        out = api_extract(archive, target, output_dir=output_dir, password=password)
        logger.info(f"Extracted '{target}' → '{out}'")
    except (FileNotFoundError, ValueError) as e:
        logger.error(str(e))
        raise typer.Exit(1)


@cli.command()
def verify(
    archive: str = typer.Argument(..., help="Path to the .pm archive."),
    threads: int = typer.Option(3, "-t", "--threads", help="Parallel threads."),
    password: Optional[str] = typer.Option(
        None, "-p", "--password", envvar="PMOLE_PASSWORD", help=_PASSWORD_HELP
    ),
):
    """
    Verify archive integrity by decompressing every file in-memory.
    Reports any files that fail or have a size mismatch.
    """
    if not Path(archive).exists():
        logger.error(f"Archive '{archive}' does not exist.")
        raise typer.Exit(1)

    try:
        results = api_verify(archive, threads=threads, password=password)
    except (FileNotFoundError, ValueError) as e:
        logger.error(str(e))
        raise typer.Exit(1)

    failures = [r for r in results if not r["ok"]]
    for r in results:
        status = "OK  " if r["ok"] else "FAIL"
        err    = f"  ← {r['error']}" if not r["ok"] else ""
        print(f"[{status}]  {r['path']}{err}")

    if failures:
        logger.error(f"{len(failures)} file(s) failed verification.")
        raise typer.Exit(1)
    else:
        logger.info(f"All {len(results)} file(s) verified OK.")


@cli.command()
def search(
    archive: str = typer.Argument(..., help="Path to the .pm archive."),
    pattern: str = typer.Argument(..., help="Regex pattern to search for."),
    threads: int = typer.Option(3, "-t", "--threads", help="Parallel threads."),
    password: Optional[str] = typer.Option(
        None, "-p", "--password", envvar="PMOLE_PASSWORD", help=_PASSWORD_HELP
    ),
):
    """
    Search for a regex pattern across all text files in the archive.
    Nothing is written to disk. Binary files are skipped.
    """
    if not Path(archive).exists():
        logger.error(f"Archive '{archive}' does not exist.")
        raise typer.Exit(1)

    try:
        matches = api_search(archive, pattern=pattern, threads=threads, password=password)
    except (FileNotFoundError, ValueError) as e:
        logger.error(str(e))
        raise typer.Exit(1)

    for m in matches:
        print(f"{m['path']}:{m['line_no']}: {m['line']}")

    if not matches:
        logger.info("No matches found.")


@cli.command()
def stats(
    archive: str = typer.Argument(..., help="Path to the .pm archive."),
    password: Optional[str] = typer.Option(
        None, "-p", "--password", envvar="PMOLE_PASSWORD", help=_PASSWORD_HELP
    ),
):
    """Show compression statistics grouped by file extension."""
    if not Path(archive).exists():
        logger.error(f"Archive '{archive}' does not exist.")
        raise typer.Exit(1)

    try:
        data = api_stats(archive, password=password)
    except (FileNotFoundError, ValueError) as e:
        logger.error(str(e))
        raise typer.Exit(1)

    by_ext = data["by_extension"]
    # Sort by original size descending
    sorted_exts = sorted(by_ext.items(), key=lambda kv: kv[1]["original"], reverse=True)

    header = f"{'Ext':<12} {'Files':>6}  {'Original':>12}  {'Compressed':>12}  {'Ratio':>6}"
    print(header)
    print("-" * len(header))
    for ext, bucket in sorted_exts:
        ratio = bucket["compressed"] / bucket["original"] if bucket["original"] else 0
        print(
            f"{ext:<12} {bucket['files']:>6}  "
            f"{_fmt_bytes(bucket['original']):>12}  "
            f"{_fmt_bytes(bucket['compressed']):>12}  "
            f"{ratio:>5.2f}x"
        )
    print("-" * len(header))
    total_ratio = (
        data["total_compressed"] / data["total_original"]
        if data["total_original"] else 0
    )
    print(
        f"{'TOTAL':<12} {data['total_files']:>6}  "
        f"{_fmt_bytes(data['total_original']):>12}  "
        f"{_fmt_bytes(data['total_compressed']):>12}  "
        f"{total_ratio:>5.2f}x"
    )


@cli.command()
def tree(
    archive: str = typer.Argument(..., help="Path to the .pm archive."),
    password: Optional[str] = typer.Option(
        None, "-p", "--password", envvar="PMOLE_PASSWORD", help=_PASSWORD_HELP
    ),
):
    """Display the directory tree structure of a .pm archive."""
    if not Path(archive).exists():
        logger.error(f"Archive '{archive}' does not exist.")
        raise typer.Exit(1)

    try:
        entries = api_list_files(archive, password=password)
    except (FileNotFoundError, ValueError) as e:
        logger.error(str(e))
        raise typer.Exit(1)

    if not entries:
        logger.info("Archive is empty or invalid.")
        return

    paths = [e.path for e in entries]
    print(_build_tree(paths))
    print(f"\n{len(entries)} file(s)")


@cli.command()
def diff(
    file1: str = typer.Argument(..., help="First file path."),
    file2: str = typer.Argument(..., help="Second file path."),
):
    """Show a unified diff between two files."""
    if not check_file_path(file1):
        logger.error(f"Path '{file1}' does not exist.")
        raise typer.Exit(1)
    if not check_file_path(file2):
        logger.error(f"Path '{file2}' does not exist.")
        raise typer.Exit(1)

    text1 = open(file1, "r").read()
    text2 = open(file2, "r").read()

    diff_lines = show_diff(text1.splitlines(True), text2.splitlines(True), file1, file2)
    logger.info(f"Diff: {file1} vs {file2}")
    for line in diff_lines:
        print(line)


def run() -> None:
    setup_cli_dir()
    cli()
