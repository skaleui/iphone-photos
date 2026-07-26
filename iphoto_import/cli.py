import argparse
import sys
from pathlib import Path
from typing import Optional

from .config import load_config_from_dotenv
from .mounts import build_smb_url, ensure_mounted, MountError
from .organizer import run_import
from .source import ImageCaptureSource


def ensure_all_mounts(config) -> None:
    ensure_mounted(
        config.pictures_mount,
        build_smb_url(config.smb_host, config.smb_user, config.smb_pass, config.pictures_share),
    )
    ensure_mounted(
        config.videos_mount,
        build_smb_url(config.smb_host, config.smb_user, config.smb_pass, config.videos_share),
    )


def build_source():
    return ImageCaptureSource()


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="Import iPhone photos/videos to SMB shares.")
    parser.add_argument("--dry-run", action="store_true", help="show the plan without downloading or writing")
    parser.add_argument("--verbose", action="store_true", help="log each file")
    parser.add_argument("--staging", type=Path, default=None, help="override staging directory")
    args = parser.parse_args(argv)

    try:
        config = load_config_from_dotenv()
    except KeyError as exc:
        print(f"Config error: missing {exc} in .env (copy .env.example).", file=sys.stderr)
        return 1
    if args.staging:
        config.staging_dir = args.staging

    try:
        ensure_all_mounts(config)
    except MountError as exc:
        print(f"Mount error: {exc}", file=sys.stderr)
        return 1

    try:
        source = build_source()
        report = run_import(source, config, dry_run=args.dry_run, verbose=args.verbose)
    except Exception as exc:
        print(f"Import failed: {exc}", file=sys.stderr)
        return 1

    label = "PLAN (dry-run)" if args.dry_run else "DONE"
    print(
        f"{label}: photos: {report.photos}, videos: {report.videos}, "
        f"skipped-existing: {report.skipped_existing}, "
        f"skipped-livephoto: {report.skipped_livephoto}, errors: {report.errors}"
    )
    return 0
