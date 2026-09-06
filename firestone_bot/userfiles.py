"""Find and import the user's files (settings.ini and friends) from another bot folder.

A user who downloads a release by hand unzips it somewhere new and starts it there: no
settings.ini next to the exe, defaults in use, the previous folder still holds their real
settings. At start-up the GUI offers to copy them over (see App._offer_settings_import);
Advanced > Files has the same import for any folder. Existing files are never overwritten.
"""

from __future__ import annotations

import os
import shutil
import sys
import time
from dataclasses import dataclass

USER_FILES = ("settings.ini", "MapStartState.ini", "gui_state.json")
SETTINGS_SECTION = "[CommonOptions]"
MAX_DIRS = 3000
MAX_DEPTH = 3
SKIP_DIRS = {"_internal", "node_modules", ".git", ".venv", "Library", "AppData", "Contents"}


@dataclass
class Candidate:
    folder: str
    mtime: float

    @property
    def label(self) -> str:
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(self.mtime))
        return f"{self.folder}  (settings.ini modified {when})"


def looks_like_bot_settings(path: str) -> bool:
    """True when the file is a Firestone bot settings.ini (UTF-16 or UTF-8)."""
    try:
        with open(path, "rb") as f:
            raw = f.read(65536)
    except OSError:
        return False
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            text = raw.decode("utf-16", errors="ignore")
        except ValueError:
            return False
    else:
        text = raw.decode("utf-8", errors="ignore")
    return SETTINGS_SECTION in text


def search_roots(base: str) -> list[str]:
    """Where a previous bot folder is likely to be: around this install, then the usual user
    folders (same list on Windows, macOS and Linux)."""
    home = os.path.expanduser("~")
    parent = os.path.dirname(base)
    roots = [parent, os.path.dirname(parent)]
    roots += [os.path.join(home, d) for d in ("Desktop", "Downloads", "Documents", "Games")]
    if sys.platform == "win32":
        for var in ("USERPROFILE", "PUBLIC"):
            if os.environ.get(var):
                roots.append(os.path.join(os.environ[var], "Desktop"))
    out: list[str] = []
    for r in roots:
        r = os.path.abspath(r)
        if r not in out and os.path.isdir(r) and r != os.path.abspath(home):
            out.append(r)
    return out


def find_candidates(base: str, roots: list[str] | None = None) -> list[Candidate]:
    """Folders (other than `base`) holding a bot settings.ini, newest first. Bounded walk."""
    base = os.path.abspath(base)
    roots = search_roots(base) if roots is None else roots
    seen: set[str] = set()
    found: dict[str, Candidate] = {}
    budget = MAX_DIRS
    for root in roots:
        root_depth = root.rstrip(os.sep).count(os.sep)
        for dirpath, dirnames, filenames in os.walk(root):
            budget -= 1
            if budget <= 0:
                break
            depth = dirpath.rstrip(os.sep).count(os.sep) - root_depth
            dirnames[:] = (
                [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
                if depth < MAX_DEPTH
                else []
            )
            dirpath = os.path.abspath(dirpath)
            if dirpath in seen or dirpath == base:
                continue
            seen.add(dirpath)
            if "settings.ini" in filenames:
                path = os.path.join(dirpath, "settings.ini")
                if looks_like_bot_settings(path):
                    found[dirpath] = Candidate(dirpath, os.path.getmtime(path))
    return sorted(found.values(), key=lambda c: c.mtime, reverse=True)


def import_user_files(src: str, base: str) -> tuple[list[str], list[str]]:
    """Copy the user files present in `src` into `base`. Returns (copied, skipped): a file
    already in `base` is never overwritten. The source is left untouched."""
    copied, skipped = [], []
    for name in USER_FILES:
        s, d = os.path.join(src, name), os.path.join(base, name)
        if not os.path.isfile(s):
            continue
        if os.path.exists(d):
            skipped.append(name)
            continue
        shutil.copy2(s, d)
        copied.append(name)
    return copied, skipped
