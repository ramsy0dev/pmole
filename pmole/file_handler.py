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
    "FileHandler",
    "BY_LINE",
    "BY_CHUNKS"
]

from pathlib import Path
from typing import Generator

from pmole.utils import create_path
from pmole.globals import SLASH

# File reading modes
BY_LINE: int = 0
BY_CHUNKS: int = 1

class FileHandler:
    """
    FileHandler
    """
    def __init__(self, file_path: str) -> None:
        self.file_path = file_path

    def read(self, threads: int, mode: int | None = BY_CHUNKS, chunks: int | None = None) -> Generator[bytes]:
        """
        Read the file data.
        """
        # Calculate the chunks needed to read the file
        if chunks is None:
            size = Path(self.file_path).__sizeof__()
            chunks = int(size / threads)

        with open(self.file_path, "rb") as f:
            if mode == BY_CHUNKS:
                while buffer := f.read(chunks):
                    yield buffer

            if mode == BY_LINE:
                for line in f:
                    yield line

    def write(self, data: str) -> None:
        """
        Write to the file.
        """
        file_path: str = None
        
        if len(self.file_path.split(SLASH)) < 2:
            file_path = self.file_path
        else:
            file_path = create_path(
                path=self.file_path
            )
        
        with open(file_path, "w") as o:
            o.write(data)

