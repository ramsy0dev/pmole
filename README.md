# pmole

Compress an entire codebase into a single binary `.pm` file.
Works on text **and** binary files. Supports encryption, in-archive search, integrity verification, and single-file extraction without full decompression.

## Installation

```bash
pip install git+https://github.com/ramsy0dev/pmole
```

or from source:

```bash
git clone https://github.com/ramsy0dev/pmole --depth=1
cd pmole
pip install -e .
```

---

## Library usage

### Compress

```python
import pmole

# Auto-selects the best algorithm per file (default)
archive = pmole.compress("./myproject")                        # → "myproject.pm"
archive = pmole.compress("./myproject", output="out.pm")

# Force a specific algorithm for every file
archive = pmole.compress("./myproject", algo="lzma")           # best ratio, slower
archive = pmole.compress("./myproject", algo="zlib")           # fast, good ratio
archive = pmole.compress("./myproject", algo="lzw")            # pure LZW

# Control parallelism (default threads=3)
archive = pmole.compress("./myproject", threads=8)

# Encrypt with AES-256-GCM
archive = pmole.compress("./myproject", password="s3cr3t")
```

### List contents

```python
entries = pmole.list_files(archive)
for e in entries:
    print(f"{e.path:40s}  {e.original_size:>8} B  "
          f"ratio={e.compression_ratio:.2f}  [{e.algo_name}]  "
          f"{'binary' if e.is_binary else 'text'}")

# Encrypted archive
entries = pmole.list_files(archive, password="s3cr3t")
```

### Extract and decompress

```python
# Extract one file
out = pmole.extract(archive, "myproject/main.py", output_dir="/tmp/out")

# Decompress entire archive; returns list of paths written
paths = pmole.decompress(archive, output_dir="/tmp/restored")
paths = pmole.decompress(archive, output_dir="/tmp/restored", threads=8)

# Encrypted archive
paths = pmole.decompress(archive, output_dir="/tmp/restored", password="s3cr3t")
```

### Codebase tools

```python
# Search for a regex pattern across all text files (nothing written to disk)
matches = pmole.search(archive, r"def \w+\(")
for m in matches:
    print(f"{m['path']}:{m['line_no']}: {m['line']}")

# Verify every file decompresses correctly (nothing written to disk)
results = pmole.verify(archive)
failures = [r for r in results if not r["ok"]]

# Compression statistics grouped by file extension
s = pmole.stats(archive)
print(f"{s['total_files']} files, "
      f"{s['total_original']} B → {s['total_compressed']} B")
for ext, bucket in s["by_extension"].items():
    ratio = bucket["compressed"] / bucket["original"]
    print(f"  {ext}: {bucket['files']} files, ratio={ratio:.2f}")

# Check whether an archive is password-protected
pmole.is_encrypted(archive)  # → True / False
```

### Raw algorithm access

```python
# LZW only
codes = pmole.lzw_compress(b"hello world hello world")
data  = pmole.lzw_decompress(codes)

# Any algorithm by constant
from pmole import ALGO_LZMA
from pmole.compression import compress_with_algo, decompress_with_algo

compressed = compress_with_algo(b"hello world", ALGO_LZMA)
original   = decompress_with_algo(compressed, ALGO_LZMA)
```

---

## Encryption

`compress(..., password="...")` encrypts the archive with **AES-256-GCM**.

| Property         | Value                                        |
|------------------|----------------------------------------------|
| Cipher           | AES-256-GCM (authenticated encryption)       |
| Key derivation   | PBKDF2-HMAC-SHA256, 260 000 iterations       |
| Salt             | 16 random bytes (unique per archive)         |
| Nonce            | 12 random bytes (unique per archive)         |
| Envelope magic   | `PME\x01` (distinct from plain `.pm`)        |
| Overhead         | 48 bytes over the compressed archive size    |

An incorrect password raises `ValueError` immediately — the GCM authentication tag fails before any data is returned. All read operations (`decompress`, `list_files`, `extract`, `verify`, `search`, `stats`) accept the same `password` parameter.

