import os
import sys
import io
import re
import argparse
from contextlib import redirect_stdout, redirect_stderr
import logging


from modules.config import config
from modules.cleanup_processing import clean_processing_folder, delete_empty_directories
from modules.collection_checker import compare_local_encora_ids
from modules.download_subtitles import download_subtitles_for_folders
from modules.non_encora_processing import move_folders_with_ne
from modules.encora_id_processing import fetch_collection, find_local_encora_ids, process_encora_ids
from modules.cast_file_generator import create_cast_files, create_encora_id_files
try:
    from modules.checksum_generator import create_checksum_files, verify_all_checksums
    _CHECKSUM_AVAILABLE = True
except ImportError:
    _CHECKSUM_AVAILABLE = False
    def create_checksum_files(*a, **kw): pass
    def verify_all_checksums(*a, **kw): return 0, 0
from modules.move_and_rename_folders import move_folders_to_processing, move_and_rename_folders
from modules.manage_file_sizes import process_directory, send_format
from modules.diff_utils import clear_diff_files, log_missing_smalls
from modules.content_organiser import organise_all_releases

# ── Terminal helpers ──────────────────────────────────────────────────────────
# Windows 10+ supports ANSI natively; this enables VT processing on older builds
if sys.platform == "win32":
    os.system("")

_G  = "\033[38;5;48m\033[1m"   # green
_R  = "\033[38;5;196m\033[1m"  # red
_DM = "\033[38;5;245m"         # dim grey
_SH = "\033[38;5;255m\033[1m"  # white bold
_RS = "\033[0m"
_CL = "\r\033[2K"              # clear current line


def _spin(msg: str) -> None:
    """Print a transient 'running' indicator that _done() will overwrite."""
    print(f"  {_DM}·  {msg}…{_RS}", end="\r", flush=True)


def _done(label: str, summary: str, details: list = None, warn: bool = False) -> None:
    """Overwrite the spinner line with a compact completion summary."""
    icon = f"{_R}✕{_RS}" if warn else f"{_G}✓{_RS}"
    print(f"{_CL}  {icon}  {_SH}{label:<18}{_RS}  {summary}")
    if details:
        for d in details:
            print(f"       {_DM}{d}{_RS}")


def _quiet(fn, *args, **kwargs):
    """Run fn, suppressing all stdout/stderr. Returns the result."""
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        return fn(*args, **kwargs)


def _capture(fn, *args, **kwargs):
    """Run fn silently. Returns (result, captured_text)."""
    buf = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(buf):
        result = fn(*args, **kwargs)
    return result, buf.getvalue()

# ── Safe-mode confirmation ─────────────────────────────────────────────────────
def _write_tty(msg: str) -> None:
    """Write directly to the controlling terminal, bypassing _quiet() redirects."""
    try:
        with open('/dev/tty', 'w') as tty:
            tty.write(msg)
            tty.flush()
    except OSError:
        sys.stderr.write(msg)
        sys.stderr.flush()


def _read_tty() -> str:
    """Read one line from the controlling terminal."""
    try:
        with open('/dev/tty') as tty:
            return tty.readline().strip().lower()
    except OSError:
        return input().strip().lower()


class _SafeConfirm:
    """
    Callable passed to destructive operations when --safe is active.
    Writes the pending action to /dev/tty and waits for y/n/a/q.
    Tracks an approve-all flag so the user can say 'a' once and move on.
    Every decision (approved / skipped) is also written to organiser-debug.log.
    """
    _log = logging.getLogger("organiser.safe")

    def __init__(self):
        self._all = False

    def __call__(self, action: str) -> bool:
        if self._all:
            self._log.info(f"AUTO-APPROVED (all): {action}")
            return True
        _write_tty(
            f"\n  {_SH}⚠  SAFE MODE{_RS} — pending action:\n"
            f"  {action}\n"
            f"  {_DM}[y] proceed  [n] skip  [a] approve all remaining  [q] quit{_RS}: "
        )
        choice = _read_tty()
        if choice == 'q':
            self._log.warning("QUIT by user")
            _write_tty("\nAborted.\n")
            sys.exit(0)
        if choice == 'a':
            self._all = True
            self._log.info(f"APPROVED (approve-all set): {action}")
            return True
        approved = choice in ('y', '')
        self._log.info(f"{'APPROVED' if approved else 'SKIPPED'}: {action}")
        return approved



