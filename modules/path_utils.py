import os
import re
import unicodedata

ENCORA_ID_CONTAINER_RE = re.compile(r'[\{\[\(]e-(\d+)[\}\]\)]')
ENCORA_ID_FALLBACK_RE = re.compile(r'e-(\d+)')
ENCORA_ID_FILE_RE = re.compile(r'^\.encora-(\d+)$')


def has_encora_id(name: str) -> bool:
    """Return True if folder name contains an Encora ID container tag like {e-123}."""
    return bool(ENCORA_ID_CONTAINER_RE.search(name))


def extract_encora_id(dir_name: str, folder_path: str | None = None) -> str | None:
    """Extract numeric Encora ID from a folder name or fallback .encora-NNN marker file."""
    if match := ENCORA_ID_CONTAINER_RE.search(dir_name):
        return match.group(1)
    if match := ENCORA_ID_FALLBACK_RE.search(dir_name):
        return match.group(1)

    if folder_path:
        try:
            for file_name in os.listdir(folder_path):
                if file_name.startswith('.encora-'):
                    id_match = ENCORA_ID_FILE_RE.match(file_name)
                    if id_match:
                        return id_match.group(1)
        except (PermissionError, FileNotFoundError, OSError):
            pass

    return None


def is_same_path(a: str, b: str) -> bool:
    """Return True if a and b refer to the same physical file or directory (case/NFD-safe)."""
    try:
        if os.path.lexists(a) and os.path.lexists(b):
            return os.path.samefile(a, b)
    except OSError:
        pass
    return unicodedata.normalize('NFC', os.path.abspath(a)) == unicodedata.normalize('NFC', os.path.abspath(b))


def exact_path_matches(a: str, b: str) -> bool:
    """Return True if a and b match character-for-character after NFC normalization."""
    return unicodedata.normalize('NFC', os.path.normpath(a)) == unicodedata.normalize('NFC', os.path.normpath(b))


def is_within(path: str, ancestor: str) -> bool:
    """Return True if path resolves to ancestor or inside ancestor."""
    try:
        rp = os.path.realpath(path)
        ra = os.path.realpath(ancestor)
        return rp == ra or rp.startswith(ra + os.sep)
    except OSError:
        return False


def unique_path(dst: str) -> str:
    """Return a non-colliding destination path if dst already exists."""
    if not os.path.lexists(dst):
        return dst
    parent = os.path.dirname(dst)
    name = os.path.basename(dst)
    stem, ext = (name, '') if os.path.isdir(dst) else os.path.splitext(name)
    counter = 1
    while True:
        candidate = os.path.join(parent, f"{stem} ({counter}){ext}")
        if not os.path.lexists(candidate):
            return candidate
        counter += 1


def case_safe_rename(src: str, dst: str) -> None:
    """Rename src -> dst safely when both refer to the same physical inode (case/NFD change)."""
    if exact_path_matches(src, dst):
        return
    parent = os.path.dirname(dst)
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)
    tmp = f"{src}.__tmp_rename__"
    counter = 0
    while os.path.lexists(tmp):
        counter += 1
        tmp = f"{src}.__tmp_rename_{counter}__"
    os.rename(src, tmp)
    os.rename(tmp, dst)


def walk_library_dirs(main_directory: str, topdown: bool = True):
    """
    Walk main_directory while skipping hidden directories (.), organiser
    control folders (!non-encora, !unmatched, !danger-zone, !processing), and symlinks.
    Prunes properly in both topdown=True and topdown=False modes.
    """
    collected = []
    for root, dirs, files in os.walk(main_directory, topdown=True):
        dirs[:] = [
            d for d in dirs
            if not d.startswith('.')
            and not d.startswith('!')
            and not os.path.islink(os.path.join(root, d))
        ]
        if topdown:
            yield root, dirs, files
        else:
            collected.append((root, list(dirs), files))

    if not topdown:
        for item in reversed(collected):
            yield item
