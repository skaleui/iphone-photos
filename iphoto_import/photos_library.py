from pathlib import Path
import subprocess
import time
from typing import Optional

from .models import MediaItem
from .source import PhotoSource


def delete_photo_asset(uuid: str) -> None:
    """Move a Photos asset to Recently Deleted through Photos.app."""
    import Quartz
    from osxphotos.photoscript_utils import photoscript_object_from_uuid
    from osxphotos.utils import get_last_library_path

    photo = photoscript_object_from_uuid(uuid, get_last_library_path())
    if photo is None:
        raise OSError(f"Photos asset {uuid} was not found")
    photo.spotlight()
    selection = subprocess.run(
        ["osascript", "-e", 'tell application "Photos" to get selection'],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    if uuid.upper() not in selection.upper():
        raise OSError(f"Photos selected the wrong asset while deleting {uuid}")

    for pressed in (True, False):
        event = Quartz.CGEventCreateKeyboardEvent(None, 51, pressed)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
    time.sleep(0.5)
    for pressed in (True, False):
        event = Quartz.CGEventCreateKeyboardEvent(None, 36, pressed)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)


class PhotosLibrarySource(PhotoSource):
    """Reads original media from a macOS Photos library via osxphotos."""

    def __init__(self, library_path: Optional[Path] = None):
        self.library_path = library_path
        self._photosdb = None

    def list_items(self) -> list[MediaItem]:
        import osxphotos

        self._photosdb = (
            osxphotos.PhotosDB(str(self.library_path))
            if self.library_path
            else osxphotos.PhotosDB()
        )
        items = []
        for photo in self._photosdb.photos():
            filename = photo.original_filename or photo.filename
            if not filename:
                continue
            name = Path(filename).name
            live_video_name = None
            live_video_path = getattr(photo, "path_live_photo", None)
            if getattr(photo, "live_photo", False):
                suffix = Path(live_video_path).suffix if live_video_path else ".MOV"
                live_video_name = f"{Path(name).stem}{suffix}"

            cleanup_group = str(photo.uuid)

            def export_assets(
                dest_dir: Path,
                photo=photo,
                name=name,
                live_video_name=live_video_name,
            ):
                dest_dir = Path(dest_dir)
                dest_dir.mkdir(parents=True, exist_ok=True)
                exported = photo.export(
                    str(dest_dir), filename=name, increment=False,
                    live_photo=live_video_name is not None,
                )
                if not exported:
                    raise OSError(f"No original file exported for {name}")
                return [Path(path) for path in exported]

            def download(dest_dir: Path, name=name, export_assets=export_assets) -> Path:
                exported = export_assets(dest_dir)
                for path in exported:
                    if path.name == name:
                        return path
                raise OSError(f"Original photo {name} was not exported")

            items.append(MediaItem(
                name=name,
                creation_date=photo.date,
                download=download,
                cleanup=lambda uuid=photo.uuid: delete_photo_asset(str(uuid)),
                cleanup_group=cleanup_group,
            ))
            if live_video_name:
                def download_live_video(
                    dest_dir: Path,
                    video_name=live_video_name,
                    export_assets=export_assets,
                ) -> Path:
                    staged_video = Path(dest_dir) / video_name
                    if not staged_video.exists():
                        exported = export_assets(dest_dir)
                        for path in exported:
                            if path.name == video_name:
                                return path
                        raise OSError(f"Live Photo video {video_name} was not exported")
                    return staged_video

                items.append(MediaItem(
                    name=live_video_name,
                    creation_date=photo.date,
                    download=download_live_video,
                    cleanup=lambda uuid=photo.uuid: delete_photo_asset(str(uuid)),
                    cleanup_group=cleanup_group,
                ))
        return items