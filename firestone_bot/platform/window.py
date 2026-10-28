"""Game window provider: public API, backend selected on sys.platform at import time.

Finds the Firestone window and reports its client rectangle in physical screen pixels
(platform/types.py). Backends: win32 (platform/win/window.py), macOS (platform/mac/window.py).
Other platforms get stubs that raise (x11 and browser backends come later, plan 4.9/4.10).

`is_foreground` / `foreground_owner` / `is_hung` serve the foreground guard (foreground.py),
which runs on Windows only: elsewhere they answer "in front", "nothing known" and "not hung".
"""

from __future__ import annotations

import sys

from .types import PROCESS_NAMES, GameWindowNotFound, Rect, WindowInfo

__all__ = [
    "PROCESS_NAMES",
    "GameWindowNotFound",
    "Rect",
    "WindowInfo",
    "activate",
    "cursor_position",
    "find_game_window",
    "foreground_owner",
    "is_foreground",
    "is_hung",
    "maximize",
    "pixels_per_point",
    "screen_size",
    "set_client_size",
]

if sys.platform == "win32":
    from .win.window import (
        activate,
        cursor_position,
        find_game_window,
        foreground_owner,
        is_foreground,
        is_hung,
        maximize,
        pixels_per_point,
        screen_size,
        set_client_size,
    )
elif sys.platform == "darwin":
    from .mac.window import (
        activate,
        cursor_position,
        find_game_window,
        maximize,
        pixels_per_point,
        screen_size,
        set_client_size,
    )

    def is_foreground(win: WindowInfo) -> bool:
        return True  # not checked on macOS (no foreground guard there)

    def foreground_owner() -> tuple[str, str, int]:
        return "", "", 0

    def is_hung(win: WindowInfo) -> bool:
        return False
else:  # pragma: no cover

    def find_game_window() -> WindowInfo:
        raise GameWindowNotFound(f"no window backend for {sys.platform} (win32 and macOS only)")

    def activate(win: WindowInfo) -> None:
        raise NotImplementedError

    def is_foreground(win: WindowInfo) -> bool:
        return True

    def foreground_owner() -> tuple[str, str, int]:
        return "", "", 0

    def is_hung(win: WindowInfo) -> bool:
        return False

    def screen_size() -> tuple[int, int]:
        raise NotImplementedError

    def pixels_per_point() -> float:
        return 1.0

    def cursor_position() -> tuple[int, int]:
        raise NotImplementedError

    def maximize(win: WindowInfo) -> None:
        raise NotImplementedError

    def set_client_size(win: WindowInfo, w: int, h: int, x: int = 0, y: int = 0) -> None:
        raise NotImplementedError
