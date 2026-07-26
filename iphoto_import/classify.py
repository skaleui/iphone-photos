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
    # Nested layout: a year parent folder, then the day folder, e.g.
    # "2026/2026-07-25". Returned as a relative path so it composes directly
    # under the Pictures/Videos mount roots.
    return dt.strftime("%Y/%Y-%m-%d") if dt is not None else "Unknown-Date"
