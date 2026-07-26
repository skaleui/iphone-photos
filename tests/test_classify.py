from datetime import datetime
from iphoto_import.classify import classify, date_folder


def test_classify_photos_case_insensitive():
    assert classify("IMG_1234.HEIC") == "photo"
    assert classify("img_1234.heic") == "photo"
    assert classify("pic.JPG") == "photo"
    assert classify("shot.jpeg") == "photo"
    assert classify("Screenshot.png") == "photo"
    assert classify("live.heif") == "photo"


def test_classify_videos_case_insensitive():
    assert classify("clip.MOV") == "video"
    assert classify("clip.mp4") == "video"
    assert classify("clip.m4v") == "video"


def test_classify_unknown_returns_none():
    assert classify("notes.txt") is None
    assert classify("archive.zip") is None


def test_date_folder_formats_date():
    assert date_folder(datetime(2026, 7, 25, 14, 30)) == "2026-07-25"


def test_date_folder_none_is_unknown():
    assert date_folder(None) == "Unknown-Date"
