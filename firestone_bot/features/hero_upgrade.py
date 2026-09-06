"""Port of Functions/HeroUpgrade.ahk: hero / guardian / special upgrades in the U menu.

Two modes: "Next Milestone" (toggle the milestone mode, then click each upgrade while its
green marker stays, unbounded like AHK unless SafetyCap is set) and the standard single-click
mode.
"""

from __future__ import annotations

import logging

import numpy as np

from firestone_bot.features.big_close import big_close
from firestone_bot.game import Game
from firestone_bot.vision import atlas
from firestone_bot.vision.atlas import Point, Probe

log = logging.getLogger("firestone_bot.hero_upgrade")


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


MODE_BIN = 10  # column profile of the label: one bin per 10 logical px of the text rect


def _ref_signature(ref, width: int):
    """A recorded (extent, profile) brought to the bins of a `width` logical px rect.

    The classic-style references were recorded in capture pixels (10 px buckets on the
    owner's screen): a profile with another bin count is resampled and its extent scaled."""
    extent, profile = ref
    bins = width // MODE_BIN
    profile = np.array(profile, dtype=float)
    if len(profile) == bins:
        return extent, profile
    f = width / (len(profile) * MODE_BIN)  # logical px per recorded bucket px
    src = (np.arange(len(profile)) + 0.5) * f * MODE_BIN
    dst = (np.arange(bins) + 0.5) * MODE_BIN
    resampled = np.interp(dst, src, profile)
    resampled /= resampled.sum() or 1.0
    return (int(extent[0] * f), int(extent[1] * f)), resampled


def _mode_signature(g: Game, rect, light_text: bool):
    """(extent, profile) of the last text line in `rect`, in logical units.

    The label of the new-style button wraps on two lines ("Upgrade" / "x10", "Next" /
    "milestone"): only the last line tells the modes apart. `extent` is the first and last
    text column in logical px from the rect's left edge, `profile` the share of text pixels
    per 10 logical px bin, so the reference recorded on one screen size holds on others."""
    img = g.region_image(rect).astype(int)
    mask = (img.min(axis=2) > 200) if light_text else (img.max(axis=2) < 120)
    rows = np.nonzero(mask.sum(axis=1) > 0)[0]
    if len(rows) == 0:
        return None
    # last group of consecutive text rows (gaps of 3+ empty rows separate the lines)
    breaks = np.nonzero(np.diff(rows) > 3)[0]
    first = rows[breaks[-1] + 1] if len(breaks) else rows[0]
    cols = mask[first : rows[-1] + 1].sum(axis=0)
    n = int(cols.sum())
    if n < 100:
        return None
    f = (rect[2] - rect[0]) / cols.shape[0]  # logical px per capture column
    xs = np.nonzero(cols)[0]
    extent = (int(xs.min() * f), int(xs.max() * f))
    nbins = (rect[2] - rect[0]) // MODE_BIN
    bins = np.clip((np.arange(cols.shape[0]) * f / MODE_BIN).astype(int), 0, nbins - 1)
    profile = np.bincount(bins, weights=cols, minlength=nbins) / n
    return extent, profile


def find_mode_button(g: Game) -> Point:
    """Centre of the blue mode button of the new-style main screen.

    Its place depends on the account (2026-09-06: 80 logical px right of the 09-05 measure
    on a level 36 account, "Upgrade max" on two lines), so look for the blue rectangle in
    the bottom-right corner; NS_MODE_BUTTON is the fallback when nothing blue is there."""
    x1, y1, x2, y2 = atlas.NS_MODE_SEARCH
    img = g.region_image((x1, y1, x2, y2)).astype(int)
    b, gr, r = img[:, :, 0], img[:, :, 1], img[:, :, 2]
    blue = (b > 200) & (r < 80) & (gr > 100) & (gr < 180)
    rows = np.nonzero(blue.sum(axis=1) > blue.shape[1] * 0.25)[0]
    cols = np.nonzero(blue.sum(axis=0) > blue.shape[0] * 0.25)[0]
    if len(rows) < 10 or len(cols) < 10:
        return atlas.NS_MODE_BUTTON
    vp = g.vp
    sx, sy = vp.to_screen(x1, y1)
    cx = sx + (cols.min() + cols.max()) / 2
    cy = sy + (rows.min() + rows.max()) / 2
    lx, ly = vp.to_logical(cx, cy)
    return Point(lx, ly)


def mode_text_rect(g: Game) -> tuple[int, int, int, int]:
    """The label rect (NS_MODE_TEXT shape) centred on the button found on screen."""
    c = find_mode_button(g)
    x1, y1, x2, y2 = atlas.NS_MODE_TEXT
    hw, hh = (x2 - x1) // 2, (y2 - y1) // 2
    return c.x - hw, c.y - hh, c.x + hw, c.y + hh


def read_upgrade_mode(g: Game) -> str:
    """Current state of the mode button ('x1', 'x10', 'x100', 'next', 'max' or 'unknown').

    Classic style: dark text on the beige button of the U menu. New style: white text on the
    blue button of the main screen. Both compare the column profile of the label's last line
    with references recorded live (logical units, see _mode_signature)."""
    if g.style == "new":
        rect = mode_text_rect(g)
        sig = _mode_signature(g, rect, light_text=True)
        refs = atlas.NS_MODE_SIGNATURES
    else:
        rect = atlas.HU_MODE_TEXT
        sig = _mode_signature(g, rect, light_text=False)
        refs = atlas.HU_MODE_SIGNATURES
    if sig is None:
        return "unknown"
    extent, profile = sig
    best, best_d = "unknown", 9.0
    for name, ref in refs.items():
        ref_extent, ref_profile = _ref_signature(ref, rect[2] - rect[0])
        d = float(np.abs(profile - ref_profile).sum())
        d += (abs(extent[0] - ref_extent[0]) + abs(extent[1] - ref_extent[1])) / 100
        if d < best_d:
            best, best_d = name, d
    return best if best_d < 0.35 else "unknown"


def set_next_milestone(g: Game) -> bool:
    """Click the mode button until it shows "Next milestone", whatever its current state."""
    toggle = find_mode_button(g) if g.style == "new" else atlas.HU_MILESTONE_TOGGLE
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
    _save_mode_diagnostic(g)
    g.toast("Hero Upgrades", "Could not set the Next milestone mode", 2)
    return False


def _save_mode_diagnostic(g: Game) -> None:
    """Keep the label region of an unreadable mode button next to the settings
    (hero-mode-miss.png) so the references can be extended from a real screen."""
    import os

    from firestone_bot.platform import capture

    try:
        rect = mode_text_rect(g) if g.style == "new" else atlas.HU_MODE_TEXT
        folder = os.path.dirname(os.path.abspath(g.map_state_path))
        capture.save_png(g.region_image(rect), os.path.join(folder, "hero-mode-miss.png"))
    except Exception:
        log.debug("mode diagnostic not saved", exc_info=True)


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
                g.tap(click, 1000)
    big_close(g)
