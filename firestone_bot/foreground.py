"""No click or key while the game window is not in front (Windows; owner request 2026-10-28).

2026-10-25 17:18 to 2026-10-26 00:34, the owner's game window could not be brought to the
foreground. The bot logged "activate: the game window could not be brought to the
foreground" 5,605 times and went on: some 3,000 clicks and 2,000 T presses went to whatever
window was in front. What held the foreground was never seen (the captures of that evening
were pruned). It outlived three kills and relaunches of the game (20:38..20:54), the
captures kept changing under it (not a frozen snip), no mouse-guard pause was logged, and
the hero-mode crops of 00:33 show the main screen at 27 % brightness (white text read
70/255, the blue mode button 0x1089FF read 0x042546) and six clicks on that button changed
nothing: a dark layer over a live game. The bot now names what is in front and sends
nothing meanwhile.

Game calls `ForegroundGuard.check` before every event it injects:
- the game window is the foreground window: nothing more (one GetForegroundWindow call);
- otherwise the Stop button and the mouse guard get their turn (a user who took the PC is
  the mouse guard's business), then the game is activated again, up to TRIES times RETRY_MS
  apart; still not in front, nothing is sent and GameNotInFront unwinds the cycle.
The runner then waits (Runner._wait_for_front): every POLL_MS one more activation, never an
input, and it goes on by itself as soon as the game is in front (back to the main screen, a
new cycle), when the game window is gone (the next cycle launches the game) or when a game
restart (scheduled, or asked for by a feature) is due and can clear what is in front
(restart_helps: the game hung, or a window of the game itself). Another program's window
outlives a restart, and the relaunched game's start button is never clicked while it is in
front (2026-10-25 20:38: three relaunches behind the same holder), so that restart waits for
the game to be in front, also when the cycle that finds it due starts behind that window
(Runner._restart_waits_for_front). The wait for the start button of a relaunched game polls
on instead, without running out while another program's window is in front
(features/game_launch.py).

One episode, from the first refusal to the game in front again, writes one status line that
names what holds the foreground by process exe name and window class only (never a window
title: other applications' titles are private, and the log goes out with Send report), one
coarse capture of the game's client area (diagnostics/...-game-not-in-front.png, block means
for a capture about CAPTURE_WIDTH pixels wide: the window or dark layer over the game shows,
its text and title bar cannot be read) and, once it has lasted HEARTBEAT_AFTER_S, one
important heartbeat. Its end writes one line (and a plain heartbeat when the important one
went out).

macOS and Linux: no guard (the runner installs it on Windows only), behaviour unchanged.
"""

from __future__ import annotations

import logging
import os
import sys
import time

from firestone_bot.game import GameNotInFront
from firestone_bot.platform import window as winapi
from firestone_bot.platform.types import PROCESS_NAMES, GameWindowNotFound

log = logging.getLogger("firestone_bot.foreground")

FRONT, BACK, GONE = "front", "back", "gone"


class _PlatformApi:
    """The window functions the guard uses (platform/window.py); tests pass a fake."""

    @staticmethod
    def is_foreground(win) -> bool:
        return winapi.is_foreground(win)

    @staticmethod
    def activate(win) -> bool:
        return winapi.activate(win) is not False

    @staticmethod
    def foreground_owner() -> tuple[str, str, int]:
        return winapi.foreground_owner()

    @staticmethod
    def is_hung(win) -> bool:
        return winapi.is_hung(win)


def _duration(seconds: float) -> str:
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}h{m:02d}m"
    return f"{m}m{sec:02d}s" if m else f"{sec}s"


