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
