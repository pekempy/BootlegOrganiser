import argparse
import io
import logging
import os
import re
import sys
from contextlib import redirect_stderr, redirect_stdout

from modules.cast_utils import create_cast_files, create_encora_id_files
from modules.cleanup_utils import delete_empty_directories
from modules.collection_utils import compare_local_encora_ids
from modules.config import config
from modules.content_utils import organise_all_releases
from modules.diff_utils import clear_diff_files, log_missing_smalls
from modules.encora_utils import fetch_collection, find_local_encora_ids, process_encora_ids
from modules.folder_utils import move_and_rename_folders
from modules.format_utils import process_directory, send_format
from modules.logging_utils import run_logging
from modules.non_encora_utils import move_folders_with_ne
from modules.safety_utils import get_quarantined_items, reset_quarantine_log
from modules.subtitle_utils import download_subtitles_for_folders
from modules.unmatched_utils import move_unmatched_items

try:
    from modules.checksum_utils import create_checksum_files, verify_all_checksums
except ImportError:
    def create_checksum_files(*a, **kw):
        pass

    def verify_all_checksums(*a, **kw):
        return 0, 0

# ── Terminal helpers ──────────────────────────────────────────────────────────
if sys.platform == "win32":
    os.system("")

_G = "\033[38;5;48m\033[1m"
_R = "\033[38;5;196m\033[1m"
_DM = "\033[38;5;245m"
_SH = "\033[38;5;255m\033[1m"
_RS = "\033[0m"
_CL = "\r\033[2K"

_logger = logging.getLogger("modules.encora_utils")


_BOX = {"first": "╔", "middle": "╠", "last": "╚"}


def _spin(msg: str, pos: str = "middle") -> None:
    edge = _BOX.get(pos, "╠")
    print(f"  {_DM}{edge} ·  {msg}…{_RS}", end="\r", flush=True)


def _done(label: str, summary: str, details: list | None = None, warn: bool = False, pos: str = "middle") -> None:
    edge = _BOX.get(pos, "╠")
    icon = f"{_R}✕{_RS}" if warn else f"{_G}✓{_RS}"
    print(f"{_CL}  {_DM}{edge}{_RS} {icon}  {_SH}{label:<18}{_RS}  {summary}")
    if details:
        for d in details:
            print(f"  {_DM}║      {d}{_RS}")

def _quiet(fn, *args, **kwargs):
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        return fn(*args, **kwargs)


def _capture(fn, *args, **kwargs):
    buf = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(buf):
        result = fn(*args, **kwargs)
    return result, buf.getvalue()


# ── Safe-mode confirmation ─────────────────────────────────────────────────────
def _write_tty(msg: str) -> None:
    try:
        with open('/dev/tty', 'w') as tty:
            tty.write(msg)
            tty.flush()
    except OSError:
        sys.stderr.write(msg)
        sys.stderr.flush()


def _read_tty() -> str:
    try:
        with open('/dev/tty') as tty:
            return tty.readline().strip().lower()
    except OSError:
        return input().strip().lower()


class _SafeConfirm:
    """Interactive confirmation gate for destructive operations when --safe is active."""

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


def _run_resilient(label: str, fn, *args, default=None, **kwargs):
    """Run an organiser step without crashing the entire pipeline on unexpected errors."""
    try:
        return fn(*args, **kwargs)
    except SystemExit:
        raise
    except Exception as exc:
        _logger.error(f"Step '{label}' failed: {exc}", exc_info=True)
        _done(label, f"error: {exc}", warn=True)
        return default


