import logging
import os
import re
from datetime import datetime

from modules.config import config
from modules.diff_utils import append_to_diff_file, are_functionally_identical

logger = logging.getLogger(__name__)


def strip_html_tags(text: str) -> str:
    """Remove HTML tags from a string."""
    return re.sub(re.compile('<.*?>'), '', text)


def format_date(date_str: str, day_known: bool = True, month_known: bool = True, date_variant: str | None = None) -> str:
    """Format date based on known day, month, and variant."""
    try:
        if 'T' in date_str:
            date_str = date_str.split('T')[0]
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')

        if not day_known and not month_known:
            formatted_date = date_obj.strftime('%Y')
        elif not day_known:
            formatted_date = date_obj.strftime('%B, %Y')
        else:
            formatted_date = date_obj.strftime('%B %d, %Y')

        if date_variant:
            formatted_date += f" ({date_variant})"

        return formatted_date
    except (ValueError, TypeError):
        return 'Unknown Date'


def generate_template(recording_data: dict) -> str:
    show = recording_data.get('show', 'Unknown Show')
    tour = recording_data.get('tour', 'Unknown Tour')
    amount_recorded = recording_data.get('metadata', {}).get('amount_recorded', 'Unknown').capitalize()
    date_info = recording_data.get('date', {})
    date_str = date_info.get('full_date', '')
    day_known = date_info.get('day_known', True)
    month_known = date_info.get('month_known', True)
    date_variant = date_info.get('date_variant', None)

    date = format_date(date_str, day_known, month_known, date_variant)
    master = recording_data.get('master', 'Unknown Master')
    media_type = recording_data.get('metadata', {}).get('media_type', 'Unknown Media Type').capitalize()

    if amount_recorded == "Complete":
        amount_recorded = ''

    cast_entries = recording_data.get('cast', [])
    cast_list = ', '.join(
        f"{entry['performer'].get('name', 'Unknown Performer')} "
        f"({entry.get('status', {}).get('abbreviation', '') if entry.get('status') else ''}"
        f"{' ' if entry.get('status') and entry.get('status').get('abbreviation', '') else ''}"
        f"{entry['character'].get('name', 'Unknown Role')})"
        for entry in cast_entries
        if entry.get('performer') and entry.get('character')
    )

    nft = recording_data.get('nft', {})
    nft_status = ''
    if nft.get('nft_forever', False):
        nft_status = "NFT Forever"
    elif nft.get('nft_date'):
        nft_status = f"NFT Until {format_date(nft['nft_date'])}"

    template = f"{show} - {tour}\n{date} - {master}\n"
    if amount_recorded:
        template += f"{amount_recorded} "

    template += (
        f"{media_type}\n\n"
        + (f"{nft_status}\n\n" if nft_status else "")
        + f"Cast:\n{cast_list}\n\n"
    )

    master_notes = recording_data.get('master_notes')
    if master_notes:
        master_notes = strip_html_tags(master_notes.strip())
        if master_notes:
            template += f"Master Notes:\n{master_notes}\n\n"

    notes = recording_data.get('notes')
    if notes:
        notes = strip_html_tags(notes.strip())
        if notes:
            template += f"Notes:\n{notes}\n"

    return template


def write_cast_file(path: str, content: str, encora_id: str) -> bool:
    cast_file_path = os.path.join(path, 'Cast.txt')
    if os.path.exists(cast_file_path):
        try:
            with open(cast_file_path, 'r', encoding='utf-8') as file:
                existing_content = file.read()
        except UnicodeDecodeError:
            with open(cast_file_path, 'r', encoding='latin-1') as file:
                existing_content = file.read()
            with open(cast_file_path, 'w', encoding='utf-8') as file:
                file.write(existing_content)

        if are_functionally_identical(content, existing_content):
            return False
        append_to_diff_file('cast_diffs.txt', encora_id, existing_content, content, cast_file_path)

    with open(cast_file_path, 'w', encoding='utf-8') as file:
        file.write(content)
    return True


def create_cast_files(encora_data: list[dict]) -> None:
    excluded_ids = config.excluded_ids
    skip_cast = config.exclude_cast_files
    updated_count = 0

    for entry in encora_data:
        path = entry['path']
        encora_id = str(entry['encora_id'])
        if skip_cast and encora_id in excluded_ids:
            continue

        try:
            template = generate_template(entry['recording_data'])
            if write_cast_file(path, template, encora_id):
                updated_count += 1
        except OSError as e:
            logger.warning(f"Failed updating Cast.txt in {path}: {e}")

    if updated_count > 0:
        print(f"Updated Cast.txt for {updated_count} recordings.")
    else:
        print("All local Cast.txt files are already up to date.")


def create_encora_id_files(encora_data: list[dict]) -> None:
    for entry in encora_data:
        path = entry['path']
        id_val = entry.get('recording_data', {}).get('id')
        if not id_val:
            continue

        encora_id = str(id_val)
        if not encora_id.isdigit():
            continue

        encora_id_file_path = os.path.join(path, f'.encora-{encora_id}')
        if not os.path.exists(encora_id_file_path):
            try:
                with open(encora_id_file_path, 'w', encoding='utf-8'):
                    pass
            except OSError as e:
                logger.warning(f"Failed creating {encora_id_file_path}: {e}")
