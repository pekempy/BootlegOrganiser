import logging
import os
import shutil

from modules.path_utils import walk_library_dirs

logger = logging.getLogger(__name__)


def folder_exists_in_non_encora(folder_name: str, base_path: str) -> bool:
    for _, dirs, _ in walk_library_dirs(base_path):
        if folder_name in dirs:
            return True
    return False


def move_folders_with_ne(main_directory: str, non_encora_folder: str) -> None:
    """Move folders tagged with {ne} into !non-encora without overwriting collisions."""
    if not os.path.exists(non_encora_folder):
        os.makedirs(non_encora_folder, exist_ok=True)
        print(f"Created folder: {non_encora_folder}")

    for root, dirs, _ in walk_library_dirs(main_directory):
        kept_dirs = []
        for dir_name in dirs:
            if '{ne}' in dir_name:
                folder_path = os.path.join(root, dir_name)
                dest_path = os.path.join(non_encora_folder, dir_name)

                if os.path.lexists(dest_path) or folder_exists_in_non_encora(dir_name, non_encora_folder):
                    logger.info(f"Skipping Non-Encora folder {folder_path}: {dir_name} already exists in !non-encora")
                    print(f"Skipping Non-Encora folder {folder_path}: {dir_name} already exists in !non-encora")
                    continue

                try:
                    shutil.move(folder_path, dest_path)
                    logger.info(f"Moved Non-Encora recording {folder_path} → {dest_path}")
                    print(f"Moved Non-Encora recording from {folder_path} to {dest_path}")
                except OSError as e:
                    logger.error(f"Error moving Non-Encora folder {folder_path}: {e}")
                    kept_dirs.append(dir_name)
            else:
                kept_dirs.append(dir_name)
        dirs[:] = kept_dirs
