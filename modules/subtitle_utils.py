import hashlib
import logging
import os
import re
from tqdm import tqdm

from modules.api_utils import authenticated_request, build_api_session
from modules.diff_utils import append_to_diff_file, are_functionally_identical
from modules.path_utils import extract_encora_id, is_same_path, walk_library_dirs

logger = logging.getLogger(__name__)

language_code_mapping = {
    "Abkhazian": "ab", "Afar": "aa", "Afrikaans": "af", "Albanian": "sq",
    "Amharic": "am", "Arabic": "ar", "Armenian": "hy", "Assamese": "as",
    "Avar": "av", "Avestan": "ae", "Aymara": "ay", "Azerbaijani": "az",
    "Bambara": "bm", "Bashkir": "ba", "Basque": "eu", "Belarusian": "be",
    "Bengali": "bn", "Bihari": "bh", "Bislama": "bi", "Bosnian": "bs",
    "Breton": "br", "Bulgarian": "bg", "Burmese": "my", "Catalan": "ca",
    "Chinese": "zh", "Chinese (Simplified)": "zh-Hans", "Chinese (Traditional)": "zh-Hant",
    "Corsican": "co", "Croatian": "hr", "Czech": "cs", "Danish": "da",
    "Dutch": "nl", "English": "en", "Esperanto": "eo", "Estonian": "et",
    "Fijian": "fj", "Finnish": "fi", "French": "fr", "Galician": "gl",
    "Georgian": "ka", "German": "de", "Greek": "el", "Guarani": "gn",
    "Gujarati": "gu", "Haitian": "ht", "Hausa": "ha", "Hebrew": "he",
    "Hindi": "hi", "Hmong": "hmn", "Hungarian": "hu", "Icelandic": "is",
    "Igbo": "ig", "Indonesian": "id", "Interlingua": "ia", "Irish": "ga",
    "Italian": "it", "Japanese": "ja", "Javanese": "jw", "Kazakh": "kk",
    "Kinyarwanda": "rw", "Korean": "ko", "Kurdish": "ku", "Kyrgyz": "ky",
    "Lao": "lo", "Latin": "la", "Latvian": "lv", "Lithuanian": "lt",
    "Luxembourgish": "lb", "Macedonian": "mk", "Malagasy": "mg", "Malay": "ms",
    "Malayalam": "ml", "Maltese": "mt", "Maori": "mi", "Marathi": "mr",
    "Mongolian": "mn", "Nepali": "ne", "Norwegian": "no", "Odia": "or",
    "Pashto": "ps", "Persian": "fa", "Polish": "pl", "Portuguese": "pt",
    "Punjabi": "pa", "Quechua": "qu", "Romanian": "ro", "Russian": "ru",
    "Samoan": "sm", "Sanskrit": "sa", "Scots Gaelic": "gd", "Serbian": "sr",
    "Sesotho": "st", "Shona": "sn", "Sindhi": "sd", "Sinhalese": "si",
    "Slovak": "sk", "Slovenian": "sl", "Somali": "so", "Spanish": "es",
    "Sundanese": "su", "Swahili": "sw", "Swedish": "sv", "Tajik": "tg",
    "Tamil": "ta", "Tatar": "tt", "Telugu": "te", "Thai": "th",
    "Turkish": "tr", "Turkmen": "tk", "Uighur": "ug", "Ukrainian": "uk",
    "Urdu": "ur", "Uzbek": "uz", "Vietnamese": "vi", "Welsh": "cy",
    "Xhosa": "xh", "Yiddish": "yi", "Yoruba": "yo", "Zulu": "zu",
}


