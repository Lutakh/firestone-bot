"""Scarab game in the tavern (Python rework of Functions/Scarab.ahk).

The AHK bot played one token per cycle without looking at which token. Like the chaos rift,
the game has free tokens (silver scarab coin, middle counter top right, 10 per day) and paid
ones (gold/purple pharaoh coin, right counter). The rework plays only while the icon inside
the green "Play" button is the free silver coin, and stops after MaxScarab plays per game day
(ScarabCountDaily, cleared by the daily reset); once the limit is reached the tavern game is
not visited again until the next reset.
"""

from __future__ import annotations

import numpy as np

from firestone_bot import daily
from firestone_bot.features.big_close import big_close
from firestone_bot.game import Game
from firestone_bot.platform import capture
from firestone_bot.platform.window import Rect
from firestone_bot.vision import atlas


def _counter_image(g: Game) -> np.ndarray:
    """Pixels of the free-token counter; a play changes the digits."""
    x1, y1, x2, y2 = atlas.SCARAB_FREE_COUNTER
    sx1, sy1 = g.vp.to_screen(x1, y1)
    sx2, sy2 = g.vp.to_screen(x2, y2)
    return capture.grab(Rect(sx1, sy1, sx2 - sx1, sy2 - sy1))[:, :, :3].copy()


def _wait_counter_change(g: Game, before: np.ndarray, timeout_ms: int = 15000) -> bool:
    waited = 0
    while waited < timeout_ms:
        g.sleep(1000)
        waited += 1000
        after = _counter_image(g)
        if (
            after.shape == before.shape
            and np.abs(after.astype(int) - before.astype(int)).max() > 40
        ):
            return True
    return False


def _play_button_token(g: Game) -> str:
    """'free', 'paid' or 'none' depending on the token icon in the Play button."""
    if g.found(atlas.SCARAB_PLAY_ICON_PAID):
        return "paid"
    if g.found(atlas.SCARAB_PLAY_ICON_FREE):
        return "free"
    return "none"


def _wait_play_button(g: Game, timeout_ms: int = 20000) -> bool:
    waited = 0
    while waited < timeout_ms:
        if g.found(atlas.TAVERN_USE_TOKEN_READY) or g.found(atlas.SCARAB_PLAY_READY_HOVER):
            return True
        g.sleep(1000)
        waited += 1000
    return False


def play_scarab(g: Game) -> int:
    """Scarab game screen must be open. Plays free tokens up to the daily limit."""
    plays = 0
    while True:
        if daily.scarab_left(g.settings) == 0:
            g.status(f"Scarab: daily limit reached ({g.settings.MaxScarab}), leaving")
            break
        if not _wait_play_button(g):
            g.status("Scarab: Play button not ready, leaving")
            break
        token = _play_button_token(g)
        if token != "free":
            g.status(f"Scarab: no free token in the Play button ({token}), leaving")
            break
        before = _counter_image(g)
        g.move_to(atlas.TAVERN_USE_TOKEN)
        g.sleep(1000)
        g.click()
        g.sleep(500)  # let Unity process the click before the pointer leaves the button
        g.move_to(atlas.SCARAB_PLAY_PARK)  # leave the button so the hover colour goes away
        if not _wait_counter_change(g, before):
            g.status("Scarab: the free-token counter did not change, leaving")
            break
        g.sleep(2000)  # let the reels settle before the next play
        daily.note_scarab_play(g.settings)
        plays += 1
        g.status(f"Scarab: play {plays} ({g.settings.ScarabCountDaily} today)")
    return plays


def scarab(g: Game) -> None:
    # check if skip using scarab token was selected
    if g.settings.flag("Scarab"):
        return
    if daily.scarab_left(g.settings) == 0:
        return  # limit reached for today: no need to open the tavern game
    g.focus()
    # open Tavern
    g.move_to(atlas.TOWN_TAVERN)
    g.sleep(1000)
    g.click()
    g.sleep(1000)
    g.move_to(atlas.TAVERN_SCARAB_TAB)
    g.sleep(1000)
    g.click()
    g.sleep(1000)
    play_scarab(g)
    big_close(g)
