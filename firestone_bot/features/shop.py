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
from firestone_bot.vision.probes import match_mask


def claim_free_mystery_box(g: Game) -> bool:
    """Scroll the daily deals back to the start and claim the free box. True when it was
    claimable (= the game day has just reset)."""
    g.tap(atlas.SHOP_FIRST_TAB, 700)  # the shop may reopen on the last tab visited
    g.move_to(atlas.SHOP_DEALS_HOVER)
    g.sleep(500)
    g.wheel(30)
    g.sleep(1000)
    hit = g.search(atlas.SHOP_MYSTERY_CLAIM_READY)
    if hit is None:
        g.status("Daily shop: no free mystery box to claim")
        return False
    p = atlas.SHOP_MYSTERY_CLAIM_READY
    green = match_mask(g.region_image((p.x1, p.y1, p.x2, p.y2)), p.color, p.variation)
    if float(green.mean()) < atlas.SHOP_MYSTERY_BUTTON_FILL:
        g.status("Daily shop: the free box was already claimed today (green tick, no button)")
        return False
    g.status("Daily shop: free mystery box found, claiming it")
    before = g.region_image(atlas.SHOP_FIRST_CARD).astype(int)
    # click inside the button from the green pixel found (its exact height differs between
    # the Mac and Windows clients)
    g.tap_xy(hit.x + 30, hit.y + 20, 0)
    # the box goes to the bag (opened later by open_chests), no pop-up; the claimed card
    # fades and moves to the end of the row, which takes a few seconds. The next card may
    # carry a green button too (2026-09-08: a claim was reported as not done), so the claim
    # is told by the card picture changing, not by the button alone.
    for _ in range(4):
        g.sleep(1500)
        if not g.found(atlas.SHOP_MYSTERY_CLAIM_READY):
            return True
        after = g.region_image(atlas.SHOP_FIRST_CARD).astype(int)
        if after.shape == before.shape and float(abs(after - before).mean()) > 12:
            g.status("Daily shop: the first card changed after the click, box claimed")
            return True
    g.status("Daily shop: the free box is still claimable after the click, no reset counted")
    g.save_diagnostic("shop-claim-miss.png")
    return False


def shop(g: Game) -> None:
    g.focus()
    # The red dot is the cheap trigger; near the expected reset time (23 h after the last
    # detected one, or never detected) the shop is opened anyway so the reset is not missed.
    if not g.found(g.ms.shop_bell) and 0 < hours_since(g.settings.LastTokenReset) < 23:
        return
    g.status("Daily shop: opening the shop")
    g.require_screen(g.ms.shop_icon, atlas.DIALOG_CLOSE_X)
    if claim_free_mystery_box(g):
        # A verified claim IS the new game day, whenever it happens: the bot started an hour
        # before the reset must clear the counters at the reset (owner, 2026-09-07). The
        # false resets of that day came from an unverified claim, not from the timing.
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
