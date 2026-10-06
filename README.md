![Health](https://oss-health-monitor.vercel.app/api/badge/pekempy/bootlegorganiser)
# Bootleg Organiser

Bootleg Organiser is a Python tool designed to keep your local bootleg collection structured, synchronised, and consistently named based on data from Encora.

By simply dropping a folder named with an Encora ID (e.g., `{e-12345}`) into your directory, the script will automatically fetch metadata, rename the folder, move it to the correct path, and update your Encora format details.

---

## Running the Organiser

### Graphical Mode (Default)
Run the script without any arguments to launch the **Tabbed Configuration GUI**:
```bash
python3 full-organise.py
```
The GUI allows you to live-preview your naming patterns, browse directories, and manage all settings visually.

### Headless Mode (--auto)
Run the script with the `--auto` flag to skip the GUI and run immediately using your saved settings:
```bash
python3 full-organise.py --auto
```
*This is ideal for scheduled tasks, batch jobs, or headless server environments.*

### Verifying Checksums (--verify-checksums)
Run with `--verify-checksums` to re-hash every file covered by a `Checksums.b2` manifest and report any mismatches, then exit (no GUI, no Encora fetch):
```bash
python3 full-organise.py --verify-checksums
```
*This fully re-reads every checksummed file, so it's slower than a normal run -- use it as an occasional integrity check, e.g. after a drive move or on a schedule separate from `--auto`.*

---

## Configuration

The organiser is highly customisable via the GUI (saved to `.env`).

### 1. API & Options
*   **Encora API Key**: required to fetch your collection and metadata.
*   **Generate Cast Files**: Replaces/Creates `Cast.txt` in every folder with the latest cast list from Encora.
*   **Generate ID Files**: Creates `.encora-id` files for compatibility with metadata agents (like Plex).
*   **Always Redownload Subtitles**: Forces a refresh of all local subtitles from the Encora database.
*   **Generate Checksums**: Creates/updates a `Checksums.b2` manifest in every recording folder (see [Checksums](#checksums) below).

### 2. Directory Settings
*   **Main Directory**: The root folder where your collection lives.
*   **Folder Pattern**: The naming scheme for individual recording folders.
*   **Structure Pattern**: The folder hierarchy (e.g., `Show/Tour/Media Type/`).
*   **Final Output Path**: A live preview showing the exact absolute path where your files will end up.
*   **Tag Buttons**: Click to insert variables like `{show_name}`, `{date}`, `{master}`, `{type}` (Video/Audio), or `{short_type}` (V/A).
*   **The `{folder}` Tag**: In the Structure Pattern, use `{folder}` to specify exactly where the recording folder sits in your hierarchy.

### 3. Advanced Rules
*   **Date Unknown Placeholder**: Choose the character (e.g., `x` or `0`) used when a month or day is unknown (results in `2024-xx-xx`).
*   **Containers**: Wrap specific tags in `[]`, `()`, or `{}` automatically.
*   **Exclusion Rules**: Skip specific Encora IDs or disable certain updates for sensitive folders.

---

## Smart Features

- **Space Guard**: The organiser automatically prevents multiple consecutive spaces in names, keeping your file system tidy even if a tag is empty.
- **ID Detection**: It detects Encora IDs regardless of your naming style (supports `{e-123}`, `[e-123]`, `(e-123)`, or raw `e-123`).
- **Flexible Sorting**: Supports removing sorting articles (The/A/An) for folder structures.
- **Processing Safety**: Folders are moved to a `!processing` queue during organisation to prevent data loss in case of hardware failure or crashes.
- **Checksums**: See [Checksums](#checksums) below.


## Checksums

When **Generate Checksums** is enabled, every recording folder gets a `Checksums.b2` manifest listing a BLAKE2b-512 digest for each file it contains, relative to that folder -- so a single-file video, a folder of tracked audio, or a VOB rip's `VIDEO_TS`/`AUDIO_TS` structure are all covered by one manifest per recording, walked recursively.

> [!WARNING]
> **The first run hashes your entire un-checksummed library once** -- this reads every byte of every file. On spinning disks, expect roughly **5 hours per TB** (much faster on SSD). A large multi-TB library can take a day or more the first time. This is unavoidable -- checksums can't be computed without reading the data -- but it's a one-time cost: incremental generation (below) means every run after that is fast.

BLAKE2b is used because it's built into Python (`hashlib`, no extra dependency), it's faster than SHA-256 on 64-bit CPUs, and it produces the exact same digest as GNU `b2sum` -- so any manifest can also be checked by hand, without this tool, via:
```bash
b2sum -c "Checksums.b2"
```

**Generation is incremental**: each folder gets a hidden `.checksums.cache` recording every file's size + mtime alongside its hash. If a file's size/mtime still match the cache, its hash is trusted and not re-read; if either changed -- including a re-graded/re-encoded file dropped in under the *same* filename, e.g. an Encora format upgrade -- it's re-hashed automatically on the next run. New files are always hashed; files that no longer exist are dropped from the manifest. `.checksums.cache` is internal bookkeeping (excluded from the GDrive upload via `rclone-exclusions.txt`) -- the portable, human/`b2sum`-checkable file is always just `Checksums.b2`.

This stat-based check is fast but not foolproof: a file replaced in-place with different content at the *exact* same size and mtime (vanishingly rare outside deliberate tampering) won't be caught until you run [`--verify-checksums`](#verifying-checksums---verify-checksums), which fully re-hashes and compares every file regardless of the cache.

Use **Skip Checksums** (Exclusion Rules tab) together with **Excluded IDs** to leave specific recordings out of checksum generation.

## Installation

1.  Clone the repository.
2.  Install requirements: `pip install -r requirements.txt`.
3.  Launch with `python3 full-organise.py`.

> [!IMPORTANT]  
> New folders should ideally contain the Encora ID in the name (like `{e-12345}`) for the first run.
> For non-Encora folders you wish to skip, include `{ne}` in the name.