# ── Organiser ─────────────────────────────────────────────────────────────────
def run_organiser(interactive: bool = True, safe: bool = False) -> None:
    confirm = _SafeConfirm() if safe else None

    main_directory = config.main_directory
    if not main_directory or not os.path.isdir(main_directory):
        print(f"{_R}Error:{_RS} BOOTLEG_MAIN_DIRECTORY is not set or does not exist: {main_directory}")
        return

    os.environ["TQDM_DISABLE"] = "1"

    with run_logging("organiser-debug.log"):
        reset_quarantine_log()
        _quiet(clear_diff_files)
        # ── Non-Encora folders ────────────────────────────────────────────────
        _spin("Checking non-Encora folders", pos="first")
        non_encora_folder = os.path.join(main_directory, '!non-encora')
        _, txt = _run_resilient(
            "Non-Encora",
            _capture,
            move_folders_with_ne,
            main_directory,
            non_encora_folder,
            default=(None, ""),
        )
        n_moved = len([l for l in txt.splitlines() if "Moved" in l])
        _done("Non-Encora", f"{n_moved} folder{'s' if n_moved != 1 else ''} moved" if n_moved else "none", pos="first")

        # ── Fetch collection ──────────────────────────────────────────────────
        _spin("Fetching collection from Encora")
        local_ids = _quiet(find_local_encora_ids, main_directory)
        encora_data = _quiet(fetch_collection)
        fetch_complete = getattr(fetch_collection, "last_complete", None)
        if not isinstance(fetch_complete, bool):
            fetch_complete = bool(encora_data)
        recording_data = _quiet(process_encora_ids, encora_data, local_ids)
        _done("Encora Sync", f"{len(recording_data)} matched")

        # ── Cast files ────────────────────────────────────────────────────────
        if config.generate_cast_files:
            _spin("Updating Cast.txt files")
            res = _run_resilient("Cast Files", _capture, create_cast_files, recording_data)
            if res is not None:
                _, txt = res
                m = re.search(r"Updated Cast\.txt for (\d+)", txt)
                _done("Cast Files", f"{m.group(1)} updated" if m else "up to date")

        # ── Encora ID files ───────────────────────────────────────────────────
        if config.generate_encoraid_files:
            _spin("Creating .encora-id files")
            if _run_resilient("Encora IDs", _quiet, create_encora_id_files, recording_data) is not None or True:
                _done("Encora IDs", f"{len(recording_data)} checked")

        # ── Move & rename ─────────────────────────────────────────────────────
        _spin("Moving & renaming folders")
        _run_resilient("Folders", _quiet, move_and_rename_folders, recording_data, main_directory, confirm=confirm)
        _done("Folders", "renamed & moved")

        # Clean empty directories before unmatched scan so empty folders aren't flagged
        _run_resilient("Cleanup", _quiet, delete_empty_directories, main_directory, confirm=confirm)

        # ── Unmatched local files/folders ─────────────────────────────────────
        if fetch_complete or not local_ids:
            _spin("Checking unmatched items")
            unmatched_folder = os.path.join(main_directory, '!unmatched')
            matched_id_set = {str(x['encora_id']) for x in recording_data}
            updated_matched = [
                {'encora_id': eid, 'path': p}
                for eid, p in _quiet(find_local_encora_ids, main_directory)
                if str(eid) in matched_id_set
            ]
            moved_unmatched = _run_resilient(
                "Unmatched",
                _quiet,
                move_unmatched_items,
                main_directory,
                unmatched_folder,
                updated_matched,
                confirm=confirm,
                default=[],
            )
            n_unmatched = len(moved_unmatched) if moved_unmatched else 0
            if n_unmatched:
                _done("Unmatched", f"{n_unmatched} moved to !unmatched")
            else:
                print(_CL, end="", flush=True)
        else:
            _done("Unmatched", "skipped (Encora collection unavailable)", warn=True)

        # ── Organise content ──────────────────────────────────────────────────
        if config.organise_content:
            _spin("Organising files inside releases")
            updated_local_ids = _quiet(find_local_encora_ids, main_directory)
            _run_resilient(
                "Release Files",
                _quiet,
                organise_all_releases,
                updated_local_ids,
                interactive=False,
                confirm=confirm,
            )
            _done("Release Files", f"{len(updated_local_ids)} recordings organised")

        _run_resilient("Cleanup", _quiet, delete_empty_directories, main_directory, confirm=confirm)

        quarantined = get_quarantined_items()
        n_danger = len(quarantined)
        if n_danger:
            _done(
                "Danger Zone",
                f"{n_danger} moved to !danger-zone",
                details=[os.path.basename(p) for p in quarantined],
                warn=True,
            )

        # ── File sizes & formats ──────────────────────────────────────────────
        _spin("Checking formats")
        final_local_ids = _quiet(find_local_encora_ids, main_directory)
        updated_formats_count = 0
        for encora_id, folder_path in final_local_ids:
            if config.exclude_format_update and str(encora_id) in config.excluded_ids:
                continue
            try:
                summary = process_directory(folder_path)
            except OSError as exc:
                _logger.warning(f"Format evaluation failed for {folder_path}: {exc}")
                continue
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
        _done("Formats", f"{updated_formats_count} updated" if updated_formats_count else "up to date")

        # ── Checksum manifests ────────────────────────────────────────────────
        if config.generate_checksums:
            _spin("Updating checksum manifests")
            final_local_ids2 = _quiet(find_local_encora_ids, main_directory)
            final_recording_data = _quiet(process_encora_ids, encora_data, final_local_ids2)
            res = _run_resilient("Checksums", _capture, create_checksum_files, final_recording_data)
            if res is not None:
                _, txt = res
                m = re.search(r"Updated checksum manifests for (\d+)", txt)
                _done("Checksums", f"{m.group(1)} updated" if m else "up to date")

        # ── Subtitles ─────────────────────────────────────────────────────────
        if config.redownload_subtitles:
            _spin("Checking subtitles")
            result = _run_resilient(
                "Subtitles",
                _quiet,
                download_subtitles_for_folders,
                main_directory,
                recording_data,
                default=(0, []),
            )
            n_dl, dl_folders = result if result else (0, [])
            if n_dl:
                _done("Subtitles", f"{n_dl} downloaded", details=dl_folders)
            else:
                _done("Subtitles", "up to date")

        # ── Library check ─────────────────────────────────────────────────────
        _spin("Comparing local vs Encora", pos="last")
        missing_ids, extra_ids = _quiet(compare_local_encora_ids, local_ids, encora_data)
        n_miss = len(missing_ids) if missing_ids else 0
        n_extra = len(extra_ids) if extra_ids else 0
        if n_miss or n_extra:
            parts = []
            if n_miss:
                parts.append(f"{n_miss} missing locally")
            if n_extra:
                parts.append(f"{n_extra} not on Encora")
            _done("Library Check", "  ·  ".join(parts), warn=bool(n_miss), pos="last")
            if missing_ids:
                with open('on_encora_not_local.txt', 'w', encoding='utf-8') as f:
                    f.write('Missing IDs locally:\n')
                    for eid in missing_ids:
                        f.write(f"{eid}\n")
        else:
            _done("Library Check", "in sync", pos="last")
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bootleg Organiser")
    parser.add_argument("--auto", action="store_true", help="Run without GUI")
    parser.add_argument("--safe", action="store_true", help="Pause and confirm before every move or delete")
    parser.add_argument("--verify-checksums", action="store_true", help="Re-hash and verify all stored checksum manifests, then exit")
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
