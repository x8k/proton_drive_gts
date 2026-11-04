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
            self.assertTrue(
                wait_until(lambda: "interrotta" in self.window.scan_status.text())
            )
        self.assertIn("interrotta", self.window.scan_status.text())


class TestScanNavigation(UiSmokeTestCase):
    """Tests for the wizard page navigation during the analysis."""

    def test_scan_moves_to_scan_page(self):
        """Test: starting the analysis switches to the scan page."""
        self.window._set_folder(self.temp_dir)  # pylint: disable=protected-access
        with patch.object(ui_flow, "scan_folder", return_value=None):
            self.window._start_scan()  # pylint: disable=protected-access
            self.assertEqual(
                self.window.stack.currentWidget(), self.window.page_scan
            )
            self.assertTrue(
                wait_until(lambda: "interrotta" in self.window.scan_status.text())
            )

    def test_welcome_reachable_again_from_scan_page(self):
        """Test: the welcome page can be reached again from the scan page."""
        self.window._goto(self.window.page_scan)  # pylint: disable=protected-access
        self.window._goto(self.window.page_welcome)  # pylint: disable=protected-access
        self.assertEqual(
            self.window.stack.currentWidget(), self.window.page_welcome
        )


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


class TestFixableFilepaths(UiSmokeTestCase):
    """Tests for the fixable-only selection passed to fix_dates."""

    def test_fixable_filepaths_filters_records(self):
        """Test: only FIXABLE records are returned, in order."""
        records = [
            ui_flow.FileRecord("fix.jpg", "fix.jpg", "2024-01-01 00:00:00", "MD used", None, None),
            ui_flow.FileRecord("ok.jpg", "ok.jpg", "2024-01-01 00:00:00", "", None, None),
            ui_flow.FileRecord("none.jpg", "none.jpg", None, "", None, None),
        ]
        self.window._records = records  # pylint: disable=protected-access
        self.assertEqual(
            self.window._fixable_filepaths(),  # pylint: disable=protected-access
            ["fix.jpg"],
        )

    def test_preview_passes_fixable_filepaths(self):
        """Test: the dry-run receives only the fixable file paths."""
        self.window._records = [  # pylint: disable=protected-access
            ui_flow.FileRecord("fix.jpg", "fix.jpg", "2024-01-01 00:00:00", "MD used", None, None)
        ]
        self.window._summary = ui_flow.ScanSummary(total=1, fixable=1)  # pylint: disable=protected-access
        seen = {}

        def fake_fix(**kwargs):
            seen.update(kwargs)
            return ui_flow.FixResult(processed=1, fixed=1)

        self.window._show_fix_page()  # pylint: disable=protected-access
        with patch.object(ui_flow, "fix_dates", side_effect=fake_fix):
            self.window._start_preview()  # pylint: disable=protected-access
            self.assertTrue(
                wait_until(self.window.fix_apply_btn.isEnabled)
            )
        self.assertEqual(seen.get("filepaths"), ["fix.jpg"])
        self.assertTrue(seen.get("dry_run"))


class TestFailureRecovery(UiSmokeTestCase):
    """Tests for recovering from job failures on the fix page."""

    def test_failure_reenables_apply_after_preview(self):
        """Test: after a preview, a failure re-enables preview and apply."""
        self.window._preview_done = True  # pylint: disable=protected-access
        self.window.fix_preview_btn.setEnabled(False)
        self.window.fix_apply_btn.setEnabled(False)
        with patch.object(QtWidgets.QMessageBox, "critical"):
            self.window._on_job_failed("boom")  # pylint: disable=protected-access
        self.assertTrue(self.window.fix_preview_btn.isEnabled())
        self.assertTrue(self.window.fix_apply_btn.isEnabled())

    def test_failure_keeps_apply_locked_without_preview(self):
        """Test: without a preview, a failure does not unlock the apply."""
        self.window._preview_done = False  # pylint: disable=protected-access
        self.window.fix_preview_btn.setEnabled(False)
        self.window.fix_apply_btn.setEnabled(False)
        with patch.object(QtWidgets.QMessageBox, "critical"):
            self.window._on_job_failed("boom")  # pylint: disable=protected-access
        self.assertTrue(self.window.fix_preview_btn.isEnabled())
        self.assertFalse(self.window.fix_apply_btn.isEnabled())


