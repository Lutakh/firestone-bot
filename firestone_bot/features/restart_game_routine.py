"""Port of Functions/RestartGameRoutine.ahk: kill the game, relaunch it through the store,
wait for the green start button (5 min per attempt, retried forever like AHK unless
SafetyCap is set)."""

from __future__ import annotations

import time

from firestone_bot.features.game_launch import wait_for_start_button
from firestone_bot.game import Game
from firestone_bot.platform import process


class PlatformUnknown(RuntimeError):
    """AHK exits the app when the platform cannot be determined."""


def restart_game_routine(g: Game) -> None:
    # 1. detect the platform BEFORE closing the game
    platform = process.detect_platform()
    if platform == "steam":
        g.toast("Check Firestone launcher", "Steam Firestone found ", 2)
    elif platform == "epic":
        g.toast("Check Firestone launcher", "Epic Firestone found ", 2)
    else:
        g.heartbeat("Error: Could not determine if game is Steam or Epic.", important=True)
        g.vars["lastRestartTime"] = int(time.monotonic() * 1000)
        raise PlatformUnknown("Could not determine if game is Steam or Epic")
    cap = int(g.settings.get("SafetyCap") or 0)
    attempts = 0
    while True:
        # 2. close the process
        process.kill_game()
        g.sleep(15000)
        # 3. launch according to the platform
        if not g.dry_run:
            process.launch_game(platform)
        if platform == "steam":
            g.heartbeat("Game Restarted via Steam, waiting for pixel...", important=True)
        # 4. wait up to 5 minutes for the start button
        pixel_found = wait_for_start_button(g, 300)
        # 5. resume or retry
        if pixel_found:
            g.heartbeat("Pixel found. Resuming bot.", important=True)
            g.vars["lastRestartTime"] = int(time.monotonic() * 1000)
            return
        g.heartbeat("Pixel not found after 5 min. Retrying restart...", important=True)
        attempts += 1
        if platform == "steam":
            # a relaunched game can stay on a black window while the Steam client keeps a
            # stale state (macOS, 2026-09-06): restart the client before the next attempt
            g.status("Game restart: start screen not found, restarting the Steam client")
            process.kill_game()
            if not g.dry_run:
                process.restart_steam()
        if cap and attempts >= cap:
            g.status(f"RestartGameRoutine: safety cap of {cap} attempts reached")
            return
