"""Port of Functions/HeroUpgrade.ahk: hero / guardian / special upgrades in the U menu.

Two modes: "Next Milestone" (toggle the milestone mode, then click each upgrade while its
green marker stays, unbounded like AHK unless SafetyCap is set) and the standard single-click
mode.
"""

from __future__ import annotations

import numpy as np

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


def read_upgrade_mode(g: Game) -> str:
    """Current state of the mode button ('x1', 'x10', 'x100', 'next', 'max' or 'unknown')."""
    img = g.region_image(atlas.HU_MODE_TEXT).astype(int)
    dark = img.max(axis=2) < 120
    cols = dark.sum(axis=0)
    n = int(cols.sum())
    if n < 300:
        return "unknown"
    width = cols.shape[0]
    buckets = np.add.reduceat(cols, np.arange(0, width, 10))[:24]
    profile = buckets / n
    xs = np.nonzero(cols)[0]
    extent = (int(xs.min()), int(xs.max()))
    best, best_d = "unknown", 9.0
    for name, (ref_extent, ref_profile) in atlas.HU_MODE_SIGNATURES.items():
        ref = np.array(ref_profile[: len(profile)])
        d = float(np.abs(profile[: len(ref)] - ref).sum())
        d += (abs(extent[0] - ref_extent[0]) + abs(extent[1] - ref_extent[1])) / 100
        if d < best_d:
            best, best_d = name, d
    return best if best_d < 0.35 else "unknown"


def set_next_milestone(g: Game) -> bool:
    """Click the mode button until it shows "Next milestone", whatever its current state."""
    for _attempt in range(3):
        g.move_to(atlas.HU_MODE_PARK)
        g.sleep(400)
        state = read_upgrade_mode(g)
        if state == "next":
            return True
        if state == "unknown":
            clicks = 1
        else:
            clicks = (atlas.HU_MODE_ORDER.index("next") - atlas.HU_MODE_ORDER.index(state)) % 5
        g.status(f"Hero Upgrades: mode button shows {state}, clicking {clicks} time(s)")
        for _ in range(clicks):
            g.move_to(atlas.HU_MILESTONE_TOGGLE)
            g.sleep(400)
            g.click()
            g.sleep(500)
    g.toast("Hero Upgrades", "Could not set the Next milestone mode", 2)
    return False


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
        # Rework: read the mode button's label and click to "Next milestone" from any state
        # (the AHK marker-pixel loop only worked when starting from x1).
        set_next_milestone(g)
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
