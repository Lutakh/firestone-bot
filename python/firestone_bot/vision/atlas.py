"""The logical canvas: every coordinate, rectangle and colour from the AHK code, verbatim.

Coordinates are in the ORIGINAL screen coordinate system (1920x1080 monitor, 100 % DPI, game
maximized, Windows 10 taskbar at the bottom). `REF` is the game client area in that system; the
viewport maps it to the live client rect at runtime (see vision/viewport.py for the anchor
model measured in plan step 4.2).

Feature modules add their own tables to this module as they are ported (plan 4.4).
"""

from __future__ import annotations

from dataclasses import dataclass

from firestone_bot.platform.window import Rect

# Reference frame: client area of the game on the original setup.
# Measured 2026-09-03 on Windows 11 as (0, 23, 1920, 1009); the AHK numbers assume a Windows 10
# machine with a 40 px taskbar, i.e. client top at y=31 (see docs/MEASUREMENTS.md, 4.1).
REF = Rect(0, 31, 1920, 1009)

# Anchor = (ax, ay), each 0.0 (left/top), 0.5 (centre) or 1.0 (right/bottom).
Anchor = tuple[float, float]

LEFT, CENTER, RIGHT = 0.0, 0.5, 1.0
TOP, BOTTOM = 0.0, 1.0


def default_anchor(fx: float, fy: float) -> Anchor:
    """Guess a widget's anchor from its position as a fraction of the client (thirds rule).

    Only matters when the live client aspect differs from REF; refine per entry when a probe
    misses at 16:9 (plan 4.6).
    """

    def one(f: float) -> float:
        if f < 1 / 3:
            return 0.0
        if f > 2 / 3:
            return 1.0
        return 0.5

    return one(fx), one(fy)


@dataclass(frozen=True)
class Point:
    x: int
    y: int
    anchor: Anchor | None = None


@dataclass(frozen=True)
class Probe:
    """A PixelSearch: rect corners (inclusive, as AHK), colour 0xRRGGBB, per-channel variation."""

    x1: int
    y1: int
    x2: int
    y2: int
    color: int
    variation: int = 3
    name: str = ""
    anchor: Anchor | None = None

    def normalized(self) -> Probe:
        return Probe(
            min(self.x1, self.x2),
            min(self.y1, self.y2),
            max(self.x1, self.x2),
            max(self.y1, self.y2),
            self.color,
            self.variation,
            self.name,
            self.anchor,
        )


# Common colours (AHK 0xRRGGBB literals).
GREEN_BUTTON = 0x0AA008  # affordable / claim button
GREEN_BUTTON_2 = 0x16BC15
RED_DOT = 0xF40000  # notification dot
IDLE_TROOP = 0x542710  # brown idle-troop marker on the map
ORANGE_1 = 0xF9AA47
ORANGE_2 = 0xFCAC47

# --- Helpers (BigClose, MainMenu, MapClose) ------------------------------------------------
BIG_CLOSE = Point(1851, 84)  # BigClose.ahk:5 (dialog X; the settings gear on the main screen)
MM_SETTINGS_OPEN = Probe(1542, 655, 1654, 687, 0x285483, 3, "mm_settings_open")  # MainMenu.ahk:13
MM_RATE_POPUP = Probe(1057, 288, 1321, 335, 0x8E4423, 2, "mm_rate_popup")  # MainMenu.ahk:18
MM_RATE_POPUP_CLOSE = Point(1397, 307)  # MainMenu.ahk:20
MAP_POPUP_CLOSE = Point(1870, 706)  # MapClose.ahk:7

# --- ClaimEvents.ahk ------------------------------------------------------------------------
EVENTS_RED_DOT = Probe(1719, 170, 1741, 204, RED_DOT, 3, "events_red_dot")  # :7
EVENTS_ICON = Point(1691, 229)  # :10
EVENTS_TOP_EVENT = Point(942, 359)  # :15
EVENTS_CHALLENGES_TAB = Point(1125, 70)  # :20
EVENTS_CHALLENGE_CLAIMS = (  # :25-43 (probe, claim button)
    (Probe(1540, 365, 1568, 405, GREEN_BUTTON, 3, "events_claim_1"), Point(1483, 382)),
    (Probe(1538, 592, 1566, 633, GREEN_BUTTON, 3, "events_claim_2"), Point(1496, 604)),
    (Probe(1530, 823, 1568, 870, GREEN_BUTTON, 3, "events_claim_3"), Point(1500, 837)),
)

# --- Quests.ahk -----------------------------------------------------------------------------
CHARACTER_ICON = Point(90, 112)  # :9
QUESTS_TAB = Point(1455, 74)  # :14
QUESTS_DAILY_TAB = Point(765, 155)  # :19
QUESTS_WEEKLY_TAB = Point(1165, 154)  # :35
QUESTS_CLAIM_READY = Probe(1544, 286, 1606, 334, GREEN_BUTTON, 3, "quests_claim_ready")  # :23
QUESTS_CLAIM = Point(1503, 309)  # :25
QUESTS_REWARD_OK = Point(1619, 990)  # :29

# --- Shop.ahk -------------------------------------------------------------------------------
SHOP_RED_DOT = Probe(1876, 523, 1905, 564, RED_DOT, 3, "shop_red_dot")  # :10
SHOP_ICON = Point(1857, 583)  # :12
SHOP_MYSTERY_BOX = Point(591, 857)  # :17
SHOP_CHECKIN_TAB = Point(1440, 125)  # :22
SHOP_CHECKIN_CLAIM = Point(1346, 894)  # :27
SHOP_CHECKIN_OK = Point(1339, 828)  # :31

