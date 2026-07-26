# iPhone Photo Import Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A manually-run Python 3 CLI on a Mac mini that pulls original photos/videos off a USB-connected iPhone (via ImageCaptureCore/PyObjC) and files them into date-based folders on two SMB-mounted SSD shares, non-destructively and incrementally.

**Architecture:** A small Python package. Pure, unit-tested core (config, classification, Live-Photo pairing, date-folder selection, dedup, path building, exiftool-record parsing) is separated from side-effecting adapters (ImageCaptureCore device source, SMB auto-mount, exiftool subprocess, file placement). The device is hidden behind a `PhotoSource` interface so the pipeline is testable with a `FakeSource` — no phone needed for unit tests.

**Tech Stack:** Python 3 (macOS), `pyobjc-framework-ImageCaptureCore`, `python-dotenv`, `exiftool` (Homebrew), `pytest`.

## Global Constraints

- Platform: macOS (Mac mini). Python 3.9+ (`dataclasses`, f-strings, `pathlib`).
- **Non-destructive:** never delete anything from the iPhone.
- **Incremental:** skip files already imported, decided by **filename + destination date folder**; skip such files **without downloading**.
- Date source order for placement (authoritative, via exiftool): `DateTimeOriginal` → `CreateDate` → `FileModifyDate` → else `Unknown-Date/`.
- Folder name format: `YYYY-MM-DD` (strftime `%Y-%m-%d`).
- Photo extensions → Pictures: `.heic .heif .jpg .jpeg .png`. Video extensions → Videos: `.mov .mp4 .m4v`. Extension matching is case-insensitive.
- Live Photo motion skip: a video file is skipped when a photo file shares its base name (stem).
- Destinations: photos → `/Volumes/<PICTURES_SHARE>/YYYY-MM-DD/`; videos → `/Volumes/<VIDEOS_SHARE>/YYYY-MM-DD/`.
- Config (host, user, password, share names) comes from a git-ignored `.env`; `.env.example` is committed. CLI flags carry runtime behavior only: `--dry-run`, `--verbose`, `--staging`.
- Secrets never committed; `.env` is git-ignored.

---

### Task 1: Project scaffold + environment verification

**Files:**
- Create: `.gitignore`, `.env.example`, `requirements.txt`, `iphoto_import/__init__.py`, `tests/__init__.py`, `tests/test_environment.py`
- Init: git repository

**Interfaces:**
- Consumes: nothing.
- Produces: the package directory `iphoto_import/` and the dev environment. Confirms `import ImageCaptureCore` works (the core risk) and `exiftool` is on PATH.

- [ ] **Step 1: Initialise git and package layout**

```bash
cd "/Volumes/Crucial/work/Home Projects/IphonePhotos"
git init
mkdir -p iphoto_import tests
touch iphoto_import/__init__.py tests/__init__.py
```

- [ ] **Step 2: Write `.gitignore`**

Create `.gitignore`:

```gitignore
.env
__pycache__/
*.pyc
.pytest_cache/
.venv/
staging/
```

- [ ] **Step 3: Write `.env.example`**

Create `.env.example`:

```dotenv
SMB_HOST=192.168.1.40
SMB_USER=youruser
SMB_PASS=yourpassword
PICTURES_SHARE=Pictures
VIDEOS_SHARE=Videos
# Optional: local staging dir for downloaded originals before placement
# STAGING_DIR=/Users/you/.iphone-import-staging
```

- [ ] **Step 4: Write `requirements.txt`**

Create `requirements.txt`:

```text
pyobjc-framework-ImageCaptureCore>=10.0
python-dotenv>=1.0
pytest>=8.0
```

- [ ] **Step 5: Install dependencies and exiftool**

```bash
cd "/Volumes/Crucial/work/Home Projects/IphonePhotos"
python3 -m pip install -r requirements.txt
which exiftool || brew install exiftool
```

- [ ] **Step 6: Write the environment verification test**

Create `tests/test_environment.py`:

```python
import importlib
import shutil


def test_imagecapturecore_binding_importable():
    # The whole device-access approach depends on this PyObjC binding.
    # If this fails, fall back to the Swift helper (see spec, decision #1).
    importlib.import_module("ImageCaptureCore")


def test_exiftool_on_path():
    assert shutil.which("exiftool") is not None, "install with: brew install exiftool"
```

- [ ] **Step 7: Run the verification test**

