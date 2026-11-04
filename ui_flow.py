#!/usr/bin/env python3
"""Qt-free workflow logic for the proton_drive_gts UI.

Wraps the operations of proton_drive_gts (scan, fix dates, move/rollback
JSON, create albums) with progress reporting, cancellation and result
summaries, so the GUI layer stays thin. No Qt imports here: this module
is testable on its own.

Progress callbacks receive (done, total, line) where line is a short
human-readable string or None. Cancellation is cooperative: pass a
threading.Event and set it to request a stop between files.
"""

import contextlib
import io
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

import proton_drive_gts as core

ProgressCallback = Callable[[int, int, Optional[str]], None]

NO_DATE = "NO_DATE"
FIXABLE = "FIXABLE"
OK = "OK"


@dataclass
class FileRecord:
    """The date status of a single media file."""

    filepath: str
    filename: str
    creation_date: Optional[str]
    source: str
    json_date: Optional[str]
    current_date: Optional[str]
    status: str = field(init=False)

    def __post_init__(self) -> None:
        if not self.creation_date:
            self.status = NO_DATE
        elif self.source:
            self.status = FIXABLE
        else:
            self.status = OK


@dataclass
class ScanSummary:
    """Aggregated statistics of a folder scan."""

    total: int = 0
    ok: int = 0
    fixable: int = 0
    no_date: int = 0

    def counts(self) -> dict:
        """Return the counters as a plain dict."""
        return {
            "total": self.total,
            "ok": self.ok,
            "fixable": self.fixable,
            "no_date": self.no_date,
        }


@dataclass
class FixResult:
    """The outcome of a fix-dates run."""

    processed: int = 0
    fixed: int = 0
    errors: List[str] = field(default_factory=list)
    cancelled: bool = False


def existing_target_dirs() -> List[str]:
    """Return the Google Photos export directories present in cwd."""
    return [name for name in core.TARGET_DIRS if Path(name).is_dir()]


def scan_folder(
    progress: Optional[ProgressCallback] = None,
    cancel: Optional[threading.Event] = None,
) -> tuple:
    """Scan the tree, returning (summary, records) with progress reports."""
    filepaths = core.collect_files(False, None)
    total = len(filepaths)
    summary = ScanSummary(total=total)
    records: List[FileRecord] = []
    for done, filepath in enumerate(filepaths, start=1):
        if cancel is not None and cancel.is_set():
            raise OperationCancelled()
        filename = os.path.basename(filepath)
        creation_date, source = core.resolve_creation_date(filepath, filename)
        record = FileRecord(
            filepath=filepath,
            filename=filename,
            creation_date=creation_date,
            source=source,
            json_date=core.get_json_date(filepath),
            current_date=core.get_current_file_date(filepath),
        )
        records.append(record)
        if record.status == OK:
            summary.ok += 1
        elif record.status == FIXABLE:
            summary.fixable += 1
        else:
            summary.no_date += 1
        if progress is not None:
            progress(done, total, filename)
    return summary, records


def record_lines(records: List[FileRecord], missing_only: bool = True) -> List[str]:
    """Render report lines, optionally restricted to non-OK files."""
    lines = []
    for record in records:
        if missing_only and record.status == OK:
            continue
        lines.append(
            core.build_output_line(
                record.filename,
                record.json_date,
                record.creation_date,
                record.source,
                record.current_date,
            )
        )
    return lines


def fix_dates(
    dry_run: bool,
    file_list: Optional[str] = None,
    filepaths: Optional[List[str]] = None,
    progress: Optional[ProgressCallback] = None,
    cancel: Optional[threading.Event] = None,
) -> FixResult:
    """Fix the creation dates of the given files (or of the whole tree).

    When `filepaths` is given, exactly those files are processed: the
    wizard passes the fixable records of its scan so the counts match
    what the user was shown. Otherwise the files come from file_list or
    from a walk of the current directory. Runs the same per-file logic
    as the CLI --set mode, counting fixed files and collecting error
    lines.
    """
    if filepaths is not None:
        paths = list(filepaths)
        operazione = "FROM_LIST"
    else:
        from_list = file_list is not None
        paths = core.collect_files(from_list, file_list)
        operazione = "FROM_LIST" if from_list else "FROM_WALK"
    total = len(paths)
    result = FixResult()
    for filepath in paths:
        if cancel is not None and cancel.is_set():
            result.cancelled = True
            return result
        lines = capture_output(core.set_file_dates, filepath, operazione, dry_run)
        result.processed += 1
        if any("error" in line.lower() for line in lines):
            result.errors.extend(lines)
        else:
            result.fixed += 1
        if progress is not None:
            progress(result.processed, total, os.path.basename(filepath))
    return result


def album_names() -> List[str]:
    """Return the names of the album directories found in the tree."""
    return [album.name for album in core.find_album_dirs()]


def album_photo_count(album_dir: Path) -> int:
    """Return the number of supported media files of an album directory."""
    return len(core.collect_album_photos(album_dir))


def log_tail(max_lines: int = 50) -> List[str]:
    """Return the last lines of creation_date.log, or an empty list."""
    log_path = Path(core.LOG_FILE)
    if not log_path.exists():
        return []
    with open(log_path, encoding="utf-8") as f:
        return f.read().splitlines()[-max_lines:]


def capture_output(fn, *args) -> List[str]:
    """Run fn capturing everything it prints, returning the output lines."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        fn(*args)
    return [line for line in buffer.getvalue().splitlines() if line]


def move_json(dry_run: bool = False, progress=None, cancel=None) -> List[str]:
    """Move the JSON metadata files, returning the printed output.

    The UI worker calls this with progress/cancel keywords; the core
    operation does not support them, so they are accepted and ignored.
    """
    del progress, cancel
    return capture_output(core.move_json_files, dry_run)


def rollback_json(dry_run: bool = False, progress=None, cancel=None) -> List[str]:
    """Restore the JSON metadata files, returning the printed output."""
    del progress, cancel
    return capture_output(core.rollback_json_files, dry_run)


def create_albums(dry_run: bool = False, progress=None, cancel=None) -> List[str]:
    """Create the Proton Drive albums, returning the printed output."""
    del progress, cancel
    return capture_output(core.create_albums, dry_run)


class OperationCancelled(Exception):
    """Raised when a cooperative cancellation stops an operation."""
