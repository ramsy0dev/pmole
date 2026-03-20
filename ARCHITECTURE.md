# pmole — Architecture

This document describes the internal design of pmole: module responsibilities, the binary `.pm` format, the encryption envelope, the compression layer, LZW implementation details, data flows for each major operation, and the auto-exclusion system.

---

## Module Map

```
pmole/
├── __init__.py       public API re-exports, __all__
├── api.py            thin wrappers + ArchiveEntry dataclass  ← user entry point
├── pmole.py          Pmole class, PMFileWriter, _read_index, _open_pm
├── crypto.py         AES-256-GCM encryption / decryption envelope
├── compression.py    multi-algorithm layer (LZW, LZW+zlib, zlib, lzma)
├── lzw.py            LZW, LZWCompressor, RESET_CODE
├── file_handler.py   FileHandler (chunked read, write, write_binary)
├── cli.py            Typer CLI (compress / decompress / list / extract /
│                               verify / search / stats / tree / diff)
├── globals.py        CACHE_DIR, exclusion lists, MAX_FILE_SIZE_BYTES
└── utils.py          measure_time, list_files_in_directory, create_path, …
```

### Layer diagram

```
User code / CLI
      │
      ▼
  api.py  ────────────────────────────────────┐
  (validates input, resolves algo/password)   │
      │                                       │
      ▼                                       ▼
  pmole.py                             compression.py
  _open_pm()  ←── crypto.py            (ALGO_LZW / LZW_ZLIB / ZLIB / LZMA)
  PMFileWriter  ── write ──►  .pm          │
  Pmole.compress ── read  ◄── .pm          ▼
  Pmole.decompress                     lzw.py
  Pmole.list_files                     (LZWCompressor, LZW)
  Pmole.extract
  Pmole.verify
  Pmole.search
      │
      ▼
  file_handler.py
  (chunked reads, binary writes)
      │
      ▼
  filesystem
```

---

## Binary `.pm` Format (v3)

The format is entirely little-endian. All integer fields use Python `struct` LE types.
Magic bytes: `b"PM\x03\x00"` (version byte `\x03` was bumped from `\x02` when multi-algorithm support was added).

### File layout overview

```
┌─────────────────────────────────────────────────────┐
│  HEADER            (16 bytes, fixed)                │
├─────────────────────────────────────────────────────┤
│  FILE SECTION 0    (18 + compressed_size bytes)     │
│  FILE SECTION 1                                     │
│  …                                                  │
├─────────────────────────────────────────────────────┤
│  INDEX TABLE       (variable, at index_offset)      │
└─────────────────────────────────────────────────────┘
```

### HEADER — 16 bytes

| Offset | Size | Type      | Field          | Notes                              |
|--------|------|-----------|----------------|------------------------------------|
| 0      | 4    | bytes     | `magic`        | `b"PM\x03\x00"`                   |
| 4      | 4    | uint32 LE | `file_count`   | number of files in archive         |
| 8      | 8    | uint64 LE | `index_offset` | byte offset to INDEX TABLE         |

`index_offset` is written as `0` initially and patched by `PMFileWriter.finalize()` once all file sections are written.

### FILE SECTION — per file (18-byte header)

| Offset | Size               | Type      | Field             | Notes                                         |
|--------|--------------------|-----------|-------------------|-----------------------------------------------|
| 0      | 8                  | uint64 LE | `original_size`   | uncompressed byte count                       |
| 8      | 8                  | uint64 LE | `compressed_size` | byte length of the compressed payload         |
| 16     | 1                  | uint8     | `is_binary`       | 0=text, 1=binary (metadata only)              |
| 17     | 1                  | uint8     | `algo`            | compression algorithm ID (see table below)    |
| 18     | `compressed_size`  | bytes     | `payload`         | format depends on `algo`                      |

```python
struct.pack("<QQBB", original_size, compressed_size, is_binary, algo)  # 18 bytes
```

### INDEX TABLE — at `index_offset`

```
[uint32 LE]  entry_count

Per entry (28 bytes fixed + path):
  [uint64 LE]  data_offset      byte offset to this file's FILE SECTION start
  [uint64 LE]  original_size
  [uint64 LE]  compressed_size
  [uint8]      is_binary
  [uint8]      algo             same ID stored in the FILE SECTION header
  [uint16 LE]  path_length      byte length of the UTF-8 path string
  [bytes]      path             UTF-8, forward slashes, no null terminator
```