Run: `cd "/Volumes/Crucial/work/Home Projects/IphonePhotos" && python3 -m pytest tests/test_environment.py -v`
Expected: PASS. If `test_imagecapturecore_binding_importable` FAILS, STOP and report — the plan's device layer (Task 7) needs the Swift fallback instead.

- [ ] **Step 8: Commit**

```bash
git add .gitignore .env.example requirements.txt iphoto_import/ tests/
git commit -m "chore: scaffold project and verify ImageCaptureCore + exiftool"
```

---

### Task 2: Config loader

**Files:**
- Create: `iphoto_import/config.py`, `tests/test_config.py`

**Interfaces:**
- Consumes: `.env` keys from Task 1.
- Produces:
  - `@dataclass Config` with fields: `smb_host: str`, `smb_user: str`, `smb_pass: str`, `pictures_share: str`, `videos_share: str`, `staging_dir: Path`.
  - `Config.pictures_mount -> Path` → `/Volumes/<pictures_share>`.
  - `Config.videos_mount -> Path` → `/Volumes/<videos_share>`.
  - `load_config(env: Mapping[str, str]) -> Config` — pure; raises `KeyError` for a missing required key. (A thin `load_config_from_dotenv()` wrapper calls `dotenv_values` and delegates.)

- [ ] **Step 1: Write the failing test**

Create `tests/test_config.py`:

```python
from pathlib import Path
import pytest
from iphoto_import.config import load_config


def _env(**over):
    base = {
        "SMB_HOST": "192.168.1.40",
        "SMB_USER": "bob",
        "SMB_PASS": "s3cret",
        "PICTURES_SHARE": "Pictures",
        "VIDEOS_SHARE": "Videos",
    }
    base.update(over)
    return base


def test_load_config_reads_required_keys():
    c = load_config(_env())
    assert c.smb_host == "192.168.1.40"
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'iphoto_import.config'`.

- [ ] **Step 3: Write minimal implementation**

Create `iphoto_import/config.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_config.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add iphoto_import/config.py tests/test_config.py
git commit -m "feat: config loader from .env"
```

---

### Task 3: Media models + classification helpers

**Files:**
- Create: `iphoto_import/models.py`, `iphoto_import/classify.py`, `tests/test_classify.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `@dataclass MediaItem` with `name: str`, `creation_date: Optional[datetime]`, `download: Callable[[Path], Path]` (default a placeholder that raises; real sources supply it). Only `name` and `creation_date` are used by the planner.
  - `classify(name: str) -> Optional[str]` → `"photo"`, `"video"`, or `None`.
  - `date_folder(dt: Optional[datetime]) -> str` → `"YYYY-MM-DD"` or `"Unknown-Date"`.
  - `PHOTO_EXTS`, `VIDEO_EXTS` frozensets.

- [ ] **Step 1: Write the failing test**

Create `tests/test_classify.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_classify.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'iphoto_import.classify'`.

- [ ] **Step 3: Write the models**

Create `iphoto_import/models.py`:

```python
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional


def _no_download(_dest_dir: Path) -> Path:
    raise NotImplementedError("MediaItem has no download function attached")


@dataclass
class MediaItem:
    name: str
    creation_date: Optional[datetime]
    download: Callable[[Path], Path] = field(default=_no_download)
```

- [ ] **Step 4: Write the classification helpers**

Create `iphoto_import/classify.py`:

```python
from datetime import datetime
from pathlib import Path
from typing import Optional

PHOTO_EXTS = frozenset({".heic", ".heif", ".jpg", ".jpeg", ".png"})
VIDEO_EXTS = frozenset({".mov", ".mp4", ".m4v"})


def classify(name: str) -> Optional[str]:
    ext = Path(name).suffix.lower()
    if ext in PHOTO_EXTS:
        return "photo"
    if ext in VIDEO_EXTS:
        return "video"
    return None


def date_folder(dt: Optional[datetime]) -> str:
    return dt.strftime("%Y-%m-%d") if dt is not None else "Unknown-Date"
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/test_classify.py -v`
Expected: PASS (5 tests).

- [ ] **Step 6: Commit**

```bash
git add iphoto_import/models.py iphoto_import/classify.py tests/test_classify.py
git commit -m "feat: media models and classification helpers"
```

---

### Task 4: Planner (Live-Photo pairing + dedup)

**Files:**
- Create: `iphoto_import/planner.py`, `tests/test_planner.py`

**Interfaces:**
- Consumes: `MediaItem` (Task 3), `classify`/`date_folder` (Task 3).
- Produces:
  - `@dataclass PlanEntry` with `item: MediaItem`, `media_type: str` (`"photo"`/`"video"`), `folder: str` (prospective date folder from `creation_date`).
  - `@dataclass PlanResult` with `to_import: List[PlanEntry]`, `skipped_existing: int`, `skipped_livephoto: int`, `skipped_other: int`.
  - `build_plan(items: Iterable[MediaItem], exists: Callable[[str, str, str], bool]) -> PlanResult`. `exists(media_type, folder, name)` returns True when the file is already at the destination. Live-Photo motion files and non-media files are excluded before the dedup check.

- [ ] **Step 1: Write the failing test**

Create `tests/test_planner.py`:

```python
from datetime import datetime
from iphoto_import.models import MediaItem
from iphoto_import.planner import build_plan


