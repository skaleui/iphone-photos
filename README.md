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
