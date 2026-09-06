"""Port of Functions/OpenChests.ahk: OpenChests() and OpenBlessChests().

The AHK code is a ladder of labels with `Goto`s that fall through to the end of each rarity
group; here each group is an ordered table and the setting picks the START index. Unknown
setting values fall into the first label exactly as in AHK (e.g. GearChestExclude="Emerald"
opens every gear chest). The "Nebula and Higher" / "Cosmic and Higher" cases both jump to
Galaxy in the AHK source (probably a bug); reproduced for parity.
"""

from __future__ import annotations

from firestone_bot.features.open_chest_type import open_chest_type
from firestone_bot.features.oracles_gift import mystery_box, oracles_gift
from firestone_bot.game import Game
from firestone_bot.vision import atlas


def _open_group(g: Game, group: tuple[tuple[str, int], ...], start: int | None) -> None:
    if start is None:  # "Exclude All"
        return
    for name, color in group[start:]:
        g.toast("Open Chests", f"Opening {name} Chests", 1.5)
        open_chest_type(g, color, 1)


def _open_bag_chests_tab(g: Game) -> None:
    # open bag
    g.open_screen(g.ms.bag_icon, atlas.BAG_CLOSE_X, 1000)
    # click chests tab
    g.tap(g.ms.bag_chests_tab, 1000)


def _close_bag(g: Game, after_ms: int) -> None:
    g.tap(g.ms.bag_close, 0)
    g.sleep(after_ms)


def open_chests(g: Game) -> None:
    _open_bag_chests_tab(g)
    # Gear chests: an unknown value starts at Titan (opens all), like the AHK fall-through.
    _open_group(g, atlas.GEAR_CHESTS, atlas.GEAR_CHEST_START.get(g.settings.GearChestExclude, 0))
    # JewelChests:
    _open_group(g, atlas.JEWEL_CHESTS, atlas.JEWEL_CHEST_START.get(g.settings.JewelChestExclude, 0))
    # Gifts:
    if g.settings.flag("OracleGifts"):
        g.toast("Open Chests", "Opening Oracle Gifts", 1.5)
        oracles_gift(g)
    if g.settings.flag("MysteryBoxes"):
        g.toast("Open Chests", "Opening Mystery Boxes", 1.5)
        mystery_box(g)
    if g.settings.flag("Bless"):
        open_bless_chests(g)  # closes the bag itself
    # AHK returns WITHOUT closing the bag when Bless is off, and closed it a second time when
    # Bless was on (a click on the Town icon in classic, on the settings gear in the new style).
    # Rework: the bag is closed exactly once, whatever the Bless setting.
    else:
        _close_bag(g, 1500)


def open_bless_chests(g: Game) -> None:
    """Celestial (blessing) chests. Called from open_chests, or from the main loop when Bless is
    on and Chests is off."""
    if not g.settings.flag("Chests"):
        if not g.settings.flag("BlessingChests"):
            return
        _open_bag_chests_tab(g)
    # OpenBlessChestsNoBag:
    g.move_to(atlas.BAG_SCROLL_HOVER)
    g.toast("Open Chests", "Scrolling to ensure bottom gifts are visible", 1.5)
    g.wheel(-5)
    start = atlas.CELESTIAL_CHEST_START.get(g.settings.CelestialChestExclude, 0)
    _open_group(g, atlas.CELESTIAL_CHESTS, start)
    # CloseBag:
    _close_bag(g, 1000)
