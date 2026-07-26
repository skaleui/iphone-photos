# IphonePhotos — Project Decisions

A pipeline that pulls original photos & videos directly off a USB-connected
iPhone and files them into date-based folders on an SSD, run manually from a
Mac mini.

## Topology
- **iPhone** → USB → **Mac mini** (the script runs here, on macOS).
- **Destination**: two separate SMB shares hosted by a Linux box (192.168.1.100),
  backed by an SSD, mounted on the Mac mini:
  - `smb://192.168.1.100/Pictures` → `/Volumes/Pictures`
  - `smb://192.168.1.100/Videos`   → `/Volumes/Videos`

## Decisions (captured during brainstorming)

1. **Device access:** Read the connected iPhone directly via Apple's
   **ImageCaptureCore** framework, driven from Python through **PyObjC**
   (all-Python, no manual Image Capture step, no separate Swift binary).
   - Fallback: a small Swift/ImageCaptureCore CLI + Python, only if the
     PyObjC `ImageCaptureCore` binding proves unavailable. (Xcode is installed.)
   - First run triggers a macOS TCC permission prompt to access the device;
     it must be granted.

2. **Date source:** EXIF/embedded "date taken" via **exiftool** (authoritative
   for placement). ImageCaptureCore's per-file `creationDate` is used as a fast
   pre-download filter. Fallback: file timestamp; else an `Unknown-Date/` folder.

3. **Folder structure:** Nested — a year parent, then one folder per day:
   `YYYY/YYYY-MM-DD` (e.g. `2026/2026-07-25`).

4. **Destination layout (two SMB shares):**
   - Photos → `/Volumes/Pictures/YYYY/YYYY-MM-DD/`  (incl. screenshots)
   - Videos → `/Volumes/Videos/YYYY/YYYY-MM-DD/`

4b. **Auto-mount:** The script mounts each share if not already mounted, using
    credentials from `.env`, via
    `osascript -e 'mount volume "smb://USER:PASS@192.168.1.100/<share>"'`
    (password URL-encoded). It verifies the real mount point (macOS may append
    `-1` if already mounted) and fails clearly if a share is
    unreachable/unwritable — before any download.

4c. **Config via `.env`:** SMB host, user, password, and share names live in a
    git-ignored `.env` (loaded at startup). A committed `.env.example` documents
    the keys. CLI flags carry runtime behavior only (`--dry-run`, `--verbose`,
    `--staging`).

5. **Incremental re-runs:** Skip files already imported, decided by
   **filename + destination date folder**. Because ImageCaptureCore exposes each
   file's name/date *before* download, already-imported files are skipped
   **without downloading** them.

6. **Copy only:** Never delete anything from the iPhone. Non-destructive.

7. **Screenshots (`.PNG`):** Included, treated as photos → `Pictures/`.

8. **Live Photo motion files:** Skipped. A `.MOV`/`.MP4` is treated as a Live
   Photo pair (and skipped) when a still image shares its base filename
   (e.g. `IMG_1234.HEIC` + `IMG_1234.MOV` → keep HEIC, skip MOV). Standalone
   videos → `Videos/`.

9. **Trigger:** Manual command run while the phone is plugged in.

10. **Language/tooling:** Python 3 + PyObjC (ImageCaptureCore) + exiftool, on macOS.

## File types
- Photos → `Pictures/`: `.heic .heif .jpg .jpeg .png`
- Videos → `Videos/`: `.mov .mp4 .m4v`

## Config (`.env`, git-ignored)
```
SMB_HOST=192.168.1.100
SMB_USER=youruser
SMB_PASS=yourpassword
PICTURES_SHARE=Pictures
VIDEOS_SHARE=Videos
# optional: STAGING_DIR=/Users/you/.iphone-import-staging
```
Mount points derived as `/Volumes/<share>`. A `.env.example` (no secrets) is committed.

## CLI (planned)
```
python3 import_photos.py [--staging PATH] [--dry-run] [--verbose]
```
(No `--source`: the connected iPhone is auto-discovered via ImageCaptureCore.
Host/credentials/shares come from `.env`.)
