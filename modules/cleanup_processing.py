import os
import re
import shutil
import logging

logger = logging.getLogger(__name__)

# Encora release-folder pattern  — {e-NNN}, [e-NNN], (e-NNN)
_ENCORA_ID_RE = re.compile(r'[\{\[\(]e-\d+[\}\]\)]')

def get_folder_size(folder):
    """Returns the total size of the folder in bytes."""
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(folder):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if not os.path.islink(fp):  # Skip symbolic links
                total_size += os.path.getsize(fp)
    return total_size

def delete_empty_directories(directory):
    """Recursively delete all empty directories within the given directory."""
    for dirpath, dirnames, filenames in os.walk(directory, topdown=False):
        if os.path.islink(dirpath) or os.path.basename(dirpath).startswith('.'):
            continue
        if not dirnames and not filenames:
            folder_name = os.path.basename(dirpath)
            # SAFETY: never silently delete a folder whose name contains an Encora
            # ID — if it's empty that's unexpected and should be surfaced loudly.
            if _ENCORA_ID_RE.search(folder_name):
                logger.warning(
                    f"delete_empty_directories: would delete Encora release folder "
                    f"that appears empty — SKIPPING to avoid data loss: {dirpath}"
                )
                continue
            logger.debug(f"delete_empty_directories: removing empty dir {dirpath}")
            try:
                os.rmdir(dirpath)
            except OSError:
                pass

def clean_processing_folder(main_directory):
    """Delete empty directories inside !processing and the folder itself if empty."""
    processing_folder = os.path.join(main_directory, '!processing')

    if os.path.exists(processing_folder):
        delete_empty_directories(processing_folder)

        if get_folder_size(processing_folder) == 0:
            shutil.rmtree(processing_folder)
