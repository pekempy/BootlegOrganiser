import hashlib
import os
import requests
from tqdm import tqdm
import re
import time
from modules.config import config
from modules.api_utils import authenticated_request
from modules.diff_utils import append_to_diff_file, are_functionally_identical


api_key = config.api_key

def get_encora_id_from_folder(folder_name):
    """Extract Encora ID from the folder name (handles various containers)."""
    match = re.search(r'[\{\[\(]e-(\d+)[\}\]\)]', folder_name)
    if not match:
        match = re.search(r'e-(\d+)', folder_name)
    return match.group(1) if match else None

language_code_mapping = {
    "Abkhazian": "ab",
    "Afar": "aa",
    "Afrikaans": "af",
    "Albanian": "sq",
    "Amharic": "am",
    "Arabic": "ar",
    "Armenian": "hy",
    "Assamese": "as",
    "Avar": "av",
    "Avestan": "ae",
    "Aymara": "ay",
    "Azerbaijani": "az",
    "Bambara": "bm",
    "Bashkir": "ba",
    "Basque": "eu",
    "Belarusian": "be",
    "Bengali": "bn",
    "Bihari": "bh",
    "Bislama": "bi",
    "Bosnian": "bs",
    "Breton": "br",
    "Bulgarian": "bg",
    "Burmese": "my",
    "Catalan": "ca",
    "Chinese": "zh",
    "Chinese (Simplified)": "zh-Hans",
    "Chinese (Traditional)": "zh-Hant",
    "Corsican": "co",
    "Croatian": "hr",
    "Czech": "cs",
    "Danish": "da",
    "Dutch": "nl",
    "English": "en",
    "Esperanto": "eo",
    "Estonian": "et",
    "Fijian": "fj",
    "Finnish": "fi",
    "French": "fr",
    "Galician": "gl",
    "Georgian": "ka",
    "German": "de",
    "Greek": "el",
    "Guarani": "gn",
    "Gujarati": "gu",
    "Haitian": "ht",
    "Hausa": "ha",
    "Hebrew": "he",
    "Hindi": "hi",
    "Hmong": "hmn",
    "Hungarian": "hu",
    "Icelandic": "is",
    "Igbo": "ig",
    "Indonesian": "id",
    "Interlingua": "ia",
    "Irish": "ga",
    "Italian": "it",
    "Japanese": "ja",
    "Javanese": "jw",
    "Kazakh": "kk",
    "Kinyarwanda": "rw",
    "Korean": "ko",
    "Kurdish": "ku",
    "Kyrgyz": "ky",
    "Lao": "lo",
    "Latin": "la",
    "Latvian": "lv",
    "Lithuanian": "lt",
    "Luxembourgish": "lb",
    "Macedonian": "mk",
    "Malagasy": "mg",
    "Malay": "ms",
    "Malayalam": "ml",
    "Maltese": "mt",
    "Maori": "mi",
    "Marathi": "mr",
    "Mongolian": "mn",
    "Nepali": "ne",
    "Norwegian": "no",
    "Odia": "or",
    "Pashto": "ps",
    "Persian": "fa",
    "Polish": "pl",
    "Portuguese": "pt",
    "Punjabi": "pa",
    "Quechua": "qu",
    "Romanian": "ro",
    "Russian": "ru",
    "Samoan": "sm",
    "Sanskrit": "sa",
    "Scots Gaelic": "gd",
    "Serbian": "sr",
    "Sesotho": "st",
    "Shona": "sn",
    "Sindhi": "sd",
    "Sinhalese": "si",
    "Slovak": "sk",
    "Slovenian": "sl",
    "Somali": "so",
    "Spanish": "es",
    "Sundanese": "su",
    "Swahili": "sw",
    "Swedish": "sv",
    "Tajik": "tg",
    "Tamil": "ta",
    "Tatar": "tt",
    "Telugu": "te",
    "Thai": "th",
    "Turkish": "tr",
    "Turkmen": "tk",
    "Uighur": "ug",
    "Ukrainian": "uk",
    "Urdu": "ur",
    "Uzbek": "uz",
    "Vietnamese": "vi",
    "Welsh": "cy",
    "Xhosa": "xh",
    "Yiddish": "yi",
    "Yoruba": "yo",
    "Zulu": "zu",
}

