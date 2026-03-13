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

---

## Configuration

The organiser is highly customisable via the GUI (saved to `.env`).

### 1. API & Options
*   **Encora API Key**: required to fetch your collection and metadata.
*   **Generate Cast Files**: Replaces/Creates `Cast.txt` in every folder with the latest cast list from Encora.
*   **Generate ID Files**: Creates `.encora-id` files for compatibility with metadata agents (like Plex).
*   **Always Redownload Subtitles**: Forces a refresh of all local subtitles from the Encora database.

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

## Installation

1.  Clone the repository.
2.  Install requirements: `pip install -r requirements.txt`.
3.  Launch with `python3 full-organise.py`.

> [!IMPORTANT]  
> New folders should ideally contain the Encora ID in the name (like `{e-12345}`) for the first run.
> For non-Encora folders you wish to skip, include `{ne}` in the name.