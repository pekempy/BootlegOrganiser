import os
from datetime import datetime

def format_date(date_str, day_known=True, month_known=True, date_variant=None):
    """Format date based on known day, month, and variant."""
    try:
        if 'T' in date_str:
            date_str = date_str.split('T')[0]
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')

        if not day_known and not month_known:
            formatted_date = date_obj.strftime('%Y')  # Only Year
        elif not day_known:
            formatted_date = date_obj.strftime('%B, %Y')  # Month and Year
        else:
            formatted_date = date_obj.strftime('%B %d, %Y')  # Full Date

        if date_variant:
            formatted_date += f" ({date_variant})"

        return formatted_date
    except ValueError:
        return 'Unknown Date'

def generate_template(recording_data):
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

    # Build cast list with safe checks for missing data and include cast status
    cast_entries = recording_data.get('cast', [])
    cast_list = ', '.join(
        f"{entry['performer'].get('name', 'Unknown Performer')} ({entry.get('cast_status', '')}{' ' if entry.get('cast_status') else ''}{entry['character'].get('name', 'Unknown Role')})"
        for entry in cast_entries
        if entry.get('performer') and entry.get('character')
    )

    # Handle NFT status
    nft = recording_data.get('nft', {})
    nft_status = ''
    if nft.get('nft_forever', False):
        nft_status = "NFT Forever"
    elif nft.get('nft_date'):
        nft_status = f"NFT Until {format_date(nft['nft_date'])}"
    
    # Build the template
    template = (
        f"{show} - {tour}\n"
        f"{date} - {master}\n"
    )
    if amount_recorded:
        template += f"{amount_recorded} "

    template +=(
        f"{media_type}\n\n"
        + (f"{nft_status}\n\n" if nft_status else "") +
        f"Cast:\n"
        f"{cast_list}\n\n"
        f"Master Notes:\n"
        f"{recording_data.get('master_notes', 'No notes available.')} \n\n"
        f"Notes:\n"
        f"{recording_data.get('notes', 'No notes available.')} \n"
    )

    return template

def write_cast_file(path, content):
    cast_file_path = os.path.join(path, 'Cast.txt')
    # Check if the file exists and read its content
    if os.path.exists(cast_file_path):
        with open(cast_file_path, 'r', encoding='utf-8') as file:
            existing_content = file.read()
        # Only proceed if the new content is different from the existing content
        if content == existing_content:
            return
    with open(cast_file_path, 'w', encoding='utf-8') as file:
        file.write(content)

def create_cast_files(encora_data):
    for entry in encora_data:
        path = entry['path']
        recording_data = entry['recording_data']
        # Generate template
        template = generate_template(recording_data)
        # Write to Cast.txt
        write_cast_file(path, template)

def create_encora_id_files(encora_data):
    for entry in encora_data:
        path = entry['path']
        recording_data = entry['recording_data']
        encora_id = str(recording_data.get('id', ''))
        # Create the .encora-ID file
        encora_id_file_path = os.path.join(path, f'.encora-{encora_id}')
        with open(encora_id_file_path, 'w', encoding='utf-8'):
            pass  
    