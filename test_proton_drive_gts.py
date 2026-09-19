#!/usr/bin/env python3
# pylint: disable=line-too-long,import-outside-toplevel,redefined-outer-name,reimported,unused-import,unused-variable,unused-wildcard-import,wildcard-import,too-many-lines,unspecified-encoding
"""Tests for proton_drive_gts.py."""

import json
import os
import signal
import tempfile
import unittest
from datetime import datetime
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import proton_drive_gts as sc


class TestNormalizeDate(unittest.TestCase):
    """Tests for normalize_date."""

    def test_normalize_date_valid_iso(self):
        """Test: ISO format."""
        result = sc.normalize_date("2024-01-15 14:30:00")
        self.assertEqual(result, "2024-01-15 14:30:00")

    def test_normalize_date_valid_italian(self):
        """Test: Italian month format."""
        result = sc.normalize_date("15 gen 2024 14:30:00")
        self.assertEqual(result, "2024-01-15 14:30:00")

    def test_normalize_date_valid_english(self):
        """Test: English month format."""
        result = sc.normalize_date("15 Jan 2024 14:30:00")
        self.assertEqual(result, "2024-01-15 14:30:00")

    def test_normalize_date_with_utc(self):
        """Test: removes UTC suffix."""
        result = sc.normalize_date("2024-01-15 14:30:00 UTC")
        self.assertEqual(result, "2024-01-15 14:30:00")

    def test_normalize_date_with_timezone(self):
        """Test: removes timezone offset."""
        result = sc.normalize_date("2024-01-15 14:30:00+02:00")
        self.assertEqual(result, "2024-01-15 14:30:00")

    def test_normalize_date_none(self):
        """Test: None as input."""
        result = sc.normalize_date(None)
        self.assertIsNone(result)

    def test_normalize_date_empty(self):
        """Test: empty string."""
        result = sc.normalize_date("")
        self.assertIsNone(result)

    def test_normalize_date_invalid(self):
        """Test: invalid date."""
        result = sc.normalize_date("not-a-date")
        self.assertIsNone(result)


class TestGetExifDate(unittest.TestCase):
    """Tests for get_exif_date."""

    def test_get_exif_date_nonexistent_file(self):
        """Test: non-existent file."""
        result = sc.get_exif_date("/nonexistent/file.jpg")
        self.assertEqual(result, (None, False))


