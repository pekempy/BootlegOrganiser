import os
from dotenv import load_dotenv
import tqdm
from modules.cleanup_processing import clean_processing_folder
from modules.collection_checker import compare_local_encora_ids
from modules.download_subtitles import download_subtitles_for_folders
from modules.non_encora_processing import move_folders_with_ne
from modules.encora_id_processing import fetch_collection, find_local_encora_ids, process_encora_ids
from modules.cast_file_generator import create_cast_files, create_encora_id_files
from modules.move_and_rename_folders import move_folders_to_processing, move_and_rename_folders
from modules.manage_file_sizes import process_directory, send_format

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
local_ids = find_local_encora_ids(main_directory)
encora_data = fetch_collection()
recording_data = process_encora_ids(encora_data, local_ids)

# Step 4: Generate cast files & .encora_id files if enabled
generate_cast_files = os.getenv('GENERATE_CAST_FILES', 'false').lower() == 'true'
if generate_cast_files:
    print(f"Generating cast files for {len(recording_data)} recordings")
    create_cast_files(recording_data)

generate_encora_id_files = os.getenv('GENERATE_ENCORAID_FILES', 'false').lower() == 'true'
if generate_cast_files:
    print(f"Generating .encora-id files for {len(recording_data)} recordings")
    create_encora_id_files(recording_data)

# Step 5: Move and rename folders based on encora_data
move_and_rename_folders(recording_data, main_directory)

# Step 6: Clean up the '!processing' folder if empty
clean_processing_folder(main_directory)

# Step 7: Evaluate file sizes
for encora_id, folder_path in tqdm.tqdm(local_ids, desc="Updating non-matching Encora Formats...", unit="ID"):
    summary = process_directory(folder_path)  
    if(summary):
        # Update encora formats _if_ the current format doesn't match what is local
        response = send_format(recording_data, encora_id, summary)

# Step 8: Download subtitles
download_subtitles_for_folders(main_directory, recording_data)

# Step 9: Check for any missing
missing_ids, extra_ids = compare_local_encora_ids(local_ids)

# Write missing IDs to a file if count > 0
if missing_ids and len(missing_ids) > 0:
    with open('missing_ids.txt', 'w') as f:
        f.write('Missing IDs locally:\n')
        for encora_id in missing_ids:
            f.write(f"{encora_id}\n")

# Write extra IDs to a file if count > 0
if extra_ids and len(extra_ids) > 0:
    with open('extra_ids.txt', 'w') as f:
        f.write('Extra IDs locally:\n')
        for encora_id in extra_ids:
            f.write(f"{encora_id}\n")
