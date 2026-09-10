"""Daily shop: free mystery box (detects the daily reset) and the daily check-in.

Port of Functions/Shop.ahk, reworked for the current shop layout (2026-09): the free mystery
box is the FIRST card of the horizontally scrolling "Daily deals" row while it is claimable
(it moves to the end once claimed), so the row is scrolled back to its start before probing
the green "Claim" button. The AHK click at (591,857) would land on a paid deal once the box
has been claimed, so the click is now guarded by the probe.

Every tab is reached through `tab_slots`, never through the blob list itself: the selected
tab is not tan and so is missing from it, which made the bot open the paid "Gems" tab each
time it meant to go back to the daily deals (owner, 2026-09-09).

The runner calls this every cycle regardless of the Shop setting so the daily reset is always
detected; the check-in part still depends on the Shop setting.
"""

from __future__ import annotations

import logging

from firestone_bot import daily
from firestone_bot.features.big_close import big_close
from firestone_bot.features.main_menu import main_menu
from firestone_bot.game import Game
from firestone_bot.state import hours_since
from firestone_bot.vision import atlas, blobs
from firestone_bot.vision.atlas import Point
from firestone_bot.vision.probes import match_mask

log = logging.getLogger("firestone_bot.shop")


def _claim_button_shown(g: Game) -> bool:
    """A wide green rectangle in the claim box is the Free button; the tick drawn there once
    the box is claimed is a small mark. The share of green (0.4 of the box) was at the
    threshold on the Windows client (0.3998, 2026-09-08: the box was never claimed)."""
    p = atlas.SHOP_MYSTERY_CLAIM_READY
    green = match_mask(g.region_image((p.x1, p.y1, p.x2, p.y2)), p.color, p.variation)
    rows = green.mean(axis=1) > 0.3
    cols = green.mean(axis=0) > 0.3
    fx = (p.x2 - p.x1) / green.shape[1]  # logical px per capture px
    fy = (p.y2 - p.y1) / green.shape[0]
    width, height = float(cols.sum() * fx), float(rows.sum() * fy)
    log.debug("free box: green rectangle %.0f x %.0f logical px", width, height)
    return width >= atlas.SHOP_MYSTERY_BUTTON_MIN_W and height >= atlas.SHOP_MYSTERY_BUTTON_MIN_H


def shop_tabs(g: Game) -> list[blobs.Blob]:
    """The UNSELECTED shop tabs, left to right. The selected tab is not tan, so it is missing
    from this list: never index it as if it were the tab row (see `tab_slots`)."""
    return sorted(
        blobs.find_blobs(
            g,
            atlas.SHOP_TAB_STRIP,
            atlas.SHOP_TAB_BG,
            atlas.SHOP_TAB_BG_VAR,
            anchor=atlas.ANCHOR_CENTER,
            min_w=atlas.SHOP_TAB_MIN_W,
            min_h=atlas.SHOP_TAB_MIN_H,
        ),
        key=lambda b: b.cx,
    )