class TestGetJsonDate(unittest.TestCase):
    """Tests for get_json_date."""

    def setUp(self):
        """Create temporary files."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_dir = os.getcwd()
        os.chdir(self.temp_dir)

    def tearDown(self):
        """Clean."""
        os.chdir(self.original_dir)
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_json_date_with_valid_json(self):
        """Test: file valid JSON with photoTakenTime."""
        json_file = Path("test.jpg.supplemental-metadata.json")
        json_file.write_text(
            json.dumps({
                "photoTakenTime": {
                    "formatted": "2024-01-15 14:30:00"
                }
            })
        )
        result = sc.get_json_date("test.jpg")
        self.assertEqual(result, "2024-01-15 14:30:00")

    def test_get_json_date_with_italian_month(self):
        """Test: JSON with Italian month."""
        json_file = Path("test.jpg.supplemental-metadata.json")
        json_file.write_text(
            json.dumps({
                "photoTakenTime": {
                    "formatted": "15 gen 2024 12:00:00"
                }
            })
        )
        result = sc.get_json_date("test.jpg")
        self.assertEqual(result, "2024-01-15 12:00:00")

    def test_get_json_date_nonexistent_json(self):
        """Test: non-existent JSON file."""
        result = sc.get_json_date("nonexistent.jpg")
        self.assertIsNone(result)

    def test_get_json_date_invalid_json(self):
        """Test: invalid JSON."""
        json_file = Path("test.jpg.supplemental-metadata.json")
        json_file.write_text("{ invalid json")
        result = sc.get_json_date("test.jpg")
        self.assertIsNone(result)


class TestExtractDateFromFilename(unittest.TestCase):
    """Tests for extract_date_from_filename."""

    def test_google_photos_format(self):
        """Test: Google Photos format _YYYY-MM-DD_at_HH.MM.SS."""
        result = sc.extract_date_from_filename("IMG_2024-01-15_at_14.30.00.jpg")
        self.assertEqual(result, "2024-01-15 14:30:00")

    def test_whatsapp_format(self):
        """Test: WhatsApp format -YYYYMMDD-WA."""
        result = sc.extract_date_from_filename("IMG-20240115-WA0001.jpg")
        self.assertEqual(result, "2024-01-15 12:00:00")

    def test_yyymmdd_hhmmss_format(self):
        """Test: YYYYMMDD format_HHMMSS."""
        result = sc.extract_date_from_filename("20240115_143000.jpg")
        self.assertEqual(result, "2024-01-15 14:30:00")

    def test_yyyy_mm_dd_format(self):
        """Test: YYYY-MM-DD format."""
        result = sc.extract_date_from_filename("2024-01-15_photo.jpg")
        self.assertEqual(result, "2024-01-15 12:00:00")

    def test_no_date(self):
        """Test: filename without date."""
        result = sc.extract_date_from_filename("photo.jpg")
        self.assertIsNone(result)


class TestExtractDateFromFolder(unittest.TestCase):
    """Tests for extract_date_from_folder."""

    def test_folder_with_year(self):
        """Test: folder with format 'Foto da YYYY'."""
        result = sc.extract_date_from_folder("/path/Foto da 2024/photo.jpg")
        self.assertEqual(result, "2024-01-01 12:00:00")

    def test_folder_without_year(self):
        """Test: folder without format year."""
        result = sc.extract_date_from_folder("/path/Other/photo.jpg")
        self.assertIsNone(result)


class TestGetCurrentFileDate(unittest.TestCase):
    """Tests for get_current_file_date."""

    def setUp(self):
        """Create temporary file."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test.txt"
        self.test_file.touch()
        self.original_dir = os.getcwd()
        os.chdir(self.temp_dir)

    def tearDown(self):
        """Clean."""
        os.chdir(self.original_dir)
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_current_file_date_exists(self):
        """Test: existing file."""
        result = sc.get_current_file_date(str(self.test_file))
        # Should return a valid date
        self.assertIsNotNone(result)
        # Correct format
        self.assertRegex(result, r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")

    def test_get_current_file_date_nonexistent(self):
        """Test: non-existent file."""
        result = sc.get_current_file_date("/nonexistent/file.txt")
        self.assertIsNone(result)


class TestSetFileCreationDate(unittest.TestCase):
    """Tests for set_file_creation_date."""

    def setUp(self):
        """Create temporary file."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test.txt"
        self.test_file.touch()
        self.original_dir = os.getcwd()
        os.chdir(self.temp_dir)

    def tearDown(self):
        """Clean."""
        os.chdir(self.original_dir)
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_set_file_creation_date_success(self):
        """Test: sets date successfully."""
        success, error = sc.set_file_creation_date(str(self.test_file), "2024-01-15 12:00:00")
        self.assertTrue(success)
        self.assertIsNone(error)


class TestResolveCreationDate(unittest.TestCase):
    """Tests for resolve_creation_date."""

    def setUp(self):
        """Prepara ambiente test."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_dir = os.getcwd()
        os.chdir(self.temp_dir)

    def tearDown(self):
        """Clean."""
        os.chdir(self.original_dir)
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_resolve_creation_date_from_filename(self):
        """Test: date from filename."""
        test_file = Path("2024-01-15_photo.jpg")
        test_file.touch()
        result, source = sc.resolve_creation_date(str(test_file), "2024-01-15_photo.jpg")
        self.assertEqual(result, "2024-01-15 12:00:00")
        self.assertEqual(source, "FILENAME used")

    def test_resolve_creation_date_from_folder(self):
        """Test: date from folder name."""
        subdir = Path("Foto da 2024")
        subdir.mkdir()
        test_file = subdir / "photo.jpg"
        test_file.touch()
        result, source = sc.resolve_creation_date(str(test_file), "photo.jpg")
        self.assertEqual(result, "2024-01-01 12:00:00")
        self.assertEqual(source, "FOLDER DATE used")

    def test_resolve_creation_date_no_source(self):
        """Test: nessuna data trovata."""
        test_file = Path("photo.jpg")
        test_file.touch()
        result, source = sc.resolve_creation_date(str(test_file), "photo.jpg")
        self.assertIsNone(result)
        self.assertEqual(source, "")


class TestBuildOutputLine(unittest.TestCase):
    """Tests for build_output_line."""

    def test_build_output_line_full(self):
        """Test: tutte le informazioni presenti."""
        result = sc.build_output_line(
            filename="photo.jpg",
            json_date="2024-01-15 12:00:00",
            creation_date="2024-01-15 12:00:00",
            source="EXIF used",
            current_date="2024-01-14 10:00:00"
        )
        self.assertIn("photo.jpg", result)
        self.assertIn("EXIF used", result)
        self.assertIn("2024-01-15 12:00:00", result)

    def test_build_output_line_missing_data(self):
        """Test: dati mancanti."""
        result = sc.build_output_line(
            filename="photo.jpg",
            json_date=None,
            creation_date=None,
            source="",
            current_date=None
        )
        self.assertIn("photo.jpg", result)
        self.assertIn("NO DATE", result)
        self.assertIn("JSON data missing", result)


class TestReadFileList(unittest.TestCase):
    """Tests for la funzione read_file_list."""

    def setUp(self):
        """Create temporary files per i test."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test_list.lst"

    def tearDown(self):
        """Clean i temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_read_file_list_simple(self):
        """Test: lista con solo nomi file, uno per riga."""
        self.test_file.write_text("foto1.jpg\nfoto2.png\n")
        result = sc.read_file_list(str(self.test_file))
        self.assertEqual(result, ["foto1.jpg", "foto2.png"])

    def test_read_file_list_with_proton_format(self):
        """Test: lista nel formato Proton (data, dimensione, nome)."""
        content = "Sep 12 2026 10:46 934.48 KiB DSCN9941.JPG\n"
        content += "Sep 12 2026 13:22 379.93 KiB DSCN9829.JPG\n"
        self.test_file.write_text(content)
        result = sc.read_file_list(str(self.test_file))
        self.assertEqual(result, ["DSCN9941.JPG", "DSCN9829.JPG"])

    def test_read_file_list_empty_lines(self):
        """Test: salta righe vuote."""
        self.test_file.write_text("foto1.jpg\n\nfoto2.png\n\n")
        result = sc.read_file_list(str(self.test_file))
        self.assertEqual(result, ["foto1.jpg", "foto2.png"])

    def test_read_file_list_nonexistent_file(self):
        """Test: non-existent file solleva errore."""
        with self.assertRaises(FileNotFoundError):
            sc.read_file_list("/nonexistent/path/file.lst")


class TestFindFilesByNames(unittest.TestCase):
    """Tests for la funzione find_files_by_names."""

    def setUp(self):
        """Create struttura file temporanea per test."""
        self.temp_dir = tempfile.mkdtemp()

        Path(self.temp_dir, "foto1.jpg").touch()
        Path(self.temp_dir, "foto2.png").touch()

        subdir = Path(self.temp_dir) / "subdir"
        subdir.mkdir()
        Path(subdir, "foto1.jpg").touch()
        Path(subdir, "foto3.jpg").touch()

        self.original_dir = os.getcwd()
        os.chdir(self.temp_dir)

    def tearDown(self):
        """Clean."""
        os.chdir(self.original_dir)
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_find_files_by_names_single_match(self):
        """Test: trova file con nome esatto."""
        result = sc.find_files_by_names(["foto1.jpg"])
        self.assertTrue(any("foto1.jpg" in f for f in result))
        self.assertEqual(len([f for f in result if "foto1.jpg" in f]), 2)

    def test_find_files_by_names_no_match(self):
        """Test: no files found."""
        result = sc.find_files_by_names(["nonexistent.jpg"])
        self.assertEqual(result, [])

    def test_find_files_by_names_multiple(self):
        """Test: trova piu' file."""
        result = sc.find_files_by_names(["foto1.jpg", "foto2.png"])
        self.assertEqual(len(result), 3)


class TestCollectFiles(unittest.TestCase):
    """Tests for la funzione collect_files."""

    def setUp(self):
        """Create struttura file temporanea."""
        self.temp_dir = tempfile.mkdtemp()

        Path(self.temp_dir, "foto1.jpg").touch()
        Path(self.temp_dir, "video.mp4").touch()
        Path(self.temp_dir, "script.py").touch()

        self.list_file = Path(self.temp_dir) / "filelist.lst"
        self.list_file.write_text("foto1.jpg\nvideo.mp4\n")

        self.original_dir = os.getcwd()
        os.chdir(self.temp_dir)

    def tearDown(self):
        """Clean."""
        os.chdir(self.original_dir)
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_collect_files_normal_mode(self):
        """Test: modalita' normale raccoglie tutti i file supportati."""
        result = sc.collect_files(from_list=False, file_list=None)
        self.assertTrue(any("foto1.jpg" in f for f in result))
        self.assertTrue(any("video.mp4" in f for f in result))
        self.assertFalse(any("script.py" in f for f in result))

    def test_collect_files_list_mode(self):
        """Test: modalita' con lista usa la lista."""
        result = sc.collect_files(from_list=True, file_list=str(self.list_file))
        self.assertTrue(any("foto1.jpg" in f for f in result))
        self.assertTrue(any("video.mp4" in f for f in result))


class TestSetExifCreationDate(unittest.TestCase):
    """Tests for set_exif_creation_date."""

    def test_set_exif_creation_date_calls_exiftool(self):
        """Test: verifica che chiami exiftool con i parametri corretti."""
        from unittest.mock import patch, MagicMock

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

            success, error = sc.set_exif_creation_date("/fake/path.jpg", "2024-01-01 12:00:00")

            self.assertTrue(success)
            self.assertIsNone(error)
            mock_run.assert_called_once_with(
                [
                    "exiftool",
                    "-overwrite_original",
                    "-CreateDate=2024-01-01 12:00:00",
                    "-CreationDate=2024-01-01 12:00:00",
                    "-DateTimeOriginal=2024-01-01 12:00:00",
                    "-MediaCreateDate=2024-01-01 12:00:00",
                    "/fake/path.jpg",
                ],
                check=True,
                timeout=10,
                capture_output=True
            )

    def test_set_exif_creation_date_fails(self):
        """Test: gestisce l'errore di exiftool."""
        from unittest.mock import patch
        import subprocess

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "exiftool")

            success, error = sc.set_exif_creation_date("/fake/path.jpg", "2024-01-01 12:00:00")

            self.assertFalse(success)
            self.assertIsNotNone(error)


