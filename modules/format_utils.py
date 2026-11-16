import logging
import os
import urllib.parse

from modules.api_utils import authenticated_request, build_api_session
from modules.config import config

logger = logging.getLogger(__name__)

VIDEO_FORMATS = {
    '.avi', '.divx', '.m2t', '.m2ts', '.mp4', '.m4v', '.mpeg', '.mpg', '.mts', '.mov',
    '.mkv', '.vob', '.ts', '.wmv',
}
AUDIO_FORMATS = {
    '.mp3', '.m4a', '.wav', '.flac', '.aiff', '.m4b', '.alac', '.aac',
}


def get_file_size(size_bytes: int) -> str:
    """Convert file size in bytes to a human-readable binary unit string."""
    if size_bytes >= 2**30:
        return f"{size_bytes / (2**30):.2f}GB"
    if size_bytes >= 2**20:
        return f"{size_bytes / (2**20):.2f}MB"
    if size_bytes >= 2**10:
        return f"{size_bytes / (2**10):.2f}KB"
    return f"{size_bytes}B"


def evaluate_media_files(directory: str) -> list[dict]:
    file_info = {'video': {}, 'audio': {}}

    for root, _, files in os.walk(directory):
        if os.path.islink(root):
            continue
        for file in files:
            file_ext = os.path.splitext(file)[1].lower()
            file_path = os.path.join(root, file)
            if os.path.islink(file_path):
                continue
            try:
                file_size_bytes = os.path.getsize(file_path)
            except OSError:
                continue

            if file_ext in VIDEO_FORMATS:
                bucket = file_info['video'].setdefault(file_ext, {'file_size': 0, 'count': 0})
                bucket['file_size'] += file_size_bytes
                bucket['count'] += 1
            elif file_ext in AUDIO_FORMATS:
                bucket = file_info['audio'].setdefault(file_ext, {'file_size': 0, 'count': 0})
                bucket['file_size'] += file_size_bytes
                bucket['count'] += 1

    aggregated_info = []
    for category in ('video', 'audio'):
        for file_type, info in file_info[category].items():
            if file_type == '.vob':
                continue
            entry = {
                'file_type': file_type[1:].upper(),
                'file_size': get_file_size(info['file_size']),
            }
            if info['count'] > 1:
                entry['count'] = info['count']
            aggregated_info.append(entry)

    return aggregated_info


def generate_vob_summary(directory: str) -> str | None:
    total_size = 0
    has_ifo = False
    has_bup = False

    for root, _, files in os.walk(directory):
        if os.path.islink(root):
            continue
        for file in files:
            file_ext = os.path.splitext(file)[1].lower()
            file_path = os.path.join(root, file)
            if os.path.islink(file_path):
                continue
            try:
                file_size_bytes = os.path.getsize(file_path)
            except OSError:
                continue

            if file_ext == '.vob':
                total_size += file_size_bytes
            elif file_ext == '.ifo':
                has_ifo = True
            elif file_ext == '.bup':
                has_bup = True

    if total_size > 0:
        vob_label = "VOB (with smalls)" if (has_ifo or has_bup) else "VOB (no smalls)"
        return f"{vob_label} ({get_file_size(total_size)})"

    return None


def generate_media_summary(aggregated_info: list[dict], vob_summary: str | None) -> str:
    summary = []
    for info in aggregated_info:
        if 'count' in info:
            summary.append(f"{info['file_type']} x{info['count']} ({info['file_size']})")
        else:
            summary.append(f"{info['file_type']} ({info['file_size']})")

    if vob_summary:
        summary.append(vob_summary)

    return " | ".join(summary)


def process_directory(directory: str) -> str:
    media_info = evaluate_media_files(directory)
    vob_summary = generate_vob_summary(directory)
    return generate_media_summary(media_info, vob_summary)


def send_format(recording_data: list[dict], encora_id: str, media_summary: str) -> bool:
    """Send updated format string to Encora when local media differs from Encora metadata."""
    matching = next((item for item in recording_data if str(item['encora_id']) == str(encora_id)), None)
    if not matching:
        print(f"Skipping format update for {encora_id}: Recording not found in your collection.")
        return False

    if matching.get('my_format') == media_summary:
        return False

    if config.dont_override_encora_format and matching.get('my_format'):
        return False

    url = f"https://encora.it/api/collection/{encora_id}/format/{urllib.parse.quote_plus(media_summary)}".replace('+', '%20')

    try:
        with build_api_session({'Content-Type': 'application/json'}) as session:
            authenticated_request('POST', url, session=session, json={})
        return True
    except Exception as err:
        logger.warning(f"Error updating format for {encora_id}: {err}")
        if "500" in str(err):
            print(f"Server Error (500) updating format for {encora_id}. The recording might not be in your collection or the ID is invalid.")
        else:
            print(f"Error updating format for {encora_id}: {err}")
        return False
