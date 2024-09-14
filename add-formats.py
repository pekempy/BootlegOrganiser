import os
import tqdm
from dotenv import load_dotenv
from modules.encora_id_processing import find_encora_ids
from modules.manage_file_sizes import process_directory, send_media_summary

# Load environment variables from .env
load_dotenv()

# Get the main directory from .env
main_directory = os.getenv('BOOTLEG_MAIN_DIRECTORY')

# Check if the variable is loaded correctly
if main_directory is None:
    raise ValueError("BOOTLEG_MAIN_DIRECTORY not found in .env file.")

# Step: Find Encora IDs and process them
encora_ids = find_encora_ids(main_directory)

# Step: Evaluate file sizes
for encora_id, folder_path in tqdm.tqdm(encora_ids, desc="Updating Encora Formats...", unit="ID"):
    summary = process_directory(folder_path)  # Call the function from manage_file_sizes
    if summary:
        response = send_media_summary(encora_id, summary)