"""Runtime context handed to every feature module.

Wraps window, viewport, capture, input and settings behind the vocabulary of the AHK code so
that ported functions read like the originals:

    g.focus()                       ControlFocus / WinActivate
    g.move(x, y); g.sleep(1000)     MouseMove x, y  /  Sleep, 1000
    g.click()                       Click
    g.click_at(x, y)                Click x, y
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
        # called with the screen pixel about to be clicked (the app hides its overlay there)
        self.click_hook: Callable[[int, int], None] | None = None
        self._pointer: tuple[int, int] | None = None  # last screen pixel the bot moved to

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

    def toast(self, title: str, text: str, seconds: float) -> None:
        """AHK timed MsgBox: shown as a status line, then the same delay."""
        self.status(f"{title}: {text}")
        self.sleep(seconds * 1000)

    def _trace(self, s: str) -> None:
        self.actions.append(s)
        log.debug(s)

    # -- input (logical coordinates) ------------------------------------------------------
    def move(self, x: int, y: int, anchor=None) -> None:
        sx, sy = self._viewport().to_screen(x, y, anchor)
        self._trace(f"move ({x},{y}) -> screen ({sx},{sy})")
        self._pointer = (sx, sy)
        if not self.dry_run:
            inp.move(sx, sy)

    def move_to(self, p: Point) -> None:
        self.move(p.x, p.y, p.anchor)

    def _before_click(self, sx: int, sy: int) -> None:
        if self.click_hook is not None and not self.dry_run:
            self.click_hook(sx, sy)

    def click(self) -> None:
        self._trace("click")
        if self._pointer is not None:
            self._before_click(*self._pointer)
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
        self._pointer = (sx, sy)
        if not self.dry_run:
            inp.move(sx, sy)

    def click_screen(self, sx: int, sy: int) -> None:
        self._trace(f"click screen ({sx},{sy})")
        self._pointer = (sx, sy)
        self._before_click(sx, sy)
        if not self.dry_run:
            inp.move(sx, sy)
            inp.click()

    def drag(self, x1: int, y1: int, x2: int, y2: int, anchor=None) -> None:
        """Left-button drag between two logical points (same anchor for both)."""
        vp = self._viewport()
        sx1, sy1 = vp.to_screen(x1, y1, anchor)
        sx2, sy2 = vp.to_screen(x2, y2, anchor)
        self._trace(f"drag ({x1},{y1}) -> ({x2},{y2}) screen ({sx1},{sy1}) -> ({sx2},{sy2})")
        self._pointer = (sx2, sy2)
        self._before_click(sx1, sy1)
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

    def wheel(self, notches: int, interval_ms: int = 200) -> None:
        """Negative = WheelDown. Each notch is followed by `interval_ms` (AHK Sleep, 200)."""
        self._trace(f"wheel {notches}")
        step = 1 if notches > 0 else -1
        for _ in range(abs(notches)):
            if not self.dry_run:
                inp.wheel(step, interval=0)
            self.sleep(interval_ms)

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
        try:
            if self._digits is None:
                from firestone_bot.vision.digits import DigitReader

                self._digits = DigitReader()
            vp = self._viewport()
            sx1, sy1 = vp.to_screen(rect[0], rect[1], (0.0, 0.0))
            sx2, sy2 = vp.to_screen(rect[2], rect[3], (0.0, 0.0))
            img = capture.grab(Rect(sx1, sy1, sx2 - sx1, sy2 - sy1))[:, :, :3]
            value = self._digits.read(img, last_word=last_word)
        except Exception:  # a missing template file, a capture error: never end the cycle
            log.exception("read_number %s failed", rect)
            value = None
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
            self.sleep(1000)
            waited += 1000
            after = self.region_image(rect)
            if after.shape == before.shape:
                changed = (np.abs(after.astype(int) - before.astype(int)) > 60).any(axis=2).sum()
                if changed > 40:
                    return True
        return False
