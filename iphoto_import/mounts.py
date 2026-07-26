import os
import subprocess
from pathlib import Path
from urllib.parse import quote


class MountError(Exception):
    pass


def build_smb_url(host: str, user: str, password: str, share: str) -> str:
    u = quote(user, safe="")
    p = quote(password, safe="")
    return f"smb://{u}:{p}@{host}/{share}"


def ensure_mounted(mount_point: Path, smb_url: str) -> None:
    if os.path.ismount(mount_point):
        return
    subprocess.run(
        ["osascript", "-e", f'mount volume "{smb_url}"'],
        capture_output=True,
        text=True,
    )
    if not mount_point.is_dir() or not os.access(mount_point, os.W_OK):
        raise MountError(
            f"Share not mounted/writable at {mount_point}. "
            f"Check the server, credentials in .env, and share name."
        )
