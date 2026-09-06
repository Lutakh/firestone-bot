"""Make sure the game is running and on screen before a cycle (owner request 2026-09-04).

- Not running: launch it through the store chosen by the GamePlatform setting (auto = the
  platform seen last, else whichever install exists), wait for the window, then wait for the
  green start button of the loading screen and click it (same wait as RestartGameRoutine).
- Minimised: Game.focus() restores the window (find_game_window keeps iconic windows).
"""

from __future__ import annotations

import time

from firestone_bot.game import Game
from firestone_bot.platform import process
from firestone_bot.platform.window import GameWindowNotFound, find_game_window
from firestone_bot.vision import atlas

WINDOW_TIMEOUT_S = 180
START_BUTTON_TIMEOUT_S = 300


def wait_for_start_button(g: Game, timeout_s: float = START_BUTTON_TIMEOUT_S) -> bool:
    """Poll the loading screen for the green start button and click it (AHK loop)."""
    start = time.monotonic()
    while time.monotonic() - start < timeout_s:
        g.focus()  # WinActivate / WinWaitActive / ControlFocus
        g.sleep(500)
        if g.window is not None and g.window.client.w > 0:
            g.move_to(atlas.RESTART_HOVER)
            g.sleep(1000)
            if g.found(atlas.RESTART_START_BUTTON):
                g.click()
                g.sleep(1000)
                return True
        g.sleep(5000)
    return False


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
    if process.wait_for_game(timeout=WINDOW_TIMEOUT_S) is None:
        g.status("Game launch: the process did not appear, giving up")
        return False
    g.settings.set("LastPlatform", platform)
    g.settings.save()
    if wait_for_start_button(g):
        g.status("Game launch: start button clicked, resuming")
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
        if process.wait_for_game(timeout=WINDOW_TIMEOUT_S) is not None and wait_for_start_button(g):
            g.status("Game launch: start button clicked after a Steam restart, resuming")
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
        return wait_for_start_button(g)
    if win.client.w == 0:
        g.status("Game window was minimised: restoring it")
    g.focus()  # restores a minimised window and re-reads the client rect
    return True
