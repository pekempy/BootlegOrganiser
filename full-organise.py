import os
import sys
import argparse
import tqdm
from modules.config import config
from modules.cleanup_processing import clean_processing_folder
from modules.collection_checker import compare_local_encora_ids
from modules.download_subtitles import download_subtitles_for_folders
from modules.non_encora_processing import move_folders_with_ne
from modules.encora_id_processing import fetch_collection, find_local_encora_ids, process_encora_ids
from modules.cast_file_generator import create_cast_files, create_encora_id_files
from modules.move_and_rename_folders import move_folders_to_processing, move_and_rename_folders
from modules.manage_file_sizes import process_directory, send_format
from modules.diff_utils import clear_diff_files, log_missing_smalls


sys.stdout.reconfigure(line_buffering=True)

def run_organiser():
    main_directory = config.main_directory
    if main_directory is None:
        print("Error: BOOTLEG_MAIN_DIRECTORY not found in config.")
        return

    # Clear previous diff files
    clear_diff_files()

    # Step 1: Find Encora IDs and process them
    # (Previously we moved everything to !processing, but now we work in-place)
    # Step 1: Find Encora IDs and process them

    # Step 2: Handle '!non-encora' folder processing
    non_encora_folder = os.path.join(main_directory, '!non-encora')
    move_folders_with_ne(main_directory, non_encora_folder)

    print('Starting script...')
    print('This may take some time to fetch your collection from Encora...')
    local_ids = find_local_encora_ids(main_directory)
    encora_data = fetch_collection()
    recording_data = process_encora_ids(encora_data, local_ids)

    # Step 4: Generate cast files & .encora_id files if enabled
    if config.generate_cast_files:
        print(f"Generating cast files for {len(recording_data)} recordings")
        create_cast_files(recording_data)

    if config.generate_encoraid_files:
        print(f"Generating .encora-id files for {len(recording_data)} recordings")
        create_encora_id_files(recording_data)

    # Step 5: Evaluate file sizes
    updated_formats_count = 0
    for encora_id, folder_path in tqdm.tqdm(local_ids, desc="Updating non-matching Encora Formats...", unit="ID"):
        if config.exclude_format_update and str(encora_id) in config.excluded_ids:
            continue
        summary = process_directory(folder_path)  
        if(summary):
            if "VOB (no smalls)" in summary:
                matching_recording = next((item for item in recording_data if str(item['encora_id']) == str(encora_id)), None)
                if matching_recording:
                    rec_data = matching_recording.get('recording_data', {})
                    show = rec_data.get('show', 'Unknown Show')
                    tour = rec_data.get('tour', 'Unknown Tour')
                    date = rec_data.get('date', {}).get('full_date', 'Unknown Date')
                    master = rec_data.get('master', 'Unknown Master')
                    log_missing_smalls(encora_id, show, tour, date, master)

            # Update encora formats _if_ the current format doesn't match what is local
            if send_format(recording_data, encora_id, summary):
                updated_formats_count += 1
    
    if updated_formats_count > 0:
        print(f"Updated formats for {updated_formats_count} recordings.")
    else:
        print("No format updates were needed.")

    # Step 6: Move and rename folders based on encora_data
    move_and_rename_folders(recording_data, main_directory)

    # Step 5: Clean up empty directories
    from modules.cleanup_processing import delete_empty_directories
    delete_empty_directories(main_directory)

    # Step 8: Download subtitles
    if config.redownload_subtitles:
        download_subtitles_for_folders(main_directory, recording_data)

    # Step 9: Check for any missing
    missing_ids, extra_ids = compare_local_encora_ids(local_ids, encora_data)

    # Write missing IDs to a file if count > 0
    if missing_ids and len(missing_ids) > 0:
        with open('on_encora_not_local.txt', 'w') as f:
            f.write('Missing IDs locally:\n')
            for encora_id in missing_ids:
                f.write(f"{encora_id}\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bootleg Organiser")
    parser.add_argument("--auto", action="store_true", help="Run without GUI")
    args = parser.parse_args()

    if args.auto:
        run_organiser()
    else:
        try:
            from modules.gui_config import start_gui
            start_gui(run_organiser)
        except ImportError:
            print("Error: Tkinter not found. GUI is required unless running with --auto.")
            sys.exit(1)
        except Exception as e:
            print(f"Error: Could not start GUI: {e}")
            sys.exit(1)
