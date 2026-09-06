"""Port of Functions/Guild.ahk: expeditions, awaken, chaos rift, pickaxes, crystal, personal
tree, notifications."""

from __future__ import annotations

import logging

from firestone_bot import daily
from firestone_bot.features.awaken import awaken_run
from firestone_bot.features.big_close import big_close
from firestone_bot.features.chaos import hit_chaos
from firestone_bot.features.ptree import personal_tree
from firestone_bot.game import Game
from firestone_bot.vision import atlas

log = logging.getLogger("firestone_bot")


def guild(g: Game) -> None:
    g.focus()
    # open guild
    g.move_to(g.ms.guild_icon)
    g.sleep(1000)
    g.click()
    g.sleep(1500)
    _guild_level_check(g)
    # check if expeditions are ready
    if g.settings.flag("GuildExpedition") and g.found(atlas.GUILD_EXPEDITION_DOT):
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
    if g.settings.flag("Awaken") and not g.locked("guild_awaken"):
        awaken_run(g)
    if g.settings.flag("Chaos") and not g.locked("guild_chaos"):
        hit_chaos(g)
    if not g.settings.flag("Pickaxes"):
        claim_axes(g)
    # CrystalHit:
    if g.settings.flag("Crystal") and not g.locked("guild_crystal"):
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


def _guild_level_check(g: Game) -> bool:
    """Read "Guild level N" on the guild map (progress.py); skipped once the guild reached
    the level that unlocks everything. The banner can take a moment after the town closes
    (a live cycle missed it once at 1.5 s, 2026-09-06), so the read is retried. An
    unreadable banner never gates anything: the guild features run as they always did."""
    if g.progress is None or not g.progress.need_guild_check():
        return True
    level = None
    for _ in range(GUILD_LEVEL_READ_TRIES):
        level = g.read_number(atlas.GUILD_LEVEL_REGION, last_word=True)
        if level is not None:
            break
        g.sleep(1000)
    g.progress.set_guild_level(level)
    if level is None:
        g.status("Guild level: banner not readable (not in a guild?), guild features run as usual")
        _save_diagnostic(g, "guild-banner-miss.png")
    else:
        g.status(f"Guild level {level}")
    return True


GUILD_LEVEL_READ_TRIES = 3


def _save_diagnostic(g: Game, name: str) -> None:
    """Capture of the game client next to the user files, to see what the bot saw."""
    import os

    from firestone_bot.platform import capture

    try:
        if g.window is None or g.dry_run:
            return
        path = os.path.join(os.path.dirname(os.path.abspath(g.map_state_path)), name)
        capture.save_png(capture.grab(g.window.client), path)
        g.status(f"Guild level: capture saved as {name}")
    except Exception:
        log.debug("diagnostic capture failed", exc_info=True)


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


MAX_CRYSTAL_HITS_PER_VISIT = 60  # safety when MaxCrystals is 0 (unlimited)


def hit_crystal(g: Game) -> None:
    """Spend pickaxes on the arcane crystal, all of today's allowance in one visit.

    Python-only daily limit (MaxCrystals, default 5; CrystalCountDaily cleared by the daily
    reset): the AHK bot hit once per cycle. Once the limit is reached the crystal is not
    opened again until the next reset.
    """
    if daily.crystal_left(g.settings) == 0:
        return
    g.move_to(atlas.GUILD_CRYSTAL)
    g.sleep(1000)
    g.click()
    g.sleep(1500)
    hits = 0
    while hits < MAX_CRYSTAL_HITS_PER_VISIT and daily.crystal_left(g.settings) != 0:
        g.move_to(atlas.GUILD_CRYSTAL_PARK)  # off the button: hover would lighten it
        g.sleep(500)
        if not g.found(atlas.GUILD_CRYSTAL_HIT_READY):
            break
        g.heartbeat("HitCrystal", important=True)
        before = g.region_image(atlas.GUILD_PICKAXE_COUNTER)
        g.move_to(atlas.GUILD_CRYSTAL_HIT)
        g.sleep(1000)
        g.click()
        g.sleep(500)
        g.move_to(atlas.GUILD_CRYSTAL_PARK)
        if not g.wait_region_change(atlas.GUILD_PICKAXE_COUNTER, before):
            # the hit animation swallows clicks: the counter did not move, do not count it
            g.status("Crystal: the pickaxe counter did not change, leaving")
            break
        g.sleep(1500)
        daily.note_crystal_hit(g.settings)
        hits += 1
        g.status(f"Crystal: hit {hits} ({g.settings.CrystalCountDaily} today)")
    if daily.crystal_left(g.settings) == 0:
        g.status(f"Crystal: daily limit reached ({g.settings.MaxCrystals})")
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
