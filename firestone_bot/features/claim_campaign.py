"""Port of Functions/subFunctions/ClaimCampaign.ahk: campaign coins/tokens, then liberation."""

from __future__ import annotations

from firestone_bot.features.big_close import big_close
from firestone_bot.features.liberation_missions import liberation_missions
from firestone_bot.game import Game
from firestone_bot.vision import atlas


def claim_campaign(g: Game) -> None:
    g.focus()
    g.tap(atlas.CAMPAIGN_ICON, 1000)
    # failsafe in case player doesn't have engineer unlocked
    if g.found(atlas.CAMPAIGN_LOCKED):
        big_close(g)
        big_close(g)
        return
    if g.found(atlas.CAMPAIGN_CLAIM_READY):
        g.tap(atlas.CAMPAIGN_CLAIM, 1000)
    if g.settings.flag("Liberation"):
        liberation_missions(g)
    big_close(g)
