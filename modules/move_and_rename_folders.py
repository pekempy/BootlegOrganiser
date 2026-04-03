import os
import shutil
import re
from datetime import datetime
from tqdm import tqdm
from modules.config import config

def sanitize_path(path):
    return re.sub(r'[<>:"/\\|?*]', '_', path)

def remove_sorting_articles(name):
    articles = [
        'a ', 'an ', 'the ',
        'de ', 'het ', 'een ', 't ', '\'t ',
        'el ', 'la ', 'los ', 'las ',
        'le ', 'las ', 'la ', 'les ',
        'der ', 'die ', 'das ', 'den ', 'dem ', 'des ',
        'ang ', 'sa ', 'ng ', 'mga '
    ]
    for article in articles:
        if name.lower().startswith(article):
            name = name[len(article):].strip()
    return name

def move_folders_to_processing(main_directory):
    # This function is no longer used but kept for backward compatibility if needed.
    pass

def format_date(date_info):
    full_date = date_info.get('full_date', None)
    
    # If full_date is not provided, return "Unknown Year".
    if full_date is None:
        return 'Unknown Year'

    # Extract year, month, and day from full_date ('YYYY-MM-DD').
    year, month, day = full_date.split('-')

    month_known = date_info.get('month_known', True)
    day_known = date_info.get('day_known', True)
    date_variant = date_info.get('date_variant', '')

    # Use placeholders if month or day are not known.
    char = config.date_replace_char
    double_char = f"{char}{char}"
    
    month = double_char if not month_known else month
    day = double_char if not day_known else day

    # Format the date as 'YYYY-MM-DD' or with placeholders.
    formatted_date = f"{year}-{month}-{day}"

    # Append the date variant if it exists.
    if date_variant:
        formatted_date += f" ({date_variant})"

    return formatted_date

def format_show_folder(recording_data, encora_id, format_string, folder_name=None):
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
            # Handle possible ISO format or simple date
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
        'Partial': 'prt'
    }
    amount_recorded = amount_recorded_mapping.get(amount_recorded, '')

    matinee_mapping = {
        'matinee': 'm',
        'evening': ''
    }
    matinee = matinee_mapping.get(matinee.lower(), '')
    
    def wrap(val, container):
        if not val or container == 'None': return val
        if container == 'Brackets []': return f"[{val}]"
        if container == 'Parenthesis ()': return f"({val})"
        if container == 'Curly Brackets {}': return f"{{{val}}}"
        return val

    # Dictionary used in formatting the string
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
        'folder': folder_name or ''
    }
    
    formatted_name = format_string.format(**format_dict)
    formatted_name = formatted_name.replace('[]', '').replace('[] ', '').strip()
    formatted_name = formatted_name.replace('{}', '').replace('{} ', '').strip()
    formatted_name = formatted_name.replace('  ', ' ').strip()
    formatted_name = formatted_name.replace('  ', ' ').strip()

    return formatted_name

def move_and_rename_folders(encora_data, main_directory):
    show_directory_format = config.show_directory_format or '{show_name}/{tour}/{type}/{folder}'
    show_folder_format = config.show_folder_format or '[{date}] [{matinee}] [{nft}] {show_name} ~ {master} {encora_id}'

    # Sort by path length descending so children are processed before parents
    encora_data_sorted = sorted(encora_data, key=lambda x: len(x['path']), reverse=True)
    
    for entry in tqdm(encora_data_sorted, desc="Moving and Renaming Folders"):
        old_path = entry['path']
        recording_data = entry['recording_data']
        encora_id = entry['encora_id']
        
        show_folder = format_show_folder(recording_data, encora_id, show_folder_format)
        show_directory = format_show_folder(recording_data, encora_id, show_directory_format, folder_name=show_folder)
        
        if '{folder}' in show_directory_format:
            new_path = os.path.join(main_directory, show_directory)
        else:
            new_path = os.path.join(main_directory, show_directory, show_folder)
        
        # If old_path and new_path are the same, nothing to do
        if os.path.normpath(old_path) == os.path.normpath(new_path):
            continue

        # Ensure all directories in the new path exist
        try:
            if not os.path.exists(new_path):
                os.makedirs(new_path)
        except Exception as e:
            print(f"Error creating directories: {e}")
            continue

        if os.path.exists(old_path):
            for item in os.listdir(old_path):
                src = os.path.join(old_path, item)
                dst = os.path.join(new_path, item)

                if os.path.isdir(src):
                    try:
                        shutil.move(src, dst)
                    except FileNotFoundError as e:
                        print(f"FileNotFoundError: {e}")
                else:
                    try:
                        # Overwrite existing file if it exists
                        shutil.move(src, dst)
                    except FileNotFoundError as e:
                        print(f"FileNotFoundError: {e}")
            
            try:
                if not os.listdir(old_path):  # Ensure the directory is empty before removal
                    os.rmdir(old_path)
                else:
                    print(f"Directory '{old_path}' is not empty.")
            except FileNotFoundError as e:
                print(f"FileNotFoundError: {e}")
            except OSError as e:
                print(f"OSError: {e}")
        else:
            print(f"Source path '{old_path}' does not exist.")
