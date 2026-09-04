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

from firestone_bot.platform import capture
from firestone_bot.platform import input as inp
from firestone_bot.platform.window import GameWindowNotFound, WindowInfo, activate, find_game_window
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
