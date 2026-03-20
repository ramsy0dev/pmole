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
    "LZWCompressor",
    "RESET_CODE"
]

from loguru import logger

# Utils
from pmole.utils import measure_time

RESET_CODE = 256


class LZWCompressor:
    """
    Stateful LZW compressor for streaming byte input.
    """
    def __init__(self, max_dict_size: int = 65536) -> None:
        self.max_dict_size = max_dict_size
        self._reset()

    def _reset(self) -> None:
        self.code_table = {bytes([i]): i for i in range(256)}
        self.next_code = 257  # 256 is reserved for RESET_CODE
        self.current_bytes = b""

    def feed(self, chunk: bytes) -> list[int]:
        """Process one chunk of bytes, return LZW codes."""
        codes = []
        for byte in chunk:
            b = bytes([byte])
            candidate = self.current_bytes + b
            if candidate in self.code_table:
                self.current_bytes = candidate
            else:
                codes.append(self.code_table[self.current_bytes])
                if self.next_code < self.max_dict_size:
                    self.code_table[candidate] = self.next_code
                    self.next_code += 1
                else:
                    codes.append(RESET_CODE)
                    self._reset()
                self.current_bytes = b
        return codes

    def flush(self) -> list[int]:
        """Emit the final pending code."""
        codes = []
        if self.current_bytes:
            codes.append(self.code_table[self.current_bytes])
            self.current_bytes = b""
        return codes


class LZW:
    """
    Lempel-Ziv-Welch lossless compression algorithm
    """
    def __init__(self) -> None:
        pass

    @measure_time
    def compress(self, data: bytes) -> list[int]:
        """
        Compress bytes using LZW algorithm.
        """
        if not data:
            return []

        compressor = LZWCompressor()
        codes = compressor.feed(data)
        codes.extend(compressor.flush())
        return codes

    @measure_time
    def decompress(self, compressed_data: list[int]) -> bytes:
        """
        Decompress LZW codes back to bytes.
        """
        if not compressed_data:
            return b""

        code_table = {i: bytes([i]) for i in range(256)}
        next_code = 257

        result = bytearray()
        idx = 0

        # Skip any leading reset code
        if compressed_data[idx] == RESET_CODE:
            code_table = {i: bytes([i]) for i in range(256)}
            next_code = 257
            idx += 1
            if idx >= len(compressed_data):
                return bytes(result)

        first_code = compressed_data[idx]
        if first_code not in code_table:
            logger.error(f"Invalid initial code: {first_code}")
            return b""

        entry = code_table[first_code]
        result.extend(entry)
        w = entry
        idx += 1

        while idx < len(compressed_data):
            code = compressed_data[idx]
            idx += 1

            if code == RESET_CODE:
                code_table = {i: bytes([i]) for i in range(256)}
                next_code = 257
                if idx >= len(compressed_data):
                    break
                code = compressed_data[idx]
                idx += 1
                if code not in code_table:
                    logger.error(f"Invalid code after reset: {code}")
                    break
                entry = code_table[code]
                result.extend(entry)
                w = entry
                continue

            if code in code_table:
                entry = code_table[code]
            elif code == next_code:
                # Special case: code equals next expected code
                entry = w + w[:1]
            else:
                logger.warning(f"Invalid code: {code}")
                continue

            result.extend(entry)

            if next_code < 65536:
                code_table[next_code] = w + entry[:1]
                next_code += 1

            w = entry

        return bytes(result)