# ── Organiser ─────────────────────────────────────────────────────────────────
def run_organiser(interactive: bool = True, safe: bool = False):
    confirm = _SafeConfirm() if safe else None

    main_directory = config.main_directory
    if main_directory is None:
        print(f"{_R}Error:{_RS} BOOTLEG_MAIN_DIRECTORY not set in config.")
        return

    # Disable tqdm globally — clean output comes from _done() summaries
    os.environ["TQDM_DISABLE"] = "1"

    # Logging setup:
    #   WARNING+ → stderr (visible in terminal, bypasses _quiet() redirects)
    #   DEBUG+   → organiser-debug.log (full trace for post-run diagnosis)
    # propagate=False prevents DEBUG from leaking to the root logger / terminal.
    _fmt_term = logging.Formatter("  %(levelname)s [%(name)s] %(message)s")
    _fmt_file = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")

    _warn_handler = logging.StreamHandler(sys.stderr)
    _warn_handler.setLevel(logging.WARNING)
    _warn_handler.setFormatter(_fmt_term)

    _dbg_handler = logging.FileHandler("organiser-debug.log", mode="w", encoding="utf-8")
    _dbg_handler.setLevel(logging.DEBUG)
    _dbg_handler.setFormatter(_fmt_file)

    for _mod in ("modules.content_organiser", "modules.cleanup_processing", "organiser.safe"):
        _lg = logging.getLogger(_mod)
        _lg.handlers.clear()
        _lg.addHandler(_warn_handler)
        _lg.addHandler(_dbg_handler)
        _lg.setLevel(logging.DEBUG)
        _lg.propagate = False  # keep DEBUG out of root logger / terminal

    _quiet(clear_diff_files)

    # ── Non-Encora folders ────────────────────────────────────────────────────
    _spin("Checking non-Encora folders")
    non_encora_folder = os.path.join(main_directory, '!non-encora')
    _, txt = _capture(move_folders_with_ne, main_directory, non_encora_folder)
    n_moved = len([l for l in txt.splitlines() if "Moved" in l])
    _done("Non-Encora", f"{n_moved} folder{'s' if n_moved != 1 else ''} moved" if n_moved else "none to process")

    # ── Fetch collection ──────────────────────────────────────────────────────
    _spin("Fetching collection from Encora")
    local_ids  = _quiet(find_local_encora_ids, main_directory)
    encora_data = _quiet(fetch_collection)
    recording_data = _quiet(process_encora_ids, encora_data, local_ids)
    _done("Collection", f"{len(recording_data)} recordings matched")

    # ── Cast files ────────────────────────────────────────────────────────────
    if config.generate_cast_files:
        _spin("Generating cast files")
        _, txt = _capture(create_cast_files, recording_data)
        m = re.search(r"Updated Cast\.txt for (\d+)", txt)
        _done("Cast files", f"{m.group(1)} updated" if m else "all up to date")

    # ── Encora ID files ───────────────────────────────────────────────────────
    if config.generate_encoraid_files:
        _spin("Generating Encora ID files")
        _quiet(create_encora_id_files, recording_data)
        _done("Encora IDs", f"{len(recording_data)} up to date")

    # ── Move & rename ─────────────────────────────────────────────────────────
    _spin("Moving & renaming folders")
    _quiet(move_and_rename_folders, recording_data, main_directory, confirm=confirm)
    _done("Folders", "renamed & organised")

    # ── Organise content ──────────────────────────────────────────────────────
    if config.organise_content:
        _spin("Organising release content")
        updated_local_ids = _quiet(find_local_encora_ids, main_directory)
        _quiet(organise_all_releases, updated_local_ids, interactive=False, confirm=confirm)
        _done("Content", f"{len(updated_local_ids)} releases organised")

    _quiet(delete_empty_directories, main_directory, confirm=confirm)

    # ── File sizes & formats ──────────────────────────────────────────────────
    _spin("Checking formats")
    final_local_ids = _quiet(find_local_encora_ids, main_directory)
    updated_formats_count = 0
    for encora_id, folder_path in final_local_ids:
        if config.exclude_format_update and str(encora_id) in config.excluded_ids:
            continue
        summary = process_directory(folder_path)
        if summary:
            if "VOB (no smalls)" in summary:
                match = next((x for x in recording_data if str(x['encora_id']) == str(encora_id)), None)
                if match:
                    rd = match.get('recording_data', {})
                    log_missing_smalls(
                        encora_id,
                        rd.get('show', 'Unknown Show'),
                        rd.get('tour', 'Unknown Tour'),
                        rd.get('date', {}).get('full_date', 'Unknown Date'),
                        rd.get('master', 'Unknown Master'),
                    )
            if config.update_encora_format and send_format(recording_data, encora_id, summary):
                updated_formats_count += 1
    _done("Formats", f"{updated_formats_count} updated" if updated_formats_count else "all up to date")

    # ── Checksum manifests ────────────────────────────────────────────────────
    if config.generate_checksums:
        _spin("Generating checksum manifests")
        final_local_ids2    = _quiet(find_local_encora_ids, main_directory)
        final_recording_data = _quiet(process_encora_ids, encora_data, final_local_ids2)
        _, txt = _capture(create_checksum_files, final_recording_data)
        m = re.search(r"Updated checksum manifests for (\d+)", txt)
        _done("Checksums", f"{m.group(1)} updated" if m else "all up to date")

    # ── Subtitles ─────────────────────────────────────────────────────────────
    if config.redownload_subtitles:
        _spin("Checking subtitles")
        result = _quiet(download_subtitles_for_folders, main_directory, recording_data)
        n_dl, dl_folders = result if result else (0, [])
        if n_dl:
            _done("Subtitles", f"{n_dl} downloaded", details=dl_folders)
        else:
            _done("Subtitles", "all up to date")

    # ── Collection check ──────────────────────────────────────────────────────
    _spin("Checking collection")
    missing_ids, extra_ids = _quiet(compare_local_encora_ids, local_ids, encora_data)
    n_miss  = len(missing_ids)  if missing_ids  else 0
    n_extra = len(extra_ids)    if extra_ids    else 0
    if n_miss or n_extra:
        parts = []
        if n_miss:  parts.append(f"{n_miss} on Encora but not local")
        if n_extra: parts.append(f"{n_extra} local but not on Encora")
        _done("Collection", "  ·  ".join(parts), warn=bool(n_miss))
        if missing_ids:
            with open('on_encora_not_local.txt', 'w') as f:
                f.write('Missing IDs locally:\n')
                for eid in missing_ids:
                    f.write(f"{eid}\n")
    else:
        _done("Collection", "in sync")

    print()