class TestExifVerifytion(unittest.TestCase):
    """Tests for la verifica dei tag EXIF dopo la modifica."""

    def setUp(self):
        """Create temporary files."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test.jpg"
        self.test_file.touch()
        self.log_file = Path(self.temp_dir) / "creation_date.log"
        self.original_dir = os.getcwd()
        os.chdir(self.temp_dir)

    def tearDown(self):
        """Clean."""
        os.chdir(self.original_dir)
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("proton_drive_gts.get_current_file_date")
    @patch("proton_drive_gts.subprocess.run")
    @patch("proton_drive_gts.get_exif_date")
    def test_verify_exif_tags_modified(self, mock_get_exif, mock_run, mock_get_current):
        """Test: verifica che il log contenga INFO se i tag sono stati modificati."""
        from unittest.mock import MagicMock
        from io import StringIO

        mock_get_exif.return_value = ("2024-01-01 12:00:00", True)
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
        mock_get_current.return_value = "2024-01-01 12:00:00"

        list_file = Path(self.temp_dir) / "filelist.lst"
        list_file.write_text("test.jpg")

        with patch("sys.argv", ["proton_drive_gts.py", "--set", "--file-list", str(list_file)]):
            with patch("sys.stdout", new_callable=StringIO):
                sc.main()

        with open(self.log_file, "r") as f:
            content = f.read()
        self.assertIn("INFO", content)
        self.assertIn("FROM_LIST", content)

    @patch("proton_drive_gts.get_current_file_date")
    @patch("proton_drive_gts.subprocess.run")
    @patch("proton_drive_gts.get_exif_date")
    def test_verify_exif_tags_not_modified(self, mock_get_exif, mock_run, mock_get_current):
        """Test: verifica che il log contenga ERROR se i tag non sono stati modificati."""
        from unittest.mock import MagicMock
        from io import StringIO

        # First call (resolve_creation_date): returns the date we want to set
        # Second call (verification): returns a DIFFERENT date
        mock_get_exif.side_effect = [
            ("2024-01-01 12:00:00", True),  # creation_date
            ("2023-01-01 12:00:00", True),  # date after modification (different)
        ]
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
        mock_get_current.return_value = "2024-01-01 12:00:00"

        list_file = Path(self.temp_dir) / "filelist.lst"
        list_file.write_text("test.jpg")

        with patch("sys.argv", ["proton_drive_gts.py", "--set", "--file-list", str(list_file)]):
            with patch("sys.stdout", new_callable=StringIO):
                sc.main()

        with open(self.log_file, "r") as f:
            content = f.read()
        self.assertIn("ERROR", content)
        self.assertIn("FROM_LIST", content)


class TestBothSetters(unittest.TestCase):
    """Tests for verifica che entrambi i setter (EXIF e filesystem) vengano chiamati."""

    def setUp(self):
        """Create temporary files."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "2024-01-15_test.jpg"
        self.test_file.touch()
        self.list_file = Path(self.temp_dir) / "filelist.lst"
        self.list_file.write_text("2024-01-15_test.jpg")
        self.original_dir = os.getcwd()
        os.chdir(self.temp_dir)

    def tearDown(self):
        """Clean."""
        os.chdir(self.original_dir)
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("proton_drive_gts.get_exif_date")
    @patch("proton_drive_gts.resolve_creation_date")  # pylint: disable=line-too-long
    @patch("proton_drive_gts.get_current_file_date")
    @patch("proton_drive_gts.subprocess.run")
    def test_both_setters_called_with_file_list(
        self, mock_run, mock_get_current, mock_resolve, mock_get_exif
    ):
        """Test: verifica che entrambi i setter vengano chiamati con --file-list."""
        from unittest.mock import MagicMock
        from io import StringIO

        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
        mock_resolve.return_value = ("2024-01-15 12:00:00", "FILENAME used")
        mock_get_current.return_value = "2024-01-14 10:00:00"
        mock_get_exif.return_value = ("2024-01-15 12:00:00", True)

        with patch(
            "sys.argv",
            ["proton_drive_gts.py", "--set", "--file-list", str(self.list_file)]
        ):
            with patch("sys.stdout", new_callable=StringIO):
                sc.main()

        has_exiftool = any(c[0][0][0] == "exiftool" for c in mock_run.call_args_list)
        has_touch = any(c[0][0][0] == "touch" for c in mock_run.call_args_list)

        self.assertTrue(has_exiftool, "exiftool non chiamato")
        self.assertTrue(has_touch, "touch non chiamato")

    @patch("proton_drive_gts.get_exif_date")
    @patch("proton_drive_gts.resolve_creation_date")  # pylint: disable=line-too-long
    @patch("proton_drive_gts.get_current_file_date")
    @patch("proton_drive_gts.subprocess.run")
    def test_both_setters_called_without_file_list(
        self, mock_run, mock_get_current, mock_resolve, mock_get_exif
    ):
        """Test: verifica che entrambi i setter vengano chiamati senza --file-list."""
        from unittest.mock import MagicMock
        from io import StringIO

        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
        mock_resolve.return_value = ("2024-01-15 12:00:00", "FILENAME used")
        mock_get_current.return_value = "2024-01-14 10:00:00"
        mock_get_exif.return_value = ("2024-01-15 12:00:00", True)

        with patch("sys.argv", ["proton_drive_gts.py", "--set"]):
            with patch("sys.stdout", new_callable=StringIO):
                sc.main()

        has_exiftool = any(c[0][0][0] == "exiftool" for c in mock_run.call_args_list)
        has_touch = any(c[0][0][0] == "touch" for c in mock_run.call_args_list)

        self.assertTrue(has_exiftool, "exiftool non chiamato")
        self.assertTrue(has_touch, "touch non chiamato")


