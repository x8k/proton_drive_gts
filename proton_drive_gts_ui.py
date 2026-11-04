#!/usr/bin/env python3
"""Guided desktop UI (PySide6/Qt) for proton_drive_gts.

A wizard-style window, in Italian, that walks a non-technical user
through fixing the creation dates of a Google Photos export: pick the
folder, analyze, preview the changes, apply them, then optionally move
the JSON metadata and create Proton Drive albums.

Usage:
    python proton_drive_gts_ui.py [--folder PATH]

Requires: pip install PySide6
"""

import argparse
import html
import os
import sys
import threading
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtSvg import QSvgRenderer

import ui_flow

APP_NAME = "Sistema le foto per Proton Drive"
MAX_TABLE_ROWS = 500
BADGE_PATH_LENGTH = 60
DROP_ZONE_HIGHLIGHT_QSS = (
    "QFrame#dropZone { background: #f1eefe; border: 2px dashed #6d4aff; "
    "border-radius: 12px; }"
)

ICONS = {
    "camera": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
        'stroke-linejoin="round"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 '
        '2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>'
    ),
    "folder": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
        'stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 '
        '0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>'
    ),
    "check": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
        'stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>'
        '<polyline points="22 4 12 14.01 9 11.01"/></svg>'
    ),
    "wrench": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
        'stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 '
        '0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 '
        '1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>'
    ),
    "braces": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
        'stroke-linejoin="round"><path d="M8 3H7a2 2 0 0 0-2 2v5a2 2 0 0 1-2 2 2 2 0 '
        '0 1 2 2v5c0 1.1.9 2 2 2h1"/><path d="M16 21h1a2 2 0 0 0 2-2v-5c0-1.1.9-2 2-2'
        'a2 2 0 0 1-2-2V5a2 2 0 0 0-2-2h-1"/></svg>'
    ),
    "album": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
        'stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/>'
        '<circle cx="8.5" cy="8.5" r="1.5"/><path d="m21 15-5-5L5 21"/></svg>'
    ),
    "alert": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
        'stroke-linejoin="round"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 '
        '2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" '
        'y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>'
    ),
    "arrow-right": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
        'stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/>'
        '<polyline points="12 5 19 12 12 19"/></svg>'
    ),
}

STYLESHEET = """
* { font-family: -apple-system, 'Segoe UI', Ubuntu, 'Helvetica Neue', sans-serif; }
QMainWindow, QWidget#root { background: #f6f5fb; }
QLabel#title { font-size: 26px; font-weight: 700; color: #1a1625; }
QLabel#subtitle { font-size: 15px; color: #6b6480; }
QLabel#sectionTitle { font-size: 19px; font-weight: 600; color: #1a1625; }
QLabel#stepLabel { font-size: 13px; font-weight: 600; color: #6d4aff;
                   letter-spacing: 1px; }
QFrame#card, QFrame#statCard { background: #ffffff; border-radius: 14px;
                               border: 1px solid #ebe8f6; }
QLabel#statValue { font-size: 30px; font-weight: 700; }
QLabel#statLabel { font-size: 13px; color: #6b6480; }
QPushButton { background: #6d4aff; color: #ffffff; border: none; border-radius: 10px;
              padding: 12px 22px; font-size: 15px; font-weight: 600; }
QPushButton:hover { background: #5a3be0; }
QPushButton:disabled { background: #d9d5ee; color: #9b94b8; }
QPushButton#secondary { background: #ffffff; color: #6d4aff; border: 1px solid #c9c0f0; }
QPushButton#secondary:hover { background: #f1eefe; }
QPushButton#danger { background: #c53030; }
QPushButton#danger:hover { background: #a32626; }
QProgressBar { border: none; background: #ebe8f6; border-radius: 7px;
               min-height: 14px; text-align: center; color: #1a1625;
               font-size: 12px; font-weight: 600; }
QProgressBar::chunk { background: #6d4aff; border-radius: 7px; }
QTextEdit, QTableWidget { background: #ffffff; border: 1px solid #ebe8f6;
                          border-radius: 10px; font-size: 13px; color: #1a1625; }
QHeaderView::section { background: #f6f5fb; border: none; padding: 8px;
                       font-weight: 600; color: #6b6480; }
QFrame#stepLine { background: #ebe8f6; border: none; }
QFrame#dropZone { background: #fbfaff; border: 2px dashed #c9c0f0; border-radius: 12px; }
QLabel#dropHint { color: #6b6480; font-size: 13px; }
"""


def svg_icon(name: str, color: str = "#6d4aff", size: int = 24) -> QtGui.QIcon:
    """Render an inline SVG string into a QIcon, tinted with a color."""
    svg = ICONS[name].replace("currentColor", color)
    renderer = QSvgRenderer(svg.encode("utf-8"))
    pixmap = QtGui.QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QtGui.QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QtGui.QIcon(pixmap)