class ForegroundGuard:
    TRIES = 3  # activations tried before an input is given up
    RETRY_MS = 500
    POLL_MS = 5000  # the runner's wait: one activation this often
    HEARTBEAT_AFTER_S = 30  # an episode this long sends its important heartbeat
    CAPTURE = "game-not-in-front.png"
    # the capture is of another program's window: block means keep its layout and light (a
    # dark layer read 27 % on 2026-10-25), not its text (Send report uploads the diagnostics
    # folder, screenshots ticked by default). 8 x 8 pixels at least, more on a wider client
    # (4K text is twice as tall): the capture is about CAPTURE_WIDTH pixels wide
    CAPTURE_BLOCK = 8
    CAPTURE_WIDTH = 240

    def __init__(self, api=None) -> None:
        self.api = api if api is not None else _PlatformApi()
        self.since: float | None = None  # time.monotonic() of the episode's first refusal
        self.beat = False  # the episode's important heartbeat went out

    @staticmethod
    def supported() -> bool:
        return sys.platform == "win32"

    def reset(self) -> None:
        """A new run: no episode carried over from a stopped one."""
        self.since = None
        self.beat = False

    # -- before every injected event ------------------------------------------------------
    def check(self, g) -> bool:
        """Return when the game window is in front: False when it already was, True when it
        had to be brought back (the pointer may have moved meanwhile: Game puts it back
        before a click or a wheel notch). Raise GameNotInFront otherwise. Sends no input
        itself."""
        win = g.window
        if win is not None and self.api.is_foreground(win):
            if self.since is not None:
                self._back(g)
            return False
        g.sleep(0)  # the Stop button and the mouse guard first
        for attempt in range(self.TRIES):
            if attempt:
                g.sleep(self.RETRY_MS)
            state = self._bring_forward(g)
            if state == FRONT:
                return True
            if state == GONE:
                raise GameNotInFront("the game window is gone", gone=True)
        self._refused(g)
        raise GameNotInFront("the game window could not be brought to the front")

    # -- the runner's wait ----------------------------------------------------------------
    def poll(self, g) -> str:
        """One activation, no input: FRONT (the episode is over), BACK or GONE."""
        state = self._bring_forward(g)
        if state == BACK:
            self._refused(g)
        return state

    def restart_helps(self, g) -> bool:
        """Whether a game restart can clear what keeps the game from the front: the game
        window hung (Windows puts its "Not Responding" ghost in front) or a window of the
        game process itself (a dialog of the game). Another program's window, a locked
        session or a system prompt outlive the restart, and the relaunched game's start
        button would not be clicked either. Unknown: True (the restart goes ahead)."""
        win = g.window
        if win is None:
            return True
        try:
            if self.api.is_hung(win):
                return True
            _exe, _cls, pid = self.api.foreground_owner()
        except Exception:  # informational only: the restart goes ahead
            log.debug("restart check failed", exc_info=True)
            return True
        return bool(pid) and pid == win.pid

    # -- internals --------------------------------------------------------------------------
    def _bring_forward(self, g) -> str:
        try:
            win = g.refresh_window()  # the handle changes when the game is relaunched
        except GameWindowNotFound:
            return GONE
        if not self.api.is_foreground(win):
            self.api.activate(win)
            if not self.api.is_foreground(win):
                return BACK
        if win.client.w == 0:  # it was minimised: its client rect comes back with it
            g.sleep(500)
            try:
                g.refresh_window()
            except GameWindowNotFound:
                return GONE
        if self.since is not None:
            self._back(g)
        return FRONT

    def _refused(self, g) -> None:
        now = time.monotonic()
        if self.since is None:
            self.since = now
            self.beat = False
            g.status(
                "Paused: the game window is not in front and could not be brought there "
                f"({self._holder(g)}); nothing is clicked or typed until it is, then the bot "
                "goes on by itself"
            )
            g.save_diagnostic(self.CAPTURE, block=self.capture_block(g))
        elif not self.beat and now - self.since >= self.HEARTBEAT_AFTER_S:
            self.beat = True
            g.heartbeat(
                "Paused: the game window cannot be brought to the front, no input until it is",
                important=True,
            )

    def capture_block(self, g) -> int:
        """Block size of the episode's coarse capture for the game's client width."""
        win = g.window
        width = win.client.w if win is not None else 0
        return max(self.CAPTURE_BLOCK, width // self.CAPTURE_WIDTH)

    def _back(self, g) -> None:
        lasted = time.monotonic() - (self.since or time.monotonic())
        beat = self.beat
        self.reset()
        g.status(f"The game window is in front again after {_duration(lasted)}; going on")
        if beat:
            g.heartbeat("Game window in front again, the bot goes on")

    def _holder(self, g) -> str:
        """What holds the foreground: exe name and window class, never the title."""
        try:
            exe, cls, pid = self.api.foreground_owner()
        except Exception:  # informational only
            log.debug("foreground owner unreadable", exc_info=True)
            return "in front: unknown"
        if not exe and not cls:
            return "no window has the foreground: a locked session or a system prompt?"
        text = f"in front: {exe or 'an unknown process'}, window class {cls or 'unknown'}"
        win = g.window
        if pid and pid == os.getpid():
            text += ", a window of the bot itself"
        elif (win is not None and pid and pid == win.pid) or exe in PROCESS_NAMES:
            text += ", a window of the game itself"
        return text
