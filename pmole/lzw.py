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
    "LZW",
    "LZWDictionary"
]

import json

from pathlib import Path
from loguru import logger
from typing import Generator
from multiprocessing import (
    Process,
    Manager
)

# Globals
from pmole.globals import (
    DICTIONARY_CACHE_FILE_PATH,
    REVERSE_DICTIONARY_CACHE_FILE_PATH
)

# Utils
from pmole.utils import measure_time

class LZW: ...
class LZWDictionary: ...

class LZW:
    """
    Lempel-Ziv-Welch lossless compression algorithm
    """
    def __init__(self) -> None:
        pass

    @measure_time
    def compress(
        self, data: Generator | str, dictionary: LZWDictionary | None = None
    ) -> list[int]:
        """
        Compress data using LZW algorithm
        """
        if dictionary is None:
            dictionary = LZWDictionary()
            dictionary.create()

        compressed_data = []

        # Initialize dictionary codes
        code_table = {chr(i): i for i in range(256)}
        next_code = 256

        # Handle input data
        if isinstance(data, str):
            input_string = data
        else:
            input_string = "".join(data)

        if not input_string:
            return compressed_data

        # LZW compression
        s = ""
        for char in input_string:
            sc = s + char
            if sc in code_table:
                s = sc
            else:
                # Output code for s
                compressed_data.append(code_table[s])
                # Add new code for sc
                code_table[sc] = next_code
                next_code += 1
                s = char

        # Output code for remaining s
        if s:
            compressed_data.append(code_table[s])

        return compressed_data

    @measure_time
    def decompress(
        self, compressed_data: list[int], dictionary: LZWDictionary | None = None
    ) -> str:
        """
        Decompress data using LZW algorithm
        """
        if not compressed_data:
            return ""

        if dictionary is None:
            dictionary = LZWDictionary()
            dictionary.create()

        # Initialize code table (reverse of compression)
        code_table = {i: chr(i) for i in range(256)}
        next_code = 256

        result = []

        # Get first code
        old_code = compressed_data.pop(0)
        if old_code not in code_table:
            logger.error(f"Invalid initial code: {old_code}")
            return ""

        s = code_table[old_code]
        result.append(s)
        w = s  # Previous string

        # Process remaining codes
        for code in compressed_data:
            if code in code_table:
                entry = code_table[code]
            elif code == next_code:
                # Special case: code equals next expected code
                entry = w + w[0]
            else:
                logger.warning(f"Invalid code: {code}")
                continue

            result.append(entry)

            # Add new code: previous_string + first_char_of_entry
            code_table[next_code] = w + entry[0]
            next_code += 1

            w = entry  # Update previous string

        return "".join(result)

