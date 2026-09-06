"""Activity overlay drawn over the game window (owner request 2026-09-06).

The AHK bot showed timed MsgBoxes over the game ("Claiming Scarab's Token"...), which cost
seconds each. The rework shows the same activity lines in a small translucent panel that
sits over the game window, is ignored by the mouse (clicks go through to the game) and is
left out of the bot's own screen captures, so probes never see it:

  Windows  WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_NOACTIVATE (click-through, no focus) and
           SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE): the window does not appear in
           BitBlt / mss captures (Windows 10 2004+; older Windows keeps it visible, so the
           panel is placed over the top edge of the client where no probe looks).
  macOS    NSWindow.setIgnoresMouseEvents_(True), floating level, and
           setSharingType_(NSWindowSharingNone): CGWindowListCreateImage skips the window.
  Linux    -alpha needs a compositor; there is no capture exclusion, so the panel is only
           shown when Overlay is on AND the user accepts that probes may see it: the panel
           is placed at the very top of the client (title strip) to stay clear of them.

Everything runs on the Tk main thread; the runner posts lines through MainWindow.post_call.
"""

from __future__ import annotations

import logging
import sys
import tkinter as tk
from collections import deque

from firestone_bot.platform.window import Rect

log = logging.getLogger("firestone_bot.overlay")

LINES = 4
WIDTH_PT = 520
ALPHA = 0.82
BG = "#101418"
FG = "#e8edf2"
FG_DIM = "#9aa4ad"
FONT = ("Helvetica", 13) if sys.platform == "darwin" else ("Segoe UI", 10)
MARGIN = 12
OVERLAY_TITLE = "firestone-bot-overlay"


class GameOverlay:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.top: tk.Toplevel | None = None
        self.lines: deque[str] = deque(maxlen=LINES)
        self.labels: list[tk.Label] = []
        self.capture_safe = False  # True when the OS leaves the window out of captures
        self.visible = False
        self._rect: Rect | None = None

    # -- lifecycle --------------------------------------------------------------------------
    def _build(self) -> None:
        top = tk.Toplevel(self.root)
        top.withdraw()
        top.title(OVERLAY_TITLE)  # how the macOS NSWindow is found back
        top.overrideredirect(True)
        top.configure(bg=BG)
        try:
            top.attributes("-topmost", True)
        except tk.TclError:
            pass
        try:
            top.attributes("-alpha", ALPHA)
        except tk.TclError:
            pass
        frame = tk.Frame(top, bg=BG, padx=10, pady=6)
        frame.pack(fill="both", expand=True)
        for i in range(LINES):
            lab = tk.Label(
                frame,
                text="",
                anchor="w",
                justify="left",
                bg=BG,
                fg=FG if i == LINES - 1 else FG_DIM,
                font=FONT,
                wraplength=WIDTH_PT - 24,
            )
            lab.pack(fill="x")
            self.labels.append(lab)
        self.top = top
        top.geometry(f"{WIDTH_PT}x{LINES * 22 + 12}+0+0")
        top.deiconify()  # the native window exists (and is listed) once mapped
        top.update()
        self.capture_safe = _platform_setup(top)
        top.withdraw()
        log.info("overlay ready (capture-safe: %s)", self.capture_safe)

    def show(self) -> None:
        if self.top is None:
            self._build()
        assert self.top is not None
        self.visible = True
        self._render()
        self._place()
        self.top.deiconify()
        try:
            self.top.lift()
        except tk.TclError:
            pass

    def hide(self) -> None:
        self.visible = False
        if self.top is not None:
            self.top.withdraw()

    def destroy(self) -> None:
        if self.top is not None:
            self.top.destroy()
            self.top = None
            self.labels = []

    # -- content ----------------------------------------------------------------------------
    def push(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        self.lines.append(text)
        if self.visible and self.top is not None:
            self._render()

    def _render(self) -> None:
        lines = list(self.lines)
        pad = [""] * (LINES - len(lines)) + lines
        for lab, line in zip(self.labels, pad, strict=True):
            if lab.cget("text") != line:
                lab.configure(text=line)

    # -- placement ------------------------------------------------------------------------
    def set_game_rect(self, rect: Rect | None) -> None:
        """Client rect of the game in physical pixels (None: game not found)."""
        self._rect = rect
        if self.visible and self.top is not None:
            self._place()

    def _place(self) -> None:
        assert self.top is not None
        r = self._rect
        if r is None:
            return
        from firestone_bot.platform.window import pixels_per_point

        f = pixels_per_point() if sys.platform == "darwin" else 1.0
        left, top, w, h = r.x / f, r.y / f, r.w / f, r.h / f
        self.top.update_idletasks()
        need_h = self.top.winfo_reqheight()
        x = int(left + MARGIN)
        if self.capture_safe:
            y = int(top + h - need_h - MARGIN)  # bottom-left, over the hero bar
        else:
            y = int(top + 2)  # top strip: no probe looks there
        width = int(min(WIDTH_PT, max(200, w - 2 * MARGIN)))
        self.top.geometry(f"{width}x{need_h}+{x}+{y}")


# -- per-OS window flags ----------------------------------------------------------------------
def _platform_setup(top: tk.Toplevel) -> bool:
    """Make the window click-through and, when the OS allows it, invisible to captures.
    Returns True when captures will not show it."""
    try:
        if sys.platform == "win32":
            return _setup_windows(top)
        if sys.platform == "darwin":
            return _setup_macos(top)
        return _setup_linux(top)
    except Exception:
        log.exception("overlay platform setup failed")
        return False


def _setup_windows(top: tk.Toplevel) -> bool:
    import ctypes

    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    hwnd = user32.GetParent(top.winfo_id()) or top.winfo_id()
    GWL_EXSTYLE = -20
    WS_EX_TRANSPARENT, WS_EX_LAYERED = 0x20, 0x80000
    WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW = 0x08000000, 0x80
    ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongW(
        hwnd,
        GWL_EXSTYLE,
        ex | WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW,
    )
    WDA_EXCLUDEFROMCAPTURE = 0x11
    return bool(user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE))


def _setup_macos(top: tk.Toplevel) -> bool:
    import AppKit

    # winfo_id is not an NSView pointer with Tk 9 (dereferencing it crashed the process):
    # find the NSWindow by the unique title given to the Toplevel instead.
    win = None
    for w in AppKit.NSApplication.sharedApplication().windows():
        if str(w.title()) == OVERLAY_TITLE:
            win = w
            break
    if win is None:
        log.info("overlay: NSWindow not found, no click-through / capture exclusion")
        return False
    win.setIgnoresMouseEvents_(True)
    win.setLevel_(AppKit.NSFloatingWindowLevel)
    win.setCollectionBehavior_(
        AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces
        | AppKit.NSWindowCollectionBehaviorFullScreenAuxiliary
        | AppKit.NSWindowCollectionBehaviorStationary
    )
    win.setSharingType_(AppKit.NSWindowSharingNone)  # left out of CGWindowListCreateImage
    return True


def _setup_linux(top: tk.Toplevel) -> bool:
    try:
        from Xlib import display
        from Xlib.ext import shape

        d = display.Display()
        w = d.create_resource_object("window", top.winfo_id())
        # empty input shape: the pointer falls through to whatever is below
        w.shape_rectangles(shape.SO.Set, shape.SK.Input, 0, 0, 0, [])
        d.sync()
    except Exception:
        log.debug("X11 input shape not applied", exc_info=True)
    return False