```python
struct.pack("<QQQBBH", data_offset, orig, compr, is_bin, algo, path_len)  # 28 bytes
```

Paths are always stored with forward slashes. On extraction, `Path(output_dir) / Path(*entry_path.split("/"))` reconstructs the OS-native path.

### Why index at the end?

Files are compressed in a single forward pass. Each file's compressed size is unknown before compression starts, so the index is written after all sections and the header's `index_offset` is back-patched with a `seek(4)` + write.

### Format version history

| Magic          | Version | Change                                                  |
|----------------|---------|---------------------------------------------------------|
| `PM\x02\x00`  | v2      | Binary format, LZW-only, 17-byte section header, 27-byte index entry |
| `PM\x03\x00`  | v3      | Multi-algorithm: added `algo` byte to section header and index entry (18 / 28 bytes) |

---

## Encrypted Archive Envelope (`crypto.py`)

When a password is supplied to `compress()`, the entire `.pm` file is wrapped in an **encrypted envelope** after writing. The envelope is a distinct file format identified by its own magic bytes.

### Envelope layout

```
┌──────────────────────────────────────────────────────────┐
│  magic   4 bytes   b"PME\x01"                           │
│  salt   16 bytes   random PBKDF2 salt                   │
│  nonce  12 bytes   random AES-GCM nonce                 │
├──────────────────────────────────────────────────────────┤
│  ciphertext + 16-byte GCM tag                           │
│  (AES-256-GCM encryption of the full .pm content)       │
└──────────────────────────────────────────────────────────┘
```

Total overhead: **48 bytes** (32-byte header + 16-byte GCM tag).

### Key derivation

```
key = PBKDF2-HMAC-SHA256(password, salt, iterations=260_000, dklen=32)
```

260 000 iterations meets the OWASP 2023 recommendation for PBKDF2-HMAC-SHA256. The 32-byte output is used directly as the AES-256 key.

### Authentication

AES-GCM produces a 16-byte authentication tag. Any modification to the ciphertext or wrong password causes `AESGCM.decrypt()` to raise, which `decrypt_archive()` catches and re-raises as `ValueError("Incorrect password or corrupted archive.")`. No partial data is ever returned.

### `_open_pm` context manager (`pmole.py`)

All read operations (`decompress`, `list_files`, `extract`, `verify`, `search`) go through `_open_pm(file_path, password)`:

```
_open_pm(file_path, password)
  ├─ read first 4 bytes
  ├─ if magic == b"PME\x01":
  │    if password is None → raise ValueError
  │    decrypt_archive(full file bytes, password) → plain bytes
  │    write plain bytes to tempfile.mkstemp()
  │    yield temp_path
  │    finally: os.unlink(temp_path)
  └─ else:
       yield file_path unchanged
```

The temp file lives for the entire `with _open_pm(...)` block, ensuring worker threads opened inside the block have a valid file descriptor for the duration of their work.

---

## Compression Layer (`compression.py`)

### Algorithm IDs

| Constant        | ID | Payload format                              | Characteristics                          |
|-----------------|----|---------------------------------------------|------------------------------------------|
| `ALGO_LZW`      | 0  | uint16 LE LZW code stream                   | Pure-Python LZW; good on repetitive text |
| `ALGO_LZW_ZLIB` | 1  | zlib of the uint16 code stream              | Pairs LZW dictionary substitution with zlib entropy coding |
| `ALGO_ZLIB`     | 2  | raw zlib / DEFLATE output                   | Fast; well-rounded for source code       |
| `ALGO_LZMA`     | 3  | raw lzma output                             | Best ratio; slower encode                |

### `compress_auto`

```
compress_auto(data: bytes) → (algo_id: int, compressed: bytes)
```

Tries every applicable algorithm and returns the `(id, bytes)` pair with the smallest result.

```
if len(data) > 10 MB:
    candidates = [ALGO_ZLIB, ALGO_LZMA]       # skip slow pure-Python LZW
else:
    candidates = [ALGO_LZW, ALGO_LZW_ZLIB, ALGO_ZLIB, ALGO_LZMA]

best = min(candidates, key=lambda a: len(compress_with_algo(data, a)))
```

The 10 MB threshold prevents the pure-Python `LZWCompressor` from spending seconds on large files where zlib or lzma will produce better results faster anyway.

### `compress_with_algo` / `decompress_with_algo`

Dispatch to the appropriate algorithm:

