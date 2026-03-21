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
    "PL_WINDOWS",
    "PL_LINUX",
    "get_platform",
    "measure_time",
    "check_file_path",
    "show_diff",
    "list_files_in_directory",
]

import os
import time
from pathlib import Path

from loguru import logger

PL_WINDOWS = 0
PL_LINUX   = 1


def get_platform() -> int:
    import platform
    return PL_WINDOWS if platform.system() == "Windows" else PL_LINUX


def measure_time(func: callable):
    """Decorator that logs how long a method call takes (debug level)."""
    def wrapper(self, *args, **kwargs):
        t0     = time.time()
        result = func(self, *args, **kwargs)
        logger.debug(f"time  {func.__name__}  {time.time() - t0:.3f}s")
        return result
    return wrapper


def check_file_path(file_path: str) -> bool:
    return Path(file_path).exists()


def show_diff(d1, d2, fromfile: str, tofile: str) -> list[str]:
    from difflib import context_diff
    return list(context_diff(d1, d2, fromfile=fromfile, tofile=tofile))


def list_files_in_directory(
    directory: str,
    exclude_directories: list[str],
    exclude_extensions: list[str],
    exclude_filenames: list[str] | None = None,
    max_file_size_bytes: int | None = None,
) -> list[str]:
    """
    List all files in a directory recursively, applying four independent
    exclusion filters:

    * **extension** — case-insensitive suffix match (e.g. ``"pyc"``)
    * **directory name** — any path component between the root and the file
    * **filename** — exact filename match, case-insensitive
    * **size** — files larger than *max_file_size_bytes* are skipped
    """
    exclude_extensions_lower  = {ext.lower() for ext in exclude_extensions}
    exclude_directories_lower = {d.lower() for d in exclude_directories}
    exclude_filenames_lower   = {fn.lower() for fn in (exclude_filenames or [])}

    included: list[str] = []
    excluded_count = 0

    for file_path in Path(directory).rglob("*"):
        if not file_path.is_file():
            continue

        file_str = str(file_path)
        reason: str | None = None

        # 1. Filename exclusion
        if file_path.name.lower() in exclude_filenames_lower:
            reason = f"filename: {file_path.name}"

        # 2. Extension exclusion
        elif file_path.suffix.lower().lstrip(".") in exclude_extensions_lower:
            reason = f"extension: {file_path.suffix}"

        # 3. Directory exclusion
        else:
            rel_parts = [p.lower() for p in file_path.relative_to(directory).parts[:-1]]
            hit = next((p for p in rel_parts if p in exclude_directories_lower), None)
            if hit:
                reason = f"directory: {hit}"

        # 4. Size exclusion
        if reason is None and max_file_size_bytes is not None:
            try:
                size = os.path.getsize(file_str)
                if size > max_file_size_bytes:
                    reason = f"size: {size} > {max_file_size_bytes} bytes"
            except OSError:
                pass

        if reason:
            logger.debug(f"Excluded '{file_str}' ({reason})")
            excluded_count += 1
        else:
            included.append(file_str)

    total = len(included) + excluded_count
    if excluded_count:
        logger.info(
            f"filter  {total} found  {excluded_count} excluded  {len(included)} queued"
        )

    return included
