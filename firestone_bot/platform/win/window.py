"""Win32 window backend: find the game window, client rect, activate, resize (ctypes)."""

from __future__ import annotations

import ctypes
from ctypes import wintypes

from ..types import GameWindowNotFound, Rect, WindowInfo, exe_of_pid, game_pids

user32 = ctypes.windll.user32

_WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
_GW_OWNER = 4
_SW_RESTORE = 9
_SW_MAXIMIZE = 3


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
        exe_of_pid(pid.value),
        outer,
        client,
        maximized,
        fullscreen,
    )


def find_game_window() -> WindowInfo:
    """Return the visible top-level window owned by the Firestone process."""
    pids = game_pids()
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
    # Prefer the largest client area (Unity may own small helper windows). A minimised
    # window reports an empty client rect; keep it as a fallback so activate() can restore
    # it (callers re-read the rect afterwards).
    best: WindowInfo | None = None
    iconic: WindowInfo | None = None
    for h in found:
        i = _info(h)
        area = i.client.w * i.client.h
        if area > 0 and (best is None or area > best.client.w * best.client.h):
            best = i
        elif user32.IsIconic(h) and iconic is None:
            iconic = i
    if best is None:
        best = iconic
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


def pixels_per_point() -> float:
    """Physical pixels per input-coordinate unit (1: pynput uses pixels on Windows)."""
    return 1.0


def cursor_position() -> tuple[int, int]:
    pt = _POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def window_dpi(win: WindowInfo) -> int | None:
    if hasattr(user32, "GetDpiForWindow"):
        return user32.GetDpiForWindow(win.handle)
    return None


def maximize(win: WindowInfo) -> None:
    import time

    user32.ShowWindow(win.handle, _SW_RESTORE)
    time.sleep(0.3)
    user32.ShowWindow(win.handle, _SW_MAXIMIZE)


def set_client_size(win: WindowInfo, w: int, h: int, x: int = 0, y: int = 0) -> None:
    """Restore the window and resize it so the client area is w x h, outer top-left at x,y."""
    import time

    user32.ShowWindow(win.handle, _SW_RESTORE)
    time.sleep(0.5)
    win = find_game_window()
    fw = win.outer.w - win.client.w
    fh = win.outer.h - win.client.h
    user32.SetWindowPos(win.handle, 0, x, y, w + fw, h + fh, 0x0004 | 0x0040)  # NOZORDER|SHOW
