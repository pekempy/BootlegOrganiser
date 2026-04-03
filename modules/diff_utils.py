import os
import difflib
import re

def get_diff_file_path(filename):
    """
    Returns the absolute path for a diff file in the project's root directory.
    """
    # Root directory is the parent of the modules directory
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root_dir, filename)

def clear_diff_files():
    """
    Clears the diff and log files at the start of a run.
    """
    for filename in ['cast_diffs.txt', 'subtitle_diffs.txt', 'missing_smalls.txt']:
        file_path = get_diff_file_path(filename)
        if os.path.exists(file_path):
            os.remove(file_path)

def log_missing_smalls(recording_id, show, tour, date, master):
    """
    Logs a recording with missing smalls to missing_smalls.txt.
    """
    file_path = get_diff_file_path('missing_smalls.txt')
    header_needed = not os.path.exists(file_path)
    
    with open(file_path, 'a', encoding='utf-8') as f:
        if header_needed:
            f.write(f"{'Recording ID':<15} | {'Show':<30} | {'Tour':<20} | {'Date':<20} | {'Master':<20}\n")
            f.write(f"{'-'*15}-+-{'-'*30}-+-{'-'*20}-+-{'-'*20}-+-{'-'*20}\n")
        
        f.write(f"{str(recording_id):<15} | {str(show):<30} | {str(tour):<20} | {str(date):<20} | {str(master):<20}\n")

def are_functionally_identical(content1, content2):
    """
    Checks if two strings (or bytes) are functionally identical,
    ignoring line endings, trailing whitespace, and BOM.
    """
    if isinstance(content1, bytes):
        try:
            content1 = content1.decode('utf-8-sig')
        except UnicodeDecodeError:
            content1 = content1.decode('utf-8', errors='ignore')
    if isinstance(content2, bytes):
        try:
            content2 = content2.decode('utf-8-sig')
        except UnicodeDecodeError:
            content2 = content2.decode('utf-8', errors='ignore')

    def clean_content(content):
        # Normalize line endings and strip whitespace
        lines = [line.strip() for line in content.splitlines()]
        
        # Filter out Aegisub Project Garbage and empty lines
        cleaned_lines = []
        skip_section = False
        for line in lines:
            # Skip Aegisub garbage
            if line == '[Aegisub Project Garbage]':
                skip_section = True
                continue
            if skip_section and line.startswith('['):
                skip_section = False
            
            if skip_section:
                continue

            # Ignore empty lines entirely for comparison
            if not line:
                continue
            
            # Normalize common time markers (e.g. 00:00:00.000 -> 00:00:00.00)
            # This handles cases where one source has more decimal precision
            line = re.sub(r'(\d+:\d+:\d+)\.(\d{2})\d*', r'\1.\2', line)
            line = re.sub(r'(\d+:\d+)\.(\d{2})\d*', r'\1.\2', line)
            
            # Normalize all internal whitespace (collapse multiple spaces, tabs, non-breaking spaces)
            line = ' '.join(line.split())
            
            # Remove minor punctuation differences that often vary between sources
            # such as spaces after commas in time-markers or brackets
            line = line.replace(', ', ',').replace(' ,', ',')
            
            cleaned_lines.append(line)
        
        return cleaned_lines

    return clean_content(content1) == clean_content(content2)

def append_to_diff_file(diff_file_name, recording_id, old_content, new_content, label):
    """
    Appends a unified diff between old_content and new_content to a diff file.
    Only records changes that are not just whitespace or line ending differences.
    """
    diff_file_path = get_diff_file_path(diff_file_name)
    
    # Ensure contents are strings
    if isinstance(old_content, bytes):
        try:
            old_content = old_content.decode('utf-8')
        except UnicodeDecodeError:
            old_content = repr(old_content)
    if isinstance(new_content, bytes):
        try:
            new_content = new_content.decode('utf-8')
        except UnicodeDecodeError:
            new_content = repr(new_content)

    # Normalize by stripping trailing whitespace and ignoring line endings
    # We split into lines and then strip EACH line.
    old_lines = [line.rstrip() for line in old_content.splitlines()]
    new_lines = [line.rstrip() for line in new_content.splitlines()]
    
    # If they are identical after normalization, they are effectively the same for the user
    if old_lines == new_lines:
        return

    # Generate the diff with normalized lines
    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile='Old',
        tofile='New',
        lineterm=''
    )
    
    diff_text = list(diff)
    if diff_text:
        with open(diff_file_path, 'a', encoding='utf-8') as f:
            f.write(f"{'='*60}\n")
            f.write(f"Recording ID: {recording_id}\n")
            f.write(f"File: {label}\n")
            f.write(f"{'-'*60}\n")
            for line in diff_text:
                f.write(line + "\n")
            f.write("\n")
