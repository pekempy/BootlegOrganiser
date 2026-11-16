import logging
import os
import re
import shutil
import unicodedata
from datetime import datetime
from tqdm import tqdm

from modules.config import config
from modules.path_utils import case_safe_rename, exact_path_matches, is_same_path
from modules.safety_utils import safe_delete_directory

logger = logging.getLogger(__name__)


def sanitize_path(path: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', '_', path)


def remove_sorting_articles(name: str) -> str:
    articles = [
        'a ', 'an ', 'the ',
        'de ', 'het ', 'een ', 't ', '\'t ',
        'el ', 'la ', 'los ', 'las ',
        'le ', 'las ', 'la ', 'les ',
        'der ', 'die ', 'das ', 'den ', 'dem ', 'des ',
        'ang ', 'sa ', 'ng ', 'mga ',
    ]
    for article in articles:
        if name.lower().startswith(article):
            name = name[len(article):].strip()
    return name


def format_date(date_info: dict) -> str:
    full_date = date_info.get('full_date', None)
    if full_date is None:
        return 'Unknown Year'

    year, month, day = full_date.split('-')
    month_known = date_info.get('month_known', True)
    day_known = date_info.get('day_known', True)
    date_variant = date_info.get('date_variant', '')

    char = config.date_replace_char
    double_char = f"{char}{char}"

    month = double_char if not month_known else month
    day = double_char if not day_known else day

    formatted_date = f"{year}-{month}-{day}"
    if date_variant:
        formatted_date += f" ({date_variant})"

    return formatted_date


def format_show_folder(recording_data: dict, encora_id: str, format_string: str, folder_name: str | None = None) -> str:
    show_name = recording_data.get('show', 'Unknown Show')
    tour = recording_data.get('tour', 'Unknown Tour')
    date_info = recording_data.get('date', {})
    date = format_date(date_info)
    matinee = recording_data.get('date', {}).get('time', '')
    nft = recording_data.get('nft', {})
    nft_status = ""
    if nft.get('nft_forever', False):
        nft_status = "NFTF"
    elif nft.get('nft_date'):
        try:
            nft_date_str = nft['nft_date'].split('T')[0] if 'T' in nft['nft_date'] else nft['nft_date']
            nft_date_obj = datetime.strptime(nft_date_str, '%Y-%m-%d')
            if nft_date_obj > datetime.now():
                nft_status = f"NFT-{nft_date_str}"
        except (ValueError, TypeError):
            pass
    master = recording_data.get('master', 'Unknown Master')
    amount_recorded = recording_data.get('metadata', {}).get('amount_recorded', 'Unknown').capitalize()
    type_of_boot = recording_data.get('metadata', {}).get('media_type', 'Unmatched').capitalize()
    encora_id_str = f"e-{encora_id}"

    if format_string == os.getenv('SHOW_DIRECTORY_FORMAT', '{show_name}/{tour}/{type}/{folder}'):
        show_name = remove_sorting_articles(show_name)

    amount_recorded_mapping = {
        'Complete': '',
        'Highlights': 'hl',
        'Partial': 'prt',
    }
    amount_recorded = amount_recorded_mapping.get(amount_recorded, '')

    matinee_mapping = {
        'matinee': 'm',
        'evening': '',
    }
    matinee = matinee_mapping.get(matinee.lower(), '')

    def wrap(val, container):
        if not val or container == 'None':
            return val
        if container == 'Brackets []':
            return f"[{val}]"
        if container == 'Parenthesis ()':
            return f"({val})"
        if container == 'Curly Brackets {}':
            return f"{{{val}}}"
        return val

    format_dict = {
        'show_name': sanitize_path(show_name),
        'tour': sanitize_path(tour),
        'date': wrap(date, config.date_container),
        'highlights': wrap(amount_recorded, config.amount_container),
        'matinee': wrap(matinee, config.matinee_container),
        'nft': wrap(nft_status, config.nft_container),
        'master': sanitize_path(master),
        'encora_id': wrap(encora_id_str, config.encora_id_container),
        'type': type_of_boot,
        'short_type': type_of_boot[0].upper() if type_of_boot and type_of_boot != 'Unmatched' else '',
        'variant': '',
        'folder': folder_name or '',
    }

    formatted_name = format_string.format(**format_dict)
    formatted_name = formatted_name.replace('[]', '').replace('[] ', '').strip()
    formatted_name = formatted_name.replace('{}', '').replace('{} ', '').strip()
    formatted_name = formatted_name.replace('  ', ' ').strip()
    formatted_name = formatted_name.replace('  ', ' ').strip()
    return formatted_name


def move_merge(src: str, dst: str) -> None:
    """Move src to dst safely. Merges directories without ever overwriting destination files."""
    if is_same_path(src, dst):
        case_safe_rename(src, dst)
        return

    if os.path.islink(src):
        try:
            target = os.path.realpath(src)
            if target == os.path.realpath(dst) or target.startswith(os.path.realpath(dst) + os.sep):
                return
        except OSError:
            pass
        if os.path.lexists(dst):
            logger.warning(f"Skipping symlink {src}: destination already exists at {dst}")
            print(f"Skipping symlink {src}: destination already exists at {dst}")
            return
        shutil.move(src, dst)
        return

    if os.path.isdir(src):
        if not os.path.lexists(dst):
            shutil.move(src, dst)
        elif os.path.isdir(dst):
            for entry in os.listdir(src):
                move_merge(os.path.join(src, entry), os.path.join(dst, entry))
            try:
                if not os.listdir(src):
                    os.rmdir(src)
            except OSError:
                pass
        else:
            logger.warning(f"Skipping directory {src}: non-directory already exists at {dst}")
            print(f"Skipping directory {src}: non-directory already exists at {dst}")
    else:
        if os.path.lexists(dst):
            logger.warning(f"Skipping file {src}: destination already exists at {dst}")
            print(f"Skipping file {src}: destination already exists at {dst}")
            return
        shutil.move(src, dst)


def move_and_rename_folders(encora_data: list[dict], main_directory: str, confirm=None) -> None:
    show_directory_format = config.show_directory_format or '{show_name}/{tour}/{type}/{folder}'
    show_folder_format = config.show_folder_format or '[{date}] [{matinee}] [{nft}] {show_name} ~ {master} {encora_id}'

    encora_data_sorted = sorted(encora_data, key=lambda x: len(x['path']), reverse=True)

    for entry in tqdm(encora_data_sorted, desc="Moving and Renaming Folders"):
        old_path = unicodedata.normalize('NFC', entry['path'])
        recording_data = entry['recording_data']
        encora_id = entry['encora_id']

        show_folder = format_show_folder(recording_data, encora_id, show_folder_format)
        show_directory = format_show_folder(recording_data, encora_id, show_directory_format, folder_name=show_folder)

        if '{folder}' in show_directory_format:
            new_path = unicodedata.normalize('NFC', os.path.join(main_directory, show_directory))
        else:
            new_path = unicodedata.normalize('NFC', os.path.join(main_directory, show_directory, show_folder))

        if not os.path.lexists(old_path) or os.path.islink(old_path):
            continue

        if is_same_path(old_path, new_path):
            if exact_path_matches(old_path, new_path):
                continue
            if confirm is not None and not confirm(
                f"RENAME folder:\n    {old_path}\n    → {new_path}"
            ):
                continue
            try:
                if is_same_path(os.path.dirname(old_path), os.path.dirname(new_path)):
                    case_safe_rename(old_path, new_path)
            except OSError as e:
                logger.error(f"Error renaming {old_path} to {new_path}: {e}")
                print(f"Error renaming {old_path} to {new_path}: {e}")
            continue

        try:
            real_old = os.path.realpath(old_path)
            real_new = os.path.realpath(new_path)
            if real_new.startswith(real_old + os.sep):
                logger.warning(f"Skipping move {old_path} → {new_path}: destination is inside source")
                print(f"Skipping move {old_path} → {new_path}: destination is inside source")
                continue
        except OSError:
            pass

        if confirm is not None and not confirm(
            f"MOVE folder:\n    {old_path}\n    → {new_path}"
        ):
            continue

        try:
            if not os.path.exists(new_path):
                os.makedirs(new_path)
        except Exception as e:
            logger.error(f"Error creating directories for {new_path}: {e}")
            print(f"Error creating directories: {e}")
            continue

        for item in os.listdir(old_path):
            src = os.path.join(old_path, item)
            dst = os.path.join(new_path, item)
            try:
                move_merge(src, dst)
            except (FileNotFoundError, shutil.Error, OSError) as e:
                logger.error(f"Error moving {src} to {dst}: {e}")
                print(f"Error moving {src} to {dst}: {e}")

        _MACOS_JUNK = {'.DS_Store', '.localized', '__MACOSX'}
        for junk in list(os.listdir(old_path)):
            if junk in _MACOS_JUNK or junk.startswith('._'):
                try:
                    junk_path = os.path.join(old_path, junk)
                    if os.path.isfile(junk_path):
                        os.remove(junk_path)
                except OSError:
                    pass

        try:
            if not is_same_path(old_path, new_path):
                if not os.listdir(old_path):
                    safe_delete_directory(
                        old_path,
                        main_directory,
                        reason="Source folder cleanup after move_and_rename_folders",
                    )
                else:
                    print(f"Directory '{old_path}' is not empty.")
        except (FileNotFoundError, OSError) as e:
            logger.warning(f"Error cleaning source folder {old_path}: {e}")
            print(f"Error cleaning source folder {old_path}: {e}")
