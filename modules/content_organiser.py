"""
content_organiser.py — normalises the internal structure of each release folder {e-XXXXX}.

Rules (all folder names configurable via .env / GUI):
  Audio:
    - Single untracked format  → Untracked/[Act N/]files
    - Multiple untracked fmts  → Untracked (MP3)/[Act N/]files  +  Untracked (WAV)/...
    - Tracked files            → Tracked/[Act N/]files  (or Tracked (MP3)/ if multi-format)
    - Device sub-groups        → Untracked/Apple Watch/[Act N/]files  etc.
    - Side A / Side B          → kept as-is (vinyl)
    - Parts/, act folders, misc named folders → mapped to Untracked/

  Video:
    - Single video file (.mp4/.mkv/.mov/.avi/.ts/.m2ts) → file at release root
    - Multiple video segments  → Parts/ folder
    - .MTS files               → Parts/ folder
    - VIDEO_TS/ folder         → contents moved into VOBs/ (or VOBs (no smalls)/)
    - .vob/.ifo/.bup           → VOBs/[Act N/]  or  VOBs (no smalls)/[Act N/]

  Extra files:
    - .DS_Store / ._. junk, .exe, .zip → delete
    - Duplicate / wrongly-named Cast.txt (not 'Cast.txt') → rename to Cast.txt
    - Cast.docx → delete
    - Album artwork images → delete
    - Numbered screenshots alongside video → delete
    - Other images (.jpg/.png/.heic etc.) → Photos/ subfolder
    - PDFs → Programme/ subfolder
    - .srt subtitles, .txt/.rtf info files → keep at root
    - Metadata (Cast.txt, Checksums.b2, .checksums.cache, .encora-NNN)
      found inside subfolders → move to release root

  Unknown patterns:
    - UNKNOWN_PATTERN_ACTION = 'prompt' → ask user interactively (CLI input)
    - UNKNOWN_PATTERN_ACTION = 'log'    → append to unrecognised_patterns.txt
    - UNKNOWN_PATTERN_ACTION = 'skip'   → leave untouched, print warning
"""

import os
import re
import sys
import shutil
import logging
from pathlib import Path
from modules.config import config

logger = logging.getLogger(__name__)

# ── File-type sets ─────────────────────────────────────────────────────────────

AUDIO_EXTS  = {'.mp3', '.m4a', '.flac', '.wav', '.aiff', '.aif', '.m4b', '.alac', '.aac', '.ogg', '.wma'}
VIDEO_EXTS  = {'.mp4', '.mkv', '.mov', '.avi', '.ts', '.wmv', '.m4v', '.divx', '.mpg', '.mpeg', '.m2v', '.flv', '.rmvb'}
MTS_EXTS    = {'.mts', '.m2ts', '.m2t'}
VOB_EXTS    = {'.vob', '.ifo', '.bup'}
IMAGE_EXTS  = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic', '.bmp', '.tiff', '.tif'}
INFO_EXTS   = {'.txt', '.rtf', '.nfo', '.odt'}
SUB_EXTS    = {'.srt', '.ass', '.ssa', '.vtt', '.sbv', '.sub'}
JUNK_NAMES  = {'.ds_store', 'thumbs.db', 'desktop.ini'}
JUNK_EXTS   = {'.exe', '.tmp', '.copytemp', '.mhtml', '.xspf', '.gdoc', '.gsheet', '.gslides', '.md5', '.sfv', '.docx', '.doc'}
ARCHIVE_EXTS = {'.zip', '.rar', '.7z', '.gz', '.tar', '.bz2'}

# Metadata always lives at release root — never touched inside subfolders during scan
METADATA_NAMES = {'cast.txt', 'checksums.b2', '.checksums.cache'}

# ── Act name normalisation ──────────────────────────────────────────────────────

