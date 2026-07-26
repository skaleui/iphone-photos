from datetime import datetime
from pathlib import Path
from typing import Optional

PHOTO_EXTS = frozenset({".heic", ".heif", ".jpg", ".jpeg", ".png"})
VIDEO_EXTS = frozenset({".mov", ".mp4", ".m4v"})


def classify(name: str) -> Optional[str]:
    ext = Path(name).suffix.lower()
    if ext in PHOTO_EXTS:
        return "photo"
    if ext in VIDEO_EXTS:
        return "video"
    return None


def date_folder(dt: Optional[datetime]) -> str:
    return dt.strftime("%Y-%m-%d") if dt is not None else "Unknown-Date"
