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

"""
Multi-algorithm compression layer
==================================

Four algorithms are available:

  ALGO_LZW       (0)  LZW codes packed as little-endian uint16 stream.
  ALGO_LZW_ZLIB  (1)  LZW uint16 stream further compressed with zlib.
                      Pairs LZW's dictionary substitution with zlib's
                      entropy coding pass — best for highly repetitive text.
  ALGO_ZLIB      (2)  Pure zlib/DEFLATE (LZ77 + Huffman).
                      Fast and well-rounded for source code.
  ALGO_LZMA      (3)  Pure LZMA.  Best compression ratio, slower encode.

``compress_auto`` tries all applicable algorithms and returns whichever
produces the smallest output. LZW-based algorithms are skipped for files
larger than ``_LZW_SIZE_LIMIT`` to avoid excessive memory use.
"""

__all__ = [
    "ALGO_LZW",
    "ALGO_LZW_ZLIB",
    "ALGO_ZLIB",
    "ALGO_LZMA",
    "ALGO_NAMES",
    "compress_with_algo",
    "decompress_with_algo",
    "compress_auto",
]

import lzma
import struct
import zlib

from loguru import logger

from pmole.lzw import LZW, LZWCompressor

# Algorithm IDs stored in every FILE SECTION header
ALGO_LZW      = 0
ALGO_LZW_ZLIB = 1
ALGO_ZLIB     = 2
ALGO_LZMA     = 3

ALGO_NAMES: dict[int, str] = {
    ALGO_LZW:      "lzw",
    ALGO_LZW_ZLIB: "lzw+zlib",
    ALGO_ZLIB:     "zlib",
    ALGO_LZMA:     "lzma",
}

# Files larger than this skip LZW-based algorithms; zlib/lzma compress and
# decompress large data faster than pure-Python LZW.
_LZW_SIZE_LIMIT = 10 * 1024 * 1024  # 10 MB

_FEED_CHUNK = 65536  # bytes fed to LZWCompressor per iteration


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _lzw_to_bytes(data: bytes) -> bytes:
    """
    LZW-compress *data* and return the codes packed as a little-endian
    uint16 stream.  Processes input in 64 KB chunks to keep peak memory low.
    """
    compressor = LZWCompressor()
    parts: list[bytes] = []

    for i in range(0, len(data), _FEED_CHUNK):
        codes = compressor.feed(data[i:i + _FEED_CHUNK])
        if codes:
            parts.append(struct.pack(f"<{len(codes)}H", *codes))

    final = compressor.flush()
    if final:
        parts.append(struct.pack(f"<{len(final)}H", *final))

    return b"".join(parts)


def _bytes_to_lzw(data: bytes) -> bytes:
    """Unpack a little-endian uint16 code stream and LZW-decompress it."""
    if not data:
        return b""
    n = len(data) // 2
    codes = list(struct.unpack(f"<{n}H", data))
    return LZW().decompress(compressed_data=codes)


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def compress_with_algo(data: bytes, algo: int) -> bytes:
    """Compress *data* with the given algorithm. Returns compressed bytes."""
    if algo == ALGO_LZW:
        return _lzw_to_bytes(data)
    if algo == ALGO_LZW_ZLIB:
        return zlib.compress(_lzw_to_bytes(data), level=6)
    if algo == ALGO_ZLIB:
        return zlib.compress(data, level=9)
    if algo == ALGO_LZMA:
        return lzma.compress(data, preset=6)
    raise ValueError(f"Unknown algorithm id: {algo}")


def decompress_with_algo(data: bytes, algo: int) -> bytes:
    """Decompress *data* that was compressed with the given algorithm."""
    if algo == ALGO_LZW:
        return _bytes_to_lzw(data)
    if algo == ALGO_LZW_ZLIB:
        return _bytes_to_lzw(zlib.decompress(data))
    if algo == ALGO_ZLIB:
        return zlib.decompress(data)
    if algo == ALGO_LZMA:
        return lzma.decompress(data)
    raise ValueError(f"Unknown algorithm id: {algo}")


def compress_auto(data: bytes) -> tuple[int, bytes]:
    """
    Try all applicable algorithms and return ``(algo_id, compressed_bytes)``
    for whichever produces the smallest output.

    LZW-based algorithms are skipped when ``len(data) > _LZW_SIZE_LIMIT``
    (10 MB) to avoid slow pure-Python processing on large inputs.
    """
    if not data:
        return ALGO_LZW, b""

    candidates = (
        [ALGO_ZLIB, ALGO_LZMA]
        if len(data) > _LZW_SIZE_LIMIT
        else [ALGO_LZW, ALGO_LZW_ZLIB, ALGO_ZLIB, ALGO_LZMA]
    )

    best_algo = candidates[0]
    best_bytes = compress_with_algo(data, best_algo)

    for algo in candidates[1:]:
        try:
            compressed = compress_with_algo(data, algo)
            if len(compressed) < len(best_bytes):
                best_algo = algo
                best_bytes = compressed
        except Exception as exc:
            logger.warning(f"algo {ALGO_NAMES.get(algo, algo)} failed: {exc}")

    ratio = len(best_bytes) / len(data)
    logger.debug(
        f"compress_auto  {ALGO_NAMES[best_algo]}"
        f"  {len(best_bytes)}/{len(data)} B  ratio={ratio:.2f}"
    )
    return best_algo, best_bytes
