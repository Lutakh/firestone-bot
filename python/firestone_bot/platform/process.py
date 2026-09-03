"""Game process handling: find, platform detection by exe path, kill, launch."""

from __future__ import annotations

import os
import subprocess
import sys
import time

import psutil

from .window import PROCESS_NAMES

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
