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
    "PLATFORM",
    "SLASH",
    "HOME_DIRECTORY",
    "ROOT_CONFIG_DIR",
    "CACHE_DIR",
    "DICTIONARY_CACHE_FILE_PATH",
    "REVERSE_DICTIONARY_CACHE_FILE_PATH"
]

import os

from pmole.utils import (
    get_platform,
    create_path,
    PL_WINDOWS,
    PL_LINUX
)

PLATFORM = get_platform()

SLASH = "/" if PLATFORM == PL_LINUX else "\\"
HOME_DIRECTORY = os.path.expanduser("~")

if PLATFORM == PL_LINUX:
    ROOT_CONFIG_DIR = f"{HOME_DIRECTORY}{SLASH}pmole"
elif PLATFORM == PL_WINDOWS:
    ROOT_CONFIG_DIR = f"{HOME_DIRECTORY}{SLASH}pmole"

CACHE_DIR = ROOT_CONFIG_DIR + SLASH + "cache"
DICTIONARY_CACHE_FILE_PATH = CACHE_DIR + SLASH + "pre_generated_dictionary.json"
REVERSE_DICTIONARY_CACHE_FILE_PATH = CACHE_DIR + SLASH + "pre_generated_reverse_dictionary.json"
