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
    "run"
]

import os

import typer

from loguru import logger
from pathlib import Path

from .pmole import Pmole

# Globals
from pmole.globals import (
    CACHE_DIR,
    DICTIONARY_CACHE_FILE_PATH,
    REVERSE_DICTIONARY_CACHE_FILE_PATH,
)

cli = typer.Typer()

def setup_cli_dir() -> None:
    """
    Create directories needed for the cli.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    
    Path(DICTIONARY_CACHE_FILE_PATH).touch()
    Path(REVERSE_DICTIONARY_CACHE_FILE_PATH).touch()

@cli.command()
def compress(
    file_path: str = typer.Option(None, "--file-path", help="The file path."),
    directory_path: str = typer.Option(None, "--dir-path", help="The directory path."),
    threads: int = typer.Option(7, "--threads", help="The number of threads."),
):
    """
    Compress a file
    """
    path = file_path if file_path is not None else directory_path

    logger.info(
        f"Compressing {'file' if file_path is not None else 'directory'} `{path}`..."
    )

    if not Path(path).exists():
        logger.error(f"The provided path '{path}' doesn't exists.")
        exit(1)

    if Path(path).is_symlink():
        logger.error(f"Symlinks are not supported.")
        exit(1)

    pmole = Pmole()

    pmole.compress(file_path=file_path, directory_path=directory_path, threads=threads)

@cli.command()
def decompress(
    pm_file_path: str = typer.Option(
        None, "--pm-file-path", help="The compressed file path (.pm)."
    ),
    threads: int = typer.Option(7, "--threads", help="The number of threads."),
):
    """
    Decompress a file
    """
    if not Path(pm_file_path).exists():
        logger.error(f"The provided path '{pm_file_path}' doesn't exists.")
        exit(1)

    logger.info(f"Decompressing `{pm_file_path}`...")

    pmole = Pmole()

    pmole.decompress(file_path=pm_file_path, threads=threads)

    logger.info(f"Decompressing is complete.")

def run() -> None:
    setup_cli_dir()
    cli()
