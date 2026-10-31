#!/usr/bin/env python3
"""Proton Drive, Google Takeout Setup - Find and normalize creation dates of multimedia files.

Copyright (C) 2026

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 2 of the License, or (at your option) any later
version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
this program. If not, see <https://www.gnu.org/licenses/>.

Priority: EXIF -> JSON -> Filename -> Folder Name
Usage:
    python proton_drive_gts.py [--find-missing] [--set] [--file-list FILELIST]
    [--dry-run] [--create-albums] [--move-json] [--rollback-json]
"""

import argparse
import json
import os
import re
import signal
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set, Tuple

LOG_FILE = "creation_date.log"
LOG_HEADER = "timestamp,log_level,operation,file,date_type_used,original_date,new_date"

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

TARGET_DIRS = ["Google Foto", "Google Photo", "GooglePhoto", "Google Photos", "GoogleFoto"]

SUPPORTED_EXTENSIONS = {
    "3gp",
    "avi",
    "mkv",
    "mov",
    "mp4",
    "wmv",
    "vob",
    "thm",
    "jpg",
    "jpeg",
    "png",
    "gif",
    "bmp",
    "tif",
    "heic",
    "dng",
    "crw",
}

PRIMARY_EXIF_TAGS = ["CreationDate", "DateTimeOriginal", "MediaCreateDate"]
ALL_EXIF_TAGS = PRIMARY_EXIF_TAGS + ["ModifyDate"]

FILENAME_DATE_PATTERNS = [
    (
        re.compile(r"_(\d{4}-\d{2}-\d{2})_at_(\d{2}\.\d{2}\.\d{2})"),
        lambda m: f"{m.group(1)} {m.group(2).replace('.', ':')}",
    ),
    (
        re.compile(r"(\d{8})_(\d{6})"),
        lambda m: (
            f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:8]} "
            f"{m.group(2)[:2]}:{m.group(2)[2:4]}:{m.group(2)[4:6]}"
        ),
    ),
    (
        re.compile(r"-(\d{8})-WA"),
        lambda m: f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:8]} 12:00:00",
    ),
    (
        re.compile(r"(\d{4}-\d{2}-\d{2})"),
        lambda m: f"{m.group(1)} 12:00:00",
    ),
]

DATE_FORMATS = [
    "%d %m %Y %H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%d %m %Y",
    "%Y-%m-%d",
]

MONTH_MAP = {
    "gen": "01",
    "jan": "01",
    "feb": "02",
    "mar": "03",
    "apr": "04",
    "mag": "05",
    "may": "05",
    "giu": "06",
    "jun": "06",
    "lug": "07",
    "jul": "07",
    "ago": "08",
    "aug": "08",
    "set": "09",
    "sep": "09",
    "ott": "10",
    "oct": "10",
    "nov": "11",
    "dic": "12",
    "dec": "12",
}

YEAR_FOLDER_PATTERN = re.compile(r"^(?:Foto da|Photo from) \d{4}$")

PROTON_DRIVE_TIMEOUT = 60
PROTON_ALBUM_LIST_PATTERN = re.compile(
    r"^(?:\S+ )?(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) "
    r"\d{2} \d{4} \d{2}:\d{2} (.*?) \(\d+ photos\)$"
)
PROTON_ERROR_MARKER = "❌"


def handle_interrupt(_signum, _frame):
    """Exit cleanly on Ctrl+C."""
    print("\nInterrupted by user. Clean exit.")
    sys.exit(0)


signal.signal(signal.SIGINT, handle_interrupt)


