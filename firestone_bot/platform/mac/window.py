"""macOS window backend (Quartz window list + AppKit + Accessibility via pyobjc).

Unit convention (see platform/types.py): the bot works in PHYSICAL pixels. macOS APIs use
points, so this module multiplies Quartz bounds by the backing scale factor of the screen that
holds the game window (2.0 on Retina) and remembers that factor for capture (mss asks in
points, returns pixels) and input (pynput moves in points). Mixed-scale multi-monitor setups
are not handled: one factor, the game's screen, applies to every coordinate.

The client area is the window bounds minus the title bar, except in fullscreen (a window that
covers the whole screen, or the fullscreen Space: no title bar). The title bar height comes
from AppKit for a standard titled window. Minimised windows report an empty client rect like
the Windows backend; activate() restores them (Accessibility) and brings the app forward.

Letterbox: the macOS build keeps the canvas at 16:9 and pads the rest of the window with
black bars (measured 2026-09-05: fullscreen Space 1512x949 pt -> 98 px bars top and bottom at
2x). The Windows build has no bars (docs/MEASUREMENTS.md 4.2). The bars are measured on a
capture of the game window itself (CGWindowListCreateImage, so other windows in front do
not matter) and removed from the client rect, so the atlas maps onto the canvas; the result
is cached per window geometry (letterbox()).

All pyobjc imports are lazy: importing this module must work headless (tests, CI).
"""

from __future__ import annotations

import logging
import subprocess
import time

from ..types import GameWindowNotFound, Rect, WindowInfo, exe_of_pid, game_pids

log = logging.getLogger(__name__)

_factor: float | None = None  # pixels per point, set by find_game_window / main screen
_BUNDLE_ID = "com.HolydayStudios.Firestone"


# -- scale factor ---------------------------------------------------------------------------
def _screens():
    import AppKit

    return list(AppKit.NSScreen.screens())


def _screen_height_pt() -> float:
    import AppKit

    return float(AppKit.NSScreen.screens()[0].frame().size.height)


def _factor_for_bounds(x: float, y: float, w: float, h: float) -> float:
    """Backing scale of the screen holding the centre of a top-left-origin points rect."""
    import AppKit

    screens = _screens()
    if not screens:
        return 1.0
    h0 = float(screens[0].frame().size.height)  # primary screen, origin bottom-left
    cx, cy = x + w / 2, y + h / 2
    for s in screens:
        f = s.frame()
        top = h0 - (f.origin.y + f.size.height)  # flip to top-left origin
        if f.origin.x <= cx < f.origin.x + f.size.width and top <= cy < top + f.size.height:
            return float(s.backingScaleFactor())
    return float(AppKit.NSScreen.mainScreen().backingScaleFactor())


def pixels_per_point() -> float:
    """Physical pixels per point for the game's screen (2.0 on Retina)."""
    global _factor
    if _factor is None:
        import AppKit

        _factor = float(AppKit.NSScreen.mainScreen().backingScaleFactor())
    return _factor


def title_bar_height_pt() -> float:
    """Height of a standard titled window's title bar in points on this macOS."""
    import AppKit

    mask = (
        AppKit.NSWindowStyleMaskTitled
        | AppKit.NSWindowStyleMaskClosable
        | AppKit.NSWindowStyleMaskResizable
    )
    frame = AppKit.NSMakeRect(0, 0, 1000, 1000)
    content = AppKit.NSWindow.contentRectForFrameRect_styleMask_(frame, mask)
    return 1000.0 - float(content.size.height)


# -- pure geometry (unit-tested) ------------------------------------------------------------
def to_pixels(x: float, y: float, w: float, h: float, factor: float) -> Rect:
    return Rect(round(x * factor), round(y * factor), round(w * factor), round(h * factor))


def client_rect(outer: Rect, title_px: int, fullscreen: bool) -> Rect:
    """Client area from the outer rect: the title bar is removed unless fullscreen."""
    if fullscreen or title_px <= 0:
        return outer
    return Rect(outer.x, outer.y + title_px, outer.w, max(0, outer.h - title_px))


