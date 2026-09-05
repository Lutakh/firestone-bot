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


def _mode_signature(g: Game, rect, light_text: bool):
    img = g.region_image(rect).astype(int)
    mask = (img.min(axis=2) > 200) if light_text else (img.max(axis=2) < 120)
    cols = mask.sum(axis=0)
    n = int(cols.sum())
    if n < 300:
        return None
    buckets = np.add.reduceat(cols, np.arange(0, cols.shape[0], 10))
    xs = np.nonzero(cols)[0]
    return n, (int(xs.min()), int(xs.max())), buckets / n


def read_upgrade_mode(g: Game) -> str:
    """Current state of the mode button ('x1', 'x10', 'x100', 'next', 'max' or 'unknown').

    Classic style: dark text on the beige button of the U menu. New style: white text on the
    blue button of the main screen. Both use a column profile of the text pixels compared with
    references recorded live."""
    if g.style == "new":
        sig = _mode_signature(g, atlas.NS_MODE_TEXT, light_text=True)
        refs = {k: (v[0], v[1], v[2]) for k, v in atlas.NS_MODE_SIGNATURES.items()}
    else:
        sig = _mode_signature(g, atlas.HU_MODE_TEXT, light_text=False)
        refs = {k: (v[0], v[1], None) for k, v in atlas.HU_MODE_SIGNATURES.items()}
    if sig is None:
        return "unknown"
    n, extent, profile = sig
    best, best_d = "unknown", 9.0
    for name, (ref_extent, ref_profile, ref_n) in refs.items():
        ref = np.array(ref_profile[: len(profile)])
        d = float(np.abs(profile[: len(ref)] - ref).sum())
        d += (abs(extent[0] - ref_extent[0]) + abs(extent[1] - ref_extent[1])) / 100
        if ref_n:
            d += abs(n - ref_n) / 1000
        if d < best_d:
            best, best_d = name, d
    return best if best_d < 0.35 else "unknown"


def set_next_milestone(g: Game) -> bool:
    """Click the mode button until it shows "Next milestone", whatever its current state."""
    toggle = atlas.NS_MODE_BUTTON if g.style == "new" else atlas.HU_MILESTONE_TOGGLE
    park = atlas.NS_MODE_PARK if g.style == "new" else atlas.HU_MODE_PARK
    for _attempt in range(3):
        g.move_to(park)
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
            g.move_to(toggle)
            g.sleep(400)
            g.click()
            g.sleep(500)
    g.toast("Hero Upgrades", "Could not set the Next milestone mode", 2)
    return False


def hero_upgrade_new_style(g: Game) -> None:
    """New adventure style: the hero row is on the main screen (no U menu). An orange card is
    upgradable; with Next milestone on, one click per card buys up to the milestone, otherwise
    one click buys one level (like the AHK x1 pass)."""
    s = g.settings
    if s.flag("NextMilestone"):
        set_next_milestone(g)
    cap = int(s.get("SafetyCap") or 0)
    for setting, probe, click in atlas.NS_HERO_CARDS:
        if not s.flag(setting):
            continue
        n = 0
        while g.found(probe):
            g.move_to(click)
            g.sleep(600)
            g.click()
            g.sleep(800)
            g.move_to(atlas.NS_MODE_PARK)
            g.sleep(400)
            n += 1
            if not s.flag("NextMilestone") or (cap and n >= cap) or n >= 60:
                break
        if n:
            g.status(f"Hero Upgrades: {setting} clicked {n} time(s)")


def hero_upgrade(g: Game) -> None:
    g.focus()
    s = g.settings
    if s.flag("NoHero"):
        return
    if g.style == "new":
        g.toast("Hero Upgrades", "Upgrading heroes from the main-screen row", 1)
        hero_upgrade_new_style(g)
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
