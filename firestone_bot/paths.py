"""Where the bot keeps its files, per OS.

- Windows / Linux: next to the exe (portable install, what the AHK bot did); from source, the
  current directory.
- macOS: ~/Library/Application Support/FirestoneBot. The bundle usually sits in /Applications,
  and Desktop, Documents and Downloads are protected folders (every access asks the user for a
  permission), so nothing user-related lives next to the .app. From source, the current
  directory, like the other OSes.
"""

from __future__ import annotations

import os
import sys

APP_SUPPORT_NAME = "FirestoneBot"
PROTECTED_MAC_FOLDERS = ("Desktop", "Documents", "Downloads", "Music", "Pictures", "Movies")


def frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundle_path() -> str | None:
    """The FirestoneBot.app bundle when running from one, else None."""
    if not frozen() or sys.platform != "darwin":
        return None
    exe_dir = os.path.dirname(sys.executable)
    if exe_dir.endswith(os.path.join(".app", "Contents", "MacOS")):
        return os.path.dirname(os.path.dirname(exe_dir))
    return None


def data_dir() -> str:
    """Folder holding settings.ini, MapStartState.ini, gui_state.json, the log and the kept
    previous version. Created when missing."""
    if frozen():
        if sys.platform == "darwin":
            d = os.path.join(
                os.path.expanduser("~"), "Library", "Application Support", APP_SUPPORT_NAME
            )
            os.makedirs(d, exist_ok=True)
            return d
        return os.path.dirname(sys.executable)
    return os.getcwd()


def is_protected_mac_folder(path: str) -> bool:
    """True when reading `path` would trigger a macOS privacy prompt (Desktop, Documents...)."""
    if sys.platform != "darwin":
        return False
    home = os.path.abspath(os.path.expanduser("~"))
    path = os.path.abspath(path)
    for name in PROTECTED_MAC_FOLDERS:
        folder = os.path.join(home, name)
        if path == folder or path.startswith(folder + os.sep):
            return True
    return False


def applications_dirs() -> list[str]:
    return ["/Applications", os.path.join(os.path.expanduser("~"), "Applications")]


def in_applications(path: str) -> bool:
    # both sides through abspath: on Windows (tests, dev) "/Applications" becomes a drive path
    path = os.path.abspath(path)
    return any(path.startswith(os.path.abspath(d) + os.sep) for d in applications_dirs())


def is_translocated(path: str) -> bool:
    """Gatekeeper runs a quarantined app from a read-only, randomised mount
    (/private/var/folders/.../AppTranslocation/...): the bundle cannot be moved from there."""
    return "/AppTranslocation/" in os.path.abspath(path)


def original_bundle_path(path: str) -> str | None:
    """The location the user launched a translocated app from (Security framework), None
    when the app is not translocated or the lookup fails."""
    if sys.platform != "darwin" or not is_translocated(path):
        return None
    try:
        import ctypes
        from urllib.parse import unquote, urlparse

        import objc
        from CoreFoundation import (
            CFURLCreateWithFileSystemPath,
            CFURLGetString,
            kCFURLPOSIXPathStyle,
        )

        sec = ctypes.CDLL("/System/Library/Frameworks/Security.framework/Security")
        fn = sec.SecTranslocateCreateOriginalPathForURL
        fn.restype = ctypes.c_void_p
        fn.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        url = CFURLCreateWithFileSystemPath(None, path, kCFURLPOSIXPathStyle, True)
        ref = fn(objc.pyobjc_id(url), None)
        if not ref:
            return None
        original = objc.objc_object(c_void_p=ref)
        text = str(CFURLGetString(original))
        return unquote(urlparse(text).path).rstrip("/")
    except Exception:  # noqa: BLE001 - best effort, the caller falls back to a copy
        return None