def is_fullscreen(x: float, y: float, w: float, h: float, screen_w: float, screen_h: float) -> bool:
    """Bounds covering the whole screen, or the whole screen minus the menu bar (fullscreen
    Space with the menu bar shown): Unity draws no title bar in both cases."""
    return w >= screen_w and x <= 0 and (y <= 0 and h >= screen_h or h >= screen_h * 0.9)


# -- letterbox ----------------------------------------------------------------------------
BLACK_MAX = 12  # a bar pixel: every channel below this
NO_BARS_TTL = 10.0  # s; "no bars" may mean another window covered the game: re-measure soon
_letterbox_cache: dict[Rect, tuple[tuple[int, int, int, int], float]] = {}


def bar_sizes(strips: list, axis_len: int, limit: float = 0.4) -> tuple[int, int]:
    """Leading and trailing bar sizes along an axis from black masks of several strips.

    `strips` are boolean 1-D arrays (True = black along that strip at that index), one per
    strip; an index is a bar only when EVERY strip is black there. Bars longer than `limit`
    of the axis (a loading screen, a dark scene) are not bars: (0, 0).
    """
    import numpy as np

    if not strips:
        return 0, 0
    black = np.logical_and.reduce(strips)
    lead = 0
    while lead < axis_len and black[lead]:
        lead += 1
    trail = 0
    while trail < axis_len - lead and black[axis_len - 1 - trail]:
        trail += 1
    if lead + trail > limit * axis_len:
        return 0, 0
    return lead, trail


def measure_letterbox(window_id: int, outer: Rect, client: Rect) -> tuple[int, int, int, int]:
    """(top, bottom, left, right) black bars inside `client`, measured on the window's own
    image (so a window in front of the game does not matter)."""
    from .capture import grab_window

    img = grab_window(window_id)
    if img is None:
        raise RuntimeError("window capture failed")
    if img.shape[0] != outer.h or img.shape[1] != outer.w:  # unexpected scale
        raise RuntimeError(f"window image {img.shape[1]}x{img.shape[0]} for outer {outer}")
    y0, x0 = client.y - outer.y, client.x - outer.x
    img = img[y0 : y0 + client.h, x0 : x0 + client.w]
    dark = img[:, :, :3].max(axis=2) < BLACK_MAX
    # a row / column is a bar when at least 99.5 % of it is black (HUD bells may overhang)
    rows = [dark.mean(axis=1) > 0.995]
    cols = [dark.mean(axis=0) > 0.995]
    top, bottom = bar_sizes(rows, client.h)
    left, right = bar_sizes(cols, client.w)
    return top, bottom, left, right


def letterbox(window_id: int, outer: Rect, client: Rect) -> Rect:
    """Client rect without the black bars Unity adds to keep its aspect.

    Bars found are cached for the window geometry; a measurement without bars is only trusted
    for NO_BARS_TTL seconds (the game may have been covered by another window)."""
    cached = _letterbox_cache.get(client)
    now = time.monotonic()
    if cached is not None and (any(cached[0]) or now < cached[1]):
        bars = cached[0]
    else:
        try:
            bars = measure_letterbox(window_id, outer, client)
        except Exception:  # capture failed (permission): keep the geometric rect
            log.debug("letterbox measure failed", exc_info=True)
            return client
        # Only a real letterbox leaves a 16:9 canvas; anything else is scene content.
        w = client.w - bars[2] - bars[3]
        h = client.h - bars[0] - bars[1]
        if h <= 0 or abs(w / h - 16 / 9) > 0.03:
            bars = (0, 0, 0, 0)
        _letterbox_cache[client] = (bars, now + NO_BARS_TTL)
        if any(bars):
            log.info("letterbox bars top/bottom/left/right %s inside client %s", bars, client)
    top, bottom, left, right = bars
    return Rect(client.x + left, client.y + top, client.w - left - right, client.h - top - bottom)


