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

import os

from pmole.lzw import LZW, LZWCompressor, RESET_CODE


def test_algo_lzw() -> None:
    """
    Test basic LZW roundtrip with text-like bytes.
    """
    lzw = LZW()

    data = b"ABABABAABAB"
    compressed = lzw.compress(data=data)
    decompressed = lzw.decompress(compressed_data=compressed)
    assert decompressed == data

    data2 = b"hello world hello world test"
    compressed2 = lzw.compress(data=data2)
    decompressed2 = lzw.decompress(compressed_data=compressed2)
    assert decompressed2 == data2


def test_compress_decompress_binary_bytes() -> None:
    """
    Roundtrip random binary data.
    """
    lzw = LZW()
    data = os.urandom(10000)
    compressed = lzw.compress(data=data)
    decompressed = lzw.decompress(compressed_data=compressed)
    assert decompressed == data


def test_all_byte_values() -> None:
    """
    Roundtrip all 256 possible byte values.
    """
    lzw = LZW()
    data = bytes(range(256))
    compressed = lzw.compress(data=data)
    decompressed = lzw.decompress(compressed_data=compressed)
    assert decompressed == data


def test_dict_reset() -> None:
    """
    Feed enough unique data to trigger a dictionary reset and verify roundtrip.
    """
    lzw = LZW()
    # ~200KB of random data: each byte is essentially unique in context,
    # adding ~1 dict entry per byte and filling the 65279-entry table ~3 times.
    data = os.urandom(200000)
    compressed = lzw.compress(data=data)
    assert RESET_CODE in compressed, "Expected at least one reset code in compressed output"
    decompressed = lzw.decompress(compressed_data=compressed)
    assert decompressed == data
