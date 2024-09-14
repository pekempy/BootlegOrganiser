import os
import shutil
from tqdm import tqdm
from dotenv import load_dotenv
import re

# Load environment variables from .env
load_dotenv()

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
    processing_directory = os.path.join(main_directory, '!processing')
    if not os.path.exists(processing_directory):
        os.makedirs(processing_directory)
    
    for folder in os.listdir(main_directory):
        if folder != '!non-encora' and folder != '!processing':
            source = os.path.join(main_directory, folder)
            destination = os.path.join(processing_directory, folder)
            if os.path.isdir(source):
                shutil.move(source, destination)

def format_show_folder(api_response, encora_id, format_string):
    show_name = api_response.get('show', 'Unknown Show')
    tour = api_response.get('tour', 'Unknown Tour')
    date = api_response.get('date', {}).get('full_date', 'Unknown Date')
    matinee = api_response.get('matinee', '')
    nft = api_response.get('nft', {})
    nft_status = "NFT" if nft.get('nft_forever', False) else ""
    master = api_response.get('master', 'Unknown Master')
    type_of_boot = api_response.get('metadata', {}).get('media_type', 'Unmatched').capitalize()
    encora_id_str = f"{encora_id}"

    if format_string == os.getenv('SHOW_DIRECTORY_FORMAT', '{show_name}/{tour}/{type}/{folder}'):
        show_name = remove_sorting_articles(show_name)
        
    format_dict = {
        'show_name': sanitize_path(show_name),
        'tour': sanitize_path(tour),
        'date': date,
        'matinee': matinee,
        'nft': nft_status,
        'master': sanitize_path(master),
        'encora_id': encora_id_str,
        'type': type_of_boot,
    }
    
    formatted_name = format_string.format(**format_dict)
    formatted_name = formatted_name.replace('[]', '').replace('[] ', '').strip()
    formatted_name = formatted_name.replace('  ', ' ').strip()
    formatted_name = formatted_name.replace('  ', ' ').strip()

    return formatted_name

def move_and_rename_folders(encora_data, main_directory):
    processing_directory = os.path.join(main_directory, '!processing')

    show_directory_format = os.getenv('SHOW_DIRECTORY_FORMAT', '{show_name}/{tour}/{type}/{folder}')
    show_folder_format = os.getenv('SHOW_FOLDER_FORMAT', '[{date}] [{matinee}] [{nft}] {show_name} ~ {master} {encora_id}')

    for entry in tqdm(encora_data, desc="Moving and Renaming Folders"):
        path = entry['path']
        api_response = entry['api_response']
        encora_id = entry['encora_id']
        
        show_directory = format_show_folder(api_response, encora_id, show_directory_format)
        show_folder = format_show_folder(api_response, encora_id, show_folder_format)

        relative_path = os.path.relpath(path, start=processing_directory)
        old_path = os.path.join(processing_directory, relative_path)
        new_path = os.path.join(main_directory, show_directory, show_folder)

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
