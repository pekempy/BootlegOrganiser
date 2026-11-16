import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from modules.api_utils import authenticated_request, build_api_session
from modules.cleanup_utils import clean_processing_folder, delete_empty_directories
from modules.config import config
from modules.content_utils import ContentOrganiser
from modules.encora_utils import find_local_encora_ids
from modules.folder_utils import move_and_rename_folders, move_merge
from modules.safety_utils import DANGER_ZONE_THRESHOLD_BYTES, safe_delete_directory
from modules.unmatched_utils import move_unmatched_items

class TestDeletionSafetyAndUnmatched(unittest.TestCase):
    def test_case_difference_on_parent_dir_does_not_delete_files(self):
        with tempfile.TemporaryDirectory() as td:
            # Disk has lowercase parent directory ("les miserables")
            rel_dir = Path(td) / "les miserables" / "Broadway" / "Video" / "2024-01-01 Les Miserables ~ Master {e-123}"
            rel_dir.mkdir(parents=True)
            media = rel_dir / "recording.mp4"
            media.write_bytes(b"precious video bytes")

            encora_data = [{
                "encora_id": "123",
                "path": str(rel_dir),
                "recording_data": {
                    "show": "Les Miserables",
                    "tour": "Broadway",
                    "date": {"full_date": "2024-01-01", "month_known": True, "day_known": True},
                    "master": "Master",
                    "metadata": {"amount_recorded": "Complete", "media_type": "Video"},
                    "nft": {},
                },
            }]

            with patch.object(type(config), "show_directory_format", property(lambda self: "{show_name}/{tour}/{type}/{folder}")), \
                 patch.object(type(config), "show_folder_format", property(lambda self: "{date} {show_name} ~ {master} {encora_id}")), \
                 patch.object(type(config), "date_container", property(lambda self: "None")), \
                 patch.object(type(config), "encora_id_container", property(lambda self: "Curly Brackets {}")):
                move_and_rename_folders(encora_data, td)

            # File must still exist on disk with exact content
            found = list(Path(td).rglob("recording.mp4"))
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0].read_bytes(), b"precious video bytes")

    def test_nfd_unicode_path_does_not_delete_files(self):
        with tempfile.TemporaryDirectory() as td:
            nfd_show = "Les Mise\u0301rables"
            rel_dir = Path(td) / nfd_show / "West End" / "Audio" / "2024-02-02 Les Mise\u0301rables ~ Master {e-456}"
            rel_dir.mkdir(parents=True)
            track = rel_dir / "01.mp3"
            track.write_bytes(b"audio bytes")

            encora_data = [{
                "encora_id": "456",
                "path": str(rel_dir),
                "recording_data": {
                    "show": "Les Mis\u00e9rables",
                    "tour": "West End",
                    "date": {"full_date": "2024-02-02", "month_known": True, "day_known": True},
                    "master": "Master",
                    "metadata": {"amount_recorded": "Complete", "media_type": "Audio"},
                    "nft": {},
                },
            }]

            with patch.object(type(config), "show_directory_format", property(lambda self: "{show_name}/{tour}/{type}/{folder}")), \
                 patch.object(type(config), "show_folder_format", property(lambda self: "{date} {show_name} ~ {master} {encora_id}")), \
                 patch.object(type(config), "date_container", property(lambda self: "None")), \
                 patch.object(type(config), "encora_id_container", property(lambda self: "Curly Brackets {}")):
                move_and_rename_folders(encora_data, td)

            found = list(Path(td).rglob("01.mp3"))
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0].read_bytes(), b"audio bytes")

    def test_move_merge_never_overwrites_existing_destination_file(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "src" / "video.mp4"
            dst = Path(td) / "dst" / "video.mp4"
            src.parent.mkdir()
            dst.parent.mkdir()
            src.write_bytes(b"new file")
            dst.write_bytes(b"existing file")

            move_merge(str(src.parent), str(dst.parent))

            self.assertEqual(dst.read_bytes(), b"existing file")
            self.assertEqual(src.read_bytes(), b"new file")

    def test_content_organiser_preserves_user_docs_cast_notes_numbered_photos_and_respects_junk_setting(self):
        with tempfile.TemporaryDirectory() as td:
            rel = Path(td) / "Show ~ Master {e-777}"
            rel.mkdir()
            (rel / "Cast.txt").write_text("official cast", encoding="utf-8")
            (rel / "Broadway Cast Notes.txt").write_text("user notes", encoding="utf-8")
            (rel / "Cast.docx").write_bytes(b"docx")
            (rel / "checksum.md5").write_text("abc", encoding="utf-8")
            (rel / "01.jpg").write_bytes(b"stage door photo")
            (rel / ".DS_Store").write_bytes(b"junk")

            orig_cwd = os.getcwd()
            try:
                os.chdir(td)
                # Even when delete_junk_files is True, user docs/md5/cast notes must survive
                with patch.object(type(config), "delete_junk_files", property(lambda self: True)):
                    ContentOrganiser(str(rel), interactive=False).run()

                self.assertTrue((rel / "Cast.txt").exists())
                self.assertTrue((rel / "Broadway Cast Notes.txt").exists())
                self.assertTrue((rel / "Cast.docx").exists())
                self.assertTrue((rel / "checksum.md5").exists())
                self.assertTrue((rel / "Photos" / "01.jpg").exists())
                self.assertFalse((rel / ".DS_Store").exists())

                # When delete_junk_files is False, even .DS_Store / .tmp stays
                (rel / "temp.tmp").write_bytes(b"tmp")
                with patch.object(type(config), "delete_junk_files", property(lambda self: False)):
                    ContentOrganiser(str(rel), interactive=False).run()
                self.assertTrue((rel / "temp.tmp").exists())
            finally:
                os.chdir(orig_cwd)

    def test_move_unmatched_items_isolates_unmatched_and_preserves_matched_and_non_encora(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            # Matched release inside hierarchy
            matched_dir = root / "Wicked" / "Broadway" / "Video" / "2024-01-01 Wicked ~ Master {e-100}"
            matched_dir.mkdir(parents=True)
            (matched_dir / "show.mp4").write_bytes(b"matched")

            # Unmatched Encora ID folder inside hierarchy
            unmatched_id_dir = root / "Wicked" / "Broadway" / "Deleted {e-999}"
            unmatched_id_dir.mkdir(parents=True)
            (unmatched_id_dir / "old.mp4").write_bytes(b"old")

            # Unmatched folder with no ID
            orphan_dir = root / "Random Unmatched Drop"
            orphan_dir.mkdir()
            (orphan_dir / "clip.mkv").write_bytes(b"clip")

            # Loose file at root
            (root / "loose.mp4").write_bytes(b"loose")

            # Non-Encora folder already moved to !non-encora
            ne_dir = root / "!non-encora" / "Concert {ne} {e-888}"
            ne_dir.mkdir(parents=True)
            (ne_dir / "concert.mp4").write_bytes(b"concert")

            unmatched_folder = str(root / "!unmatched")
            moved = move_unmatched_items(
                str(root),
                unmatched_folder,
                [{"encora_id": "100", "path": str(matched_dir)}],
            )

            self.assertEqual(len(moved), 3)
            # Matched release & non-encora untouched
            self.assertTrue((matched_dir / "show.mp4").exists())
            self.assertTrue((ne_dir / "concert.mp4").exists())
            self.assertFalse(unmatched_id_dir.exists())
            self.assertFalse(orphan_dir.exists())
            self.assertFalse((root / "loose.mp4").exists())
            self.assertTrue((root / "!unmatched" / "Wicked" / "Broadway" / "Deleted {e-999}" / "old.mp4").exists())
            self.assertTrue((root / "!unmatched" / "Random Unmatched Drop" / "clip.mkv").exists())
            self.assertTrue((root / "!unmatched" / "loose.mp4").exists())

            found_ids = find_local_encora_ids(str(root))
            self.assertEqual([eid for eid, _ in found_ids], ["100"])
            delete_empty_directories(str(root))
            self.assertTrue((root / "!unmatched").exists())
            self.assertTrue((root / "!non-encora").exists())

    def test_run_organiser_end_to_end_and_api_outage_guard(self):
        import importlib
        full_organise = importlib.import_module("full-organise")

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            matched_dir = root / "Drop {e-100}"
            matched_dir.mkdir()
            (matched_dir / "video.mp4").write_bytes(b"video")

            unmatched_dir = root / "Unmatched {e-404}"
            unmatched_dir.mkdir()
            (unmatched_dir / "other.mp4").write_bytes(b"other")

            orig_cwd = os.getcwd()
            try:
                os.chdir(td)
                with patch.object(type(config), "main_directory", property(lambda self: str(root))), \
                     patch.object(type(config), "api_key", property(lambda self: "fake-key")), \
                     patch.object(type(config), "generate_cast_files", property(lambda self: False)), \
                     patch.object(type(config), "generate_encoraid_files", property(lambda self: False)), \
                     patch.object(type(config), "organise_content", property(lambda self: False)), \
                     patch.object(type(config), "update_encora_format", property(lambda self: False)), \
                     patch.object(type(config), "generate_checksums", property(lambda self: False)), \
                     patch.object(type(config), "redownload_subtitles", property(lambda self: False)), \
                     patch.object(full_organise, "fetch_collection", return_value=[]), \
                     patch("modules.encora_utils.authenticated_request", side_effect=RuntimeError("offline")), \
                     patch("modules.encora_utils.fetch_single_recording", return_value=None):
                    # API returned empty collection -> must NOT sweep matched/local folders to !unmatched
                    full_organise.run_organiser(interactive=False, safe=False)
                    self.assertFalse((root / "!unmatched").exists())
                    self.assertTrue((matched_dir / "video.mp4").exists())
                    self.assertTrue((unmatched_dir / "other.mp4").exists())

                # Now API returns collection with 100 matched and 404 still unmatched
                fake_collection = [{
                    "recording": {
                        "id": 100,
                        "show": "Wicked",
                        "tour": "Broadway",
                        "date": {"full_date": "2024-01-01", "month_known": True, "day_known": True},
                        "master": "Master",
                        "metadata": {"amount_recorded": "Complete", "media_type": "Video"},
                        "nft": {},
                    },
                    "format": "",
                }]
                with patch.object(type(config), "main_directory", property(lambda self: str(root))), \
                     patch.object(type(config), "api_key", property(lambda self: "fake-key")), \
                     patch.object(type(config), "generate_cast_files", property(lambda self: False)), \
                     patch.object(type(config), "generate_encoraid_files", property(lambda self: False)), \
                     patch.object(type(config), "organise_content", property(lambda self: False)), \
                     patch.object(type(config), "update_encora_format", property(lambda self: False)), \
                     patch.object(type(config), "generate_checksums", property(lambda self: False)), \
                     patch.object(type(config), "redownload_subtitles", property(lambda self: False)), \
                     patch.object(type(config), "show_directory_format", property(lambda self: "{show_name}/{tour}/{type}/{folder}")), \
                     patch.object(type(config), "show_folder_format", property(lambda self: "{date} {show_name} ~ {master} {encora_id}")), \
                     patch.object(type(config), "date_container", property(lambda self: "None")), \
                     patch.object(type(config), "encora_id_container", property(lambda self: "Curly Brackets {}")), \
                     patch.object(full_organise, "fetch_collection", return_value=fake_collection), \
                     patch("modules.encora_utils.authenticated_request", side_effect=RuntimeError("404")), \
                     patch("modules.encora_utils.fetch_single_recording", return_value=None):
                    full_organise.run_organiser(interactive=False, safe=False)
                    self.assertTrue((root / "Wicked" / "Broadway" / "Video" / "2024-01-01 Wicked ~ Master {e-100}" / "video.mp4").exists())
                    self.assertTrue((root / "!unmatched" / "Unmatched {e-404}" / "other.mp4").exists())

                # Partial API fetch (last_complete=False even with non-empty data) must skip !unmatched
                stray_dir = root / "Unmatched Drop 2"
                stray_dir.mkdir()
                (stray_dir / "keep.mp4").write_bytes(b"keep")
                def partial_fetch():
                    partial_fetch.last_complete = False
                    return fake_collection
                partial_fetch.last_complete = False
                with patch.object(type(config), "main_directory", property(lambda self: str(root))), \
                     patch.object(type(config), "api_key", property(lambda self: "fake-key")), \
                     patch.object(type(config), "generate_cast_files", property(lambda self: False)), \
                     patch.object(type(config), "generate_encoraid_files", property(lambda self: False)), \
                     patch.object(type(config), "organise_content", property(lambda self: False)), \
                     patch.object(type(config), "update_encora_format", property(lambda self: False)), \
                     patch.object(type(config), "generate_checksums", property(lambda self: False)), \
                     patch.object(type(config), "redownload_subtitles", property(lambda self: False)), \
                     patch.object(type(config), "show_directory_format", property(lambda self: "{show_name}/{tour}/{type}/{folder}")), \
                     patch.object(type(config), "show_folder_format", property(lambda self: "{date} {show_name} ~ {master} {encora_id}")), \
                     patch.object(type(config), "date_container", property(lambda self: "None")), \
                     patch.object(type(config), "encora_id_container", property(lambda self: "Curly Brackets {}")), \
                     patch.object(full_organise, "fetch_collection", partial_fetch), \
                     patch("modules.encora_utils.authenticated_request", side_effect=RuntimeError("offline")):
                    full_organise.run_organiser(interactive=False, safe=False)
                    self.assertTrue((stray_dir / "keep.mp4").exists())
            finally:
                os.chdir(orig_cwd)

    def test_large_folder_delete_quarantines_to_danger_zone_with_reason_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            at_risk = root / "!processing"
            at_risk.mkdir()
            big_file = at_risk / "bootleg.mkv"
            big_file.write_bytes(b"\0" * (DANGER_ZONE_THRESHOLD_BYTES + 1024))

            clean_processing_folder(str(root))

            self.assertFalse(at_risk.exists())
            quarantined = root / "!danger-zone" / "!processing"
            self.assertTrue(quarantined.exists())
            self.assertTrue((quarantined / "bootleg.mkv").exists())
            reason_file = quarantined / "DANGER_ZONE_REASON.txt"
            self.assertTrue(reason_file.exists())
            reason_text = reason_file.read_text(encoding="utf-8")
            self.assertIn("10 MB", reason_text)
            self.assertIn("!processing", reason_text)

            delete_empty_directories(str(root))
            self.assertTrue((quarantined / "bootleg.mkv").exists())

            other = root / "RiskyFolder"
            other.mkdir()
            (other / "large.mp4").write_bytes(b"\0" * (DANGER_ZONE_THRESHOLD_BYTES + 2048))
            safe_delete_directory(str(other), str(root), reason="Test deletion trigger")
            self.assertFalse(other.exists())
            self.assertTrue((root / "!danger-zone" / "RiskyFolder" / "large.mp4").exists())
            self.assertIn("Test deletion trigger", (root / "!danger-zone" / "RiskyFolder" / "DANGER_ZONE_REASON.txt").read_text(encoding="utf-8"))

    def test_api_session_reads_key_dynamically_and_retries_transient_500(self):
        with patch.object(type(config), "api_key", property(lambda self: "dynamic-key-123")):
            with build_api_session() as sess:
                self.assertEqual(sess.headers.get("Authorization"), "Bearer dynamic-key-123")

        class FakeResp:
            def __init__(self, status_code, payload=None):
                self.status_code = status_code
                self.headers = {}
                self._payload = payload or {}

            def raise_for_status(self):
                if self.status_code >= 400:
                    import requests
                    raise requests.exceptions.HTTPError(f"HTTP {self.status_code}")

            def json(self):
                return self._payload

        class FakeSession:
            def __init__(self):
                self.calls = 0

            def get(self, url, **kwargs):
                self.calls += 1
                if self.calls == 1:
                    return FakeResp(502)
                return FakeResp(200, {"ok": True})

        fake_sess = FakeSession()
        with patch("modules.api_utils.time.sleep"):
            resp = authenticated_request("GET", "https://encora.it/api/test", session=fake_sess, retries=2)
        self.assertEqual(fake_sess.calls, 2)
        self.assertEqual(resp.json(), {"ok": True})

    def test_run_organiser_continues_when_optional_step_raises(self):
        import importlib
        full_organise = importlib.import_module("full-organise")

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            matched_dir = root / "Drop {e-100}"
            matched_dir.mkdir()
            (matched_dir / "video.mp4").write_bytes(b"video")

            fake_collection = [{
                "recording": {
                    "id": 100,
                    "show": "Wicked",
                    "tour": "Broadway",
                    "date": {"full_date": "2024-01-01", "month_known": True, "day_known": True},
                    "master": "Master",
                    "metadata": {"amount_recorded": "Complete", "media_type": "Video"},
                    "nft": {},
                },
                "format": "",
            }]
            orig_cwd = os.getcwd()
            try:
                os.chdir(td)
                with patch.object(type(config), "main_directory", property(lambda self: str(root))), \
                     patch.object(type(config), "api_key", property(lambda self: "fake-key")), \
                     patch.object(type(config), "generate_cast_files", property(lambda self: True)), \
                     patch.object(type(config), "generate_encoraid_files", property(lambda self: False)), \
                     patch.object(type(config), "organise_content", property(lambda self: False)), \
                     patch.object(type(config), "update_encora_format", property(lambda self: False)), \
                     patch.object(type(config), "generate_checksums", property(lambda self: False)), \
                     patch.object(type(config), "redownload_subtitles", property(lambda self: False)), \
                     patch.object(type(config), "show_directory_format", property(lambda self: "{show_name}/{tour}/{type}/{folder}")), \
                     patch.object(type(config), "show_folder_format", property(lambda self: "{date} {show_name} ~ {master} {encora_id}")), \
                     patch.object(type(config), "date_container", property(lambda self: "None")), \
                     patch.object(type(config), "encora_id_container", property(lambda self: "Curly Brackets {}")), \
                     patch.object(full_organise, "fetch_collection", return_value=fake_collection), \
                     patch.object(full_organise, "create_cast_files", side_effect=PermissionError("read-only")):
                    full_organise.run_organiser(interactive=False, safe=False)
                    self.assertTrue((root / "Wicked" / "Broadway" / "Video" / "2024-01-01 Wicked ~ Master {e-100}" / "video.mp4").exists())
            finally:
                os.chdir(orig_cwd)


if __name__ == "__main__":
    unittest.main()
