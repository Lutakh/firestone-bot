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
    path = os.path.abspath(path)
    return any(path.startswith(d + os.sep) for d in applications_dirs())
