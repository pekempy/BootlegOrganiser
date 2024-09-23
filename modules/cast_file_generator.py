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

def generate_template(api_response):
    show = api_response.get('show', 'Unknown Show')
    tour = api_response.get('tour', 'Unknown Tour')
    amount_recorded = api_response.get('metadata', {}).get('amount_recorded', 'Unknown').capitalize()
    date_info = api_response.get('date', {})
    date_str = date_info.get('full_date', '')
    day_known = date_info.get('day_known', True)
    month_known = date_info.get('month_known', True)
    date_variant = date_info.get('date_variant', None)

    date = format_date(date_str, day_known, month_known, date_variant)
    master = api_response.get('master', 'Unknown Master')
    media_type = api_response.get('metadata', {}).get('media_type', 'Unknown Media Type').capitalize()

    if amount_recorded == "Complete":
        amount_recorded = ''

    # Build cast list with safe checks for missing data and include cast status
    cast_entries = api_response.get('cast', [])
    cast_list = ', '.join(
        f"{entry['performer'].get('name', 'Unknown Performer')} ({entry.get('cast_status', '')}{' ' if entry.get('cast_status') else ''}{entry['character'].get('name', 'Unknown Role')})"
        for entry in cast_entries
        if entry.get('performer') and entry.get('character')
    )

    # Handle NFT status
    nft = api_response.get('nft', {})
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
        f"{api_response.get('master_notes', 'No notes available.')} \n\n"
        f"Notes:\n"
        f"{api_response.get('notes', 'No notes available.')} \n"
    )

    return template

def write_cast_file(path, content):
    cast_file_path = os.path.join(path, 'Cast.txt')    
    if os.path.exists(cast_file_path):
        os.remove(cast_file_path)
    with open(cast_file_path, 'w', encoding='utf-8') as file:
        file.write(content)

def create_cast_files(encora_data):
    for entry in encora_data:
        path = entry['path']
        api_response = entry['api_response']

        # Generate template
        template = generate_template(api_response)

        # Write to Cast.txt
        write_cast_file(path, template)

def create_encora_id_files(encora_data):
    for entry in encora_data:
        path = entry['path']
        api_response = entry['api_response']
        encora_id = str(api_response.get('id', ''))

        # Create the .encora-ID file
        encora_id_file_path = os.path.join(path, f'.encora-{encora_id}')
        with open(encora_id_file_path, 'w', encoding='utf-8'):
            pass  # Create an empty file
    