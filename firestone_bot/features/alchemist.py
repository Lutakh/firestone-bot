"""Port of Functions/Alchemist.ahk: collect finished experiments, complete free ones, start
Dragon Blood / Strange Dust (and Exotic Coins when enabled)."""

from __future__ import annotations

from firestone_bot.features.big_close import big_close
from firestone_bot.game import Game
from firestone_bot.vision import atlas


def alchemist(g: Game) -> None:
    g.focus()
    # open Alchemist
    g.tap(atlas.TOWN_ALCHEMIST)
    # collect completed experiments (only when the slot is running)
    collect = g.settings.flag("AlchCollect")
    for slot in atlas.ALCHEMY_SLOTS if collect else ():
        if g.found(slot.not_running):
            g.toast("Alchemy Status", f"{slot.name} alchemy is not running", 1.5)
        elif g.found(slot.complete):
            g.move_to(slot.collect)
            g.toast("Alchemy Status", f"{slot.name} experiment is complete", 1.5)
            g.click()
            g.sleep(1000)
    # free to complete
    for slot in atlas.ALCHEMY_SLOTS if collect else ():
        if g.found(slot.free):
            g.move_to(slot.collect)
            g.toast("Alchemy Status", f"{slot.name} experiment is free to complete", 1.5)
            g.click()
            g.sleep(1000)
    blood, dust, coin = atlas.ALCHEMY_SLOTS
    # check if don't use Dragon Blood is checked
    if not g.settings.flag("DragonBlood"):
        _start(g, blood)
    # DustSearch:
    if not g.settings.flag("Dust"):
        _start(g, dust)
    # ExoticCheck:
    if g.settings.flag("Coin"):
        _start(g, coin)
    # FinishAlch:
    big_close(g)


def _start(g: Game, slot: atlas.AlchemySlot) -> None:
    if g.found(slot.in_progress):
        g.toast("Alchemy Status", f"{slot.name} experiment has more than 3 minutes remaining", 1.5)
    else:
        g.move_to(slot.start)
        g.toast("Alchemy Status", f"Starting {slot.name} experiment", 1.5)
        g.click()
        g.sleep(1000)
