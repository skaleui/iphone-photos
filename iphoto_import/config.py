from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass
class Config:
    smb_host: str
    smb_user: str
    smb_pass: str
    pictures_share: str
    videos_share: str
    staging_dir: Path

    @property
    def pictures_mount(self) -> Path:
        return Path("/Volumes") / self.pictures_share

    @property
    def videos_mount(self) -> Path:
        return Path("/Volumes") / self.videos_share


def load_config(env: Mapping[str, str]) -> Config:
    staging = env.get("STAGING_DIR")
    return Config(
        smb_host=env["SMB_HOST"],
        smb_user=env["SMB_USER"],
        smb_pass=env["SMB_PASS"],
        pictures_share=env["PICTURES_SHARE"],
        videos_share=env["VIDEOS_SHARE"],
        staging_dir=Path(staging) if staging else Path.home() / ".iphone-import-staging",
    )


def load_config_from_dotenv(path: str = ".env") -> Config:
    from dotenv import dotenv_values

    values = {k: v for k, v in dotenv_values(path).items() if v is not None}
    return load_config(values)