def tab_slots(g: Game) -> list[Point]:
    """The whole tab row, left to right, including the selected tab.

    `shop_tabs` only sees the tan (unselected) tabs, so `shop_tabs()[0]` is the SECOND tab
    whenever the first one is selected - which is how the shop usually reopens. That is how
    the bot clicked the paid "Gems" tab while it meant to go back to the daily deals (owner,
    2026-09-09). The tabs are evenly spaced and the row is centred in the strip, so the
    selected tab is put back: either in the double gap it leaves between two tan tabs, or, if
    it sits at one end, at the end that keeps the row centred.
    """
    found = shop_tabs(g)
    if not found:
        return []
    xs = [b.cx for b in found]
    cy = sorted(b.cy for b in found)[len(found) // 2]
    if len(xs) >= 2:
        gaps = sorted(xs[i + 1] - xs[i] for i in range(len(xs) - 1))
        pitch = gaps[0]
        hole = next((i for i in range(len(xs) - 1) if xs[i + 1] - xs[i] > pitch * 1.5), None)
        if hole is not None:
            xs.insert(hole + 1, (xs[hole] + xs[hole + 1]) // 2)
        else:
            centre = (atlas.SHOP_TAB_STRIP[0] + atlas.SHOP_TAB_STRIP[2]) / 2
            left, right = xs[0] - pitch, xs[-1] + pitch
            if abs((left + xs[-1]) / 2 - centre) <= abs((xs[0] + right) / 2 - centre):
                xs.insert(0, left)
            else:
                xs.append(right)
    return [Point(x, cy, atlas.ANCHOR_CENTER) for x in xs]


def _select_slot(g: Game, slots: list[Point], index: int) -> bool:
    """Make sure the tab at `index` of the row is the selected one, and say so. A tab that
    stays tan after the click was not selected: better to skip the step than to act on a page
    that is not the one meant (paid offers live one tab away)."""
    want = slots[index]
    if not any(abs(b.cx - want.x) < 20 for b in shop_tabs(g)):
        return True  # not tan any more: it is the selected tab already
    g.tap(want, 1200)
    g.wait_still()
    if any(abs(b.cx - want.x) < 20 for b in shop_tabs(g)):
        g.status("Daily shop: the tab did not open, step skipped")
        g.save_diagnostic("shop-tab-miss.png")
        return False
    return True


def claim_free_mystery_box(g: Game) -> bool:
    """Scroll the daily deals back to the start and claim the free box. True when it was
    claimable (= the game day has just reset)."""
    slots = tab_slots(g)
    if not slots:
        g.status("Daily shop: no tab row found, free box skipped")
        return False
    if not _select_slot(g, slots, 0):  # the shop may reopen on the last tab visited
        return False
    g.move_to(atlas.SHOP_DEALS_HOVER)
    g.sleep(500)
    g.wheel(30)
    g.sleep(1000)
    hit = g.search(atlas.SHOP_MYSTERY_CLAIM_READY)
    if hit is None:
        g.status("Daily shop: no free mystery box to claim")
        return False
    if not _claim_button_shown(g):
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


def button_shaped(found: list) -> list:
    """The blobs that look like the Check In button: much wider than high. The reward tiles
    of the page carry green frames and green ticks, which are square."""
    return [
        b
        for b in found
        if b.h <= atlas.SHOP_CHECKIN_MAX_H and b.w >= atlas.SHOP_CHECKIN_MIN_RATIO * b.h
    ]


def check_in(g: Game) -> None:
    """Daily check-in: the calendar tab is the last one of the row; its green "Check In"
    button is clicked only where it is actually found, anywhere in the body of the dialog
    (a limited-time banner pushes it down). The AHK clicked two fixed points blind, which at
    another aspect landed on a paid bundle and opened the Steam checkout (2026-09-09)."""
    slots = tab_slots(g)
    if not slots:
        g.status("Daily shop: no tab row found, check-in skipped")
        return
    if not _select_slot(g, slots, -1):
        return
    found = blobs.find_blobs(
        g,
        atlas.SHOP_CHECKIN_AREA,
        atlas.SHOP_CHECKIN_GREEN,
        atlas.SHOP_CHECKIN_GREEN_VAR,
        anchor=atlas.ANCHOR_CENTER,
        min_w=atlas.SHOP_CHECKIN_MIN_W,
        min_h=atlas.SHOP_CHECKIN_MIN_H,
    )
    button = button_shaped(found)
    if not button:
        g.status("Daily shop: nothing to check in today")
        if found:
            g.save_diagnostic("shop-checkin-shape.png")  # green, but not button-shaped
        return
    b = max(button, key=lambda b: b.w * b.h)
    g.status("Daily shop: checking in")
    g.tap(Point(b.cx, b.cy, atlas.ANCHOR_CENTER), 2000)
    g.wait_still()


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
        check_in(g)
    big_close(g)
    g.toast(
        "Main Menu Check", "Checking to ensure we are on main screen after redeeming shop gifts", 2
    )
    main_menu(g)
