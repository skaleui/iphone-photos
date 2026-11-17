import sys
from datetime import datetime
from pathlib import Path
from types import ModuleType

from iphoto_import.photos_library import PhotosLibrarySource


class FakePhoto:
    uuid = "photo-uuid"
    original_filename = "IMG_1.HEIC"
    filename = "internal-name.heic"
    date = datetime(2026, 7, 25, 8, 0)
    live_photo = False
    path_live_photo = None

    def export(self, dest, filename, increment, live_photo=False):
        assert increment is False
        path = Path(dest) / filename
        path.write_bytes(b"original")
        exported = [path]
        if live_photo:
            motion = Path(dest) / f"{Path(filename).stem}.MOV"
            motion.write_bytes(b"motion")
            exported.append(motion)
        return exported


class FakeLivePhoto(FakePhoto):
    live_photo = True
    path_live_photo = "/library/IMG_1.MOV"


class FakePhotosDB:
    def __init__(self, path=None):
        self.path = path

    def photos(self):
        return [FakePhoto()]


def test_photos_library_source_lists_and_exports_original(tmp_path, monkeypatch):
    fake_module = ModuleType("osxphotos")
    fake_module.PhotosDB = FakePhotosDB
    monkeypatch.setitem(sys.modules, "osxphotos", fake_module)

    source = PhotosLibrarySource()
    items = source.list_items()

    assert len(items) == 1
    assert items[0].name == "IMG_1.HEIC"
    assert items[0].creation_date == datetime(2026, 7, 25, 8, 0)
    exported = items[0].download(tmp_path)
    assert exported.read_bytes() == b"original"

    deleted = []
    monkeypatch.setattr("iphoto_import.photos_library.delete_photo_asset",
                        lambda uuid: deleted.append(uuid))
    items[0].cleanup()
    assert deleted == ["photo-uuid"]


def test_photos_library_source_includes_live_photo_motion(tmp_path, monkeypatch):
    fake_module = ModuleType("osxphotos")
    fake_module.PhotosDB = lambda *_args: type("DB", (), {"photos": lambda self: [FakeLivePhoto()]})()
    monkeypatch.setitem(sys.modules, "osxphotos", fake_module)

    items = PhotosLibrarySource().list_items()

    assert [item.name for item in items] == ["IMG_1.HEIC", "IMG_1.MOV"]
    motion = items[1].download(tmp_path)
    assert motion.name == "IMG_1.MOV"
    assert motion.read_bytes() == b"motion"


def test_photos_library_source_uses_explicit_library_path(tmp_path, monkeypatch):
    fake_module = ModuleType("osxphotos")
    fake_module.PhotosDB = FakePhotosDB
    monkeypatch.setitem(sys.modules, "osxphotos", fake_module)

    source = PhotosLibrarySource(tmp_path / "Library.photoslibrary")
    source.list_items()

    assert source._photosdb.path == str(tmp_path / "Library.photoslibrary")