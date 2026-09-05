"""Game process handling: find, platform detection by exe path, kill, launch."""

from __future__ import annotations

import os
import subprocess
import sys
import time

import psutil

from .types import PROCESS_NAMES

STEAM_APP_ID = "1013320"
STEAM_URL = f"steam://rungameid/{STEAM_APP_ID}"
EPIC_URL = (
    "com.epicgames.launcher://apps/"
    "bda8d2133655435982b9118972792328%3Ae0aa26672dcb40c3a137ced30ed1f160"
    "%3A43d4ef20fcb94eb39a864d13164fe3ca?action=launch&silent=true"
)


def find_game_process() -> psutil.Process | None:
    for p in psutil.process_iter(["name"]):
        if p.info["name"] in PROCESS_NAMES:
            return p
    return None


def exe_path(proc: psutil.Process | None = None) -> str:
    proc = proc or find_game_process()
    if proc is None:
        return ""
    try:
        return proc.exe()
    except (psutil.Error, OSError):
        return ""


def detect_platform(path: str | None = None) -> str:
    """'steam', 'epic' or 'unknown' from the running exe path."""
    p = (path if path is not None else exe_path()).lower().replace("\\", "/")
    if "/steamapps/" in p or "/steam/" in p:
        return "steam"
    if "/epic games/" in p or "epicgames" in p:
        return "epic"
    return "unknown"


def kill_game(timeout: float = 10.0) -> bool:
    """Terminate every Firestone process (AHK `Process, Close`). Returns True if none remain."""
    procs = [p for p in psutil.process_iter(["name"]) if p.info["name"] in PROCESS_NAMES]
    for p in procs:
        try:
            p.kill()
        except psutil.Error:
            pass
    _, alive = psutil.wait_procs(procs, timeout=timeout)
    return not alive


def launch_game(platform: str) -> None:
    """Relaunch through the store client (AHK `Run, explorer.exe steam://...`)."""
    url = {"steam": STEAM_URL, "epic": EPIC_URL}[platform]
    if sys.platform == "win32":
        os.startfile(url)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", url])
    else:
        subprocess.Popen(["xdg-open", url])


def wait_for_game(timeout: float = 120.0, poll: float = 1.0) -> psutil.Process | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        p = find_game_process()
        if p is not None:
            return p
        time.sleep(poll)
    return None


EPIC_DEFAULT_EXE = r"C:\Program Files\Epic Games\FirestoneOnlineIdleRPG\Firestone.exe"
STEAM_ROOTS_WIN = (r"C:\Program Files (x86)\Steam", r"C:\Program Files\Steam")
STEAM_ROOTS_MAC = (os.path.expanduser("~/Library/Application Support/Steam"),)
STEAM_ROOTS_LINUX = (
    os.path.expanduser("~/.steam/steam"),
    os.path.expanduser("~/.local/share/Steam"),
)
# Relative path of the game binary inside a Steam library (Firestone.app on macOS)
STEAM_GAME_FILE = {
    "win32": ("Firestone", "Firestone.exe"),
    "darwin": ("Firestone", "Firestone.app"),
}.get(sys.platform, ("Firestone", "Firestone.x86_64"))


def _steam_library_paths() -> list[str]:
    """Steam library roots from libraryfolders.vdf (default install of each OS)."""
    import re

    roots = []
    bases = {"win32": STEAM_ROOTS_WIN, "darwin": STEAM_ROOTS_MAC}.get(
        sys.platform, STEAM_ROOTS_LINUX
    )
    for base in bases:
        vdf = os.path.join(base, "steamapps", "libraryfolders.vdf")
        if os.path.exists(vdf):
            roots.append(base)
            try:
                with open(vdf, encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except OSError:
                continue
            roots += [p.replace("\\\\", "\\") for p in re.findall(r'"path"\s+"([^"]+)"', text)]
    return roots


def installed_platforms() -> list[str]:
    """Stores with a Firestone install on this machine, e.g. ['epic', 'steam'] (Epic has no
    macOS / Linux client, so only Steam is looked up there)."""
    found = []
    if sys.platform == "win32" and os.path.exists(EPIC_DEFAULT_EXE):
        found.append("epic")
    for root in _steam_library_paths():
        if os.path.exists(os.path.join(root, "steamapps", "common", *STEAM_GAME_FILE)):
            found.append("steam")
            break
    return found


def choose_platform(setting: str, last: str = "") -> str | None:
    """Platform to launch: the GamePlatform setting, else the running game's store, else the
    platform used last, else the first install found."""
    setting = (setting or "auto").strip().lower()
    if setting in ("steam", "epic"):
        return setting
    running = detect_platform()
    if running in ("steam", "epic"):
        return running
    installed = installed_platforms()
    if last in installed:
        return last
    return installed[0] if installed else None