# -- window list ------------------------------------------------------------------------
def _quartz_windows(pids: set[int]) -> list[dict]:
    import Quartz

    opts = Quartz.kCGWindowListOptionAll | Quartz.kCGWindowListExcludeDesktopElements
    out = []
    for w in Quartz.CGWindowListCopyWindowInfo(opts, Quartz.kCGNullWindowID) or []:
        if w.get("kCGWindowOwnerPID") not in pids or w.get("kCGWindowLayer", 0) != 0:
            continue
        if float(w.get("kCGWindowAlpha", 1.0)) <= 0:
            continue
        b = w.get("kCGWindowBounds") or {}
        out.append(
            {
                "id": int(w.get("kCGWindowNumber", 0)),
                "pid": int(w.get("kCGWindowOwnerPID")),
                "title": str(w.get("kCGWindowName") or w.get("kCGWindowOwnerName") or ""),
                "x": float(b.get("X", 0)),
                "y": float(b.get("Y", 0)),
                "w": float(b.get("Width", 0)),
                "h": float(b.get("Height", 0)),
                "onscreen": bool(w.get("kCGWindowIsOnscreen", False)),
            }
        )
    return out


def _running_app(pid: int):
    import AppKit

    return AppKit.NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)


def _ax_window(pid: int, size: tuple[float, float] | None = None):
    """The app's AX window (matching `size` in points when several), or None."""
    try:
        import ApplicationServices as AS
    except ImportError:
        return None
    app = AS.AXUIElementCreateApplication(pid)
    err, wins = AS.AXUIElementCopyAttributeValue(app, AS.kAXWindowsAttribute, None)
    if err != 0 or not wins:
        return None
    if size is not None and len(wins) > 1:
        for w in wins:
            e, v = AS.AXUIElementCopyAttributeValue(w, AS.kAXSizeAttribute, None)
            if e == 0 and v is not None:
                ok, sz = AS.AXValueGetValue(v, AS.kAXValueCGSizeType, None)
                if ok and abs(sz.width - size[0]) < 2 and abs(sz.height - size[1]) < 2:
                    return w
    return wins[0]


def _ax_bool(element, attr: str) -> bool | None:
    import ApplicationServices as AS

    if element is None:
        return None
    err, v = AS.AXUIElementCopyAttributeValue(element, attr, None)
    return bool(v) if err == 0 and v is not None else None


def find_game_window() -> WindowInfo:
    """Return the largest window owned by the Firestone process, in physical pixels."""
    global _factor
    pids = game_pids()
    if not pids:
        raise GameWindowNotFound("Firestone process not running")
    wins = _quartz_windows(pids)
    if not wins:
        raise GameWindowNotFound("Firestone process found but no window")
    # largest area; among equals prefer the one on screen
    best = max(wins, key=lambda w: (w["w"] * w["h"], w["onscreen"]))
    _factor = _factor_for_bounds(best["x"], best["y"], best["w"], best["h"])
    f = _factor
    outer = to_pixels(best["x"], best["y"], best["w"], best["h"], f)
    screen_w = float(_screens()[0].frame().size.width) if _screens() else best["w"]
    ax = _ax_window(best["pid"], (best["w"], best["h"]))
    fullscreen = bool(_ax_bool(ax, "AXFullScreen")) or is_fullscreen(
        best["x"], best["y"], best["w"], best["h"], screen_w, _screen_height_pt()
    )
    minimised = bool(_ax_bool(ax, "AXMinimized"))
    app = _running_app(best["pid"])
    hidden = bool(app.isHidden()) if app is not None else False
    if minimised or hidden:
        client = Rect(outer.x, outer.y, 0, 0)
    else:
        client = client_rect(outer, round(title_bar_height_pt() * f), fullscreen)
        client = letterbox(best["id"], outer, client)
    return WindowInfo(
        best["id"],
        best["title"],
        best["pid"],
        exe_of_pid(best["pid"]),
        outer,
        client,
        fullscreen,  # a zoomed window is reported as maximized only when it fills the screen
        fullscreen,
    )


# -- activation ---------------------------------------------------------------------------
def activate(win: WindowInfo) -> None:
    """Unhide / un-minimise the game and bring it to the front (switches Space if needed).

    Since macOS 14 a background process cannot always activate another app through
    NSRunningApplication, so the Accessibility API (kAXFrontmost) and `open -b` are tried
    next; the first that makes the app active wins. When the app was not active before (a
    Space switch to a fullscreen game animates for about a second) the call also waits for
    the window to be on screen plus a settle delay, so the next capture shows the game.
    """

    app = _running_app(win.pid)
    if app is None:
        return
    was_active = bool(app.isActive()) and _window_onscreen(win.handle)
    _bring_front(app, win)
    if not was_active:
        end = time.monotonic() + 3.0
        while time.monotonic() < end and not _window_onscreen(win.handle):
            time.sleep(0.05)
        time.sleep(SPACE_SWITCH_SETTLE)


