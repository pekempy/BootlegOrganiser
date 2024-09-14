import os
import re
import requests
from tqdm import tqdm
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Define regex patterns to extract Encora ID from folder names
id_pattern = re.compile(r'\{(\d+)\}')
e_id_pattern = re.compile(r'\{e-(\d+)\}')

# Get the API key from environment variables
api_key = os.getenv('ENCORA_API_KEY')

def find_encora_ids(main_directory):
    encora_ids = []
    total_folders = sum([len(dirs) for _, dirs, _ in os.walk(main_directory)])  # Count total subfolders
    
    # Loop through all subfolders in main_directory with a progress bar
    for root, dirs, _ in tqdm(os.walk(main_directory), total=total_folders, desc="Processing Folders"):
        for dir_name in dirs:
            # Search for Encora ID in the folder name
            match = id_pattern.search(dir_name)
            if match:
                encora_id = match.group(1)
            else:
                match = e_id_pattern.search(dir_name)
                if match:
                    encora_id = match.group(1)
                else:
                    continue  # No Encora ID found in this folder
                
            folder_path = os.path.join(root, dir_name)  # Full path
            encora_ids.append((encora_id, folder_path))
    
    return encora_ids

def query_encora_api(encora_id):
    url = f"https://encora.it/api/recording/{encora_id}"
    headers = {
        'Authorization': f'Bearer {api_key}'
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()  # Raise an error for bad responses
    return response.json()

def process_encora_ids(encora_ids, limit=10):
    results = []
    
    # Use tqdm to show progress for API querying
    for i, (encora_id, path) in enumerate(tqdm(encora_ids[:limit], desc="Querying Encora API")):
        try:
            api_response = query_encora_api(encora_id)
            results.append({
                'encora_id': encora_id,
                'path': path,
                'api_response': api_response
            })
        except requests.RequestException as e:
            print(f"Request failed for path {path}: {e}")
    
    return results