_ACT_MAP = {
    # Arabic
    'act 1': 'Act 1', 'act1': 'Act 1',
    'act 2': 'Act 2', 'act2': 'Act 2',
    'act 3': 'Act 3', 'act3': 'Act 3',
    'act 4': 'Act 4', 'act4': 'Act 4',
    # Roman
    'act i': 'Act 1', 'act ii': 'Act 2', 'act iii': 'Act 3', 'act iv': 'Act 4',
    # Spelled
    'act one': 'Act 1', 'act two': 'Act 2', 'act three': 'Act 3',
    # Uppercase variants
    'act 1': 'Act 1', 'act 2': 'Act 2',  # already covered; belt-and-suspenders
    # Disc (non-vinyl)
    'disc 1': 'Act 1', 'disc 2': 'Act 2', 'disc 3': 'Act 3',
    'disk 1': 'Act 1', 'disk 2': 'Act 2',
    'disc one': 'Act 1', 'disc two': 'Act 2',
}
# Vinyl sides — kept verbatim
_VINYL = {'side a', 'side b', 'side 1', 'side 2', 'side one', 'side two'}

# Device folder keywords
_DEVICE_KW = {'apple watch', 'iphone', 'ipad', 'dolby', 'android', 'samsung', 'pixel'}


def _normalise_act(name: str) -> str | None:
    """Return canonical 'Act N' / 'Side X' for known act folder names, else None."""
    low = name.lower().strip()
    if low in _VINYL:
        return name  # preserve original capitalisation for vinyl
    return _ACT_MAP.get(low)


def _is_device_folder(name: str) -> bool:
    low = name.lower()
    return any(k in low for k in _DEVICE_KW)


def _is_tracked_folder(name: str) -> bool:
    low = name.lower()
    return ('tracked' in low and 'untracked' not in low) or low == 'parts - tracked'


def _is_untracked_folder(name: str) -> bool:
    low = name.lower()
    return 'untracked' in low or low in ('parts', 'parts/')


def _is_metadata(filename: str) -> bool:
    low = filename.lower()
    if low in METADATA_NAMES:
        return True
    if re.match(r'^\.encora-\d+$', low):
        return True
    return False


# ── Image classifier ────────────────────────────────────────────────────────────

_ARTWORK_RE = re.compile(
    r'^(art|artwork|album[ _\-]?art(small)?|album[ _\-]?cover|cover|poster|flyer|logo|thumbnail)(\.\w+)?$',
    re.IGNORECASE,
)
_SCREENSHOT_RE = re.compile(r'^\d{1,3}\.(png|jpg|jpeg)$', re.IGNORECASE)


def _classify_image(filename: str) -> str:
    """Return 'delete' (artwork/screenshot) or 'photos' (cast/prod photo)."""
    if _SCREENSHOT_RE.match(filename):
        return 'delete'
    if _ARTWORK_RE.match(os.path.splitext(filename)[0]):
        return 'delete'
    # Timestamp-style filenames (phone photos) → Photos/
    if re.match(r'^\d{8}[_\-]\d+', filename):
        return 'photos'
    # .heic = Apple phone format → Photos/
    if filename.lower().endswith('.heic'):
        return 'photos'
    # Default: Photos/ (safer than deleting unknown images)
    return 'photos'


# ── ContentOrganiser ────────────────────────────────────────────────────────────

