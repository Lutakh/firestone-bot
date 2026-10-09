"""Battle pass: claim the milestone rewards (owner request 2026-09-04).

Main screen: the Battle pass button (bottom left, next to Events) shows a bell when a reward
is claimable. Inside, two tabs: Challenges and Rewards; the Rewards tab carries a red badge
with the number of claimable rewards. The Rewards page scrolls horizontally by itself to the
first claimable milestone; green "Claim" buttons appear in two rows (Golden pass on top, Free
at the bottom) under the reward tiles. Buttons are found by colour inside those two rows, so
their exact x does not matter; the page is rescanned after every claim (it may shift) and
scrolled further right once when nothing is left in view.

A button sits about 22 px lower under a tile with a label ("100%", "5%"): the old bands held
only its top edge and the click went just above it, then counted as a claim, thirty times in
a row (Qualitas, 2026-10-09). The bands now cover both heights, the click goes to the
button's own middle, and a claim counts once its button is gone; a button still there after
two clicks ends the visit.
"""

from __future__ import annotations

import numpy as np

from firestone_bot.features.main_menu import main_menu
from firestone_bot.game import Game
from firestone_bot.platform import capture
from firestone_bot.vision import atlas, bells
from firestone_bot.vision.probes import match_mask

MAX_CLAIMS = 30
MAX_CLICKS = 2 * MAX_CLAIMS  # clicks a visit, confirmed or not
MIN_W = 80  # screen px of green columns: a Claim button is about 160 wide at 1920
MIN_H = 12  # screen px of green rows: it is about 47 high
SAME_X = 40  # screen px: the button seen again after its click is the same one


def _green_buttons(g: Game) -> list[tuple[int, int, int]]:
    """(screen x, screen y, row) of the green Claim buttons, Golden row first, left to right;
    (x, y) is the middle of the button itself, wherever it sits in its band."""
    vp = g.vp
    x1, x2 = atlas.BP_REWARD_COLUMNS
    out: list[tuple[int, int, int]] = []
    for row, (y1, y2) in enumerate(atlas.BP_REWARD_ROWS):
        sx1, sy1 = vp.to_screen(x1, y1)
        sx2, sy2 = vp.to_screen(x2, y2)
        rect = capture.Rect(sx1, sy1, sx2 - sx1, sy2 - sy1)
        mask = match_mask(capture.grab(rect), atlas.GREEN_BUTTON, 3)
        # a column of the white "Claim" letters keeps few green pixels (10 at 1920 on the
        # owner's capture of 2026-09-04): any green pixel counts, as it always did
        cols = mask.any(axis=0)
        # runs of green columns wider than half a button are buttons
        start = None
        for x, on in enumerate(list(cols) + [False]):
            if on and start is None:
                start = x
            elif not on and start is not None:
                if x - start >= MIN_W:
                    # its rows: green across a quarter of the run at least (a row through
                    # the letters too); only the flat middle of the button matches the colour
                    rows = np.nonzero(mask[:, start:x].mean(axis=1) >= 0.25)[0]
                    if len(rows) >= MIN_H:
                        cy = (int(rows[0]) + int(rows[-1])) // 2
                        out.append((rect.x + (start + x) // 2, rect.y + cy, row))
                start = None
    return out


def claim_rewards(g: Game) -> int:
    """Rewards tab must be open. Claims every green button, rescanning after each click: a
    claim counts once its button is gone."""
    claimed = clicks = 0
    scrolled = False
    last: tuple[int, int, int] | None = None  # the button clicked, still to be seen gone
    tries = 0  # clicks on that same button
    while claimed < MAX_CLAIMS:
        g.move_to(atlas.BP_PARK)  # off the buttons: hover turns them lighter green
        g.sleep(600)
        buttons = _green_buttons(g)
        target = None
        if last is not None:
            same = [b for b in buttons if b[2] == last[2] and abs(b[0] - last[0]) <= SAME_X]
            if same:
                if tries >= 2:
                    g.status("Battle pass: a Claim button is still there after two clicks, leaving")
                    g.save_diagnostic("bp-claim-stays.png")
                    break
                target = same[0]
            else:
                claimed += 1
                g.status(f"Battle pass: reward {claimed} claimed")
                last, tries = None, 0
                continue  # the next look decides what comes next
        if target is None:
            if not buttons:
                if scrolled:
                    break
                g.move_to(atlas.BP_SCROLL_HOVER)
                g.sleep(300)
                g.wheel(-10)  # further milestones to the right
                g.sleep(1000)
                scrolled = True
                continue
            target, tries = buttons[0], 0
        if clicks >= MAX_CLICKS:
            break
        sx, sy, _ = target
        g.move_screen(sx, sy)
        g.sleep(800)
        g.click()
        clicks += 1
        g.sleep(2000)  # reward pop-up / tile animation
        last, tries = target, tries + 1
    return claimed


def battle_pass(g: Game) -> None:
    g.focus()
    if not bells.bell_in(g, g.ms.bp_bell):
        g.status("Battle pass: no bell on the button, nothing to claim")
        return
    g.status("Battle pass: bell found, opening the battle pass")
    g.require_screen(g.ms.bp_icon, atlas.BP_CLOSE_X, 2500)
    if g.found(atlas.BP_REWARDS_BADGE):
        g.tap(atlas.BP_REWARDS_TAB, 2500)
        claim_rewards(g)
    else:
        g.status("Battle pass: no reward badge on the Rewards tab, leaving")
    g.tap(atlas.BP_CLOSE)
    g.toast("Main Menu Check", "Checking to ensure we are on main screen after the battle pass", 2)
    main_menu(g)
