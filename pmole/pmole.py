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

from pmole.convert import Convert

from pmole.file_handler import FileHandler

# Algos
from pmole.algo import LZW
from pmole.algo import LZWDictionary

# File handler
from pmole.file_handler import FileHandler

# Utils
from pmole.utils import Nodes
from pmole.utils import measure_time
from pmole.utils import list_files_in_directory

class Pmole:
    """
    pmole is a compression algorithm that aims to convert large
    amount of data into smaller ones that can proccessed as needed.
    """
    def __init__(self) -> None:
        self.convert = Convert()
        self.lzw = LZW()
    
    @measure_time
    def compress(self, file_path: str, directory_path: str | None = None, threads: int | None = 3) -> None:
        """
        Compress a file or a directory.
        """
        files: list[FileHandler] = list()
        files_paths: list[str] = list()
        dictionary: LZWDictionary = LZWDictionary()
        dictionary.create()

        if directory_path is not None:
            files_paths = list_files_in_directory(
                directory=directory_path
            )
            files = [FileHandler(file_path) for file_path in files_paths]
        else:
            files = [FileHandler(file_path), ]
        
        file_structure = self.generate_file_structure(
            files_paths=[file.file_path for file in files]
        )

        output_data: list[list[int]] = list()
        
        for file in files:
            file_buffer = file.read(threads)
            compressed_data = self.lzw.compress(
                data=file_buffer
            )
            output_data.append(compressed_data)
        
        if len(files_paths) > 1:
            output_file_name = Path(directory_path).name + ".pm"
        else:
            output_file_name = Path(file_path).name.split(".")[0] + ".pm"
        
        output_data = self.output_file_data(
            file_structure=file_structure,
            compressed_data=output_data
        )
        
        output_file = FileHandler(output_file_name)
        output_file.write(
            output_data
        )

    def decompress(self, file_path: str, threads: int | None = 3) -> None:    
        """
        Decompress data
        """
        pass

    def generate_file_structure(self, files_paths: str, directory_path: str | None = None) -> Nodes:
        """
        Generate the .pm file structure.
        """
        root_node = Nodes(prev=None)

        root_node_data = []
        for file_path in files_paths:
            root_node_data.append(f":: {Path(file_path).name}\n")
         
        root_node.data = root_node_data

        data_node = Nodes(prev=root_node)
        
        root_node.next = data_node
        
        data_node.data = str()

        return root_node
    
    def output_file_data(self, file_structure: Nodes, compressed_data: list[list[int]], threads_n: int | None = 3) -> bytes:
        """
        convert the file structure into a file's data
        """
        output_data: list = list()

        for i in range(len(compressed_data)):
            output_data.append(file_structure.data[i])
            line_length = 0
            
            if len(compressed_data[i]) < 80:
                line_length = int(len(compressed_data[i])/8)
            else:
                line_length = int(len(compressed_data[i])/12)
            
            buffer = []

            for _ in range(len(compressed_data[i])):
                token = compressed_data[i][_]
                if len(buffer) == line_length:
                    output_data.append("\n" + " ".join(buffer))
                    buffer = []
                else:
                    buffer.append(str(token))
                    if len(compressed_data[i]) == _:
                        output_data.append("\n" + " ".join(buffer))

            return "".join(output_data)
    