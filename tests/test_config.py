from pathlib import Path
import pytest
from iphoto_import.config import load_config


def _env(**over):
    base = {
        "SMB_HOST": "192.168.1.100",
        "SMB_USER": "bob",
        "SMB_PASS": "s3cret",
        "PICTURES_SHARE": "Pictures",
        "VIDEOS_SHARE": "Videos",
    }
    base.update(over)
    return base


def test_load_config_reads_required_keys():
    c = load_config(_env())
    assert c.smb_host == "192.168.1.100"
    assert c.smb_user == "bob"
    assert c.smb_pass == "s3cret"
    assert c.pictures_share == "Pictures"
    assert c.videos_share == "Videos"


def test_mount_points_derived_from_share_names():
    c = load_config(_env())
    assert c.pictures_mount == Path("/Volumes/Pictures")
    assert c.videos_mount == Path("/Volumes/Videos")


def test_staging_dir_defaults_when_absent():
    c = load_config(_env())
    assert c.staging_dir == Path.home() / ".iphone-import-staging"


def test_staging_dir_override():
    c = load_config(_env(STAGING_DIR="/tmp/stage"))
    assert c.staging_dir == Path("/tmp/stage")


def test_missing_required_key_raises():
    env = _env()
    del env["SMB_PASS"]
    with pytest.raises(KeyError):
        load_config(env)
