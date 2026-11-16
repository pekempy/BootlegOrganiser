import importlib
import os
import tempfile
import unicodedata
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from modules.checksum_utils import verify_all_checksums
from modules.config import config
from modules.safety_utils import DANGER_ZONE_THRESHOLD_BYTES, safe_delete_directory


class TestIntegrationDummyLibrary(unittest.TestCase):
    """
    Full-pipeline integration test against a realistic dummy library folder.
    Verifies every file is either preserved in its canonical location, moved to
    !non-encora / !unmatched / !danger-zone, or explicitly expected (Cast.txt,
    .encora-NNN, Checksums.b2, .checksums.cache) with zero unexpected deletions
    and zero Encora API mutations.
    """

    def test_full_pipeline_on_dummy_library_with_strict_file_accounting(self):
        full_organise = importlib.import_module("full-organise")

        with tempfile.TemporaryDirectory() as lib_td, tempfile.TemporaryDirectory() as cwd_td:
            root = Path(lib_td)

            # 1. Matched video release in mismatched-case parent folder
            r1 = root / "murder ballad" / "Off-Broadway" / "Video" / "Drop {e-101}"
            r1.mkdir(parents=True)
            (r1 / "MurderBallad.mp4").write_bytes(b"video-101")
            (r1 / "Cast Notes.txt").write_text("my custom cast notes", encoding="utf-8")
            (r1 / "Cast.docx").write_bytes(b"docx-notes")
            (r1 / "01.jpg").write_bytes(b"stage-door-photo")
            (r1 / "cover.jpg").write_bytes(b"album-cover")
            (r1 / ".DS_Store").write_bytes(b"finder-junk")

            # 2. NFD Unicode show path + tracked audio (>3 numbered tracks -> Tracked/)
            r2 = root / "Les Mise\u0301rables" / "West End" / "Audio" / "Drop {e-102}"
            r2.mkdir(parents=True)
            (r2 / "01 Overture.mp3").write_bytes(b"mp3-1")
            (r2 / "02 Prologue.mp3").write_bytes(b"mp3-2")
            (r2 / "03 At the End of the Day.mp3").write_bytes(b"mp3-3")
            (r2 / "04 I Dreamed a Dream.mp3").write_bytes(b"mp3-4")

            # 3. Non-Encora {ne} folder
            ne = root / "Home Recording {ne}"
            ne.mkdir()
            (ne / "concert.wav").write_bytes(b"wav-ne")

            # 4. Unmatched Encora ID folder (e.g. deleted recording)
            unmatched_id = root / "Deleted Recording {e-999999999}"
            unmatched_id.mkdir()
            (unmatched_id / "deleted.mkv").write_bytes(b"mkv-unmatched")

            # 5. Unmatched folder without Encora ID
            unsorted = root / "Random Unsorted Folder"
            unsorted.mkdir()
            (unsorted / "extra_clip.mp4").write_bytes(b"clip-unmatched")

            # 6. Loose unmatched file at root
            (root / "stray_notes.txt").write_text("stray note", encoding="utf-8")

            # 7. Truly empty directory that is safe to remove
            (root / "EmptyOldFolder").mkdir()

            # 8. Oversized (>10 MB) directory that must quarantine to !danger-zone
            oversized = root / "BigAtRiskFolder"
            oversized.mkdir()
            (oversized / "huge.mkv").write_bytes(b"\0" * (DANGER_ZONE_THRESHOLD_BYTES + 1024))

            fake_collection = [
                {
                    "recording": {
                        "id": 101,
                        "show": "Murder Ballad",
                        "tour": "Off-Broadway",
                        "date": {"full_date": "2013-05-22", "month_known": True, "day_known": True},
                        "master": "TestMaster",
                        "metadata": {"amount_recorded": "Complete", "media_type": "Video"},
                        "nft": {},
                        "cast": [
                            {"performer": {"name": "Caissie Levy"}, "character": {"name": "Sara"}, "status": {"abbreviation": ""}}
                        ],
                    },
                    "format": "",
                },
                {
                    "recording": {
                        "id": 102,
                        "show": "Les Mis\u00e9rables",
                        "tour": "West End",
                        "date": {"full_date": "2024-02-02", "month_known": True, "day_known": True},
                        "master": "AudioMaster",
                        "metadata": {"amount_recorded": "Complete", "media_type": "Audio"},
                        "nft": {},
                        "cast": [],
                    },
                    "format": "",
                },
            ]

            def forbid_send(*args, **kwargs):
                raise AssertionError(f"send_format must not be called when update_encora_format=False: {args}")

            orig_cwd = os.getcwd()
            try:
                os.chdir(cwd_td)
                patches = [
                    patch.object(type(config), "main_directory", property(lambda self: str(root))),
                    patch.object(type(config), "api_key", property(lambda self: "dummy-key")),
                    patch.object(type(config), "generate_cast_files", property(lambda self: True)),
                    patch.object(type(config), "generate_encoraid_files", property(lambda self: True)),
                    patch.object(type(config), "organise_content", property(lambda self: True)),
                    patch.object(type(config), "update_encora_format", property(lambda self: False)),
                    patch.object(type(config), "generate_checksums", property(lambda self: True)),
                    patch.object(type(config), "redownload_subtitles", property(lambda self: False)),
                    patch.object(type(config), "delete_junk_files", property(lambda self: True)),
                    patch.object(type(config), "delete_artwork", property(lambda self: True)),
                    patch.object(type(config), "move_photos", property(lambda self: True)),
                    patch.object(type(config), "show_directory_format", property(lambda self: "{show_name}/{tour}/{type}/{folder}")),
                    patch.object(type(config), "show_folder_format", property(lambda self: "{date} {show_name} ~ {master} {encora_id}")),
                    patch.object(type(config), "date_container", property(lambda self: "None")),
                    patch.object(type(config), "encora_id_container", property(lambda self: "Curly Brackets {}")),
                    patch.object(full_organise, "fetch_collection", return_value=fake_collection),
                    patch("modules.encora_utils.authenticated_request", side_effect=RuntimeError("404")),
                    patch("modules.encora_utils.fetch_single_recording", return_value=None),
                    patch.object(full_organise, "send_format", side_effect=forbid_send),
                ]
                with ExitStack() as stack:
                    for p in patches:
                        stack.enter_context(p)
                    safe_delete_directory(str(oversized), str(root), reason="Simulated risky folder deletion")
                    full_organise.run_organiser(interactive=False, safe=False)
            finally:
                os.chdir(orig_cwd)

            actual_files = {
                unicodedata.normalize('NFC', str(p.relative_to(root)).replace(os.sep, "/")).lower()
                for p in root.rglob("*")
                if p.is_file()
            }

            expected_files = {
                p.lower()
                for p in {
                    "Murder Ballad/Off-Broadway/Video/2013-05-22 Murder Ballad ~ TestMaster {e-101}/MurderBallad.mp4",
                    "Murder Ballad/Off-Broadway/Video/2013-05-22 Murder Ballad ~ TestMaster {e-101}/Cast Notes.txt",
                    "Murder Ballad/Off-Broadway/Video/2013-05-22 Murder Ballad ~ TestMaster {e-101}/Cast.docx",
                    "Murder Ballad/Off-Broadway/Video/2013-05-22 Murder Ballad ~ TestMaster {e-101}/Photos/01.jpg",
                    "Murder Ballad/Off-Broadway/Video/2013-05-22 Murder Ballad ~ TestMaster {e-101}/Cast.txt",
                    "Murder Ballad/Off-Broadway/Video/2013-05-22 Murder Ballad ~ TestMaster {e-101}/.encora-101",
                    "Murder Ballad/Off-Broadway/Video/2013-05-22 Murder Ballad ~ TestMaster {e-101}/Checksums.b2",
                    "Murder Ballad/Off-Broadway/Video/2013-05-22 Murder Ballad ~ TestMaster {e-101}/.checksums.cache",
                    "Les Mis\u00e9rables/West End/Audio/2024-02-02 Les Mis\u00e9rables ~ AudioMaster {e-102}/Tracked/01 Overture.mp3",
                    "Les Mis\u00e9rables/West End/Audio/2024-02-02 Les Mis\u00e9rables ~ AudioMaster {e-102}/Tracked/02 Prologue.mp3",
                    "Les Mis\u00e9rables/West End/Audio/2024-02-02 Les Mis\u00e9rables ~ AudioMaster {e-102}/Tracked/03 At the End of the Day.mp3",
                    "Les Mis\u00e9rables/West End/Audio/2024-02-02 Les Mis\u00e9rables ~ AudioMaster {e-102}/Tracked/04 I Dreamed a Dream.mp3",
                    "Les Mis\u00e9rables/West End/Audio/2024-02-02 Les Mis\u00e9rables ~ AudioMaster {e-102}/Cast.txt",
                    "Les Mis\u00e9rables/West End/Audio/2024-02-02 Les Mis\u00e9rables ~ AudioMaster {e-102}/.encora-102",
                    "Les Mis\u00e9rables/West End/Audio/2024-02-02 Les Mis\u00e9rables ~ AudioMaster {e-102}/Checksums.b2",
                    "Les Mis\u00e9rables/West End/Audio/2024-02-02 Les Mis\u00e9rables ~ AudioMaster {e-102}/.checksums.cache",
                    "!non-encora/Home Recording {ne}/concert.wav",
                    "!unmatched/Deleted Recording {e-999999999}/deleted.mkv",
                    "!unmatched/Random Unsorted Folder/extra_clip.mp4",
                    "!unmatched/stray_notes.txt",
                    "!danger-zone/BigAtRiskFolder/huge.mkv",
                    "!danger-zone/BigAtRiskFolder/DANGER_ZONE_REASON.txt",
                }
            }

            self.assertEqual(actual_files, expected_files)
            self.assertFalse((root / "EmptyOldFolder").exists())

            checked, failed = verify_all_checksums(str(root))
            self.assertEqual(checked, 2)
            self.assertEqual(failed, 0)

            self.assertTrue((Path(cwd_td) / "organiser-debug.log").exists())
            self.assertTrue((Path(cwd_td) / "unrecognised_patterns.txt").exists())


if __name__ == "__main__":
    unittest.main()
