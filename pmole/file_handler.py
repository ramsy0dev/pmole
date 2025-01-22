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

from pathlib import Path
from typing import Generator

class FileHandler:
    """
    FileHandler
    """
    def __init__(self, file_path: str) -> None:
        self.file_path = file_path

    def read(self, threads: int, chunks: int | None = None) -> Generator[bytes]:
        """
        Read the file data.
        """
        # Calculate the chunks needed to read the file
        if chunks is None:
            size = Path(self.file_path).__sizeof__()
            chunks = int(size/threads)
        
        with open(self.file_path, "rb") as f:
            while buffer:= f.read(chunks):
                yield buffer
    
    def next_at(self) -> None: ...

    def close(self) -> None: ...
