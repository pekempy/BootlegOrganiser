import logging
import os
import re
import shutil
import sys
from pathlib import Path

from modules.config import config
from modules.content_classifiers import (
    ARCHIVE_EXTS,
    AUDIO_EXTS,
    IMAGE_EXTS,
    INFO_EXTS,
    JUNK_EXTS,
    JUNK_NAMES,
    MTS_EXTS,
    SUB_EXTS,
    VIDEO_EXTS,
    VOB_EXTS,
    classify_image,
    detect_tracked_status,
    is_device_folder,
    is_metadata,
    is_tracked_folder,
    is_untracked_folder,
    normalise_act,
)
from modules.safety_utils import safe_delete_directory, safe_delete_file

logger = logging.getLogger(__name__)


class ContentOrganiser:
    """Analyses one release folder, plans safe move/cleanup actions, and executes them."""

    def __init__(self, release_path: str, interactive: bool = True, confirm=None):
        self.release_path = Path(release_path)
        self.interactive = interactive
        self.confirm = confirm
        self.unknown_action = config.unknown_pattern_action
        self._ops: list[tuple] = []
        self._unknowns: list[Path] = []
        self._loose_audio: list[Path] = []

    def run(self) -> None:
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

        if inv['video'] or inv['mts'] or inv['vobs']:
            self._organise_video(inv['video'], inv['mts'], inv['vobs'])

        if self._unknowns:
            self._handle_unknowns()

        self._execute()
        self._clean_empty_subdirs()

    def _scan(self) -> dict:
        inv: dict[str, list] = {
            'audio': [], 'video': [], 'mts': [], 'vobs': [],
            'images': [], 'pdfs': [], 'archives': [], 'info': [], 'junk': [],
        }

        for root, dirs, files in os.walk(self.release_path):
            rel = Path(root).relative_to(self.release_path)
            parts = rel.parts
            dirs[:] = [d for d in dirs if not d.startswith('.')]

            for fn in files:
                fp = Path(root) / fn
                low = fn.lower()
                ext = Path(fn).suffix.lower()

                if is_metadata(fn):
                    continue

                if config.delete_junk_files and (
                    low in JUNK_NAMES or low.startswith('._.') or ext in JUNK_EXTS
                    or re.match(r'^cast\.txt\.conflict', low)
                ):
                    inv['junk'].append(fp)
                    continue

                if ext in SUB_EXTS:
                    continue
                if ext in AUDIO_EXTS:
                    inv['audio'].append((fp, parts))
                elif ext in VIDEO_EXTS:
                    inv['video'].append((fp, parts))
                elif ext in MTS_EXTS:
                    inv['mts'].append((fp, parts))
                elif ext in VOB_EXTS:
                    inv['vobs'].append((fp, parts))
                elif ext in IMAGE_EXTS:
                    inv['images'].append(fp)
                elif ext == '.pdf':
                    inv['pdfs'].append(fp)
                elif ext in ARCHIVE_EXTS:
                    inv['archives'].append(fp)
                elif ext in INFO_EXTS:
                    if 'cast' in low and low != 'cast.txt':
                        inv['info'].append(('rename_cast', fp))
                    else:
                        inv['info'].append(('keep', fp))
                elif not parts:
                    self._unknowns.append(fp)

        return inv

    def _fix_metadata_locations(self) -> None:
        for root, _, files in os.walk(self.release_path):
            if Path(root) == self.release_path:
                continue
            for fn in files:
                if is_metadata(fn):
                    src = Path(root) / fn
                    dst = self.release_path / fn
                    if not dst.exists():
                        self._ops.append(('move', src, dst))

    def _clean_junk(self, junk: list[Path]) -> None:
        if not config.delete_junk_files:
            return
        for f in junk:
            self._ops.append(('delete', f))

    def _handle_info_files(self, info: list[tuple]) -> None:
        cast_root = self.release_path / 'Cast.txt'
        for kind, fp in info:
            if kind == 'rename_cast' and not cast_root.exists():
                self._ops.append(('move', fp, cast_root))

    def _handle_images(self, images: list[Path]) -> None:
        if not config.delete_artwork and not config.move_photos:
            return
        photos_dir = self.release_path / config.photos_folder_name
        for img in images:
            action = classify_image(img.name)
            if action == 'delete' and config.delete_artwork:
                self._ops.append(('delete', img))
            elif action == 'photos' and config.move_photos:
                self._ops.append(('move', img, photos_dir / img.name))

    def _handle_pdfs(self, pdfs: list[Path]) -> None:
        if not pdfs or not config.move_programmes:
            return
        prog_dir = self.release_path / config.programme_folder_name
        for pdf in pdfs:
            self._ops.append(('move', pdf, prog_dir / pdf.name))

    def _handle_archives(self, archives: list[Path]) -> None:
        if not archives or not config.move_archives:
            return
        archive_dir = self.release_path / config.archive_folder_name
        for arc in archives:
            self._ops.append(('move', arc, archive_dir / arc.name))

    def _organise_audio(self, audio: list[tuple]) -> None:
        classified = []
        for fp, parts in audio:
            if not parts:
                self._loose_audio.append(fp)
                continue

            tracked = 'untracked'
            act = None
            device = None

            for part in parts:
                if is_tracked_folder(part):
                    tracked = 'tracked'
                elif is_untracked_folder(part):
                    tracked = 'untracked'

                a = normalise_act(part)
                if a:
                    act = a

                if is_device_folder(part) and device is None:
                    device = part

            classified.append((tracked, fp.suffix.lower(), act, device, fp))

        if not classified:
            return

        untracked_exts = {ext for ts, ext, _, _, _ in classified if ts == 'untracked'}
        tracked_exts = {ext for ts, ext, _, _, _ in classified if ts == 'tracked'}
        multi_untracked = len(untracked_exts) > 1
        multi_tracked = len(tracked_exts) > 1

        def _base(status: str, ext: str) -> str:
            if status == 'tracked':
                name = config.tracked_folder_name
                return f"{name} ({ext[1:].upper()})" if multi_tracked else name
            name = config.untracked_folder_name
            return f"{name} ({ext[1:].upper()})" if multi_untracked else name

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

    def _organise_video(self, video: list[tuple], mts: list[tuple], vobs: list[tuple]) -> None:
        vts = self.release_path / 'VIDEO_TS'
        if vts.exists() and vts.is_dir():
            self._flatten_video_ts(vts)

        if vobs:
            self._organise_vobs(vobs)

        if mts:
            parts_dir = self.release_path / config.parts_folder_name
            for fp, _ in mts:
                dst = parts_dir / fp.name
                if fp.resolve() != dst.resolve():
                    self._ops.append(('move', fp, dst))

        if video:
            self._organise_video_files(video)

    def _organise_video_files(self, video: list[tuple]) -> None:
        plain = [
            (fp, pts) for fp, pts in video
            if not any(p.lower() in ('parts', 'video_ts') or p.lower().startswith('vobs') for p in pts)
        ]
        if not plain:
            return

        if len(plain) == 1:
            fp, parts = plain[0]
            if parts:
                dst = self.release_path / fp.name
                if fp.resolve() != dst.resolve():
                    self._ops.append(('move', fp, dst))
        else:
            parts_dir = self.release_path / config.parts_folder_name
            for fp, _ in plain:
                dst = parts_dir / fp.name
                if fp.resolve() != dst.resolve():
                    self._ops.append(('move', fp, dst))

    def _organise_vobs(self, vobs: list[tuple]) -> None:
        has_smalls = any(fp.suffix.lower() in {'.ifo', '.bup'} for fp, _ in vobs)
        base = config.vobs_folder_name if has_smalls else f"{config.vobs_folder_name} (no smalls)"

        for fp, parts in vobs:
            act = None
            for part in parts:
                a = normalise_act(part)
                if a:
                    act = a
                    break
            dst_dir = (self.release_path / base / act) if act else (self.release_path / base)
            dst = dst_dir / fp.name
            if fp.resolve() != dst.resolve():
                self._ops.append(('move', fp, dst))

    def _flatten_video_ts(self, vts_dir: Path) -> None:
        children = [f for f in vts_dir.iterdir() if f.is_file()]
        has_smalls = any(f.suffix.lower() in {'.ifo', '.bup'} for f in children)
        base = config.vobs_folder_name + ('' if has_smalls else ' (no smalls)')
        dst_dir = self.release_path / base
        for f in children:
            self._ops.append(('move', f, dst_dir / f.name))
        self._ops.append(('rmdir', vts_dir))

    def _handle_unknowns(self) -> None:
        action = self.unknown_action
        if action == 'skip':
            print(f"  ⚠ Skipping {len(self._unknowns)} unrecognised file(s) in {self.release_path.name}")
            return

        if action == 'log' or not (self.interactive and sys.stdin.isatty()):
            with open('unrecognised_patterns.txt', 'a', encoding='utf-8') as fh:
                for fp in self._unknowns:
                    fh.write(f"{fp}\n")
            return

        print(f"\n⚠  Unrecognised file(s) in: {self.release_path}")
        for fp in self._unknowns:
            print(f"   {fp.relative_to(self.release_path)}")

        print("\nOptions:\n  [s] Skip — leave as-is\n  [l] Log\n  [f] Enter a subfolder name")
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

    def _handle_loose_audio(self) -> None:
        exts = {fp.suffix.lower() for fp in self._loose_audio}
        fmt_str = ', '.join(e.lstrip('.').upper() for e in sorted(exts))
        sample = [fp.name for fp in self._loose_audio[:5]]
        sample_str = ', '.join(sample) + (' ...' if len(self._loose_audio) > 5 else '')

        detected = detect_tracked_status(self._loose_audio)
        if detected is not None:
            logger.debug(f"Auto-detected {'tracked' if detected == 't' else 'untracked'} for {self.release_path.name}")
            self._apply_loose_audio_choice(detected, exts)
            return

        if self.interactive and sys.stdin.isatty():
            print(f"\n❓  {len(self._loose_audio)} ambiguous loose audio file(s) at root of: {self.release_path}")
            print(f"   Formats: {fmt_str}  |  e.g. {sample_str}")
            choice = input("Choice [t/u/s/l]: ").strip().lower()
        elif self.interactive:
            choice = self._gui_loose_audio_dialog(fmt_str, sample_str) or 'l'
        else:
            choice = 'l'

        self._apply_loose_audio_choice(choice, exts)

    def _gui_loose_audio_dialog(self, fmt_str: str, sample_str: str) -> str | None:
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
        tk.Label(root, text="❓  Can't auto-detect: Tracked or Untracked?", font=("Segoe UI", 11, "bold"), bg="#1c1c1e", fg="#f5f5f7").pack(anchor="w", **pad)
        tk.Label(root, text=self.release_path.name, font=("Segoe UI", 9), bg="#1c1c1e", fg="#8e8e93", wraplength=460).pack(anchor="w", padx=16, pady=(0, 4))
        tk.Label(root, text=f"{len(self._loose_audio)} file(s)  |  {fmt_str}", font=("Segoe UI", 9), bg="#1c1c1e", fg="#f5f5f7").pack(anchor="w", padx=16)
        tk.Label(root, text=f"e.g. {sample_str}", font=("Segoe UI", 8), bg="#1c1c1e", fg="#8e8e93", wraplength=460).pack(anchor="w", padx=16, pady=(2, 12))

        btn_frame = tk.Frame(root, bg="#1c1c1e")
        btn_frame.pack(fill="x", padx=16, pady=10)

        def choose(val):
            result[0] = val
            root.destroy()

        cfg = dict(font=("Segoe UI", 10), relief="flat", padx=14, pady=8, cursor="hand2", highlightthickness=0, bd=0)
        tk.Button(btn_frame, text="Tracked/", bg="#30d158", fg="#1c1c1e", command=lambda: choose('t'), **cfg).pack(side="left", padx=(0, 6))
        tk.Button(btn_frame, text="Untracked/", bg="#0a84ff", fg="white", command=lambda: choose('u'), **cfg).pack(side="left", padx=(0, 6))
        tk.Button(btn_frame, text="Skip", bg="#3a3a3c", fg="#f5f5f7", command=lambda: choose('s'), **cfg).pack(side="left", padx=(0, 6))
        tk.Button(btn_frame, text="Log for later", bg="#3a3a3c", fg="#8e8e93", command=lambda: choose('l'), **cfg).pack(side="left")

        root.update_idletasks()
        w, h = root.winfo_reqwidth(), root.winfo_reqheight()
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        root.mainloop()
        return result[0]

    def _apply_loose_audio_choice(self, choice: str, exts: set) -> None:
        if choice in ('t', 'u'):
            folder_name = config.tracked_folder_name if choice == 't' else config.untracked_folder_name
            multi = len(exts) > 1
            for fp in self._loose_audio:
                ext = fp.suffix.lower()
                base = f"{folder_name} ({ext[1:].upper()})" if multi else folder_name
                self._ops.append(('move', fp, self.release_path / base / fp.name))
        elif choice == 'l':
            with open('unrecognised_patterns.txt', 'a', encoding='utf-8') as fh:
                fh.write("# Loose audio — tracked/untracked ambiguous:\n")
                for fp in self._loose_audio:
                    fh.write(f"  {fp}\n")

    def _execute(self) -> None:
        _log = logger.info if self.confirm is not None else logger.debug

        if self.confirm is not None and self._ops:
            lines = []
            for op in self._ops:
                if op[0] == 'move':
                    try:
                        rel_dst = Path(op[2]).relative_to(self.release_path)
                    except ValueError:
                        rel_dst = Path(op[2])
                    lines.append(f"    MOVE   {Path(op[1]).name}  →  {rel_dst}")
                elif op[0] == 'delete':
                    lines.append(f"    DELETE {Path(op[1]).name}")
                elif op[0] == 'rmdir':
                    lines.append(f"    RMDIR  {Path(op[1]).name}/")
            preview = "\n".join(lines[:25])
            if len(lines) > 25:
                preview += f"\n    … and {len(lines) - 25} more"
            if not self.confirm(f"Organise release folder: {self.release_path.name}\n{preview}"):
                return

        main_dir = config.main_directory or str(self.release_path.parent)

        for op in self._ops:
            try:
                if op[0] == 'delete':
                    p = Path(op[1])
                    if p.exists():
                        if safe_delete_file(str(p), main_dir, reason=f"ContentOrganiser cleanup inside {self.release_path.name}"):
                            _log(f"Handled delete/quarantine for {p}")

                elif op[0] == 'move':
                    src, dst = Path(op[1]), Path(op[2])
                    if not src.exists():
                        continue
                    same_phys = False
                    try:
                        if dst.exists():
                            same_phys = os.path.samefile(src, dst)
                    except OSError:
                        pass
                    if same_phys:
                        if str(src) != str(dst):
                            dst.parent.mkdir(parents=True, exist_ok=True)
                            tmp = src.with_name(f"{src.name}.__tmp_rename__")
                            src.rename(tmp)
                            tmp.rename(dst)
                            _log(f"Renamed {src} → {dst}")
                        continue
                    if dst.exists():
                        logger.warning(f"Skipping move {src} → {dst}: destination already exists")
                        continue
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(src), str(dst))
                    _log(f"Moved {src} → {dst}")

                elif op[0] == 'rmdir':
                    p = Path(op[1])
                    if p.exists() and p.is_dir():
                        safe_delete_directory(
                            str(p),
                            main_dir,
                            reason=f"ContentOrganiser folder removal inside {self.release_path.name}",
                        )
            except Exception as exc:
                logger.error(f"Error in {op}: {exc}")

    def _clean_empty_subdirs(self) -> None:
        main_dir = config.main_directory or str(self.release_path.parent)
        for root, dirs, files in os.walk(self.release_path, topdown=False):
            p = Path(root)
            try:
                same = os.path.samefile(p, self.release_path)
            except OSError:
                same = (p == self.release_path)
            if same:
                continue
            if not dirs and not files:
                safe_delete_directory(
                    str(p),
                    main_dir,
                    reason=f"Empty subdirectory cleanup inside {self.release_path.name}",
                )


def organise_all_releases(local_ids: list[tuple], interactive: bool = True, confirm=None) -> None:
    import tqdm as _tqdm

    for _, folder_path in _tqdm.tqdm(local_ids, desc="Organising content...", unit="release"):
        if folder_path and os.path.isdir(folder_path):
            try:
                ContentOrganiser(folder_path, interactive=interactive, confirm=confirm).run()
            except Exception as exc:
                logger.error(f"Error organising {folder_path}: {exc}")
