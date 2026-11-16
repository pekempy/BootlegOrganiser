import logging
import os
import shutil
from datetime import datetime, timezone

from modules.path_utils import is_same_path, is_within, unique_path

logger = logging.getLogger(__name__)

DANGER_ZONE_THRESHOLD_BYTES = 10 * 1024 * 1024  # 10 MiB


def get_path_size_bytes(path: str) -> int:
    """Return total bytes on disk under path (file or directory), skipping symlinks."""
    if not os.path.lexists(path) or os.path.islink(path):
        return 0
    if os.path.isfile(path):
        try:
            return os.path.getsize(path)
        except OSError:
            return 0

    total = 0
    for dirpath, _, filenames in os.walk(path):
        if os.path.islink(dirpath):
            continue
        for fn in filenames:
            fp = os.path.join(dirpath, fn)
            if not os.path.islink(fp):
                try:
                    total += os.path.getsize(fp)
                except OSError:
                    pass
    return total


def quarantine_to_danger_zone(
    target_path: str,
    main_directory: str,
    reason: str,
    confirm=None,
) -> str | None:
    """
    Move target_path into <main_directory>/!danger-zone/ and write a
    DANGER_ZONE_REASON.txt explaining why it was potentially at risk.
    """
    if not target_path or not os.path.lexists(target_path):
        return None
    if not main_directory:
        main_directory = os.path.dirname(os.path.abspath(target_path))

    danger_root = os.path.join(main_directory, '!danger-zone')
    if is_within(target_path, danger_root):
        logger.warning(f"Skipping quarantine for item already inside !danger-zone: {target_path}")
        return None

    size_bytes = get_path_size_bytes(target_path)
    size_mb = size_bytes / (1024 * 1024)
    base_name = os.path.basename(os.path.normpath(target_path)) or 'item'

    os.makedirs(danger_root, exist_ok=True)

    if os.path.isdir(target_path):
        dest_dir = unique_path(os.path.join(danger_root, base_name))
        if confirm is not None and not confirm(
            f"MOVE at-risk folder ({size_mb:.2f} MB) to !danger-zone instead of deleting:\n"
            f"    {target_path}\n    → {dest_dir}\n    Reason: {reason}"
        ):
            return None
        shutil.move(target_path, dest_dir)
    else:
        dest_dir = unique_path(os.path.join(danger_root, base_name))
        os.makedirs(dest_dir, exist_ok=True)
        dest_file = os.path.join(dest_dir, base_name)
        if confirm is not None and not confirm(
            f"MOVE at-risk file ({size_mb:.2f} MB) to !danger-zone instead of deleting:\n"
            f"    {target_path}\n    → {dest_file}\n    Reason: {reason}"
        ):
            return None
        shutil.move(target_path, dest_file)

    note_path = unique_path(os.path.join(dest_dir, 'DANGER_ZONE_REASON.txt'))
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    note_content = (
        f"Bootleg Organiser — !danger-zone Safety Quarantine\n"
        f"{'=' * 52}\n"
        f"Timestamp     : {timestamp}\n"
        f"Original path : {target_path}\n"
        f"Size on disk  : {size_mb:.2f} MB ({size_bytes} bytes)\n"
        f"Reason        : {reason}\n"
    )
    with open(note_path, 'w', encoding='utf-8') as f:
        f.write(note_content)

    logger.warning(
        f"Quarantined to !danger-zone ({size_mb:.2f} MB): {target_path} → {dest_dir} | {reason}"
    )
    print(f"Quarantined at-risk item ({size_mb:.2f} MB) to {dest_dir}")
    return dest_dir


def safe_delete_directory(
    dirpath: str,
    main_directory: str,
    reason: str = "Directory scheduled for deletion",
    confirm=None,
) -> bool:
    """
    Safely delete an empty directory, OR quarantine to !danger-zone if it is
    >10 MB on disk (refusing to delete any non-empty directory).
    """
    if not dirpath or not os.path.lexists(dirpath) or not os.path.isdir(dirpath) or os.path.islink(dirpath):
        return False

    if main_directory:
        if is_same_path(dirpath, main_directory):
            logger.warning(f"Refusing to delete main_directory itself: {dirpath}")
            return False
        if is_within(dirpath, os.path.join(main_directory, '!danger-zone')):
            return False

    size_bytes = get_path_size_bytes(dirpath)
    if size_bytes > DANGER_ZONE_THRESHOLD_BYTES:
        quarantine_to_danger_zone(
            dirpath,
            main_directory,
            reason=f"{reason} (folder exceeded 10 MB safety threshold at {size_bytes / (1024 * 1024):.2f} MB)",
            confirm=confirm,
        )
        return True

    try:
        if os.listdir(dirpath):
            logger.warning(f"safe_delete_directory: directory is not empty, skipping delete: {dirpath}")
            return False
    except OSError:
        return False

    if confirm is not None and not confirm(f"DELETE empty directory:\n    {dirpath}"):
        return False

    try:
        os.rmdir(dirpath)
        logger.debug(f"Removed empty dir {dirpath}")
        return True
    except OSError:
        return False


def safe_delete_file(
    filepath: str,
    main_directory: str,
    reason: str = "File scheduled for deletion",
    confirm=None,
) -> bool:
    """Safely delete a file <=10 MB, or quarantine to !danger-zone if >10 MB on disk."""
    if not filepath or not os.path.lexists(filepath) or os.path.isdir(filepath):
        return False

    size_bytes = get_path_size_bytes(filepath)
    if size_bytes > DANGER_ZONE_THRESHOLD_BYTES:
        quarantine_to_danger_zone(
            filepath,
            main_directory,
            reason=f"{reason} (file exceeded 10 MB safety threshold at {size_bytes / (1024 * 1024):.2f} MB)",
            confirm=confirm,
        )
        return True

    if confirm is not None and not confirm(f"DELETE file:\n    {filepath}"):
        return False

    try:
        os.unlink(filepath)
        return True
    except OSError:
        return False
