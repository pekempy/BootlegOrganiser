import os
import shutil

def folder_exists_in_non_encora(folder_name, base_path):
    for root, dirs, _ in os.walk(base_path):
        if folder_name in dirs:
            return True
    return False

def move_folders_with_ne(main_directory, non_encora_folder):
    # Create the '!non-encora' folder if it doesn't exist
    if not os.path.exists(non_encora_folder):
        os.makedirs(non_encora_folder)
        print(f"Created folder: {non_encora_folder}")

    # Loop through all subfolders in main_directory
    for root, dirs, _ in os.walk(main_directory):
        for dir_name in dirs:
            if '{ne}' in dir_name:
                # Paths
                folder_path = os.path.join(root, dir_name)
                dest_path = os.path.join(non_encora_folder, dir_name)
                
                # Check if the folder already exists anywhere in '!non-encora'
                if not folder_exists_in_non_encora(dir_name, non_encora_folder):
                    # Move the folder to '!non-encora'
                    shutil.move(folder_path, dest_path)
                    print(f"Moved Non-Encora recording from {folder_path} to {dest_path}")
                else:
                    continue