The `PMOLE_PASSWORD` environment variable is used by the CLI as a fallback so the password is never visible in shell history.

---

## Compression algorithms

Four algorithms are available. Use `algo="auto"` (the default) to let pmole benchmark each one per file and keep the smallest result.

| Constant        | Name        | Description                                                      | Best for                        |
|-----------------|-------------|------------------------------------------------------------------|---------------------------------|
| `ALGO_LZW`      | `"lzw"`     | Pure LZW, codes packed as uint16 LE                              | Highly repetitive data          |
| `ALGO_LZW_ZLIB` | `"lzw+zlib"`| LZW uint16 stream further compressed with zlib                   | Repetitive text with patterns   |
| `ALGO_ZLIB`     | `"zlib"`    | zlib / DEFLATE (LZ77 + Huffman), Python built-in                 | Source code, mixed content      |
| `ALGO_LZMA`     | `"lzma"`    | LZMA, Python built-in                                            | Best ratio, any content         |

> **Note:** LZW-based algorithms (`lzw`, `lzw+zlib`) are automatically skipped for files larger than 10 MB; only `zlib` and `lzma` are tried for large files.

---

## `ArchiveEntry`

`list_files()` returns a list of `ArchiveEntry` dataclass instances:

| Field               | Type    | Description                                      |
|---------------------|---------|--------------------------------------------------|
| `path`              | `str`   | Archived path (forward slashes)                  |
| `original_size`     | `int`   | Uncompressed size in bytes                       |
| `compressed_size`   | `int`   | Compressed size in bytes                         |
| `is_binary`         | `bool`  | Detected as binary (metadata only)               |
| `algo`              | `int`   | Algorithm ID used for this file                  |
| `data_offset`       | `int`   | Byte offset of this file's section in archive    |
| `compression_ratio` | `float` | `compressed_size / original_size` (property)     |
| `algo_name`         | `str`   | Human-readable algorithm name (property)         |

---

## Auto-exclusion

`compress()` applies five independent exclusion layers before touching any file. All defaults are exported from `pmole` and can be overridden per call.

### `.pmignore` / `.gitignore`

When compressing a directory, pmole looks for `.pmignore` in the root first, then `.gitignore`. If found, its patterns are applied using full gitignore semantics (`**`, negation `!`, directory anchoring `/`). `.pmignore` itself is always excluded from the archive.

Create a `.pmignore` to override or extend `.gitignore` patterns for archiving:

```
# .pmignore
*.log
scratch/
local_settings.py
```

### File extensions — `EXCLUDE_EXTENSIONS`

Files whose suffix (case-insensitive, no leading dot) matches are skipped.

| Category              | Extensions                                                                 |
|-----------------------|----------------------------------------------------------------------------|
| Compiled / executable | `exe` `dll` `so` `dylib` `ko` `sys` `efi` `lib` `a` `o` `obj` `out` `elf` `bin` `wasm` `app` `msi` `bat` `cmd` |
| Python bytecode       | `pyc` `pyo` `pyd`                                                          |
| JVM / .NET            | `class` `jar` `pdb`                                                        |
| Mobile / embedded     | `apk` `ipa` `xex` `xbe` `3dsx`                                            |
| Game engine           | `pak` `gdc` `pck` `uasset`                                                |
| Raw / firmware        | `img` `hex` `srec` `rom` `bios` `bootloader` `boot`                       |
| Archives              | `zip` `gz` `bz2` `xz` `zst` `lz4` `7z` `rar` `tar` `tgz` `tbz2` `txz`  |
| Images                | `png` `jpg` `jpeg` `gif` `bmp` `tiff` `tif` `webp` `avif` `heic` `ico`   |
| Audio / video         | `mp3` `mp4` `wav` `flac` `ogg` `aac` `m4a` `avi` `mkv` `mov` `wmv` `flv` `webm` |
| Fonts                 | `ttf` `otf` `woff` `woff2` `eot`                                          |
| Databases             | `sqlite` `sqlite3` `db` `mdb` `accdb`                                     |
| Lock files            | `lock`                                                                     |
| Source maps           | `map`                                                                      |
| Log / temp            | `log` `tmp` `bak` `swp` `swo`                                             |

