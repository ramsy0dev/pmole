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
    "Pmole"
]

from pathlib import Path
from loguru import logger

from pmole.convert import Convert

from pmole.file_handler import FileHandler

# LZW algorithm
from pmole.lzw import LZW
from pmole.lzw import LZWDictionary

# File handler
from pmole.file_handler import FileHandler
from pmole.file_handler import BY_LINE

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
    def compress(self, file_path: str | None = None, directory_path: str | None = None, threads: int | None = 7) -> None:
        """
        Compress a file or a directory.
        """
        files: list[FileHandler] = list()
        files_paths: list[str] = list()
        
        if directory_path is not None:
            files_paths = list_files_in_directory(
                directory=directory_path
            )
            
            logger.info(f"Found {len(files_paths)} files.")

            files = [FileHandler(file_path) for file_path in files_paths]
        else:
            files = [FileHandler(file_path), ]
            files_paths = [file_path, ]

        file_structure = self.generate_file_structure(
            files_paths=[file_path for file_path in files_paths]
        )

        output_data: list[list[int]] = list()
        
        for file in files:
            dictionary: LZWDictionary = LZWDictionary()
            dictionary.create()
        
            logger.info(f"Compressing file `{file.file_path}`...")

            file_buffer = file.read(threads)
            # Decode bytes to string for LZW compression
            string_data = (chunk.decode('utf-8') for chunk in file_buffer)
            compressed_data = self.lzw.compress(
                data=string_data,
                dictionary=dictionary
            )
            
            output_data.append(compressed_data)
        
        if len(files_paths) > 1:
            output_file_name = Path(directory_path).name + ".pm"
        else:
            output_file_name = Path(file_path).name.split(".")[0] + ".pm"
        
        logger.info("Constructing compress output file's data...")

        compressed_file_content = self.output_file_data(
            file_structure=file_structure,
            compressed_data=output_data
        )

        logger.debug(f"Compressed file content preview: {repr(compressed_file_content[:100])}")

        output_file = FileHandler(output_file_name)
        output_file.write(
            compressed_file_content
        )

        logger.info(f"Compressing is done. output file is `{output_file_name}`.")

    def decompress(self, file_path: str, threads: int | None = 3) -> None:
        """
        Decompress data with visual formatting support
        """
        file = FileHandler(file_path=file_path)

        # Read entire file content at once to handle multi-line compressed data
        file_content = ""
        for buffer in file.read(threads=threads, mode=BY_LINE):
            file_content += buffer.decode("utf-8")

        # Parse the file content
        lines = file_content.strip().split('\n')
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            if line.startswith(":: "):
                # Extract file path
                file_path = line[3:].strip()  # Remove ":: " prefix
                logger.debug(f"Found file path `{file_path}`")

                # Create file handler for this file
                file_h = FileHandler(file_path=file_path)

                # Collect all compressed tokens for this file
                compressed_tokens = []
                i += 1  # Move to next line

                # Collect tokens from all "--" lines until "[EOF]" is found
                found_eof = False
                while i < len(lines) and not found_eof:
                    line = lines[i].strip()

                    if line.startswith("-- "):
                        # Parse tokens from this line
                        parts = line.split()
                        # Skip "--" and collect tokens until "[EOF]" or end
                        for part in parts[1:]:
                            if part == "[EOF]":
                                # Found end marker, we've collected all tokens
                                found_eof = True
                                break
                            try:
                                compressed_tokens.append(int(part))
                            except ValueError:
                                logger.warning(f"Invalid token '{part}', skipping")
                        i += 1
                    elif line.startswith(":: "):
                        # Next file started, break
                        break
                    else:
                        i += 1

                # Decompress the collected tokens
                if compressed_tokens and found_eof:
                    logger.info(f"Decompressing file `{file_path}`...")

                    decompressed_file_data = self.lzw.decompress(
                        compressed_data=compressed_tokens
                    )
                    logger.debug(f"Decompressed file data: \n{decompressed_file_data}")

                    file_h.write(data=decompressed_file_data)

            else:
                i += 1

    def generate_file_structure(self, files_paths: str, directory_path: str | None = None) -> Nodes:
        """
        Generate the .pm file structure.
        """
        root_node = Nodes(prev=None)

        root_node_data = []
        for file_path in files_paths:
            root_node_data.append(f":: {file_path}")  # Remove trailing newline

        root_node.data = root_node_data

        data_node = Nodes(prev=root_node)

        root_node.next = data_node

        data_node.data = str()

        return root_node
    
    def output_file_data(self, file_structure: Nodes, compressed_data: list[list[int]], threads_n: int | None = 7) -> str:
        """
        Convert the file structure into a file's data.
        Format compressed tokens with newlines for visual beauty.
        """
        output_data = []

        logger.debug(f"Number of compressed file data: {len(compressed_data)}")

        for i in range(len(compressed_data)):
            if i == 0:
                output_data.append(file_structure.data[i])
            else:
                output_data.append("\n\n" + file_structure.data[i])

            # Format compressed tokens with newlines for readability
            token_strings = [str(token) for token in compressed_data[i]]

            # Group tokens into lines of ~12 tokens for visual appeal
            line_length = 12
            lines = []
            for j in range(0, len(token_strings), line_length):
                chunk = token_strings[j:j + line_length]
                lines.append("-- " + " ".join(chunk))

            # Add [EOF] to the last line
            if lines:
                lines[-1] += " [EOF]"
            else:
                lines.append("-- [EOF]")

            output_data.extend(lines)

        return "\n".join(output_data)
