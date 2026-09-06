"""Pause the bot when the user touches the mouse or the keyboard (owner spec, 2026-09-04).

pynput listeners watch the mouse and keyboard. The bot's own events are told apart by timing
and position: an event within IGNORE_AFTER_INJECTION_S of the bot's last injection, or a
pointer position within MOVE_TOLERANCE of where the bot last put it, is the bot's. The
`injected` flag pynput 1.8 reports on Windows only strengthens the other direction: an event
NOT flagged injected is certainly the user's. It cannot exclude events, because a remote
desktop (Parsec, RDP) injects the user's real mouse the same way the bot does: the owner
moved the mouse through Parsec on 2026-09-06 and nothing happened. Any user event while a
run is armed sets `triggered`; the bot thread notices it in Game.sleep() (every wait goes
through it) and calls `check()`, which hands over to the GUI (`on_pause`): a pop-up offers to
start a new cycle or to continue where the bot stopped, and starts a new cycle by itself
after PAUSE_TIMEOUT_S without an answer, the countdown restarting on every new movement.
"""

from __future__ import annotations

import logging
import math
import os
import threading
import time
from collections.abc import Callable

from firestone_bot.platform import input as inp

log = logging.getLogger("firestone_bot.inputguard")

PAUSE_TIMEOUT_S = 30
# Test hook: with this variable set, pynput's `injected` flag is ignored and only the timing
# / position heuristic tells the bot's events apart, so a script posting synthetic events
# (CGEventPost on macOS flags them injected) can exercise the pause flow end to end.
IGNORE_INJECTED_FLAG = bool(os.environ.get("FIRESTONE_GUARD_IGNORE_INJECTED_FLAG"))
IGNORE_AFTER_INJECTION_S = 0.25
MOVE_TOLERANCE = 8  # pynput units (points on macOS, pixels elsewhere)


class UserInterrupted(Exception):
    """The user asked for a new cycle (or the pause timed out): unwinds the current cycle."""


class InputGuard:
    def __init__(self, on_pause: Callable[[InputGuard], str]) -> None:
        self.on_pause = on_pause  # blocks until a decision: "restart" or "continue"
        self.active = False
        self.paused = False
        self.triggered = threading.Event()
        self.last_activity = 0.0
        self.reason = ""
        self._listeners: list = []

    # -- listeners ------------------------------------------------------------------------
    def start(self) -> bool:
        if self._listeners:
            return True
        try:
            from pynput import keyboard, mouse
        except Exception:
            log.exception("input guard: pynput unavailable")
            return False
        try:
            m = mouse.Listener(
                on_move=self._on_move, on_click=self._on_click, on_scroll=self._on_scroll
            )
            k = keyboard.Listener(on_press=self._on_press)
            for li in (m, k):
                li.daemon = True
                li.start()
            self._listeners = [m, k]
        except Exception:
            log.exception("input guard: listeners failed to start")
            return False
        return True

    def stop(self) -> None:
        for li in self._listeners:
            try:
                li.stop()
            except Exception:
                log.debug("input guard: listener stop failed", exc_info=True)
        self._listeners = []

    def arm(self) -> None:
        self.triggered.clear()
        self.active = True

    def disarm(self) -> None:
        self.active = False
        self.triggered.clear()

    # -- event classification -------------------------------------------------------------
    @staticmethod
    def _bot_own(pos: tuple[float, float] | None) -> bool:
        t, last_pos = inp.last_injection()
        if time.monotonic() - t < IGNORE_AFTER_INJECTION_S:
            return True
        if pos is not None and last_pos is not None:
            return math.dist(pos, last_pos) <= MOVE_TOLERANCE
        return False

    def _event(self, what: str, injected, pos=None) -> None:
        if not self.active:
            return
        if IGNORE_INJECTED_FLAG:
            injected = None
        if injected is False:
            pass  # hardware event: the user's for sure
        elif self._bot_own(pos):
            return  # injected (the bot, or a remote desktop) and where/when the bot acted
        self.last_activity = time.monotonic()
        self.reason = what
        self.triggered.set()

    def _on_move(self, x, y, *rest) -> None:
        self._event("mouse moved", rest[0] if rest else None, (x, y))

    def _on_click(self, x, y, button, pressed, *rest) -> None:
        if pressed:
            self._event("mouse clicked", rest[0] if rest else None, None)

    def _on_scroll(self, x, y, dx, dy, *rest) -> None:
        self._event("mouse wheel used", rest[0] if rest else None, None)

    def _on_press(self, key, *rest) -> None:
        self._event("keyboard used", rest[0] if rest else None, None)

    # -- bot thread -----------------------------------------------------------------------
    def check(self, game) -> None:
        """Called from the bot thread inside every wait. Blocks while the pop-up is up;
        raises UserInterrupted when a new cycle was chosen (or the pause timed out)."""
        if not self.active or self.paused or not self.triggered.is_set():
            return
        self.paused = True
        try:
            game.status(f"Paused: {self.reason} while the bot was running")
            decision = self.on_pause(self)
        finally:
            self.paused = False
            self.triggered.clear()
        if decision == "continue":
            game.status("Continuing the cycle where it stopped")
            game.focus()
            inp.restore_position()
            self.triggered.clear()
            return
        raise UserInterrupted(decision)

    def remaining(self) -> float:
        """Seconds left before the pause turns into a new cycle."""
        return max(0.0, PAUSE_TIMEOUT_S - (time.monotonic() - self.last_activity))