def item(name, y=2026, mo=7, d=25):
    return MediaItem(name=name, creation_date=datetime(y, mo, d, 9, 0))


def never_exists(_t, _f, _n):
    return False


def test_photos_and_videos_are_split_into_folders():
    items = [item("IMG_1.HEIC"), item("VID_1.MOV")]
    plan = build_plan(items, never_exists)
    by_name = {e.item.name: e for e in plan.to_import}
    assert by_name["IMG_1.HEIC"].media_type == "photo"
    assert by_name["IMG_1.HEIC"].folder == "2026-07-25"
    assert by_name["VID_1.MOV"].media_type == "video"


def test_live_photo_motion_is_skipped():
    # IMG_1.MOV shares its stem with IMG_1.HEIC -> Live Photo motion, skip it.
    items = [item("IMG_1.HEIC"), item("IMG_1.MOV")]
    plan = build_plan(items, never_exists)
    names = {e.item.name for e in plan.to_import}
    assert names == {"IMG_1.HEIC"}
    assert plan.skipped_livephoto == 1


def test_standalone_video_is_kept():
    items = [item("VID_9.MOV")]
    plan = build_plan(items, never_exists)
    assert {e.item.name for e in plan.to_import} == {"VID_9.MOV"}
    assert plan.skipped_livephoto == 0


def test_non_media_is_skipped_as_other():
    items = [item("notes.txt"), item("IMG_2.JPG")]
    plan = build_plan(items, never_exists)
    assert {e.item.name for e in plan.to_import} == {"IMG_2.JPG"}
    assert plan.skipped_other == 1


def test_already_imported_is_skipped_by_name_and_folder():
    def exists(media_type, folder, name):
        return media_type == "photo" and folder == "2026-07-25" and name == "IMG_1.HEIC"

    items = [item("IMG_1.HEIC"), item("IMG_2.HEIC")]
    plan = build_plan(items, exists)
    assert {e.item.name for e in plan.to_import} == {"IMG_2.HEIC"}
    assert plan.skipped_existing == 1


def test_unknown_date_goes_to_unknown_folder():
    items = [MediaItem(name="IMG_3.HEIC", creation_date=None)]
    plan = build_plan(items, never_exists)
    assert plan.to_import[0].folder == "Unknown-Date"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_planner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'iphoto_import.planner'`.

- [ ] **Step 3: Write minimal implementation**

Create `iphoto_import/planner.py`:

```python
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, List

from .classify import classify, date_folder
from .models import MediaItem


@dataclass
class PlanEntry:
    item: MediaItem
    media_type: str
    folder: str


@dataclass
class PlanResult:
    to_import: List[PlanEntry] = field(default_factory=list)
    skipped_existing: int = 0
    skipped_livephoto: int = 0
    skipped_other: int = 0


def build_plan(
    items: Iterable[MediaItem],
    exists: Callable[[str, str, str], bool],
) -> PlanResult:
    items = list(items)
    photo_stems = {
        Path(i.name).stem for i in items if classify(i.name) == "photo"
    }

    result = PlanResult()
    for it in items:
        media_type = classify(it.name)
        if media_type is None:
            result.skipped_other += 1
            continue
        if media_type == "video" and Path(it.name).stem in photo_stems:
            result.skipped_livephoto += 1
            continue
        folder = date_folder(it.creation_date)
        if exists(media_type, folder, it.name):
            result.skipped_existing += 1
            continue
        result.to_import.append(PlanEntry(item=it, media_type=media_type, folder=folder))
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_planner.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add iphoto_import/planner.py tests/test_planner.py
git commit -m "feat: planner with Live-Photo pairing and dedup"
```

---

### Task 5: exiftool date reader

**Files:**
- Create: `iphoto_import/exif.py`, `tests/test_exif.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `parse_exif_date(record: dict) -> Optional[datetime]` — pure; picks `DateTimeOriginal` → `CreateDate` → `FileModifyDate`; parses exiftool's `"YYYY:MM:DD HH:MM:SS"` form (ignoring any trailing timezone/subsec); returns `None` if none parseable.
  - `read_dates(paths: List[Path]) -> Dict[Path, Optional[datetime]]` — one batch `exiftool -j -DateTimeOriginal -CreateDate -FileModifyDate <paths>` call, JSON parsed, mapped via `parse_exif_date`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_exif.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_exif.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'iphoto_import.exif'`.

- [ ] **Step 3: Write minimal implementation**

Create `iphoto_import/exif.py`:

```python
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

