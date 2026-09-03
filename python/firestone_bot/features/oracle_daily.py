"""Port of Functions/subFunctions/OracleDaily.ahk: claim the Oracle's daily gift."""

from __future__ import annotations

from firestone_bot.features.big_close import big_close
from firestone_bot.game import Game
from firestone_bot.vision import atlas


def oracle_daily(g: Game) -> None:
    # Look for oracle gift notification
    if g.found(atlas.ORACLE_GIFT_DOT):
        g.move_to(atlas.ORACLE_GIFT_TAB)
        g.sleep(1000)
        g.click()
        g.sleep(1500)
        # Claim Oracle's gift
        g.move_to(atlas.ORACLE_GIFT_CLAIM)
        g.sleep(1000)
        g.click()
        g.sleep(1500)
        big_close(g)
