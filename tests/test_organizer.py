from datetime import datetime
from pathlib import Path
import pytest
from iphoto_import.config import Config
from iphoto_import.organizer import destination_path, run_import
from iphoto_import.models import MediaItem
from iphoto_import.source import FakeSource


def make_config(tmp_path):
    pics = tmp_path / "Volumes" / "Pictures"
    vids = tmp_path / "Volumes" / "Videos"
    pics.mkdir(parents=True)
    vids.mkdir(parents=True)
    c = Config("h", "u", "p", "Pictures", "Videos", tmp_path / "staging")
    # Override mount points to the temp dirs for tests.
    c.__dict__["_pics"] = pics
    c.__dict__["_vids"] = vids
    return c, pics, vids


def test_destination_path_photo_and_video(tmp_path, monkeypatch):
    c, pics, vids = make_config(tmp_path)
    monkeypatch.setattr(type(c), "pictures_mount", property(lambda self: pics))
    monkeypatch.setattr(type(c), "videos_mount", property(lambda self: vids))
    assert destination_path("photo", "2026/2026-07-25", "IMG_1.HEIC", c) == pics / "2026" / "2026-07-25" / "IMG_1.HEIC"
    assert destination_path("video", "2026/2026-07-25", "VID_1.MOV", c) == vids / "2026" / "2026-07-25" / "VID_1.MOV"


def test_run_import_places_files_by_exif_date(tmp_path, monkeypatch):
    c, pics, vids = make_config(tmp_path)
    monkeypatch.setattr(type(c), "pictures_mount", property(lambda self: pics))
    monkeypatch.setattr(type(c), "videos_mount", property(lambda self: vids))
    # exiftool would read the real file; stub read_dates to a known date.
    import iphoto_import.organizer as org
    monkeypatch.setattr(org, "read_dates",
                        lambda paths: {p: datetime(2026, 7, 25, 8, 0) for p in paths})
    src = FakeSource([("IMG_1.HEIC", datetime(2026, 7, 25, 8, 0), b"x")])
    report = run_import(src, c)
    assert (pics / "2026" / "2026-07-25" / "IMG_1.HEIC").read_bytes() == b"x"
    assert report.photos == 1 and report.videos == 0


def test_run_import_skips_already_present(tmp_path, monkeypatch):
    c, pics, vids = make_config(tmp_path)
    monkeypatch.setattr(type(c), "pictures_mount", property(lambda self: pics))
    monkeypatch.setattr(type(c), "videos_mount", property(lambda self: vids))
    (pics / "2026" / "2026-07-25").mkdir(parents=True)
    (pics / "2026" / "2026-07-25" / "IMG_1.HEIC").write_bytes(b"old")
    import iphoto_import.organizer as org
    monkeypatch.setattr(org, "read_dates",
                        lambda paths: {p: datetime(2026, 7, 25, 8, 0) for p in paths})
    src = FakeSource([("IMG_1.HEIC", datetime(2026, 7, 25, 8, 0), b"new")])
    report = run_import(src, c)
    # Not re-downloaded/overwritten.
    assert (pics / "2026" / "2026-07-25" / "IMG_1.HEIC").read_bytes() == b"old"
    assert report.skipped_existing == 1


def test_run_import_cleans_source_for_existing_destination(tmp_path, monkeypatch):
    c, pics, vids = make_config(tmp_path)
    monkeypatch.setattr(type(c), "pictures_mount", property(lambda self: pics))
    monkeypatch.setattr(type(c), "videos_mount", property(lambda self: vids))
    (pics / "2026" / "2026-07-25").mkdir(parents=True)
    (pics / "2026" / "2026-07-25" / "IMG_1.HEIC").write_bytes(b"imported")
    cleaned = []
    item = MediaItem(
        "IMG_1.HEIC", datetime(2026, 7, 25),
        cleanup=lambda: cleaned.append("asset"), cleanup_group="asset",
    )
    source = type("Source", (), {"list_items": lambda self: [item]})()

    report = run_import(source, c, cleanup_source=True)

    assert report.skipped_existing == 1
    assert report.deleted_source == 1
    assert cleaned == ["asset"]


def test_dry_run_writes_nothing(tmp_path, monkeypatch):
    c, pics, vids = make_config(tmp_path)
    monkeypatch.setattr(type(c), "pictures_mount", property(lambda self: pics))
    monkeypatch.setattr(type(c), "videos_mount", property(lambda self: vids))
    src = FakeSource([("IMG_1.HEIC", datetime(2026, 7, 25, 8, 0), b"x")])
    report = run_import(src, c, dry_run=True)
    assert not (pics / "2026").exists()
    assert report.photos == 1  # would-import count


def test_run_import_cleans_source_once_after_group_succeeds(tmp_path, monkeypatch):
    c, pics, vids = make_config(tmp_path)
    monkeypatch.setattr(type(c), "pictures_mount", property(lambda self: pics))
    monkeypatch.setattr(type(c), "videos_mount", property(lambda self: vids))
    import iphoto_import.organizer as org
    monkeypatch.setattr(org, "read_dates",
                        lambda paths: {p: datetime(2026, 7, 25, 8, 0) for p in paths})
    cleaned = []

    def download(name, content):
        def _download(dest_dir):
            path = Path(dest_dir) / name
            path.write_bytes(content)
            return path
        return _download

    items = [
        MediaItem("IMG_1.HEIC", datetime(2026, 7, 25),
                  download("IMG_1.HEIC", b"photo"),
                  cleanup=lambda: cleaned.append("asset"), cleanup_group="asset"),
        MediaItem("IMG_1.MOV", datetime(2026, 7, 25),
                  download("IMG_1.MOV", b"video"),
                  cleanup=lambda: cleaned.append("asset"), cleanup_group="asset"),
    ]
    source = type("Source", (), {"list_items": lambda self: items})()

    report = run_import(source, c, cleanup_source=True)

    assert report.errors == 0
    assert cleaned == ["asset"]


def test_run_import_does_not_clean_source_when_group_fails(tmp_path, monkeypatch):
    c, pics, vids = make_config(tmp_path)
    monkeypatch.setattr(type(c), "pictures_mount", property(lambda self: pics))
    monkeypatch.setattr(type(c), "videos_mount", property(lambda self: vids))
    import iphoto_import.organizer as org
    monkeypatch.setattr(org, "read_dates",
                        lambda paths: {p: datetime(2026, 7, 25, 8, 0) for p in paths})
    cleaned = []

    def fail_download(_dest_dir):
        raise OSError("download failed")

    def successful_download(dest_dir):
        path = Path(dest_dir) / "IMG_1.HEIC"
        path.write_bytes(b"photo")
        return path

    items = [
        MediaItem("IMG_1.HEIC", datetime(2026, 7, 25),
                  successful_download,
                  cleanup=lambda: cleaned.append("asset"), cleanup_group="asset"),
        MediaItem("IMG_1.MOV", datetime(2026, 7, 25), fail_download,
                  cleanup=lambda: cleaned.append("asset"), cleanup_group="asset"),
    ]
    source = type("Source", (), {"list_items": lambda self: items})()

    report = run_import(source, c, cleanup_source=True, skip_livephoto=False)

    assert report.errors == 1
    assert cleaned == []
