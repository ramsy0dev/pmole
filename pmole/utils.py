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
    "get_platform",
    "measure_time",
    "check_file_path",
    "create_path",
    "show_diff",
    "split_data_to_batches",
    "list_files_in_directory",
    "replace_unsupported_characters"
]

import os
import time
import wcwidth

from pathlib import Path

from loguru import logger

# Types
PL_WINDOWS = 0
PL_LINUX = 1

# Stubs
class Nodes: ...

def get_platform() -> int: ...
def measure_time(func: callable) -> None: ...
def create_path(path: str) -> bool: ...
def check_file_path(file_path: str) -> bool: ...
def show_diff(d1, d2, file1: str, file2: str) -> str: ...
def split_data_to_batches(data_n: int, k: int) -> list: ...
def list_files_in_directory(directory: str) -> list[str]: ...
def replace_unsupported_characters(input_string: str, placeholder: str = "?") -> str: ...

#Implementations
class Nodes:
    """
    Node
    """
    def __init__(
            self,
            next: Nodes | None = None,
            prev: Nodes | None = None,
            data: str | None = None        
    ) -> None:
        self.next = next
        self.prev = prev
        self.data = data

def get_platform() -> int:
    import platform
    
    plattype = platform.system()
    
    return PL_WINDOWS if plattype == "Windows" else PL_LINUX

def measure_time(func: callable) -> None:
    """
    Mesure the time a function takes.
    """
    def wrapper(self, *args, **kwargs):
        start_time = time.time()
        result = func(self, *args, **kwargs)
        end_time = time.time()
        deff = end_time - start_time

        logger.debug(f"Function '{func.__name__}' took '{deff:.6f}' seconds")

        return result
    
    return wrapper

def create_path(path: str) -> str:
    """
    Create a path
    """
    platform = get_platform()
    slash = "/" if platform == PL_LINUX else "\\"
    
    dirs = path.split(slash)
    
    root_dir = os.getcwd()

    logger.debug(f"Current working directory: {root_dir}")

    last_dir = root_dir
    
    for i in range(len(dirs)):
        directory = ""
        
        if dirs[i] == "":
            continue
        
        directory = last_dir + slash + dirs[i]
        
        logger.debug(f"Processing directory: `{directory}`")

        directory = Path(directory)

        is_file_format = i == len(dirs) - 1
        
        if not is_file_format and not directory.exists():
            directory.mkdir()
        elif is_file_format and not directory.exists():
            directory.touch()
    
        last_dir += slash + dirs[i]
    
    return last_dir

def check_file_path(file_path: str) -> bool:
    """
    Check the existant of a file path.
    """
    return Path(file_path).exists()

def show_diff(d1, d2, fromfile: str, tofile: str) -> list[str]:
    from difflib import context_diff
    
    diff = context_diff(
        d1, d2, fromfile=fromfile, tofile=tofile
    )
    
    return [line for line in diff]

def split_data_to_batches(data_n: int, k: int) -> list:
    """
    Split a large list of data into batches.

    (start, stop) idx
    """
    x = int(data_n / k)
    batches = [(i * x, (i + 1) * x) for i in range(k)]
    
    return batches

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
            logger.info(f"Excluded '{file_str}' ({reason})")
            excluded_count += 1
        else:
            included.append(file_str)

    total = len(included) + excluded_count
    if excluded_count:
        logger.info(
            f"File filtering: {total} found, {excluded_count} excluded, "
            f"{len(included)} will be processed"
        )

    return included

def replace_unsupported_characters(input_string: str, placeholder: str = "?") -> str:
    return ''.join(char if wcwidth.wcwidth(char) != -1 else placeholder for char in input_string)