SPACE_SWITCH_SETTLE = 0.7  # s after the window is on screen (Space transition animation)


def _window_onscreen(window_id: int) -> bool:
    import Quartz

    wl = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID
    )
    return any(int(w.get("kCGWindowNumber", -1)) == window_id for w in wl or [])


def _bring_front(app, win: WindowInfo) -> None:
    import AppKit

    if app.isHidden():
        app.unhide()
    ax_win = _ax_window(
        win.pid, (win.outer.w / pixels_per_point(), win.outer.h / pixels_per_point())
    )
    if _ax_bool(ax_win, "AXMinimized"):
        import ApplicationServices as AS

        AS.AXUIElementSetAttributeValue(ax_win, AS.kAXMinimizedAttribute, False)
        time.sleep(0.3)
    app.activateWithOptions_(AppKit.NSApplicationActivateIgnoringOtherApps)
    if _wait_active(app, 0.6):
        return
    try:
        import ApplicationServices as AS

        AS.AXUIElementSetAttributeValue(
            AS.AXUIElementCreateApplication(win.pid), AS.kAXFrontmostAttribute, True
        )
    except Exception:  # Accessibility not granted
        log.debug("AX frontmost failed", exc_info=True)
    if _wait_active(app, 0.8):
        return
    bundle = app.bundleIdentifier() or _BUNDLE_ID
    subprocess.run(["open", "-b", bundle], check=False)
    _wait_active(app, 2.0)


def _wait_active(app, timeout: float) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if app.isActive():
            return True
        time.sleep(0.05)
    return bool(app.isActive())


# -- misc ---------------------------------------------------------------------------------
def screen_size() -> tuple[int, int]:
    """Primary screen size in physical pixels."""
    import Quartz

    d = Quartz.CGMainDisplayID()
    return int(Quartz.CGDisplayPixelsWide(d)), int(Quartz.CGDisplayPixelsHigh(d))


def cursor_position() -> tuple[int, int]:
    import Quartz

    ev = Quartz.CGEventCreate(None)
    p = Quartz.CGEventGetLocation(ev)
    f = pixels_per_point()
    return round(p.x * f), round(p.y * f)


def maximize(win: WindowInfo) -> None:
    """Zoom the window to the visible screen area (not the fullscreen Space)."""
    import AppKit

    vf = AppKit.NSScreen.mainScreen().visibleFrame()
    h0 = _screen_height_pt()
    top = h0 - (vf.origin.y + vf.size.height)
    _ax_set_frame(win, vf.origin.x, top, vf.size.width, vf.size.height)


def set_client_size(win: WindowInfo, w: int, h: int, x: int = 0, y: int = 0) -> None:
    """Resize so the client area is w x h physical pixels, outer top-left at x,y (pixels)."""
    f = pixels_per_point()
    title = 0 if win.fullscreen else title_bar_height_pt()
    _ax_set_frame(win, x / f, y / f, w / f, h / f + title)


def _ax_set_frame(win: WindowInfo, x: float, y: float, w: float, h: float) -> None:
    import ApplicationServices as AS
    import Quartz

    ax = _ax_window(win.pid)
    if ax is None:
        raise RuntimeError("Accessibility window not available (permission missing?)")
    pos = AS.AXValueCreate(AS.kAXValueCGPointType, Quartz.CGPoint(x, y))
    size = AS.AXValueCreate(AS.kAXValueCGSizeType, Quartz.CGSize(w, h))
    AS.AXUIElementSetAttributeValue(ax, AS.kAXPositionAttribute, pos)
    AS.AXUIElementSetAttributeValue(ax, AS.kAXSizeAttribute, size)
    AS.AXUIElementSetAttributeValue(ax, AS.kAXPositionAttribute, pos)
