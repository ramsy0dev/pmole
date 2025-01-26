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

from typing import Generator
from multiprocessing import Process, Manager

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
    def compress(self, data: Generator) -> LZWDictionary:
        """
        Compress data
        """
        dictionary = LZWDictionary()
        dictionary.create()

        compressed_data = []

        last_char = ""
        dict_size = dictionary.INIT_DICT_SIZE
        
        for buffer in data:
            for char in buffer:
                current_sequence = last_char + char
                
                exists, idx = dictionary.exists(key=current_sequence)
                if exists:
                    last_char = current_sequence
                else:
                    idx = dict_size
                    compressed_data.append(dictionary.get_value(
                        key=last_char
                    ))
                    
                    dictionary.add(key=current_sequence, value=idx)
                    dict_size += 1
                    
                    last_char = char

        if last_char:
            compressed_data.append(dictionary.get_value(last_char))

        return compressed_data

    @measure_time
    def decompress(self, compressed_data: list[int]) -> str:
        """
        Decompress data using the LZW algorithm.

        Args:
            compressed_data (list[int]): The list of dictionary indexes to decompress.

        Returns:
            str: The decompressed string.
        """
        if not compressed_data:
            return ""
        
        dictionary = LZWDictionary()
        dictionary.create()

        result = list()

        dict_size = dictionary.INIT_DICT_SIZE
        w = dictionary.reverse_dictionary[compressed_data.pop(0)]
        result.append(w)

        for token  in compressed_data:
            exists, value = dictionary.exists(value=token)
            if exists:
                entry = value
            elif token == dict_size:
                entry = w + w[0]
            else:
                # Handle unexpected cases
                raise ValueError(f"Invalid token encountered: {token = }")
        
            result.append(entry)
            dictionary.add(
                key=w + entry[0],
                value=dict_size
            )

            dict_size += 1
            w = entry
        
        return ''.join(result)

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

    # init_dict_range: int = 1114112 # The range for chars in bytes
    # The full range is 1114112
    INIT_DICT_SIZE: int = 0
    ASCII: tuple[int, int] = (0x00, 0x7F+1)
    EXTENDED_ASCII: tuple[int, int] = (0x00, 0xFF+1)
    BASIC_UNICODE: tuple[int, int] = (0x0, 0xFFFF+1)
    FULL_UNICODE_RANGE: tuple[int, int] = (0x00, 0x10FFFF+1)
    BASIC_SYMBOLS: tuple[int, int] = (0x2000, 0x26FF+1)
    EMOJIS: tuple[int, int] = (0x1F300, 0x1FAFF+1)

    VALUE: str = "idx"
    COUNT: str = "count"
    HEADERS: list[str] = [VALUE, COUNT]

    def __init__(self) -> None:        
        self.dictionary = dict()
        self.keys = list()
        self.items = tuple()

        self.reverse_dictionary = dict() # Reverse mapping (doesn't include the header)
    
    # def __repr__(self):
    #     max_pairs = 100
    #     pairs = dict()

    #     dictionary_list = list(self.dictionary.items())
    #     if len(self.dictionary) > max_pairs:
    #         a = dictionary_list[1:int(max_pairs/2)]
    #         b = [(".....", [".....", "....."])]
    #         c = dictionary_list[-int(max_pairs/2):]
    #         pairs = a + b + c
    #     else:
    #         pairs = dictionary_list[1:]
        
    #     table = BeautifulTable()
    #     table.columns.header = self.HEADERS
    #     table.rows.header = [str(i[0]) for i in pairs]
        
    #     for i in range(len(pairs)):
    #         pairs[i][1][0] = replace_unsupported_characters(pairs[i][1][0]) if not isinstance(pairs[i][1][0], int) else pairs[i][1][0]
    #         table.rows[i] = pairs[i][1]
        
    #     return table.__str__()

    def create(self, columns: list[str] | None = None, generate_default_dict: bool | None = True) -> None:
        """
        Create the dictionary
        """
        if len(self.dictionary) > 0:
            return

        if columns is None:
            columns = self.HEADERS
        
        self.dictionary["char"] = columns
        
        if generate_default_dict:
            self.__generate_dict__()
        
        self.keys = list(self.dictionary.keys()) # dict_items -> list

    def add(self, key: str, value: int | None = None, ignore_exists_checks: bool | None = False) -> None:
        """
        Add a new pair
        """
        # value is the idx of the character
        if value is None:
            if isinstance(self.values[-1], str):
                value = 0
            else:
                value = self.values[-1] + 1

        self.dictionary[key] = [value, 1]
        
        self.reverse_dictionary[value] = key

        self.values.append(value)
        self.keys.append(key)

    def get_value(self, key) -> str:
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

        _ = {
            key: [value, count+1]
        }
        self.dictionary.update(_)
    
    def decrease_count(self, key) -> None:
        """
        decrease the count of a value
        """
        value = self.get_value(key)
        count = self.get_count(key)

        _ = {
            key: [value, count-1]
        }
        self.dictionary.update(_)

    def exists(self, key: str | None = None, value: str | None = None) -> tuple[bool, str]:
        """
        Does the value exists or not.
        """
        if key is not None and key in self.keys:
            return (True, self.dictionary[key][0])
        if value is not None and value in self.reverse_dictionary:
            return (True, self.reverse_dictionary[value])
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
        """Dummy generate function for demonstration."""
        d = {}
        for i in range(start, stop):
            d[chr(i)] = [i, 0]
            reverse_dictionary[i] = chr(i)
        
        return {chr(i): [i, 0] for i in range(start, stop)}

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
        Generates the default dict.
        """
        # processes_n = 8  # Fixed number of processes
        processes = []

        # Create a Manager to share results across processes
        with Manager() as manager:
            indexes = [
                # self.ASCII,
                # self.EXTENDED_ASCII
                self.BASIC_UNICODE,
                # self.BASIC_SYMBOLS,
                # self.EMOJIS
            ]
            for index in indexes:
                self.values += [i for i in range(index[0], index[1])]
            
            processes_n = len(indexes)
            shared_results = manager.list([{} for _ in range(processes_n)])
            reverse_dictionary = manager.dict()
            # Create and start processes
            for idx, (start, stop) in enumerate(indexes):
                process = Process(
                    target=self.worker,
                    args=(
                        start, stop, idx, shared_results, reverse_dictionary
                    )
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
            self.INIT_DICT_SIZE = len(self.dictionary)-1