# pylint: disable=too-many-arguments,too-many-positional-arguments
def write_log(
    log_level: str,
    operazione: str,
    filepath: str,
    tipo_data: str,
    old_date: Optional[str],
    new_date: Optional[str],
):
    """Append a line to creation_date.log."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = (
        f"{timestamp},{log_level},{operazione},{filepath},"
        f"{tipo_data},{old_date or ''},{new_date or ''}"
    )
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        if f.tell() == 0:
            f.write(LOG_HEADER + "\n")
        f.write(line + "\n")


def write_operation_log(log_level: str, operazione: str, filepath: str) -> None:
    """Log an operation that has no dates (move/rollback/create album)."""
    write_log(log_level, operazione, filepath, "", None, None)


def normalize_date(date_str: Optional[str]) -> Optional[str]:
    """Normalize a date string to the standard YYYY-MM-DD HH:MM:SS format."""
    if not date_str:
        return None

    date_str = re.sub(r"[\s\xa0]+", " ", date_str).strip()
    date_str = re.sub(r"U\s*C", "", date_str, flags=re.IGNORECASE)
    for month, num in MONTH_MAP.items():
        date_str = re.sub(rf"\b{month}\b", num, date_str, flags=re.IGNORECASE)
    date_str = re.sub(r"UTC|GMT|Z", "", date_str, flags=re.IGNORECASE)
    date_str = re.sub(r"[+-]\d{2}:?\d{2}", "", date_str)
    date_str = date_str.replace("T", " ").replace(",", " ").strip()
    date_str = re.sub(r" +", " ", date_str)
    date_str = re.sub(r"(?<![a-zA-Z0-9])[UC](?![a-zA-Z0-9])", "", date_str)

    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(date_str, fmt).strftime(DATE_FORMAT)
        except ValueError:
            continue
    return None


def get_exif_date(filepath: str) -> Tuple[Optional[str], bool]:
    """Read the EXIF creation date of a file with exiftool.

    Returns:
        Tuple[date_str, is_primary]: the date, and whether it came
        from a primary tag rather than ModifyDate
    """
    for tag in ALL_EXIF_TAGS:
        try:
            result = subprocess.run(
                ["exiftool", "-s3", f"-{tag}", "-d", DATE_FORMAT, filepath],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
        except OSError:
            continue
        if output := result.stdout.strip():
            if not output.startswith("0000"):
                return output, tag in PRIMARY_EXIF_TAGS
    return None, False


def get_json_date(filepath: str) -> Optional[str]:
    """Read the date from the associated .supplemental-metadata.json file."""
    json_file = Path(filepath + ".supplemental-metadata.json")
    if not json_file.exists():
        return None
    try:
        with open(json_file, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data.get("photoTakenTime"), dict):
            return normalize_date(data["photoTakenTime"].get("formatted"))
    except (OSError, json.JSONDecodeError, ValueError):
        pass
    return None


def extract_date_from_filename(filename: str) -> Optional[str]:
    """Extract a date from the filename using the known patterns."""
    for pattern, transform in FILENAME_DATE_PATTERNS:
        if match := pattern.search(filename):
            return transform(match)
    return None


def extract_date_from_folder(filepath: str) -> Optional[str]:
    """Extract a date from the parent folder (e.g. 'Foto da 2024')."""
    if match := re.search(r"Foto da (\d{4})", os.path.dirname(filepath)):
        return f"{match.group(1)}-01-01 12:00:00"
    return None


def get_current_file_date(filepath: str) -> Optional[str]:
    """Read the current filesystem date of a file (birth time, or mtime)."""
    try:
        stat = os.stat(filepath)
        timestamp = getattr(stat, "st_birthtime", stat.st_mtime)
        return datetime.fromtimestamp(timestamp).strftime(DATE_FORMAT)
    except (OSError, ValueError, TypeError):
        return None


def set_file_creation_date(filepath: str, new_date: str) -> Tuple[bool, Optional[str]]:
    """Set the filesystem date of a file with touch.

    Returns:
        Tuple[success, error]: True if successful, (False, error) otherwise
    """
    try:
        subprocess.run(
            ["touch", "-d", new_date, filepath],
            check=True,
            timeout=5,
            capture_output=True,
        )
        return True, None
    except (subprocess.CalledProcessError, OSError) as e:
        return False, str(e)


def set_exif_creation_date(filepath: str, new_date: str) -> Tuple[bool, Optional[str]]:
    """Set the EXIF creation date tags of a file with exiftool.

    Returns:
        Tuple[success, error]: True if successful, (False, error) otherwise
    """
    try:
        subprocess.run(
            [
                "exiftool",
                "-overwrite_original",
                "-CreateDate=" + new_date,
                "-CreationDate=" + new_date,
                "-DateTimeOriginal=" + new_date,
                "-MediaCreateDate=" + new_date,
                filepath,
            ],
            check=True,
            timeout=10,
            capture_output=True,
        )
        return True, None
    except (subprocess.CalledProcessError, OSError) as e:
        return False, str(e)


def resolve_creation_date(filepath: str, filename: str) -> Tuple[Optional[str], str]:
    """Resolve the creation date of a file.

    Priority: EXIF -> JSON -> filename -> folder name.

    Returns:
        Tuple[creation_date, source]: the date and a label describing its origin
    """
    creation_date, has_primary = get_exif_date(filepath)
    if creation_date:
        return creation_date, "" if has_primary else "MD used"

    if json_date := get_json_date(filepath):
        return json_date, "JSON used"
    if fn_date := extract_date_from_filename(filename):
        return fn_date, "FILENAME used"
    if fd_date := extract_date_from_folder(filepath):
        return fd_date, "FOLDER DATE used"
    return None, ""


def build_output_line(
    filename: str,
    json_date: Optional[str],
    creation_date: Optional[str],
    source: str,
    current_date: Optional[str],
) -> str:
    """Build a report line for a file."""
    info_parts = []
    if source:
        info_parts.append(source)
    if not creation_date:
        info_parts.append("NO DATE")
    if json_date is None:
        info_parts.append("JSON data missing")
    info_str = f"[{', '.join(info_parts)}]" if info_parts else "[]"

    jd = json_date or "NIL"
    cd = creation_date or "NIL"
    cur = current_date or "NIL"
    return (
        f'{filename}\tJSON:"{jd}"\tDATE:"{cd}"\t'
        f"INFO:{info_str}\t --- CURRENT:<{cur}>\tNEW:<{cd}>"
    )


def is_supported_file(filepath: str) -> bool:
    """Check whether a path has a supported extension."""
    ext = os.path.splitext(filepath)[1][1:].lower()
    return ext in SUPPORTED_EXTENSIONS


def read_file_list(filepath: str) -> List[str]:
    """Read a list of filenames from a text file, one per line."""
    with open(filepath, "r", encoding="utf-8") as f:
        return [line.strip().split()[-1] for line in f if line.strip()]


def find_files_by_names(filenames: List[str]) -> List[str]:
    """Find the files in the tree whose basename is in the given list."""
    wanted = set(filenames)
    found = []
    for root, _, files in os.walk("."):
        for file in files:
            if file in wanted:
                found.append(os.path.abspath(os.path.join(root, file)))
    return found


def collect_files(from_list: bool, file_list: Optional[str]) -> List[str]:
    """Collect the files to process.

    Args:
        from_list: if True, take the names from file_list
        file_list: path to the file list (optional)

    Returns:
        List of full paths of the files to process
    """
    if from_list and file_list:
        return find_files_by_names(read_file_list(file_list))

    files = []
    for root, _, filenames in os.walk("."):
        for filename in filenames:
            filepath = os.path.join(root, filename)
            if is_supported_file(filepath):
                files.append(filepath)
    return files


def move_json_files(dry_run: bool) -> None:
    """Move the JSON metadata files to google_takeout_metadata and write data.lst."""
    metadata_dir = Path("google_takeout_metadata").resolve()
    metadata_dir.mkdir(exist_ok=True)
    data_file = metadata_dir / "data.lst"

    actions = []
    with open(data_file, "w", encoding="utf-8") as f:
        for target_dir in TARGET_DIRS:
            if Path(target_dir).exists():
                for root, _, filenames in os.walk(target_dir):
                    for filename in filenames:
                        if filename.endswith(".json"):
                            filepath = Path(root) / filename
                            f.write(f'"{filepath.resolve()}" "{filename}"\n')
                            actions.append((filepath.resolve(), metadata_dir / filename))

    for src, dest in actions:
        if dry_run:
            print(f"DRY-RUN: {src} -> {dest}")
        else:
            src.rename(dest)
            write_operation_log("INFO", "MOVE_JSON", str(src))


def rollback_json_files(dry_run: bool) -> None:
    """Restore the JSON metadata files recorded in google_takeout_metadata/data.lst."""
    metadata_dir = Path("google_takeout_metadata").resolve()
    data_file = metadata_dir / "data.lst"

    if not data_file.exists():
        print("Error: google_takeout_metadata/data.lst does not exist")
        return

    actions = []
    with open(data_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                parts = line.strip().split('" "')
                if len(parts) == 2:
                    original_path = Path(parts[0].strip('"'))
                    filename = parts[1].strip('"')
                    actions.append((metadata_dir / filename, original_path))

    for src, dest in actions:
        if dry_run:
            print(f"DRY-RUN: {src} -> {dest}")
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dest.resolve())
            write_operation_log("INFO", "ROLLBACK_JSON", str(dest))


def find_album_dirs() -> List[Path]:
    """Find the first-level album directories in every target dir.

    Year folders ('Foto da <ANNO>' / 'Photo from <YEAR>') are excluded.
    """
    albums = []
    for target_dir in TARGET_DIRS:
        if Path(target_dir).is_dir():
            albums.extend(
                entry
                for entry in sorted(Path(target_dir).iterdir())
                if entry.is_dir() and not YEAR_FOLDER_PATTERN.match(entry.name)
            )
    return albums


def list_proton_albums() -> Set[str]:
    """Return the names of the albums already present in Proton Drive."""
    result = subprocess.run(
        ["proton-drive", "album", "list"],
        capture_output=True,
        text=True,
        timeout=PROTON_DRIVE_TIMEOUT,
        check=False,
    )
    return {
        match.group(1)
        for line in result.stdout.splitlines()
        if (match := PROTON_ALBUM_LIST_PATTERN.match(line.strip()))
    }


def create_proton_album(album_name: str) -> bool:
    """Create an album in Proton Drive.

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        subprocess.run(
            ["proton-drive", "album", "create", album_name],
            capture_output=True,
            timeout=PROTON_DRIVE_TIMEOUT,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, OSError):
        return False


