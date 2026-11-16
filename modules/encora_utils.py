import logging
import os
import unicodedata
from tqdm import tqdm

from modules.api_utils import authenticated_request, build_api_session
from modules.config import config
from modules.path_utils import extract_encora_id, walk_library_dirs

logger = logging.getLogger(__name__)


def find_local_encora_ids(main_directory: str) -> list[tuple[str, str]]:
    """Scan main_directory for release folders tagged with an Encora ID."""
    encora_ids = []
    if not main_directory or not os.path.isdir(main_directory):
        return encora_ids

    for root, dirs, _ in walk_library_dirs(main_directory):
        for dir_name in dirs:
            folder_path = unicodedata.normalize('NFC', os.path.join(root, dir_name))
            encora_id = extract_encora_id(dir_name, folder_path)
            if encora_id:
                encora_ids.append((encora_id, folder_path))

    return encora_ids


def fetch_collection() -> list[dict]:
    """Fetch the full user collection from Encora, tracking completeness in last_complete."""
    fetch_collection.last_complete = False
    if not config.api_key:
        print("Error: ENCORA_API_KEY not set.")
        return []

    base_url = "https://encora.it/api/collection"
    all_recordings = []
    current_page = 1
    page_size = config.collection_page_size

    with build_api_session() as session:
        while True:
            try:
                response = authenticated_request(
                    'GET',
                    f"{base_url}?per_page={page_size}&page={current_page}",
                    session=session,
                    timeout=30,
                )
                data = response.json()

                if 'data' not in data:
                    print(f"\nUnexpected API response format on page {current_page}")
                    break

                all_recordings.extend(data['data'])
                print(f"\rPage: {current_page}, Recordings Loaded: {len(all_recordings)}", end='')

                if not data.get('next_page_url'):
                    fetch_collection.last_complete = True
                    break

                current_page += 1
            except Exception as e:
                logger.warning(f"Error occurred fetching collection page {current_page}: {e}")
                print(f"\nError occurred fetching collection: {e}")
                break

    print()
    return all_recordings


fetch_collection.last_complete = False


def fetch_single_recording(encora_id: str, session=None) -> dict | None:
    """
    Fetch details of a single recording. If merged, the API redirects to the
    target recording whose id will differ from encora_id.
    """
    url = f"https://encora.it/api/recording/{encora_id}"
    try:
        response = authenticated_request('GET', url, session=session)
        data = response.json()
        return data.get('recording') or data
    except Exception as e:
        logger.warning(f"Error fetching recording {encora_id}: {e}")
        print(f"\nError fetching recording {encora_id}: {e}")
        return None


def process_encora_ids(encora_data: list[dict], local_ids: list[tuple[str, str]]) -> list[dict]:
    """Match local Encora ID folders against fetched collection (collecting missing IDs when possible)."""
    results = []
    by_id = {}
    for r in encora_data:
        rec = r.get('recording') or {}
        if rec.get('id') is not None:
            by_id[str(rec['id'])] = r

    with build_api_session({'Content-Type': 'application/json'}) as session:
        for encora_id, path in tqdm(local_ids, desc="Processing local Encora IDs"):
            matching = by_id.get(str(encora_id))
            if matching:
                results.append({
                    'encora_id': encora_id,
                    'path': path,
                    'recording_data': matching.get('recording', {}),
                    'my_format': matching.get('format', ""),
                })
                continue

            url = f"https://encora.it/api/collection/{encora_id}/collect"
            try:
                authenticated_request('POST', url, session=session)
                fetched_recording = fetch_single_recording(encora_id, session=session)
                if fetched_recording:
                    returned_id = str(fetched_recording.get('id', encora_id))
                    if returned_id != str(encora_id):
                        folder_name = os.path.basename(path)
                        tqdm.write(
                            f"\n\033[93m{'='*60}\n"
                            f"  ⚠  RECORDING MERGED\n"
                            f"{'='*60}\033[0m\n"
                            f"  Folder : {folder_name}\n"
                            f"  Old ID : {encora_id}  →  \033[92mNew ID : {returned_id}\033[0m\n"
                            f"  Rename  e-{encora_id}  to  e-{returned_id}  in your folder name\n"
                            f"  \033[96mhttps://encora.it/recordings/{returned_id}\033[0m\n"
                            f"\033[93m{'='*60}\033[0m\n"
                        )
                    entry = {'recording': fetched_recording, 'format': ""}
                    encora_data.append(entry)
                    by_id[str(encora_id)] = entry
                    results.append({
                        'encora_id': encora_id,
                        'path': path,
                        'recording_data': fetched_recording,
                        'my_format': "",
                    })
                else:
                    print(f"\nFailed to fetch recording {encora_id} after collecting.")
            except Exception as err:
                logger.warning(f"Error collecting ID {encora_id} ({path}): {err}")
                print(f"\nError collecting ID {encora_id}: {err}")

    return results
