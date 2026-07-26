import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

_DATE_FIELDS = ("DateTimeOriginal", "CreateDate", "FileModifyDate")


def parse_exif_date(record: dict) -> Optional[datetime]:
    for field in _DATE_FIELDS:
        raw = record.get(field)
        if not raw:
            continue
        # Keep the first 19 chars: "YYYY:MM:DD HH:MM:SS", dropping tz/subsec.
        stamp = str(raw)[:19]
        if stamp.startswith("0000"):
            continue
        try:
            return datetime.strptime(stamp, "%Y:%m:%d %H:%M:%S")
        except ValueError:
            continue
    return None


def read_dates(paths: List[Path]) -> Dict[Path, Optional[datetime]]:
    if not paths:
        return {}
    cmd = ["exiftool", "-j", "-DateTimeOriginal", "-CreateDate", "-FileModifyDate"]
    cmd += [str(p) for p in paths]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    records = json.loads(out) if out.strip() else []
    result: Dict[Path, Optional[datetime]] = {}
    for rec in records:
        result[Path(rec["SourceFile"])] = parse_exif_date(rec)
    return result
