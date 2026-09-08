"""Claim the daily and weekly quest rewards (port of Functions/Quests.ahk).

The lock is the red bell on the Quests tab of the character page. The AHK probed a badge
on the first icon under the avatar instead, but that column of icons depends on the
account (a beer mug with "26" on the reference capture, a hammer with "5" on the owner's
level-55 account): the bot walked into the quests and clicked greyed Claim buttons
(2026-09-08). In the new style the icon column is fixed and its badge is kept as a cheap
first check; the tab bell still decides.

NOTE: in the AHK file the function's closing brace comes BEFORE `BigClose()`, so ClaimQuests
never closed the character window itself; the main loop's following MainMenu() does.
"""

from __future__ import annotations

from firestone_bot.features.big_close import big_close
from firestone_bot.game import Game
from firestone_bot.vision import atlas, bells


def _claim_tab(g: Game, name: str, tab: atlas.Point) -> None:
    g.tap(tab, 1000)
    g.wait_still()
    if not g.found(atlas.QUESTS_CLAIM_READY):
        g.status(f"Quests: nothing to claim in the {name} tab")
        return
    g.status(f"Quests: claiming the {name} reward")
    g.save_diagnostic(f"quests-claim-{name}.png")
    g.tap(atlas.QUESTS_CLAIM, 1000)
    g.tap(atlas.QUESTS_REWARD_OK, 1000)


def claim_quests(g: Game) -> None:
    if g.style == "new" and not g.found(g.ms.quests_badge):
        g.status("Quests: no notification badge, nothing to claim")
        return
    g.status("Quests: opening the character page")
    g.require_screen(g.ms.character_icon, g.ms.character_close_x, 1000)
    g.wait_still()
    if not bells.has_bell(g, atlas.QUESTS_TAB_BELL):
        g.status("Quests: no bell on the Quests tab, nothing to claim")
        big_close(g)
        return
    g.tap(atlas.QUESTS_TAB, 1000)
    _claim_tab(g, "daily", atlas.QUESTS_DAILY_TAB)
    _claim_tab(g, "weekly", atlas.QUESTS_WEEKLY_TAB)
