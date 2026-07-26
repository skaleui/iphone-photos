from datetime import datetime
from pathlib import Path

from iphoto_import.source import FakeSource


def test_fake_source_lists_items():
    src = FakeSource([("IMG_1.HEIC", datetime(2026, 7, 25, 9, 0), b"abc")])
    items = src.list_items()
    assert len(items) == 1
    assert items[0].name == "IMG_1.HEIC"
    assert items[0].creation_date == datetime(2026, 7, 25, 9, 0)


def test_fake_source_download_writes_bytes(tmp_path):
    src = FakeSource([("IMG_1.HEIC", None, b"hello")])
    item = src.list_items()[0]
    out = item.download(tmp_path)
    assert Path(out).read_bytes() == b"hello"
    assert Path(out).name == "IMG_1.HEIC"
