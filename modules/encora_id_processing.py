import os
import re
import time
import requests
from tqdm import tqdm
from time import sleep
from modules.config import config

# Define regex patterns to extract Encora ID from folder names (handles various containers)
id_pattern = re.compile(r'[\{\[\(](\d+)[\}\]\)]')
e_id_pattern = re.compile(r'[\{\[\(]e-(\d+)[\}\]\)]')

def find_local_encora_ids(main_directory):
    encora_ids = []
    
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
                    # Final fallback: look for raw e-ID without container
                    match = re.search(r'e-(\d+)', dir_name)
                    if match:
                        encora_id = match.group(1)
                    else:
                        continue  # No Encora ID found in this folder
                
            folder_path = os.path.join(root, dir_name)  # Full path
            encora_ids.append((encora_id, folder_path))
    
    return encora_ids

def fetch_collection():
    base_url = "https://encora.it/api/collection"
    api_key = config.api_key
    if not api_key:
        print("Error: ENCORA_API_KEY not set.")
        return []

    headers = {
        'Authorization': f'Bearer {api_key}', 
        'User-Agent': 'BootOrganiser'
    }
    all_recordings = []
    current_page = 1
    retries = 3
    timeout = 30
    page_size = config.collection_page_size

    session = requests.Session()
    session.headers.update(headers)

    while True:
        try:
            response = session.get(f"{base_url}?per_page={page_size}&page={current_page}", timeout=timeout)
            response.raise_for_status()
            data = response.json()

            if 'data' not in data:
                print(f"\nUnexpected API response format on page {current_page}")
                break

            all_recordings.extend(data['data'])
            print(f"\rPage: {current_page}, Recordings Loaded: {len(all_recordings)}", end='')
            
            if not data.get('next_page_url'):
                break
            
            current_page += 1

        except requests.exceptions.Timeout:
            print(f"\nRequest timed out on page {current_page}. Retrying...")
            sleep(2)

        except requests.exceptions.RequestException as e:
            print(f"\nError occurred: {e}")
            retries -= 1
            if retries == 0:
                print("Max retries reached. Exiting.")
                break
            sleep(2)

    print() # New line after the loading indicator
    return all_recordings

def process_encora_ids(encora_data, local_ids):
    results = []
    api_key = config.api_key

    session = requests.Session()
    session.headers.update({
        'Authorization': f'Bearer {api_key}', 
        'Content-Type': 'application/json', 
        "User-Agent": "BootOrganiser"
    })

    # Use tqdm to show progress while processing the local IDs
    for encora_id, path in tqdm(local_ids, desc="Processing local Encora IDs"):
        
        matching_recording = next((r for r in encora_data if r.get('recording', {}).get('id') == int(encora_id)), None)
        
        if matching_recording:
            results.append({
                'encora_id': encora_id,
                'path': path,  
                'recording_data': matching_recording.get('recording', {}),
                'my_format': matching_recording.get('format', "")
            })
        else:            
            url = f"https://encora.it/api/collection/{encora_id}/collect"
            try:
                response = session.post(url)
            
                if response.headers.get('x-RateLimit-Remaining') == '0':
                    print(f"\nRate limit reached for ID {encora_id}. Waiting for 1 minute...")
                    time.sleep(60)
                    response = session.post(url)
                
                response.raise_for_status() 

                fetched_recording = fetch_single_recording(encora_id, session)
                if fetched_recording:
                    encora_data.append({'recording': fetched_recording, 'format': ""})
                    results.append({
                        'encora_id': encora_id,
                        'path': path,
                        'recording_data': fetched_recording,
                        'my_format': ""
                    })
                else:
                    print(f"\nFailed to fetch recording {encora_id} after collecting.")
                    
            except requests.exceptions.HTTPError as err:
                print(f"\nHTTP error occurred for ID {encora_id}: {err}")

    return results

def fetch_single_recording(encora_id, session=None):
    base_url = "https://encora.it/api/recording"
    
    if session is None:
        session = requests.Session()
        session.headers.update({
            'Authorization': f'Bearer {config.api_key}', 
            'User-Agent': 'BootOrganiser'
        })

    retries = 3
    timeout = 30

    for attempt in range(retries):
        try:
            response = session.get(f"{base_url}/{encora_id}", timeout=timeout)
            response.raise_for_status()
            recording_json = response.json()

            if 'id' in recording_json:
                return recording_json
            else:
                print(f"\nNo valid recording ID found yet for {encora_id} (attempt {attempt + 1}/{retries})...")
                time.sleep(2)
        except requests.exceptions.RequestException as e:
            print(f"\nRequest error for {encora_id}: {e}")
            time.sleep(2)

    return None
