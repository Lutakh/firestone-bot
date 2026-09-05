"""Types shared by the window backends (win / mac) and the rest of the package.

Every rectangle is in PHYSICAL screen pixels, origin at the top-left of the primary display.
On Windows that is the native unit once the process is DPI aware. On macOS the backends
convert: Quartz reports points, the bot multiplies by the backing scale factor of the screen
that holds the game window (2 on Retina), so captures (mss returns physical pixels) and atlas
maths see one unit; input converts back to points (see platform/mac/README in window.py).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    w: int
    h: int

    @property
    def right(self) -> int:
        return self.x + self.w

    @property
    def bottom(self) -> int:
        return self.y + self.h


@dataclass(frozen=True)
class WindowInfo:
    handle: int
    title: str
    pid: int
    exe: str
    outer: Rect  # window rect including the frame
    client: Rect  # client area in physical screen coordinates (w == 0 when minimised)
    maximized: bool
    fullscreen: bool


PROCESS_NAMES = ("Firestone.exe", "Firestone.x86_64", "Firestone")


class GameWindowNotFound(RuntimeError):
    pass


def game_pids() -> set[int]:
    import psutil

    return {p.pid for p in psutil.process_iter(["name"]) if p.info["name"] in PROCESS_NAMES}


def exe_of_pid(pid: int) -> str:
    import psutil

    try:
        return psutil.Process(pid).exe()
    except (psutil.Error, OSError):
        return ""
