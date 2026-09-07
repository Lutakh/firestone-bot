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
    chest_open_buttons: tuple  # (probe, button) largest first, in the chest dialog
    chest_result_ready: tuple[Probe, ...]  # any of them: the opening animation ended
    chest_open_more: Point  # x50 on the result screen
    chest_open_more_ready: Probe
    chest_result_close: Point | None  # None: the result screen closes like the dialog
    character_icon: Point
    character_close_x: Probe  # entry probe of the character page (its X)
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
    chest_open_buttons=atlas.CHEST_OPEN_BUTTONS,
    chest_result_ready=(),
    chest_open_more=atlas.CHEST_OPEN_MORE,
    chest_open_more_ready=atlas.CHEST_OPEN_MORE_READY,
    chest_result_close=None,
    character_icon=atlas.CHARACTER_ICON,
    character_close_x=atlas.CHARACTER_CLOSE_X,
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
    chest_open_buttons=atlas.NS_CHEST_OPEN_BUTTONS,
    chest_result_ready=(atlas.NS_CHEST_RESULT_OPEN_MORE_READY, atlas.NS_CHEST_RESULT_CLOSE_X),
    chest_open_more=atlas.NS_CHEST_RESULT_OPEN_MORE,
    chest_open_more_ready=atlas.NS_CHEST_RESULT_OPEN_MORE_READY,
    chest_result_close=atlas.NS_CHEST_RESULT_CLOSE,
    character_icon=atlas.CHARACTER_ICON,
    character_close_x=atlas.CHARACTER_CLOSE_X,
    quests_badge=atlas.NS_QUESTS_BADGE,
)

BY_NAME = {"classic": CLASSIC, "new": NEW}


def on_new_main_screen(g) -> bool:
    """New style: the blue mode button is there AND its label reads as one of the five upgrade
    modes. The blue alone also matches the sea of the town screen and the blue buttons of
    the scarab game (2026-09-07: BigClose skipped inside the tavern, dialogs left open)."""
    from firestone_bot.features.hero_upgrade import find_mode_button, read_upgrade_mode

    if not (g.found(atlas.NS_STYLE_PROBE) or g.found(atlas.NS_STYLE_PROBE_HOVER)):
        return False
    # the tavern's blue "x1" multiplier sits higher on the screen (its label would pass)
    if abs(find_mode_button(g).y - atlas.NS_MODE_BUTTON.y) > 30:
        return False
    return read_upgrade_mode(g) in atlas.HU_MODE_ORDER


def detect_style(g, setting: str = "auto", previous: str | None = None) -> str:
    """'classic' or 'new'. The setting forces a style; auto probes the main screen (the game
    must be on the main screen: the blue mode button is only there).

    The pointer is moved off the button first (hovered, it turns lighter and the probe
    missed: a whole run went on in the classic layout, 2026-09-06), the hovered colour is
    accepted too, and a miss keeps `previous` when one is known: the style does not change
    between two cycles, a miss is a pop-up or an animation over the button."""
    setting = (setting or "auto").strip().lower()
    if setting in BY_NAME:
        return setting
    g.move_to(atlas.NS_MODE_PARK)
    g.sleep(300)
    if g.found(atlas.NS_STYLE_PROBE) or g.found(atlas.NS_STYLE_PROBE_HOVER):
        return "new"
    if previous == "new":
        # A miss on a known new-style account is a pop-up or an animation over the button.
        g.status("Interface style: new-style button not seen, keeping new")
        return "new"
    return "classic"  # no new-style button: the classic layout (owner, 2026-09-07)
