from iphoto_import.mounts import build_smb_url


def test_build_smb_url_basic():
    assert (
        build_smb_url("192.168.1.100", "bob", "pw", "Pictures")
        == "smb://bob:pw@192.168.1.100/Pictures"
    )


def test_build_smb_url_encodes_special_chars():
    url = build_smb_url("192.168.1.100", "bob", "p@s/w:d", "Pictures")
    assert url == "smb://bob:p%40s%2Fw%3Ad@192.168.1.100/Pictures"


def test_build_smb_url_encodes_username():
    url = build_smb_url("h", "a@b", "pw", "S")
    assert url == "smb://a%40b:pw@h/S"
