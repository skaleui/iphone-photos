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


# --- Real device source -----------------------------------------------------
#
# API names below were verified by inspecting the actual PyObjC binding on
# this machine (macOS, Python 3.14.6, pyobjc-framework-ImageCaptureCore), not
# just taken from documentation:
#
#   ICDeviceBrowser.setBrowsedDeviceTypeMask_, .setDelegate_, .start, .stop
#   ICDeviceBrowserDelegate (formal protocol, introspected via
#       objc.protocolNamed("ICDeviceBrowserDelegate")):
#       deviceBrowser:didAddDevice:moreComing:      (required)
#       deviceBrowser:didRemoveDevice:moreGoing:    (required)
#   ICCameraDevice.mediaFiles, .requestOpenSessionWithOptions:completion:,
#       .setDelegate_
#   ICDeviceDelegate (required): device:didOpenSessionWithError:,
#       device:didCloseSessionWithError:, didRemoveDevice:
#   ICCameraDeviceDelegate (required, several): cameraDevice:didAddItems:,
#       cameraDevice:didRemoveItems:, cameraDevice:didReceiveThumbnail:forItem:error:,
#       cameraDevice:didReceiveMetadata:forItem:error:, cameraDevice:didRenameItems:,
#       cameraDeviceDidChangeCapability:, cameraDevice:didReceivePTPEvent:,
#       deviceDidBecomeReadyWithCompleteContentCatalog:,
#       cameraDeviceDidRemoveAccessRestriction:, cameraDeviceDidEnableAccessRestriction:
#   ICCameraFile.name, .creationDate, .requestDownloadWithOptions:completion:
#
# Deviations from the task brief's example:
#   - Session open and file download both use the *completion-block* selector
#     variants (requestOpenSessionWithOptions:completion:,
#     requestDownloadWithOptions:completion:) rather than the old-style
#     delegate+selector variants the brief sketched
#     (requestDownloadWithOptions_downloadDelegate_didDownloadSelector_...).
#     PyObjC bridges Objective-C completion blocks to plain Python callables
#     directly, so no separate "_DownloadWaiter" NSObject subclass is needed
#     for downloads (the brief's sketch of that helper also called an
#     undefined `objc_super_init`, which would not have worked as written).
#   - The brief's CameraDelegate used a nonexistent method name
#     `device_didAddItems_`; the real ICCameraDeviceDelegate selector is
#     `cameraDevice:didAddItems:`. The readiness signal used here is
#     `deviceDidBecomeReadyWithCompleteContentCatalog:`, which is the
#     ICCameraDeviceDelegate method that fires once the camera's full file
#     catalog has been enumerated (the brief's `deviceDidBecomeReady:` is a
#     generic ICDeviceDelegate method and is not guaranteed to mean the file
#     list is populated).
#   - Because ICDeviceDelegate/ICCameraDeviceDelegate mark several methods as
#     "required" in the formal protocol, this module defines no-op stubs for
#     all of them on the delegate class. PyObjC delegates are duck-typed (no
#     enforced conformance), but if ImageCaptureCore calls a "required"
#     selector the delegate object doesn't implement, that is an
#     unrecognized-selector crash. Implementing no-op stubs for all of them
#     is cheap insurance against that failure mode, which cannot be fully
#     exercised without a real device attached.


class ImageCaptureError(Exception):
    pass