# --- CheckMail.ahk --------------------------------------------------------------------------
MAIL_ICON = Point(56, 777)  # :8
MAIL_CLAIM_ALL = Probe(1260, 780, 1334, 835, GREEN_BUTTON, 3, "mail_claim_all")  # :13
MAIL_CLAIM_BUTTON = Point(1215, 808)  # :15
MAIL_REWARD_OK = Point(1172, 688)  # :20
MAIL_DELETE_READY = Probe(1533, 904, 1601, 969, 0xE9554E, 3, "mail_delete_ready")  # :26
MAIL_DELETE_BUTTON = Point(1569, 939)  # :28

# --- OpenChests.ahk / OpenChestType.ahk / OraclesGift.ahk / MysteryBox.ahk -----------------
BAG_ICON = Point(1581, 939)  # OpenChests.ahk:30
BAG_CHESTS_TAB = Point(1487, 460)  # :35
BAG_CLOSE = Point(1870, 246)  # :159
BAG_SCROLL_HOVER = Point(1720, 608)  # :185 (mouse position while wheeling)
CHEST_GRID = (1543, 307, 1887, 905)  # OpenChestType.ahk:12 search rect for chest signatures
CHEST_OPEN_BUTTONS = (  # OpenChestType.ahk:18-36 (probe, button): 11-50, 2-10, 1
    (Probe(1200, 773, 1300, 850, GREEN_BUTTON, 1, "chest_open_50"), Point(1209, 812)),
    (Probe(1090, 773, 1173, 850, GREEN_BUTTON, 1, "chest_open_10"), Point(1089, 812)),
    (Probe(860, 773, 1055, 850, GREEN_BUTTON, 1, "chest_open_1"), Point(914, 812)),
)
GIFT_OPEN_BUTTONS = (  # OraclesGift.ahk:25-43, one row lower than chests
    (Probe(1200, 862, 1300, 930, GREEN_BUTTON, 1, "gift_open_50"), Point(1209, 898)),
    (Probe(1090, 862, 1173, 930, GREEN_BUTTON, 1, "gift_open_10"), Point(1089, 898)),
    (Probe(860, 862, 1055, 930, GREEN_BUTTON, 1, "gift_open_1"), Point(914, 898)),
)
CHEST_EQUIP_READY = Probe(860, 860, 1084, 892, GREEN_BUTTON, 1, "chest_equip_ready")  # :44
CHEST_EQUIP = Point(964, 880)  # :46
CHEST_OPEN_MORE_READY = Probe(1773, 932, 1831, 976, GREEN_BUTTON, 1, "chest_open_more")  # :53
CHEST_OPEN_MORE = Point(1797, 959)  # :56
CHEST_FAILSAFE = Point(59, 181)  # :82 "failsafe in case big close opens options"
ORACLE_GIFT_COLOR = 0xFFD800  # OraclesGift.ahk:12
MYSTERY_BOX_COLOR = 0xF78BF1  # MysteryBox.ahk:12

# Rarity groups in AHK label order; the setting selects the start label (None = Exclude All).
GEAR_CHESTS = (
    ("Titan", 0x08BAC6),
    ("Mythic", 0xF09C15),
    ("Legendary", 0xC63A07),
    ("Epic", 0xB273F5),
    ("Rare", 0x5C98FB),
    ("Uncommon", 0xB54424),
    ("Common", 0xC9782B),
)
GEAR_CHEST_START: dict[str, int | None] = {
    "Exclude All": None,
    "Don't Exclude Any": 0,
    "Titan": 1,
    "Mythic and Higher": 2,
    "Legendary and Higher": 3,
    "Epic and Higher": 4,
}
JEWEL_CHESTS = (
    ("Platinum", 0xFFB2DC),
    ("Emerald", 0x7B6926),
    ("Opal", 0xA1F3E3),
    ("Diamond", 0xF60151),
    ("Golden", 0xCF7029),
    ("Iron", 0x071250),
    ("Wooden", 0x442522),
)
JEWEL_CHEST_START: dict[str, int | None] = {
    "Exclude All": None,
    "Don't Exclude Any": 0,
    "Diamond and Higher": 4,
    "Opal and Higher": 3,
    "Emerald and Higher": 2,
    "Platinum": 1,
}
CELESTIAL_CHESTS = (
    ("Galaxy", 0xFF82FF),
    ("Cosmic", 0xD326C0),
    ("Nebula", 0x5B1D84),
    ("Solar", 0xFEF343),
    ("Lunar", 0x00F694),
    ("Comet", 0x9F3C29),
)
CELESTIAL_CHEST_START: dict[str, int | None] = {
    "Exclude All": None,
    "Don't Exclude Any": 0,
    "Solar and Higher": 4,
    "Nebula and Higher": 0,  # AHK jumps to Galaxy (sic)
    "Cosmic and Higher": 0,  # AHK jumps to Galaxy (sic)
    "Galaxy": 1,
}

# --- MapStart.ahk (partial; the rest comes with the map_start port) -------------------------
MAP_TROOP_IDLE = Probe(1175, 996, 1187, 1012, IDLE_TROOP, 10, "map_troop_idle")  # :179
