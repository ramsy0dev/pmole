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

import typer

from pathlib import Path

from .pmole import Pmole
from pmole.globals import logger

cli = typer.Typer()

@cli.command()
def compress(
    file_path: str = typer.Option(None, "--file-path", help="The file path."),
    directory_path: str = typer.Option(None, "--dir-path", help="The directory path."),
    threads: int = typer.Option(3, "--threads", help="The number of threads.")
):
    """
    Compress a file
    """
    path = file_path if file_path is not None else directory_path

    if not Path(path).exists():
        logger.error(f"The provided path '{path}' doesn't exists.")
        exit(1)
    
    if Path(path).is_symlink():
        logger.error(f"Symlinks are not supported.")
        exit(1)

    pmole = Pmole()

    pmole.compress(
        file_path=file_path,
        directory_path=directory_path,
        threads=threads
    )

@cli.command()
def decompress(
    pm_file_path: str = typer.Option(None, "--pm-file-path", help="The compressed file path (.pm)."),
    threads: int = typer.Option(3, "--threads", help="The number of threads.")
):
    """
    Decompress a file
    """
    pass


def run() -> None:
    cli()
