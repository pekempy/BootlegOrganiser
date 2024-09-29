import hashlib
import os
import requests
from tqdm import tqdm
from dotenv import load_dotenv
import re
import time

# Load environment variables from .env
load_dotenv()
api_key = os.getenv('ENCORA_API_KEY')

def get_encora_id_from_folder(folder_name):
    """Extract Encora ID from the folder name."""
    match = re.search(r'\{e-(\d+)\}', folder_name)
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
    # Extract all recording IDs
    recording_ids = [item[0] for item in recording_ids_with_subtitles]
    ids_str = ','.join(recording_ids)
    
    subtitles_url = f"https://encora.it/api/subtitles/{ids_str}"
    headers = {'Authorization': f'Bearer {api_key}'}
    
    try:
        response = requests.get(subtitles_url, headers=headers)
        response.raise_for_status()
        
        # Check rate limit header
        if response.headers.get('x-RateLimit-Remaining') == '0':
            print("Rate limit reached. Waiting for 1 minute...")
            time.sleep(60)  # Wait for 1 minute
        
        subtitles_data = response.json()

        # Group subtitles by recording_id
        subtitles_by_recording_id = {}
        for subtitle in subtitles_data:
            recording_id = str(subtitle['recording_id'])
            if recording_id not in subtitles_by_recording_id:
                subtitles_by_recording_id[recording_id] = []
            subtitles_by_recording_id[recording_id].append(subtitle)

        for recording_id, folder_path in tqdm(recording_ids_with_subtitles, desc="Downloading non-matching subtitles"):
            if recording_id in subtitles_by_recording_id:
                subtitles = subtitles_by_recording_id[recording_id]
                download_directory = folder_path

                for subtitle in subtitles:
                    subtitle_url = subtitle['url']
                    # Get the ISO language code from the mapping
                    lang_code = language_code_mapping.get(subtitle['language'], subtitle['language'][:2].lower())
                    file_name = f"{subtitle['author'].replace(' ', '_').replace('/', ' ').replace('\\', '').replace(':', '-')}.{lang_code}.{subtitle['file_type'].lower()}"
                    file_path = os.path.join(download_directory, file_name)

                    # Ensure the download directory exists
                    os.makedirs(download_directory, exist_ok=True)

                    # Download the subtitle file
                    subtitle_response = requests.get(subtitle_url, stream=True)
                    subtitle_response.raise_for_status()

                    # Calculate the hash of the new content
                    new_content_hash = hashlib.sha256()
                    new_content = subtitle_response.content
                    new_content_hash.update(new_content)
                    new_content_hash = new_content_hash.hexdigest()

                    # Check if the file exists and compare the content
                    if os.path.exists(file_path):
                        existing_content_hash = file_content_hash(file_path)
                        if existing_content_hash == new_content_hash:
                            continue  # Skip writing the file if the content is the same

                    # Write the new content to the file
                    with open(file_path, 'wb') as file:
                        file.write(new_content)
                
    except requests.exceptions.RequestException as e:
        print(f"Error downloading subtitles: {e}")
                

def download_subtitles_for_folders(main_directory, recording_data):
    """Recursively download subtitles for all folders in the main directory."""
    
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

    download_all_subtitles(recording_ids_with_subtitles)