class LZWDictionary:
    """
    Dictionary used for Lempel-Ziv-Welch algorithm.

    The dictionary's representation looks like this:
        >>> {
            "char": ["idx", "count"],
            0: [...],
            1: [...],
            ...
        }
    """

    values: list[int] = list()
    keys: list[str] = list()
    items: tuple

    # The full range is 1114112
    INIT_DICT_SIZE: int = 0
    ASCII: tuple[int, int] = (0x00, 0x7F + 1)
    EXTENDED_ASCII: tuple[int, int] = (0x00, 0xFF + 1)
    BASIC_UNICODE: tuple[int, int] = (0x0, 0xFFFF + 1)
    FULL_UNICODE_RANGE: tuple[int, int] = (0x00, 0x10FFFF + 1)
    BASIC_SYMBOLS: tuple[int, int] = (0x2000, 0x26FF + 1)
    EMOJIS: tuple[int, int] = (0x1F300, 0x1FAFF + 1)

    VALUE: str = "idx"
    COUNT: str = "count"
    HEADERS: list[str] = [VALUE, COUNT]

    def __init__(self) -> None:
        self.dictionary = dict()
        self.keys = list()
        self.items = tuple()

        self.reverse_dictionary = dict()  # Reverse mapping (doesn't include the header)

    @staticmethod
    def check_cache_exists() -> bool:
        dictionary_file = Path(DICTIONARY_CACHE_FILE_PATH)
        reverse_dictionary_file = Path(REVERSE_DICTIONARY_CACHE_FILE_PATH)

        return (
            dictionary_file.exists() and dictionary_file.stat().st_size > 0
            and reverse_dictionary_file.exists() and reverse_dictionary_file.stat().st_size > 0
        )

    @staticmethod
    def load_from_temp() -> tuple[dict[str, list], dict[int, str]]:
        cached_dictionary: dict[str, list] = dict()
        cached_reverse_dictionary: dict = dict()

        with open(DICTIONARY_CACHE_FILE_PATH, "r") as f:
            cached_dictionary = json.load(f)

        with open(REVERSE_DICTIONARY_CACHE_FILE_PATH, "r") as f:
            cached_reverse_dictionary = json.load(f)
            cached_reverse_dictionary = {
                int(key): element for key, element in cached_reverse_dictionary.items()
            }

        logger.debug(f"Loaded dictionary: {list(cached_dictionary.items())[:10]}")
        logger.debug(f"Loaded reverse dictionary: {list(cached_reverse_dictionary.items())[:10]}")

        return (cached_dictionary, cached_reverse_dictionary)

    @staticmethod
    def save_dictionary_to_cache(
        dictionary: dict[str, list], reverse_dictionary: dict[int, str]
    ) -> None:
        with open(DICTIONARY_CACHE_FILE_PATH, "w") as o:
            json.dump(dictionary, o)

        with open(REVERSE_DICTIONARY_CACHE_FILE_PATH, "w") as o:
            json.dump(reverse_dictionary, o)

        logger.debug(f"Saved dictionary: {list(dictionary.items())[:10]}")
        logger.debug(f"Saved reverse dictionary: {list(reverse_dictionary.items())[:10]}")

    def create(
        self,
        columns: list[str] | None = None,
        generate_default_dict: bool | None = True,
    ) -> None:
        """
        Create the dictionary with caching support for optimal performance.
        """
        if len(self.dictionary) > 0:
            return

        if columns is None:
            columns = self.HEADERS

        self.dictionary["char"] = columns

        if generate_default_dict:
            # Try to load from cache first
            if self.check_cache_exists():
                logger.debug("Loading dictionary from cache")
                try:
                    cached_dict, cached_reverse = self.load_from_temp()
                    self.dictionary.update(cached_dict)
                    self.reverse_dictionary.update(cached_reverse)
                    # Rebuild values and keys lists
                    for key, value in cached_dict.items():
                        if key != "char":  # Skip header
                            self.values.append(value[0])
                            self.keys.append(key)
                    logger.debug("Successfully loaded dictionary from cache")
                except Exception as e:
                    logger.warning(f"Failed to load cache: {e}, regenerating...")
                    self.__generate_dict__()
            else:
                logger.debug("No cache found, generating dictionary")
                self.__generate_dict__()
                # Save to cache for future use
                self.save_dictionary_to_cache(self.dictionary, self.reverse_dictionary)

        self.keys = list(self.dictionary.keys()) # dict_items -> list

        logger.debug(f"Dictionary ready: {len(self.dictionary)-1} characters loaded")
        
    def add(
        self,
        key: str,
        value: int | None = None,
        ignore_exists_checks: bool | None = False,
    ) -> None:
        """
        Add a new pair to the dictionary
        """
        # If value is not provided, use the next available code
        if value is None:
            value = len(self.dictionary)  # Next code after current dictionary size

        self.dictionary[key] = [value, 1]
        self.reverse_dictionary[value] = key

        logger.debug(f"Added key `{key}` with value `{value}` to the dictionary")

        self.values.append(value)
        self.keys.append(key)

    def get_key(self, value) -> bytes:
        """
        Get key using value
        """
        return self.reverse_dictionary[value]

    def get_value(self, key) -> bytes:
        """
        Get value using key.
        """
        return self.dictionary[key][0]

    def get_count(self, key) -> int:
        """
        Get the count of a value using the key.
        """
        return self.dictionary[key][1]

    def get_column(self, key, column: str):
        """
        Gets a column for a row based on its key.
        """
        index = self.HEADERS.index(column)

        return self.dictionary[key][index]

    def increase_count(self, key) -> None:
        """
        Increase the count of a value
        """
        value = self.get_value(key)
        count = self.get_count(key)

        _ = {key: [value, count + 1]}
        self.dictionary.update(_)

    def decrease_count(self, key) -> None:
        """
        decrease the count of a value
        """
        value = self.get_value(key)
        count = self.get_count(key)

        _ = {key: [value, count - 1]}
        self.dictionary.update(_)

    def exists(
        self, key: str | None = None, value: str | None = None
    ) -> tuple[bool, str]:
        """
        Does the value exists or not.
        """
        if key is not None and key in self.keys:
            logger.debug(
                f"Found key `{key}` in `self.keys`: {key} = {self.dictionary[key][0]}"
            )

            return (True, self.dictionary[key][0])
        if value is not None and value in self.reverse_dictionary:
            logger.debug(
                f"Found value `{value}` in `self.reverse_dictionary`: {value} = {self.reverse_dictionary[value]}"
            )

            return (True, self.reverse_dictionary[value])

        log_msg = (
            [f"value `{value}`", "`self.reverse_dictionary`"]
            if value is not None
            else [f"key `{key}`", "`self.keys`"]
        )
        logger.debug(f"Not found {log_msg[0]} in {log_msg[1]}")

        return (False, None)

    def delete(self, key) -> None:
        """
        Delete pair.
        """
        del self.dictionary[key]

        self.keys.remove(key)

    def drop(self) -> None:
        """
        Drop the dictionary
        """
        self.dictionary.clear()
        self.reverse_dictionary.clear()

        self.keys, self.items = (list(), tuple())

    @staticmethod
    def __generate__(start, stop, reverse_dictionary):
        """
        Generate dictionary chunk - optimized for ASCII/Extended ASCII ranges.
        No exception handling needed since we're using valid character ranges.
        """
        d = {}
        for i in range(start, stop):
            char_value = chr(i)
            d[char_value] = [int(i), int(0)]
            reverse_dictionary[int(i)] = char_value

        logger.debug(f"Generated dictionary chunk: {start}-{stop} ({len(d)} chars)")
        return d

    @staticmethod
    def worker(start, stop, idx, shared_results, reverse_dictionary):
        """
        Worker function to process dictionary generation.
        """
        result = LZWDictionary.__generate__(start, stop, reverse_dictionary)
        shared_results[idx] = result  # Update shared dictionary

    @measure_time
    def __generate_dict__(self):
        """
        Generates the optimized dictionary for code compression.
        Uses ASCII + Extended ASCII for comprehensive symbol support.
        """
        processes = []

        # Create a Manager to share results across processes
        with Manager() as manager:
            # Optimized ranges for code compression: ASCII + Extended symbols
            indexes = [
                self.ASCII,              # 0-127: Basic ASCII (letters, numbers, common symbols)
                self.EXTENDED_ASCII,     # 128-255: Extended ASCII (programming symbols, operators)
            ]

            # Pre-populate values list efficiently
            for index in indexes:
                self.values.extend(range(index[0], index[1]))

            processes_n = len(indexes)
            shared_results = manager.list([{} for _ in range(processes_n)])
            reverse_dictionary = manager.dict()

            # Create and start processes
            for idx, (start, stop) in enumerate(indexes):
                process = Process(
                    target=self.worker,
                    args=(start, stop, idx, shared_results, reverse_dictionary),
                )
                process.start()
                processes.append(process)

            # Wait for all processes to finish
            for process in processes:
                process.join()

            # Merge results into the main dictionary
            for result in shared_results:
                self.dictionary.update(result)

            self.reverse_dictionary = reverse_dictionary.copy()
            self.INIT_DICT_SIZE = len(self.dictionary) - 1