def file_content_hash(file_path):
    """Calculate the SHA-256 hash of the file content."""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as file:
        for chunk in iter(lambda: file.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

def download_all_subtitles(recording_ids_with_subtitles):
    """Download subtitles for the given Encora IDs."""
    if not recording_ids_with_subtitles:
        return

    # Extract all recording IDs
    recording_ids = [item[0] for item in recording_ids_with_subtitles]
    ids_str = ','.join(recording_ids)
    
    subtitles_url = f"https://encora.it/api/subtitles/{ids_str}"
    headers = {'Authorization': f'Bearer {api_key}', "User-Agent": "BootOrganiser"}
    
    try:
        response = authenticated_request('GET', subtitles_url, headers=headers)
        subtitles_data = response.json()

        # Group subtitles by recording_id
        subtitles_by_recording_id = {}
        for subtitle in subtitles_data:
            recording_id = str(subtitle['recording_id'])
            if recording_id not in subtitles_by_recording_id:
                subtitles_by_recording_id[recording_id] = []
            subtitles_by_recording_id[recording_id].append(subtitle)

        updated_subs = 0
        for recording_id, folder_path in tqdm(recording_ids_with_subtitles, desc="Downloading non-matching subtitles"):
            if recording_id in subtitles_by_recording_id:
                subtitles = subtitles_by_recording_id[recording_id]
                download_directory = folder_path

                for subtitle in subtitles:
                    subtitle_url = subtitle['url']
                    # Get the ISO language code from the mapping
                    lang_code = language_code_mapping.get(subtitle['language'], subtitle['language'][:2].lower())
                    author_sanitised = subtitle['author'].replace(' ', '_').replace('/', ' ').replace('\\', '').replace(':', '-')
                    
                    # Use the unique subtitle ID to prevent collisions (e.g. for Act 1/Act 2 splits by same author)
                    subtitle_id = subtitle.get('id')
                    if subtitle_id:
                        file_name = f"{author_sanitised} ({subtitle_id}).{lang_code}.{subtitle['file_type'].lower()}"
                    else:
                        file_name = f"{author_sanitised}.{lang_code}.{subtitle['file_type'].lower()}"
                    
                    file_path = os.path.join(download_directory, file_name)

                    # Ensure the download directory exists
                    os.makedirs(download_directory, exist_ok=True)

                    # Download the subtitle file
                    try:
                        subtitle_response = requests.get(subtitle_url, stream=True, timeout=10)
                        subtitle_response.raise_for_status()
                    except (requests.exceptions.RequestException, requests.exceptions.Timeout) as e:
                        print(f"\nSkipping subtitle due to download error: {e}")
                        continue
                    new_content = subtitle_response.content

                    # Check if ANY existing file in the directory matches this content
                    is_already_present = False
                    existing_matching_file = None
                    
                    subtitle_extensions = ('.ass', '.srt', '.vtt', '.sub', '.sbv')
                    for item in os.listdir(download_directory):
                        if item.lower().endswith(subtitle_extensions):
                            existing_file_path = os.path.join(download_directory, item)
                            try:
                                with open(existing_file_path, 'rb') as f:
                                    existing_content_bytes = f.read()
                                
                                if are_functionally_identical(existing_content_bytes, new_content):
                                    is_already_present = True
                                    existing_matching_file = existing_file_path
                                    break
                            except Exception:
                                continue

                    if is_already_present:
                        # Content already exists locally under some name, skip
                        continue

                    # If not present, prepare the filename
                    # Look for "Act" or "Part" in the subtitle description if available
                    content_note = ""
                    note = subtitle.get('notes', '') or ''
                    act_match = re.search(r'(Act\s*\d+|Part\s*\d+)', note, re.I)
                    if act_match:
                        content_note = f"_{act_match.group(1).replace(' ', '')}"
                    
                    # Try to find a unique ID (Encora uses 'id' or 'subtitle_id' in different contexts)
                    sub_uid = subtitle.get('id') or subtitle.get('subtitle_id')
                    if not sub_uid:
                        # Use a stable hash of the URL if no ID is provided by the API
                        sub_uid = hashlib.md5(subtitle_url.encode()).hexdigest()[:8]
                    
                    # Generate a unique filename that won't overwrite unless it's a perfect match
                    file_name = f"{author_sanitised}{content_note}_{sub_uid}.{lang_code}.{subtitle['file_type'].lower()}"
                    file_path = os.path.join(download_directory, file_name)

                    # Write the new content to the file
                    if os.path.exists(file_path):
                        # Record the difference before overwriting
                        with open(file_path, 'rb') as f:
                            old_content_bytes = f.read()
                        append_to_diff_file('subtitle_diffs.txt', recording_id, old_content_bytes, new_content, file_path)

                    with open(file_path, 'wb') as file:
                        file.write(new_content)
                    updated_subs += 1
        
        if updated_subs > 0:
            print(f"Downloaded/Updated {updated_subs} subtitle files.")
        else:
            print("All local subtitles are already up to date.")
                
    except Exception as e:
        print(f"Error downloading subtitles: {e}")
                

def download_subtitles_for_folders(main_directory, recording_data):
    """Recursively download subtitles for all folders in the main directory."""
    print("Checking for missing subtitles...")
    # Get all directories to process
    all_folders = []
    for root, dirs, _ in os.walk(main_directory):
        for folder_name in dirs:
            all_folders.append(os.path.join(root, folder_name))

    # Array to store recording_ids and their folder paths
    recording_ids_with_subtitles = []

    for folder_path in all_folders:
        encora_id = get_encora_id_from_folder(os.path.basename(folder_path))
        
        if encora_id:
            # Find the recording entry that matches the encora_id
            matching_recording = next((item for item in recording_data if item['encora_id'] == encora_id), None)
            
            if matching_recording and matching_recording.get('recording_data', {}).get('metadata', {}).get('has_subtitles', False):
                recording_ids_with_subtitles.append((encora_id, folder_path))

    if not recording_ids_with_subtitles:
        print("No recordings found requiring subtitle downloads.")
        return

    download_all_subtitles(recording_ids_with_subtitles)
