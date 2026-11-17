from datetime import datetime
import iphoto_import.cli as cli
from iphoto_import.config import Config
from iphoto_import.source import FakeSource


def test_main_runs_dry_run_with_injected_deps(tmp_path, monkeypatch, capsys):
    pics = tmp_path / "Pictures"; vids = tmp_path / "Videos"
    pics.mkdir(); vids.mkdir()
    cfg = Config("h", "u", "p", "Pictures", "Videos", tmp_path / "staging")
    monkeypatch.setattr(type(cfg), "pictures_mount", property(lambda self: pics))
    monkeypatch.setattr(type(cfg), "videos_mount", property(lambda self: vids))

    monkeypatch.setattr(cli, "load_config_from_dotenv", lambda: cfg)
    monkeypatch.setattr(cli, "ensure_all_mounts", lambda c: None)
    monkeypatch.setattr(cli, "build_source",
                        lambda: FakeSource([("IMG_1.HEIC", datetime(2026, 7, 25, 8, 0), b"x")]))
    monkeypatch.setattr(cli.shutil, "which", lambda _name: "/usr/bin/exiftool")

    rc = cli.main(["--dry-run"])
    assert rc == 0
    out = capsys.readouterr().out.lower()
    assert "photos: 1" in out


def test_main_exits_before_download_when_exiftool_missing(tmp_path, monkeypatch, capsys):
    cfg = Config("h", "u", "p", "Pictures", "Videos", tmp_path / "staging")
    monkeypatch.setattr(cli, "load_config_from_dotenv", lambda: cfg)

    def _fail(*args, **kwargs):
        raise AssertionError("must exit before reaching this")

    monkeypatch.setattr(cli, "ensure_all_mounts", _fail)
    monkeypatch.setattr(cli, "build_source", _fail)
    monkeypatch.setattr(cli, "run_import", _fail)
    monkeypatch.setattr(cli.shutil, "which", lambda name: None)

    rc = cli.main(["--dry-run"])
    assert rc == 1
    err = capsys.readouterr().err.lower()
    assert "exiftool not found" in err


def test_main_selects_photos_library_source(tmp_path, monkeypatch, capsys):
    pics = tmp_path / "Pictures"; vids = tmp_path / "Videos"
    pics.mkdir(); vids.mkdir()
    cfg = Config("h", "u", "p", "Pictures", "Videos", tmp_path / "staging")
    monkeypatch.setattr(type(cfg), "pictures_mount", property(lambda self: pics))
    monkeypatch.setattr(type(cfg), "videos_mount", property(lambda self: vids))
    monkeypatch.setattr(cli, "load_config_from_dotenv", lambda: cfg)
    monkeypatch.setattr(cli, "ensure_all_mounts", lambda _config: None)
    monkeypatch.setattr(cli.shutil, "which", lambda _name: "/usr/bin/exiftool")
    monkeypatch.setattr(cli, "PhotosLibrarySource", lambda _path: FakeSource([
        ("IMG_1.HEIC", datetime(2026, 7, 25, 8, 0), b"x")
    ]))

    rc = cli.main(["--source", "photos", "--dry-run"])

    assert rc == 0
    assert "photos: 1" in capsys.readouterr().out.lower()
