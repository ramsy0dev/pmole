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
    "PLATFORM",
    "SLASH",
    "HOME_DIRECTORY",
    "ROOT_CONFIG_DIR",
    "CACHE_DIR",
    "EXCLUDE_EXTENSIONS",
    "EXCLUDE_DIRECTORIES",
    "EXCLUDE_FILENAMES",
    "MAX_FILE_SIZE_BYTES",
]

import os

from pmole.utils import (
    get_platform,
    create_path,
    PL_WINDOWS,
    PL_LINUX
)

PLATFORM = get_platform()

SLASH = "/" if PLATFORM == PL_LINUX else "\\"
HOME_DIRECTORY = os.path.expanduser("~")

if PLATFORM == PL_LINUX:
    ROOT_CONFIG_DIR = f"{HOME_DIRECTORY}{SLASH}pmole"
elif PLATFORM == PL_WINDOWS:
    ROOT_CONFIG_DIR = f"{HOME_DIRECTORY}{SLASH}pmole"

CACHE_DIR = ROOT_CONFIG_DIR + SLASH + "cache"

# Files larger than this are skipped during compression (50 MB default).
# Override via the API's max_file_size_bytes parameter.
MAX_FILE_SIZE_BYTES: int = 50 * 1024 * 1024  # 50 MB

# ---------------------------------------------------------------------------
# Auto-exclusion: extensions
# ---------------------------------------------------------------------------
# Extensions are matched case-insensitively without the leading dot.
# The list covers compiled artifacts, binary formats that are already
# compressed, lock files, and runtime outputs that have no place in a
# codebase snapshot.
EXCLUDE_EXTENSIONS: list[str] = [
    # ── Compiled / executable ───────────────────────────────────────────
    "exe", "dll", "so", "dylib", "ko", "sys", "efi",
    "lib", "a", "o", "obj",
    "out", "elf", "bin", "wasm",
    "app", "framework",
    "msi", "bat", "cmd",

    # ── Python bytecode ─────────────────────────────────────────────────
    "pyc", "pyo", "pyd",

    # ── JVM / .NET ──────────────────────────────────────────────────────
    "class", "jar",
    "dll",          # already above, listed for clarity
    "pdb",

    # ── Mobile / embedded ───────────────────────────────────────────────
    "apk", "ipa", "xex", "xbe", "3dsx",

    # ── Game engine ─────────────────────────────────────────────────────
    "pak", "gdc", "pck", "uasset",

    # ── Raw / firmware ──────────────────────────────────────────────────
    "img", "hex", "srec", "rom", "bios", "bootloader", "boot",

    # ── Archives / already-compressed ───────────────────────────────────
    # These won't benefit from a second compression pass.
    "zip", "gz", "bz2", "xz", "zst", "lz4", "7z", "rar", "tar",
    "tgz", "tbz2", "txz",

    # ── Images ──────────────────────────────────────────────────────────
    # Raster formats are already compressed; archiving them gains nothing.
    "png", "jpg", "jpeg", "gif", "bmp", "tiff", "tif",
    "webp", "avif", "heic", "ico",

    # ── Audio / video ───────────────────────────────────────────────────
    "mp3", "mp4", "wav", "flac", "ogg", "aac", "m4a",
    "avi", "mkv", "mov", "wmv", "flv", "webm",

    # ── Fonts ───────────────────────────────────────────────────────────
    "ttf", "otf", "woff", "woff2", "eot",

    # ── Database files ──────────────────────────────────────────────────
    "sqlite", "sqlite3", "db", "mdb", "accdb",

    # ── Lock files ──────────────────────────────────────────────────────
    # Regenerable; often large; not part of source truth.
    "lock",

    # ── Source maps ─────────────────────────────────────────────────────
    "map",

    # ── Log / temp ──────────────────────────────────────────────────────
    "log", "tmp", "bak", "swp", "swo",
]

# ---------------------------------------------------------------------------
# Auto-exclusion: directories
# ---------------------------------------------------------------------------
# Matched case-insensitively against every path component between the root
# and the file.  Add project-specific names via the API's
# exclude_directories parameter.
EXCLUDE_DIRECTORIES: list[str] = [
    # ── Version control ─────────────────────────────────────────────────
    ".git", ".svn", ".hg", ".bzr",

    # ── Python ──────────────────────────────────────────────────────────
    "__pycache__",
    "venv", ".venv", "env", ".env",
    ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    ".pytype", ".pyre",
    "htmlcov", ".eggs", ".egg-info",

    # ── Node / JS ecosystem ─────────────────────────────────────────────
    "node_modules",
    ".next", ".nuxt", ".svelte-kit",
    ".turbo", ".parcel-cache",

    # ── Build outputs ───────────────────────────────────────────────────
    "build", "dist", "out", "bin", "obj",
    "target",          # Rust / Maven
    ".gradle",         # Gradle cache

    # ── IDEs / editors ──────────────────────────────────────────────────
    ".idea", ".vscode", ".vs", ".eclipse", ".fleet",

    # ── Package caches ──────────────────────────────────────────────────
    ".m2",             # Maven local repo
    ".bundle",         # Bundler (Ruby)
    "vendor",          # Go modules / PHP Composer

    # ── Test / coverage ─────────────────────────────────────────────────
    "coverage", "cov", ".coverage",

    # ── Misc generated / transient ──────────────────────────────────────
    "lib", "libs",
    "assets", "res", "resources", "ressources",
    "static", "public",
    "cache", ".cache",
    "tmp", "temp",
    "fonts", "media",
    "data",
    ".terraform",
    ".docker",
    "$recycle.bin",
    ".spotlight-v100",
]

# ---------------------------------------------------------------------------
# Auto-exclusion: specific filenames
# ---------------------------------------------------------------------------
# Exact filename match (case-insensitive).  Use this for OS artifacts,
# secret files, and other names that cannot be identified by extension alone.
EXCLUDE_FILENAMES: list[str] = [
    # ── OS artifacts ────────────────────────────────────────────────────
    ".ds_store",
    "thumbs.db",
    "desktop.ini",
    ".spotlight-v100",

    # ── Secrets / local config ──────────────────────────────────────────
    ".env",            # runtime secrets; archive .env.example instead

    # ── Editor swap files ───────────────────────────────────────────────
    # (also covered by extension, belt-and-suspenders for dotfiles)
    ".swp", ".swo",

    # ── Compiled Python in root ─────────────────────────────────────────
    # (also covered by extension)
    "__pycache__",

    # ── pmole ignore files ───────────────────────────────────────────────
    ".pmignore",
]
