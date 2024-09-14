import os
import requests
import urllib
from dotenv import load_dotenv
import re

# Define media formats
VIDEO_FORMATS = {
    '.avi', '.divx', '.m2t', '.m2ts', '.mp4', '.mpeg', '.mpg', '.mts', '.mov', 
    '.mkv', '.vob', '.ts', '.wmv'
}
AUDIO_FORMATS = {
    '.mp3', '.m4a', '.wav', '.flac', '.aiff'
}

load_dotenv()
api_key = os.getenv('ENCORA_API_KEY')

def get_file_size(size_bytes):
    """Convert file size in bytes to a human-readable format with binary units and trim off after the second decimal place."""
    if size_bytes >= 2**30:  # GiB
        size_gb = size_bytes / (2**30)
        return f"{size_gb:.2f}GB"  # Trimmed to two decimal places
    elif size_bytes >= 2**20:  # MiB
        size_mb = size_bytes / (2**20)
        return f"{size_mb:.2f}MB"  # Trimmed to two decimal places
    elif size_bytes >= 2**10:  # KiB
        size_kb = size_bytes / (2**10)
        return f"{size_kb:.2f}KB"  # Trimmed to two decimal places
    else:
        return f"{size_bytes}B"  # No decimal places for bytes

def evaluate_media_files(directory):
    file_info = {'video': {}, 'audio': {}}
    
    for root, _, files in os.walk(directory):
        for file in files:
            file_ext = os.path.splitext(file)[1].lower()
            file_path = os.path.join(root, file)
            file_size_bytes = os.path.getsize(file_path)
            
            if file_ext in VIDEO_FORMATS:
                if file_ext not in file_info['video']:
                    file_info['video'][file_ext] = {'file_size': 0, 'count': 0}
                file_info['video'][file_ext]['file_size'] += file_size_bytes
                file_info['video'][file_ext]['count'] += 1
            elif file_ext in AUDIO_FORMATS:
                if file_ext not in file_info['audio']:
                    file_info['audio'][file_ext] = {'file_size': 0, 'count': 0}
                file_info['audio'][file_ext]['file_size'] += file_size_bytes
                file_info['audio'][file_ext]['count'] += 1

    # Aggregate file sizes and format information
    aggregated_info = []
    for category in ['video', 'audio']:
        for file_type, info in file_info[category].items():
            if file_type == '.vob':
                continue  # Skip VOB files for now
            
            size_str = get_file_size(info['file_size'])
            if info['count'] > 1:
                aggregated_info.append({
                    'file_type': file_type[1:].upper(), 
                    'file_size': size_str,
                    'count': info['count']
                })
            else:
                aggregated_info.append({
                    'file_type': file_type[1:].upper(), 
                    'file_size': size_str
                })

    return aggregated_info

def generate_vob_summary(directory):
    vob_info = {'total_size': 0, 'with_smalls': False}
    has_ifo = has_bup = False
    
    for root, _, files in os.walk(directory):
        for file in files:
            file_ext = os.path.splitext(file)[1].lower()
            file_path = os.path.join(root, file)
            file_size_bytes = os.path.getsize(file_path)
            
            if file_ext == '.vob':
                vob_info['total_size'] += file_size_bytes
            elif file_ext == '.ifo':
                has_ifo = True
            elif file_ext == '.bup':
                has_bup = True
    
    if vob_info['total_size'] > 0:
        vob_info['with_smalls'] = has_ifo or has_bup
        vob_size_str = get_file_size(vob_info['total_size'])
        vob_label = "VOB (with smalls)" if vob_info['with_smalls'] else "VOB (no smalls)"
        return f"{vob_label} ({vob_size_str})"
    
    return None  # Return None if there are no VOB files

def generate_media_summary(aggregated_info, vob_summary):
    summary = []
    for info in aggregated_info:
        if 'count' in info:
            summary.append(f"{info['file_type']} x{info['count']} ({info['file_size']})")
        else:
            summary.append(f"{info['file_type']} ({info['file_size']})")
    
    if vob_summary:
        summary.append(vob_summary)
    
    # Combine the summary into a single string
    media_summary = " | ".join(summary)
    
    return media_summary

def process_directory(directory):
    directory = directory.replace('!processing\\', '')
    media_info = evaluate_media_files(directory)
    vob_summary = generate_vob_summary(directory)
    summary = generate_media_summary(media_info, vob_summary)
    return summary

def send_media_summary(encora_id, media_summary):
    """Send a POST request with the Encora ID and formatted media summary."""
    # Construct the URL
    url = f"https://encora.it/api/collection/{encora_id}/format/{urllib.parse.quote_plus(media_summary)}"
    url = url.replace('+', '%20')

    # Define headers
    headers = {
        'Authorization': f'Bearer {api_key}',  # Ensure api_key is defined and loaded from .env
        'Content-Type': 'application/json'
    }
    
    try:
        # Make the POST request
        response = requests.post(url, headers=headers)
        response.raise_for_status()  # Raise an error for bad responses
        
        # Return the JSON response
        return response.json()
    
    except requests.exceptions.HTTPError as err:
        # Print the HTTP error
        print(f"HTTP error occurred: {err}")
    
    except Exception as err:
        # Print any other error
        print(f"Other error occurred: {err}")
