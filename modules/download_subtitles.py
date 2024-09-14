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
    for file_name in os.listdir(download_directory):
        if file_name.endswith('.srt') or file_name.endswith('.ass'):
            file_path = os.path.join(download_directory, file_name)
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
        
        for subtitle in subtitles:
            if subtitle['language'] == 'English':
                subtitle_url = subtitle['url']
                file_name = f"{subtitle['author'].replace(' ', '_')}.{subtitle['file_type'].lower()}"
                file_path = os.path.join(download_directory, file_name)

                # Get the size of the file
                subtitle_response = requests.get(subtitle_url, stream=True)
                subtitle_response.raise_for_status()
                total_size = int(subtitle_response.headers.get('content-length', 0))
                
                with open(file_path, 'wb') as file:
                    for chunk in subtitle_response.iter_content(chunk_size=1024):
                        file.write(chunk)
                
    except requests.exceptions.RequestException as e:
        print(f"Error downloading subtitles: {e}")

def download_subtitles_for_folders(main_directory):
    """Recursively download English subtitles for all folders in the main directory."""
    
    for root, dirs, files in os.walk(main_directory):
        for folder_name in dirs:
            folder_path = os.path.join(root, folder_name)
            encora_id = get_encora_id_from_folder(folder_name)
            
            if encora_id:
                download_english_subtitles(encora_id, folder_path)
