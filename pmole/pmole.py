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

from pathlib import Path

from pmole.globals import logger
from pmole.convert import Convert

from pmole.file_handler import FileHandler

# Utils
from pmole.utils import Nodes
from pmole.utils import measure_time

class Pmole:
    """
    pmole is a compression algorithm that aims to convert large
    amount of data into smaller ones that can proccessed as needed.
    """
    def __init__(self) -> None:
        self.convert = Convert()

    @measure_time
    def compress(self, file_path: str, directory_path: str | None = None, threads: int | None = 3) -> None:
        """
        Compress a file or a directory.
        """
        file = FileHandler(file_path)
        file_structure = self.generate_file_structure(
            file_path=file_path
        )

        for buffer in file.read(threads):
            b2_buffer = b"-- " + b'\x01'.join(self.convert.convert_utf8_to_base_2(buffer.decode("ütf-8")))

            file_structure.next.data += b2_buffer + b"\n"

        with open(f"{Path(file_path).name.split('.')[0]}.pm", "wb") as o:
            output_data = self.output_file_data(file_structure)
            o.write(output_data)
        
    def decompress(self) -> None: ...

    def generate_file_structure(self, file_path: str, directory_path: str | None = None) -> Nodes:
        """
        Generate the .pm file structure.
        """
        root_node = Nodes(prev=None)

        root_node_data = [
            f":: {Path(file_path).name}"
        ]
        root_node.data = bytes(str(''.join(root_node_data)).encode("utf-8"))

        data_node = Nodes(prev=root_node)
        
        root_node.next = data_node
        
        data_node.data = bytes()

        return root_node
    
    def output_file_data(self, file_structure: Nodes) -> bytes:
        """
        convert the file structure into a file's data
        """
        output_data = [
            file_structure.data.decode('utf-8', errors='replace'),  # Decode bytes to string
            file_structure.next.data.decode('utf-8', errors='replace')  # Decode bytes to string
        ]

        return bytes(str('\n'.join(output_data)).encode("utf-8"))