_DATE_FIELDS = ("DateTimeOriginal", "CreateDate", "FileModifyDate")


def parse_exif_date(record: dict) -> Optional[datetime]:
    for field in _DATE_FIELDS:
        raw = record.get(field)
        if not raw:
            continue
        # Keep the first 19 chars: "YYYY:MM:DD HH:MM:SS", dropping tz/subsec.
        stamp = str(raw)[:19]
        if stamp.startswith("0000"):
            continue
        try:
            return datetime.strptime(stamp, "%Y:%m:%d %H:%M:%S")
        except ValueError:
            continue
    return None


def read_dates(paths: List[Path]) -> Dict[Path, Optional[datetime]]:
    if not paths:
        return {}
    cmd = ["exiftool", "-j", "-DateTimeOriginal", "-CreateDate", "-FileModifyDate"]
    cmd += [str(p) for p in paths]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    records = json.loads(out) if out.strip() else []
    result: Dict[Path, Optional[datetime]] = {}
    for rec in records:
        result[Path(rec["SourceFile"])] = parse_exif_date(rec)
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_exif.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Integration check against a real file**

Run:
```bash
python3 -c "
from pathlib import Path; from iphoto_import.exif import read_dates
import subprocess
# make a tiny jpeg and stamp a known date
open('/tmp/t.jpg','wb').write(bytes.fromhex('ffd8ffe000104a46494600010100000100010000ffd9'))
subprocess.run(['exiftool','-overwrite_original','-DateTimeOriginal=2026:07:25 12:00:00','/tmp/t.jpg'],check=True)
print(read_dates([Path('/tmp/t.jpg')]))
"
```
Expected: prints `{PosixPath('/tmp/t.jpg'): datetime.datetime(2026, 7, 25, 12, 0)}`.

- [ ] **Step 6: Commit**

```bash
git add iphoto_import/exif.py tests/test_exif.py
git commit -m "feat: exiftool batch date reader"
```

---

### Task 6: SMB auto-mount

**Files:**
- Create: `iphoto_import/mounts.py`, `tests/test_mounts.py`

**Interfaces:**
- Consumes: `Config` (Task 2).
- Produces:
  - `build_smb_url(host, user, password, share) -> str` — pure; returns `smb://user:pass@host/share` with user and password URL-encoded (`urllib.parse.quote`, `safe=""`).
  - `ensure_mounted(mount_point: Path, smb_url: str) -> None` — if `mount_point` is not already a mount, run `osascript -e 'mount volume "<smb_url>"'`; raise `MountError` if the mount point is still absent/unwritable afterward. Side-effecting; validated manually.
  - `class MountError(Exception)`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_mounts.py`:

```python
from iphoto_import.mounts import build_smb_url


def test_build_smb_url_basic():
    assert (
        build_smb_url("192.168.1.40", "bob", "pw", "Pictures")
        == "smb://bob:pw@192.168.1.40/Pictures"
    )


def test_build_smb_url_encodes_special_chars():
    url = build_smb_url("192.168.1.40", "bob", "p@s/w:d", "Pictures")
    assert url == "smb://bob:p%40s%2Fw%3Ad@192.168.1.40/Pictures"


def test_build_smb_url_encodes_username():
    url = build_smb_url("h", "a@b", "pw", "S")
    assert url == "smb://a%40b:pw@h/S"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_mounts.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'iphoto_import.mounts'`.

- [ ] **Step 3: Write minimal implementation**

Create `iphoto_import/mounts.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_mounts.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Manual mount check**

With `.env` populated and the server reachable, run:
```bash
python3 -c "
from iphoto_import.config import load_config_from_dotenv
from iphoto_import.mounts import build_smb_url, ensure_mounted
c = load_config_from_dotenv()
ensure_mounted(c.pictures_mount, build_smb_url(c.smb_host, c.smb_user, c.smb_pass, c.pictures_share))
ensure_mounted(c.videos_mount, build_smb_url(c.smb_host, c.smb_user, c.smb_pass, c.videos_share))
print('mounted:', c.pictures_mount, c.videos_mount)
"
```
Expected: both mount points exist under `/Volumes/` and the command prints `mounted: ...`.

