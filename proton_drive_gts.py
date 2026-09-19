#!/usr/bin/env python3
"""Proton Drive, Google Takeout Setup - Trova e normalizza date di creazione di file multimediali.

Copyright (C) 2026

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 2 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with this program. If not, see <https://www.gnu.org/licenses/>.

Priorita: EXIF -> JSON -> Nome File -> Nome Cartella
Uso: python proton_drive_gts.py [--find-missing] [--set] [--exif-files FILELIST] [--dry-run]
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
from typing import List, Optional, Tuple


def handle_interrupt(signum, frame):
    print("\nInterrotto dall'utente. Uscita pulita.")
    sys.exit(0)


signal.signal(signal.SIGINT, handle_interrupt)

LOG_FILE = "creation_date.log"


def write_log(
    log_level: str,
    operazione: str,
    filepath: str,
    tipo_data: str,
    old_date: Optional[str],
    new_date: Optional[str],
):
    header = (
        "timestamp,log_level,operazione,file,tipo_data_usata,data_originale,data_nuova"
    )
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{timestamp},{log_level},{operazione},{filepath},{tipo_data},{old_date or ''},{new_date or ''}"

    with open(LOG_FILE, "a") as f:
        if f.tell() == 0:
            f.write(header + "\n")
        f.write(line + "\n")


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
        r"_(\d{4}-\d{2}-\d{2})_at_(\d{2}\.\d{2}\.\d{2})",
        lambda m: f"{m.group(1)} {m.group(2).replace('.', ':')}",
    ),
    (
        r"(\d{8})_(\d{6})",
        lambda m: f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:8]} {m.group(2)[:2]}:{m.group(2)[2:4]}:{m.group(2)[4:6]}",
    ),
    (
        r"-(\d{8})-WA",
        lambda m: f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:8]} 12:00:00",
    ),
    (r"(\d{4}-\d{2}-\d{2})", lambda m: f"{m.group(1)} 12:00:00"),
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


def normalize_date(date_str: Optional[str]) -> Optional[str]:
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
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return None


def get_exif_date(filepath: str) -> Tuple[Optional[str], bool]:
    for tag in ALL_EXIF_TAGS:
        try:
            result = subprocess.run(
                ["exiftool", "-s3", f"-{tag}", "-d", "%Y-%m-%d %H:%M:%S", filepath],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            if output := result.stdout.strip():
                if not output.startswith("0000"):
                    return output, tag in PRIMARY_EXIF_TAGS
        except OSError:
            pass
    return None, False


def get_json_date(filepath: str) -> Optional[str]:
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
    for pattern, transform in FILENAME_DATE_PATTERNS:
        if re.search(pattern, filename):
            return transform(re.search(pattern, filename))
    return None


def extract_date_from_folder(filepath: str) -> Optional[str]:
    if match := re.search(r"Foto da (\d{4})", os.path.dirname(filepath)):
        return f"{match.group(1)}-01-01 12:00:00"
    return None


def get_current_file_date(filepath: str) -> Optional[str]:
    try:
        stat = os.stat(filepath)
        timestamp = getattr(stat, "st_birthtime", stat.st_mtime)
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    except (OSError, ValueError, TypeError):
        return None


def set_file_creation_date(filepath: str, new_date: str) -> Tuple[bool, Optional[str]]:
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
    creation_date, has_primary = get_exif_date(filepath)
    source = ""

    if not creation_date:
        if json_date := get_json_date(filepath):
            creation_date, source = json_date, "JSON used"
        elif fn_date := extract_date_from_filename(filename):
            creation_date, source = fn_date, "FILENAME used"
        elif fd_date := extract_date_from_folder(filepath):
            creation_date, source = fd_date, "FOLDER DATE used"
    elif not has_primary:
        source = "MD used"

    return creation_date, source


def build_output_line(
    filename: str,
    json_date: Optional[str],
    creation_date: Optional[str],
    source: str,
    current_date: Optional[str],
) -> str:
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


def read_file_list(filepath: str) -> List[str]:
    with open(filepath, "r", encoding="utf-8") as f:
        return [line.strip().split()[-1] for line in f if line.strip()]


def find_files_by_names(filenames: List[str]) -> List[str]:
    found_files = []
    for root, _, files in os.walk("."):
        for file in files:
            if file in filenames:
                found_files.append(os.path.abspath(os.path.join(root, file)))
    return found_files


def move_json_files(dry_run: bool) -> None:
    """Trova tutti i file JSON metadata e crea data.lst in google_takeout_metadata."""
    metadata_dir = Path("google_takeout_metadata").resolve()
    metadata_dir.mkdir(exist_ok=True)

    data_file = metadata_dir / "data.lst"

    target_dirs = ["Google Foto", "Google Photo", "GooglePhoto", "Google Photos"]

    actions = []
    with open(data_file, "w", encoding="utf-8") as f:
        for target_dir in target_dirs:
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


def rollback_json_files(dry_run: bool) -> None:
    """Ripristina i file JSON metadata dalle informazioni in google_takeout_metadata/data.lst."""
    metadata_dir = Path("google_takeout_metadata").resolve()
    data_file = metadata_dir / "data.lst"
    
    if not data_file.exists():
        print("Errore: google_takeout_metadata/data.lst non esiste")
        return

    actions = []
    with open(data_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                parts = line.strip().split('" "')
                if len(parts) == 2:
                    original_path = Path(parts[0].strip('"'))
                    filename = parts[1].strip('"')
                    src_path = metadata_dir / filename
                    actions.append((src_path, original_path))

    for src, dest in actions:
        if dry_run:
            print(f"DRY-RUN: {src} -> {dest}")
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dest.resolve())


def collect_files(from_list: bool, file_list: Optional[str]) -> List[str]:
    if from_list and file_list:
        return find_files_by_names(read_file_list(file_list))

    files = []
    for root, _, filenames in os.walk("."):
        for filename in filenames:
            ext = os.path.splitext(filename)[1][1:].lower()
            if ext in SUPPORTED_EXTENSIONS:
                files.append(os.path.join(root, filename))
    return files


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Proton Drive, Google Takeout Setup - Trova e normalizza date di creazione di file multimediali."
    )
    parser.add_argument(
        "--find-missing",
        action="store_true",
        help="Mostra solo i file senza data EXIF primaria",
    )
    parser.add_argument(
        "--set", action="store_true", help="Imposta la data di creazione dei file"
    )
    parser.add_argument(
        "--file-list",
        type=str,
        default=None,
        help="File contenente lista di nomi file (uno per riga)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Mostra le azioni senza eseguirle"
    )
    parser.add_argument(
        "--move-json",
        action="store_true",
        help="Sposta i file JSON metadata in google_takeout_metadata e crea data.lst",
    )
    parser.add_argument(
        "--rollback-json",
        action="store_true",
        help="Ripristina i file JSON metadata dalle informazioni in google_takeout_metadata/data.lst",
    )

    args = parser.parse_args()
    from_list = args.file_list is not None
    dry_run = args.dry_run
    move_json = args.move_json
    rollback_json = args.rollback_json

    if from_list and not os.path.exists(args.file_list):
        print(f"Errore: il file '{args.file_list}' non esiste")
        sys.exit(1)

    files = collect_files(from_list, args.file_list)

    if move_json:
        move_json_files(dry_run)
        return

    if rollback_json:
        rollback_json_files(dry_run)
        return

    if not args.set:
        header = "FILE CREATION DATE REPORT"
        if args.find_missing:
            header += " - MISSING ONLY"
        print("=" * 70)
        print(header)
        print("=" * 70)

    operazione = "FROM_LIST" if from_list else "FROM_WALK"

    for filepath in files:
        filename = os.path.basename(filepath)

        ext = os.path.splitext(filename)[1][1:].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            continue

        json_date = get_json_date(filepath)
        current_date = get_current_file_date(filepath)
        creation_date, source = resolve_creation_date(filepath, filename)
        output_line = build_output_line(
            filename, json_date, creation_date, source, current_date
        )

        if args.find_missing and not args.set and source != "MD used" and creation_date:
            continue

        if args.set:
            if creation_date:
                if dry_run:
                    print(
                        f"DRY-RUN: Impostare data EXIF e filesystem per {filepath} a {creation_date}"
                    )
                else:
                    # Modifica EXIF
                    success_exif, error_exif = set_exif_creation_date(filepath, creation_date)
                    # Modifica filesystem
                    success_touch, error_touch = set_file_creation_date(filepath, creation_date)

                    if success_exif and success_touch:
                        # Verifica EXIF
                        new_exif_date, _ = get_exif_date(filepath)
                        verified_exif = new_exif_date == creation_date
                        
                        # Verifica filesystem
                        new_file_date = get_current_file_date(filepath)
                        verified_touch = new_file_date == creation_date
                        
                        log_level = "INFO" if (verified_exif and verified_touch) else "ERROR"
                        write_log(
                            log_level,
                            operazione,
                            filepath,
                            source,
                            current_date,
                            creation_date,
                        )
                    else:
                        write_log(
                            "ERROR",
                            operazione,
                            filepath,
                            source,
                            current_date,
                            creation_date,
                        )
                        print(output_line)
                        if not success_exif:
                            print(f"Errore EXIF: impossibile impostare la data per {filepath}: {error_exif}")
                        if not success_touch:
                            print(f"Errore filesystem: impossibile impostare la data per {filepath}: {error_touch}")
            else:
                print(output_line)
                print(f"Errore: nessuna data valida per {filepath}")
        else:
            print(output_line)


if __name__ == "__main__":
    main()