```
ALGO_LZW       → _lzw_to_bytes(data)                  /  _bytes_to_lzw(data)
ALGO_LZW_ZLIB  → zlib.compress(_lzw_to_bytes(data))   /  _bytes_to_lzw(zlib.decompress(data))
ALGO_ZLIB      → zlib.compress(data, level=9)          /  zlib.decompress(data)
ALGO_LZMA      → lzma.compress(data, preset=6)         /  lzma.decompress(data)
```

### `_lzw_to_bytes` — chunked packing

`LZWCompressor.feed()` is called in 64 KB increments. Each batch of returned codes is immediately packed to bytes and appended to a list; the list is joined once at the end. This avoids keeping all Python `int` objects in memory simultaneously (a list of 5 M Python ints ≈ 140 MB vs. the 10 MB packed bytes).

---

## LZW Implementation (`lzw.py`)

### Constants

```python
RESET_CODE = 256   # reserved; never used as a data code
# valid data codes: 0–255 (initial alphabet) and 257–65535 (learned entries)
```

### `LZWCompressor` — stateful streaming compressor

```
LZWCompressor
  code_table:     dict[bytes, int]   # bytes sequence → code
  next_code:      int                # next code to assign (starts at 257)
  current_bytes:  bytes              # partial match in progress
```

`feed(chunk: bytes) → list[int]`
: Extends `current_bytes` one byte at a time. On a miss, emits the code for `current_bytes`, adds the new sequence to `code_table`, and resets `current_bytes` to the current byte. If `next_code >= 65536` at assignment time, emits `RESET_CODE` (256) and calls `_reset()` before continuing.

`flush() → list[int]`
: Emits the pending code for any remaining `current_bytes`. Must be called after all chunks are fed.

`_reset()`
: Reinitialises `code_table = {bytes([i]): i for i in range(256)}` and `next_code = 257`. Does **not** emit `RESET_CODE` — the caller does that first.

### `LZW.compress` / `LZW.decompress`

`compress(data: bytes) → list[int]`
: Creates one `LZWCompressor`, calls `feed(data)` then `flush()`. Used by `compression._lzw_to_bytes` (which drives it in 64 KB chunks when called from `PMFileWriter`).

`decompress(compressed_data: list[int]) → bytes`
: Reconstructs data from a flat code list. Maintains a reverse table `{code: bytes}`, handles `RESET_CODE` by re-initialising the table mid-stream, uses an index variable instead of destructive `pop(0)` to keep O(n) behaviour.

### Why all codes fit in `uint16`

The dictionary resets when `next_code` would reach 65536. All emitted codes therefore fit in `[0, 65535]`, allowing 2-byte-per-code packing. Code 256 is `RESET_CODE` and is never a dictionary key.

### Why `bytes` keys, not `str` keys

Using `bytes([b])` as the base alphabet means every byte value 0–255 is handled identically with no `UnicodeDecodeError` on binary files.

---

## Data Flows

### compress

```
api.compress(path, output, algo, threads, password, exclude_*, max_file_size_bytes)
  └─ Pmole.compress(directory_path=…, output_path=…, algo=…, threads=…, password=…, …)
       ├─ list_files_in_directory()
       │    apply extension / directory / filename / size filters
       │    → list[str] file paths (order preserved)
       │
       ├─ _load_ignore_spec(directory_path)
       │    look for .pmignore, then .gitignore
       │    if found: apply pathspec patterns → filter files_paths
       │
       ├─ ThreadPoolExecutor(max_workers=threads)
       │    executor.map(_compress_file_task, files_paths)   ← parallel
       │      each task:
       │        read full file via FileHandler
       │        if algo is None: compress_auto(data)  → (algo_id, compressed)
       │        else:            compress_with_algo(data, algo)
       │    → results list in original file order
       │
       ├─ PMFileWriter(output_path).__enter__()     ← sequential write
       │    write HEADER placeholder (16 bytes)
       │    for each (fp, orig_size, is_binary, algo_id, compressed) in results:
       │      write FILE SECTION header (18 bytes: orig, compr, is_bin, algo)
       │      write compressed payload
       │    PMFileWriter.finalize()
       │      write INDEX TABLE
       │      seek(4); patch file_count + index_offset into HEADER
       │
       └─ if password is not None:
            read full .pm back into memory
            encrypt_archive(plain, password) → PME\x01 envelope
            overwrite output file with ciphertext
```

### decompress

