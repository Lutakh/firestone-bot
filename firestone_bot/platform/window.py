"""Game window provider.

Finds the Firestone window and reports its client rectangle in physical screen pixels.
Only the win32 backend exists for now; x11 and browser backends come later (plan 4.9/4.10).
"""

from __future__ import annotations

import sys
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
    client: Rect  # client area in physical screen coordinates
    maximized: bool
    fullscreen: bool


PROCESS_NAMES = ("Firestone.exe", "Firestone.x86_64", "Firestone")


class GameWindowNotFound(RuntimeError):
    pass


def _game_pids() -> set[int]:
    import psutil

    return {p.pid for p in psutil.process_iter(["name"]) if p.info["name"] in PROCESS_NAMES}


def _exe_of_pid(pid: int) -> str:
    import psutil

    try:
        return psutil.Process(pid).exe()
    except (psutil.Error, OSError):
        return ""


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32

    _WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    _GW_OWNER = 4
    _SW_RESTORE = 9

    class _POINT(ctypes.Structure):
        _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

    def _title(hwnd: int) -> str:
        n = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        return buf.value

    def _info(hwnd: int) -> WindowInfo:
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        wr = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(wr))
        cr = wintypes.RECT()
        user32.GetClientRect(hwnd, ctypes.byref(cr))
        origin = _POINT(0, 0)
        user32.ClientToScreen(hwnd, ctypes.byref(origin))
        outer = Rect(wr.left, wr.top, wr.right - wr.left, wr.bottom - wr.top)
        client = Rect(origin.x, origin.y, cr.right - cr.left, cr.bottom - cr.top)
        maximized = bool(user32.IsZoomed(hwnd))
        sw, sh = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        fullscreen = outer == client and client.w == sw and client.h == sh
        return WindowInfo(
            hwnd,
            _title(hwnd),
            pid.value,
            _exe_of_pid(pid.value),
            outer,
            client,
            maximized,
            fullscreen,
        )

    def find_game_window() -> WindowInfo:
        """Return the visible top-level window owned by the Firestone process."""
        pids = _game_pids()
        if not pids:
            raise GameWindowNotFound("Firestone process not running")
        found: list[int] = []

        @_WNDENUMPROC
        def cb(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value in pids and user32.GetWindow(hwnd, _GW_OWNER) == 0:
                found.append(hwnd)
            return True

        user32.EnumWindows(cb, 0)
        # Prefer the largest client area (Unity may own small helper windows).
        best: WindowInfo | None = None
        for h in found:
            i = _info(h)
            area = i.client.w * i.client.h
            if area > 0 and (best is None or area > best.client.w * best.client.h):
                best = i
        if best is None:
            raise GameWindowNotFound("Firestone process found but no visible window")
        return best

    def activate(win: WindowInfo) -> None:
        """Bring the game window to the foreground (replaces WinActivate / ControlFocus)."""
        if user32.IsIconic(win.handle):
            user32.ShowWindow(win.handle, _SW_RESTORE)
        user32.SetForegroundWindow(win.handle)

    def screen_size() -> tuple[int, int]:
        return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)

else:  # pragma: no cover

    def find_game_window() -> WindowInfo:
        raise GameWindowNotFound("only the win32 backend is implemented for now")

    def activate(win: WindowInfo) -> None:
        raise NotImplementedError

    def screen_size() -> tuple[int, int]:
        raise NotImplementedError