def add_photo_to_album(album_name: str, photo_name: str) -> bool:
    """Add a photo to a Proton Drive album.

    The command fails if the return code is non-zero or the output
    contains the error marker (e.g. a duplicate photo).

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        result = subprocess.run(
            [
                "proton-drive",
                "album",
                "add-photo",
                f"/albums/{album_name}",
                f"/photos/{photo_name}",
            ],
            capture_output=True,
            text=True,
            timeout=PROTON_DRIVE_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    output = result.stdout + result.stderr
    return result.returncode == 0 and PROTON_ERROR_MARKER not in output


def collect_album_photos(album_dir: Path) -> List[Path]:
    """Return the supported media files of an album directory, sorted by name."""
    return sorted(
        entry
        for entry in album_dir.iterdir()
        if entry.is_file() and is_supported_file(entry.name)
    )


def create_albums(dry_run: bool) -> None:
    """Create the Proton Drive albums from the target directories and add their photos."""
    existing_albums = set() if dry_run else list_proton_albums()

    for album_dir in find_album_dirs():
        album_name = album_dir.name

        if album_name in existing_albums:
            print(f"Album already exists: {album_name}")
        elif dry_run:
            print(f'DRY-RUN: proton-drive album create "{album_name}"')
        elif create_proton_album(album_name):
            existing_albums.add(album_name)
            write_operation_log("INFO", "CREATE_ALBUM", str(album_dir))
        else:
            write_operation_log("ERROR", "CREATE_ALBUM", str(album_dir))
            print(f"Error: failed to create album {album_name}")
            continue

        for photo in collect_album_photos(album_dir):
            if dry_run:
                print(
                    f"DRY-RUN: proton-drive album add-photo "
                    f"/albums/{album_name} /photos/{photo.name}"
                )
            elif add_photo_to_album(album_name, photo.name):
                write_operation_log("INFO", "ADD_PHOTO", str(photo))
            else:
                write_operation_log("ERROR", "ADD_PHOTO", str(photo))
                print(f"Error: failed to add {photo.name} to {album_name}")


def report_files(files: List[str], find_missing: bool) -> None:
    """Print the creation date report for the collected files."""
    header = "FILE CREATION DATE REPORT"
    if find_missing:
        header += " - MISSING ONLY"
    print("=" * 70)
    print(header)
    print("=" * 70)

    for filepath in files:
        filename = os.path.basename(filepath)
        json_date = get_json_date(filepath)
        current_date = get_current_file_date(filepath)
        creation_date, source = resolve_creation_date(filepath, filename)

        if find_missing and source != "MD used" and creation_date:
            continue
        print(build_output_line(filename, json_date, creation_date, source, current_date))


def set_file_dates(filepath: str, operazione: str, dry_run: bool) -> None:
    """Set the EXIF and filesystem creation dates of a single file."""
    filename = os.path.basename(filepath)
    json_date = get_json_date(filepath)
    current_date = get_current_file_date(filepath)
    creation_date, source = resolve_creation_date(filepath, filename)
    output_line = build_output_line(filename, json_date, creation_date, source, current_date)

    if not creation_date:
        print(output_line)
        print(f"Error: no valid date for {filepath}")
        return

    if dry_run:
        print(f"DRY-RUN: Set EXIF and filesystem date per {filepath} a {creation_date}")
        return

    success_exif, error_exif = set_exif_creation_date(filepath, creation_date)
    success_touch, error_touch = set_file_creation_date(filepath, creation_date)

    if not (success_exif and success_touch):
        write_log("ERROR", operazione, filepath, source, current_date, creation_date)
        print(output_line)
        if not success_exif:
            print(f"EXIF error: failed to set date per {filepath}: {error_exif}")
        if not success_touch:
            print(f"Filesystem error: failed to set date per {filepath}: {error_touch}")
        return

    verified = (
        get_exif_date(filepath)[0] == creation_date
        and get_current_file_date(filepath) == creation_date
    )
    log_level = "INFO" if verified else "ERROR"
    write_log(log_level, operazione, filepath, source, current_date, creation_date)


def parse_args() -> argparse.Namespace:
    """Parse the command line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Proton Drive, Google Takeout Setup - "
            "Find and normalize creation dates of multimedia files."
        )
    )
    parser.add_argument(
        "--find-missing",
        action="store_true",
        help="Show only files without primary EXIF date",
    )
    parser.add_argument(
        "--set", action="store_true", help="Set creation date for files"
    )
    parser.add_argument(
        "--file-list",
        type=str,
        default=None,
        help="File containing list of filenames (one per line)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show actions without executing them"
    )
    parser.add_argument(
        "--move-json",
        action="store_true",
        help="Move JSON metadata files to google_takeout_metadata and create data.lst",
    )
    parser.add_argument(
        "--rollback-json",
        action="store_true",
        help=(
            "Restore JSON metadata files from information in "
            "google_takeout_metadata/data.lst"
        ),
    )
    parser.add_argument(
        "--create-albums",
        action="store_true",
        help=(
            "Create Proton Drive albums from target directories "
            "(excluding year folders) and add their photos"
        ),
    )
    return parser.parse_args()


def main() -> None:
    """Run the tool according to the command line arguments."""
    args = parse_args()

    if args.move_json:
        move_json_files(args.dry_run)
        return
    if args.rollback_json:
        rollback_json_files(args.dry_run)
        return
    if args.create_albums:
        create_albums(args.dry_run)
        return

    from_list = args.file_list is not None
    if from_list and not os.path.exists(args.file_list):
        print(f"Error: file '{args.file_list}' does not exist")
        sys.exit(1)

    files = [
        filepath
        for filepath in collect_files(from_list, args.file_list)
        if is_supported_file(filepath)
    ]

    if args.set:
        operazione = "FROM_LIST" if from_list else "FROM_WALK"
        for filepath in files:
            set_file_dates(filepath, operazione, args.dry_run)
    else:
        report_files(files, args.find_missing)


if __name__ == "__main__":
    main()
