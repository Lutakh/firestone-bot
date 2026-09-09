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
    # The loot button is at the very bottom left of the campaign map, i.e. under the overlay
    # panel (placed bottom-left when it is capture-safe). Verified live at 2560x1302 with the
    # panel over it, 2026-09-09: the probe reads through it (the panel is left out of the
    # captures) and the click goes through it (macOS click-through), the loot was claimed.
    # Said out loud so that a next "the claim does not work" can be told apart from a loot
    # that was simply not ready yet (it fills over 6 h).
    if g.found(atlas.CAMPAIGN_CLAIM_READY):
        g.status("Campaign: claiming the war machine loot")
        g.tap(atlas.CAMPAIGN_CLAIM, 1000)
    else:
        g.status("Campaign: no loot to claim yet")
    if g.settings.flag("Liberation"):
        liberation_missions(g)
    big_close(g)
