# Progress

- Resumed the in-progress Photos library source work on 2026-10-30.
- Current changes add `--source photos`, `--library`, and `osxphotos` integration; generated import logs are untracked.
- Validation complete: `.venv/bin/python -m pytest -q` passes all 38 tests.
- Runtime smoke test complete: `import_photos.py --source photos --dry-run` planned 272 photos and 42 videos, skipped 447 existing files, and reported 0 errors.
- Runtime contract verified against `osxphotos 0.77.2`: `PhotoInfo.export()` returns `list[str]` as expected.
- Non-destructive rerun on 2026-11-01 completed with fresh staging: 1 photo imported, 523 existing files skipped, 16 source-export errors, and no source deletion.
- Authorized destructive rerun on 2026-11-01 completed: 0 new imports, 524 existing files skipped, 16 source-export errors, and 0 source deletions.
- Fixed destructive cleanup completed on 2026-11-01: 513 existing destination matches were moved from Photos to Recently Deleted, 16 export failures were protected, and no new files were imported. Including the single verified probe deletion before the bulk run, 514 source assets were moved during this cleanup effort.
- Final already-imported cleanup on 2026-11-01 found no remaining destination matches to delete; the same 16 unexportable assets remain protected.
- Destructive rerun on 2026-11-01 again found 0 destination matches and 16 export failures. Verification: 16 assets remain in the active library and Photos reports 800 items in Recently Deleted.
- Destructive rerun after iCloud download on 2026-11-01: 7 photos imported, 3 existing destinations verified, 10 source assets moved to Recently Deleted, and 6 export failures remained protected.
- 2026-11-09 (paused): Started read-only comparison of iPhone files vs SMB destinations to identify already-imported files for deletion from the phone. Scratch script `compare_iphone.py` (session scratchpad) checks name + byte-size match; scan was stopped before finishing. Next: rerun the scan, review the IMPORTED_VERIFIED list with the user, then confirm before deleting anything from the iPhone (watch Live Photo motion clips and iCloud Photos sync). No files have been deleted.
- 2026-11-16: iPhone import completed after SMB server (10.0.0.40) came back online: 38 photos and 2 videos imported, 805 already-imported files skipped, 1 unsupported file skipped, 0 errors, nothing deleted from the phone. The iPhone-deletion comparison is still paused.
