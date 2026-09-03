"""Port of Functions/HeroUpgrade.ahk: hero / guardian / special upgrades in the U menu.

Two modes: "Next Milestone" (toggle the milestone mode, then click each upgrade while its
green marker stays, unbounded like AHK unless SafetyCap is set) and the standard single-click
mode.
"""

from __future__ import annotations

from firestone_bot.features.big_close import big_close
from firestone_bot.game import Game
from firestone_bot.vision import atlas
from firestone_bot.vision.atlas import Probe


def click_hero_if_pixel_found(g: Game, probe: Probe, click: atlas.Point) -> None:
    g.move(probe.x1, probe.y1)
    g.sleep(300)
    cap = int(g.settings.get("SafetyCap") or 0)
    n = 0
    while g.found(probe):
        g.heartbeat("HeroUpgrade: found pixel", important=True)
        g.click_point(click)  # MouseClick, Left, x, y, 1, 0
        g.sleep(300)
        n += 1
        if cap and n >= cap:
            g.status(f"HeroUpgrade: safety cap of {cap} clicks reached")
            return


def hero_upgrade(g: Game) -> None:
    g.focus()
    s = g.settings
    if s.flag("NoHero"):
        return
    # open upgrade menu
    g.toast("Hero Upgrades", "Opening Hero Upgrade Menu", 2)
    g.key("u")
    g.sleep(1500)
    if s.flag("NextMilestone"):
        # Set to Next Milestone
        count = 0
        while True:
            if g.found(atlas.HU_MILESTONE_MARKER):
                g.click_point(atlas.HU_MILESTONE_TOGGLE)
                g.sleep(300)
                break
            g.click_point(atlas.HU_MILESTONE_TOGGLE)
            g.sleep(300)
            count += 1
            if count >= 10:
                g.toast("Hero Upgrades", f"Failed to find pixel after {count} tries.", 2)
                break
        for setting, rect, click in atlas.HERO_UPGRADE_SLOTS:
            if s.flag(setting):
                probe = Probe(*rect, atlas.GREEN_BUTTON_2, 3, f"hero_{setting}")
                click_hero_if_pixel_found(g, probe, click)
    else:
        # Standard Single Check Mode
        for setting, rect, click in atlas.HERO_UPGRADE_SLOTS:
            if s.flag(setting) and g.found(Probe(*rect, atlas.GREEN_BUTTON, 3, f"hero_{setting}")):
                g.move_to(click)
                g.sleep(1000)
                g.click()
                g.sleep(1000)
    big_close(g)
