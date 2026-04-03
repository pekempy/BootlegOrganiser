import os
import difflib

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

def append_to_diff_file(diff_file_name, recording_id, old_content, new_content, label):
    """
    Appends a unified diff between old_content and new_content to a diff file.
    
    Args:
        diff_file_name (str): The filename of the diff file in the root directory.
        recording_id (str): The Encora recording ID.
        old_content (str/bytes): The original content of the file.
        new_content (str/bytes): The updated content of the file.
        label (str): A label for the file (e.g., its path relative to root or show name).
    """
    diff_file_path = get_diff_file_path(diff_file_name)
    
    # Ensure contents are safe for splitlines
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

    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)
    
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
            f.writelines(diff_text)
            f.write("\n\n")
