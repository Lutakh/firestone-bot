"""Make sure the game is running and on screen before a cycle (owner request 2026-09-04).

- Not running: launch it through the store chosen by the GamePlatform setting (auto = the
  platform seen last, else whichever install exists), wait for the window, then wait for the
  green start button of the loading screen and click it (same wait as RestartGameRoutine).
- Minimised: Game.focus() restores the window (find_game_window keeps iconic windows).
"""

from __future__ import annotations

import sys
import time

from firestone_bot.game import BotStopped, Game, GameNotInFront
from firestone_bot.platform import process, window
from firestone_bot.platform.window import GameWindowNotFound, find_game_window
from firestone_bot.vision import atlas

WINDOW_TIMEOUT_S = 180
START_BUTTON_TIMEOUT_S = 300


def wait_for_start_button(g: Game, timeout_s: float = START_BUTTON_TIMEOUT_S) -> bool:
    """Poll the loading screen for the green start button and click it (AHK loop).

    A relaunched game that cannot be brought to the front (GameNotInFront, Windows) gets no
    move and no click: the wait polls on rather than unwind a half-done restart
    (2026-10-25 20:39: three relaunches whose windows never came to the front). While
    another program's window holds the front, the wait does not run out either: a timeout
    reads as "no start screen", and the callers would kill the game (and restart Steam)
    every few minutes for as long as that window stays (review 2026-10-28). A hung game, a
    dialog of the game or a window that went away keep the timeout (restart_helps)."""
    start = time.monotonic()
    while time.monotonic() - start < timeout_s:
        g.focus()  # WinActivate / WinWaitActive / ControlFocus
        g.sleep(500)
        if g.window is not None and g.window.client.w > 0:
            try:
                g.move_to(atlas.RESTART_HOVER)
                g.sleep(1000)
                if g.found(atlas.RESTART_START_BUTTON):
                    g.click()
                    g.sleep(1000)
                    return True
            except GameNotInFront as e:
                # nothing was sent; the next round tries again
                guard = getattr(g, "front_guard", None)
                if not e.gone and guard is not None and not guard.restart_helps(g):
                    start = time.monotonic()
        g.sleep(5000)
    return False


MAXIMIZED = "game_maximized"  # Game.vars: the game window was maximized at the last cycle


def note_window(g: Game) -> None:
    """Remember whether the game window is maximized (read at every cycle start)."""
    win = getattr(g, "window", None)
    if win is not None and win.client.w > 0:
        g.vars[MAXIMIZED] = bool(win.maximized)


def restore_maximized(g: Game) -> None:
    """Maximize the relaunched game window when it was maximized before (Windows: a user
    found the game no longer maximized after the restarts, 2026-10-22). macOS keeps its
    zoom; a fullscreen or a resized window of the user is left as it is."""
    if sys.platform != "win32" or getattr(g, "dry_run", False):
        return
    if not getattr(g, "vars", {}).get(MAXIMIZED):
        return
    try:
        win = find_game_window()
    except GameWindowNotFound:
        return
    if win.maximized or win.fullscreen:
        return
    window.maximize(win)
    g.sleep(1000)
    g.focus()
    g.status("Game launch: the game window is maximized again, as before the relaunch")


def wait_for_game(g: Game, timeout_s: float = WINDOW_TIMEOUT_S) -> bool:
    """Wait for the game process; a Stop ends the wait (the Epic path waits twice, up to 6
    min: a Stop pressed meanwhile still closed the launcher and relaunched the game, review
    2026-09-29)."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if process.find_game_process() is not None:
            return True
        if g.stop_event.is_set():
            raise BotStopped
        time.sleep(1)
    return process.find_game_process() is not None


def launch_game(g: Game) -> bool:
    """Launch the game through the store and wait for its start screen. False on timeout."""
    platform = process.choose_platform(
        g.settings.get("GamePlatform"), g.settings.get("LastPlatform")
    )
    if platform is None:
        g.status("Game launch: no Steam or Epic install found, cannot start the game")
        return False
    g.status(f"Game not running: launching it through {platform}")
    if not g.dry_run:
        process.launch_game(platform)
    if not wait_for_game(g):
        if platform != "epic" or g.dry_run:
            g.status("Game launch: the process did not appear, giving up")
            return False
        # a window of the launcher can hold the launch ("Application is busy" after an
        # update installed while the game was closed, 2026-09-29): a fresh launcher, once
        g.status(
            "Game launch: the game did not start, closing and reopening the Epic launcher "
            "(about a minute), this is expected"
        )
        process.close_epic()
        process.launch_game(platform)
        if not wait_for_game(g):
            g.status("Game launch: the process did not appear after the Epic restart, giving up")
            return False
    g.settings.set("LastPlatform", platform)
    g.settings.save()
    if wait_for_start_button(g):
        g.status("Game launch: start button clicked, resuming")
        restore_maximized(g)
        return True
    if platform == "steam":
        # black window after the launch: restart the Steam client and try once more
        g.status(
            "Game launch: start button not found, closing and relaunching the Steam client "
            "(about a minute), this is expected"
        )
        process.kill_game()
        if not g.dry_run:
            process.restart_steam()
            process.launch_game(platform)
        if wait_for_game(g) and wait_for_start_button(g):
            g.status("Game launch: start button clicked after a Steam restart, resuming")
            restore_maximized(g)
            return True
    g.status("Game launch: start button not found in time")
    return False


def ensure_game_running(g: Game) -> bool:
    """Called at the start of every cycle: launch or restore the game as needed."""
    if process.find_game_process() is None:
        return launch_game(g)
    try:
        win = find_game_window()
    except GameWindowNotFound:
        # process alive but no window yet (still loading): wait for the start screen
        if wait_for_start_button(g):
            return True
        # 2026-09-28 23:51: the owner's game lost its window and stayed a 30 MB process;
        # the start-button wait ran out and the bot stopped for the night. A process that
        # shows no window for that long is a dead game: close it and launch it again, once.
        if process.find_game_process() is None:
            return launch_game(g)
        try:
            find_game_window()
        except GameWindowNotFound:
            g.status("Game launch: the game process has no window (crashed?), restarting it")
            process.kill_game()
            return launch_game(g)
        return wait_for_start_button(g)
    if win.client.w == 0:
        g.status("Game window was minimised: restoring it")
    g.focus()  # restores a minimised window and re-reads the client rect
    return True