class TestDryRun(unittest.TestCase):
    """Tests for la modalita' --dry-run."""

    def setUp(self):
        """Create temporary file."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test.jpg"
        self.test_file.touch()
        self.original_dir = os.getcwd()
        os.chdir(self.temp_dir)

    def tearDown(self):
        """Clean."""
        os.chdir(self.original_dir)
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_dry_run_does_not_modify_filesystem(self):
        """Test: --dry-run non modifica il filesystem."""
        from unittest.mock import patch, MagicMock
        from io import StringIO
        import sys

        original_stat = os.stat(str(self.test_file))

        with patch("sys.argv", ["proton_drive_gts.py", "--set", "--dry-run"]):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                sc.main()
                output = mock_stdout.getvalue()

        new_stat = os.stat(str(self.test_file))
        self.assertEqual(original_stat.st_mtime, new_stat.st_mtime)

    def test_dry_run_shows_action(self):
        """Test: --dry-run mostra l'azione che verra' eseguita."""
        from unittest.mock import patch
        from io import StringIO

        # Create file with date in name
        test_file_with_date = Path(self.temp_dir) / "2024-01-15_test.jpg"
        test_file_with_date.touch()

        list_file = Path(self.temp_dir) / "filelist.lst"
        list_file.write_text("2024-01-15_test.jpg")

        with patch("sys.argv", ["proton_drive_gts.py", "--set", "--dry-run", "--file-list", str(list_file)]):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                sc.main()
                output = mock_stdout.getvalue()

        self.assertIn("DRY-RUN", output)
        self.assertIn("2024-01-15_test.jpg", output)


class TestLogFile(unittest.TestCase):
    """Tests for il file di log."""

    def setUp(self):
        """Create temporary files."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "2024-01-15_test.jpg"
        self.test_file.touch()
        self.log_file = Path(self.temp_dir) / "creation_date.log"
        self.original_dir = os.getcwd()
        os.chdir(self.temp_dir)

    def tearDown(self):
        """Clean."""
        os.chdir(self.original_dir)
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_log_file_created(self):
        """Test: file di log creato quando si esegue --set."""
        from io import StringIO
        with patch("sys.argv", ["proton_drive_gts.py", "--set"]):
            with patch("sys.stdout", new_callable=StringIO):
                sc.main()
        self.assertTrue(self.log_file.exists())

    def test_log_file_csv_format(self):
        """Test: formato CSV corretto con log level."""
        from io import StringIO
        with patch("sys.argv", ["proton_drive_gts.py", "--set"]):
            with patch("sys.stdout", new_callable=StringIO):
                sc.main()

        with open(self.log_file, "r") as f:
            lines = f.readlines()

        self.assertEqual(len(lines), 2)
        header = lines[0].strip()
        self.assertEqual(header, "timestamp,log_level,operation,file,date_type_used,original_date,new_date")

    def test_log_level_info_on_success(self):
        """Test: log level INFO per operazioni di successo."""
        from unittest.mock import patch, MagicMock
        from io import StringIO

        with patch("proton_drive_gts.resolve_creation_date") as mock_resolve, \
             patch("proton_drive_gts.get_current_file_date") as mock_get_current, \
             patch("proton_drive_gts.get_exif_date") as mock_get_exif, \
             patch("proton_drive_gts.subprocess.run") as mock_run:

            mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
            mock_resolve.return_value = ("2024-01-15 12:00:00", "FILENAME used")
            mock_get_current.return_value = "2024-01-15 12:00:00"
            mock_get_exif.return_value = ("2024-01-15 12:00:00", True)

            with patch("sys.argv", ["proton_drive_gts.py", "--set"]):
                with patch("sys.stdout", new_callable=StringIO):
                    sc.main()

        with open(self.log_file, "r") as f:
            lines = f.readlines()
        self.assertIn("INFO", lines[1])

    def test_log_file_append_mode(self):
        """Test: file in modalita' append."""
        from io import StringIO

        # First execution
        with patch("sys.argv", ["proton_drive_gts.py", "--set"]):
            with patch("sys.stdout", new_callable=StringIO):
                sc.main()

        first_size = self.log_file.stat().st_size

        # Second execution
        with patch("sys.argv", ["proton_drive_gts.py", "--set"]):
            with patch("sys.stdout", new_callable=StringIO):
                sc.main()

        self.assertGreater(self.log_file.stat().st_size, first_size)

    def test_log_file_list_operation(self):
        """Test: operazione FROM_LIST per modalita' con lista."""
        from io import StringIO
        list_file = Path(self.temp_dir) / "filelist.lst"
        list_file.write_text("2024-01-15_test.jpg")

        with patch("sys.argv", ["proton_drive_gts.py", "--set", "--file-list", str(list_file)]):
            with patch("sys.stdout", new_callable=StringIO):
                sc.main()

        with open(self.log_file, "r") as f:
            lines = f.readlines()
        self.assertIn("FROM_LIST", lines[1])

    def test_log_file_walk_operation(self):
        """Test: operazione FROM_WALK per modalita' normale."""
        from io import StringIO
        with patch("sys.argv", ["proton_drive_gts.py", "--set"]):
            with patch("sys.stdout", new_callable=StringIO):
                sc.main()

        with open(self.log_file, "r") as f:
            lines = f.readlines()
        self.assertIn("FROM_WALK", lines[1])


