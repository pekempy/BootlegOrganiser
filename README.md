![Health](https://oss-health-monitor.vercel.app/api/badge/pekempy/bootlegorganiser)
# Bootleg Organiser

Organises, renames, and syncs a local bootleg library against your Encora collection.

Drop a folder with an Encora ID in its name (like `{e-12345}`) into your library directory and run the script. It fetches metadata from Encora, moves/renames the folder to match your template, and optionally generates `Cast.txt`, `.encora-id` files, subtitles, checksums, and Encora format updates.

For non-Encora folders you want to keep separate, put `{ne}` in the folder name.

## Quick Start

```bash
pip install -r requirements.txt
python3 full-organise.py
```

## Usage

- **GUI (default):** `python3 full-organise.py`
- **Headless:** `python3 full-organise.py --auto`
- **Safe mode (prompt before every move/delete):** `python3 full-organise.py --auto --safe`
- **Verify checksums:** `python3 full-organise.py --verify-checksums`

<details>
<summary>Configuration &amp; Naming Patterns</summary>

Settings are managed through the GUI and saved to `.env`.

- **API &amp; Options:** Encora API key, `Cast.txt` generation, `.encora-id` marker files, subtitle downloads, checksums, and internal content organisation.
- **Directory Settings:** Main library path, folder naming pattern, and directory hierarchy (`Show/Tour/Media Type/{folder}` etc.) with live preview in the GUI.
- **Tags:** `{show_name}`, `{tour}`, `{date}`, `{master}`, `{highlights}`, `{matinee}`, `{nft}`, `{encora_id}`, `{type}`, `{short_type}`, `{folder}`.
- **Rules &amp; Exclusions:** Unknown-date placeholder character (`x` or `0`), tag brackets (`[]`, `()`, `{}`), and per-ID exclusions for formats, cast files, or checksums.

</details>

<details>
<summary>Safety &amp; Special Folders</summary>

- **`!non-encora`:** Folders containing `{ne}` are moved here and left alone.
- **`!unmatched`:** Local folders/files that don't match an Encora recording (or have no Encora ID) are moved here instead of sitting loose. Skipped automatically if the Encora collection fetch fails or is incomplete.
- **`!danger-zone`:** Any folder or file larger than 10 MB targeted for deletion is quarantined here instead of being deleted, alongside a `DANGER_ZONE_REASON.txt` explaining why it was at risk.
- **Case / Unicode safety:** Folder moves check physical file identity (`samefile` / inodes) so case-only or NFD/NFC path differences on macOS/Windows don't overwrite or delete files.

</details>

<details>
<summary>Checksums (BLAKE2b)</summary>

When **Generate Checksums** is enabled, each recording folder gets a `Checksums.b2` manifest listing a BLAKE2b-512 hash per file (compatible with `b2sum -c "Checksums.b2"`).

- **First run:** Hashes every un-checksummed file once (roughly ~5 hrs/TB on spinning disks, much faster on SSD).
- **Incremental updates:** `.checksums.cache` stores each file's size, mtime, and hash so unchanged files aren't re-read on future runs.
- **Full verification:** Run `python3 full-organise.py --verify-checksums` to re-hash and check every file regardless of the cache.

</details>

<details>
<summary>Running Tests</summary>

```bash
python3 -m unittest discover -s tests -v
```

</details>