class ContentOrganiser:
    """
    Analyses one release folder and produces a set of move/delete actions,
    then executes them.
    """

    def __init__(self, release_path: str, interactive: bool = True):
        self.release_path = Path(release_path)
        self.interactive   = interactive
        self.unknown_action = config.unknown_pattern_action  # 'prompt'|'skip'|'log'
        # Pending operations: ('move', src, dst) | ('delete', src) | ('rmdir', path)
        self._ops: list[tuple] = []
        self._unknowns: list[Path] = []
        self._loose_audio: list[Path] = []  # audio at root — track status unknown

    # ── Public entry ───────────────────────────────────────────────────────────

    def run(self):
        inv = self._scan()

        self._fix_metadata_locations()
        self._clean_junk(inv['junk'])
        self._handle_info_files(inv['info'])
        self._handle_images(inv['images'])
        self._handle_pdfs(inv['pdfs'])
        self._handle_archives(inv['archives'])

        if inv['audio']:
            self._organise_audio(inv['audio'])

        if self._loose_audio:
            self._handle_loose_audio()

        has_video = inv['video'] or inv['mts'] or inv['vobs']
        if has_video:
            self._organise_video(inv['video'], inv['mts'], inv['vobs'])

        if self._unknowns:
            self._handle_unknowns()

        self._execute()
        self._clean_empty_subdirs()

    # ── Scanning ───────────────────────────────────────────────────────────────

    def _scan(self) -> dict:
        inv: dict[str, list] = {
            'audio':    [],   # (Path, folder_parts_tuple)
            'video':    [],   # (Path, folder_parts_tuple)
            'mts':      [],   # (Path, folder_parts_tuple)
            'vobs':     [],   # (Path, folder_parts_tuple)
            'images':   [],   # Path
            'pdfs':     [],   # Path
            'archives': [],   # Path
            'info':     [],   # (kind, Path)  kind ∈ 'keep'|'rename_cast'
            'junk':     [],   # Path
        }

        for root, dirs, files in os.walk(self.release_path):
            rel  = Path(root).relative_to(self.release_path)
            parts = rel.parts  # () at root

            # Skip hidden dirs (e.g. __pycache__)
            dirs[:] = [d for d in dirs if not d.startswith('.')]

            for fn in files:
                fp  = Path(root) / fn
                low = fn.lower()
                ext = Path(fn).suffix.lower()

                if _is_metadata(fn):
                    continue  # handled separately in _fix_metadata_locations

                if (low in JUNK_NAMES or low.startswith('._.') or ext in JUNK_EXTS
                        or re.match(r'^cast\.txt\.conflict', low)):
                    inv['junk'].append(fp)
                    continue

                if ext in SUB_EXTS:
                    continue  # subtitles: leave at root

                if ext in AUDIO_EXTS:
                    inv['audio'].append((fp, parts))
                    continue

                if ext in VIDEO_EXTS:
                    inv['video'].append((fp, parts))
                    continue

                if ext in MTS_EXTS:
                    inv['mts'].append((fp, parts))
                    continue

                if ext in VOB_EXTS:
                    inv['vobs'].append((fp, parts))
                    continue

                if ext in IMAGE_EXTS:
                    inv['images'].append(fp)
                    continue

                if ext == '.pdf':
                    inv['pdfs'].append(fp)
                    continue

                if ext in ARCHIVE_EXTS:
                    inv['archives'].append(fp)
                    continue

                if ext in INFO_EXTS:
                    # Wrongly-named cast file?
                    if 'cast' in low and low != 'cast.txt':
                        inv['info'].append(('rename_cast', fp))
                    else:
                        inv['info'].append(('keep', fp))
                    continue

                # Anything else at root is unknown
                if not parts:
                    self._unknowns.append(fp)

        return inv

    # ── Metadata relocation ────────────────────────────────────────────────────

    def _fix_metadata_locations(self):
        """Move Cast.txt / Checksums.b2 / .encora-NNN found inside subfolders to release root."""
        for root, _, files in os.walk(self.release_path):
            if Path(root) == self.release_path:
                continue
            for fn in files:
                if _is_metadata(fn):
                    src = Path(root) / fn
                    dst = self.release_path / fn
                    if not dst.exists():
                        self._ops.append(('move', src, dst))

    # ── Junk & info ───────────────────────────────────────────────────────────

    def _clean_junk(self, junk: list[Path]):
        for f in junk:
            self._ops.append(('delete', f))

    def _handle_info_files(self, info: list[tuple]):
        """Rename wrongly-named cast files; leave other info files at root."""
        cast_root = self.release_path / 'Cast.txt'
        for kind, fp in info:
            if kind == 'rename_cast' and not cast_root.exists():
                self._ops.append(('move', fp, cast_root))
            elif kind == 'rename_cast':
                # A real Cast.txt already exists — delete the duplicate
                self._ops.append(('delete', fp))
            # 'keep' → do nothing

    # ── Images ────────────────────────────────────────────────────────────────

    def _handle_images(self, images: list[Path]):
        if not config.delete_artwork and not config.move_photos:
            return
        photos_dir = self.release_path / config.photos_folder_name
        for img in images:
            action = _classify_image(img.name)
            if action == 'delete' and config.delete_artwork:
                self._ops.append(('delete', img))
            elif action == 'photos' and config.move_photos:
                self._ops.append(('move', img, photos_dir / img.name))

    # ── PDFs ──────────────────────────────────────────────────────────────────

    def _handle_pdfs(self, pdfs: list[Path]):
        if not pdfs or not config.move_programmes:
            return
        prog_dir = self.release_path / config.programme_folder_name
        for pdf in pdfs:
            self._ops.append(('move', pdf, prog_dir / pdf.name))

    def _handle_archives(self, archives: list[Path]):
        if not archives or not config.move_archives:
            return
        archive_dir = self.release_path / config.archive_folder_name
        for arc in archives:
            self._ops.append(('move', arc, archive_dir / arc.name))

    # ── Audio ─────────────────────────────────────────────────────────────────

    def _organise_audio(self, audio: list[tuple]):
        """
        Normalise audio files that are already in a named subfolder.

        Files sitting loose at the release root (parts == ()) are left untouched
        because we cannot determine whether they are tracked or untracked without
        user input — guessing wrong would be misleading.

        Files in a recognised subfolder (Parts/, tracked/, untracked/, Act 1/,
        device folders, etc.) are moved into the canonical structure.
        """
        # ── First pass: classify; skip loose root files ────────────────────────
        classified = []  # (tracked, ext, act, device, filepath)

        for fp, parts in audio:
            # Loose at release root — can't infer tracked status, handle separately
            if not parts:
                self._loose_audio.append(fp)
                continue

            tracked = 'untracked'
            act     = None
            device  = None

            for part in parts:
                if _is_tracked_folder(part):
                    tracked = 'tracked'
                elif _is_untracked_folder(part):
                    tracked = 'untracked'

                a = _normalise_act(part)
                if a:
                    act = a

                if _is_device_folder(part) and device is None:
                    device = part  # preserve original capitalisation

            ext = fp.suffix.lower()
            classified.append((tracked, ext, act, device, fp))

        if not classified:
            return

        # ── Count formats per status to decide suffix ──────────────────────────
        untracked_exts  = {ext for ts, ext, _, _, _ in classified if ts == 'untracked'}
        tracked_exts    = {ext for ts, ext, _, _, _ in classified if ts == 'tracked'}
        multi_untracked = len(untracked_exts) > 1
        multi_tracked   = len(tracked_exts)   > 1

        def _base(status: str, ext: str) -> str:
            if status == 'tracked':
                name = config.tracked_folder_name
                return f"{name} ({ext[1:].upper()})" if multi_tracked else name
            else:
                name = config.untracked_folder_name
                return f"{name} ({ext[1:].upper()})" if multi_untracked else name

        # ── Second pass: queue moves ───────────────────────────────────────────
        for tracked, ext, act, device, fp in classified:
            base = _base(tracked, ext)

            if device:
                dir_path = self.release_path / base / device / (act or '')
            elif act:
                dir_path = self.release_path / base / act
            else:
                dir_path = self.release_path / base

            dst = dir_path / fp.name
            if fp.resolve() != dst.resolve():
                self._ops.append(('move', fp, dst))

    # ── Video ─────────────────────────────────────────────────────────────────

    def _organise_video(
        self,
        video: list[tuple],
        mts:   list[tuple],
        vobs:  list[tuple],
    ):
        # VIDEO_TS → VOBs/
        vts = self.release_path / 'VIDEO_TS'
        if vts.exists() and vts.is_dir():
            self._flatten_video_ts(vts)

        # .vob/.ifo/.bup
        if vobs:
            self._organise_vobs(vobs)

        # .MTS → Parts/
        if mts:
            parts_dir = self.release_path / config.parts_folder_name
            for fp, _ in mts:
                dst = parts_dir / fp.name
                if fp.resolve() != dst.resolve():
                    self._ops.append(('move', fp, dst))

        # Regular video files
        if video:
            self._organise_video_files(video)

    def _organise_video_files(self, video: list[tuple]):
        """Single file → root.  Multiple files → Parts/."""
        # Filter: only files not already in a VOBs/ or Parts/ context
        plain = [(fp, pts) for fp, pts in video
                 if not any(p.lower() in ('parts', 'video_ts') or
                            p.lower().startswith('vobs') for p in pts)]

        if not plain:
            return

        if len(plain) == 1:
            fp, parts = plain[0]
            if parts:  # not already at root
                dst = self.release_path / fp.name
                if fp.resolve() != dst.resolve():
                    self._ops.append(('move', fp, dst))
        else:
            parts_dir = self.release_path / config.parts_folder_name
            for fp, _ in plain:
                dst = parts_dir / fp.name
                if fp.resolve() != dst.resolve():
                    self._ops.append(('move', fp, dst))

    def _organise_vobs(self, vobs: list[tuple]):
        has_smalls = any(fp.suffix.lower() in {'.ifo', '.bup'} for fp, _ in vobs)
        base = config.vobs_folder_name
        if not has_smalls:
            base = f"{base} (no smalls)"

        # Detect act structure from existing folder names
        for fp, parts in vobs:
            act = None
            for part in parts:
                a = _normalise_act(part)
                if a:
                    act = a
                    break

            dst_dir = (self.release_path / base / act) if act else (self.release_path / base)
            dst = dst_dir / fp.name
            if fp.resolve() != dst.resolve():
                self._ops.append(('move', fp, dst))

    def _flatten_video_ts(self, vts_dir: Path):
        """Move VIDEO_TS/* into VOBs/ or VOBs (no smalls)/."""
        children = [f for f in vts_dir.iterdir() if f.is_file()]
        has_smalls = any(f.suffix.lower() in {'.ifo', '.bup'} for f in children)
        base = config.vobs_folder_name + ('' if has_smalls else ' (no smalls)')
        dst_dir = self.release_path / base
        for f in children:
            self._ops.append(('move', f, dst_dir / f.name))
        self._ops.append(('rmdir', vts_dir))

    # ── Unknown patterns ───────────────────────────────────────────────────────

    def _handle_unknowns(self):
        action = self.unknown_action

        if action == 'skip':
            print(f"  ⚠ Skipping {len(self._unknowns)} unrecognised file(s) in {self.release_path.name}")
            return

        if action == 'log':
            with open('unrecognised_patterns.txt', 'a', encoding='utf-8') as fh:
                for fp in self._unknowns:
                    fh.write(f"{fp}\n")
            return

        # 'prompt' — but only if we actually have a TTY
        has_tty = self.interactive and sys.stdin.isatty()
        if not has_tty:
            # No TTY (launched from GUI or piped) → fall back to log
            with open('unrecognised_patterns.txt', 'a', encoding='utf-8') as fh:
                for fp in self._unknowns:
                    fh.write(f"{fp}\n")
            return

        print(f"\n⚠  Unrecognised file(s) in: {self.release_path}")
        for fp in self._unknowns:
            print(f"   {fp.relative_to(self.release_path)}")

        print("\nOptions:")
        print("  [s] Skip — leave as-is")
        print("  [l] Log  — record to unrecognised_patterns.txt and skip")
        print("  [f] Enter a subfolder name to move them into")
        choice = input("Choice [s/l/f]: ").strip().lower()

        if choice == 'l':
            with open('unrecognised_patterns.txt', 'a', encoding='utf-8') as fh:
                for fp in self._unknowns:
                    fh.write(f"{fp}\n")
        elif choice == 'f':
            folder = input("Subfolder name: ").strip()
            if folder:
                dst_dir = self.release_path / folder
                for fp in self._unknowns:
                    self._ops.append(('move', fp, dst_dir / fp.name))
        # 's' → do nothing

    # ── Tracked/Untracked auto-detection ──────────────────────────────────────

    @staticmethod
    def _detect_tracked_status(files: list) -> str | None:
        """
        Infer tracked/untracked from filenames alone.

        Tracked:   many files (>3) where most start with a track-number prefix
                   e.g. '01 Murder Ballad.mp3', '02 Narrator 1.mp3'
        Untracked: 1–4 files named like 'Act 1.mp3', 'Act 2.m4a', or a single
                   whole-show file with no track-number prefix
        Returns 't', 'u', or None when genuinely ambiguous.
        """
        # Track-number prefix: leading 1-3 digits followed by space, dash, dot, or underscore
        _TRACK_NUM = re.compile(r'^\d{1,3}[\s.\-_]')
        # Act-file names: "Act 1.mp3", "Act Two.wav", "Act I.flac", "Side A.mp3"
        _ACT_FILE  = re.compile(
            r'^(act|side)\s*[1-9ivxab]\b', re.IGNORECASE
        )

        names = [fp.name for fp in files]
        numbered = sum(1 for n in names if _TRACK_NUM.match(n))
        act_files = sum(1 for n in names if _ACT_FILE.match(os.path.splitext(n)[0]))
        total = len(names)

        # Clear tracked signal: majority of files have track-number prefixes
        if total > 3 and numbered / total >= 0.7:
            return 't'

        # Clear untracked: small number of act-level or single whole-show files
        if total <= 4 or act_files >= total * 0.7:
            return 'u'

        return None  # ambiguous — ask user

    def _handle_loose_audio(self):
        """
        Handle audio files sitting loose at the release root.
        1. Try to auto-detect tracked vs untracked from filenames.
        2. If confident → move automatically (no prompt).
        3. If ambiguous → prompt (GUI dialog or CLI input depending on context).
        """
        exts       = {fp.suffix.lower() for fp in self._loose_audio}
        fmt_str    = ', '.join(e.lstrip('.').upper() for e in sorted(exts))
        sample     = [fp.name for fp in self._loose_audio[:5]]
        sample_str = ', '.join(sample) + (' ...' if len(self._loose_audio) > 5 else '')

        # ── Auto-detect ────────────────────────────────────────────────────────
        detected = self._detect_tracked_status(self._loose_audio)
        if detected is not None:
            logger.debug(f"Auto-detected {'tracked' if detected == 't' else 'untracked'} "
                         f"for {self.release_path.name}")
            self._apply_loose_audio_choice(detected, exts)
            return

        # ── Genuinely ambiguous — ask user ─────────────────────────────────────
        has_tty = self.interactive and sys.stdin.isatty()

        if has_tty:
            print(f"\n❓  {len(self._loose_audio)} ambiguous loose audio file(s) at root of:")
            print(f"   {self.release_path}")
            print(f"   Formats: {fmt_str}  |  e.g. {sample_str}")
            print("\nCan't auto-detect — are these files Tracked or Untracked?")
            print("  [t] Tracked    — move into Tracked/")
            print("  [u] Untracked  — move into Untracked/")
            print("  [s] Skip       — leave at root as-is")
            print("  [l] Log        — record to unrecognised_patterns.txt")
            choice = input("Choice [t/u/s/l]: ").strip().lower()

        elif self.interactive:
            choice = self._gui_loose_audio_dialog(fmt_str, sample_str)
            if choice is None:
                choice = 'l'
        else:
            choice = 'l'

        self._apply_loose_audio_choice(choice, exts)

    def _gui_loose_audio_dialog(self, fmt_str: str, sample_str: str) -> str | None:
        """Tkinter dialog for ambiguous loose audio — Tracked/Untracked/Skip/Log."""
        try:
            import tkinter as tk
        except ImportError:
            return None

        result = [None]
        root = tk.Tk()
        root.title("Ambiguous Audio Files")
        root.configure(bg="#1c1c1e")
        root.resizable(False, False)
        root.attributes('-topmost', True)

        pad = dict(padx=16, pady=6)
        tk.Label(root, text="❓  Can't auto-detect: Tracked or Untracked?",
                 font=("Segoe UI", 11, "bold"), bg="#1c1c1e", fg="#f5f5f7").pack(anchor="w", **pad)
        tk.Label(root, text=self.release_path.name, font=("Segoe UI", 9),
                 bg="#1c1c1e", fg="#8e8e93", wraplength=460).pack(anchor="w", padx=16, pady=(0, 4))
        tk.Label(root, text=f"{len(self._loose_audio)} file(s)  |  {fmt_str}",
                 font=("Segoe UI", 9), bg="#1c1c1e", fg="#f5f5f7").pack(anchor="w", padx=16)
        tk.Label(root, text=f"e.g. {sample_str}", font=("Segoe UI", 8),
                 bg="#1c1c1e", fg="#8e8e93", wraplength=460).pack(anchor="w", padx=16, pady=(2, 12))

        btn_frame = tk.Frame(root, bg="#1c1c1e")
        btn_frame.pack(fill="x", padx=16, pady=10)

        def choose(val):
            result[0] = val
            root.destroy()

        cfg = dict(font=("Segoe UI", 10), relief="flat", padx=14, pady=8,
                   cursor="hand2", highlightthickness=0, bd=0)
        tk.Button(btn_frame, text="Tracked/",    bg="#30d158", fg="#1c1c1e",
                  command=lambda: choose('t'), **cfg).pack(side="left", padx=(0, 6))
        tk.Button(btn_frame, text="Untracked/",  bg="#0a84ff", fg="white",
                  command=lambda: choose('u'), **cfg).pack(side="left", padx=(0, 6))
        tk.Button(btn_frame, text="Skip",        bg="#3a3a3c", fg="#f5f5f7",
                  command=lambda: choose('s'), **cfg).pack(side="left", padx=(0, 6))
        tk.Button(btn_frame, text="Log for later", bg="#3a3a3c", fg="#8e8e93",
                  command=lambda: choose('l'), **cfg).pack(side="left")

        root.update_idletasks()
        w, h = root.winfo_reqwidth(), root.winfo_reqheight()
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        root.mainloop()
        return result[0]

    def _apply_loose_audio_choice(self, choice: str, exts: set):
        """Queue move ops for loose audio files based on t/u/s/l choice."""
        if choice in ('t', 'u'):
            folder_name = (config.tracked_folder_name if choice == 't'
                           else config.untracked_folder_name)
            multi = len(exts) > 1
            for fp in self._loose_audio:
                ext  = fp.suffix.lower()
                base = f"{folder_name} ({ext[1:].upper()})" if multi else folder_name
                self._ops.append(('move', fp, self.release_path / base / fp.name))
        elif choice == 'l':
            with open('unrecognised_patterns.txt', 'a', encoding='utf-8') as fh:
                fh.write(f"# Loose audio — tracked/untracked ambiguous:\n")
                for fp in self._loose_audio:
                    fh.write(f"  {fp}\n")
        # 's' → leave at root
    # ── Execution ──────────────────────────────────────────────────────────────

    def _execute(self):
        for op in self._ops:
            try:
                if op[0] == 'delete':
                    p = Path(op[1])
                    if p.exists():
                        p.unlink()
                        logger.debug(f"Deleted {p}")

                elif op[0] == 'move':
                    src, dst = Path(op[1]), Path(op[2])
                    if src.exists() and src.resolve() != dst.resolve():
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(src), str(dst))
                        logger.debug(f"Moved {src} → {dst}")

                elif op[0] == 'rmdir':
                    p = Path(op[1])
                    if p.exists() and p.is_dir():
                        try:
                            p.rmdir()  # only removes if empty
                        except OSError:
                            pass  # not empty — leave it

            except Exception as exc:
                logger.error(f"Error in {op}: {exc}")

    def _clean_empty_subdirs(self):
        """Remove empty subdirectories left behind after moves, bottom-up."""
        for root, dirs, files in os.walk(self.release_path, topdown=False):
            p = Path(root)
            if p == self.release_path:
                continue  # never remove the release root itself
            try:
                p.rmdir()  # only succeeds if empty
                logger.debug(f"Removed empty dir {p}")
            except OSError:
                pass  # not empty — leave it


# ── Batch entry point ──────────────────────────────────────────────────────────

def organise_all_releases(local_ids: list[tuple], interactive: bool = True):
    """
    Organise content for every release folder in local_ids.
    local_ids: list of (encora_id, folder_path) from find_local_encora_ids().
    """
    import tqdm as _tqdm
    for _, folder_path in _tqdm.tqdm(local_ids, desc="Organising content...", unit="release"):
        if folder_path and os.path.isdir(folder_path):
            try:
                ContentOrganiser(folder_path, interactive=interactive).run()
            except Exception as exc:
                logger.error(f"Error organising {folder_path}: {exc}")
