from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, List

from .classify import classify, date_folder
from .models import MediaItem


@dataclass
class PlanEntry:
    item: MediaItem
    media_type: str
    folder: str


@dataclass
class PlanResult:
    to_import: List[PlanEntry] = field(default_factory=list)
    existing: List[PlanEntry] = field(default_factory=list)
    skipped_existing: int = 0
    skipped_livephoto: int = 0
    skipped_other: int = 0


def build_plan(
    items: Iterable[MediaItem],
    exists: Callable[[str, str, str], bool],
    skip_livephoto: bool = True,
) -> PlanResult:
    items = list(items)
    photo_stems = {
        Path(i.name).stem for i in items if classify(i.name) == "photo"
    }

    result = PlanResult()
    for it in items:
        media_type = classify(it.name)
        if media_type is None:
            result.skipped_other += 1
            continue
        if skip_livephoto and media_type == "video" and Path(it.name).stem in photo_stems:
            result.skipped_livephoto += 1
            continue
        folder = date_folder(it.creation_date)
        if exists(media_type, folder, it.name):
            result.skipped_existing += 1
            result.existing.append(PlanEntry(item=it, media_type=media_type, folder=folder))
            continue
        result.to_import.append(PlanEntry(item=it, media_type=media_type, folder=folder))
    return result
