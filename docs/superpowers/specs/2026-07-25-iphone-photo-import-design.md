# iPhone → SSD Photo Import Pipeline — Design Spec

**Date:** 2026-07-25
**Status:** Approved for planning

## 1. Purpose

Pull original photos and videos directly off a USB-connected iPhone and file them
into date-based folders on an SSD, run manually from a Mac mini. The import is
**non-destructive** (nothing is deleted from the phone) and **incremental**
(re-runs copy only new files).

## 2. Topology

- **iPhone** → USB → **Mac mini**. The script runs on macOS.
- **Destination**: two separate SMB shares hosted by a Linux box at `192.168.1.40`,
  backed by an SSD, mounted on the Mac mini:
  - `smb://192.168.1.40/Pictures` → `/Volumes/Pictures`
  - `smb://192.168.1.40/Videos`   → `/Volumes/Videos`

## 3. Confirmed decisions

| # | Decision |
|---|----------|
| 1 | **Device access** via Apple **ImageCaptureCore**, driven from Python through **PyObjC** (all-Python; no manual Image Capture step, no separate binary). Fallback: a small Swift/ImageCaptureCore CLI + Python, only if the PyObjC `ImageCaptureCore` binding is unavailable (Xcode is installed). |
| 2 | **Date for placement** = EXIF/embedded "date taken" via **exiftool** (authoritative). ImageCaptureCore per-file `creationDate` is a pre-download filter only. Fallback: file timestamp; else an `Unknown-Date/` folder. |
| 3 | **Folder structure**: flat, one folder per day, `YYYY-MM-DD`. |
| 4 | **Destination layout** (two shares): photos → `/Volumes/Pictures/YYYY-MM-DD/`; videos → `/Volumes/Videos/YYYY-MM-DD/`. |
| 5 | **Incremental**: skip files already imported, decided by **filename + destination date folder**. Because names/dates are known before download, already-imported files are skipped **without downloading**. |
| 6 | **Copy only**: never delete from the iPhone. |
| 7 | **Screenshots (`.png`)**: included, treated as photos. |
| 8 | **Live Photo motion files**: skipped — a `.mov`/`.mp4` is treated as a Live Photo pair (and skipped) when a still image shares its base filename. Standalone videos are kept. |
| 9 | **Trigger**: manual command run while the phone is plugged in. |
| 10 | **Auto-mount**: the script mounts each SMB share if not already mounted, using credentials from `.env`, and fails clearly if unreachable, before any download. |
| 11 | **Stack**: Python 3 + PyObjC (ImageCaptureCore) + exiftool, on macOS. |
| 12 | **Config via `.env`**: SMB host, username, password, and share names live in a `.env` file (loaded at startup). A committed `.env.example` documents the keys; the real `.env` is git-ignored. CLI flags are for runtime behavior only (`--dry-run`, `--verbose`, `--staging`). |

## 4. File types

- Photos → `/Volumes/Pictures/`: `.heic .heif .jpg .jpeg .png`
- Videos → `/Volumes/Videos/`: `.mov .mp4 .m4v`

## 4b. Configuration (`.env`)

Connection settings and credentials are loaded from a `.env` file at startup
(via `python-dotenv`, or a minimal parser). Keys:

```
SMB_HOST=192.168.1.40
SMB_USER=youruser
SMB_PASS=yourpassword
PICTURES_SHARE=Pictures
VIDEOS_SHARE=Videos
# optional overrides
# STAGING_DIR=/Users/you/.iphone-import-staging
```

- Mount points are derived as `/Volumes/<share>`.
- A `.env.example` (no secrets) is committed; the real `.env` is git-ignored.
- The password is URL-encoded (`urllib.parse.quote`) when building the
  `smb://user:pass@host/share` mount URL, so special characters are safe.

## 5. Architecture

A single Python 3 CLI on the Mac mini. Pipeline:

```
ensure mounts → discover device → list files (name+date+type)
   → plan (classify / Live-Photo pair / dedup)
   → download new files to staging
   → exiftool date → place into date folders → report
```

