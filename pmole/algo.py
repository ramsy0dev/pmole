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

from beautifultable import BeautifulTable

from pmole.utils import measure_time

class LZW: ...
class LZWDictionary: ...


class LZW:
    """
    Lempel-Ziv-Welch lossless compression algorithm
    """
    def __init__(self) -> None:
        self.dictionary = LZWDictionary()
        self.dictionary.create(
            # is_default=False
        )
    
    @measure_time
    def compress(self, data: str) -> str:
        """
        Compress data
        """
        compressed_data_dictionary = LZWDictionary()

        print(f"{len(data) = }")
        # Check for spaces
        split_by_space = False
        count_spaces = 0
        
        for char in data:
            if char == " ":
                count_spaces += 1
        if count_spaces >= 2:
            split_by_space = True
        
        if split_by_space:
            data_list = data.split(" ")

            for element in data_list:
                self.dictionary.add(element)

        print(f"{self.dictionary}")
    
    def decompress(self, compressed_data) -> str: ...

class LZWDictionary:
    """
    Dictionary used for Lempel-Ziv-Welch algorithm.

    The dictionary's representation looks like this:
        >>> {
            "header": ["value", "count", "position_in_data"],
            0: "x"
        }
    """
    keys: list
    items: tuple

    init_dict_range: int = 0x110000 # The range for chars in bytes

    VALUE: str = "value"
    COUNT: str = "count"
    POSITION_IN_DATA: int = "position_in_data"
    HEADERS: list[str] = [VALUE, COUNT, POSITION_IN_DATA]

    def __init__(self) -> None:        
        self.dictionary = dict()
        self.keys = list()
        self.items = tuple()

    def __repr__(self):
        max_pairs = 20
        pairs = dict()

        dictionary_list = list(self.dictionary.items())
        if len(self.dictionary) > max_pairs:
            pairs = dictionary_list[1:int(max_pairs/2)] + dictionary_list[-int(len(dictionary_list)-int(max_pairs/2)):]
        else:
            pairs = dictionary_list[1:]
        
        table = BeautifulTable()
        table.columns.header = self.HEADERS
        table.rows.header = [str(i[0]) for i in pairs]
        
        for i in range(len(pairs)):
            table.rows[i] = pairs[i][1]
        
        return table.__str__()

    @measure_time
    def create(self, columns: list[str] | None = None, is_default: bool | None = True) -> None:
        """
        Create the dictionary
        """
        if len(self.dictionary) > 0:
            return

        if columns is None:
            columns = self.HEADERS
        
        self.dictionary["header"] = columns
        
        if is_default:
            for i in range(1, self.init_dict_range+1):
                self.add(
                    key=i,
                    value=chr(i-1)
                )
        
        self.keys = list(self.dictionary.keys()) # dict_items -> list

    def add(self, value, key: int | None = None) -> None:
        """
        Add a new pair
        """
        if key is None:
            if isinstance(self.keys[-1], str):
                key = 0
            else:
                key = self.keys[-1] + 1
        
        # Check if the value already exists
        is_exists, exists_key = self.exists(value=value)
        if is_exists:
            self.increase_count(key=exists_key)
            return
        
        self.dictionary[key] = [value, 1, None]

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
    
    def increase_count(self, key) -> None:
        """
        Increase the count of a value
        """
        value = self.get_value(key)
        count = self.get_count(key)

        _ = {
            key: [value, count+1, None]
        }
        self.dictionary.update(_)
    
    def decrease_count(self, key) -> None:
        """
        decrease the count of a value
        """
        value = self.get_value(key)
        count = self.get_count(key)

        _ = {
            key: [value, count-1, None]
        }
        self.dictionary.update(_)

    def exists(self, value) -> tuple[bool, str]:
        """
        Does the value exists or not.
        """
        for key in self.dictionary:
            if self.dictionary[key][0] == value and key != "header":
                return (True, key)
        
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

        self.keys, self.items = (list(), tuple())
