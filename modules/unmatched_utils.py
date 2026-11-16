import logging
import os
import shutil
import unicodedata

from modules.path_utils import unique_path

logger = logging.getLogger(__name__)

_SYSTEM_JUNK_FILES = {'.ds_store', '.localized', 'thumbs.db', 'desktop.ini'}

def _is_system_junk(filename: str) -> bool:
    low = filename.lower()
    return low in _SYSTEM_JUNK_FILES or low.startswith('._')


def _has_real_files(dirpath: str) -> bool:
    """Return True if dirpath contains at least one non-junk file anywhere beneath it."""
    for root, dirs, files in os.walk(dirpath):
        dirs[:] = [d for d in dirs if not d.startswith('.') and not os.path.islink(os.path.join(root, d))]
        for fn in files:
            if fn.startswith('.') or _is_system_junk(fn):
                continue
            return True
    return False

def _path_identity(path: str) -> tuple:
    """
    Return a canonical identity key for an existing path that is immune to
    macOS NFD/NFC differences and case-insensitive filesystem casing.
    """
    try:
        st = os.stat(path)
        if st.st_ino:
            return ('ino', st.st_dev, st.st_ino)
    except OSError:
        pass
    return ('path', unicodedata.normalize('NFC', os.path.normcase(os.path.realpath(path))))


def move_unmatched_items(
    main_directory: str,
    unmatched_folder: str,
    matched_recording_data: list,
    confirm=None,
) -> list[str]:
    """
    Move local folders and loose files that are not matched to Encora into !unmatched/.

    Preserves hierarchy directories (e.g. Show/Tour/Video/) that contain matched
    release folders underneath them, and never touches !-prefixed folders
    (!non-encora, !unmatched, !danger-zone, !processing), hidden directories, or symlinks.
    """
    if not main_directory or not os.path.isdir(main_directory):
        return []

    main_id = _path_identity(main_directory)
    matched_ids = set()
    protected_ancestors = {main_id}

    for entry in matched_recording_data:
        p = entry.get('path')
        if not p or not os.path.exists(p):
            continue
        matched_ids.add(_path_identity(p))
        cur = os.path.dirname(os.path.abspath(p))
        while cur and cur != os.path.dirname(cur):
            cur_id = _path_identity(cur)
            protected_ancestors.add(cur_id)
            if cur_id == main_id:
                break
            cur = os.path.dirname(cur)

    moved_items: list[str] = []

    for root, dirs, files in os.walk(main_directory, topdown=True):
        root_id = _path_identity(root)

        if root_id in matched_ids:
            dirs[:] = []
            continue

        kept_dirs = []
        for d in dirs:
            if d.startswith('.') or d.startswith('!'):
                continue
            full_d = os.path.join(root, d)
            if os.path.islink(full_d):
                continue
            dir_id = _path_identity(full_d)
            if dir_id in matched_ids:
                continue
            if dir_id in protected_ancestors:
                kept_dirs.append(d)
                continue
            # Never move empty folders into !unmatched — let empty-dir cleanup handle them
            if not _has_real_files(full_d):
                continue

            rel_path = unicodedata.normalize('NFC', os.path.relpath(full_d, main_directory))
            dst = unique_path(os.path.join(unmatched_folder, rel_path))
            if confirm is not None and not confirm(
                f"MOVE unmatched folder to !unmatched:\n    {full_d}\n    → {dst}"
            ):
                continue
            try:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.move(full_d, dst)
                logger.info(f"Moved unmatched folder {full_d} → {dst}")
                print(f"Moved unmatched folder from {full_d} to {dst}")
                moved_items.append(dst)
            except OSError as e:
                logger.error(f"Error moving unmatched folder {full_d}: {e}")

        dirs[:] = kept_dirs

        for fn in files:
            if fn.startswith('.') or _is_system_junk(fn):
                continue
            full_f = os.path.join(root, fn)
            if os.path.islink(full_f):
                continue
            rel_path = unicodedata.normalize('NFC', os.path.relpath(full_f, main_directory))
            dst = unique_path(os.path.join(unmatched_folder, rel_path))
            if confirm is not None and not confirm(
                f"MOVE unmatched file to !unmatched:\n    {full_f}\n    → {dst}"
            ):
                continue
            try:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.move(full_f, dst)
                logger.info(f"Moved unmatched file {full_f} → {dst}")
                print(f"Moved unmatched file from {full_f} to {dst}")
                moved_items.append(dst)
            except OSError as e:
                logger.error(f"Error moving unmatched file {full_f}: {e}")

    return moved_items
