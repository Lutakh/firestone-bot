"""Daily shop: free mystery box (detects the daily reset) and the daily check-in.

Port of Functions/Shop.ahk, reworked for the current shop layout (2026-09): the free mystery
box is the LAST card of the horizontally scrolling "Daily deals" row, so the row is scrolled to
the end before probing its green "Claim" button. The AHK click at (591,857) now lands on a
paid deal and was removed.

The runner calls this every cycle regardless of the Shop setting so the daily reset is always
detected; the check-in part still depends on the Shop setting.
"""

from __future__ import annotations

from firestone_bot import daily
from firestone_bot.features.big_close import big_close
from firestone_bot.features.main_menu import main_menu
from firestone_bot.game import Game
from firestone_bot.vision import atlas


def claim_free_mystery_box(g: Game) -> bool:
    """Scroll the daily deals to the end and claim the free box. True when it was claimable
    (= the game day has just reset)."""
    g.move_to(atlas.SHOP_DEALS_HOVER)
    g.sleep(500)
    g.wheel(-30)
    g.sleep(1000)
    if not g.found(atlas.SHOP_MYSTERY_CLAIM_READY):
        return False
    g.move_to(atlas.SHOP_MYSTERY_CLAIM)
    g.sleep(1000)
    g.click()
    g.sleep(2000)
    # reward pop-up: click away from it
    g.move_to(atlas.SHOP_REWARD_DISMISS)
    g.sleep(1000)
    g.click()
    g.sleep(1000)
    return True


def shop(g: Game) -> None:
    g.focus()
    if not g.found(atlas.SHOP_RED_DOT):
        return
    g.move_to(atlas.SHOP_ICON)
    g.sleep(1000)
    g.click()
    g.sleep(1500)
    if claim_free_mystery_box(g):
        daily.mark_daily_reset(g.settings)
        g.status("Daily shop: free mystery box claimed, daily counters reset")
    if g.settings.flag("Shop"):
        # open daily check-in
        g.move_to(atlas.SHOP_CHECKIN_TAB)
        g.sleep(1000)
        g.click()
        g.sleep(1000)
        # check in
        g.move_to(atlas.SHOP_CHECKIN_CLAIM)
        g.sleep(3000)
        g.click()
        g.sleep(1000)
        g.move_to(atlas.SHOP_CHECKIN_OK)
        g.sleep(3000)
        g.click()
        g.sleep(1000)
    big_close(g)
    g.toast(
        "Main Menu Check", "Checking to ensure we are on main screen after redeeming shop gifts", 2
    )
    main_menu(g)
