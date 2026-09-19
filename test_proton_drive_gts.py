#!/usr/bin/env python3
"""Test per proton_drive_gts.py."""

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
    """Test per normalize_date."""

    def test_normalize_date_valid_iso(self):
        """Test: formato ISO standard."""
        result = sc.normalize_date("2024-01-15 14:30:00")
        self.assertEqual(result, "2024-01-15 14:30:00")

    def test_normalize_date_valid_italian(self):
        """Test: formato con mesi italiani."""
        result = sc.normalize_date("15 gen 2024 14:30:00")
        self.assertEqual(result, "2024-01-15 14:30:00")

    def test_normalize_date_valid_english(self):
        """Test: formato con mesi inglesi."""
        result = sc.normalize_date("15 Jan 2024 14:30:00")
        self.assertEqual(result, "2024-01-15 14:30:00")

    def test_normalize_date_with_utc(self):
        """Test: rimuove suffix UTC."""
        result = sc.normalize_date("2024-01-15 14:30:00 UTC")
        self.assertEqual(result, "2024-01-15 14:30:00")

    def test_normalize_date_with_timezone(self):
        """Test: rimuove timezone offset."""
        result = sc.normalize_date("2024-01-15 14:30:00+02:00")
        self.assertEqual(result, "2024-01-15 14:30:00")

    def test_normalize_date_none(self):
        """Test: None in input."""
        result = sc.normalize_date(None)
        self.assertIsNone(result)

    def test_normalize_date_empty(self):
        """Test: stringa vuota."""
        result = sc.normalize_date("")
        self.assertIsNone(result)

    def test_normalize_date_invalid(self):
        """Test: data non valida."""
        result = sc.normalize_date("not-a-date")
        self.assertIsNone(result)


class TestGetExifDate(unittest.TestCase):
    """Test per get_exif_date."""

    def test_get_exif_date_nonexistent_file(self):
        """Test: file non esistente."""
        result = sc.get_exif_date("/nonexistent/file.jpg")
        self.assertEqual(result, (None, False))