class Worker(QtCore.QObject):
    """Runs a ui_flow callable in the background, reporting progress."""

    progress = Signal(int, int, str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, fn, **kwargs):
        """The callable must accept progress and cancel keyword args."""
        super().__init__()
        self._fn = fn
        self._kwargs = kwargs
        self.cancel = threading.Event()

    @Slot()
    def run(self) -> None:
        """Execute the callable and emit the result or the failure."""
        try:
            result = self._fn(
                progress=self.emit_progress, cancel=self.cancel, **self._kwargs
            )
            self.finished.emit(result)
        except ui_flow.OperationCancelled:
            self.finished.emit(None)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.failed.emit(str(exc))

    def emit_progress(self, done: int, total: int, line: str) -> None:
        """Forward a ui_flow progress callback as a Qt signal."""
        self.progress.emit(done, total, line or "")


class ProgressArea(QtWidgets.QWidget):
    """Progress bar, status line and cancel button."""

    def __init__(self, parent=None):
        """Build the widgets, hidden until an operation starts."""
        super().__init__(parent)
        self._bar = QtWidgets.QProgressBar()
        self._bar.setRange(0, 100)
        self._status = QtWidgets.QLabel("")
        self._status.setWordWrap(True)
        self._cancel = QtWidgets.QPushButton("Interrompi")
        self._cancel.setObjectName("secondary")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._bar)
        layout.addWidget(self._status)
        layout.addWidget(self._cancel, alignment=Qt.AlignLeft)
        self.hide()
        self._cancel.clicked.connect(self._on_cancel)
        self.cancel_requested = None

    def _on_cancel(self) -> None:
        """Forward the cancel click to the registered handler."""
        if self.cancel_requested:
            self.cancel_requested()

    def start(self, cancellable: bool) -> None:
        """Show the area in indeterminate mode."""
        self._bar.setRange(0, 0)
        self._status.setText("")
        self._cancel.setVisible(cancellable)
        self.show()

    def update_progress(self, done: int, total: int, line: str) -> None:
        """Update the bar and the status line."""
        self._bar.setRange(0, max(total, 1))
        self._bar.setValue(done)
        self._status.setText(line)

    def finish(self) -> None:
        """Hide the area when the operation is over."""
        self.hide()


class Card(QtWidgets.QFrame):  # pylint: disable=too-few-public-methods
    """A white rounded card container."""

    def __init__(self, parent=None):
        """Create the card with a vertical layout."""
        super().__init__(parent)
        self.setObjectName("card")
        self._layout = QtWidgets.QVBoxLayout(self)
        self._layout.setContentsMargins(28, 28, 28, 28)
        self._layout.setSpacing(14)

    @property
    def body(self) -> QtWidgets.QVBoxLayout:
        """The card's vertical layout."""
        return self._layout


class StepIndicator(QtWidgets.QWidget):  # pylint: disable=too-few-public-methods
    """Breadcrumb of the three wizard steps with their state."""

    STEPS = ("Cartella", "Analisi", "Correzione")

    def __init__(self, parent=None):
        """Build the numbered circles joined by connector lines."""
        super().__init__(parent)
        self._circles = []
        self._names = []
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        for i, name in enumerate(self.STEPS):
            circle = QtWidgets.QLabel(str(i + 1))
            circle.setFixedSize(26, 26)
            circle.setAlignment(Qt.AlignCenter)
            name_label = QtWidgets.QLabel(name)
            self._circles.append(circle)
            self._names.append(name_label)
            row.addWidget(circle)
            row.addWidget(name_label)
            if i < len(self.STEPS) - 1:
                line = QtWidgets.QFrame()
                line.setObjectName("stepLine")
                line.setFixedHeight(2)
                row.addWidget(line, stretch=1)
        self.set_state(0, 0)

    def set_state(self, current: int, completed: int) -> None:
        """Mark the steps before `completed` as done, `current` as active."""
        for i, (circle, name) in enumerate(zip(self._circles, self._names)):
            if i < completed:
                circle.setText("✓")
                circle.setStyleSheet(
                    "background:#0e8a5f;color:#ffffff;border-radius:13px;"
                    "font-weight:700;"
                )
                name.setStyleSheet("color:#0e8a5f;font-weight:600;")
            elif i == current:
                circle.setText(str(i + 1))
                circle.setStyleSheet(
                    "background:#6d4aff;color:#ffffff;border-radius:13px;"
                    "font-weight:700;"
                )
                name.setStyleSheet("color:#1a1625;font-weight:600;")
            else:
                circle.setText(str(i + 1))
                circle.setStyleSheet(
                    "background:#ffffff;color:#9b94b8;border:1px solid #d9d5ee;"
                    "border-radius:13px;"
                )
                name.setStyleSheet("color:#9b94b8;")