class FakeThread:
    """Minimal stand-in for a busy QThread."""

    def isRunning(self):  # pylint: disable=invalid-name
        """Pretend the job thread is busy."""
        return True

    def quit(self):
        """No-op matching the QThread API used on close."""

    def wait(self, timeout):
        """No-op matching the QThread API used on close."""


class TestFolderSwitch(UiSmokeTestCase):
    """Tests for switching folders in the middle of the flow."""

    def test_set_folder_resets_previous_scan_state(self):
        """Test: choosing a new folder clears the old results."""
        record = ui_flow.FileRecord(
            "a.jpg", "a.jpg", "2024-05-10 08:00:00", "MD used", None, None
        )
        self.window._records = [record]  # pylint: disable=protected-access
        self.window._summary = ui_flow.ScanSummary(total=1, fixable=1)  # pylint: disable=protected-access
        self.window._preview_done = True  # pylint: disable=protected-access
        self.window.scan_fix.setEnabled(True)
        self.window.scan_table.setRowCount(3)
        self.window.scan_status.setText("vecchio stato")
        self.window.fix_preview.setPlainText("vecchia anteprima")
        self.window.fix_result_label.setText("vecchio risultato")
        self.window.fix_apply_btn.setEnabled(True)
        self.window._set_folder(self.temp_dir)  # pylint: disable=protected-access
        self.assertEqual(self.window._records, [])
        self.assertIsNone(self.window._summary)
        self.assertFalse(self.window._preview_done)
        self.assertFalse(self.window.scan_fix.isEnabled())
        self.assertEqual(self.window.scan_table.rowCount(), 0)
        self.assertEqual(self.window.scan_status.text(), "")
        self.assertEqual(self.window.fix_preview.toPlainText(), "")
        self.assertEqual(self.window.fix_result_label.text(), "")
        self.assertFalse(self.window.fix_apply_btn.isEnabled())

    def test_set_folder_blocked_while_job_running(self):
        """Test: a folder change during a running job is rejected."""
        self.window.folder = None
        self.window._thread = FakeThread()  # pylint: disable=protected-access
        self.window._set_folder(self.temp_dir)  # pylint: disable=protected-access
        self.assertIsNone(self.window.folder)
        self.assertIn("Attendi", self.window.statusBar().currentMessage())


class TestDonePage(UiSmokeTestCase):
    """Tests for the celebratory done page."""

    def test_done_page_shows_summary_cards(self):
        """Test: the cards mirror the whole scan, not only the fixed files."""
        self.window._summary = ui_flow.ScanSummary(total=21, ok=12, fixable=7, no_date=2)  # pylint: disable=protected-access
        result = ui_flow.FixResult(processed=7, fixed=7)
        self.window._on_fix_done(result)  # pylint: disable=protected-access
        values = self.window.done_values
        self.assertEqual(values["processed"].text(), "21")
        self.assertEqual(values["fixed"].text(), "7")
        self.assertEqual(values["left"].text(), "2")
        self.assertIn("2 file senza una data", self.window.done_label.text())
        self.assertNotIn("Attenzione", self.window.done_label.text())

    def test_done_page_separates_errors_from_no_date(self):
        """Test: real errors and files left without a date are distinct."""
        self.window._summary = ui_flow.ScanSummary(total=21, ok=12, fixable=7, no_date=2)  # pylint: disable=protected-access
        result = ui_flow.FixResult(
            processed=7, fixed=5, errors=["EXIF error: a.jpg"]
        )
        self.window._on_fix_done(result)  # pylint: disable=protected-access
        label = self.window.done_label.text()
        self.assertIn("non sono stati corretti", label)
        self.assertIn("2 file senza una data", label)
        self.assertEqual(self.window.done_values["fixed"].text(), "5")


if __name__ == "__main__":
    unittest.main()
