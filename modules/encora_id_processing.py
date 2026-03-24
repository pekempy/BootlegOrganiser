import os
import re
import time
import requests
from tqdm import tqdm
from time import sleep
from modules.config import config
from modules.api_utils import authenticated_request

# Define regex patterns to extract Encora ID from folder names (strictly requires 'e-' prefix)
e_id_pattern = re.compile(r'[\{\[\(]e-(\d+)[\}\]\)]')

def find_local_encora_ids(main_directory):
    encora_ids = []
    
    # Loop through all subfolders in main_directory
    for root, dirs, _ in os.walk(main_directory):
        for dir_name in dirs:
            folder_path = os.path.join(root, dir_name)
            encora_id = None

            # 1. Prioritise folder name regex patterns (strictly requiring 'e-')
            if match := e_id_pattern.search(dir_name):
                encora_id = match.group(1)
            elif match := re.search(r'e-(\d+)', dir_name):
                encora_id = match.group(1)

            # 2. Fallback to hidden .encora-ID files ONLY if folder name has no ID
            if not encora_id:
                try:
                    for file_name in os.listdir(folder_path):
                        if file_name.startswith('.encora-'):
                            id_match = re.search(r'\.encora-(\d+)', file_name)
                            if id_match:
                                encora_id = id_match.group(1)
                                break
                except (PermissionError, FileNotFoundError):
                    pass

            if encora_id:
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
    timeout = 30
    page_size = config.collection_page_size

    session = requests.Session()
    session.headers.update(headers)

    while True:
        try:
            response = authenticated_request('GET', f"{base_url}?per_page={page_size}&page={current_page}", session=session, timeout=timeout)
            data = response.json()

            if 'data' not in data:
                print(f"\nUnexpected API response format on page {current_page}")
                break

            all_recordings.extend(data['data'])
            print(f"\rPage: {current_page}, Recordings Loaded: {len(all_recordings)}", end='')
            
            if not data.get('next_page_url'):
                break
            
            current_page += 1

        except Exception as e:
            print(f"\nError occurred fetching collection: {e}")
            break

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
                response = authenticated_request('POST', url, session=session)
                
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
                    
            except Exception as err:
                 print(f"\nError collecting ID {encora_id}: {err}")

    return results

def fetch_single_recording(encora_id, session=None):
    """Fetch details of a single recording."""
    url = f"https://encora.it/api/recording/{encora_id}"
    try:
        response = authenticated_request('GET', url, session=session)
        data = response.json()
        return data.get('recording') or data # Wrap for different response shapes if needed
    except Exception as e:
        print(f"\nError fetching recording {encora_id}: {e}")
        return None