# ── Entry point ───────────────────────────────────────────────────────────────
def section(title):
    """Legacy stub kept for any external callers; no-op in clean mode."""
    pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bootleg Organiser")
    parser.add_argument("--auto", action="store_true", help="Run without GUI")
    parser.add_argument("--safe", action="store_true",
                        help="Pause and confirm before every move or delete")
    parser.add_argument("--verify-checksums", action="store_true",
                        help="Re-hash and verify all stored checksum manifests, then exit")
    args = parser.parse_args()

    if args.verify_checksums:
        if config.main_directory is None:
            print("Error: BOOTLEG_MAIN_DIRECTORY not found in config.")
            sys.exit(1)
        _, failed = verify_all_checksums(config.main_directory)
        sys.exit(1 if failed else 0)

    if args.auto:
        run_organiser(interactive=False, safe=args.safe)
    else:
        try:
            from modules.gui_config import start_gui
            start_gui(run_organiser)
        except ImportError:
            print("Error: Tkinter is not installed. The GUI requires it.")
            print("  macOS:   brew install python-tk")
            print("  Ubuntu:  sudo apt install python3-tk")
            print("  Fedora:  sudo dnf install python3-tkinter")
            print("  Windows: reinstall Python from python.org and tick 'tcl/tk and IDLE'")
            print("Run with --auto to skip the GUI entirely.")
            sys.exit(1)
        except Exception as e:
            print(f"Error: Could not start GUI: {e}")
            sys.exit(1)
