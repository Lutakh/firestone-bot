"""Battle pass: claim the milestone rewards (owner request 2026-09-04).

Main screen: the Battle pass button (bottom left, next to Events) shows a bell when a reward
is claimable. Inside, two tabs: Challenges and Rewards; the Rewards tab carries a red badge
with the number of claimable rewards. The Rewards page scrolls horizontally by itself to the
first claimable milestone; green "Claim" buttons appear in two rows (Golden pass on top, Free
at the bottom) under the reward tiles. Buttons are found by colour inside those two rows, so
their exact x does not matter; the page is rescanned after every claim (it may shift) and
scrolled further right once when nothing is left in view.
"""

from __future__ import annotations

from firestone_bot.features.main_menu import main_menu
from firestone_bot.game import Game
from firestone_bot.platform import capture
from firestone_bot.vision import atlas
from firestone_bot.vision.probes import match_mask

MAX_CLAIMS = 30


def _green_buttons(g: Game) -> list[tuple[int, int]]:
    """Screen centres of the green Claim buttons in the two reward rows (left to right)."""
    vp = g.vp
    x1, x2 = atlas.BP_REWARD_COLUMNS
    out: list[tuple[int, int]] = []
    for y1, y2 in atlas.BP_REWARD_ROWS:
        sx1, sy1 = vp.to_screen(x1, y1)
        sx2, sy2 = vp.to_screen(x2, y2)
        rect = capture.Rect(sx1, sy1, sx2 - sx1, sy2 - sy1)
        img = capture.grab(rect)
        cols = match_mask(img, atlas.GREEN_BUTTON, 3).any(axis=0)
        # runs of green columns wider than half a button are buttons
        start = None
        for x, on in enumerate(list(cols) + [False]):
            if on and start is None:
                start = x
            elif not on and start is not None:
                if x - start >= 80:
                    out.append((rect.x + (start + x) // 2, rect.y + rect.h // 2))
                start = None
    return out


def claim_rewards(g: Game) -> int:
    """Rewards tab must be open. Claims every green button, rescanning after each click."""
    claimed = 0
    scrolled = False
    while claimed < MAX_CLAIMS:
        g.move_to(atlas.BP_PARK)  # off the buttons: hover turns them lighter green
        g.sleep(600)
        buttons = _green_buttons(g)
        if not buttons:
            if scrolled:
                break
            g.move_to(atlas.BP_SCROLL_HOVER)
            g.sleep(300)
            g.wheel(-10)  # further milestones to the right
            g.sleep(1000)
            scrolled = True
            continue
        sx, sy = buttons[0]
        g.move_screen(sx, sy)
        g.sleep(800)
        g.click()
        g.sleep(2000)  # reward pop-up / tile animation
        claimed += 1
        g.status(f"Battle pass: reward {claimed} claimed")
    return claimed


def battle_pass(g: Game) -> None:
    g.focus()
    if not g.found(g.ms.bp_bell):
        return
    g.open_screen(g.ms.bp_icon, atlas.BP_CLOSE_X, 2500)
    if g.found(atlas.BP_REWARDS_BADGE):
        g.tap(atlas.BP_REWARDS_TAB, 2500)
        claim_rewards(g)
    else:
        g.status("Battle pass: no reward badge on the Rewards tab, leaving")
    g.tap(atlas.BP_CLOSE)
    g.toast("Main Menu Check", "Checking to ensure we are on main screen after the battle pass", 2)
    main_menu(g)
