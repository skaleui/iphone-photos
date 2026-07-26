import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .classify import date_folder
from .config import Config
from .exif import read_dates
from .planner import build_plan
from .source import PhotoSource


@dataclass
class ImportReport:
    photos: int = 0
    videos: int = 0
    skipped_existing: int = 0
    skipped_livephoto: int = 0
    errors: int = 0


def destination_path(media_type: str, folder: str, name: str, config: Config) -> Path:
    root = config.pictures_mount if media_type == "photo" else config.videos_mount
    return root / folder / name


def dest_exists_checker(config: Config) -> Callable[[str, str, str], bool]:
    def exists(media_type: str, folder: str, name: str) -> bool:
        return destination_path(media_type, folder, name, config).exists()
    return exists


def run_import(source: PhotoSource, config: Config,
               dry_run: bool = False, verbose: bool = False) -> ImportReport:
    items = source.list_items()
    plan = build_plan(items, dest_exists_checker(config))
    report = ImportReport(
        skipped_existing=plan.skipped_existing,
        skipped_livephoto=plan.skipped_livephoto,
    )

    for entry in plan.to_import:
        if dry_run:
            _count(report, entry.media_type)
            if verbose:
                print(f"[dry-run] would import {entry.item.name} -> {entry.media_type}")
            continue
        try:
            config.staging_dir.mkdir(parents=True, exist_ok=True)
            staged = entry.item.download(config.staging_dir)
            exif_date = read_dates([staged]).get(Path(staged))
            folder = date_folder(exif_date)
            dest = destination_path(entry.media_type, folder, entry.item.name, config)
            if dest.exists():
                report.skipped_existing += 1
                staged.unlink(missing_ok=True)
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(staged), str(dest))
            _count(report, entry.media_type)
            if verbose:
                print(f"imported {entry.item.name} -> {dest}")
        except Exception as exc:  # per-file failure never aborts the run
            report.errors += 1
            print(f"ERROR importing {entry.item.name}: {exc}")
    return report


def _count(report: ImportReport, media_type: str) -> None:
    if media_type == "photo":
        report.photos += 1
    else:
        report.videos += 1
