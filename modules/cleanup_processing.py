import os
import shutil

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
        if not dirnames and not filenames:
            os.rmdir(dirpath)

def clean_processing_folder(main_directory):
    """Delete empty directories inside !processing and the folder itself if empty."""
    processing_folder = os.path.join(main_directory, '!processing')

    if os.path.exists(processing_folder):
        delete_empty_directories(processing_folder)

        if get_folder_size(processing_folder) == 0:
            shutil.rmtree(processing_folder)