def download_all_subtitles(recording_ids_with_subtitles: list[tuple[str, str]]) -> tuple[int, list[str]]:
    """Download subtitles for matched recordings. Returns (updated_count, [folder_basenames])."""
    if not recording_ids_with_subtitles:
        return 0, []

    recording_ids = [item[0] for item in recording_ids_with_subtitles]
    chunk_size = 25

    try:
        with build_api_session() as session:
            subtitles_data = []
            for i in range(0, len(recording_ids), chunk_size):
                chunk = recording_ids[i:i + chunk_size]
                subtitles_url = f"https://encora.it/api/subtitles/{','.join(chunk)}"
                response = authenticated_request('GET', subtitles_url, session=session)
                subtitles_data.extend(response.json())

            subtitles_by_recording_id: dict[str, list] = {}
            for subtitle in subtitles_data:
                rec_id = str(subtitle['recording_id'])
                subtitles_by_recording_id.setdefault(rec_id, []).append(subtitle)

            updated_subs = 0
            updated_folders = []
            for recording_id, folder_path in tqdm(recording_ids_with_subtitles, desc="Downloading non-matching subtitles"):
                rec_updated = False
                for subtitle in subtitles_by_recording_id.get(recording_id, []):
                    subtitle_url = subtitle['url']
                    lang_code = language_code_mapping.get(subtitle['language'], subtitle['language'][:2].lower())
                    author = subtitle.get('author', 'Unknown')
                    author_sanitised = re.sub(r'[<>:"/\\|?*]', '_', author).strip()

                    coverage = subtitle.get('coverage', '')
                    if coverage:
                        coverage_str = f" [{coverage.replace('-', ' ').title()}]"
                    else:
                        note = subtitle.get('notes', '') or ''
                        act_match = re.search(r'(Act\s*\d+|Part\s*\d+)', note, re.I)
                        coverage_str = f" [{act_match.group(1).title()}]" if act_match else ""

                    sub_uid = subtitle.get('id') or subtitle.get('subtitle_id') or hashlib.md5(subtitle_url.encode()).hexdigest()[:8]
                    ext = subtitle['file_type'].lower()
                    file_name = f"{author_sanitised}{coverage_str} {{{sub_uid}}}.{lang_code}.{ext}"
                    file_path = os.path.join(folder_path, file_name)
                    os.makedirs(folder_path, exist_ok=True)

                    try:
                        subtitle_response = authenticated_request('GET', subtitle_url, session=session, timeout=15)
                        if subtitle_response is None:
                            print(f"\nSkipping subtitle due to empty download response: {subtitle_url}")
                            continue
                    except Exception as e:
                        logger.warning(f"Skipping subtitle due to download error ({subtitle_url}): {e}")
                        print(f"\nSkipping subtitle due to download error: {e}")
                        continue
                    new_content = subtitle_response.content

                    is_already_present = False
                    existing_matching_file_path = None
                    subtitle_extensions = ('.ass', '.srt', '.vtt', '.sub', '.sbv')
                    for item in os.listdir(folder_path):
                        if item.lower().endswith(subtitle_extensions):
                            existing_file_path = os.path.join(folder_path, item)
                            try:
                                with open(existing_file_path, 'rb') as f:
                                    existing_content_bytes = f.read()
                                if are_functionally_identical(existing_content_bytes, new_content):
                                    is_already_present = True
                                    existing_matching_file_path = existing_file_path
                                    break
                            except OSError:
                                continue

                    if is_already_present and existing_matching_file_path:
                        if os.path.basename(existing_matching_file_path) != file_name:
                            try:
                                if os.path.lexists(file_path) and not is_same_path(existing_matching_file_path, file_path):
                                    print(f"Skipping subtitle rename: destination already exists at {file_path}")
                                else:
                                    os.rename(existing_matching_file_path, file_path)
                                    updated_subs += 1
                                    rec_updated = True
                            except OSError as e:
                                print(f"Error renaming local subtitle: {e}")
                        continue

                    if os.path.exists(file_path):
                        with open(file_path, 'rb') as f:
                            old_content_bytes = f.read()
                        append_to_diff_file('subtitle_diffs.txt', recording_id, old_content_bytes, new_content, file_path)

                    with open(file_path, 'wb') as file:
                        file.write(new_content)
                    updated_subs += 1
                    rec_updated = True

                if rec_updated:
                    updated_folders.append(os.path.basename(folder_path))

            return updated_subs, updated_folders
    except Exception as e:
        logger.warning(f"Error downloading subtitles: {e}")
        print(f"Error downloading subtitles: {e}")
        return 0, []


def download_subtitles_for_folders(main_directory: str, recording_data: list[dict]) -> tuple[int, list[str]]:
    """Recursively download missing subtitles for matched folders in main_directory."""
    print("Checking for missing subtitles...")
    by_id = {str(item['encora_id']): item for item in recording_data}
    recording_ids_with_subtitles = []

    for root, dirs, _ in walk_library_dirs(main_directory):
        for folder_name in dirs:
            folder_path = os.path.join(root, folder_name)
            encora_id = extract_encora_id(folder_name)
            if encora_id:
                match = by_id.get(str(encora_id))
                if match and match.get('recording_data', {}).get('metadata', {}).get('has_subtitles', False):
                    recording_ids_with_subtitles.append((encora_id, folder_path))

    if not recording_ids_with_subtitles:
        return 0, []

    return download_all_subtitles(recording_ids_with_subtitles)
