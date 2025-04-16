import os
import requests
import csv
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Get the API key from .env
api_key = os.getenv('ENCORA_API_KEY')
base_url = "https://encora.it/api/recording"

def fetch_recording_details(encora_id):
    """Fetch recording details from the Encora API."""
    headers = {
        'Authorization': f'Bearer {api_key}',
        'User-Agent': 'BootOrganiser'
    }
    try:
        response = requests.get(f"{base_url}/{encora_id}", headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching details for Encora ID {encora_id}: {e}")
        return None

def parse_recording_details(recording_data):
    """Extract relevant details from the recording data."""
    if not recording_data:
        print("No recording data found.")  # Debug print
        return None

    # Directly access the fields from the top-level response
    show_name = recording_data.get('show', 'Unknown Show')
    tour_name = recording_data.get('tour', 'Unknown Tour')
    date_info = recording_data.get('date', {})
    date = date_info.get('full_date', 'Unknown Date')
    master = recording_data.get('master', 'Unknown Master')
    nft = recording_data.get('nft', {})
    nft_status = (
        nft.get('nft_date', 'NFT Forever')[:10]  # Extract only the date (YYYY-MM-DD)
        if nft.get('nft_date') else "Not NFT"
    )
    cast = recording_data.get('cast', [])
    cast_list = ', '.join(
        f"{entry['performer'].get('name', 'Unknown Performer')} "
        f"({(entry.get('status') if isinstance(entry.get('status'), str) else '').strip()} {entry['character'].get('name', 'Unknown Role')})".strip()
        for entry in cast if entry.get('performer') and entry.get('character')
    )
    encora_link = f"https://encora.it/recordings/{recording_data.get('id', 'Unknown')}"

    return {
        'encora_id': recording_data.get('id', 'Unknown'),
        'show_name': show_name,
        'tour_name': tour_name,
        'date': date,
        'master': master,
        'nft_status': nft_status,
        'cast': cast_list,
        'encora_link': encora_link
    }

def process_ids(file_path, output_file):
    """Process IDs from the given file and fetch their details."""
    if not os.path.exists(file_path):
        print(f"{file_path} does not exist.")
        return

    with open(file_path, 'r') as f:
        ids = [line.strip().split('/')[-1] for line in f if line.strip()]

    details = []
    for encora_id in ids:
        print(f"Fetching details for Encora ID: {encora_id}")
        recording_data = fetch_recording_details(encora_id)
        parsed_details = parse_recording_details(recording_data)
        if parsed_details:
            details.append(parsed_details)

    # Write the details to the output CSV file
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['encora_id', 'show_name', 'tour_name', 'date', 'master', 'nft_status', 'cast', 'encora_link'])
        writer.writeheader()
        writer.writerows(details)

if __name__ == "__main__":
    print("Processing missing IDs...")
    process_ids('local_not_on_encora.txt', 'local_not_on_encora_details.csv')

    print("Processing extra IDs...")
    process_ids('on_encora_not_local.txt', 'on_encora_not_local_details.csv')