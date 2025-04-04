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
    "Nodes",
    "get_platform",
    "measure_time",
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

def show_diff(d1, d2, fromfile: str, tofile: str) -> str:
    from difflib import context_diff
    
    diff = context_diff(
        d1, d2, fromfile=fromfile, tofile=tofile
    )
    
    return diff

def split_data_to_batches(data_n: int, k: int) -> list:
    """
    Split a large list of data into batches.

    (start, stop) idx
    """
    x = int(data_n / k)
    batches = [(i * x, (i + 1) * x) for i in range(k)]
    
    return batches

def list_files_in_directory(directory: str) -> list[str]:
    return [str(file) for file in Path(directory).rglob('*') if file.is_file()]

def replace_unsupported_characters(input_string: str, placeholder: str = "?") -> str:
    return ''.join(char if wcwidth.wcwidth(char) != -1 else placeholder for char in input_string)
