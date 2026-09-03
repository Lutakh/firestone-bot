"""Port of Functions/Shop.ahk: claim the mystery box and the daily check-in when the shop has
a red notification dot."""

from __future__ import annotations

from firestone_bot.features.big_close import big_close
from firestone_bot.features.main_menu import main_menu
from firestone_bot.game import Game
from firestone_bot.vision import atlas


def shop(g: Game) -> None:
    g.focus()
    if not g.found(atlas.SHOP_RED_DOT):
        return
    g.move_to(atlas.SHOP_ICON)
    g.sleep(1000)
    g.click()
    g.sleep(1500)
    # claim mystery box
    g.move_to(atlas.SHOP_MYSTERY_BOX)
    g.sleep(1000)
    g.click()
    g.sleep(1000)
    # open daily check-in
    g.move_to(atlas.SHOP_CHECKIN_TAB)
    g.sleep(1000)
    g.click()
    g.sleep(1000)
    # check in
    g.move_to(atlas.SHOP_CHECKIN_CLAIM)
    g.sleep(3000)
    g.click()
    g.sleep(1000)
    g.move_to(atlas.SHOP_CHECKIN_OK)
    g.sleep(3000)
    g.click()
    g.sleep(1000)
    big_close(g)
    g.toast(
        "Main Menu Check", "Checking to ensure we are on main screen after redeeming shop gifts", 2
    )
    main_menu(g)
