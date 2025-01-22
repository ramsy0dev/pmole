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

from bitarray import bitarray

class Convert:
    RAINBOW_TABLE: dict = {
        0:      bitarray("0000"),     1:      bitarray("0001"),
        2:      bitarray("0010"),     3:      bitarray("0011"),
        4:      bitarray("0100"),     5:      bitarray("0101"),
        6:      bitarray("0110"),     7:      bitarray("0111"),
        8:      bitarray("1000"),     9:      bitarray("1001"),
        10:     bitarray("1010"),     11:     bitarray("1011"),
        12:     bitarray("1100"),     13:     bitarray("1101"),
        14:     bitarray("1110"),     15:     bitarray("1111"),
    }
    BASE_2_N: int = 2

    def __init__(self) -> None:
        pass
    
    def convert_utf8_to_base_10(self, data: str) -> list:
        """
        Convert utf8 to base 10.
        """
        utf8_bytes = data.encode("utf-8")
        padded_bytes = b'\x00' * (4 - len(utf8_bytes)) + utf8_bytes

        return [byte for byte in padded_bytes]

    def convert_utf8_to_base_2(self, data: str) -> list[bytes]:
        """
        Convert utf8 to binary (base 2).
        """
        base10_utf8 = self.convert_utf8_to_base_10(data)
        result = [bytes(self.convert_base_10_to_base_2(i).encode()) for i in base10_utf8]

        return result

    def convert_base_10_to_base_2(self, num: int) -> bitarray:
        """
        Convert base 10 to binary (base 2)

        Args:
            num (int): The base 10 number.
        """
        b_rep = list()
        
        result = 1
        while result > 0:
            result = int(num / self.BASE_2_N)

            b_rep.append(int(num%self.BASE_2_N))
            num = result
        
        return ''.join([str(_) for _ in b_rep[::-1]])
    	
    def convert_base_2_to_base_10(self, b_rep: bitarray) -> str:
        """
        convert base 2 to base 10
        """
        num = int()
        n = len(b_rep) - 1

        for i in range(n + 1):
            if int(b_rep[i]) == 1:
                num += self.BASE_2_N ** n

            n -= 1
        
        return str(num)
