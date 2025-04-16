import requests
import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Get the API key from .env
api_key = os.getenv('ENCORA_API_KEY')
base_url = "https://encora.it/api/collection"

def fetch_encora_collection():
    """Fetch all pages of the Encora collection"""
    collection = []
    page = 1
    while True:
        response = requests.get(f"{base_url}?page={page}", headers={"Authorization": f"Bearer {api_key}", "User-Agent": "BootOrganiser"})
        if response.status_code != 200:
            raise Exception(f"Failed to fetch collection page {page}: {response.status_code}")
        
        data = response.json()
        collection.extend(data['data'])
        
        # If there are no more pages, break the loop
        if not data['next_page_url']:
            break
        
        page += 1
    return collection

def compare_local_encora_ids(local_ids):
    """Compare local Encora IDs with the fetched Encora collection"""
    # Fetch Encora collection
    collection = fetch_encora_collection()
    encora_collection_ids = [str(item['recording']['id']).strip() for item in collection]
    
    # Normalize local IDs: Extract only the Encora ID from tuples or strings
    normalized_local_ids = []
    for item in local_ids:
        if isinstance(item, tuple):
            # If it's a tuple, assume the first element is the Encora ID
            normalized_local_ids.append(str(item[0]).strip())
        elif isinstance(item, str):
            # If it's a string, extract the Encora ID (e.g., from "{e-2004467}")
            if "{" in item and "}" in item:
                start = item.find("{") + 1
                end = item.find("}")
                normalized_local_ids.append(item[start:end].strip())
            else:
                normalized_local_ids.append(item.strip())
        else:
            # If it's neither a tuple nor a string, skip it
            continue
    
    # Find missing Encora IDs locally
    missing_ids = [encora_id for encora_id in encora_collection_ids if encora_id not in normalized_local_ids]
    
    # Find extra Encora IDs locally
    extra_ids = [encora_id for encora_id in normalized_local_ids if encora_id not in encora_collection_ids]
    
    # Only return if there are missing or extra IDs
    if missing_ids or extra_ids:
        return missing_ids, extra_ids
    else:
        return None, None