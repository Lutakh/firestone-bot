"""Port of Functions/subFunctions/ScarabToken.ahk: claim the Pharaoh's token in the tavern.

Reworked 2026-09-10 (the token was never claimed):
- the bell on the tavern's "Scarab's game" card was probed at an unanchored AHK rect that
  the thirds rule put beside it, so the step stopped there every cycle: it is now a
  centre-anchored rect read by red-pixel count;
- the free token sits in the scarab Market next to a paid pass, so it is claimed only
  through a green button found inside the free card, and the claim is checked afterwards.
"""

from __future__ import annotations

from firestone_bot.features.big_close import big_close
from firestone_bot.game import Game
from firestone_bot.vision import atlas, bells, blobs
from firestone_bot.vision.atlas import Point


def free_button(g: Game) -> blobs.Blob | None:
    """The green "Free" button of the daily token card, or None (claimed, or not there)."""
    found = blobs.find_blobs(
        g,
        atlas.SCARAB_FREE_CARD,
        atlas.GREEN_BUTTON,
        atlas.SCARAB_FREE_VAR,
        anchor=atlas.ANCHOR_CENTER,
        min_w=atlas.SCARAB_FREE_MIN_W,
        min_h=atlas.SCARAB_FREE_MIN_H,
    )
    return max(found, key=lambda b: b.w * b.h) if found else None


def claim_free_token(g: Game) -> bool:
    """Scarab Market open: click the free token's green button, True when it is gone after."""
    g.move_to(Point(960, 1040, atlas.ANCHOR_CENTER))  # a hovered button is a lighter green
    g.sleep(300)
    b = free_button(g)
    if b is None:
        g.status("Scarab's Token: no free token to claim in the market")
        return False
    g.tap(Point(b.cx, b.cy, atlas.ANCHOR_CENTER), 1000)
    g.wait_still()
    g.move_to(Point(960, 1040, atlas.ANCHOR_CENTER))
    g.sleep(300)
    if free_button(g) is not None:
        g.status("Scarab's Token: the Free button is still there after the click")
        g.save_diagnostic("scarab-token-miss.png")
        return False
    g.status("Scarab's Token: Pharaoh's token claimed")
    return True


def scarab_token(g: Game) -> None:
    if not g.settings.flag("ScarabTokenClaim"):
        return
    g.toast("Scarab's Token", "Claiming Scarab's Token", 2)
    g.focus()
    # open Tavern
    g.require_screen(atlas.TOWN_TAVERN, atlas.TAVERN_CLOSE_X, 1000, via_town=True)
    if not bells.bell_in(g, atlas.SCARAB_GAME_DOT):
        g.status("Scarab's Token: no bell on the Scarab's game, nothing to claim")
        big_close(g)
        return
    # Open Scarab's Game
    g.tap(atlas.TAVERN_SCARAB_TAB, 1000)
    if g.found(atlas.SCARAB_TOKEN_DOT):
        g.tap(atlas.SCARAB_TOKEN_TAB)  # the market, on its Monthly pass page
        claim_free_token(g)
        big_close(g)
    else:
        g.status("Scarab's Token: no bell on the market, nothing to claim")
    big_close(g)