```
api.decompress(pm_file_path, output_dir, threads, password)
  └─ Pmole.decompress(file_path=…, output_dir=…, threads=…, password=…)
       └─ _open_pm(file_path, password)    ← decrypt to temp if encrypted
            with open(effective_path, "rb") as f:
              _read_index(f)    → list[dict] entries
            ThreadPoolExecutor(max_workers=threads)   ← parallel
              executor.map(_decompress_file_task, entries)
                each task (independent fd per thread):
                  f.seek(data_offset + 18)
                  payload = f.read(compressed_size)
                  data = decompress_with_algo(payload, algo)
                  FileHandler(out_path).write_binary(data)
```

### list

```
api.list_files(pm_file_path, password)
  └─ Pmole.list_files(pm_file_path, password)
       └─ _open_pm(pm_file_path, password)
            with open(effective_path, "rb") as f:
              _read_index(f)    reads HEADER + INDEX TABLE only
                seek(index_offset) jumps past all FILE SECTIONs in one seek
  map dicts → list[ArchiveEntry]
```

Cost is proportional to the number of files, not archive size.

### extract (single file)

```
api.extract(pm_file_path, target, output_dir, password)
  └─ Pmole.extract(pm_file_path, target_path, output_dir, password)
       └─ _open_pm(pm_file_path, password)
            _read_index(f) → find entry by path → raise FileNotFoundError if missing
            _decompress_file_task(effective_path, entry, output_dir)
              f.seek(data_offset + 18)
              payload = f.read(compressed_size)
              data = decompress_with_algo(payload, algo)
              FileHandler(out_path).write_binary(data)
```

Cost is proportional to a single file, not the whole archive.

### verify

```
api.verify(pm_file_path, threads, password)
  └─ Pmole.verify(pm_file_path, threads, password)
       └─ _open_pm(pm_file_path, password)
            _read_index(f) → list[dict] entries
            ThreadPoolExecutor(max_workers=threads)   ← parallel
              executor.map(_verify_file_task, entries)
                each task (independent fd per thread):
                  f.seek(data_offset + 18)
                  payload = f.read(compressed_size)
                  data = decompress_with_algo(payload, algo)
                  if len(data) != original_size → {ok: False, error: "Size mismatch"}
                  else                          → {ok: True, error: None}
  returns list[{path, ok, error}]
```

Nothing is written to disk. The check is purely in-memory.

### search

```
api.search(pm_file_path, pattern, threads, password)
  └─ Pmole.search(pm_file_path, pattern, threads, password)
       └─ _open_pm(pm_file_path, password)
            _read_index(f) → list[dict] entries
            ThreadPoolExecutor(max_workers=threads)   ← parallel
              executor.map(_search_file_task, entries)
                each task:
                  if entry["is_binary"]: return []   # skip binary files
                  decompress payload
                  decode as UTF-8 (errors="replace")
                  for each line: re.search(pattern, line)
                  return [{path, line_no, line}, …]
  flatten per-file lists → sorted by file order
```

Nothing is written to disk. Binary files are skipped automatically.

### stats

```
api.stats(pm_file_path, password)
  └─ list_files(pm_file_path, password)     index only — no data read
     group entries by Path(e.path).suffix.lower()
     return {total_files, total_original, total_compressed, by_extension: {…}}
```

---

## Auto-exclusion System

Five independent layers are applied before any file is read or compressed. The first four are hardcoded defaults in `globals.py`; the fifth reads a project-specific ignore file.

### Layer 1 — filename (`EXCLUDE_FILENAMES`)

Exact match on `file_path.name.lower()`. OS artifacts, secret files, `.pmignore` itself.

### Layer 2 — file extension (`EXCLUDE_EXTENSIONS`)

`file_path.suffix.lower().lstrip(".")` checked against the set. Compiled artifacts, already-compressed formats (zip, png, mp4…), bytecode, lock files, logs.

### Layer 3 — directory name (`EXCLUDE_DIRECTORIES`)

Every path component between the root and the file is checked case-insensitively. Catches nested occurrences anywhere in the tree. VCS dirs, IDE configs, virtual environments, build outputs, caches.

### Layer 4 — file size (`MAX_FILE_SIZE_BYTES`, default 50 MB)

`os.path.getsize()` after the three name-based filters. Files over the limit are skipped with an info log.

### Layer 5 — `.pmignore` / `.gitignore` patterns

After the four built-in filters produce the candidate file list, `_load_ignore_spec(directory)` looks for `.pmignore` first, then `.gitignore`, in the root of the directory being compressed. If found, it is parsed with `pathspec` using gitignore semantics (`**`, negation `!`, directory anchoring `/`). Files whose relative path matches are removed from the list.