class ImageCaptureSource(PhotoSource):
    """Reads the first connected camera (iPhone) via ImageCaptureCore.

    Delegate callbacks are driven by pumping the current run loop; list_items
    blocks until the device's file list is available (or discovery/open/ready
    times out).

    Session lifetime: the device session opened in list_items() is
    intentionally left OPEN when the method returns. The per-file download()
    closures run later (Task 8's organizer) and require the session to still
    be open. This is a one-shot CLI, so the session's lifetime is the process
    and the OS reclaims it on exit. (Stopping the browser only ends device
    discovery; it does not close an already-open device session.)

    Object lifetime: the browser, both delegates, and the found device are
    intentionally retained as instance attributes (self._browser,
    self._browser_delegate, self._camera_delegate, self._device) rather than
    left as list_items() locals. ImageCaptureCore holds the device delegate
    WEAKLY, so if these were collected when list_items() returns, a delegate
    callback firing during a deferred download() would hit a dangling
    reference (unrecognized-selector crash), and deallocating the browser
    could tear down the device the closures depend on. Keeping strong refs on
    the instance (which the CLI holds for the whole run) prevents that.
    """

    def __init__(self, discovery_timeout: float = 30.0, ready_timeout: float = 30.0):
        self.discovery_timeout = discovery_timeout
        self.ready_timeout = ready_timeout
        self._browser = None
        self._browser_delegate = None
        self._camera_delegate = None
        self._device = None

    def list_items(self) -> List[MediaItem]:
        import ImageCaptureCore as ICC
        from Foundation import NSObject

        state = {"device": None, "open_error": None}
        device_found = threading.Event()
        session_done = threading.Event()
        files_ready = threading.Event()

        class BrowserDelegate(NSObject):
            def deviceBrowser_didAddDevice_moreComing_(self, browser, device, more):
                if state["device"] is None and device.isKindOfClass_(ICC.ICCameraDevice):
                    state["device"] = device
                    device_found.set()

            def deviceBrowser_didRemoveDevice_moreGoing_(self, browser, device, more):
                pass

        class CameraDelegate(NSObject):
            # --- readiness signal we actually care about ---
            def deviceDidBecomeReadyWithCompleteContentCatalog_(self, device):
                files_ready.set()

            # --- ICDeviceDelegate required no-ops ---
            def device_didOpenSessionWithError_(self, device, error):
                pass

            def device_didCloseSessionWithError_(self, device, error):
                pass

            def didRemoveDevice_(self, device):
                pass

            # --- ICCameraDeviceDelegate required no-ops ---
            def cameraDevice_didAddItems_(self, device, items):
                files_ready.set()

            def cameraDevice_didRemoveItems_(self, device, items):
                pass

            def cameraDevice_didReceiveThumbnail_forItem_error_(self, device, thumbnail, item, error):
                pass

            def cameraDevice_didReceiveMetadata_forItem_error_(self, device, metadata, item, error):
                pass

            def cameraDevice_didRenameItems_(self, device, items):
                pass

            def cameraDeviceDidChangeCapability_(self, device):
                pass

            def cameraDevice_didReceivePTPEvent_(self, device, event):
                pass

            def cameraDeviceDidRemoveAccessRestriction_(self, device):
                pass

            def cameraDeviceDidEnableAccessRestriction_(self, device):
                pass

        # Retain on the instance (not just as locals): ImageCaptureCore holds the
        # device delegate weakly, and the download() closures returned below run
        # after this method returns. If these were collected, a delegate callback
        # during a deferred download would hit a dangling reference. See class docstring.
        camera_delegate = CameraDelegate.alloc().init()
        browser_delegate = BrowserDelegate.alloc().init()
        self._camera_delegate = camera_delegate
        self._browser_delegate = browser_delegate

        browser = ICC.ICDeviceBrowser.alloc().init()
        self._browser = browser
        browser.setDelegate_(browser_delegate)
        browser.setBrowsedDeviceTypeMask_(
            ICC.ICDeviceTypeMaskCamera | ICC.ICDeviceLocationTypeMaskLocal
        )
        browser.start()

        try:
            _pump_runloop_until(self.discovery_timeout, device_found.is_set)

            device = state["device"]
            if device is None:
                raise ImageCaptureError(
                    "No iPhone/camera found. Plug in, unlock, and tap 'Trust'. "
                    "If this is the first run, grant the macOS permission prompt."
                )

            self._device = device
            device.setDelegate_(camera_delegate)

            def open_completion(error):
                state["open_error"] = error
                session_done.set()

            # NOTE: this session is intentionally NOT closed by list_items().
            # The per-file download() closures returned below run later (Task 8's
            # organizer) and require this session to remain open. As a one-shot
            # CLI, the session's lifetime is the process and the OS reclaims it on
            # exit. The finally: below stops the *browser* (discovery only), which
            # does not close an already-open device session.
            device.requestOpenSessionWithOptions_completion_(None, open_completion)
            _pump_runloop_until(self.discovery_timeout, session_done.is_set)

            if not session_done.is_set():
                raise ImageCaptureError("Timed out opening a session with the camera.")
            if state["open_error"] is not None:
                raise ImageCaptureError(f"Failed to open camera session: {state['open_error']}")

            def files_present():
                files = device.mediaFiles()
                return files is not None and len(files) > 0

            _pump_runloop_until(self.ready_timeout, lambda: files_ready.is_set() or files_present())

            media_files = device.mediaFiles() or []
            items: List[MediaItem] = []
            for f in media_files:
                name = f.name()
                created = _ns_to_datetime(f.creationDate())
                items.append(MediaItem(name=name, creation_date=created, download=_make_download(f)))

            return items
        finally:
            browser.stop()


def _pump_runloop_until(timeout: float, predicate) -> None:
    from Foundation import NSRunLoop, NSDefaultRunLoopMode, NSDate

    deadline = time.time() + timeout
    run_loop = NSRunLoop.currentRunLoop()
    while time.time() < deadline and not predicate():
        run_loop.runMode_beforeDate_(
            NSDefaultRunLoopMode, NSDate.dateWithTimeIntervalSinceNow_(0.2)
        )


def _ns_to_datetime(ns_date) -> Optional[datetime]:
    if ns_date is None:
        return None
    return datetime.fromtimestamp(ns_date.timeIntervalSince1970())


def _make_download(camera_file):
    def download(dest_dir: Path, timeout: float = 120.0) -> Path:
        import ImageCaptureCore as ICC
        from Foundation import NSURL

        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        result = {"path": None, "error": None, "done": False}

        def completion(info, error):
            if error is not None:
                result["error"] = str(error)
            else:
                saved_name = None
                if info:
                    saved_name = info.get(ICC.ICSavedFilename)
                result["path"] = str(dest_dir / (saved_name or camera_file.name()))
            result["done"] = True

        options = {
            ICC.ICDownloadsDirectoryURL: NSURL.fileURLWithPath_(str(dest_dir)),
            ICC.ICSaveAsFilename: camera_file.name(),
            ICC.ICOverwrite: True,
        }
        camera_file.requestDownloadWithOptions_completion_(options, completion)
        _pump_runloop_until(timeout, lambda: result["done"])

        if not result["done"]:
            raise ImageCaptureError(f"download timed out for {camera_file.name()}")
        if result["error"]:
            raise ImageCaptureError(f"download failed for {camera_file.name()}: {result['error']}")
        return Path(result["path"])

    return download
