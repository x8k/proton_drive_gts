#!/usr/bin/env python3
# pylint: disable=line-too-long,import-outside-toplevel,redefined-outer-name,unused-import,unused-variable
"""Tests for ui_flow.py (Qt-free UI workflow logic)."""

import json
import os
import shutil
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import proton_drive_gts as core
import ui_flow


def fake_exif_run(tags_by_file, dates_by_tag=None):
    """Build a subprocess.run replacement for exiftool lookups.

    tags_by_file maps a filepath to the list of EXIF tags it returns in
    order; dates_by_tag maps a tag to the printed date.
    """
    dates = dates_by_tag or {}

    def run(cmd, *args, **kwargs):
        filepath = cmd[-1]
        if cmd[0] == "touch":
            return SimpleNamespace(returncode=0)
        if cmd[0] != "exiftool":
            raise OSError("unexpected command")
        if "-overwrite_original" in cmd:
            return SimpleNamespace(stdout="", returncode=0)
        tag = cmd[-4].lstrip("-")
        tags = tags_by_file.get(os.path.basename(filepath), [])
        if tag in tags:
            date = dates.get(tag, "2024-05-10 08:00:00")
            return SimpleNamespace(stdout=date + "\n", returncode=0)
        return SimpleNamespace(stdout="", returncode=0)

    return run