class TestGetJsonDate(unittest.TestCase):
    """Test per get_json_date."""

    def setUp(self):
        """Crea file temporanei."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_dir = os.getcwd()
        os.chdir(self.temp_dir)

    def tearDown(self):
        """Pulisce."""
        os.chdir(self.original_dir)
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_json_date_with_valid_json(self):
        """Test: file JSON valido con photoTakenTime."""
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
        """Test: JSON con mese in italiano."""
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
        """Test: file JSON non esistente."""
        result = sc.get_json_date("nonexistent.jpg")
        self.assertIsNone(result)

    def test_get_json_date_invalid_json(self):
        """Test: JSON non valido."""
        json_file = Path("test.jpg.supplemental-metadata.json")
        json_file.write_text("{ invalid json")
        result = sc.get_json_date("test.jpg")
        self.assertIsNone(result)


class TestExtractDateFromFilename(unittest.TestCase):
    """Test per extract_date_from_filename."""

    def test_google_photos_format(self):
        """Test: formato Google Foto _YYYY-MM-DD_at_HH.MM.SS."""
        result = sc.extract_date_from_filename("IMG_2024-01-15_at_14.30.00.jpg")
        self.assertEqual(result, "2024-01-15 14:30:00")

    def test_whatsapp_format(self):
        """Test: formato WhatsApp -YYYYMMDD-WA."""
        result = sc.extract_date_from_filename("IMG-20240115-WA0001.jpg")
        self.assertEqual(result, "2024-01-15 12:00:00")

    def test_yyymmdd_hhmmss_format(self):
        """Test: formato YYYYMMDD_HHMMSS."""
        result = sc.extract_date_from_filename("20240115_143000.jpg")
        self.assertEqual(result, "2024-01-15 14:30:00")

    def test_yyyy_mm_dd_format(self):
        """Test: formato YYYY-MM-DD."""
        result = sc.extract_date_from_filename("2024-01-15_photo.jpg")
        self.assertEqual(result, "2024-01-15 12:00:00")

    def test_no_date(self):
        """Test: nome file senza data."""
        result = sc.extract_date_from_filename("photo.jpg")
        self.assertIsNone(result)


class TestExtractDateFromFolder(unittest.TestCase):
    """Test per extract_date_from_folder."""

    def test_folder_with_year(self):
        """Test: cartella con formato 'Foto da YYYY'."""
        result = sc.extract_date_from_folder("/path/Foto da 2024/photo.jpg")
        self.assertEqual(result, "2024-01-01 12:00:00")

    def test_folder_without_year(self):
        """Test: cartella senza formato year."""
        result = sc.extract_date_from_folder("/path/Other/photo.jpg")
        self.assertIsNone(result)


class TestGetCurrentFileDate(unittest.TestCase):
    """Test per get_current_file_date."""

    def setUp(self):
        """Crea file temporaneo."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test.txt"
        self.test_file.touch()
        self.original_dir = os.getcwd()
        os.chdir(self.temp_dir)

    def tearDown(self):
        """Pulisce."""
        os.chdir(self.original_dir)
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_current_file_date_exists(self):
        """Test: file esistente."""
        result = sc.get_current_file_date(str(self.test_file))
        # Dovrebbe restituire una data valida
        self.assertIsNotNone(result)
        # Formato corretto
        self.assertRegex(result, r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")

    def test_get_current_file_date_nonexistent(self):
        """Test: file non esistente."""
        result = sc.get_current_file_date("/nonexistent/file.txt")
        self.assertIsNone(result)


class TestSetFileCreationDate(unittest.TestCase):
    """Test per set_file_creation_date."""

    def setUp(self):
        """Crea file temporaneo."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test.txt"
        self.test_file.touch()
        self.original_dir = os.getcwd()
        os.chdir(self.temp_dir)

    def tearDown(self):
        """Pulisce."""
        os.chdir(self.original_dir)
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_set_file_creation_date_success(self):
        """Test: imposta data con successo."""
        success, error = sc.set_file_creation_date(str(self.test_file), "2024-01-15 12:00:00")
        self.assertTrue(success)
        self.assertIsNone(error)


class TestResolveCreationDate(unittest.TestCase):
    """Test per resolve_creation_date."""

    def setUp(self):
        """Prepara ambiente test."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_dir = os.getcwd()
        os.chdir(self.temp_dir)

    def tearDown(self):
        """Pulisce."""
        os.chdir(self.original_dir)
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_resolve_creation_date_from_filename(self):
        """Test: data dal nome file."""
        test_file = Path("2024-01-15_photo.jpg")
        test_file.touch()
        result, source = sc.resolve_creation_date(str(test_file), "2024-01-15_photo.jpg")
        self.assertEqual(result, "2024-01-15 12:00:00")
        self.assertEqual(source, "FILENAME used")

    def test_resolve_creation_date_from_folder(self):
        """Test: data dal nome cartella."""
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
    """Test per build_output_line."""

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
    """Test per la funzione read_file_list."""

    def setUp(self):
        """Crea file temporanei per i test."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test_list.lst"

    def tearDown(self):
        """Pulisce i file temporanei."""
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
        """Test: file non esistente solleva errore."""
        with self.assertRaises(FileNotFoundError):
            sc.read_file_list("/nonexistent/path/file.lst")


class TestFindFilesByNames(unittest.TestCase):
    """Test per la funzione find_files_by_names."""

    def setUp(self):
        """Crea struttura file temporanea per test."""
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
        """Pulisce."""
        os.chdir(self.original_dir)
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_find_files_by_names_single_match(self):
        """Test: trova file con nome esatto."""
        result = sc.find_files_by_names(["foto1.jpg"])
        self.assertTrue(any("foto1.jpg" in f for f in result))
        self.assertEqual(len([f for f in result if "foto1.jpg" in f]), 2)

    def test_find_files_by_names_no_match(self):
        """Test: nessun file trovato."""
        result = sc.find_files_by_names(["nonexistent.jpg"])
        self.assertEqual(result, [])

    def test_find_files_by_names_multiple(self):
        """Test: trova piu' file."""
        result = sc.find_files_by_names(["foto1.jpg", "foto2.png"])
        self.assertEqual(len(result), 3)


class TestCollectFiles(unittest.TestCase):
    """Test per la funzione collect_files."""

    def setUp(self):
        """Crea struttura file temporanea."""
        self.temp_dir = tempfile.mkdtemp()
        
        Path(self.temp_dir, "foto1.jpg").touch()
        Path(self.temp_dir, "video.mp4").touch()
        Path(self.temp_dir, "script.py").touch()
        
        self.list_file = Path(self.temp_dir) / "filelist.lst"
        self.list_file.write_text("foto1.jpg\nvideo.mp4\n")
        
        self.original_dir = os.getcwd()
        os.chdir(self.temp_dir)

    def tearDown(self):
        """Pulisce."""
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
    """Test per set_exif_creation_date."""

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


class TestExifVerification(unittest.TestCase):
    """Test per la verifica dei tag EXIF dopo la modifica."""

    def setUp(self):
        """Crea file temporanei."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test.jpg"
        self.test_file.touch()
        self.log_file = Path(self.temp_dir) / "creation_date.log"
        self.original_dir = os.getcwd()
        os.chdir(self.temp_dir)

    def tearDown(self):
        """Pulisce."""
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

        # Prima chiamata (resolve_creation_date): restituisce la data che vogliamo impostare
        # Seconda chiamata (verifica): restituisce una data DIVERSA
        mock_get_exif.side_effect = [
            ("2024-01-01 12:00:00", True),  # creation_date
            ("2023-01-01 12:00:00", True),  # data dopo modifica (diversa)
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
    """Test per verifica che entrambi i setter (EXIF e filesystem) vengano chiamati."""

    def setUp(self):
        """Crea file temporanei."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "2024-01-15_test.jpg"
        self.test_file.touch()
        self.list_file = Path(self.temp_dir) / "filelist.lst"
        self.list_file.write_text("2024-01-15_test.jpg")
        self.original_dir = os.getcwd()
        os.chdir(self.temp_dir)

    def tearDown(self):
        """Pulisce."""
        os.chdir(self.original_dir)
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("proton_drive_gts.get_exif_date")
    @patch("proton_drive_gts.resolve_creation_date")
    @patch("proton_drive_gts.get_current_file_date")
    @patch("proton_drive_gts.subprocess.run")
    def test_both_setters_called_with_file_list(self, mock_run, mock_get_current, mock_resolve, mock_get_exif):
        """Test: verifica che entrambi i setter vengano chiamati con --file-list."""
        from unittest.mock import MagicMock
        from io import StringIO

        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
        mock_resolve.return_value = ("2024-01-15 12:00:00", "FILENAME used")
        mock_get_current.return_value = "2024-01-14 10:00:00"
        mock_get_exif.return_value = ("2024-01-15 12:00:00", True)

        with patch("sys.argv", ["proton_drive_gts.py", "--set", "--file-list", str(self.list_file)]):
            with patch("sys.stdout", new_callable=StringIO):
                sc.main()

        has_exiftool = any(c[0][0][0] == "exiftool" for c in mock_run.call_args_list)
        has_touch = any(c[0][0][0] == "touch" for c in mock_run.call_args_list)

        self.assertTrue(has_exiftool, "exiftool non chiamato")
        self.assertTrue(has_touch, "touch non chiamato")

    @patch("proton_drive_gts.get_exif_date")
    @patch("proton_drive_gts.resolve_creation_date")
    @patch("proton_drive_gts.get_current_file_date")
    @patch("proton_drive_gts.subprocess.run")
    def test_both_setters_called_without_file_list(self, mock_run, mock_get_current, mock_resolve, mock_get_exif):
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
    """Test per la modalita' --dry-run."""

    def setUp(self):
        """Crea file temporaneo."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test.jpg"
        self.test_file.touch()
        self.original_dir = os.getcwd()
        os.chdir(self.temp_dir)

    def tearDown(self):
        """Pulisce."""
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

        # Crea file con data nel nome
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
    """Test per il file di log."""

    def setUp(self):
        """Crea file temporanei."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "2024-01-15_test.jpg"
        self.test_file.touch()
        self.log_file = Path(self.temp_dir) / "creation_date.log"
        self.original_dir = os.getcwd()
        os.chdir(self.temp_dir)

    def tearDown(self):
        """Pulisce."""
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
        self.assertEqual(header, "timestamp,log_level,operazione,file,tipo_data_usata,data_originale,data_nuova")

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

        # Prima esecuzione
        with patch("sys.argv", ["proton_drive_gts.py", "--set"]):
            with patch("sys.stdout", new_callable=StringIO):
                sc.main()

        first_size = self.log_file.stat().st_size

        # Seconda esecuzione
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
    """Test per la gestione di Ctrl+C (SIGINT)."""

    @patch("signal.signal")
    def test_ctrl_c_handler_registered(self, mock_signal):
        """Test: verifica che il programma registri un handler per SIGINT."""
        import importlib
        importlib.reload(sc)

        # Verifica che signal.signal sia stato chiamato per SIGINT
        self.assertTrue(any(
            call[0][0] == signal.SIGINT
            for call in mock_signal.call_args_list
        ))


class TestMoveJson(unittest.TestCase):
    """Test per lo switch --move-json."""

    def setUp(self):
        """Crea struttura temporanea per test."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_dir = os.getcwd()
        os.chdir(self.temp_dir)
        
        # Crea directory simile a Google Foto
        Path("Google Foto").mkdir()
        Path("Google Foto/subdir1").mkdir()
        Path("Google Foto/subdir2").mkdir()
        Path("Google Photo").mkdir()
        
        # Crea file JSON
        Path("Google Foto/file1.jpg.supplemental-metadata.json").touch()
        Path("Google Foto/subdir1/file2.jpg.supplemental-metadata.json").touch()
        Path("Google Photo/file3.jpg.supplemental-metadata.json").touch()

    def tearDown(self):
        """Pulisce."""
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
        
        # Verifica che ci siano le righe attese
        expected_entries = [
            "Google Foto/file1.jpg.supplemental-metadata.json",
            "Google Foto/subdir1/file2.jpg.supplemental-metadata.json",
            "Google Photo/file3.jpg.supplemental-metadata.json",
        ]
        
        for entry in expected_entries:
            self.assertIn(entry, content)

    def test_move_json_dry_run_does_not_move_files(self):
        """Test: --move-json --dry-run NON spostano i file JSON."""
        # Memorizza i path originali
        original_json_files = [
            Path("Google Foto/file1.jpg.supplemental-metadata.json"),
            Path("Google Foto/subdir1/file2.jpg.supplemental-metadata.json"),
            Path("Google Photo/file3.jpg.supplemental-metadata.json"),
        ]
        
        # Verifica che esistano
        for f in original_json_files:
            self.assertTrue(f.exists())
        
        with patch("sys.argv", ["proton_drive_gts.py", "--move-json", "--dry-run"]):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                sc.main()
                output = mock_stdout.getvalue()
        
        # Verifica che i file NON siano stati spostati
        for f in original_json_files:
            self.assertTrue(f.exists(), f"File {f} è stato spostato, ma non avrebbe dovuto")
        
        # Verifica che l'output contenga DRY-RUN
        self.assertIn("DRY-RUN", output)

    def test_move_json_dry_run_shows_actions(self):
        """Test: --move-json --dry-run mostra le azioni che verranno eseguite."""
        with patch("sys.argv", ["proton_drive_gts.py", "--move-json", "--dry-run"]):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                sc.main()
                output = mock_stdout.getvalue()
        
        # Verifica che mostri le azioni di spostamento
        self.assertIn("DRY-RUN", output)
        self.assertIn("->", output)  # Simbolo di spostamento

    def test_rollback_json_dry_run_does_not_move_files(self):
        """Test: --rollback-json --dry-run NON spostano i file JSON."""
        # Crea la directory google_takeout_metadata con file JSON
        metadata_dir = Path("google_takeout_metadata")
        metadata_dir.mkdir()
        Path(metadata_dir, "file1.jpg.supplemental-metadata.json").touch()
        Path(metadata_dir, "file2.jpg.supplemental-metadata.json").touch()
        
        # Crea data.lst
        data_file = metadata_dir / "data.lst"
        data_file.write_text('"Google Foto/file1.jpg.supplemental-metadata.json" "file1.jpg.supplemental-metadata.json"\n')
        data_file.write_text('"Google Foto/file2.jpg.supplemental-metadata.json" "file2.jpg.supplemental-metadata.json"\n')
        
        # Memorizza i path
        json_files_in_metadata = [
            Path(metadata_dir, "file1.jpg.supplemental-metadata.json"),
            Path(metadata_dir, "file2.jpg.supplemental-metadata.json"),
        ]
        
        # Verifica che esistano
        for f in json_files_in_metadata:
            self.assertTrue(f.exists())
        
        with patch("sys.argv", ["proton_drive_gts.py", "--rollback-json", "--dry-run"]):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                sc.main()
                output = mock_stdout.getvalue()
        
        # Verifica che i file NON siano stati spostati
        for f in json_files_in_metadata:
            self.assertTrue(f.exists(), f"File {f} è stato spostato, ma non avrebbe dovuto")
        
        # Verifica che l'output contenga DRY-RUN
        self.assertIn("DRY-RUN", output)

    def test_rollback_json_dry_run_shows_actions(self):
        """Test: --rollback-json --dry-run mostra le azioni che verranno eseguite."""
        # Crea la directory google_takeout_metadata con file JSON
        metadata_dir = Path("google_takeout_metadata")
        metadata_dir.mkdir()
        Path(metadata_dir, "file1.jpg.supplemental-metadata.json").touch()
        
        # Crea data.lst
        data_file = metadata_dir / "data.lst"
        data_file.write_text('"Google Foto/file1.jpg.supplemental-metadata.json" "file1.jpg.supplemental-metadata.json"\n')
        
        with patch("sys.argv", ["proton_drive_gts.py", "--rollback-json", "--dry-run"]):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                sc.main()
                output = mock_stdout.getvalue()
        
        # Verifica che mostri le azioni di rollback
        self.assertIn("DRY-RUN", output)
        self.assertIn("->", output)

    def test_move_json_moves_files_to_metadata_dir(self):
        """Test: --move-json SENZA dry-run sposta effettivamente i file JSON in google_takeout_metadata/."""
        # Memorizza i path originali
        original_json_files = [
            Path("Google Foto/file1.jpg.supplemental-metadata.json"),
            Path("Google Foto/subdir1/file2.jpg.supplemental-metadata.json"),
            Path("Google Photo/file3.jpg.supplemental-metadata.json"),
        ]
        
        # Verifica che esistano
        for f in original_json_files:
            self.assertTrue(f.exists())
        
        with patch("sys.argv", ["proton_drive_gts.py", "--move-json"]):
            with patch("sys.stdout", new_callable=StringIO):
                sc.main()
        
        # Verifica che i file siano stati spostati in google_takeout_metadata/
        metadata_dir = Path("google_takeout_metadata")
        for f in original_json_files:
            moved_file = metadata_dir / f.name
            self.assertTrue(moved_file.exists(), f"File {f} NON è stato spostato in {moved_file}")
            self.assertFalse(f.exists(), f"File {f} è ancora nella posizione originale")

    def test_rollback_json_restores_files(self):
        """Test: --rollback-json SENZA dry-run ripristina effettivamente i file JSON."""
        # Crea la directory google_takeout_metadata con file JSON UNIVOCI
        metadata_dir = Path("google_takeout_metadata")
        metadata_dir.mkdir(exist_ok=True)
        # Usa nomi file univoci per evitare conflitti con setUp
        Path(metadata_dir, "rollback_test_file1.json").touch()
        Path(metadata_dir, "rollback_test_file2.json").touch()
        
        # Crea directory di destinazione univoca
        unique_dir = Path("RollbackTestDir")
        unique_dir.mkdir(exist_ok=True)
        
        # Crea data.lst con path ASSOLUTI (come fa move_json_files)
        data_file = metadata_dir / "data.lst"
        dest_path1 = (unique_dir / "rollback_test_file1.json").resolve()
        dest_path2 = (unique_dir / "rollback_test_file2.json").resolve()
        data_file.write_text(f'"{dest_path1}" "rollback_test_file1.json"\n"{dest_path2}" "rollback_test_file2.json"\n')
        
        # Verifica che i file siano in metadata_dir
        self.assertTrue((metadata_dir / "rollback_test_file1.json").exists())
        self.assertTrue((metadata_dir / "rollback_test_file2.json").exists())
        
        with patch("sys.argv", ["proton_drive_gts.py", "--rollback-json"]):
            with patch("sys.stdout", new_callable=StringIO):
                sc.main()
        
        # Verifica che i file siano stati ripristinati
        self.assertTrue(dest_path1.exists(), "File rollback_test_file1.json NON è stato ripristinato")
        self.assertTrue(dest_path2.exists(), "File rollback_test_file2.json NON è stato ripristinato")
        # Verifica che non esistano più in metadata_dir
        self.assertFalse((metadata_dir / "rollback_test_file1.json").exists(), "File rollback_test_file1.json è ancora in metadata_dir")
        self.assertFalse((metadata_dir / "rollback_test_file2.json").exists(), "File rollback_test_file2.json è ancora in metadata_dir")

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
        
        # Verifica che i file siano stati spostati
        metadata_dir = Path("google_takeout_metadata")
        for entry in expected_entries:
            filename = Path(entry).name
            moved_file = metadata_dir / filename
            self.assertTrue(moved_file.exists(), f"File {filename} NON spostato in {moved_file}")


if __name__ == "__main__":
    unittest.main()
