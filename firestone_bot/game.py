"""Runtime context handed to every feature module.

Wraps window, viewport, capture, input and settings behind the vocabulary of the AHK code so
that ported functions read like the originals:

    g.focus()                       ControlFocus / WinActivate
    g.move(x, y); g.sleep(1000)     MouseMove x, y  /  Sleep, 1000
    g.click()                       Click
    g.click_at(x, y)                Click x, y
    g.tap(p, 1500)                  MouseMove; Sleep 1000; Click; Sleep 1500  (see tap())
    g.search(probe) -> hit | None   PixelSearch ... ErrorLevel = 0
    g.toast(title, text, seconds)   MsgBox , , title, text, seconds   (non-blocking + same delay)
    g.key("m")                      Send, M
    g.wheel(-5)                     5 x Send {WheelDown} (200 ms apart)

Coordinates given to Game are LOGICAL (atlas / AHK) unless the method name says `screen`.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from firestone_bot.platform import capture
from firestone_bot.platform import input as inp
from firestone_bot.platform.window import (
    GameWindowNotFound,
    Rect,
    WindowInfo,
    activate,
    find_game_window,
)
from firestone_bot.settings import Settings
from firestone_bot.vision.atlas import Point, Probe
from firestone_bot.vision.probes import pixel_search_in
from firestone_bot.vision.viewport import Viewport

log = logging.getLogger("firestone_bot")


class BotStopped(Exception):
    """Raised from sleep() when the stop event is set; unwinds the current cycle."""


@dataclass
class Hit:
    """A PixelSearch result: screen pixel plus its logical equivalent."""

    sx: int
    sy: int
    x: int
    y: int


class Game:
    def __init__(
        self,
        settings: Settings,
        *,
        dry_run: bool = False,
        stop_event: threading.Event | None = None,
        status_cb: Callable[[str], None] | None = None,
        time_scale: float = 1.0,
    ) -> None:
        self.settings = settings
        self.dry_run = dry_run
        self.stop_event = stop_event or threading.Event()
        self.status_cb = status_cb
        self.time_scale = time_scale  # < 1 speeds up sleeps for dry runs only
        self.window: WindowInfo | None = None
        self.vp: Viewport | None = None
        self.actions: list[str] = []  # dry-run / debug trace
        self.vars: dict[str, int] = {}  # AHK globals shared between feature functions
        self.heartbeat_cb: Callable[[str, bool, bool], None] | None = None
        self.map_state_path = "MapStartState.ini"
        self.style = "classic"  # main-screen layout, detected at each cycle start (layouts.py)
        self.progress = None  # progress.Progress, set by the runner / app
        self._digits = None
        self.timing = str(settings.get("Timing") or "fast").strip().lower()
        self.stats: dict[str, float] = {}  # per-cycle counters (waits saved, ...)

    @property
    def ms(self):
        """Main-screen layout for the detected interface style."""
        from firestone_bot.vision import layouts

        return layouts.BY_NAME.get(self.style, layouts.CLASSIC)

    # -- window -------------------------------------------------------------------------
    def refresh_window(self) -> WindowInfo:
        self.window = find_game_window()
        self.vp = Viewport(self.window.client)
        return self.window

    def focus(self) -> None:
        """ControlFocus / WinActivate on the game. Re-reads the client rect every time."""
        try:
            win = self.refresh_window()
        except GameWindowNotFound:
            log.warning("focus: game window not found")
            return
        if not self.dry_run:
            activate(win)
            if win.client.w == 0:  # was minimised: read the restored client rect
                self.sleep(500)
                self.refresh_window()

    def _viewport(self) -> Viewport:
        if self.vp is None:
            self.refresh_window()
        assert self.vp is not None
        return self.vp

    # -- timing / status ----------------------------------------------------------------
    def sleep(self, ms: float) -> None:
        end = time.monotonic() + ms / 1000 * self.time_scale
        while True:
            if self.stop_event.is_set():
                raise BotStopped
            left = end - time.monotonic()
            if left <= 0:
                return
            time.sleep(min(left, 0.1))

    def status(self, text: str) -> None:
        log.info(text)
        if self.status_cb:
            self.status_cb(text)

    def heartbeat(self, msg: str, is_stop: bool = False, important: bool = False) -> None:
        """AHK SendHeartbeat(): forwarded to the heartbeat hook when one is installed."""
        self._trace(f"heartbeat {msg!r} stop={is_stop} important={important}")
        if self.heartbeat_cb:
            self.heartbeat_cb(msg, is_stop, important)

    TOAST_FAST_S = 0.3

    def toast(self, title: str, text: str, seconds: float) -> None:
        """AHK timed MsgBox: shown as a status line, then the same delay (fast timing: the
        line only, the MsgBox delay was never needed by the game)."""
        self.status(f"{title}: {text}")
        if self.fast() and seconds > self.TOAST_FAST_S:
            self.stats["wait_saved_ms"] = (
                self.stats.get("wait_saved_ms", 0.0) + (seconds - self.TOAST_FAST_S) * 1000
            )
            seconds = self.TOAST_FAST_S
        self.sleep(seconds * 1000)

    def _trace(self, s: str) -> None:
        self.actions.append(s)
        log.debug(s)

    # -- input (logical coordinates) ------------------------------------------------------
    def move(self, x: int, y: int, anchor=None) -> None:
        sx, sy = self._viewport().to_screen(x, y, anchor)
        self._trace(f"move ({x},{y}) -> screen ({sx},{sy})")
        if not self.dry_run:
            inp.move(sx, sy)

    def move_to(self, p: Point) -> None:
        self.move(p.x, p.y, p.anchor)

    def click(self) -> None:
        self._trace("click")
        if not self.dry_run:
            inp.click()

    def click_at(self, x: int, y: int, anchor=None) -> None:
        """AHK `Click x, y` (moves then clicks, no sleep in between)."""
        self.move(x, y, anchor)
        self.click()

    def click_point(self, p: Point) -> None:
        self.click_at(p.x, p.y, p.anchor)

    def move_screen(self, sx: int, sy: int) -> None:
        """MouseMove to a screen pixel (used for PixelSearch hits)."""
        self._trace(f"move screen ({sx},{sy})")
        if not self.dry_run:
            inp.move(sx, sy)

    def click_screen(self, sx: int, sy: int) -> None:
        self._trace(f"click screen ({sx},{sy})")
        if not self.dry_run:
            inp.move(sx, sy)
            inp.click()

    def drag(self, x1: int, y1: int, x2: int, y2: int, anchor=None) -> None:
        """Left-button drag between two logical points (same anchor for both)."""
        vp = self._viewport()
        sx1, sy1 = vp.to_screen(x1, y1, anchor)
        sx2, sy2 = vp.to_screen(x2, y2, anchor)
        self._trace(f"drag ({x1},{y1}) -> ({x2},{y2}) screen ({sx1},{sy1}) -> ({sx2},{sy2})")
        if not self.dry_run:
            inp.drag(sx1, sy1, sx2, sy2)

    def key(self, name: str) -> None:
        self._trace(f"key {name}")
        if not self.dry_run:
            inp.key(name)

    def key_down(self, name: str) -> None:
        self._trace(f"key_down {name}")
        if not self.dry_run:
            inp.key_down(name)

    def key_up(self, name: str) -> None:
        self._trace(f"key_up {name}")
        if not self.dry_run:
            inp.key_up(name)

    WHEEL_FAST_MS = 50  # per notch in fast timing (AHK: 200), then WHEEL_SETTLE_MS once
    WHEEL_SETTLE_MS = 300

    def wheel(self, notches: int, interval_ms: int = 200) -> None:
        """Negative = WheelDown. Each notch is followed by `interval_ms` (AHK Sleep, 200);
        fast timing sends notches 50 ms apart and settles once at the end (a 35-notch
        scroll takes 2 s instead of 7)."""
        self._trace(f"wheel {notches}")
        step = 1 if notches > 0 else -1
        fast = self.fast() and interval_ms >= 100
        per = self.WHEEL_FAST_MS if fast else interval_ms
        for _ in range(abs(notches)):
            if not self.dry_run:
                inp.wheel(step, interval=0)
            self.sleep(per)
        if fast:
            self.stats["wait_saved_ms"] = (
                self.stats.get("wait_saved_ms", 0.0)
                + abs(notches) * (interval_ms - per)
                - self.WHEEL_SETTLE_MS
            )
            self.sleep(self.WHEEL_SETTLE_MS)

    # -- timed clicks (plan: robustness + speed, owner request 2026-09-06) -------------------
    HOVER_SAFE_MS = 1000  # AHK: MouseMove, Sleep 1000, Click
    HOVER_FAST_MS = 150
    CHANGE_POLL_MS = 100
    CHANGE_SETTLE_MS = 250  # after the screen changed: let the transition finish
    CHANGE_FRACTION = 0.30  # of thumbnail cells that must differ (a dialog covers far more)
    CHANGE_LEVELS = 40  # per-cell mean absolute difference (0-255) that counts as changed

    POLL_SAFE_MS = 1000  # AHK loops: Sleep 1000 between two PixelSearch
    POLL_FAST_MS = 250

    def fast(self) -> bool:
        return self.timing != "safe" and not self.dry_run

    def poll_ms(self) -> int:
        """Interval of the "wait until the screen shows X" loops (scarab, arena, crystal)."""
        return self.POLL_FAST_MS if self.fast() else self.POLL_SAFE_MS

    def hover(self) -> None:
        """The pause between moving onto a button and clicking it."""
        self.sleep(self.HOVER_FAST_MS if self.fast() else self.HOVER_SAFE_MS)

    def _thumbnail(self) -> np.ndarray | None:
        """Client capture reduced to a coarse grid (block means), for change detection."""
        if self.window is None:
            return None
        img = capture.grab(self.window.client)[:, :, :3]
        h, w = img.shape[:2]
        gh, gw = 27, 48
        bh, bw = h // gh, w // gw
        if bh == 0 or bw == 0:
            return None
        cropped = img[: bh * gh, : bw * gw].astype(np.float32)
        return cropped.reshape(gh, bh, gw, bw, 3).mean(axis=(1, 3))

    def wait_change(self, max_ms: float, before: np.ndarray | None = None) -> bool:
        """Wait until the game screen differs from `before` (or from now), at most `max_ms`.

        Safe timing (or dry run): a plain sleep of `max_ms`, the AHK behaviour. Fast timing:
        poll the screen; as soon as enough of it changed, a short settle and return True.
        Nothing changing by `max_ms` returns False after exactly the old delay, so the fast
        mode is never slower than the safe one on a click that changes nothing."""
        if not self.fast():
            self.sleep(max_ms)
            return False
        if before is None:
            before = self._thumbnail()
        if before is None:
            self.sleep(max_ms)
            return False
        end = time.monotonic() + max_ms / 1000
        while True:
            self.sleep(self.CHANGE_POLL_MS)
            now = self._thumbnail()
            if now is not None and now.shape == before.shape:
                diff = np.abs(now - before).mean(axis=2)
                if (diff > self.CHANGE_LEVELS).mean() >= self.CHANGE_FRACTION:
                    left = (end - time.monotonic()) * 1000
                    self.stats["wait_saved_ms"] = self.stats.get("wait_saved_ms", 0.0) + max(
                        0.0, left - self.CHANGE_SETTLE_MS
                    )
                    self.sleep(self.CHANGE_SETTLE_MS)
                    return True
            if time.monotonic() >= end:
                return False

    EXPECT_TIMEOUT_MS = 4000  # patience for an expected screen (slow game / server)

    EXPECT_STABLE_MS = 100  # a dialog scaling in can match for one frame: confirm once

    def wait_for(self, p: Probe, timeout_ms: float = EXPECT_TIMEOUT_MS) -> bool:
        """Poll until `p` is found twice EXPECT_STABLE_MS apart (True) or `timeout_ms`
        elapsed (False)."""
        end = time.monotonic() + timeout_ms / 1000
        while True:
            if self.found(p):
                self.sleep(self.EXPECT_STABLE_MS)
                if self.found(p):
                    return True
            if time.monotonic() >= end:
                return False
            self.sleep(self.CHANGE_POLL_MS)

    def wait_gone(self, p: Probe, timeout_ms: float = EXPECT_TIMEOUT_MS) -> bool:
        """Poll until `p` is no longer found (True) or `timeout_ms` elapsed (False)."""
        end = time.monotonic() + timeout_ms / 1000
        while True:
            if not self.found(p):
                return True
            if time.monotonic() >= end:
                return False
            self.sleep(self.CHANGE_POLL_MS)

    def tap(self, p: Point, settle_ms: float = 1500, expect: Probe | None = None) -> None:
        """AHK `MouseMove x, y; Sleep 1000; Click; Sleep settle`: move onto the point, hover,
        click, then wait for the screen to react (fast timing) or `settle_ms` (safe).

        `expect`: the probe the click should bring up (a dialog's close button...). Fast
        timing then waits for it, with more patience than `settle_ms` (EXPECT_TIMEOUT_MS,
        for a slow game) and returns as soon as it is there; a probe that never shows only
        logs a line, the feature goes on as before."""
        self.move_to(p)
        self.hover()
        if expect is not None and self.fast():
            self.click()
            self.sleep(self.CHANGE_SETTLE_MS)
            if not self.wait_for(expect, max(self.EXPECT_TIMEOUT_MS, settle_ms)):
                self.status(f"Expected screen ({expect.name}) did not appear after the click")
            return
        before = self._thumbnail() if self.fast() and settle_ms else None
        self.click()
        if settle_ms:
            self.wait_change(settle_ms, before)

    def open_screen(self, p: Point, expect: Probe, settle_ms: float = 1500) -> bool:
        """Click a main-screen icon that opens a full-screen dialog. Fast timing: wait for
        `expect`; when it does not show (the click landed elsewhere, a leftover dialog), go
        back to the main screen (big X, main-menu check) and click once more. Returns
        whether the expected screen is there (always True in safe timing, which cannot
        tell)."""
        self.tap(p, settle_ms, expect=expect)
        if not self.fast() or self.found(expect):
            return True
        from firestone_bot.features.big_close import big_close
        from firestone_bot.features.main_menu import main_menu

        self.status("Screen not reached, returning to the main screen and retrying")
        big_close(self)
        main_menu(self)
        self.focus()
        self.tap(p, settle_ms, expect=expect)
        return self.found(expect)

    def tap_xy(self, x: int, y: int, settle_ms: float = 1500, anchor=None) -> None:
        self.tap(Point(x, y, anchor), settle_ms)

    def tap_screen(self, sx: int, sy: int, settle_ms: float = 1000) -> None:
        """tap() on a screen pixel (a PixelSearch hit)."""
        self.move_screen(sx, sy)
        self.hover()
        before = self._thumbnail() if self.fast() and settle_ms else None
        self.click()
        if settle_ms:
            self.wait_change(settle_ms, before)

    # -- vision -----------------------------------------------------------------------------
    def search(self, p: Probe, variation: int | None = None) -> Hit | None:
        """PixelSearch on a fresh capture of the probe rect. None when ErrorLevel != 0."""
        vp = self._viewport()
        rect = vp.probe_rect_screen(p)
        var = (p.variation if variation is None else variation) + vp.variation_boost()
        img = capture.grab(rect)
        found = pixel_search_in(img, rect, rect, p.color, var)
        if found is None:
            self._trace(f"search {p.name or p} -> miss")
            return None
        lx, ly = vp.to_logical(found[0], found[1], p.anchor)
        self._trace(f"search {p.name or p} -> screen {found} logical ({lx},{ly})")
        return Hit(found[0], found[1], lx, ly)

    def found(self, p: Probe, variation: int | None = None) -> bool:
        return self.search(p, variation) is not None

    def region_image(self, rect: tuple[int, int, int, int]) -> np.ndarray:
        """BGR pixels of a logical rect (x1, y1, x2, y2), e.g. a counter's digits."""
        vp = self._viewport()
        sx1, sy1 = vp.to_screen(rect[0], rect[1])
        sx2, sy2 = vp.to_screen(rect[2], rect[3])
        return capture.grab(Rect(sx1, sy1, sx2 - sx1, sy2 - sy1))[:, :, :3].copy()

    def read_number(self, rect: tuple[int, int, int, int], last_word: bool = False) -> int | None:
        """The white number drawn in a logical rect (top-left anchored), None if unreadable."""
        if self._digits is None:
            from firestone_bot.vision.digits import DigitReader

            self._digits = DigitReader()
        vp = self._viewport()
        sx1, sy1 = vp.to_screen(rect[0], rect[1], (0.0, 0.0))
        sx2, sy2 = vp.to_screen(rect[2], rect[3], (0.0, 0.0))
        img = capture.grab(Rect(sx1, sy1, sx2 - sx1, sy2 - sy1))[:, :, :3]
        value = self._digits.read(img, last_word=last_word)
        self._trace(f"read_number {rect} -> {value}")
        return value

    def locked(self, feature: str) -> bool:
        """True (with a status line) when the account cannot use `feature` yet."""
        if self.progress is None:
            return False
        from firestone_bot.progress import LABELS

        reason = self.progress.locked_reason(feature)
        if reason:
            self.status(f"{LABELS.get(feature, feature)}: {reason}, skipped")
            return True
        return False

    def wait_region_change(
        self, rect: tuple[int, int, int, int], before: np.ndarray, timeout_ms: int = 15000
    ) -> bool:
        """Poll a logical rect until enough pixels differ from `before` (digits redrawn)."""
        waited = 0
        while waited < timeout_ms:
            step = self.poll_ms()
            self.sleep(step)
            waited += step
            after = self.region_image(rect)
            if after.shape == before.shape:
                changed = (np.abs(after.astype(int) - before.astype(int)) > 60).any(axis=2).sum()
                if changed > 40:
                    return True
        return False
