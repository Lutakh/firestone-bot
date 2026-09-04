"""Chaos rift from the guild screen (Python rework of subFunctions/Chaos.ahk).

The AHK bot switched the rift to Auto, which spends every available token, including the
paid ones (orange medallion, second counter top right). The rework only hits manually while
the icon shown inside the green "Hit" button is the FREE token (blue moon, first counter,
10 per day, refilled about an hour after the daily reset), and stops after MaxChaos hits per
game day (ChaosCountDaily, cleared by the daily reset). The Auto/Manual toggle is never touched.
"""

from __future__ import annotations

from firestone_bot import daily
from firestone_bot.features.big_close import big_close
from firestone_bot.game import Game
from firestone_bot.vision import atlas


def _hit_button_token(g: Game) -> str:
    """'free', 'paid' or 'none' depending on the token icon in the Hit button."""
    if g.found(atlas.CHAOS_HIT_ICON_FREE):
        return "free"
    if g.found(atlas.CHAOS_HIT_ICON_PAID):
        return "paid"
    return "none"


def _wait_hit_button(g: Game, timeout_ms: int = 30000) -> bool:
    """Wait for the green Hit button to be back after a hit animation."""
    waited = 0
    while waited < timeout_ms:
        if g.found(atlas.CHAOS_HIT_READY):
            return True
        g.sleep(1000)
        waited += 1000
    return False


def hit_chaos(g: Game) -> None:
    g.focus()
    # Check for Chaos notification on guild screen
    if not g.found(atlas.CHAOS_DOT):
        return
    g.click_point(atlas.CHAOS_OPEN)  # MouseClick, Left, x, y, 1, 0
    g.sleep(1500)
    hits = 0
    while True:
        left = daily.chaos_left(g.settings)
        if left == 0:
            g.status(f"Chaos rift: daily limit reached ({g.settings.MaxChaos}), leaving")
            break
        if not _wait_hit_button(g):
            g.status("Chaos rift: Hit button not found, leaving")
            break
        token = _hit_button_token(g)
        if token != "free":
            g.status(f"Chaos rift: no free token in the Hit button ({token}), leaving")
            break
        g.move_to(atlas.CHAOS_HIT)
        g.sleep(1000)
        g.click()
        g.sleep(3000)
        daily.note_chaos_hit(g.settings)
        hits += 1
        g.status(f"Chaos rift: hit {hits} ({g.settings.ChaosCountDaily} today)")
    big_close(g)
