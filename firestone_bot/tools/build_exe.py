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


def main() -> int:
    if os.path.exists(os.path.join(DIST, "FirestoneBot.exe")):
        try:
            os.rename(
                os.path.join(DIST, "FirestoneBot.exe"), os.path.join(DIST, "FirestoneBot.exe")
            )
        except OSError:
            print("dist/FirestoneBot/FirestoneBot.exe is in use: close the bot window first")
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
    for name in ("_internal",):
        dst = os.path.join(DIST, name)
        if os.path.isdir(dst):
            shutil.rmtree(dst)
        shutil.move(os.path.join(src, name), dst)
    shutil.move(os.path.join(src, "FirestoneBot.exe"), os.path.join(DIST, "FirestoneBot.exe"))
    kept = [k for k in KEEP if os.path.exists(os.path.join(DIST, k))]
    print(f"exe updated in {DIST}; kept: {', '.join(kept) or 'nothing (first build)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
