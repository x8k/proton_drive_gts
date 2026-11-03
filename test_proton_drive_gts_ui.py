#!/usr/bin/env python3
# pylint: disable=line-too-long,import-outside-toplevel,unused-import,unused-variable,unused-argument,protected-access
"""Smoke tests for the PySide6 UI (proton_drive_gts_ui).

These tests need a Qt runtime. On a headless machine set
QT_QPA_PLATFORM=offscreen before running them. They cover the wizard
flow with mocked ui_flow operations: folder selection, scan results
and the fix preview.
"""

import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

try:
    import proton_drive_gts_ui as ui
    import ui_flow
except ImportError as exc:  # pragma: no cover
    raise unittest.SkipTest(f"UI dependencies not available: {exc}") from exc

from PySide6 import QtCore, QtWidgets

TIMEOUT_MS = 5000


def wait_until(condition, timeout_ms=TIMEOUT_MS):
    """Run the event loop until condition() is true or the timeout ends."""
    steps = timeout_ms // 50
    for _ in range(steps):
        if condition():
            return True
        QtCore.QCoreApplication.processEvents()
        QtCore.QThread.msleep(50)
    return condition()


class UiSmokeTestCase(unittest.TestCase):
    """Base class: offscreen QApplication and a temp export folder."""

    @classmethod
    def setUpClass(cls):
        """Create one shared QApplication for all the smoke tests."""
        if not QtWidgets.QApplication.instance():
            cls.app = QtWidgets.QApplication(sys.argv)

    def setUp(self):
        """Create a temp folder with a fake export and the main window."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_dir = os.getcwd()
        os.makedirs(os.path.join(self.temp_dir, "Google Foto"), exist_ok=True)
        with open(os.path.join(self.temp_dir, "Google Foto", "a.jpg"), "w", encoding="utf-8") as f:
            f.write("x")
        self.window = ui.MainWindow()

    def tearDown(self):
        """Close the window and remove the temp folder."""
        self.window.close()
        os.chdir(self.original_dir)
        shutil.rmtree(self.temp_dir, ignore_errors=True)


class TestWelcomePage(UiSmokeTestCase):
    """Tests for the welcome page."""

    def test_window_shows_welcome(self):
        """Test: the wizard opens on the welcome page."""
        self.assertEqual(self.window.stack.currentWidget(), self.window.page_welcome)
        self.assertFalse(self.window.welcome_analyze.isEnabled())

    def test_folder_selection_enables_analyze(self):
        """Test: choosing a folder with an export enables the analysis."""
        self.window._set_folder(self.temp_dir)  # pylint: disable=protected-access
        self.assertTrue(self.window.welcome_analyze.isEnabled())
        self.assertIn(
            "Google Foto", self.window.welcome_targets_label.text()
        )


class TestScanFlow(UiSmokeTestCase):
    """Tests for the analysis flow."""

    def test_scan_populates_results(self):
        """Test: after the scan the cards show the summary counts."""
        self.window._set_folder(self.temp_dir)  # pylint: disable=protected-access
        record = ui_flow.FileRecord(
            "a.jpg", "a.jpg", "2024-05-10 08:00:00", "MD used", None, None
        )
        summary = ui_flow.ScanSummary(total=1, ok=0, fixable=1, no_date=0)
        with patch.object(ui_flow, "scan_folder", return_value=(summary, [record])):
            self.window._start_scan()  # pylint: disable=protected-access
            self.assertTrue(
                wait_until(lambda: self.window.scan_cards[0][1].text() != "–")
            )
        self.assertEqual(
            self.window.scan_cards[0][1].text(),
            "0",
        )
        self.assertEqual(self.window.scan_cards[1][1].text(), "1")
        self.assertTrue(self.window.scan_fix.isEnabled())

    def test_scan_cancelled_shows_note(self):
        """Test: a cancelled scan (None result) updates the status."""
        self.window._set_folder(self.temp_dir)  # pylint: disable=protected-access
        with patch.object(ui_flow, "scan_folder", return_value=None):
            self.window._start_scan()  # pylint: disable=protected-access
            self.assertTrue(wait_until(self.window.scan_status.isVisible))
        self.assertIn("interrotta", self.window.scan_status.text())


class TestWorker(UiSmokeTestCase):
    """Tests for the background worker plumbing."""

    def test_worker_forwards_kwargs(self):
        """Test: job kwargs (e.g. dry_run) reach the callable."""
        seen = {}

        def fn(progress, cancel, dry_run=False):
            seen["dry_run"] = dry_run
            return seen

        worker = ui.Worker(fn, dry_run=True)
        worker.run()
        self.assertTrue(seen["dry_run"])


class TestFixFlow(UiSmokeTestCase):
    """Tests for the fix preview."""

    def test_preview_unlocks_apply(self):
        """Test: after a dry-run the apply button is enabled."""
        record = ui_flow.FileRecord(
            "a.jpg", "a.jpg", "2024-05-10 08:00:00", "MD used", None, None
        )
        self.window._summary = ui_flow.ScanSummary(total=1, ok=0, fixable=1)  # pylint: disable=protected-access
        self.window._records = [record]  # pylint: disable=protected-access
        self.window._show_fix_page()  # pylint: disable=protected-access
        result = ui_flow.FixResult(processed=1, fixed=1)
        self.window._on_preview_done(result)  # pylint: disable=protected-access
        self.assertTrue(self.window.fix_apply_btn.isEnabled())
        self.assertIn("1 file", self.window.fix_preview.toPlainText())


class TestStepIndicator(UiSmokeTestCase):
    """Tests for the wizard step breadcrumb."""

    def test_indicator_marks_done_and_active(self):
        """Test: completed steps show a check, the active one its number."""
        indicator = ui.StepIndicator()
        indicator.set_state(1, 1)
        circles = indicator._circles  # pylint: disable=protected-access
        self.assertEqual(circles[0].text(), "✓")
        self.assertEqual(circles[1].text(), "2")
        self.assertEqual(circles[2].text(), "3")

    def test_goto_updates_indicator(self):
        """Test: switching to a page refreshes the breadcrumb state."""
        self.window._goto(self.window.page_scan)  # pylint: disable=protected-access
        circles = self.window.step_indicator._circles  # pylint: disable=protected-access
        self.assertEqual(circles[0].text(), "✓")


class TestDragAndDrop(UiSmokeTestCase):
    """Tests for the folder drag & drop support."""

    def test_first_local_dir(self):
        """Test: the first local directory among the URLs is returned."""
        file_url = QtCore.QUrl.fromLocalFile(
            os.path.join(self.temp_dir, "Google Foto", "a.jpg")
        )
        dir_url = QtCore.QUrl.fromLocalFile(self.temp_dir)
        self.assertEqual(
            ui.MainWindow._first_local_dir([file_url, dir_url]),
            self.temp_dir,
        )
        self.assertIsNone(ui.MainWindow._first_local_dir([file_url]))


class TestPreviewHtml(UiSmokeTestCase):
    """Tests for the before → after preview."""

    def test_preview_rows_show_before_and_after(self):
        """Test: each fixable row shows the old and the new date."""
        record = ui_flow.FileRecord(
            "a.jpg", "a.jpg", "2024-05-10 08:00:00", "MD used", None,
            "2020:01:15 12:00:00",
        )
        self.window._records = [record]  # pylint: disable=protected-access
        html_text = "".join(  # pylint: disable=protected-access
            self.window._preview_rows()
        )
        self.assertIn("2020:01:15 12:00:00", html_text)
        self.assertIn("2024-05-10 08:00:00", html_text)
        self.assertIn("→", html_text)


class TestDonePage(UiSmokeTestCase):
    """Tests for the celebratory done page."""

    def test_done_page_shows_summary_cards(self):
        """Test: the summary cards show the fix counts."""
        result = ui_flow.FixResult(processed=21, fixed=7)
        self.window._on_fix_done(result)  # pylint: disable=protected-access
        values = self.window.done_values
        self.assertEqual(values["processed"].text(), "21")
        self.assertEqual(values["fixed"].text(), "7")
        self.assertEqual(values["left"].text(), "14")


if __name__ == "__main__":
    unittest.main()
