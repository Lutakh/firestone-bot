"""Claim the daily and weekly quest rewards (port of Functions/Quests.ahk).

The lock is the red bell on the Quests tab of the character page. The AHK probed a badge
on the first icon under the avatar instead, but that column of icons depends on the
account (a beer mug with "26" on the reference capture, a hammer with "5" on the owner's
level-55 account): the bot walked into the quests and clicked greyed Claim buttons
(2026-09-08). In the new style the icon column is fixed and its badge is kept as a cheap
first check; the tab bell still decides.

Every claimable quest is claimed in one visit (owner, 2026-09-10): the Claim buttons are
found by colour and the topmost is clicked until none is left; a claim shows no pop-up, the
list just re-sorts with the claimable quests first. The page is checked before each click.

NOTE: in the AHK file the function's closing brace comes BEFORE `BigClose()`, so ClaimQuests
never closed the character window itself; the main loop's following MainMenu() does.
"""

from __future__ import annotations

from firestone_bot.features.big_close import big_close
from firestone_bot.game import Game
from firestone_bot.vision import atlas, bells, blobs
from firestone_bot.vision.atlas import Point

MAX_CLAIMS_PER_TAB = 20


def claim_buttons(g: Game) -> list[blobs.Blob]:
    """The green Claim buttons of the open quest tab, top to bottom."""
    return sorted(
        blobs.find_blobs(
            g,
            atlas.QUESTS_CLAIM_COLUMN,
            atlas.GREEN_BUTTON,
            atlas.QUESTS_CLAIM_VAR,
            anchor=atlas.ANCHOR_CENTER,
            min_w=atlas.QUESTS_CLAIM_MIN_W,
            min_h=atlas.QUESTS_CLAIM_MIN_H,
        ),
        key=lambda b: b.cy,
    )


def _claim_tab(g: Game, name: str, tab: Point) -> int:
    g.tap(tab, 1000)
    g.wait_still()
    claimed = 0
    while claimed < MAX_CLAIMS_PER_TAB:
        g.move_to(atlas.QUESTS_PARK)  # a hovered button is a lighter green
        g.sleep(300)
        if not g.found(g.ms.character_close_x):
            g.status(f"Quests: the quest page is gone, {name} claims stopped")
            g.save_diagnostic(f"quests-page-lost-{name}.png")
            break
        found = claim_buttons(g)
        if not found:
            break
        top = found[0]
        g.tap(Point(top.cx, top.cy, atlas.ANCHOR_CENTER), 800)
        g.wait_still()
        claimed += 1
    g.status(
        f"Quests: {claimed} {name} reward(s) claimed"
        if claimed
        else f"Quests: nothing to claim in the {name} tab"
    )
    return claimed


def claim_quests(g: Game) -> None:
    if g.style == "new" and not g.found(g.ms.quests_badge):
        g.status("Quests: no notification badge, nothing to claim")
        return
    g.status("Quests: opening the character page")
    g.require_screen(g.ms.character_icon, g.ms.character_close_x, 1000)
    g.wait_still()
    bell = bells.has_bell(
        g,
        atlas.QUESTS_TAB_BELL,
        bells.scaled(g, bells.BELL_PIXELS),
        atlas.QUESTS_TAB_BELL_ANCHOR,
    )
    if not bell:
        g.status("Quests: no bell on the Quests tab, nothing to claim")
        big_close(g)
        return
    g.tap(atlas.QUESTS_TAB, 1000)
    _claim_tab(g, "daily", atlas.QUESTS_DAILY_TAB)
    _claim_tab(g, "weekly", atlas.QUESTS_WEEKLY_TAB)