`.pmignore` is always excluded from archives (covered by layer 1) so it does not archive itself.

### Execution order

```
for each file found by rglob("*"):
    1. filename in EXCLUDE_FILENAMES?         → skip
    2. extension in EXCLUDE_EXTENSIONS?       → skip
    3. any parent dir in EXCLUDE_DIRECTORIES? → skip
    4. file size > MAX_FILE_SIZE_BYTES?       → skip
    → candidate list

5. pathspec.match_file(relative_path)?        → remove from list
→ final list passed to compression workers
```

Checks 1–3 are pure string comparisons; check 4 performs a single `stat` call; check 5 is applied once to the entire list after filtering.

---

## Public API (`pmole/api.py`)

```python
# Core operations
compress(
    path,
    output=None,
    algo=None,           # int | "lzw" | "lzw+zlib" | "zlib" | "lzma" | "auto"
    threads=3,
    password=None,       # AES-256-GCM encryption
    exclude_extensions=None,
    exclude_directories=None,
    exclude_filenames=None,
    max_file_size_bytes=None,
) -> str

decompress(pm_file_path, output_dir=".", threads=3, password=None) -> list[str]
list_files(pm_file_path, password=None) -> list[ArchiveEntry]
extract(pm_file_path, target, output_dir=".", password=None) -> str

# Codebase tools
verify(pm_file_path, threads=3, password=None) -> list[dict]   # {path, ok, error}
search(pm_file_path, pattern, threads=3, password=None) -> list[dict]  # {path, line_no, line}
stats(pm_file_path, password=None) -> dict  # {total_files, total_original, total_compressed, by_extension}
is_encrypted(pm_file_path) -> bool

# Raw algorithm access
lzw_compress(data: bytes) -> list[int]
lzw_decompress(codes: list[int]) -> bytes
```

`ArchiveEntry` fields: `path`, `original_size`, `compressed_size`, `is_binary`, `algo`, `data_offset`, `compression_ratio` (property), `algo_name` (property).

`_resolve_algo()` converts string names (`"zlib"`, `"lzma"`, `"auto"`, …) to integer IDs. `"auto"` and `None` both resolve to `None`, which signals `Pmole` to call `compress_auto` per file.

---

## CLI (`pmole/cli.py`)

All primary inputs are positional arguments. Optional flags use short (`-x`) and long (`--xxx`) forms. The `PMOLE_PASSWORD` environment variable is accepted by all commands that take `-p/--password`.

```
pmole compress   PATH   [-o OUTPUT] [-a ALGO] [-t THREADS] [-p PASSWORD]
                        [--exclude-ext E] [--exclude-dir D] [--exclude-name N]

pmole decompress ARCHIVE  [OUTPUT_DIR]  [-t THREADS]  [-p PASSWORD]

pmole list       ARCHIVE  [-p PASSWORD]

pmole extract    ARCHIVE  TARGET  [OUTPUT_DIR]  [-p PASSWORD]

pmole verify     ARCHIVE  [-t THREADS]  [-p PASSWORD]

pmole search     ARCHIVE  PATTERN  [-t THREADS]  [-p PASSWORD]

pmole stats      ARCHIVE  [-p PASSWORD]

pmole tree       ARCHIVE  [-p PASSWORD]

pmole diff       FILE1  FILE2
```

| Command      | Positional args                   | Key options                                          | Delegates to          |
|--------------|-----------------------------------|------------------------------------------------------|-----------------------|
| `compress`   | `PATH`                            | `-o` `-a` `-t` `-p` `--exclude-*`                   | `api.compress()`      |
| `decompress` | `ARCHIVE` `[OUTPUT_DIR]`          | `-t` `-p`                                            | `api.decompress()`    |
| `list`       | `ARCHIVE`                         | `-p`                                                 | `api.list_files()`    |
| `extract`    | `ARCHIVE` `TARGET` `[OUTPUT_DIR]` | `-p`                                                 | `api.extract()`       |
| `verify`     | `ARCHIVE`                         | `-t` `-p`                                            | `api.verify()`        |
| `search`     | `ARCHIVE` `PATTERN`               | `-t` `-p`                                            | `api.search()`        |
| `stats`      | `ARCHIVE`                         | `-p`                                                 | `api.stats()`         |
| `tree`       | `ARCHIVE`                         | `-p`                                                 | `api.list_files()`    |
| `diff`       | `FILE1` `FILE2`                   | —                                                    | `utils.show_diff()`   |

