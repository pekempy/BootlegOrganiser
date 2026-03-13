from modules.config import config

def compare_local_encora_ids(local_ids, encora_data):
    """Compare local Encora IDs with the fetched Encora collection"""
    
    encora_collection_ids = [str(item['recording']['id']).strip() for item in encora_data if 'recording' in item and 'id' in item['recording']]
    
    # Normalize local IDs: Extract only the Encora ID from tuples or strings
    normalized_local_ids = []
    for item in local_ids:
        if isinstance(item, tuple):
            # If it's a tuple, assume the first element is the Encora ID
            normalized_local_ids.append(str(item[0]).strip())
        elif isinstance(item, str):
            # If it's a string, extract the Encora ID (e.g., from "{e-2004467}")
            # This part is mostly a fallback as find_local_encora_ids returns tuples
            match = item.strip().strip('{}').replace('e-', '')
            normalized_local_ids.append(match)
        else:
            continue
    
    # Find missing Encora IDs locally
    missing_ids = [encora_id for encora_id in encora_collection_ids if encora_id not in normalized_local_ids]
    
    # Find extra Encora IDs locally
    extra_ids = [encora_id for encora_id in normalized_local_ids if encora_id not in encora_collection_ids]
    
    return missing_ids, extra_ids