### Directories — `EXCLUDE_DIRECTORIES`

Any path component (between the root and the file) that matches is skipped, case-insensitively.

| Category              | Names                                                                                   |
|-----------------------|-----------------------------------------------------------------------------------------|
| Version control       | `.git` `.svn` `.hg` `.bzr`                                                              |
| Python                | `__pycache__` `venv` `.venv` `env` `.env` `.tox` `.mypy_cache` `.pytest_cache` `.ruff_cache` `.pytype` `.pyre` `htmlcov` `.eggs` `.egg-info` |
| Node / JS             | `node_modules` `.next` `.nuxt` `.svelte-kit` `.turbo` `.parcel-cache`                   |
| Build outputs         | `build` `dist` `out` `bin` `obj` `target` `.gradle`                                    |
| IDEs / editors        | `.idea` `.vscode` `.vs` `.eclipse` `.fleet`                                             |
| Package caches        | `.m2` `.bundle` `vendor`                                                                |
| Test / coverage       | `coverage` `cov` `.coverage`                                                            |
| Misc generated        | `lib` `libs` `assets` `res` `resources` `static` `public` `cache` `.cache` `tmp` `temp` `fonts` `media` `data` `.terraform` `.docker` |

### Filenames — `EXCLUDE_FILENAMES`

Exact filename match, case-insensitive.

| File           | Reason                                  |
|----------------|-----------------------------------------|
| `.DS_Store`    | macOS directory metadata                |
| `Thumbs.db`    | Windows thumbnail cache                 |
| `desktop.ini`  | Windows folder settings                 |
| `.env`         | Runtime secrets (archive `.env.example` instead) |
| `.swp` `.swo`  | Vim swap files                          |
| `.pmignore`    | pmole ignore file (meta — not archived) |

### File size — `MAX_FILE_SIZE_BYTES`

Files larger than **50 MB** (default) are skipped with an info log. Override per call:

```python
pmole.compress("./data", max_file_size_bytes=10 * 1024 * 1024)  # 10 MB cap
```

### Customising filters

All four lists are exported at the top level. Pass replacements directly to `compress()`:

```python
import pmole

# Extend the defaults
pmole.compress(
    "./myproject",
    exclude_extensions=[*pmole.EXCLUDE_EXTENSIONS, "csv", "parquet"],
    exclude_directories=[*pmole.EXCLUDE_DIRECTORIES, "migrations"],
    exclude_filenames=[*pmole.EXCLUDE_FILENAMES, "secrets.json"],
    max_file_size_bytes=5 * 1024 * 1024,
)

# Or replace them entirely
pmole.compress("./myproject", exclude_extensions=[], exclude_directories=[])
```

---

## CLI usage

```bash
# Enable debug output (timestamps + source location on every log line)
pmole --debug compress ./myproject

# Compress a directory (auto algorithm, 3 threads)
pmole compress ./myproject

# Force a specific algorithm
pmole compress ./myproject --algo lzma
pmole compress ./myproject -a zlib

# Compress a single file
pmole compress ./README.md

# Custom output path, more threads
pmole compress ./myproject -o out.pm -t 8

# Encrypt the archive
pmole compress ./myproject -p mysecret
# or via environment variable (keeps password out of shell history)
PMOLE_PASSWORD=mysecret pmole compress ./myproject

# Add extra exclusions
pmole compress ./myproject \
    --exclude-dir ".cache,scratch" \
    --exclude-ext "csv,parquet" \
    --exclude-name "local_settings.py"

# List archive contents (no decompression)
pmole list myproject.pm
pmole list myproject.pm -p mysecret            # encrypted

# Show directory tree structure
pmole tree myproject.pm

# Extract one file (optional output dir, default = current dir)
pmole extract myproject.pm myproject/main.py /tmp/out

# Decompress full archive (optional output dir, default = current dir)
pmole decompress myproject.pm /tmp/restored
pmole decompress myproject.pm -t 8             # more threads
pmole decompress myproject.pm -p mysecret      # encrypted

# Verify archive integrity (no disk writes)
pmole verify myproject.pm

# Search for a regex pattern in all text files (no disk writes)
pmole search myproject.pm "def \w+"
pmole search myproject.pm "TODO|FIXME"

# Show compression statistics grouped by file extension
pmole stats myproject.pm

# Diff two files
pmole diff a.py b.py
```

