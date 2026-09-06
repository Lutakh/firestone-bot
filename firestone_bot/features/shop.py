"""Daily shop: free mystery box (detects the daily reset) and the daily check-in.

Port of Functions/Shop.ahk, reworked for the current shop layout (2026-09): the free mystery
box is the FIRST card of the horizontally scrolling "Daily deals" row while it is claimable
(it moves to the end once claimed), so the row is scrolled back to its start before probing
the green "Claim" button. The AHK click at (591,857) would land on a paid deal once the box
has been claimed, so the click is now guarded by the probe.

The runner calls this every cycle regardless of the Shop setting so the daily reset is always
detected; the check-in part still depends on the Shop setting.
"""

from __future__ import annotations

from firestone_bot import daily
from firestone_bot.features.big_close import big_close
from firestone_bot.features.main_menu import main_menu
from firestone_bot.game import Game
from firestone_bot.state import hours_since
from firestone_bot.vision import atlas


def claim_free_mystery_box(g: Game) -> bool:
    """Scroll the daily deals back to the start and claim the free box. True when it was
    claimable (= the game day has just reset)."""
    g.move_to(atlas.SHOP_DEALS_HOVER)
    g.sleep(500)
    g.wheel(30)
    g.sleep(1000)
    if not g.found(atlas.SHOP_MYSTERY_CLAIM_READY):
        return False
    g.tap(atlas.SHOP_MYSTERY_CLAIM, 0)
    g.sleep(2000)  # the box goes to the bag (opened later by open_chests), no pop-up
    return True


def shop(g: Game) -> None:
    g.focus()
    # The red dot is the cheap trigger; near the expected reset time (23 h after the last
    # detected one, or never detected) the shop is opened anyway so the reset is not missed.
    if not g.found(g.ms.shop_bell) and 0 < hours_since(g.settings.LastTokenReset) < 23:
        return
    g.tap(g.ms.shop_icon)
    if claim_free_mystery_box(g):
        daily.mark_daily_reset(g.settings)
        g.status("Daily shop: free mystery box claimed, daily counters reset")
    if g.settings.flag("Shop"):
        # open daily check-in
        g.tap(atlas.SHOP_CHECKIN_TAB, 1000)
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
