import os
import requests
from tqdm import tqdm
from dotenv import load_dotenv
import re

# Load environment variables from .env
load_dotenv()
api_key = os.getenv('ENCORA_API_KEY')

def get_encora_id_from_folder(folder_name):
    """Extract Encora ID from the folder name."""
    match = re.search(r'\{e-(\d+)\}', folder_name)
    return match.group(1) if match else None

def delete_existing_subtitles(download_directory):
    """Delete existing .srt or .ass subtitle files in the download directory."""
    for root, dirs, files in os.walk(download_directory):
        for file_name in files:
            if file_name.endswith('.srt') or file_name.endswith('.ass'):
                file_path = os.path.join(root, file_name)
                os.remove(file_path)

def download_english_subtitles(encora_id, download_directory):
    """Download English subtitles for the given Encora ID."""
    subtitles_url = f"https://encora.it/api/recording/{encora_id}/subtitles"
    headers = {'Authorization': f'Bearer {api_key}'}
    
    try:
        delete_existing_subtitles(download_directory)

        response = requests.get(subtitles_url, headers=headers)
        response.raise_for_status()
        subtitles = response.json()
        
        # Filter English subtitles
        english_subtitles = [subtitle for subtitle in subtitles if isinstance(subtitle, dict) and subtitle.get('language') == 'English']
        
        for subtitle in english_subtitles:
            subtitle_url = subtitle['url']
            file_name = f"{subtitle['author'].replace(' ', '_').replace('/', ' ').replace('\\', '').replace(':', '-')}.{subtitle['file_type'].lower()}"
            file_path = os.path.join(download_directory, file_name)

            # Ensure the download directory exists
            os.makedirs(download_directory, exist_ok=True)

            # Download the subtitle file
            subtitle_response = requests.get(subtitle_url, stream=True)
            subtitle_response.raise_for_status()
            
            with open(file_path, 'wb') as file:
                for chunk in subtitle_response.iter_content(chunk_size=1024):
                    file.write(chunk)
                
    except requests.exceptions.RequestException as e:
        print(f"Error downloading subtitles: {e}")

def download_subtitles_for_folders(main_directory):
    """Recursively download English subtitles for all folders in the main directory."""
    
    # Get all directories to process
    all_folders = []
    for root, dirs, _ in os.walk(main_directory):
        for folder_name in dirs:
            all_folders.append(os.path.join(root, folder_name))

    # Use tqdm to show progress
    for folder_path in tqdm(all_folders, desc="Checking folders for subtitles"):
        encora_id = get_encora_id_from_folder(os.path.basename(folder_path))
        
        if encora_id:
            download_english_subtitles(encora_id, folder_path)
