import os
from modules.encora_id_processing import find_encora_ids
from modules.collection_checker import compare_local_encora_ids

def main():
    # Load environment variables from .env
    from dotenv import load_dotenv
    load_dotenv()

    # Get the main directory from .env
    main_directory = os.getenv('BOOTLEG_MAIN_DIRECTORY')

    # Check if the variable is loaded correctly
    if main_directory is None:
        raise ValueError("BOOTLEG_MAIN_DIRECTORY not found in .env file.")

    # Find Encora IDs
    encora_id_tuples = find_encora_ids(main_directory)
    
    # Extract just the IDs
    encora_ids = [str(encora_id).strip() for encora_id, path in encora_id_tuples]

    # Compare local and Encora IDs
    missing_ids, extra_ids = compare_local_encora_ids(encora_ids)

    # Write missing IDs to a file if there are any
    if missing_ids:
        with open('missing_ids.txt', 'w') as f:
            f.write('Missing IDs locally:\n')
            for encora_id in missing_ids:
                f.write(f"{encora_id}\n")

    # Write extra IDs to a file if there are any
    if extra_ids:
        with open('extra_ids.txt', 'w') as f:
            f.write('Extra IDs locally:\n')
            for encora_id in extra_ids:
                f.write(f"{encora_id}\n")

if __name__ == "__main__":
    main()