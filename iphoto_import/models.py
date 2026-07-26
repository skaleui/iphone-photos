from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional


def _no_download(_dest_dir: Path) -> Path:
    raise NotImplementedError("MediaItem has no download function attached")


@dataclass
class MediaItem:
    name: str
    creation_date: Optional[datetime]
    download: Callable[[Path], Path] = field(default=_no_download)
