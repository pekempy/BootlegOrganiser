import os
import re
import requests
from tqdm import tqdm
from dotenv import load_dotenv
from time import sleep

# Load environment variables from .env
load_dotenv()

# Define regex patterns to extract Encora ID from folder names
id_pattern = re.compile(r'\{(\d+)\}')
e_id_pattern = re.compile(r'\{e-(\d+)\}')

# Get the API key from environment variables
api_key = os.getenv('ENCORA_API_KEY')

def find_local_encora_ids(main_directory):
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

def fetch_collection():
    base_url = "https://encora.it/api/collection"
    headers = {
        'Authorization': f'Bearer {api_key}', 
        'User-Agent': 'BootOrganiser'
    }
    all_recordings = []
    current_page = 1
    retries = 3
    timeout = 30

    page_size = os.getenv('COLLECTION_PAGE_SIZE')

    while True:
        try:
            print(f"Fetching page {current_page}...")
            # Attempt the request with a timeout
            response = requests.get(f"{base_url}?per_page={page_size}&page={current_page}", headers=headers, timeout=timeout)
            response.raise_for_status()  # Raise an error for bad status codes (e.g. 4xx, 5xx)
            data = response.json()

            # Append all recording data from the current page
            all_recordings.extend(data['data'])
            
            # If there's no next page, break the loop
            if data['next_page_url'] is None:
                break
            
            # Move to the next page
            current_page += 1

        except requests.exceptions.Timeout:
            print(f"Request timed out after {timeout} seconds. Retrying...")
            sleep(2)  # Wait 2 seconds before retrying

        except requests.exceptions.RequestException as e:
            # If any other error occurs, handle it or retry
            print(f"Error occurred: {e}")
            retries -= 1
            if retries == 0:
                print("Max retries reached. Exiting.")
                break
            sleep(2)  # Wait before retrying

    return all_recordings

def process_encora_ids(encora_data, local_ids):
    results = []

    # Use tqdm to show progress while processing the local IDs
    for i, (encora_id, path) in enumerate(tqdm(local_ids, desc="Processing local Encora IDs")):
        
        matching_recording = next((r for r in encora_data if r['recording']['id'] == int(encora_id)), None)
        
        if matching_recording:
            # Process the matching recording and store results
            results.append({
                'encora_id': encora_id,
                'path': path,  
                'recording_data': matching_recording.get('recording', {}),
                'my_format': matching_recording['format']
            })
        else:
            print(f"No matching recording found for Encora ID {encora_id} in {path}")

    return results