- [ ] **Step 6: Commit**

```bash
git add iphoto_import/mounts.py tests/test_mounts.py
git commit -m "feat: SMB URL builder and auto-mount"
```

---

### Task 7: Device source (ImageCaptureCore) + FakeSource

**Files:**
- Create: `iphoto_import/source.py`, `tests/test_source_fake.py`

**Interfaces:**
- Consumes: `MediaItem` (Task 3).
- Produces:
  - `class PhotoSource` (protocol/base) with `list_items() -> List[MediaItem]`. Each returned `MediaItem.download(dest_dir: Path) -> Path` downloads the original into `dest_dir` and returns the written path.
  - `class FakeSource(PhotoSource)` built from `(name, creation_date, content_bytes)` tuples; its `download` writes the bytes — used by tests and Task 8.
  - `class ImageCaptureSource(PhotoSource)` — connects to the first camera device via `ICDeviceBrowser`, enumerates `mediaFiles`, and returns `MediaItem`s whose `download` calls `requestDownloadFile`. Validated manually on-device (Step 5); the fallback if the binding/behaviour misbehaves is the Swift helper (spec decision #1).

- [ ] **Step 1: Write the failing test (FakeSource contract)**

Create `tests/test_source_fake.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_source_fake.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'iphoto_import.source'`.

- [ ] **Step 3: Write the source module**

Create `iphoto_import/source.py`:

```python
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from .models import MediaItem


class PhotoSource:
    def list_items(self) -> List[MediaItem]:
        raise NotImplementedError


class FakeSource(PhotoSource):
    def __init__(self, rows: List[Tuple[str, Optional[datetime], bytes]]):
        self._rows = rows

    def list_items(self) -> List[MediaItem]:
        items = []
        for name, created, content in self._rows:
            def make_download(name=name, content=content):
                def download(dest_dir: Path) -> Path:
                    dest_dir = Path(dest_dir)
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    out = dest_dir / name
                    out.write_bytes(content)
                    return out
                return download

            items.append(MediaItem(name=name, creation_date=created, download=make_download()))
        return items


# --- Real device source (validated on-device; see Step 5) -------------------

class ImageCaptureError(Exception):
    pass


class ImageCaptureSource(PhotoSource):
    """Reads the first connected camera (iPhone) via ImageCaptureCore.

    Delegate callbacks are driven on a background run loop; list_items blocks
    until the device's file list is available (or times out).
    """

    def __init__(self, discovery_timeout: float = 30.0):
        self.discovery_timeout = discovery_timeout

    def list_items(self) -> List[MediaItem]:
        import ImageCaptureCore as ICC
        from Foundation import NSObject, NSRunLoop, NSDate
        import objc

        state = {"device": None, "done_files": False}
        lock = threading.Event()
        files_ready = threading.Event()

        class BrowserDelegate(NSObject):
            def deviceBrowser_didAddDevice_moreComing_(self, browser, device, more):
                if state["device"] is None and device.isKindOfClass_(ICC.ICCameraDevice):
                    state["device"] = device
                    device.setDelegate_(camera_delegate)
                    device.requestOpenSession()
                    lock.set()

        class CameraDelegate(NSObject):
            def deviceDidBecomeReady_(self, device):
                files_ready.set()

            def device_didAddItems_(self, device, items):
                files_ready.set()

            def cameraDeviceDidRemoveAccessRestriction_(self, device):
                pass

            def didRemoveDevice_(self, device):
                pass

        camera_delegate = CameraDelegate.alloc().init()
        browser_delegate = BrowserDelegate.alloc().init()

        browser = ICC.ICDeviceBrowser.alloc().init()
        browser.setDelegate_(browser_delegate)
        browser.setBrowsedDeviceTypeMask_(
            ICC.ICDeviceTypeMaskCamera | ICC.ICDeviceLocationTypeMaskLocal
        )
        browser.start()

        deadline = time.time() + self.discovery_timeout
        while time.time() < deadline and not files_ready.is_set():
            NSRunLoop.currentRunLoop().runMode_beforeDate_(
                "kCFRunLoopDefaultMode",
                NSDate.dateWithTimeIntervalSinceNow_(0.2),
            )
            if state["device"] is not None and state["device"].mediaFiles() is not None:
                files_ready.set()

        device = state["device"]
        if device is None:
            browser.stop()
            raise ImageCaptureError(
                "No iPhone/camera found. Plug in, unlock, and tap 'Trust'. "
                "If this is the first run, grant the macOS permission prompt."
            )

        media_files = device.mediaFiles() or []
        items: List[MediaItem] = []
        for f in media_files:
            name = f.name()
            created = _ns_to_datetime(f.creationDate())
            items.append(MediaItem(name=name, creation_date=created,
                                   download=_make_download(f)))
        return items


def _ns_to_datetime(ns_date) -> Optional[datetime]:
    if ns_date is None:
        return None
    return datetime.fromtimestamp(ns_date.timeIntervalSince1970())


def _make_download(camera_file):
    def download(dest_dir: Path) -> Path:
        import ImageCaptureCore as ICC
        from Foundation import NSRunLoop, NSDate, NSURL

        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        done = {"path": None, "error": None}

        def completion(err, saved_url):
            if err is not None:
                done["error"] = str(err)
            else:
                done["path"] = saved_url.path() if saved_url else None

        options = {
            ICC.ICDownloadsDirectoryURL: NSURL.fileURLWithPath_(str(dest_dir)),
            ICC.ICSaveAsFilename: camera_file.name(),
            ICC.ICOverwrite: True,
        }
        camera_file.requestDownloadWithOptions_downloadDelegate_didDownloadSelector_contextInfo_(
            options, _DownloadWaiter.alloc().initWithCallback_(completion), None, None
        )
        deadline = time.time() + 120
        while time.time() < deadline and done["path"] is None and done["error"] is None:
            NSRunLoop.currentRunLoop().runMode_beforeDate_(
                "kCFRunLoopDefaultMode", NSDate.dateWithTimeIntervalSinceNow_(0.2)
            )
        if done["error"]:
            raise ImageCaptureError(f"download failed for {camera_file.name()}: {done['error']}")
        return Path(done["path"])
    return download
```

Note: `_DownloadWaiter` is an Objective-C delegate object. Add it near the top of `source.py` (after imports are available at call time it is defined lazily). For clarity define it at module import guarded by macOS:

```python
try:
    from Foundation import NSObject

    class _DownloadWaiter(NSObject):
        def initWithCallback_(self, cb):
            self = objc_super_init(self)
            self._cb = cb
            return self

        def didDownloadFile_error_options_contextInfo_(self, file, error, options, ctx):
            saved = options.get("ICSavedFilename") if options else None
            self._cb(error, saved)
except Exception:  # non-macOS / binding unavailable at import
    _DownloadWaiter = None
```

> **Implementation note for the executor:** ImageCaptureCore's exact selector/option constant names (`ICDownloadsDirectoryURL`, `ICSavedFilename`, the download delegate selector) can vary slightly by macOS version. If Step 5 fails, print `dir(ImageCaptureCore)` and the `ICCameraFile` methods to confirm the real names, adjust, and re-run. If the binding cannot be made to work, switch to the Swift helper fallback (spec decision #1) — the rest of the pipeline (Tasks 8–9) consumes `PhotoSource` and is unaffected.

- [ ] **Step 4: Run the FakeSource test to verify it passes**

Run: `python3 -m pytest tests/test_source_fake.py -v`
Expected: PASS (2 tests). (The real `ImageCaptureSource` is not exercised here.)

- [ ] **Step 5: Manual on-device smoke test**

Plug in the unlocked iPhone (tap **Trust**), then:
```bash
python3 -c "
from iphoto_import.source import ImageCaptureSource
items = ImageCaptureSource().list_items()
print('found', len(items), 'items; first:', items[0].name, items[0].creation_date)
"
```
Expected: prints a nonzero count and a real filename/date. Grant the macOS permission prompt on first run. If it fails, follow the implementation note above.

- [ ] **Step 6: Commit**

```bash
git add iphoto_import/source.py tests/test_source_fake.py
git commit -m "feat: PhotoSource interface, FakeSource, ImageCaptureCore source"
```

---

### Task 8: Organizer (placement path + import orchestration)

**Files:**
- Create: `iphoto_import/organizer.py`, `tests/test_organizer.py`

**Interfaces:**
- Consumes: `Config` (2), `PlanEntry`/`PlanResult`/`build_plan` (4), `read_dates` (5), `PhotoSource`/`FakeSource` (7), `date_folder` (3).
- Produces:
  - `destination_path(media_type, folder, name, config) -> Path` — pure; `photo` → `pictures_mount/folder/name`, `video` → `videos_mount/folder/name`.
  - `dest_exists_checker(config) -> Callable[[str, str, str], bool]` — returns an `exists(media_type, folder, name)` bound to the config's mounts (used by `build_plan`).
  - `run_import(source, config, dry_run=False, verbose=False) -> ImportReport` — orchestrates: plan (using pre-download `creation_date`) → for each entry, download to staging → exiftool date → final `destination_path` (using authoritative date) → skip if final path exists, else move into place. Cleans staging. Returns counts.
  - `@dataclass ImportReport` with `photos: int`, `videos: int`, `skipped_existing: int`, `skipped_livephoto: int`, `errors: int`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_organizer.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_organizer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'iphoto_import.organizer'`.

- [ ] **Step 3: Write minimal implementation**

Create `iphoto_import/organizer.py`:

```python
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .classify import date_folder
from .config import Config
from .exif import read_dates
from .planner import build_plan
from .source import PhotoSource


@dataclass
class ImportReport:
    photos: int = 0
    videos: int = 0
    skipped_existing: int = 0
    skipped_livephoto: int = 0
    errors: int = 0


def destination_path(media_type: str, folder: str, name: str, config: Config) -> Path:
    root = config.pictures_mount if media_type == "photo" else config.videos_mount
    return root / folder / name


def dest_exists_checker(config: Config) -> Callable[[str, str, str], bool]:
    def exists(media_type: str, folder: str, name: str) -> bool:
        return destination_path(media_type, folder, name, config).exists()
    return exists


def run_import(source: PhotoSource, config: Config,
               dry_run: bool = False, verbose: bool = False) -> ImportReport:
    items = source.list_items()
    plan = build_plan(items, dest_exists_checker(config))
    report = ImportReport(
        skipped_existing=plan.skipped_existing,
        skipped_livephoto=plan.skipped_livephoto,
    )

    for entry in plan.to_import:
        if dry_run:
            _count(report, entry.media_type)
            if verbose:
                print(f"[dry-run] would import {entry.item.name} -> {entry.media_type}")
            continue
        try:
            config.staging_dir.mkdir(parents=True, exist_ok=True)
            staged = entry.item.download(config.staging_dir)
            exif_date = read_dates([staged]).get(Path(staged))
            folder = date_folder(exif_date)
            dest = destination_path(entry.media_type, folder, entry.item.name, config)
            if dest.exists():
                report.skipped_existing += 1
                staged.unlink(missing_ok=True)
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(staged), str(dest))
            _count(report, entry.media_type)
            if verbose:
                print(f"imported {entry.item.name} -> {dest}")
        except Exception as exc:  # per-file failure never aborts the run
            report.errors += 1
            print(f"ERROR importing {entry.item.name}: {exc}")
    return report


