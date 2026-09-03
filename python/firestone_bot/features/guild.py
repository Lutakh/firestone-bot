"""Port of Functions/Guild.ahk: expeditions, awaken, chaos rift, pickaxes, crystal, personal
tree, notifications."""

from __future__ import annotations

from firestone_bot.features.awaken import awaken_run
from firestone_bot.features.big_close import big_close
from firestone_bot.features.chaos import hit_chaos
from firestone_bot.features.ptree import personal_tree
from firestone_bot.game import Game
from firestone_bot.vision import atlas


def guild(g: Game) -> None:
    g.focus()
    # open guild
    g.move_to(atlas.MAIN_GUILD_ICON)
    g.sleep(1000)
    g.click()
    g.sleep(1500)
    # check if expeditions are ready
    if g.found(atlas.GUILD_EXPEDITION_DOT):
        g.heartbeat("Guild expedition start", important=True)
        g.move_to(atlas.GUILD_EXPEDITIONS)
        g.sleep(1000)
        g.click()
        g.sleep(1500)
        g.move_to(atlas.GUILD_EXPEDITION_START)
        g.sleep(1000)
        g.click()
        g.sleep(1500)
        g.click()
        g.sleep(1000)
        big_close(g)
    if g.settings.flag("Awaken"):
        awaken_run(g)
    if g.settings.flag("Chaos"):
        hit_chaos(g)
    if not g.settings.flag("Pickaxes"):
        claim_axes(g)
    # CrystalHit:
    if g.settings.flag("Crystal"):
        hit_crystal(g)
    if g.settings.flag("PTree"):
        g.move_to(atlas.GUILD_PTREE_ENTRY)
        g.sleep(1000)
        g.click()
        g.sleep(1500)
        personal_tree(g)
    if g.settings.flag("GNotif"):
        clear_notifications(g)
    big_close(g)


def claim_axes(g: Game) -> None:
    # Guild Shop
    g.move_to(atlas.GUILD_SHOP)
    g.sleep(1000)
    g.click()
    g.sleep(1500)
    # Supplies
    g.move_to(atlas.GUILD_SHOP_SUPPLIES)
    g.sleep(1000)
    g.click()
    g.sleep(1500)
    if g.found(atlas.GUILD_AXE_READY):
        g.heartbeat("ClaimAxe", important=True)
        g.move_to(atlas.GUILD_AXE_CLAIM)
        g.sleep(1000)
        g.click()
        g.sleep(1500)
    big_close(g)


def hit_crystal(g: Game) -> None:
    g.move_to(atlas.GUILD_CRYSTAL)
    g.sleep(1000)
    g.click()
    g.sleep(1500)
    if g.found(atlas.GUILD_CRYSTAL_HIT_READY):
        g.heartbeat("HitCrystal", important=True)
        g.move_to(atlas.GUILD_CRYSTAL_HIT)
        g.sleep(1000)
        g.click()
        g.sleep(1500)
    big_close(g)


def clear_notifications(g: Game) -> None:
    g.move_to(atlas.GUILD_NOTIF_1)
    g.sleep(1000)
    g.click()
    g.sleep(1500)
    big_close(g)
    g.move_to(atlas.GUILD_NOTIF_2)
    g.sleep(1000)
    g.click()
    g.sleep(1500)
    big_close(g)