### 5.1 Testable core via a `PhotoSource` interface

The device layer is hidden behind a small interface so the logic is testable
without a phone:

- `PhotoSource` yields items of `(name, creation_date, media_type, download_fn)`.
- Real implementation: `ImageCaptureSource` (PyObjC/ImageCaptureCore).
- Test implementation: `FakeSource` built from synthetic item lists.

The **planner/organizer** (classification, Live-Photo pairing, date-folder
selection, dedup) is pure and consumes `PhotoSource` items — fully unit-testable.

## 6. Run flow

1. **Ensure mounts.** Load `.env`. For each share: if its mount point is absent,
   mount using the `.env` credentials, e.g.
   `osascript -e 'mount volume "smb://USER:PASS@192.168.1.40/<share>"'`
   (password URL-encoded). Resolve the actual mount point (macOS may append `-1`
   if already mounted). Verify writability. On failure → clear error, exit before
   any download.
2. **Discover iPhone** via `ICDeviceBrowser`. Errors clearly if no device /
   not trusted / TCC permission denied. (First run triggers the TCC prompt.)
3. **Enumerate** camera files → `(name, creationDate, type)` without downloading.
4. **Plan** (pure):
   - Split photo vs video by extension.
   - Compute the set of still-image base names; **drop** any `.mov`/`.mp4`
     whose base name matches a still (Live Photo).
   - Prospective date folder from `creationDate`.
   - Mark **skip** if `filename` already exists in that destination date folder.
5. **Download** only non-skipped files into a local **staging** folder.
6. **exiftool** (single batch call, JSON) over staged files → authoritative date.
   `DateTimeOriginal` → `CreateDate` → `FileModifyDate` → else `Unknown-Date/`.
7. **Place** each staged file via `shutil.move` into
   `/Volumes/Pictures|Videos/<YYYY-MM-DD>/<name>`, creating folders as needed,
   tolerating SMB partial metadata-copy quirks. If the final destination already
   exists (e.g. date differed from the pre-filter), skip. Clean staging.
8. **Report**: downloaded photos, downloaded videos, skipped-existing,
   skipped-LivePhoto, errors.

### 6.1 Date-disagreement note

The pre-download filter uses `creationDate`; final placement uses exiftool. If
they disagree across a day boundary, the worst case is one needless re-download.
A duplicate is never written, because final placement re-checks existence.

## 7. CLI

```
python3 import_photos.py [--staging PATH] [--dry-run] [--verbose]
```

- No `--source`: the iPhone is auto-discovered.
- Host, credentials, and share names come from `.env` (§4b); the CLI carries
  runtime flags only.
- `--dry-run`: ensure mounts, enumerate, and print the plan (skip / download+place)
  **without downloading or writing** — the safe first smoke test.

## 8. Error handling

- No device / not trusted / TCC denied → clear message, exit.
- Share unreachable/unwritable, or exiftool missing → exit **before** any download.
- Per-file download or placement failure → logged; the run continues.
- File with no readable date → `Unknown-Date/` rather than crashing.

## 9. Prerequisites (verified/installed during implementation)

- `exiftool` (`brew install exiftool`).
- PyObjC with the `ImageCaptureCore` binding — **verified as implementation step 1**;
  if unavailable, fall back to the Swift helper (Xcode present).
- `python-dotenv` (or a minimal built-in `.env` parser).
- A populated `.env` (copied from `.env.example`); SMB shares reachable from the Mac.

## 10. Testing

- **Unit tests** on the pure planner using `FakeSource`: date-folder selection,
  photo/video split, Live-Photo pairing/skip, filename+folder dedup, Unknown-Date
  fallback.
- **Manual integration**: `--dry-run` against the real connected iPhone, then a
  real run; verify folders and file counts on the SSD.

## 11. Out of scope

- Automatic (unattended) triggering on plug-in — manual only for now.
- Deleting from the phone; deduplication by content hash; RAW/other formats;
  the macOS Photos library.
