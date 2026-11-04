#!/usr/bin/env python3
"""Canary for the CI UI environment: the UI tests must really run.

The UI smoke tests skip themselves when PySide6 is missing, so a green
CI run could hide a broken Qt installation. This canary fails instead:
if the Qt runtime or the UI module cannot be imported, the pipeline
turns red and the problem becomes visible.
"""

import unittest


class TestUiEnvironment(unittest.TestCase):
    """Fail when the UI test environment is incomplete."""

    def test_qt_runtime_is_importable(self):
        """Test: PySide6 QtCore/QtWidgets import without errors."""
        # pylint: disable=import-outside-toplevel,unused-import
        from PySide6 import QtCore, QtWidgets

        self.assertTrue(hasattr(QtCore, "QThread"))
        self.assertTrue(hasattr(QtWidgets, "QApplication"))

    def test_qt_svg_is_importable(self):
        """Test: PySide6 QtSvg imports without errors."""
        # pylint: disable=import-outside-toplevel,unused-import
        from PySide6 import QtSvg

        self.assertTrue(hasattr(QtSvg, "QSvgRenderer"))

    def test_ui_module_is_importable(self):
        """Test: the UI module imports without errors."""
        # pylint: disable=import-outside-toplevel,unused-import
        import proton_drive_gts_ui

        self.assertTrue(hasattr(proton_drive_gts_ui, "MainWindow"))


if __name__ == "__main__":
    unittest.main()
