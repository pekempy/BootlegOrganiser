import os
import re
import time
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
    
    # Loop through all subfolders in main_directory
    for root, dirs, _ in os.walk(main_directory):
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
            # Attempt the request with a timeout
            response = requests.get(f"{base_url}?per_page={page_size}&page={current_page}", headers=headers, timeout=timeout)
            response.raise_for_status()  # Raise an error for bad status codes (e.g. 4xx, 5xx)
            data = response.json()

            # Append all recording data from the current page
            all_recordings.extend(data['data'])

            # Print the current page and the number of recordings collected so far
            print(f"\rPage: {current_page}, Recordings Loaded: {len(all_recordings)}", end='')
            
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
            headers = {
                'Authorization': f'Bearer {api_key}', 
                'Content-Type': 'application/json', 
                "User-Agent": "BootOrganiser"
            }
            # collect the recording on Encora before adding the format:
            url = f"https://encora.it/api/collection/{encora_id}/collect"
            try:
                response = requests.post(url, headers=headers)
            
                # Check Rate Limit Header
                if response.headers.get('x-RateLimit-Remaining') == '0':
                    print("\nRate limit reached. Waiting for 1 minute...")
                    time.sleep(60)  # Wait for 60 seconds before retrying
                    response = requests.post(url, headers=headers)  # Retry the request
                
                response.raise_for_status() 

                # Appends the data of a single recording into encora_data
                fetched_recording = fetch_single_recording(encora_id)
                if fetched_recording:
                    encora_data.append({'recording': fetched_recording, 'format': ""})
                    results.append({
                        'encora_id': encora_id,
                        'path': path,
                        'recording_data': fetched_recording,
                        'my_format': ""
                    })
                else:
                    print(f"Failed to fetch recording {encora_id} after collecting.")
                    
            except requests.exceptions.HTTPError as err:
                print(f"HTTP error occurred: {err}")

    return results

# Gathers the data from a single recording
def fetch_single_recording(encora_id):
    base_url = "https://encora.it/api/recording"
    headers = {
        'Authorization': f'Bearer {api_key}', 
        'User-Agent': 'BootOrganiser'
    }
    retries = 3
    timeout = 30

    for attempt in range(retries):
        try:
            response = requests.get(f"{base_url}/{encora_id}", headers=headers, timeout=timeout)
            response.raise_for_status()

            recording_json = response.json()

            if 'id' in recording_json:
                return recording_json
            else:
                print(f"No valid recording ID found yet (attempt {attempt + 1}/{retries})...")
                time.sleep(2)
        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")
            time.sleep(2)

    print(f"Failed to fetch recording {encora_id} after {retries} retries.")
    return None
