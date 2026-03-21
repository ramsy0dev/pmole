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
    # High-level API
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
    "ArchiveEntry",
    # Algorithm constants
    "ALGO_LZW",
    "ALGO_LZW_ZLIB",
    "ALGO_ZLIB",
    "ALGO_LZMA",
    "ALGO_NAMES",
    # Low-level class (advanced use)
    "Pmole",
    # Default filter lists (copy and modify to customise)
    "EXCLUDE_EXTENSIONS",
    "EXCLUDE_DIRECTORIES",
    "EXCLUDE_FILENAMES",
    "MAX_FILE_SIZE_BYTES",
]

from pmole.api import (
    ArchiveEntry,
    compress,
    decompress,
    extract,
    is_encrypted,
    list_files,
    lzw_compress,
    lzw_decompress,
    search,
    stats,
    verify,
)
from pmole.compression import ALGO_LZMA, ALGO_LZW, ALGO_LZW_ZLIB, ALGO_NAMES, ALGO_ZLIB
from pmole.globals import (
    EXCLUDE_DIRECTORIES,
    EXCLUDE_EXTENSIONS,
    EXCLUDE_FILENAMES,
    MAX_FILE_SIZE_BYTES,
)
from pmole.pmole import Pmole
