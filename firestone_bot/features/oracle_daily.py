"""Port of Functions/subFunctions/OracleDaily.ahk: claim the Oracle's daily gift."""

from __future__ import annotations

from firestone_bot.features.big_close import big_close
from firestone_bot.game import Game
from firestone_bot.vision import atlas


def oracle_daily(g: Game) -> None:
    # Look for oracle gift notification
    if g.found(atlas.ORACLE_GIFT_DOT):
        g.tap(atlas.ORACLE_GIFT_TAB)
        # Claim Oracle's gift
        g.tap(atlas.ORACLE_GIFT_CLAIM)
        big_close(g)
