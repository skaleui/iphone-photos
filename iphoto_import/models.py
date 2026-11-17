from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional


def _no_download(_dest_dir: Path) -> Path:
    raise NotImplementedError("MediaItem has no download function attached")


def _no_cleanup() -> None:
    return None


@dataclass
class MediaItem:
    name: str
    creation_date: Optional[datetime]
    download: Callable[[Path], Path] = field(default=_no_download)
    cleanup: Callable[[], None] = field(default=_no_cleanup)
    cleanup_group: Optional[str] = None