class UiFlowTestCase(unittest.TestCase):
    """Base class: temp working folder with a small fake export."""

    def setUp(self):
        """Create a temporary folder with a fake Google Takeout export."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_dir = os.getcwd()
        os.chdir(self.temp_dir)
        os.makedirs("Google Foto/Album vacanze", exist_ok=True)
        with open("Google Foto/Album vacanze/ok.jpg", "w", encoding="utf-8") as f:
            f.write("x")
        with open("Google Foto/Album vacanze/md.jpg", "w", encoding="utf-8") as f:
            f.write("x")
        with open("Google Foto/Album vacanze/json.jpg", "w", encoding="utf-8") as f:
            f.write("x")
        with open("Google Foto/Album vacanze/nothing.jpg", "w", encoding="utf-8") as f:
            f.write("x")
        with open(
            "Google Foto/Album vacanze/json.jpg.supplemental-metadata.json",
            "w",
            encoding="utf-8",
        ) as f:
            json.dump({"photoTakenTime": {"formatted": "2024-06-01 10:00:00"}}, f)

    def tearDown(self):
        """Clean up the temporary folder."""
        os.chdir(self.original_dir)
        shutil.rmtree(self.temp_dir, ignore_errors=True)


class TestScanFolder(UiFlowTestCase):
    """Tests for scan_folder and the record classification."""

    def test_scan_classifies_files(self):
        """Test: OK, FIXABLE (ModifyDate), FIXABLE (JSON) and NO_DATE."""
        tags = {
            "ok.jpg": ["DateTimeOriginal"],
            "md.jpg": ["ModifyDate"],
            "json.jpg": [],
            "nothing.jpg": [],
        }
        with patch.object(
            core.subprocess, "run", side_effect=fake_exif_run(tags)
        ):
            summary, records = ui_flow.scan_folder()
        self.assertEqual(summary.counts(), {"total": 4, "ok": 1, "fixable": 2, "no_date": 1})
        by_name = {r.filename: r.status for r in records}
        self.assertEqual(by_name["ok.jpg"], ui_flow.OK)
        self.assertEqual(by_name["md.jpg"], ui_flow.FIXABLE)
        self.assertEqual(by_name["json.jpg"], ui_flow.FIXABLE)
        self.assertEqual(by_name["nothing.jpg"], ui_flow.NO_DATE)

    def test_scan_reports_progress(self):
        """Test: the progress callback receives every file."""
        seen = []
        with patch.object(core.subprocess, "run", side_effect=fake_exif_run({})):
            summary, _ = ui_flow.scan_folder(progress=lambda d, t, n: seen.append((d, t, n)))
        self.assertEqual(len(seen), 4)
        self.assertEqual(seen[0][0], 1)
        self.assertEqual(seen[-1][1], 4)

    def test_scan_can_be_cancelled(self):
        """Test: a set cancel event stops the scan."""
        cancel = threading.Event()
        cancel.set()
        with patch.object(core.subprocess, "run", side_effect=fake_exif_run({})):
            with self.assertRaises(ui_flow.OperationCancelled):
                ui_flow.scan_folder(cancel=cancel)


class TestRecordLines(UiFlowTestCase):
    """Tests for record_lines rendering."""

    def test_missing_only_skips_ok(self):
        """Test: only non-OK records are rendered when missing_only."""
        records = [
            ui_flow.FileRecord("a.jpg", "a.jpg", "2024-01-01 00:00:00", "", None, None),
            ui_flow.FileRecord("b.jpg", "b.jpg", "2024-01-01 00:00:00", "MD used", None, None),
            ui_flow.FileRecord("c.jpg", "c.jpg", None, "", None, None),
        ]
        lines = ui_flow.record_lines(records)
        self.assertEqual(len(lines), 2)
        self.assertNotIn("a.jpg", "\n".join(lines))

    def test_all_records_when_not_missing_only(self):
        """Test: every record is rendered when missing_only is False."""
        records = [
            ui_flow.FileRecord("a.jpg", "a.jpg", "2024-01-01 00:00:00", "", None, None),
            ui_flow.FileRecord("b.jpg", "b.jpg", "2024-01-01 00:00:00", "MD used", None, None),
        ]
        lines = ui_flow.record_lines(records, missing_only=False)
        self.assertEqual(len(lines), 2)


class TestFixDates(UiFlowTestCase):
    """Tests for fix_dates."""

    def test_fix_counts_fixed_and_errors(self):
        """Test: files with a date are fixed, files without are errors."""
        tags = {
            "ok.jpg": ["DateTimeOriginal"],
            "md.jpg": ["ModifyDate"],
            "json.jpg": [],
            "nothing.jpg": [],
        }
        with patch.object(core.subprocess, "run", side_effect=fake_exif_run(tags)):
            result = ui_flow.fix_dates(dry_run=False)
        self.assertEqual(result.processed, 4)
        self.assertEqual(result.fixed, 3)
        self.assertFalse(result.cancelled)
        # nothing.jpg is the only failing file: it prints its report
        # line plus the 'no valid date' error line.
        self.assertEqual(len(result.errors), 2)
        self.assertTrue(all("nothing.jpg" in line for line in result.errors))

    def test_fix_dry_run_does_not_touch_files(self):
        """Test: dry-run processes everything but writes nothing.

        md.jpg and json.jpg get a dry-run plan; ok.jpg and nothing.jpg
        have no date to apply and are reported as errors.
        """
        writes = []
        tags = {"md.jpg": ["ModifyDate"]}

        def run(cmd, *args, **kwargs):
            if cmd[0] == "touch" or (cmd[0] == "exiftool" and "-overwrite_original" in cmd):
                writes.append(cmd[0])
                raise AssertionError("dry-run must not write anything")
            return fake_exif_run(tags)(cmd, *args, **kwargs)

        with patch.object(core.subprocess, "run", side_effect=run):
            result = ui_flow.fix_dates(dry_run=True)
        self.assertEqual(result.processed, 4)
        self.assertEqual(result.fixed, 2)
        # ok.jpg and nothing.jpg have no date: two error lines each.
        self.assertEqual(len(result.errors), 4)
        self.assertEqual(writes, [])

    def test_fix_can_be_cancelled(self):
        """Test: a set cancel event stops before processing anything."""
        cancel = threading.Event()
        cancel.set()
        with patch.object(core.subprocess, "run", side_effect=fake_exif_run({})):
            result = ui_flow.fix_dates(dry_run=False, cancel=cancel)
        self.assertTrue(result.cancelled)
        self.assertEqual(result.processed, 0)


class TestHelpers(UiFlowTestCase):
    """Tests for the small helpers."""

    def test_existing_target_dirs(self):
        """Test: only the existing export folder is returned."""
        self.assertEqual(ui_flow.existing_target_dirs(), ["Google Foto"])

    def test_album_names(self):
        """Test: album directories are found, year folders excluded."""
        os.makedirs("Google Foto/Foto da 2024", exist_ok=True)
        self.assertEqual(ui_flow.album_names(), ["Album vacanze"])

    def test_log_tail_missing(self):
        """Test: an empty list when no log exists."""
        self.assertEqual(ui_flow.log_tail(), [])

    def test_log_tail_reads_last_lines(self):
        """Test: the last lines of the log are returned."""
        with open(core.LOG_FILE, "w", encoding="utf-8") as f:
            f.write("one\n")
            f.write("two\n")
            f.write("three\n")
        self.assertEqual(ui_flow.log_tail(2), ["two", "three"])

    def test_capture_output(self):
        """Test: printed output is captured as a list of lines."""
        def printer():
            print("hello")
            print("world")

        self.assertEqual(ui_flow.capture_output(printer), ["hello", "world"])


if __name__ == "__main__":
    unittest.main()
