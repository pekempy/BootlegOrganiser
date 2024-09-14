import os
from dotenv import load_dotenv
from modules.download_subtitles import download_subtitles_for_folders

# Load environment variables from .env
load_dotenv()

# Get the main directory from .env
main_directory = os.getenv('BOOTLEG_MAIN_DIRECTORY')

# Check if the variable is loaded correctly
if main_directory is None:
    raise ValueError("BOOTLEG_MAIN_DIRECTORY not found in .env file.")

# Step: Download subtitles
print("Downloading subtitles...")
download_subtitles_for_folders(main_directory)