def _count(report: ImportReport, media_type: str) -> None:
    if media_type == "photo":
        report.photos += 1
    else:
        report.videos += 1
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_organizer.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add iphoto_import/organizer.py tests/test_organizer.py
git commit -m "feat: organizer placement and import orchestration"
```

---

### Task 9: CLI entry point + README

**Files:**
- Create: `import_photos.py`, `iphoto_import/cli.py`, `README.md`, `tests/test_cli.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `iphoto_import/cli.py`: `main(argv=None) -> int` — parse `--dry-run`, `--verbose`, `--staging`; load config; ensure both mounts (unless `--dry-run` skips mounting? no — dry-run still needs dest to check existence, so mount anyway); build `ImageCaptureSource`; call `run_import`; print the summary; return exit code (0 success, 1 on hard error).
  - `import_photos.py`: thin `sys.exit(main())` wrapper.

- [ ] **Step 1: Write the failing test**

Create `tests/test_cli.py`:

```python
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

    rc = cli.main(["--dry-run"])
    assert rc == 0
    assert "would import" in capsys.readouterr().out.lower() or "photos: 1" in capsys.readouterr().out.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'iphoto_import.cli'`.

- [ ] **Step 3: Write the CLI**

Create `iphoto_import/cli.py`:

```python
import argparse
import sys
from pathlib import Path
from typing import Optional

from .config import load_config_from_dotenv
from .mounts import build_smb_url, ensure_mounted, MountError
from .organizer import run_import
from .source import ImageCaptureSource


def ensure_all_mounts(config) -> None:
    ensure_mounted(
        config.pictures_mount,
        build_smb_url(config.smb_host, config.smb_user, config.smb_pass, config.pictures_share),
    )
    ensure_mounted(
        config.videos_mount,
        build_smb_url(config.smb_host, config.smb_user, config.smb_pass, config.videos_share),
    )


def build_source():
    return ImageCaptureSource()


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="Import iPhone photos/videos to SMB shares.")
    parser.add_argument("--dry-run", action="store_true", help="show the plan without downloading or writing")
    parser.add_argument("--verbose", action="store_true", help="log each file")
    parser.add_argument("--staging", type=Path, default=None, help="override staging directory")
    args = parser.parse_args(argv)

    try:
        config = load_config_from_dotenv()
    except KeyError as exc:
        print(f"Config error: missing {exc} in .env (copy .env.example).", file=sys.stderr)
        return 1
    if args.staging:
        config.staging_dir = args.staging

    try:
        ensure_all_mounts(config)
    except MountError as exc:
        print(f"Mount error: {exc}", file=sys.stderr)
        return 1

    try:
        source = build_source()
        report = run_import(source, config, dry_run=args.dry_run, verbose=args.verbose)
    except Exception as exc:
        print(f"Import failed: {exc}", file=sys.stderr)
        return 1

    label = "PLAN (dry-run)" if args.dry_run else "DONE"
    print(
        f"{label}: photos: {report.photos}, videos: {report.videos}, "
        f"skipped-existing: {report.skipped_existing}, "
        f"skipped-livephoto: {report.skipped_livephoto}, errors: {report.errors}"
    )
    return 0
```

