from datetime import datetime
from pathlib import Path
import pytest
from iphoto_import.config import Config
from iphoto_import.organizer import destination_path, run_import
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
    assert destination_path("photo", "2026-07-25", "IMG_1.HEIC", c) == pics / "2026-07-25" / "IMG_1.HEIC"
    assert destination_path("video", "2026-07-25", "VID_1.MOV", c) == vids / "2026-07-25" / "VID_1.MOV"


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
    assert (pics / "2026-07-25" / "IMG_1.HEIC").read_bytes() == b"x"
    assert report.photos == 1 and report.videos == 0


def test_run_import_skips_already_present(tmp_path, monkeypatch):
    c, pics, vids = make_config(tmp_path)
    monkeypatch.setattr(type(c), "pictures_mount", property(lambda self: pics))
    monkeypatch.setattr(type(c), "videos_mount", property(lambda self: vids))
    (pics / "2026-07-25").mkdir(parents=True)
    (pics / "2026-07-25" / "IMG_1.HEIC").write_bytes(b"old")
    import iphoto_import.organizer as org
    monkeypatch.setattr(org, "read_dates",
                        lambda paths: {p: datetime(2026, 7, 25, 8, 0) for p in paths})
    src = FakeSource([("IMG_1.HEIC", datetime(2026, 7, 25, 8, 0), b"new")])
    report = run_import(src, c)
    # Not re-downloaded/overwritten.
    assert (pics / "2026-07-25" / "IMG_1.HEIC").read_bytes() == b"old"
    assert report.skipped_existing == 1


def test_dry_run_writes_nothing(tmp_path, monkeypatch):
    c, pics, vids = make_config(tmp_path)
    monkeypatch.setattr(type(c), "pictures_mount", property(lambda self: pics))
    monkeypatch.setattr(type(c), "videos_mount", property(lambda self: vids))
    src = FakeSource([("IMG_1.HEIC", datetime(2026, 7, 25, 8, 0), b"x")])
    report = run_import(src, c, dry_run=True)
    assert not (pics / "2026-07-25").exists()
    assert report.photos == 1  # would-import count
