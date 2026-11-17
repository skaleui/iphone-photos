from datetime import datetime
from pathlib import Path
from typing import Optional

PHOTO_EXTS = frozenset({
    ".heic", ".heif", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".gif",
    ".bmp", ".dng", ".cr2", ".cr3", ".nef", ".nrw", ".arw", ".raf",
    ".orf", ".rw2", ".pef", ".srw", ".raw", ".3fr", ".fff", ".iiq",
    ".k25", ".kdc", ".mef", ".mos", ".mrw", ".rwl", ".x3f",
})
VIDEO_EXTS = frozenset({
    ".mov", ".mp4", ".m4v", ".avi", ".mkv", ".mpg", ".mpeg", ".mts",
    ".m2ts", ".3gp", ".3g2", ".flv", ".vob", ".ts", ".webm", ".wmv",
})


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
