"""Main-screen layouts: the classic interface and the "new adventure style" (2026-09-05).

Only the main screen differs between the two styles (HUD icon positions and the hero upgrade
row); dialogs, town, guild and map are the same. `detect_style` looks for the blue "Upgrade"
mode button of the new style at the bottom right of the main screen.
"""

from __future__ import annotations

from dataclasses import dataclass

from firestone_bot.vision import atlas
from firestone_bot.vision.atlas import Point, Probe

STYLES = ("auto", "classic", "new")


@dataclass(frozen=True)
class MainScreen:
    name: str
    mail_icon: Point
    events_icon: Point
    events_bell: Probe
    bp_icon: Point
    bp_bell: Probe
    shop_icon: Point
    shop_bell: Probe
    guild_icon: Point
    bag_icon: Point
    bag_close: Point
    bag_close_x: Probe  # entry probe of the bag panel (its close button's orange ring)
    bag_chests_tab: Point
    chest_grid: tuple[int, int, int, int]
    chest_dialog_close: Point | None  # None: BigClose + failsafe (classic)
    character_icon: Point
    quests_badge: Probe  # red badge on the quests icon: nothing to claim without it


CLASSIC = MainScreen(
    "classic",
    mail_icon=atlas.MAIL_ICON,
    events_icon=atlas.EVENTS_ICON,
    events_bell=atlas.EVENTS_BELL,
    bp_icon=atlas.BP_ICON,
    bp_bell=atlas.BP_BELL,
    shop_icon=atlas.SHOP_ICON,
    shop_bell=atlas.SHOP_RED_DOT,
    guild_icon=atlas.MAIN_GUILD_ICON,
    bag_icon=atlas.BAG_ICON,
    bag_close=atlas.BAG_CLOSE,
    bag_close_x=atlas.BAG_CLOSE_X_CLASSIC,
    bag_chests_tab=atlas.BAG_CHESTS_TAB,
    chest_grid=atlas.CHEST_GRID,
    chest_dialog_close=None,
    character_icon=atlas.CHARACTER_ICON,
    quests_badge=atlas.QUESTS_BADGE,
)

NEW = MainScreen(
    "new",
    mail_icon=atlas.NS_MAIL_ICON,
    events_icon=atlas.NS_EVENTS_ICON,
    events_bell=atlas.NS_EVENTS_BELL,
    bp_icon=atlas.NS_BP_ICON,
    bp_bell=atlas.NS_BP_BELL,
    shop_icon=atlas.NS_SHOP_ICON,
    shop_bell=atlas.NS_SHOP_BELL,
    guild_icon=atlas.NS_GUILD_ICON,
    bag_icon=atlas.NS_BAG_ICON,
    bag_close=atlas.NS_BAG_CLOSE,
    bag_close_x=atlas.BAG_CLOSE_X,
    bag_chests_tab=atlas.NS_BAG_CHESTS_TAB,
    chest_grid=atlas.NS_CHEST_GRID,
    chest_dialog_close=atlas.NS_CHEST_DIALOG_CLOSE,
    character_icon=atlas.CHARACTER_ICON,
    quests_badge=atlas.NS_QUESTS_BADGE,
)

BY_NAME = {"classic": CLASSIC, "new": NEW}


def detect_style(g, setting: str = "auto") -> str:
    """'classic' or 'new'. The setting forces a style; auto probes the main screen (the game
    must be on the main screen: the blue mode button is only there)."""
    setting = (setting or "auto").strip().lower()
    if setting in BY_NAME:
        return setting
    return "new" if g.found(atlas.NS_STYLE_PROBE) else "classic"