- [ ] **Step 4: Write the entry point**

Create `import_photos.py`:

```python
#!/usr/bin/env python3
import sys
from iphoto_import.cli import main

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/test_cli.py -v`
Expected: PASS (1 test).

- [ ] **Step 6: Write the README**

Create `README.md`:

```markdown
# IphonePhotos

Import original photos & videos from a USB-connected iPhone into date-based
folders on two SMB-mounted SSD shares. Runs manually on a Mac mini. Non-destructive
and incremental.

## Setup
1. `python3 -m pip install -r requirements.txt`
2. `brew install exiftool`
3. `cp .env.example .env` and fill in SMB host, user, password, share names.
4. First run triggers a macOS prompt to access the iPhone — grant it.

## Use
Plug in the unlocked iPhone (tap **Trust**), then:

    python3 import_photos.py --dry-run     # preview
    python3 import_photos.py               # import
    python3 import_photos.py --verbose     # import, logging each file

Photos land in `/Volumes/<PICTURES_SHARE>/YYYY-MM-DD/`, videos in
`/Volumes/<VIDEOS_SHARE>/YYYY-MM-DD/`. Files already imported (same filename in
the same date folder) are skipped without re-downloading. Nothing is deleted
from the phone. Live Photo motion clips (a `.MOV` sharing a photo's name) are skipped.
```

