import os
from dotenv import load_dotenv, set_key

class Config:
    def __init__(self, env_path='.env'):
        self.env_path = env_path
        load_dotenv(self.env_path)
        
    def get(self, key, default=None):
        return os.getenv(key, default)
    
    def set(self, key, value):
        os.environ[key] = str(value)
        set_key(self.env_path, key, str(value))

    @property
    def api_key(self):
        return self.get('ENCORA_API_KEY')

    @property
    def main_directory(self):
        return self.get('BOOTLEG_MAIN_DIRECTORY')

    @property
    def generate_cast_files(self):
        return self.get('GENERATE_CAST_FILES', 'false').lower() == 'true'

    @property
    def generate_encoraid_files(self):
        return self.get('GENERATE_ENCORAID_FILES', 'false').lower() == 'true'

    @property
    def update_encora_format(self):
        return self.get('UPDATE_ENCORA_FORMAT', 'true').lower() == 'true'

    @property
    def dont_override_encora_format(self):
        return self.get('DONT_OVERRIDE_ENCORA_FORMAT', 'false').lower() == 'true'

    @property
    def redownload_subtitles(self):
        return self.get('REDOWNLOAD_SUBTITLES', 'false').lower() == 'true'

    @property
    def generate_checksums(self):
        return self.get('GENERATE_CHECKSUMS', 'false').lower() == 'true'

    @property
    def collection_page_size(self):
        return int(self.get('COLLECTION_PAGE_SIZE', '100'))

    @property
    def show_folder_format(self):
        return self.get('SHOW_FOLDER_FORMAT')

    @property
    def show_directory_format(self):
        return self.get('SHOW_DIRECTORY_FORMAT')

    @property
    def excluded_ids(self):
        ids = self.get('EXCLUDED_IDS', '')
        return [id.strip() for id in ids.split(',') if id.strip()]

    @property
    def exclude_format_update(self):
        return self.get('EXCLUDE_FORMAT_UPDATE', 'false').lower() == 'true'

    @property
    def exclude_cast_files(self):
        return self.get('EXCLUDE_CAST_FILES', 'false').lower() == 'true'

    @property
    def exclude_checksum_files(self):
        return self.get('EXCLUDE_CHECKSUM_FILES', 'false').lower() == 'true'

    @property
    def date_container(self):
        return self.get('DATE_CONTAINER', 'None')

    @property
    def nft_container(self):
        return self.get('NFT_CONTAINER', 'None')

    @property
    def matinee_container(self):
        return self.get('MATINEE_CONTAINER', 'None')

    @property
    def amount_container(self):
        return self.get('AMOUNT_CONTAINER', 'None')

    @property
    def encora_id_container(self):
        return self.get('ENCORA_ID_CONTAINER', 'None')

    @property
    def date_replace_char(self):
        return self.get('DATE_REPLACE_CHAR', '0')

    # ── Content organiser ──────────────────────────────────────────────────────

    @property
    def organise_content(self):
        return self.get('ORGANISE_CONTENT', 'false').lower() == 'true'

    @property
    def unknown_pattern_action(self):
        """How to handle unrecognised file patterns: 'prompt' | 'skip' | 'log'."""
        return self.get('UNKNOWN_PATTERN_ACTION', 'prompt')

    @property
    def tracked_folder_name(self):
        return self.get('TRACKED_FOLDER_NAME', 'Tracked')

    @property
    def untracked_folder_name(self):
        return self.get('UNTRACKED_FOLDER_NAME', 'Untracked')

    @property
    def vobs_folder_name(self):
        return self.get('VOBS_FOLDER_NAME', 'VOBs')

    @property
    def parts_folder_name(self):
        return self.get('PARTS_FOLDER_NAME', 'Parts')

    @property
    def photos_folder_name(self):
        return self.get('PHOTOS_FOLDER_NAME', 'Photos')

    @property
    def programme_folder_name(self):
        return self.get('PROGRAMME_FOLDER_NAME', 'Programme')

    @property
    def delete_artwork(self):
        return self.get('DELETE_ARTWORK', 'true').lower() == 'true'

    @property
    def move_photos(self):
        return self.get('MOVE_PHOTOS', 'true').lower() == 'true'

    @property
    def move_programmes(self):
        return self.get('MOVE_PROGRAMMES', 'true').lower() == 'true'

    @property
    def delete_junk_files(self):
        return self.get('DELETE_JUNK_FILES', 'true').lower() == 'true'

    @property
    def archive_folder_name(self):
        return self.get('ARCHIVE_FOLDER_NAME', 'Archive')

    @property
    def move_archives(self):
        return self.get('MOVE_ARCHIVES', 'true').lower() == 'true'

config = Config()
