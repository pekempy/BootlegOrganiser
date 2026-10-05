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
from modules.checksum_generator import create_checksum_files, verify_all_checksums
from modules.move_and_rename_folders import move_folders_to_processing, move_and_rename_folders
from modules.manage_file_sizes import process_directory, send_format
from modules.diff_utils import clear_diff_files, log_missing_smalls

def section(title):
    """Print a visible section header to the terminal."""
    width = 60
    print(f"\n\033[96m{'='*width}\033[0m")
    print(f"\033[96m  {title}\033[0m")
    print(f"\033[96m{'='*width}\033[0m")


def run_organiser():
    main_directory = config.main_directory
    if main_directory is None:
        print("Error: BOOTLEG_MAIN_DIRECTORY not found in config.")
        return

    # Clear previous diff files
    clear_diff_files()

    section("NON-ENCORA FOLDERS")
    non_encora_folder = os.path.join(main_directory, '!non-encora')
    move_folders_with_ne(main_directory, non_encora_folder)

    section("FETCHING COLLECTION FROM ENCORA")
    print('This may take some time...')
    local_ids = find_local_encora_ids(main_directory)
    encora_data = fetch_collection()
    recording_data = process_encora_ids(encora_data, local_ids)
    print(f"Matched {len(recording_data)} recordings.")

    if config.generate_cast_files:
        section("CAST FILES")
        print(f"Generating cast files for {len(recording_data)} recordings")
        create_cast_files(recording_data)

    if config.generate_encoraid_files:
        section("ENCORA ID FILES")
        print(f"Generating .encora-id files for {len(recording_data)} recordings")
        create_encora_id_files(recording_data)

    if config.generate_checksums:
        section("CHECKSUM MANIFESTS")
        print(f"Generating checksum manifests for {len(recording_data)} recordings")
        create_checksum_files(recording_data)

    section("FILE SIZES & ENCORA FORMATS")
    updated_formats_count = 0
    desc = "Updating non-matching Encora Formats..." if config.update_encora_format else "Evaluating file sizes..."
    for encora_id, folder_path in tqdm.tqdm(local_ids, desc=desc, unit="ID"):
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

            if config.update_encora_format:
                if send_format(recording_data, encora_id, summary):
                    updated_formats_count += 1

    if updated_formats_count > 0:
        print(f"Updated formats for {updated_formats_count} recordings.")
    else:
        print("No format updates were needed.")

    section("MOVING & RENAMING FOLDERS")
    move_and_rename_folders(recording_data, main_directory)

    from modules.cleanup_processing import delete_empty_directories
    delete_empty_directories(main_directory)

    if config.redownload_subtitles:
        section("SUBTITLES")
        download_subtitles_for_folders(main_directory, recording_data)

    section("COLLECTION CHECK")
    missing_ids, extra_ids = compare_local_encora_ids(local_ids, encora_data)

    if missing_ids and len(missing_ids) > 0:
        with open('on_encora_not_local.txt', 'w') as f:
            f.write('Missing IDs locally:\n')
            for encora_id in missing_ids:
                f.write(f"{encora_id}\n")

    section("DONE")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bootleg Organiser")
    parser.add_argument("--auto", action="store_true", help="Run without GUI")
    parser.add_argument("--verify-checksums", action="store_true",
                         help="Re-hash and verify all stored checksum manifests, then exit")
    args = parser.parse_args()

    if args.verify_checksums:
        if config.main_directory is None:
            print("Error: BOOTLEG_MAIN_DIRECTORY not found in config.")
            sys.exit(1)
        _, failed = verify_all_checksums(config.main_directory)
        sys.exit(1 if failed else 0)

    if args.auto:
        run_organiser()
    else:
        try:
            from modules.gui_config import start_gui
            start_gui(run_organiser)
        except ImportError:
            print("Error: Tkinter is not installed. The GUI requires it.")
            print("  macOS:   brew install python-tk")
            print("  Ubuntu:  sudo apt install python3-tk")
            print("  Fedora:  sudo dnf install python3-tkinter")
            print("  Windows: reinstall Python from python.org and tick 'tcl/tk and IDLE'")
            print("Run with --auto to skip the GUI entirely.")
            sys.exit(1)
        except Exception as e:
            print(f"Error: Could not start GUI: {e}")
            sys.exit(1)
