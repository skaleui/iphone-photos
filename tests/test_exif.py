from datetime import datetime
from iphoto_import.exif import parse_exif_date


def test_prefers_datetimeoriginal():
    rec = {
        "DateTimeOriginal": "2026:07:25 14:30:00",
        "CreateDate": "2020:01:01 00:00:00",
        "FileModifyDate": "2019:01:01 00:00:00",
    }
    assert parse_exif_date(rec) == datetime(2026, 7, 25, 14, 30, 0)


def test_falls_back_to_createdate():
    rec = {"CreateDate": "2021:03:04 05:06:07"}
    assert parse_exif_date(rec) == datetime(2021, 3, 4, 5, 6, 7)


def test_falls_back_to_filemodifydate():
    rec = {"FileModifyDate": "2018:12:31 23:59:59+05:30"}
    assert parse_exif_date(rec) == datetime(2018, 12, 31, 23, 59, 59)


def test_returns_none_when_no_dates():
    assert parse_exif_date({"SourceFile": "x.heic"}) is None


def test_returns_none_on_zero_date():
    # exiftool emits this for missing/blank dates
    assert parse_exif_date({"CreateDate": "0000:00:00 00:00:00"}) is None
