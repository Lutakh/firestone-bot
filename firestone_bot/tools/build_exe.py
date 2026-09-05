"""Build the one-dir exe without touching the user files next to it.

    python -m firestone_bot.tools.build_exe

PyInstaller wipes its output folder before every build, so building straight into
dist/FirestoneBot would delete settings.ini, MapStartState.ini, gui_state.json and the log
that the running bot keeps there. This script builds into build/stage and then replaces ONLY
FirestoneBot.exe and _internal in dist/FirestoneBot.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STAGE = os.path.join(ROOT, "build", "stage")
DIST = os.path.join(ROOT, "dist", "FirestoneBot")
KEEP = ("settings.ini", "MapStartState.ini", "gui_state.json", "firestone-bot.log")


def bot_running() -> bool:
    """True when a process runs dist/FirestoneBot/FirestoneBot.exe (rename checks are not
    enough: Windows lets a running exe be renamed, and rmtree on _internal then fails half-way
    through on a locked .pyd, leaving a broken install)."""
    import psutil

    target = os.path.normcase(os.path.join(DIST, "FirestoneBot.exe"))
    for proc in psutil.process_iter(["exe"]):
        try:
            exe = proc.info["exe"]
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        if exe and os.path.normcase(exe) == target:
            return True
    return False


def _swap(name: str, src: str) -> None:
    """Replace DIST/name by src/name: the old item is renamed aside first (fails cleanly when
    it is in use, nothing is deleted), then the new one is moved in, then the old one is
    removed if possible (a leftover *.old is cleaned on the next build)."""
    dst = os.path.join(DIST, name)
    old = dst + ".old"
    if os.path.exists(old):
        (shutil.rmtree if os.path.isdir(old) else os.remove)(old)
    if os.path.exists(dst):
        os.rename(dst, old)
    shutil.move(os.path.join(src, name), dst)
    if os.path.exists(old):
        try:
            (shutil.rmtree if os.path.isdir(old) else os.remove)(old)
        except OSError:
            print(f"{old} is still in use, it will be removed by the next build")


def main() -> int:
    if bot_running():
        print("dist/FirestoneBot/FirestoneBot.exe is running: close the bot window first")
        return 1
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--log-level",
        "ERROR",
        "--distpath",
        STAGE,
        "--workpath",
        os.path.join(ROOT, "build", "work"),
        os.path.join(ROOT, "firestone-bot.spec"),
    ]
    r = subprocess.run(cmd, cwd=ROOT, check=False)
    if r.returncode != 0:
        return r.returncode
    src = os.path.join(STAGE, "FirestoneBot")
    os.makedirs(DIST, exist_ok=True)
    _swap("_internal", src)
    _swap("FirestoneBot.exe", src)
    kept = [k for k in KEEP if os.path.exists(os.path.join(DIST, k))]
    print(f"exe updated in {DIST}; kept: {', '.join(kept) or 'nothing (first build)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