class MainWindow(QtWidgets.QMainWindow):  # pylint: disable=too-many-instance-attributes,too-many-public-methods,too-few-public-methods,too-many-statements
    """The wizard main window: a stack of pages plus a shared job runner."""

    def __init__(self, folder: str = None):
        """Build the window and show the welcome page."""
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(720, 620)
        self.setAcceptDrops(True)
        self.folder = folder
        self._thread = None
        self._worker = None
        self._records = []
        self._summary = None
        self._fix_result = None
        self._preview_done = False
        # Wizard pages and widgets, created by _build_pages().
        self.page_welcome = None
        self.page_scan = None
        self.page_fix = None
        self.page_done = None
        self.page_tools = None
        self.welcome_folder_label = None
        self.welcome_targets_label = None
        self.welcome_analyze = None
        self.welcome_drop_zone = None
        self.scan_status = None
        self.scan_progress = None
        self.scan_cards = None
        self.scan_table = None
        self.scan_fix = None
        self.fix_intro = None
        self.fix_preview = None
        self.fix_progress = None
        self.fix_result_label = None
        self.fix_preview_btn = None
        self.fix_apply_btn = None
        self.done_label = None
        self.done_log = None
        self.done_badge = None
        self.done_values = None
        self.tools_progress = None
        self.tools_output = None
        self._badge_animation = None

        self.stack = QtWidgets.QStackedWidget()
        root = QtWidgets.QWidget()
        root.setObjectName("root")
        root_layout = QtWidgets.QVBoxLayout(root)
        root_layout.setContentsMargins(48, 36, 48, 36)
        root_layout.setSpacing(10)
        self.step_indicator = StepIndicator()
        root_layout.addWidget(self.step_indicator)
        root_layout.addWidget(self.stack)
        self.setCentralWidget(root)
        self._build_pages()
        if folder:
            self._set_folder(folder)

    # -- pages ------------------------------------------------------------

    def _build_pages(self) -> None:
        """Create every wizard page."""
        self.page_welcome = self._build_welcome_page()
        self.page_scan = self._build_scan_page()
        self.page_fix = self._build_fix_page()
        self.page_done = self._build_done_page()
        self.page_tools = self._build_tools_page()
        for page in (
            self.page_welcome,
            self.page_scan,
            self.page_fix,
            self.page_done,
            self.page_tools,
        ):
            self.stack.addWidget(page)

    def _header(self, parent: QtWidgets.QWidget, step: str, title: str, sub: str):
        """Build the page header (step, title, subtitle)."""
        box = QtWidgets.QVBoxLayout()
        step_label = QtWidgets.QLabel(step.upper())
        step_label.setObjectName("stepLabel")
        title_label = QtWidgets.QLabel(title)
        title_label.setObjectName("title")
        sub_label = QtWidgets.QLabel(sub)
        sub_label.setObjectName("subtitle")
        sub_label.setWordWrap(True)
        box.addWidget(step_label)
        box.addWidget(title_label)
        box.addWidget(sub_label)
        box.setSpacing(4)
        parent.layout().addLayout(box)
        return box

    def _build_welcome_page(self) -> QtWidgets.QWidget:
        """Step 1: pick the export folder."""
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setSpacing(18)
        self._header(
            page,
            "Passo 1 di 3",
            "Sistema le date delle tue foto",
            "Prima di importare le foto in Proton Drive, questo programma controlla "
            "e corregge le date di creazione. Nessuna foto viene cancellata o "
            "modificata nel contenuto.",
        )
        card = Card()
        self.welcome_folder_label = QtWidgets.QLabel(
            "Cartella non selezionata — premi il pulsante qui sotto."
        )
        self.welcome_folder_label.setWordWrap(True)
        self.welcome_targets_label = QtWidgets.QLabel("")
        self.welcome_targets_label.setWordWrap(True)
        self.welcome_targets_label.setStyleSheet("color:#6b6480;")
        pick = QtWidgets.QPushButton("  Scegli la cartella dell'archivio")
        pick.setIcon(svg_icon("folder", "#ffffff"))
        pick.setMinimumHeight(48)
        pick.clicked.connect(self._pick_folder)
        analyze = QtWidgets.QPushButton("  Analizza le foto")
        analyze.setIcon(svg_icon("arrow-right", "#ffffff"))
        analyze.setMinimumHeight(48)
        analyze.setEnabled(False)
        analyze.clicked.connect(self._start_scan)
        self.welcome_analyze = analyze
        card.body.addWidget(self.welcome_folder_label)
        card.body.addWidget(self.welcome_targets_label)
        card.body.addWidget(pick)
        card.body.addWidget(analyze)

        drop_zone = QtWidgets.QFrame()
        drop_zone.setObjectName("dropZone")
        zone_layout = QtWidgets.QVBoxLayout(drop_zone)
        zone_layout.setContentsMargins(16, 14, 16, 14)
        zone_title = QtWidgets.QLabel("oppure trascina qui la cartella dell'archivio")
        zone_title.setObjectName("dropHint")
        zone_title.setAlignment(Qt.AlignCenter)
        zone_sub = QtWidgets.QLabel(
            "Funziona in qualsiasi momento: trascina una cartella sulla finestra."
        )
        zone_sub.setObjectName("dropHint")
        zone_sub.setStyleSheet("font-size:11px;")
        zone_sub.setAlignment(Qt.AlignCenter)
        zone_layout.addWidget(zone_title)
        zone_layout.addWidget(zone_sub)
        self.welcome_drop_zone = drop_zone
        card.body.addWidget(drop_zone)
        layout.addWidget(card)

        tools = QtWidgets.QPushButton("Strumenti avanzati (metadati JSON, album)")
        tools.setObjectName("secondary")
        tools.clicked.connect(lambda: self._goto(self.page_tools))
        layout.addWidget(tools)
        layout.addStretch()
        return page

    def _build_scan_page(self) -> QtWidgets.QWidget:
        """Step 2: analysis progress and results."""
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setSpacing(18)
        self._header(
            page,
            "Passo 2 di 3",
            "Analisi dell'archivio",
            "Controllo le date di creazione di ogni foto e video.",
        )
        card = Card()
        self.scan_status = QtWidgets.QLabel("")
        self.scan_status.setWordWrap(True)
        self.scan_progress = ProgressArea()
        self.scan_progress.cancel_requested = self._cancel_job
        card.body.addWidget(self.scan_status)
        card.body.addWidget(self.scan_progress)

        row = QtWidgets.QHBoxLayout()
        self.scan_cards = []
        for key, color, label in (
            ("ok", "#0e8a5f", "Foto già a posto"),
            ("fixable", "#6d4aff", "Foto da correggere"),
            ("no_date", "#b7791f", "Foto senza data"),
        ):
            stat = Card()
            stat.setObjectName("statCard")
            value = QtWidgets.QLabel("–")
            value.setObjectName("statValue")
            value.setStyleSheet(f"color:{color};")
            name = QtWidgets.QLabel(label)
            name.setObjectName("statLabel")
            stat.body.addWidget(value)
            stat.body.addWidget(name)
            row.addWidget(stat)
            self.scan_cards.append((key, value))
        card.body.addLayout(row)

        self.scan_table = QtWidgets.QTableWidget(0, 3)
        self.scan_table.setHorizontalHeaderLabels(["File", "Data trovata", "Origine"])
        self.scan_table.horizontalHeader().setStretchLastSection(True)
        self.scan_table.setColumnWidth(0, 320)
        self.scan_table.setColumnWidth(1, 180)
        self.scan_table.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)
        card.body.addWidget(self.scan_table)

        back = QtWidgets.QPushButton("Cambia cartella")
        back.setObjectName("secondary")
        back.clicked.connect(lambda: self._goto(self.page_welcome))
        self.scan_fix = QtWidgets.QPushButton("  Correggi le date")
        self.scan_fix.setIcon(svg_icon("wrench", "#ffffff"))
        self.scan_fix.setMinimumHeight(44)
        self.scan_fix.setEnabled(False)
        self.scan_fix.clicked.connect(self._show_fix_page)
        buttons = QtWidgets.QHBoxLayout()
        buttons.addWidget(back)
        buttons.addStretch()
        buttons.addWidget(self.scan_fix)
        card.body.addLayout(buttons)
        layout.addWidget(card)
        layout.addStretch()
        return page

    def _build_fix_page(self) -> QtWidgets.QWidget:
        """Step 3: preview and apply the fixes."""
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setSpacing(18)
        self._header(
            page,
            "Passo 3 di 3",
            "Correzione delle date",
            "Prima guarda cosa verrà fatto, poi confermi. Nessuna modifica viene "
            "eseguita senza il tuo consenso.",
        )
        card = Card()
        self.fix_intro = QtWidgets.QLabel("")
        self.fix_intro.setWordWrap(True)
        self.fix_preview = QtWidgets.QTextEdit()
        self.fix_preview.setReadOnly(True)
        self.fix_preview.setPlaceholderText("L'anteprima apparirà qui.")
        self.fix_progress = ProgressArea()
        self.fix_progress.cancel_requested = self._cancel_job
        self.fix_result_label = QtWidgets.QLabel("")
        self.fix_result_label.setWordWrap(True)
        preview = QtWidgets.QPushButton("  Anteprima delle modifiche")
        preview.setIcon(svg_icon("braces", "#ffffff"))
        preview.clicked.connect(self._start_preview)
        apply_btn = QtWidgets.QPushButton("  Applica le correzioni")
        apply_btn.setIcon(svg_icon("check", "#ffffff"))
        apply_btn.setMinimumHeight(44)
        apply_btn.setEnabled(False)
        apply_btn.clicked.connect(self._apply_fixes)
        self.fix_preview_btn = preview
        self.fix_apply_btn = apply_btn
        back = QtWidgets.QPushButton("Torna all'analisi")
        back.setObjectName("secondary")
        back.clicked.connect(lambda: self._goto(self.page_scan))
        buttons = QtWidgets.QHBoxLayout()
        buttons.addWidget(preview)
        buttons.addWidget(apply_btn)
        buttons.addWidget(back)
        card.body.addWidget(self.fix_intro)
        card.body.addWidget(self.fix_preview)
        card.body.addWidget(self.fix_progress)
        card.body.addWidget(self.fix_result_label)
        card.body.addLayout(buttons)
        layout.addWidget(card)
        layout.addStretch()
        return page

    def _build_done_page(self) -> QtWidgets.QWidget:
        """Final page: animated check, summary cards and next steps."""
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setSpacing(18)
        self._header(
            page,
            "Fatto!",
            "Date sistemate",
            "Le tue foto sono pronte per l'importazione in Proton Drive.",
        )
        card = Card()
        self.done_badge = QtWidgets.QLabel()
        self.done_badge.setAlignment(Qt.AlignCenter)
        self.done_badge.setMinimumSize(96, 96)
        row = QtWidgets.QHBoxLayout()
        self.done_values = {}
        for key, color, label in (
            ("processed", "#6d4aff", "File controllati"),
            ("fixed", "#0e8a5f", "Date corrette"),
            ("left", "#b7791f", "Lasciate senza data"),
        ):
            stat = Card()
            stat.setObjectName("statCard")
            value = QtWidgets.QLabel("–")
            value.setObjectName("statValue")
            value.setStyleSheet(f"color:{color};")
            name = QtWidgets.QLabel(label)
            name.setObjectName("statLabel")
            stat.body.addWidget(value)
            stat.body.addWidget(name)
            row.addWidget(stat)
            self.done_values[key] = value
        self.done_label = QtWidgets.QLabel("")
        self.done_label.setWordWrap(True)
        self.done_log = QtWidgets.QTextEdit()
        self.done_log.setReadOnly(True)
        self.done_log.setVisible(False)
        show_log = QtWidgets.QPushButton("Mostra il registro delle operazioni")
        show_log.setObjectName("secondary")
        show_log.clicked.connect(self._toggle_log)
        tools = QtWidgets.QPushButton("Strumenti avanzati")
        tools.setObjectName("secondary")
        tools.clicked.connect(lambda: self._goto(self.page_tools))
        restart = QtWidgets.QPushButton("  Ricomincia con un'altra cartella")
        restart.setIcon(svg_icon("arrow-right", "#ffffff"))
        restart.clicked.connect(lambda: self._goto(self.page_welcome))
        card.body.addWidget(self.done_badge)
        card.body.addLayout(row)
        card.body.addWidget(self.done_label)
        card.body.addWidget(self.done_log)
        card.body.addWidget(show_log)
        card.body.addWidget(tools)
        card.body.addWidget(restart)
        layout.addWidget(card)
        layout.addStretch()
        return page

    def _build_tools_page(self) -> QtWidgets.QWidget:
        """Advanced tools: JSON metadata move/rollback and albums."""
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setSpacing(18)
        self._header(
            page,
            "Strumenti avanzati",
            "Metadati e album",
            "Operazioni opzionali, da usare dopo aver corretto le date.",
        )
        card = Card()
        card.body.addWidget(QtWidgets.QLabel("Sposta i metadati JSON"))
        json_hint = QtWidgets.QLabel(
            "Raccoglie i file .supplemental-metadata.json in una cartella "
            "google_takeout_metadata, per un archivio più pulito."
        )
        json_hint.setStyleSheet("color:#6b6480;")
        json_hint.setWordWrap(True)
        card.body.addWidget(json_hint)
        json_row = QtWidgets.QHBoxLayout()
        move_btn = QtWidgets.QPushButton("Sposta")
        move_btn.setObjectName("secondary")
        move_btn.clicked.connect(self._move_json)
        rollback_btn = QtWidgets.QPushButton("Ripristina")
        rollback_btn.setObjectName("secondary")
        rollback_btn.clicked.connect(self._rollback_json)
        json_row.addWidget(move_btn)
        json_row.addWidget(rollback_btn)
        json_row.addStretch()
        card.body.addLayout(json_row)

        card.body.addWidget(QtWidgets.QLabel("Crea gli album su Proton Drive"))
        album_hint = QtWidgets.QLabel(
            "Crea un album per ogni cartella dell'archivio e aggiunge le foto. "
            "Richiede l'applicazione proton-drive installata e collegata."
        )
        album_hint.setStyleSheet("color:#6b6480;")
        album_hint.setWordWrap(True)
        album_row = QtWidgets.QHBoxLayout()
        albums_btn = QtWidgets.QPushButton("  Crea album")
        albums_btn.setIcon(svg_icon("album", "#ffffff"))
        albums_btn.clicked.connect(self._create_albums)
        album_row.addWidget(albums_btn)
        album_row.addStretch()
        card.body.addWidget(album_hint)
        card.body.addLayout(album_row)

        self.tools_progress = ProgressArea()
        self.tools_output = QtWidgets.QTextEdit()
        self.tools_output.setReadOnly(True)
        card.body.addWidget(self.tools_progress)
        card.body.addWidget(self.tools_output)

        back = QtWidgets.QPushButton("Torna all'inizio")
        back.setObjectName("secondary")
        back.clicked.connect(lambda: self._goto(self.page_welcome))
        card.body.addWidget(back)
        layout.addWidget(card)
        layout.addStretch()
        return page

    # -- actions -----------------------------------------------------------

    def _goto(self, page: QtWidgets.QWidget) -> None:
        """Switch the visible page and refresh the step indicator."""
        self.stack.setCurrentWidget(page)
        if page is self.page_welcome:
            self.step_indicator.set_state(0, 0)
        elif page is self.page_scan:
            self.step_indicator.set_state(1, 1)
        elif page is self.page_fix:
            self.step_indicator.set_state(2, 1)
        elif page is self.page_done:
            self.step_indicator.set_state(2, 3)
        else:
            self.step_indicator.hide()
            return
        self.step_indicator.show()

    def _pick_folder(self) -> None:
        """Open the folder picker and inspect the chosen folder."""
        chosen = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Scegli la cartella dell'archivio", str(Path.home())
        )
        if chosen:
            self._set_folder(chosen)

    def dragEnterEvent(self, event) -> None:  # pylint: disable=invalid-name
        """Accept the drag when it carries at least one local folder."""
        if self._first_local_dir(event.mimeData().urls()) is not None:
            event.acceptProposedAction()
            self._set_drop_highlight(True)

    def dragLeaveEvent(self, event) -> None:  # pylint: disable=invalid-name,unused-argument
        """Remove the drop-zone highlight when the drag leaves the window."""
        self._set_drop_highlight(False)

    def dropEvent(self, event) -> None:  # pylint: disable=invalid-name
        """Use the first dropped local folder as the export folder."""
        self._set_drop_highlight(False)
        folder = self._first_local_dir(event.mimeData().urls())
        if folder:
            self._set_folder(folder)
            event.acceptProposedAction()

    def _set_drop_highlight(self, active: bool) -> None:
        """Highlight the welcome drop zone while a folder hovers over it."""
        if self.welcome_drop_zone is not None:
            self.welcome_drop_zone.setStyleSheet(
                DROP_ZONE_HIGHLIGHT_QSS if active else ""
            )

    @staticmethod
    def _first_local_dir(urls) -> "str | None":
        """Return the first local directory among the dragged URLs."""
        for url in urls:
            if url.isLocalFile():
                path = Path(url.toLocalFile())
                if path.is_dir():
                    return str(path)
        return None

    def _set_folder(self, folder: str) -> None:
        """Point the tool at a folder and show what was found in it."""
        if self._thread is not None and self._thread.isRunning():
            self.statusBar().showMessage(
                "Attendi la fine dell'operazione in corso.", 4000
            )
            return
        self.folder = folder
        os.chdir(folder)
        # A new folder invalidates every previous scan result.
        self._records = []
        self._summary = None
        self._fix_result = None
        self._preview_done = False
        self.scan_status.setText("")
        self.scan_table.setRowCount(0)
        self.scan_fix.setEnabled(False)
        self.fix_preview.clear()
        self.fix_result_label.setText("")
        self.fix_apply_btn.setEnabled(False)
        targets = ui_flow.existing_target_dirs()
        self.welcome_folder_label.setText(f"Cartella: {folder}")
        if targets:
            names = ", ".join(targets)
            self.welcome_targets_label.setText(f"Archivi trovati: {names}")
        else:
            self.welcome_targets_label.setText(
                "Attenzione: nessuna cartella Google Foto/Photo trovata qui. "
                "Scegli la cartella che contiene l'archivio."
            )
        self.welcome_analyze.setEnabled(True)
        self._goto(self.page_welcome)

    def _start_scan(self) -> None:
        """Analyze the folder in the background."""
        self._goto(self.page_scan)
        self.scan_fix.setEnabled(False)
        self.scan_status.setText("Analisi in corso…")
        self.scan_progress.start(cancellable=True)
        self.scan_table.setRowCount(0)
        for _, value in self.scan_cards:
            value.setText("–")
        self._start_job(ui_flow.scan_folder, self._on_scan_done, self._on_job_failed)

    def _on_scan_done(self, result) -> None:
        """Show the scan results."""
        self.scan_progress.finish()
        if result is None:
            self.scan_status.setText("Analisi interrotta.")
            return
        summary, records = result
        self._summary, self._records = summary, records
        counts = summary.counts()
        for key, value in self.scan_cards:
            value.setText(str(counts[key]))
        self.scan_status.setText(
            f"Analisi completata: {counts['total']} file controllati."
        )
        fixable = [r for r in records if r.status == ui_flow.FIXABLE]
        no_date = [r for r in records if r.status == ui_flow.NO_DATE]
        rows = (fixable + no_date)[:MAX_TABLE_ROWS]
        self.scan_table.setRowCount(len(rows))
        for i, record in enumerate(rows):
            self.scan_table.setItem(i, 0, QtWidgets.QTableWidgetItem(record.filename))
            self.scan_table.setItem(
                i, 1, QtWidgets.QTableWidgetItem(record.creation_date or "—")
            )
            self.scan_table.setItem(
                i, 2, QtWidgets.QTableWidgetItem(record.source or "nessuna data")
            )
        if counts["fixable"] == 0:
            self.scan_status.setText(
                "Analisi completata: tutte le foto hanno già la data corretta!"
            )
        self.scan_fix.setEnabled(counts["fixable"] > 0)

    def _show_fix_page(self) -> None:
        """Show the fix page with the plan for this folder."""
        counts = self._summary.counts()
        self._preview_done = False
        self.fix_intro.setText(
            f"Verranno corrette le date di {counts['fixable']} file su "
            f"{counts['total']}. La data viene presa dall'EXIF, dai file JSON "
            "di Google, dal nome del file o dal nome della cartella."
        )
        self.fix_preview.clear()
        self.fix_result_label.setText("")
        self.fix_apply_btn.setEnabled(False)
        self._goto(self.page_fix)

    def _fixable_filepaths(self) -> list:
        """Return the file paths of the fixable records of the last scan."""
        return [r.filepath for r in self._records if r.status == ui_flow.FIXABLE]

    def _start_preview(self) -> None:
        """Run a dry-run and show the planned changes."""
        self.fix_progress.start(cancellable=True)
        self.fix_result_label.setText("Calcolo dell'anteprima…")
        self._start_job(
            ui_flow.fix_dates,
            self._on_preview_done,
            self._on_job_failed,
            dry_run=True,
            filepaths=self._fixable_filepaths(),
        )

    def _on_preview_done(self, result) -> None:
        """Show the preview lines and unlock the apply button."""
        self.fix_progress.finish()
        self.fix_result_label.setText("")
        if result is None:
            return
        self._preview_done = True
        rows = self._preview_rows()
        doc = (
            f"<div style='margin-bottom:6px;color:#1a1625'>Verranno corretti "
            f"<b>{result.fixed}</b> file:</div>" + "".join(rows[:MAX_TABLE_ROWS])
        )
        if len(rows) > MAX_TABLE_ROWS:
            doc += (
                f"<div style='color:#6b6480'>… e altri "
                f"{len(rows) - MAX_TABLE_ROWS} file.</div>"
            )
        self.fix_preview.setHtml(doc)
        self.fix_result_label.setText(
            f"{result.fixed} file verranno corretti. Controlla l'anteprima e "
            "premi «Applica le correzioni»."
        )
        self.fix_apply_btn.setEnabled(result.fixed > 0)

    def _preview_rows(self) -> list:
        """Build the before → after HTML rows for the fixable records."""
        rows = []
        for record in self._records:
            if record.status != ui_flow.FIXABLE:
                continue
            old = record.current_date or "nessuna data"
            new = record.creation_date or "—"
            source = record.source or "nessuna origine"
            rows.append(
                "<div style='margin-bottom:4px;'>"
                f"<span style='color:#1a1625'>{html.escape(record.filename)}</span>"
                "&nbsp; "
                f"<span style='color:#b3261e;text-decoration:line-through'>"
                f"{html.escape(old)}</span> "
                "<span style='color:#6d4aff'>→</span> "
                f"<b style='color:#0e8a5f'>{html.escape(new)}</b> "
                f"<span style='color:#9b94b8;font-size:11px;'>"
                f"({html.escape(source)})</span>"
                "</div>"
            )
        return rows

    def _apply_fixes(self) -> None:
        """Ask for confirmation, then fix the dates for real."""
        answer = QtWidgets.QMessageBox.question(
            self,
            "Conferma",
            "Le date di creazione (EXIF e file system) verranno aggiornate. "
            "Procedo?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if answer != QtWidgets.QMessageBox.Yes:
            return
        self.fix_preview_btn.setEnabled(False)
        self.fix_apply_btn.setEnabled(False)
        self.fix_progress.start(cancellable=True)
        self._start_job(
            ui_flow.fix_dates,
            self._on_fix_done,
            self._on_job_failed,
            dry_run=False,
            filepaths=self._fixable_filepaths(),
        )

    def _on_fix_done(self, result) -> None:
        """Show the final summary page with its animated check."""
        self.fix_progress.finish()
        self.fix_preview_btn.setEnabled(True)
        self._fix_result = result
        if result is None:
            self.fix_result_label.setText("Correzione interrotta.")
            self.fix_apply_btn.setEnabled(True)
            return
        # The cards reflect the whole scan: only the fixable files were
        # processed, and the files without a findable date are counted
        # separately from the ones that failed with an error.
        counts = self._summary.counts() if self._summary else {}
        processed = counts.get("total", result.processed)
        left = counts.get("no_date", processed - result.fixed)
        self.done_values["processed"].setText(str(processed))
        self.done_values["fixed"].setText(str(result.fixed))
        self.done_values["left"].setText(str(left))
        message = (
            "Tutto fatto! Prossimo passo: importa le foto in Proton Drive "
            "(proton.me/drive/import)."
        )
        failed = result.processed - result.fixed
        if failed and result.errors:
            message = (
                f"Attenzione: {failed} file non sono stati corretti per "
                f"errori (dettagli nel registro).\n\n{message}"
            )
        if left:
            message = (
                f"{left} file senza una data trovabile sono stati lasciati "
                f"invariati.\n\n{message}"
            )
        self.done_label.setText(message)
        self.done_log.setPlainText("\n".join(ui_flow.log_tail()))
        self._goto(self.page_done)
        self._animate_check_badge()

    def _animate_check_badge(self) -> None:
        """Play the check-drawing animation on the done page."""
        self._badge_animation = QtCore.QVariantAnimation(self)
        self._badge_animation.setDuration(900)
        self._badge_animation.setStartValue(0.0)
        self._badge_animation.setEndValue(1.0)
        self._badge_animation.valueChanged.connect(self._render_badge)
        self._render_badge(0.0)
        self._badge_animation.start()

    def _render_badge(self, progress: float) -> None:
        """Render the check badge SVG at the given drawing progress."""
        offset = BADGE_PATH_LENGTH * (1.0 - float(progress))
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96">'
            '<circle cx="48" cy="48" r="44" fill="#e6f6ef"/>'
            '<path d="M29 50 L44 64 L69 34" fill="none" stroke="#0e8a5f" '
            'stroke-width="7" stroke-linecap="round" stroke-linejoin="round" '
            f'stroke-dasharray="{BADGE_PATH_LENGTH}" stroke-dashoffset="{offset}"/>'
            "</svg>"
        )
        renderer = QSvgRenderer(svg.encode("utf-8"))
        pixmap = QtGui.QPixmap(96, 96)
        pixmap.fill(Qt.transparent)
        painter = QtGui.QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        self.done_badge.setPixmap(pixmap)

    def _toggle_log(self) -> None:
        """Show or hide the operation log."""
        self.done_log.setVisible(not self.done_log.isVisible())

    def _move_json(self) -> None:
        """Move the JSON metadata files."""
        self.tools_progress.start(cancellable=False)
        self._start_job(
            ui_flow.move_json,
            self._on_tools_done,
            self._on_job_failed,
            dry_run=False,
        )

    def _rollback_json(self) -> None:
        """Restore the JSON metadata files."""
        self.tools_progress.start(cancellable=False)
        self._start_job(
            ui_flow.rollback_json,
            self._on_tools_done,
            self._on_job_failed,
            dry_run=False,
        )

    def _create_albums(self) -> None:
        """Create the Proton Drive albums."""
        self.tools_progress.start(cancellable=False)
        self._start_job(
            ui_flow.create_albums,
            self._on_tools_done,
            self._on_job_failed,
            dry_run=False,
        )

    def _on_tools_done(self, result) -> None:
        """Show the output of an advanced tool."""
        self.tools_progress.finish()
        if result is None:
            return
        self.tools_output.setPlainText("\n".join(result))

    # -- job plumbing ------------------------------------------------------

    def _start_job(self, fn, on_done, on_fail, **kwargs) -> None:
        """Run fn(progress=…, cancel=…) on a worker thread."""
        if self._thread is not None and self._thread.isRunning():
            QtWidgets.QMessageBox.warning(
                self, "Attendere", "Un'altra operazione è in corso."
            )
            return
        self._thread = QtCore.QThread()
        self._worker = Worker(fn, **kwargs)
        self._worker.moveToThread(self._thread)
        self._worker.progress.connect(self._on_job_progress)
        self._worker.finished.connect(self._on_finished_wrapper(on_done))
        self._worker.failed.connect(on_fail)
        self._thread.started.connect(self._worker.run)
        self._thread.start()

    def _on_job_progress(self, done: int, total: int, line: str) -> None:
        """Update the progress area of the current page."""
        for area in (self.scan_progress, self.fix_progress, self.tools_progress):
            if area.isVisible():
                area.update_progress(done, total, line)

    def _on_finished_wrapper(self, on_done):
        """Wrap a finished callback to also stop the worker thread."""

        def handle(result) -> None:
            on_done(result)
            if self._thread is not None:
                self._thread.quit()
                self._thread.wait(2000)

        return handle

    def _on_job_failed(self, message: str) -> None:
        """Report a job failure and restore the wizard navigation."""
        for area in (self.scan_progress, self.fix_progress, self.tools_progress):
            area.finish()
        self.fix_preview_btn.setEnabled(True)
        if self._preview_done:
            self.fix_apply_btn.setEnabled(True)
        QtWidgets.QMessageBox.critical(
            self,
            "Errore",
            "L'operazione non è riuscita:\n" + message,
        )

    def _cancel_job(self) -> None:
        """Request cooperative cancellation of the running job."""
        if self._worker is not None:
            self._worker.cancel.set()

    def closeEvent(self, event) -> None:  # pylint: disable=invalid-name
        """Stop the running job and its thread before the window closes."""
        if self._worker is not None:
            self._worker.cancel.set()
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(2000)
        event.accept()


def parse_args() -> argparse.Namespace:
    """Parse the command line arguments."""
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument(
        "--folder",
        type=str,
        default=None,
        help="Folder containing the Google Photos export",
    )
    return parser.parse_args()


def main() -> None:
    """Start the application."""
    args = parse_args()
    folder = args.folder
    app = QtWidgets.QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    app.setApplicationName(APP_NAME)
    app.setWindowIcon(svg_icon("camera"))
    if folder and not Path(folder).is_dir():
        QtWidgets.QMessageBox.critical(
            None,
            "Errore",
            f"La cartella indicata non esiste:\n{folder}",
        )
        folder = None
    window = MainWindow(folder)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