`PATH` for `compress` is auto-detected as file or directory. `OUTPUT_DIR` defaults to `.`. `--threads` defaults to `3`. `setup_cli_dir()` creates `CACHE_DIR` on startup.

---

## Key Design Decisions

**Binary format, not text.** The original format stored LZW codes as space-separated ASCII integers (`65537` = 7 bytes). The binary format packs each code as `uint16` (2 bytes), more than halving the on-disk footprint.

**Index at end, not beginning.** Compressed sizes are unknown until compression is done. Appending the index after all file sections and back-patching the header pointer avoids a two-pass write or full in-memory buffering.

**`algo` byte in both FILE SECTION and INDEX.** Storing the algorithm in the index entry means `list_files`, `verify`, and `search` never need to seek into data sections — all metadata needed for any operation is available after reading the 16-byte header and the index table.

**`compress_auto` benchmarks all candidates per file.** Different file types compress differently. Source code benefits most from `zlib`; highly repetitive small files may compress better with `lzw`; large text files often prefer `lzma`. Letting each file pick its own winner produces smaller archives than forcing one algorithm across the board.

**LZW-based algorithms skip files > 10 MB.** Pure-Python LZW is O(n) but has high constant overhead. Above 10 MB, `zlib` and `lzma` (C extensions) are both faster and produce smaller output, so LZW candidates are dropped from `compress_auto`'s list.

**Chunked LZW packing.** `_lzw_to_bytes` drives `LZWCompressor` in 64 KB slices and packs each batch's codes to bytes immediately. This avoids materialising millions of Python `int` objects simultaneously (5 M ints ≈ 140 MB vs. 10 MB of packed bytes).

**`RESET_CODE = 256` keeps all codes in `uint16`.** Without resets, a long stream of unique byte sequences would exhaust the 65536-code space and require wider codes. Resetting when `next_code` reaches 65536 guarantees every emitted value fits in two bytes.

**`bytes` keys, not `str` keys.** Using `bytes([b])` as the LZW alphabet means every byte value 0–255 is treated identically — no UTF-8 decode layer, no `UnicodeDecodeError` on binary files.

**Parallel compression and decompression via `ThreadPoolExecutor`.** zlib and lzma are C extensions that release the GIL, so multiple threads achieve real concurrency on a multicore machine. The default thread count is 3, balancing throughput against memory pressure (each thread holds one file's compressed bytes simultaneously).

**Module-level task functions, not lambdas.** `_compress_file_task`, `_decompress_file_task`, `_verify_file_task`, and `_search_file_task` are plain module-level functions. `ThreadPoolExecutor` can submit them from any context without closure/pickling issues.

**`executor.map()` for order-preserving results.** Using `executor.map(task, files)` rather than `submit()` + `as_completed()` means results are yielded in input order. This makes the archive layout deterministic — the same input always produces the same file order.

**Independent file descriptors per worker thread.** Each task function opens the archive independently with its own `open()` call and `seek()` to the right offset. No locking is needed because threads only read.

**Encrypt-after-write, not encrypt-on-the-fly.** AES-GCM requires authenticating the entire plaintext to produce a valid tag. Writing the `.pm` first and then reading it back for encryption is cleaner than trying to encrypt while streaming — the extra memory cost is the compressed archive size, which for source code is typically a few MB.

**`_open_pm` context manager for transparent decryption.** All read operations call `_open_pm(path, password)` which either yields the original path (unencrypted) or decrypts to a temp file and yields that path. This keeps each operation's logic identical whether the archive is encrypted or not, and the temp file is deleted when the context exits — after all threads have finished.

**`verify` and `search` are in-memory, disk-free operations.** Decompressing into RAM and checking sizes (verify) or scanning text (search) without writing to disk means these operations are safe to run against an archive at any time, with no cleanup needed and no risk of overwriting existing files.

**`.pmignore` / `.gitignore` as a fifth filter layer.** The four built-in exclusion filters cover common artifacts universally. Project-specific exclusions (generated files, local scripts, data exports) are better expressed in a version-controlled ignore file. Reading `.pmignore` first (then falling back to `.gitignore`) lets the archive respect the same exclusions as the version control system without duplicating configuration. `pathspec` is used for correct gitignore semantics including `**`, negation, and anchoring.

**Four exclusion filters, applied cheapest-first.** Filename and extension checks are pure dict lookups; directory and size checks follow. The `stat` call for size is only made after all name-based filters pass, minimising syscalls on large trees.