- [ ] **Step 7: Run the full test suite**

Run: `python3 -m pytest -v`
Expected: PASS (all tests across tasks 1–9).

- [ ] **Step 8: End-to-end dry run on device**

With `.env` set, shares reachable, and the iPhone plugged in/unlocked:
```bash
python3 import_photos.py --dry-run
```
Expected: prints `PLAN (dry-run): photos: N, videos: M, ...` with sensible counts and no files written.

- [ ] **Step 9: Commit**

```bash
git add import_photos.py iphoto_import/cli.py README.md tests/test_cli.py
git commit -m "feat: CLI entry point and README"
```

---

## Self-Review Notes

- **Spec coverage:** device access via PyObjC/ImageCaptureCore (Task 7), EXIF date via exiftool with fallback order (Task 5) applied in placement (Task 8), flat `YYYY-MM-DD` folders (Task 3/8), two-share layout (Task 8), incremental filename+folder dedup without download (Task 4 pre-filter + Task 8 final re-check), copy-only (never deletes phone — Task 7/8), screenshots as photos (`.png` in `PHOTO_EXTS`, Task 3), Live-Photo motion skip (Task 4), manual trigger (Task 9 CLI), auto-mount with `.env` creds (Task 6/9), `.env` config + `.env.example` (Task 1/2). All covered.
- **Fallback:** Swift helper path is out of scope for this plan but flagged at Task 1 Step 7 and Task 7 Step 3; the `PhotoSource` boundary means only Task 7 changes if the fallback is needed.
- **Type consistency:** `MediaItem(name, creation_date, download)`, `PlanEntry(item, media_type, folder)`, `exists(media_type, folder, name)`, and `destination_path(media_type, folder, name, config)` names/signatures are consistent across Tasks 3–9.
```
