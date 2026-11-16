import logging
import os

from modules.path_utils import has_encora_id, walk_library_dirs
from modules.safety_utils import get_path_size_bytes, safe_delete_directory

logger = logging.getLogger(__name__)


def get_folder_size(folder: str) -> int:
    """Return the total size of the folder in bytes."""
    return get_path_size_bytes(folder)


def delete_empty_directories(directory: str, confirm=None) -> None:
    """Recursively delete truly empty directories, protecting Encora IDs and >10MB folders."""
    for dirpath, dirnames, filenames in walk_library_dirs(directory, topdown=False):
        if not dirnames and not filenames:
            folder_name = os.path.basename(dirpath)
            if has_encora_id(folder_name):
                logger.warning(
                    f"delete_empty_directories: would delete Encora release folder "
                    f"that appears empty — SKIPPING to avoid data loss: {dirpath}"
                )
                continue
            safe_delete_directory(
                dirpath,
                directory,
                reason="Empty directory cleanup after organisation",
                confirm=confirm,
            )


def clean_processing_folder(main_directory: str, confirm=None) -> None:
    """Clean empty directories inside !processing; quarantine to !danger-zone if >10MB."""
    processing_folder = os.path.join(main_directory, '!processing')

    if os.path.exists(processing_folder):
        delete_empty_directories(processing_folder, confirm=confirm)
        safe_delete_directory(
            processing_folder,
            main_directory,
            reason="!processing cleanup after organisation",
            confirm=confirm,
        )
