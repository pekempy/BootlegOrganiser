import os
import re

AUDIO_EXTS = {'.mp3', '.m4a', '.flac', '.wav', '.aiff', '.aif', '.m4b', '.alac', '.aac', '.ogg', '.wma'}
VIDEO_EXTS = {'.mp4', '.mkv', '.mov', '.avi', '.ts', '.wmv', '.m4v', '.divx', '.mpg', '.mpeg', '.m2v', '.flv', '.rmvb'}
MTS_EXTS = {'.mts', '.m2ts', '.m2t'}
VOB_EXTS = {'.vob', '.ifo', '.bup'}
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic', '.bmp', '.tiff', '.tif'}
INFO_EXTS = {'.txt', '.rtf', '.nfo', '.odt'}
SUB_EXTS = {'.srt', '.ass', '.ssa', '.vtt', '.sbv', '.sub'}
JUNK_NAMES = {'.ds_store', 'thumbs.db', 'desktop.ini'}
JUNK_EXTS = {'.tmp', '.copytemp'}
ARCHIVE_EXTS = {'.zip', '.rar', '.7z', '.gz', '.tar', '.bz2'}
METADATA_NAMES = {'cast.txt', 'checksums.b2', '.checksums.cache'}

_ACT_MAP = {
    'act 1': 'Act 1', 'act1': 'Act 1',
    'act 2': 'Act 2', 'act2': 'Act 2',
    'act 3': 'Act 3', 'act3': 'Act 3',
    'act 4': 'Act 4', 'act4': 'Act 4',
    'act i': 'Act 1', 'act ii': 'Act 2', 'act iii': 'Act 3', 'act iv': 'Act 4',
    'act one': 'Act 1', 'act two': 'Act 2', 'act three': 'Act 3',
    'disc 1': 'Act 1', 'disc 2': 'Act 2', 'disc 3': 'Act 3',
    'disk 1': 'Act 1', 'disk 2': 'Act 2',
    'disc one': 'Act 1', 'disc two': 'Act 2',
}
_VINYL = {'side a', 'side b', 'side 1', 'side 2', 'side one', 'side two'}
_DEVICE_KW = {'apple watch', 'iphone', 'ipad', 'dolby', 'android', 'samsung', 'pixel'}
_ARTWORK_RE = re.compile(
    r'^(art|artwork|album[ _\-]?art(small)?|album[ _\-]?cover|cover|poster|flyer|logo|thumbnail)(\.\w+)?$',
    re.IGNORECASE,
)


def normalise_act(name: str) -> str | None:
    low = name.lower().strip()
    if low in _VINYL:
        return name
    return _ACT_MAP.get(low)


def is_device_folder(name: str) -> bool:
    low = name.lower()
    return any(k in low for k in _DEVICE_KW)


def is_tracked_folder(name: str) -> bool:
    low = name.lower()
    return ('tracked' in low and 'untracked' not in low) or low == 'parts - tracked'


def is_untracked_folder(name: str) -> bool:
    low = name.lower()
    return 'untracked' in low or low in ('parts', 'parts/')


def is_metadata(filename: str) -> bool:
    low = filename.lower()
    if low in METADATA_NAMES:
        return True
    return bool(re.match(r'^\.encora-\d+$', low))


def classify_image(filename: str) -> str:
    """Return 'delete' (explicit album artwork only) or 'photos' (cast/prod/numbered photo)."""
    if _ARTWORK_RE.match(os.path.splitext(filename)[0]):
        return 'delete'
    return 'photos'


def detect_tracked_status(files: list) -> str | None:
    """Infer 't' (tracked), 'u' (untracked), or None (ambiguous) from audio filenames."""
    track_num = re.compile(r'^\d{1,3}[\s.\-_]')
    act_file = re.compile(r'^(act|side)\s*[1-9ivxab]\b', re.IGNORECASE)

    names = [fp.name for fp in files]
    numbered = sum(1 for n in names if track_num.match(n))
    act_files = sum(1 for n in names if act_file.match(os.path.splitext(n)[0]))
    total = len(names)

    if total > 3 and numbered / total >= 0.7:
        return 't'
    if total <= 4 or act_files >= total * 0.7:
        return 'u'
    return None