### Debug output

`--debug` is a global flag that must come **before** the sub-command name. It switches the log format from the terse default to a timestamped form that includes the source file and line number — useful when diagnosing slow archives or unexpected exclusions.

```
# Normal output (default)
INFO      scan  42 source files
INFO      pack  src/utils.py  8120 B → 1943 B  [lzma]
INFO      wrote  myproject.pm

# Debug output  (pmole --debug compress …)
14:23:01  DEBUG     [utils.py:215]   Excluded 'src/vendor/jquery.min.js' (extension: js)
14:23:01  DEBUG     [compression.py:173]  compress_auto  lzma  1823/4096 B  ratio=0.44
14:23:01  INFO      scan  42 source files
```

Per-file exclusion lines (`Excluded '…'`) are only shown in debug mode; they are suppressed at the default INFO level to keep normal output clean.

---

## `.pm` format overview

A `.pm` file (magic `PM\x03\x00`) has three sections:

1. **Header** (16 bytes) — magic, file count, byte offset to the index table.
2. **File sections** — one per stored file: an 18-byte header (`original_size`, `compressed_size`, `is_binary`, `algo`) followed by the compressed payload.
3. **Index table** (at end) — one entry per file storing its path, sizes, algorithm, and `data_offset`, enabling listing and single-file extraction by seeking directly to the right section.

When encrypted, the entire `.pm` content is wrapped in an **encrypted envelope** (magic `PME\x01`, 32-byte header containing salt and nonce, followed by the AES-256-GCM ciphertext). See [ARCHITECTURE.md](ARCHITECTURE.md) for the full byte-level specification.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full byte-level specification and design rationale.

## Testing

```bash
# Run all tests
pytest

# Run only the fast correctness + credibility suite
pytest tests/test_api.py tests/test_credibility.py tests/test_algo_lzw.py

# Run benchmarks (single iteration each, no stats)
pytest tests/test_benchmark.py -v

# Run benchmarks with full statistics (requires pytest-benchmark)
pip install pytest-benchmark
pytest tests/test_benchmark.py -v --benchmark-sort=mean

# Print the compression ratio table
pytest -s tests/test_credibility.py::test_ratio_summary_table
```

### Test files

| File | Purpose |
|---|---|
| `tests/test_api.py` | Integration smoke tests for the public API (compress, decompress, encrypt, verify, search, stats, exclusions) |
| `tests/test_algo_lzw.py` | Unit tests for the raw LZW compressor / decompressor |
| `tests/test_credibility.py` | Quantitative correctness and ratio-bound tests — edge-case roundtrips (empty, single byte, all-zeros, all-`0xFF`, 200 KB repetitive, 500 KB random), ratio thresholds per algorithm, auto-selection invariants, archive metadata accuracy, double-roundtrip identity, unicode content, corrupt-archive handling |
| `tests/test_benchmark.py` | Performance benchmarks for raw compress/decompress throughput per algorithm, auto-select overhead, full archive creation/restoration, thread-scaling (1 / 2 / 4 threads), and verify/search timing |
| `tests/conftest.py` | Provides a minimal `benchmark` fixture when `pytest-benchmark` is not installed so the benchmark tests always run |

## LICENSE

[MIT](https://github.com/ramsy0dev/pmole/blob/main/LICENSE)