class TestCtrlC(unittest.TestCase):
    """Tests for la gestione di Ctrl+C (SIGINT)."""

    @patch("signal.signal")
    def test_ctrl_c_handler_registered(self, mock_signal):
        """Test: verifica che il programma registri un handler per SIGINT."""
        import importlib
        importlib.reload(sc)

        # Verify that signal.signal was called for SIGINT
        self.assertTrue(any(
            call[0][0] == signal.SIGINT
            for call in mock_signal.call_args_list
        ))


class TestMoveJson(unittest.TestCase):
    """Tests for lo switch --move-json."""

    def setUp(self):
        """Create struttura temporanea per test."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_dir = os.getcwd()
        os.chdir(self.temp_dir)

        # Create directory similar to Google Photos
        Path("Google Foto").mkdir()
        Path("Google Foto/subdir1").mkdir()
        Path("Google Foto/subdir2").mkdir()
        Path("Google Photo").mkdir()

        # Create JSON files
        Path("Google Foto/file1.jpg.supplemental-metadata.json").touch()
        Path("Google Foto/subdir1/file2.jpg.supplemental-metadata.json").touch()
        Path("Google Photo/file3.jpg.supplemental-metadata.json").touch()

    def tearDown(self):
        """Clean."""
        os.chdir(self.original_dir)
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_move_json_creates_metadata_dir(self):
        """Test: verifica che venga creato google_takeout_metadata."""
        with patch("sys.argv", ["proton_drive_gts.py", "--move-json"]):
            with patch("sys.stdout", new_callable=StringIO):
                sc.main()

        metadata_dir = Path("google_takeout_metadata")
        self.assertTrue(metadata_dir.exists())
        self.assertTrue(metadata_dir.is_dir())

    def test_move_json_creates_data_lst(self):
        """Test: verifica che venga creato google_takeout_metadata/data.lst."""
        with patch("sys.argv", ["proton_drive_gts.py", "--move-json"]):
            with patch("sys.stdout", new_callable=StringIO):
                sc.main()

        data_file = Path("google_takeout_metadata/data.lst")
        self.assertTrue(data_file.exists())
        self.assertTrue(data_file.is_file())

    def test_move_json_data_lst_format(self):
        """Test: verifica formato di data.lst: PATH_ORIGINALE NOME_FILE.json."""
        with patch("sys.argv", ["proton_drive_gts.py", "--move-json"]):
            with patch("sys.stdout", new_callable=StringIO):
                sc.main()

        data_file = Path("google_takeout_metadata/data.lst")
        content = data_file.read_text()

        # Verify that expected lines exist
        expected_entries = [
            "Google Foto/file1.jpg.supplemental-metadata.json",
            "Google Foto/subdir1/file2.jpg.supplemental-metadata.json",
            "Google Photo/file3.jpg.supplemental-metadata.json",
        ]

        for entry in expected_entries:
            self.assertIn(entry, content)

    def test_move_json_dry_run_does_not_move_files(self):
        """Test: --move-json --dry-run NON spostano i file JSON."""
        # Store original paths
        original_json_files = [
            Path("Google Foto/file1.jpg.supplemental-metadata.json"),
            Path("Google Foto/subdir1/file2.jpg.supplemental-metadata.json"),
            Path("Google Photo/file3.jpg.supplemental-metadata.json"),
        ]

        # Verify they exist
        for f in original_json_files:
            self.assertTrue(f.exists())

        with patch("sys.argv", ["proton_drive_gts.py", "--move-json", "--dry-run"]):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                sc.main()
                output = mock_stdout.getvalue()

        # Verify files were NOT moved
        for f in original_json_files:
            self.assertTrue(f.exists(), f"File {f} was moved but should not have been")

        # Verify output contains DRY-RUN
        self.assertIn("DRY-RUN", output)

    def test_move_json_dry_run_shows_actions(self):
        """Test: --move-json --dry-run mostra le azioni che verranno eseguite."""
        with patch("sys.argv", ["proton_drive_gts.py", "--move-json", "--dry-run"]):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                sc.main()
                output = mock_stdout.getvalue()

        # Verify it shows move actions
        self.assertIn("DRY-RUN", output)
        self.assertIn("->", output)  # Move symbol

    def test_rollback_json_dry_run_does_not_move_files(self):
        """Test: --rollback-json --dry-run NON spostano i file JSON."""
        # Create google_takeout_metadata directory with JSON files
        metadata_dir = Path("google_takeout_metadata")
        metadata_dir.mkdir()
        Path(metadata_dir, "file1.jpg.supplemental-metadata.json").touch()
        Path(metadata_dir, "file2.jpg.supplemental-metadata.json").touch()

        # Create data.lst
        data_file = metadata_dir / "data.lst"
        data_file.write_text('"Google Foto/file1.jpg.supplemental-metadata.json" "file1.jpg.supplemental-metadata.json"\n')
        data_file.write_text('"Google Foto/file2.jpg.supplemental-metadata.json" "file2.jpg.supplemental-metadata.json"\n')

        # Store paths
        json_files_in_metadata = [
            Path(metadata_dir, "file1.jpg.supplemental-metadata.json"),
            Path(metadata_dir, "file2.jpg.supplemental-metadata.json"),
        ]

        # Verify they exist
        for f in json_files_in_metadata:
            self.assertTrue(f.exists())

        with patch("sys.argv", ["proton_drive_gts.py", "--rollback-json", "--dry-run"]):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                sc.main()
                output = mock_stdout.getvalue()

        # Verify files were NOT moved
        for f in json_files_in_metadata:
            self.assertTrue(f.exists(), f"File {f} was moved but should not have been")

        # Verify output contains DRY-RUN
        self.assertIn("DRY-RUN", output)

    def test_rollback_json_dry_run_shows_actions(self):
        """Test: --rollback-json --dry-run mostra le azioni che verranno eseguite."""
        # Create google_takeout_metadata directory with JSON files
        metadata_dir = Path("google_takeout_metadata")
        metadata_dir.mkdir()
        Path(metadata_dir, "file1.jpg.supplemental-metadata.json").touch()

        # Create data.lst
        data_file = metadata_dir / "data.lst"
        data_file.write_text('"Google Foto/file1.jpg.supplemental-metadata.json" "file1.jpg.supplemental-metadata.json"\n')

        with patch("sys.argv", ["proton_drive_gts.py", "--rollback-json", "--dry-run"]):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                sc.main()
                output = mock_stdout.getvalue()

        # Verify che mostri le azioni di rollback
        self.assertIn("DRY-RUN", output)
        self.assertIn("->", output)

    def test_move_json_moves_files_to_metadata_dir(self):
        """Test: --move-json SENZA dry-run sposta effettivamente i file JSON in google_takeout_metadata/."""
        # Store original paths
        original_json_files = [
            Path("Google Foto/file1.jpg.supplemental-metadata.json"),
            Path("Google Foto/subdir1/file2.jpg.supplemental-metadata.json"),
            Path("Google Photo/file3.jpg.supplemental-metadata.json"),
        ]

        # Verify they exist
        for f in original_json_files:
            self.assertTrue(f.exists())

        with patch("sys.argv", ["proton_drive_gts.py", "--move-json"]):
            with patch("sys.stdout", new_callable=StringIO):
                sc.main()

        # Verify che i file siano stati spostati in google_takeout_metadata/
        metadata_dir = Path("google_takeout_metadata")
        for f in original_json_files:
            moved_file = metadata_dir / f.name
            self.assertTrue(moved_file.exists(), f"File {f} was NOT moved to {moved_file}")
            self.assertFalse(f.exists(), f"File {f} is still in original position")

    def test_rollback_json_restores_files(self):
        """Test: --rollback-json SENZA dry-run ripristina effettivamente i file JSON."""
        # Create google_takeout_metadata directory with JSON files UNIVOCI
        metadata_dir = Path("google_takeout_metadata")
        metadata_dir.mkdir(exist_ok=True)
        # Use unique filenames to avoid conflicts with setUp
        Path(metadata_dir, "rollback_test_file1.json").touch()
        Path(metadata_dir, "rollback_test_file2.json").touch()

        # Create directory di destinazione univoca
        unique_dir = Path("RollbackTestDir")
        unique_dir.mkdir(exist_ok=True)

        # Create data.lst con path ASSOLUTI (come fa move_json_files)
        data_file = metadata_dir / "data.lst"
        dest_path1 = (unique_dir / "rollback_test_file1.json").resolve()
        dest_path2 = (unique_dir / "rollback_test_file2.json").resolve()
        data_file.write_text(f'"{dest_path1}" "rollback_test_file1.json"\n"{dest_path2}" "rollback_test_file2.json"\n')

        # Verify che i file siano in metadata_dir
        self.assertTrue((metadata_dir / "rollback_test_file1.json").exists())
        self.assertTrue((metadata_dir / "rollback_test_file2.json").exists())

        with patch("sys.argv", ["proton_drive_gts.py", "--rollback-json"]):
            with patch("sys.stdout", new_callable=StringIO):
                sc.main()

        # Verify che i file siano stati ripristinati
        self.assertTrue(dest_path1.exists(), "File rollback_test_file1.json was NOT restored")
        self.assertTrue(dest_path2.exists(), "File rollback_test_file2.json was NOT restored")
        # Verify that they no longer exist in metadata_dir
        self.assertFalse((metadata_dir / "rollback_test_file1.json").exists(), "File rollback_test_file1.json is still in metadata_dir")
        self.assertFalse((metadata_dir / "rollback_test_file2.json").exists(), "File rollback_test_file2.json is still in metadata_dir")

    def test_move_json_creates_correct_data_lst_and_moves(self):
        """Test: --move-json crea data.lst corretto E sposta i file."""
        with patch("sys.argv", ["proton_drive_gts.py", "--move-json"]):
            with patch("sys.stdout", new_callable=StringIO):
                sc.main()

        data_file = Path("google_takeout_metadata/data.lst")
        self.assertTrue(data_file.exists())

        content = data_file.read_text()
        expected_entries = [
            "Google Foto/file1.jpg.supplemental-metadata.json",
            "Google Foto/subdir1/file2.jpg.supplemental-metadata.json",
            "Google Photo/file3.jpg.supplemental-metadata.json",
        ]

        for entry in expected_entries:
            self.assertIn(entry, content)

        # Verify che i file siano stati spostati
        metadata_dir = Path("google_takeout_metadata")
        for entry in expected_entries:
            filename = Path(entry).name
            moved_file = metadata_dir / filename
            self.assertTrue(moved_file.exists(), f"File {filename} NON spostato in {moved_file}")


class TestLoggingMoveAndRollback(unittest.TestCase):
    """Tests for verificare che --move-json e --rollback-json scrivano nel log."""

    def setUp(self):
        """Create struttura temporanea per test."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_dir = os.getcwd()
        os.chdir(self.temp_dir)

        Path("Google Foto").mkdir()
        Path("Google Foto/file1.jpg.supplemental-metadata.json").touch()

        self.log_file = Path("creation_date.log")
        if self.log_file.exists():
            self.log_file.unlink()

    def tearDown(self):
        """Clean."""
        os.chdir(self.original_dir)
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_move_json_writes_to_log(self):
        """Test: --move-json scrive nel log creation_date.log."""
        with patch("sys.argv", ["proton_drive_gts.py", "--move-json"]):
            with patch("sys.stdout", new_callable=StringIO):
                sc.main()

        self.assertTrue(self.log_file.exists(), "Log file non creato")

        with open(self.log_file, "r") as f:
            content = f.read()

        self.assertIn("MOVE_JSON", content, "Log non contiene operazione MOVE_JSON")
        self.assertIn("Google Foto", content, "Log non contiene path originale")

    def test_rollback_json_writes_to_log(self):
        """Test: --rollback-json scrive nel log creation_date.log."""
        metadata_dir = Path("google_takeout_metadata")
        metadata_dir.mkdir()
        Path(metadata_dir, "file1.jpg.supplemental-metadata.json").touch()

        data_file = metadata_dir / "data.lst"
        data_file.write_text('"Google Foto/file1.jpg.supplemental-metadata.json" "file1.jpg.supplemental-metadata.json"\n')

        with patch("sys.argv", ["proton_drive_gts.py", "--rollback-json"]):
            with patch("sys.stdout", new_callable=StringIO):
                sc.main()

        self.assertTrue(self.log_file.exists(), "Log file non creato")

        with open(self.log_file, "r") as f:
            content = f.read()

        self.assertIn("ROLLBACK_JSON", content, "Log non contiene operazione ROLLBACK_JSON")


if __name__ == "__main__":
    unittest.main()
