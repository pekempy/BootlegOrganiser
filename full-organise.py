import os
import shutil
from dotenv import load_dotenv
import tqdm
from modules.cleanup_processing import clean_processing_folder
from modules.collection_checker import compare_local_encora_ids
from modules.download_subtitles import download_subtitles_for_folders
from modules.non_encora_processing import move_folders_with_ne
from modules.encora_id_processing import find_encora_ids, process_encora_ids
from modules.cast_file_generator import create_cast_files, create_encora_id_files
from modules.move_and_rename_folders import move_folders_to_processing, move_and_rename_folders
from modules.manage_file_sizes import process_directory, send_media_summary

# Load environment variables from .env
load_dotenv()

# Get the API key and main directory from .env
api_key = os.getenv('ENCORA_API_KEY')
main_directory = os.getenv('BOOTLEG_MAIN_DIRECTORY')

# Check if the variables are loaded correctly
if main_directory is None:
    raise ValueError("BOOTLEG_MAIN_DIRECTORY not found in .env file.")

def get_folder_size(folder_path):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(folder_path):
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            total_size += os.path.getsize(file_path)
    return total_size

# Step 1: Move folders to '!processing'
move_folders_to_processing(main_directory)

# Step 2: Handle '!non-encora' folder processing
non_encora_folder = os.path.join(main_directory, '!non-encora')
move_folders_with_ne(main_directory, non_encora_folder)

# Step 3: Find Encora IDs and process them
encora_ids = find_encora_ids(main_directory)
encora_data = process_encora_ids(encora_ids, limit=5000)  # Adjust the limit as necessary

# Step 4: Generate cast files & .encora_id files if enabled
generate_cast_files = os.getenv('GENERATE_CAST_FILES', 'false').lower() == 'true'
if generate_cast_files:
    print(f"Generating cast files for {len(encora_data)} recordings")
    create_cast_files(encora_data)

generate_encora_id_files = os.getenv('GENERATE_ENCORAID_FILES', 'false').lower() == 'true'
if generate_cast_files:
    print(f"Generating .encora_id files for {len(encora_data)} recordings")
    create_encora_id_files(encora_data)

# Step 5: Move and rename folders based on encora_data
move_and_rename_folders(encora_data, main_directory)

# Step 6: Clean up the '!processing' folder if empty
clean_processing_folder(main_directory)
clean_processing_folder(main_directory)
clean_processing_folder(main_directory)
clean_processing_folder(main_directory)

# Step 7: Evaluate file sizes
for encora_id, folder_path in tqdm.tqdm(encora_ids, desc="Updating Encora Formats...", unit="ID"):
    summary = process_directory(folder_path)  # Call the function from manage_file_sizes
    if(summary):
        response = send_media_summary(encora_id, summary)

# Step 8: Download subtitles
print("Downloading subtitles...")
download_subtitles_for_folders(main_directory)

# Step 9: Check for any missing
missing_ids, extra_ids = compare_local_encora_ids(encora_ids)
if missing_ids:
    with open('missing_ids.txt', 'w') as f:
        f.write('Missing IDs locally:\n')
        for encora_id in missing_ids:
            f.write(f"{encora_id}\n")

# Write extra IDs to a file
if extra_ids:
    with open('extra_ids.txt', 'w') as f:
        f.write('Extra IDs locally:\n')
        for encora_id in extra_ids:
            f.write(f"{encora_id}\n")
