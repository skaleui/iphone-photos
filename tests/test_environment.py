import importlib
import shutil


def test_imagecapturecore_binding_importable():
    # The whole device-access approach depends on this PyObjC binding.
    # If this fails, fall back to the Swift helper (see spec, decision #1).
    importlib.import_module("ImageCaptureCore")


def test_exiftool_on_path():
    assert shutil.which("exiftool") is not None, "install with: brew install exiftool"
