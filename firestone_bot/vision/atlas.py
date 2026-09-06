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
ANCHOR_CENTER: Anchor = (CENTER, CENTER)  # centred content (dialogs, the world map)


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

# --- ClaimEvents.ahk (main-screen part re-measured 2026-09-04) -------------------------------
# AHK looked for the red dot in (1719,170)-(1741,204) and clicked the icon at (1691,229): the
# Events button is now at the bottom left of the main screen (client (583,930), bell (609,907)).
EVENTS_BELL = Probe(595, 916, 635, 956, RED_DOT, 3, "events_bell")
EVENTS_ICON = Point(583, 961)
# Events list: active cards first, 175 px pitch; bell at the top-right corner of a card.
# The list is a centred dialog: at 16:9 its right-hand edge (bells, X) must be anchored to the
# centre, not to the screen edge (measured on macOS 2026-09-06: bell 125 px right of the
# edge-anchored rect).
EVENTS_CARDS = tuple(Point(960, 359 + i * 175, (CENTER, CENTER)) for i in range(4))
EVENTS_CARD_BELLS = tuple(
    Probe(
        1417,
        299 + i * 175,
        1447,
        329 + i * 175,
        RED_DOT,
        3,
        f"events_card_bell_{i + 1}",
        (CENTER, CENTER),
    )
    for i in range(4)
)
EVENTS_LIST_CLOSE = Point(1490, 81, (CENTER, CENTER))  # X of the list (client (1490,50))
EVENTS_TOP_EVENT = EVENTS_CARDS[0]  # :15 (AHK clicked (942,359))
# The event page is centred too (macOS 2026-09-06: tab bell 106 px right of the edge-anchored
# rect).
EVENTS_CHALLENGES_TAB = Point(1125, 70, (CENTER, CENTER))  # :20
EVENTS_CHALLENGES_TAB_BELL = Probe(
    1290, 44, 1320, 74, RED_DOT, 3, "events_tab_bell", (CENTER, CENTER)
)
EVENTS_PAGE_CLOSE = Point(1715, 124, (CENTER, CENTER))  # X of the event page (client (1715,93))
EVENTS_CHALLENGE_CLAIMS = (  # :25-43 (probe, claim button) - still valid in the 2026 layout
    (
        Probe(1540, 365, 1568, 405, GREEN_BUTTON, 3, "events_claim_1", (CENTER, CENTER)),
        Point(1483, 382, (CENTER, CENTER)),
    ),
    (
        Probe(1538, 592, 1566, 633, GREEN_BUTTON, 3, "events_claim_2", (CENTER, CENTER)),
        Point(1496, 604, (CENTER, CENTER)),
    ),
    (
        Probe(1530, 823, 1568, 870, GREEN_BUTTON, 3, "events_claim_3", (CENTER, CENTER)),
        Point(1500, 837, (CENTER, CENTER)),
    ),
)

# --- Battle pass (Python-only, measured 2026-09-04) -----------------------------------------
BP_ICON = Point(445, 961)  # main-screen button (client (445,930)), left of Events
BP_BELL = Probe(470, 894, 500, 924, RED_DOT, 3, "bp_bell")
BP_REWARDS_TAB = Point(1085, 79)  # tab (client (1085,48))
BP_REWARDS_BADGE = Probe(1198, 46, 1228, 76, RED_DOT, 3, "bp_rewards_badge")
BP_REWARD_COLUMNS = (360, 1830)  # logical x range of the milestone track
BP_REWARD_ROWS = ((525, 565), (945, 985))  # logical y bands of the Golden / Free Claim rows
BP_PARK = Point(960, 1015)
BP_SCROLL_HOVER = Point(1100, 700)
BP_CLOSE = Point(1815, 126)  # X of the battle pass (client (1815,95))

# --- Quests.ahk -----------------------------------------------------------------------------
CHARACTER_ICON = Point(90, 112)  # :9
# Red badge on the quests icon under the avatar (classic and new layouts differ in y):
# measured 2026-09-06 on the Mac client, badge extent (90..120, 249..275) / (90..120, 188..213).
QUESTS_BADGE = Probe(94, 253, 116, 271, RED_DOT, 30, "quests_badge")
NS_QUESTS_BADGE = Probe(94, 192, 116, 209, RED_DOT, 30, "ns_quests_badge")
QUESTS_TAB = Point(1455, 74)  # :14
QUESTS_DAILY_TAB = Point(765, 155)  # :19
QUESTS_WEEKLY_TAB = Point(1165, 154)  # :35
QUESTS_CLAIM_READY = Probe(1544, 286, 1606, 334, GREEN_BUTTON, 3, "quests_claim_ready")  # :23
QUESTS_CLAIM = Point(1503, 309)  # :25
QUESTS_REWARD_OK = Point(1619, 990)  # :29

# --- Shop.ahk -------------------------------------------------------------------------------
SHOP_RED_DOT = Probe(1876, 523, 1905, 564, RED_DOT, 3, "shop_red_dot")  # :10
SHOP_ICON = Point(1857, 583)  # :12
# Shop.ahk:17 clicked the mystery box at (591,857). In the 2026 shop the "Daily deals" row
# scrolls horizontally: the free mystery box is the FIRST card while claimable (green button
# at logical (466,812)-(711,852), measured 2026-09-04 right after the reset) and moves to the
# end of the row once claimed, where a paid deal takes its place.
SHOP_DEALS_HOVER = Point(1100, 600)
# Green "Free" button of the first daily-deal card, measured 2026-09-06 (extent 488..796 x
# 850..899); the previous rect sat above the button and the box was never claimed.
SHOP_MYSTERY_CLAIM_READY = Probe(520, 860, 760, 890, GREEN_BUTTON, 30, "shop_mystery_claim")
SHOP_MYSTERY_CLAIM = Point(642, 875)
SHOP_FIRST_TAB = Point(493, 124)  # bundle tab holding the free mystery box
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

# --- Town buildings -------------------------------------------------------------------------
TOWN_MAGIC_QUARTER = Point(658, 284)  # Guardian.ahk:9
TOWN_TAVERN = Point(719, 957)  # ClaimBeer.ahk:14
TOWN_ORACLE = Point(1023, 994)  # ClaimRituals.ahk:10
TOWN_ENGINEER = Point(1230, 820)  # ClaimEngineer.ahk:9

# --- Guardian.ahk ---------------------------------------------------------------------------
GUARDIAN_EVOLVE_DOT = Probe(1307, 107, 1346, 136, RED_DOT, 3, "guardian_evolve_dot")  # :14
GUARDIAN_EVOLVE_TAB = Point(1200, 165)  # :17
GUARDIAN_EVOLVE_BUTTON = Point(1117, 750)  # :21
GUARDIAN_BACK_TAB = Point(1049, 171)  # :26
GUARDIAN_TRAIN_READY = Probe(1199, 766, 1257, 810, GREEN_BUTTON, 3, "guardian_train_ready")  # :32
GUARDIAN_TRAIN_BUTTON = Point(1138, 787)  # :64
# Chaos-rift tab of the guardian screen (Python-only, measured 2026-09-04): third tab, bell on
# it, bells at the top-right corner of the 4 roster portraits, green Upgrade button.
GUARDIAN_CHAOS_TAB = Point(1360, 171)
GUARDIAN_CHAOS_TAB_BELL = Probe(1385, 111, 1415, 141, RED_DOT, 3, "guardian_chaos_tab_bell")
GUARDIAN_ROSTER = tuple(  # (bell probe, portrait click) for roster positions 1..4
    (Probe(x - 12, 897, x + 12, 921, RED_DOT, 3, f"guardian_bell_{i}"), Point(x - 55, 966))
    for i, x in enumerate((805, 945, 1085, 1225), start=1)
)
GUARDIAN_CHAOS_UPGRADE_READY = Probe(1580, 691, 1770, 781, GREEN_BUTTON, 3, "guardian_chaos_up")
GUARDIAN_CHAOS_UPGRADE = Point(1672, 731)

# --- ClaimBeer.ahk / UseTavernToken.ahk / CraftArtifact.ahk -----------------------------------
TAVERN_BEER_TAB = Point(773, 500)  # ClaimBeer.ahk:18
TAVERN_TOKEN_SHOP = Point(1735, 69)  # :23
# ClaimBeer.ahk:27 looked for a yellow 0xFFBB33 button in (616,610)-(697,656); the token shop
# button is now green (0x0AA008) and spans (407,611)-(652,654) (measured 2026-09-04).
TAVERN_BEER_CLAIM_READY = Probe(430, 615, 630, 650, GREEN_BUTTON, 3, "tavern_beer_claim")
TAVERN_BEER_CLAIM = Point(544, 630)  # :29
TAVERN_USE_TOKEN_READY = Probe(
    1019, 934, 1050, 991, GREEN_BUTTON, 3, "tavern_use_token"
)  # UseTavernToken.ahk:8
TAVERN_USE_TOKEN = Point(962, 958)  # :10
TAVERN_CARDS = (  # :20-21
    Point(680, 315),
    Point(956, 315),
    Point(1243, 315),
    Point(680, 715),
    Point(956, 715),
    Point(1243, 715),
)
TAVERN_DISMISS = Point(1257, 49)  # :36
CRAFT_ARTIFACT_READY = Probe(
    305, 517, 356, 558, GREEN_BUTTON, 3, "craft_artifact_ready"
)  # CraftArtifact.ahk:6
CRAFT_ARTIFACT = Point(227, 507)  # :8

# --- ScarabToken.ahk / Scarab.ahk -------------------------------------------------------------
SCARAB_GAME_DOT = Probe(1275, 320, 1310, 360, RED_DOT, 3, "scarab_game_dot")  # ScarabToken.ahk:16
TAVERN_SCARAB_TAB = Point(1108, 500)  # :19
SCARAB_TOKEN_DOT = Probe(1860, 667, 1900, 705, RED_DOT, 3, "scarab_token_dot")  # :24
SCARAB_TOKEN_TAB = Point(1809, 722)  # :26
SCARAB_TOKEN_CLAIM = Point(685, 763)  # :31
# Rework (2026-09-04): token icon inside the green Play button, client (905..955, 900..950).
# Paid coin has a purple ring (0x9C1C9C..0xB53CF7), the free coin is silver (0xBFC5C5).
# hovered Play button is the lighter green 0x16BC15
SCARAB_PLAY_READY_HOVER = Probe(1019, 934, 1050, 991, GREEN_BUTTON_2, 3, "scarab_play_hover")
SCARAB_PLAY_PARK = Point(1250, 890)  # mouse parking spot away from the button and reels
SCARAB_FREE_COUNTER = (1440, 56, 1520, 96)  # logical rect of the free-token counter digits
SCARAB_PLAY_ICON_PAID = Probe(905, 931, 955, 981, 0xA524A5, 30, "scarab_play_icon_paid")
SCARAB_PLAY_ICON_FREE = Probe(905, 931, 955, 981, 0xBFC5C5, 18, "scarab_play_icon_free")

# --- ClaimRituals.ahk -----------------------------------------------------------------------
RITUALS_DOT = Probe(871, 341, 903, 382, RED_DOT, 3, "rituals_dot")  # :15
RITUALS_TAB = Point(830, 420)  # :17
RITUAL_CLAIMS = (  # :22-45
    (Probe(1259, 463, 1331, 536, GREEN_BUTTON, 3, "ritual_1"), Point(1180, 500)),
    (Probe(1609, 458, 1677, 514, GREEN_BUTTON, 3, "ritual_2"), Point(1586, 514)),
    (Probe(1272, 811, 1326, 872, GREEN_BUTTON, 3, "ritual_3"), Point(1170, 837)),
    (Probe(1619, 805, 1690, 870, GREEN_BUTTON, 3, "ritual_4"), Point(1579, 840)),
)

# --- UpgradeBlessings.ahk / ClickBless.ahk ----------------------------------------------------
BLESSINGS_DOT = Probe(865, 506, 904, 547, RED_DOT, 1, "blessings_dot")  # :12
BLESSINGS_TAB = Point(828, 585)  # :14
BLESSING_SLOTS = (  # clock positions 12..11 then fate; (red-dot probe, click point)
    (Probe(1402, 185, 1457, 231, RED_DOT, 1, "bless_12"), Point(1375, 239)),
    (Probe(1565, 220, 1631, 291, RED_DOT, 1, "bless_1"), Point(1535, 286)),
    (Probe(1688, 340, 1734, 389, RED_DOT, 1, "bless_2"), Point(1662, 407)),
    (Probe(1741, 507, 1777, 546, RED_DOT, 1, "bless_3"), Point(1703, 578)),
    (Probe(1695, 673, 1731, 711, RED_DOT, 1, "bless_4"), Point(1653, 741)),
    (Probe(1577, 795, 1613, 825, RED_DOT, 1, "bless_5"), Point(1531, 860)),
    (Probe(1414, 837, 1447, 876, RED_DOT, 1, "bless_6"), Point(1372, 903)),
    (Probe(1258, 793, 1283, 828, RED_DOT, 1, "bless_7"), Point(1207, 852)),
    (Probe(1132, 672, 1165, 703, RED_DOT, 1, "bless_8"), Point(1089, 742)),
    (Probe(1091, 510, 1115, 554, RED_DOT, 1, "bless_9"), Point(1045, 575)),  # AHK y2=5541 typo
    (Probe(1131, 345, 1165, 377, RED_DOT, 1, "bless_10"), Point(1089, 415)),
    (Probe(1256, 224, 1277, 261, RED_DOT, 1, "bless_11"), Point(1209, 291)),
    (Probe(1431, 498, 1465, 531, RED_DOT, 1, "bless_fate"), Point(1370, 572)),
)
BLESS_UPGRADE_READY = Probe(
    1249, 763, 1498, 861, GREEN_BUTTON, 3, "bless_upgrade_ready"
)  # ClickBless.ahk:6
BLESS_UPGRADE = Point(1371, 812)  # :8
BLESS_CLOSE = Point(1661, 229)  # :14

# --- OracleDaily.ahk ------------------------------------------------------------------------
ORACLE_GIFT_DOT = Probe(859, 684, 901, 740, RED_DOT, 3, "oracle_gift_dot")  # :7
ORACLE_GIFT_TAB = Point(823, 760)  # :9
ORACLE_GIFT_CLAIM = Point(711, 791)  # :14

# --- ClaimEngineer.ahk ----------------------------------------------------------------------
ENGINEER_WM_TAB = Point(964, 507)  # :16
ENGINEER_TAB = Point(131, 435)  # :22
ENGINEER_SELECT = Point(610, 540)  # :29
ENGINEER_TOOLS_READY = Probe(1709, 686, 1747, 733, GREEN_BUTTON, 3, "engineer_tools_ready")  # :35
ENGINEER_TOOLS_CLAIM = Point(1642, 704)  # :37

# --- WMUpgrade.ahk / WMLevelOnly.ahk / WMBlueprintsOnly.ahk ---------------------------------
WM_ROSTER = (248, 894, 1878, 1020)  # WMUpgrade.ahk: bottom strip searched for the WM signature
WAR_MACHINES = (  # label order in WMUpgrade.ahk; signature colour in the roster strip
    ("Aegis", 0xA49789),
    ("Cloudfist", 0xF7661C),
    ("Curator", 0x740D0B),
    ("Earthshatterer", 0x3B4F98),
    ("Firecracker", 0xEA4019),  # Gui.ahk offers "Upgrade FireCracker": never matches, like AHK
    ("Fortress", 0x275094),
    ("Goliath", 0x702815),
    ("Harvester", 0x010BAF),
    ("Hunter", 0x6CB932),
    ("Judgement", 0x971DAB),
    ("Sentinel", 0xC2EFD9),
    ("Talos", 0x226B10),
    ("Thunderclap", 0x3EE0EE),
)
WM_LEVEL_DOT = Probe(1358, 103, 1400, 133, RED_DOT, 3, "wm_level_dot")  # WMLevelOnly.ahk:4
WM_ANVIL_TAB = Point(1337, 170)  # :7
WM_LEVEL_UPGRADE = Point(1428, 581)  # :12
WM_BLUEPRINT_TAB = Point(1486, 170)  # WMBlueprintsOnly.ahk:5
WM_BLUEPRINT_STATS = {  # :45-65 (probe, button)
    "damage": (Probe(1171, 594, 1225, 644, GREEN_BUTTON, 3, "wm_bp_damage"), Point(1108, 600)),
    "health": (Probe(1477, 597, 1536, 644, GREEN_BUTTON, 3, "wm_bp_health"), Point(1413, 600)),
    "armor": (Probe(1786, 596, 1844, 642, GREEN_BUTTON, 3, "wm_bp_armor"), Point(1726, 600)),
}
WM_BLUEPRINT_CHOICES = {  # Blueprints setting -> stats in click order
    "Upgrade All": ("damage", "health", "armor"),
    "Damage Only": ("damage",),
    "Health": ("health",),  # Gui.ahk offers "Health Only" / "Armor Only": never match, so
    "Armor": ("armor",),  # those choices upgrade all, exactly like the AHK fall-through
    "Damage and Health": ("damage", "health"),
    "Damage and Armor": ("damage", "armor"),
    "Health and Armor": ("health", "armor"),
}

# --- ExoticMerchant.ahk / ExoticUpgrades.ahk / BuyExotic.ahk --------------------------------
TOWN_EXOTIC_MERCHANT = Point(1459, 650)  # ExoticMerchant.ahk:9
EXOTIC_SCROLLS = (  # :34-55 speed, damage, health
    (Probe(1026, 596, 1074, 636, GREEN_BUTTON, 3, "sell_scroll_speed"), Point(959, 596)),
    (Probe(1350, 598, 1401, 634, GREEN_BUTTON, 3, "sell_scroll_damage"), Point(1280, 601)),
    (Probe(1678, 596, 1724, 635, GREEN_BUTTON, 3, "sell_scroll_health"), Point(1595, 592)),
)
EXOTIC_GOLD_TOP = (  # :60-81 midas' touch, pouch of gold, bucket of gold
    (Probe(1022, 912, 1078, 951, GREEN_BUTTON, 3, "sell_midas"), Point(962, 908)),
    (Probe(1336, 916, 1399, 956, GREEN_BUTTON, 3, "sell_pouch"), Point(1278, 910)),
    (Probe(1663, 917, 1720, 950, GREEN_BUTTON, 3, "sell_bucket"), Point(1602, 911)),
)
EXOTIC_GOLD_BOTTOM = (  # :88-101 after 35 wheel-downs: crate of gold, barrel of gold
    (Probe(1026, 298, 1081, 338, GREEN_BUTTON, 3, "sell_crate"), Point(967, 307)),
    (Probe(1341, 296, 1398, 335, GREEN_BUTTON, 3, "sell_barrel"), Point(1280, 313)),
)
EXOTIC_ITEMS_BOTTOM = (  # :104-141 drums of war, dragon armor, guardian's rune, totems
    (Probe(1678, 298, 1721, 332, GREEN_BUTTON, 3, "sell_drums"), Point(1611, 313)),
    (Probe(1024, 616, 1078, 648, GREEN_BUTTON, 3, "sell_dragon_armor"), Point(954, 616)),
    (Probe(1346, 614, 1399, 651, GREEN_BUTTON, 3, "sell_guardian_rune"), Point(1269, 608)),
    (Probe(1667, 616, 1722, 652, GREEN_BUTTON, 3, "sell_totem_agony"), Point(1591, 610)),
    (Probe(1030, 930, 1078, 975, GREEN_BUTTON, 3, "sell_totem_annihilation"), Point(951, 934)),
)
EXOTIC_UPGRADES_TAB = Point(1282, 173)  # ExoticUpgrades.ahk:4
EXOTIC_UPGRADES_HOVER = Point(1270, 567)  # :8
_EXU_ROW1 = (
    (Probe(1004, 833, 1060, 874, GREEN_BUTTON, 3, "exu_r1s1"), Point(900, 851)),
    (Probe(1350, 830, 1400, 865, GREEN_BUTTON, 3, "exu_r1s2"), Point(1284, 840)),
    (Probe(1694, 831, 1741, 872, GREEN_BUTTON, 3, "exu_r1s3"), Point(1626, 836)),
)
_EXU_ROWN = (  # rows 2-4 share the same screen positions after scrolling
    (Probe(999, 907, 1051, 946, GREEN_BUTTON, 3, "exu_rNs1"), Point(932, 919)),
    (Probe(1353, 905, 1400, 944, GREEN_BUTTON, 3, "exu_rNs2"), Point(1278, 911)),
    (Probe(1695, 904, 1745, 939, GREEN_BUTTON, 3, "exu_rNs3"), Point(1621, 906)),
)
EXOTIC_UPGRADE_ROWS = ((0, _EXU_ROW1), (13, _EXU_ROWN), (15, _EXU_ROWN), (15, _EXU_ROWN))
EMBLEM_MARKET_TAB = Point(1436, 187)  # BuyExotic.ahk:6
EMBLEM_CHEST_TABS = (Point(689, 470), Point(695, 622), Point(689, 780))  # gear, wm, oracle
EMBLEM_BUY_READY = Probe(1211, 579, 1253, 640, GREEN_BUTTON, 3, "emblem_buy_ready")  # :16
EMBLEM_BUY = Point(1153, 611)  # :18

# --- Arena.ahk / ArenaBattle.ahk ------------------------------------------------------------
TOWN_BATTLES = Point(362, 204)  # Arena.ahk:9
ARENA_OF_KINGS = Point(1120, 507)  # :14
ARENA_OPPONENT_COLUMNS = (700, 954, 1220)  # :19
ARENA_OPPONENT_Y = 630  # :30
ARENA_REFRESH = Point(871, 195)  # :25
ARENA_BUY_MORE = Probe(1243, 669, 1291, 713, GREEN_BUTTON, 1, "arena_buy_more")  # :35
ARENA_FIGHT = Point(961, 570)  # :41
ARENA_BATTLE_DONE = Probe(
    979, 753, 1056, 798, GREEN_BUTTON, 3, "arena_battle_done"
)  # ArenaBattle.ahk:5
ARENA_BATTLE_CLAIM = Point(959, 775)  # :7

# --- Alchemist.ahk --------------------------------------------------------------------------
TOWN_ALCHEMIST = Point(511, 837)  # :8


@dataclass(frozen=True)
class AlchemySlot:
    name: str
    not_running: Probe  # yellow marker when the slot is idle
    complete: Probe  # green "collect"
    free: Probe  # orange "free to complete"
    in_progress: Probe  # brown timer: more than 3 minutes remaining
    collect: Point
    start: Point


ALCHEMY_SLOTS = (
    AlchemySlot(
        "Dragon Blood",
        Probe(928, 519, 948, 535, 0xFFC700, 3, "alch_blood_idle"),
        Probe(985, 746, 1037, 792, GREEN_BUTTON, 3, "alch_blood_done"),
        Probe(969, 742, 1026, 756, ORANGE_1, 3, "alch_blood_free"),
        Probe(1007, 735, 1030, 766, 0x916A38, 3, "alch_blood_running"),
        Point(949, 777),
        Point(951, 771),
    ),
    AlchemySlot(
        "Strange Dust",
        Probe(1274, 515, 1298, 537, 0xFFC700, 3, "alch_dust_idle"),
        Probe(1336, 748, 1386, 789, GREEN_BUTTON, 3, "alch_dust_done"),
        Probe(1336, 748, 1386, 789, ORANGE_1, 3, "alch_dust_free"),
        Probe(1346, 734, 1373, 766, 0x916A38, 3, "alch_dust_running"),
        Point(1286, 786),
        Point(1286, 786),
    ),
    AlchemySlot(
        "Exotic Coins",
        Probe(1622, 518, 1645, 538, 0xFFC700, 3, "alch_coin_idle"),
        Probe(1679, 748, 1735, 796, GREEN_BUTTON, 3, "alch_coin_done"),
        Probe(1679, 748, 1735, 796, ORANGE_1, 3, "alch_coin_free"),
        Probe(1699, 737, 1723, 767, 0x916A38, 3, "alch_coin_running"),
        Point(1632, 772),
        Point(1641, 767),
    ),
)

# --- Research.ahk and sub-functions -----------------------------------------------------------
TOWN_LIBRARY = Point(329, 657)  # Research.ahk:12
RS_FIRESTONE_TREE = Point(1816, 610)  # :18
RS_NODE_AVAILABLE = 0x0D49DE  # ResearchStart.ahk: blue of an available node (variation 0)
RS_TREE_HOVER = Point(1429, 944)  # ResearchStart.ahk:5
RS_START_OR_DISMISS = Point(721, 747)  # ResearchClicks.ahk:6
RS_SLOT2_LOCKED = Probe(1208, 892, 1264, 931, 0x6F6F6F, 1, "rs_slot2_locked")  # SlotTest:6
RS_SLOT2_IN_PROGRESS = Probe(1228, 889, 1269, 929, 0x916A37, 3, "rs_slot2_running")  # :13
RS_SLOT2_FREE = Probe(1234, 912, 1272, 974, ORANGE_1, 3, "rs_slot2_free")  # :20
RS_SLOT2_DONE = Probe(1234, 912, 1272, 974, GREEN_BUTTON, 3, "rs_slot2_done")  # :31
RS_SLOT2_CLAIM = Point(1204, 938)  # :22
RS_SLOT1_IN_PROGRESS = Probe(603, 891, 624, 932, 0x916A37, 3, "rs_slot1_running")  # :48
RS_SLOT1_FREE = Probe(588, 911, 620, 967, ORANGE_1, 3, "rs_slot1_free")  # :55
RS_SLOT1_DONE = Probe(588, 911, 620, 967, GREEN_BUTTON, 3, "rs_slot1_done")  # :71
RS_SLOT1_CLAIM = Point(545, 940)  # :57
RAST_SLOT2 = Point(1202, 944)  # ResearchAfterStartTest.ahk:8
RAST_SLOT1 = Point(554, 939)  # :29
RAST_IN_PROGRESS = Probe(562, 245, 754, 311, 0x8C4221, 10, "rast_in_progress")  # :12

# --- Guild.ahk ------------------------------------------------------------------------------
MAIN_GUILD_ICON = Point(1857, 481)  # :12
# The guild map and its dialogs are centred (like the world map): at 16:9 every entry below
# must be anchored to the centre (measured on macOS 2026-09-06: the expeditions bell sat 47 px
# left of the left-anchored rect).
GUILD_EXPEDITION_DOT = Probe(
    450, 410, 380, 490, RED_DOT, 3, "guild_expedition_dot", (CENTER, CENTER)
)  # :17 (inverted)
GUILD_EXPEDITIONS = Point(308, 406, (CENTER, CENTER))  # :20
GUILD_EXPEDITION_START = Point(1321, 331, (CENTER, CENTER))  # :24
GUILD_PTREE_ENTRY = Point(1560, 366, (CENTER, CENTER))  # :58
GUILD_SHOP = Point(639, 263, (CENTER, CENTER))  # :72
GUILD_SHOP_SUPPLIES = Point(141, 790, (CENTER, CENTER))  # :77
# Guild.ahk:81-84 probed the teal card colour 0x1EA569 in (764,617)-(869,653) and clicked
# (716,637). Since the 2026 layout the "Free pickaxes" card has its green Claim button at the
# bottom, logical (590,723)-(835,766) (measured 2026-09-04).
GUILD_AXE_READY = Probe(620, 730, 800, 760, GREEN_BUTTON, 3, "guild_axe_ready", (CENTER, CENTER))
GUILD_AXE_CLAIM = Point(714, 747, (CENTER, CENTER))
GUILD_CRYSTAL = Point(1646, 928, (CENTER, CENTER))  # :93
GUILD_CRYSTAL_HIT_READY = Probe(
    1101, 904, 1075, 946, GREEN_BUTTON, 3, "guild_crystal_hit", (CENTER, CENTER)
)  # :97 (inverted)
GUILD_CRYSTAL_HIT = Point(957, 896, (CENTER, CENTER))  # :100
GUILD_CRYSTAL_PARK = Point(
    300, 950, (CENTER, CENTER)
)  # mouse parking spot away from the hit button
GUILD_PICKAXE_COUNTER = (1590, 51, 1710, 91)  # logical rect of the pickaxe counter digits
GUILD_NOTIF_1 = Point(1056, 487)  # :109
GUILD_NOTIF_2 = Point(230, 667)  # :114

# --- Awaken.ahk -----------------------------------------------------------------------------
AWAKEN_GREEN = 0x0A9F05
AWAKEN_DOT = Probe(1107, 745, 1367, 944, RED_DOT, 3, "awaken_dot")  # :8
AWAKEN_OPEN = Point(1192, 847)  # :11
AWAKEN_X1 = Point(1577, 400)  # :39
AWAKEN_BUTTON_ORANGE = Probe(1600, 566, 1845, 612, 0xF4A044, 1, "awaken_button_orange")  # :43
AWAKEN_BUTTON_GREEN = Probe(1600, 566, 1845, 612, AWAKEN_GREEN, 1, "awaken_button_green")  # :150
AWAKEN_BUTTON = Point(1725, 582)  # :152
AWAKEN_AUTO_READY = Probe(1650, 955, 1900, 1015, AWAKEN_GREEN, 1, "awaken_auto_ready")  # :54
AWAKEN_AUTO = Point(1774, 993)  # :146
AWAKEN_MULTIPLIERS = (  # :49-141 x160, x80, x40, x20, x10, x5, x2, x1 (probe, button)
    (Probe(1825, 632, 1910, 692, AWAKEN_GREEN, 1, "awaken_x160"), Point(1872, 666)),
    (Probe(1727, 632, 1815, 692, AWAKEN_GREEN, 1, "awaken_x80"), Point(1772, 666)),
    (Probe(1630, 632, 1716, 692, AWAKEN_GREEN, 1, "awaken_x40"), Point(1679, 666)),
    (Probe(1535, 632, 1615, 692, AWAKEN_GREEN, 1, "awaken_x20"), Point(1577, 666)),
    (Probe(1825, 365, 1910, 423, AWAKEN_GREEN, 1, "awaken_x10"), Point(1872, 400)),
    (Probe(1727, 365, 1815, 423, AWAKEN_GREEN, 1, "awaken_x5"), Point(1772, 400)),
    (Probe(1630, 365, 1716, 423, AWAKEN_GREEN, 1, "awaken_x2"), Point(1679, 400)),
    (Probe(1535, 365, 1615, 423, AWAKEN_GREEN, 1, "awaken_x1"), Point(1577, 400)),
)

# --- Chaos.ahk ------------------------------------------------------------------------------
CHAOS_DOT = Probe(1525, 695, 1555, 725, RED_DOT, 3, "chaos_dot")  # :8
CHAOS_OPEN = Point(1410, 625)  # :10
CHAOS_AUTO = Point(1740, 980)  # :13 (Auto/Manual toggle; NOT used by the rework, see chaos.py)
# Rework (2026-09-04): manual hits with free tokens only. Hit button at client (960,855),
# token icon inside it at client (905..955, 880..920); colours measured on captures.
CHAOS_HIT = Point(960, 886)
CHAOS_HIT_READY = Probe(850, 865, 1070, 905, GREEN_BUTTON, 3, "chaos_hit_ready")
CHAOS_HIT_ICON_PAID = Probe(905, 911, 955, 951, 0xA54510, 12, "chaos_hit_icon_paid")
CHAOS_HIT_ICON_FREE = Probe(905, 911, 955, 951, 0x3182C6, 16, "chaos_hit_icon_free")
# Rift shop (books), measured 2026-09-04: Shop button right column with its bell, Supplies
# entry in the shop's left menu with its bell, green price button of the "Tome of power" card.
RIFT_SHOP = Point(1815, 721)
RIFT_SHOP_BELL = Probe(1865, 641, 1895, 671, RED_DOT, 3, "rift_shop_bell")
RIFT_SUPPLIES = Point(115, 587)
RIFT_SUPPLIES_BELL = Probe(190, 538, 220, 568, RED_DOT, 3, "rift_supplies_bell")
RIFT_BOOKS_READY = Probe(580, 775, 770, 808, GREEN_BUTTON, 3, "rift_books_ready")
RIFT_BOOKS_BUY = Point(675, 792)
RIFT_BOOKS_PARK = Point(300, 950)
# "You need N more Dark rune" pop-up: the price button stays green when unaffordable, so the
# pop-up's green OK button (client (805,595)-(1100,672)) is the stop signal.
RIFT_NEED_MORE_OK_READY = Probe(860, 640, 1040, 690, GREEN_BUTTON, 3, "rift_need_more_ok")
RIFT_NEED_MORE_OK = Point(952, 664)

# --- PTree.ahk ------------------------------------------------------------------------------
PTREE_OPEN = Point(1823, 945)  # :8
PTREE_CONFIRM = Point(960, 680)  # :18
PTREE_UPGRADE = Point(1760, 561)  # :22 (clicked twice)
PTREE_NODES = (  # (setting name, node position) in AHK order
    ("AttDmg", Point(365, 313)),
    ("AttHp", Point(512, 276)),
    ("AttArm", Point(687, 367)),
    ("Energy", Point(353, 492)),
    ("Mana", Point(511, 442)),
    ("Rage", Point(687, 534)),
    ("Miner", Point(858, 199)),
    ("Battle", Point(1061, 205)),
    ("MainAtt", Point(957, 365)),
    ("Prest", Point(963, 536)),
    ("Fire", Point(860, 696)),
    ("Gold", Point(1059, 701)),
    ("Level", Point(849, 866)),
    ("Guard", Point(1063, 867)),
    ("Fist", Point(1235, 369)),
    ("Prec", Point(1399, 276)),
    ("Magic", Point(1567, 320)),
    ("Tank", Point(1233, 535)),
    ("Damage", Point(1404, 440)),
    ("Heal", Point(1572, 492)),
)

# --- LiberationMissions.ahk / LiberationInProgressCheck.ahk ---------------------------------
LIB_DOT = Probe(1873, 920, 1900, 954, RED_DOT, 3, "lib_dot")  # :9
LIB_OPEN = Point(1800, 982)  # :11
LIB_TAB = Point(697, 788)  # :19
LIB_ALREADY_DONE = Probe(1723, 51, 1797, 123, 0xFF4805, 10, "lib_already_done")  # :34
LIB_MISSIONS_PAGE2 = (  # after 70 wheel-downs: 319, 190, 155, 110, 80 stars
    Point(1583, 755),
    Point(1191, 755),
    Point(791, 755),
    Point(412, 755),
    Point(133, 748),
)
LIB_MISSIONS_PAGE1 = (  # after 63 wheel-ups: 60, 40, 20, 10, 5 stars
    Point(1688, 755),
    Point(1291, 755),
    Point(900, 755),
    Point(517, 755),
    Point(157, 758),
)
LIB_DUNGEON = Point(1223, 794)  # :188
LIB_DUNGEON_120 = Point(1149, 763)  # :194
LIB_DUNGEON_70 = Point(768, 762)  # :209
LIB_DONE = Probe(990, 703, 1059, 737, GREEN_BUTTON, 10, "lib_done")  # InProgressCheck:5
LIB_DONE_CLAIM = Point(967, 744)  # :7
LIB_HOVER = Point(1650, 500)  # :14

# --- MapRedeem.ahk --------------------------------------------------------------------------
MR_FREE_RESET = Probe(221, 878, 277, 891, ORANGE_2, 3, "mr_free_reset")  # :13
MR_FREE_RESET_BUTTON = Point(173, 918)  # :15
MR_NO_MISSIONS = Probe(117, 249, 208, 334, 0x1452B4, 3, "mr_no_missions")  # :25
MR_MISSION_DONE = Probe(207, 305, 244, 348, GREEN_BUTTON, 3, "mr_mission_done")  # :33
MR_FIRST_MISSION = Point(162, 334)  # :35
MR_DIALOG_OK = Point(971, 628)  # :39
MR_MORE_THAN_3_MIN = Probe(1427, 730, 1481, 762, 0x916A38, 0, "mr_more_than_3_min")  # :50
MR_FREE_EARLY = Probe(1427, 730, 1481, 762, ORANGE_1, 10, "mr_free_early")  # :57
MR_FREE_EARLY_BUTTON = Point(1365, 758)  # :59
MR_SECOND_MISSION_NOT_DONE = Probe(205, 443, 242, 484, GREEN_BUTTON, 3, "mr_second_not_done")  # :71
MR_RESET_AVAILABLE = Probe(104, 878, 300, 977, 0xED00EF, 3, "mr_reset_available")  # :92
MR_RESET_BUTTON = Point(200, 930)  # :102
MR_RESET_CONFIRM = Point(961, 675)  # :108

# --- ClaimCampaign.ahk ----------------------------------------------------------------------
CAMPAIGN_ICON = Point(1857, 606)  # :10
CAMPAIGN_LOCKED = Probe(997, 310, 1305, 461, 0xF4E0C6, 2, "campaign_locked")  # :15
CAMPAIGN_CLAIM_READY = Probe(187, 926, 246, 990, GREEN_BUTTON, 3, "campaign_claim_ready")  # :21
CAMPAIGN_CLAIM = Point(165, 977)  # :23

# --- HeroUpgrade.ahk ------------------------------------------------------------------------
HU_MILESTONE_MARKER = Probe(1500, 975, 1504, 985, IDLE_TROOP, 3, "hu_milestone_marker")  # :55
HU_MILESTONE_TOGGLE = Point(
    1599, 951
)  # :60 (the "Upgrade x1 / x10 / x100 / Next milestone / max" button)
# Rework 2026-09-05: the button cycles x1 -> x10 -> x100 -> Next milestone -> max -> x1. Its
# state is read from the label text: dark pixels of the text area (logical rect below), column
# profile in 24 buckets of 10 px plus the horizontal extent, compared with these references
# (recorded live at 1920x1009).
HU_MODE_TEXT = (1480, 949, 1720, 999)
HU_MODE_ORDER = ("x1", "x10", "x100", "next", "max")
HU_MODE_PARK = Point(1200, 600)
# 2026-09-06: the classic references were recorded one click behind the cycle (the label
# of each state was the previous one, verified live on the Mac: "Upgrade max" matched the
# entry then called "next" with a distance of 0.03); keys re-labelled, values unchanged.
HU_MODE_SIGNATURES = {
    "x10": (
        (30, 211),
        (
            0.0,
            0.0,
            0.0,
            0.069,
            0.052,
            0.073,
            0.047,
            0.077,
            0.059,
            0.048,
            0.043,
            0.056,
            0.053,
            0.061,
            0.057,
            0.028,
            0.03,
            0.047,
            0.064,
            0.05,
            0.073,
            0.014,
            0.0,
            0.0,
        ),
    ),
    "x100": (
        (19, 222),
        (
            0.0,
            0.004,
            0.058,
            0.05,
            0.064,
            0.041,
            0.07,
            0.049,
            0.039,
            0.038,
            0.049,
            0.049,
            0.053,
            0.054,
            0.02,
            0.028,
            0.039,
            0.058,
            0.045,
            0.064,
            0.047,
            0.065,
            0.017,
            0.0,
        ),
    ),
    "next": (
        (11, 230),
        (
            0.0,
            0.066,
            0.062,
            0.044,
            0.034,
            0.05,
            0.033,
            0.043,
            0.023,
            0.047,
            0.047,
            0.048,
            0.054,
            0.039,
            0.038,
            0.054,
            0.045,
            0.036,
            0.055,
            0.04,
            0.042,
            0.042,
            0.055,
            0.001,
        ),
    ),
    "max": (
        (23, 218),
        (
            0.0,
            0.0,
            0.058,
            0.06,
            0.058,
            0.053,
            0.059,
            0.066,
            0.042,
            0.032,
            0.068,
            0.044,
            0.07,
            0.043,
            0.042,
            0.014,
            0.053,
            0.05,
            0.041,
            0.068,
            0.031,
            0.047,
            0.0,
            0.0,
        ),
    ),
    "x1": (
        (40, 200),
        (
            0.0,
            0.0,
            0.0,
            0.0,
            0.077,
            0.064,
            0.082,
            0.052,
            0.089,
            0.063,
            0.059,
            0.048,
            0.07,
            0.06,
            0.073,
            0.063,
            0.033,
            0.03,
            0.059,
            0.068,
            0.009,
            0.0,
            0.0,
            0.0,
        ),
    ),
}

HERO_UPGRADE_SLOTS = (  # (setting, probe rect, click point) in AHK order
    ("UpgradeSpecial", (1874, 207, 1889, 249), Point(1670, 205)),
    ("UpgradeH5", (1868, 880, 1885, 912), Point(1670, 873)),
    ("UpgradeH4", (1864, 770, 1889, 802), Point(1670, 772)),
    ("UpgradeH3", (1866, 654, 1889, 693), Point(1670, 650)),
    ("UpgradeH2", (1866, 545, 1885, 584), Point(1670, 539)),
    ("UpgradeH1", (1862, 434, 1888, 469), Point(1670, 427)),
    ("UpgradeGuardian", (1869, 319, 1890, 352), Point(1670, 317)),
)

# --- Main screen, "new adventure style" (measured 2026-09-05, client y + 31 = logical) --------
# Right column of icons (Town, Map, Guild, Shop, Events, Battle pass) at client x 1862, bells at
# the icon's top-right (+38, -30, seen on the Map icon); bottom row Sale / Bag / Fellowship /
# Party at client y 790; hero cards at client y 925, orange 0xFCAC47 card = upgradable, grey
# 0xB7B7B7 = not; blue 0x1089FF "Upgrade x1" mode button bottom right.
NS_STYLE_PROBE = Probe(1640, 946, 1800, 966, 0x1089FF, 6, "ns_style_probe")
NS_MAIL_ICON = Point(55, 606)
NS_EVENTS_ICON = Point(1862, 681)
NS_EVENTS_BELL = Probe(1885, 636, 1915, 666, RED_DOT, 3, "ns_events_bell")
NS_BP_ICON = Point(1862, 811)
NS_BP_BELL = Probe(1885, 766, 1915, 796, RED_DOT, 3, "ns_bp_bell")
NS_SHOP_ICON = Point(1862, 556)
NS_SHOP_BELL = Probe(1885, 511, 1915, 541, RED_DOT, 3, "ns_shop_bell")
NS_GUILD_ICON = Point(1862, 431)
NS_BAG_ICON = Point(1455, 821)
# The bag opens as a panel anchored at the top right (X at client 1868,68; tabs backpack /
# scroll / chests / gems at client x 1487, y 100 / 190 / 285 / 370; chest grid rows at client
# y 180-700). The chest dialog is the same as in classic but its own X (client 1413,55) is
# used instead of BigClose, which would hit the panel's X in this layout.
NS_BAG_CLOSE = Point(1868, 99)
NS_BAG_CHESTS_TAB = Point(1487, 316)
NS_CHEST_GRID = (1543, 150, 1887, 760)
NS_CHEST_DIALOG_CLOSE = Point(1413, 86)
NS_MODE_BUTTON = Point(1720, 981)
NS_MODE_TEXT = (1630, 946, 1810, 1016)  # white text on the blue button (shape only: the
# rect is re-centred on the button found in NS_MODE_SEARCH, see hero_upgrade.find_mode_button)
NS_MODE_SEARCH = (1500, 880, 1919, 1039)  # bottom-right corner where the blue button sits
NS_MODE_PARK = Point(1200, 600)
NS_HERO_CARDS = tuple(  # (setting, orange-border probe, click point), left to right
    (setting, Probe(x - 60, 893, x + 60, 903, ORANGE_2, 8, f"ns_card_{setting}"), Point(x, 956))
    for setting, x in (
        ("UpgradeH1", 165),  # leader (leftmost card)
        ("UpgradeH2", 620),
        ("UpgradeH3", 800),
        ("UpgradeH4", 980),
        ("UpgradeH5", 1160),
        ("UpgradeGuardian", 1340),
        ("UpgradeSpecial", 1520),
    )
)
NS_MODE_SIGNATURES = {  # (extent, profile) of the label's last line, logical units, 2026-09-06
    "x1": (
        (76, 102),
        [
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.133,
            0.381,
            0.287,
            0.199,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
        ],
    ),
    "x10": (
        (65, 113),
        [
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.077,
            0.204,
            0.155,
            0.186,
            0.265,
            0.112,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
        ],
    ),
    "x100": (
        (55, 123),
        [
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.057,
            0.134,
            0.128,
            0.109,
            0.181,
            0.123,
            0.182,
            0.086,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
        ],
    ),
    "next": (
        (18, 161),
        [
            0.0,
            0.016,
            0.073,
            0.071,
            0.071,
            0.089,
            0.062,
            0.065,
            0.061,
            0.06,
            0.068,
            0.076,
            0.059,
            0.064,
            0.067,
            0.088,
            0.009,
            0.0,
        ],
    ),
    "max": (
        (59, 120),
        [
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.006,
            0.172,
            0.168,
            0.132,
            0.215,
            0.125,
            0.18,
            0.002,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
        ],
    ),
}

# --- RestartGameRoutine.ahk -----------------------------------------------------------------
RESTART_HOVER = Point(900, 900)  # :56
RESTART_START_BUTTON = Probe(845, 860, 1080, 937, GREEN_BUTTON_2, 3, "restart_start_button")  # :58

# --- Main loop (firestone-bot.ahk) ------------------------------------------------------------
END_OF_CYCLE_PARK = Point(947, 755)  # MouseMove before the end-of-cycle delay

# --- MapStart.ahk ---------------------------------------------------------------------------
MAP_TROOP_IDLE = Probe(1175, 996, 1187, 1012, IDLE_TROOP, 10, "map_troop_idle")  # :179
MS_START_BUTTON = Probe(953, 822, 1205, 898, GREEN_BUTTON, 10, "ms_start_button")  # :170
MS_START = Point(1084, 865)  # :172
# Missions on the north edge of the map (2026-09-05): in a 1920x1009 client the centred map
# loses ~35 px at the top and bottom compared with the 1920x1080 canvas, so an icon whose
# centre is above logical y 100 is hidden behind the HUD (only its pin / timer shows) and a
# click there hits the squad counter. Such points are reached by dragging the map down by
# MAP_NORTH_DRAG_DY (drag on open sea, verified to move the map by exactly that amount and
# back), clicking, then dragging back.
MAP_NORTH_DRAG_LIMIT = 100  # logical y below which a point needs the drag
MAP_NORTH_DRAG_DY = 80
MAP_NORTH_DRAG_FROM = (350, 631)  # open sea south-west of Ebony Jungle (centre anchor)
# Map alignment (features/map_align.py, measured 2026-09-06): zoom slider bottom right, its
# knob's dark rim scanned on a row above the track; home = default zoom (knob at the left
# end). The mouse wheel over the map zooms (about 1.6 px of knob per notch); 30 notches down
# reach the minimum from any zoom. Landmark = the "World of Alandria" title on open sea,
# compared at half resolution with vision/map_landmark.json within +-100 logical px.
MAP_ZOOM_KNOB_ROW = (1340, 981, 1620, 985)
MAP_ZOOM_KNOB_HOME = 1374
MAP_ZOOM_TOLERANCE = 6
MAP_ZOOM_OUT_NOTCHES = 30
MAP_WHEEL_CENTRE = Point(960, 520, ANCHOR_CENTER)
MAP_LANDMARK_RECT = (310, 765, 489, 847)  # centre anchor
MAP_LANDMARK_SCALE = 0.5
MAP_LANDMARK_SEARCH = 100
# World-map mission points (x, y) per category, AHK order. The map must never be moved/zoomed.
MAP_MISSION_GROUPS: dict[str, tuple[tuple[int, int], ...]] = {
    "2 Squad": (
        (384, 1009),  # Pirate Cove
        (484, 920),  # Dragon Island
        (543, 1032),  # Hydra
        (633, 576),  # Dragon's Cave
        (616, 204),  # Frostfire Gorge
        (1150, 340),  # Irongard's Harbor
        (883, 460),  # Lake's Terror
        (1130, 546),  # Collect The Bounty
        (836, 1039),  # Open Sea
        (970, 810),  # Orc Lieutenant
        (1486, 770),  # Ships On Fire
        (1255, 853),  # Trade Route
        (1533, 98),
        (1608, 119),
        (1534, 123),
        (1440, 140),
        (1207, 32),
        (1290, 99),
        (1177, 35),
        (1104, 43),
        (1300, 26),  # Eastrock volcano island, north edge (timed mission, hidden; 2026-09-05)
        (
            484,
            166,
        ),  # Frostfire north-west, "Visit the Northern Tribes" (2 squads, timed; 2026-09-04)
    ),
    "War": (
        (672, 423),  # Tipsy Wisp Tavern
        (720, 675),  # Ambush in the Trees
        (780, 845),  # Stop The Pirate Raids
        (812, 637),  # Xandor Dock
        (849, 794),  # Protect The Fishermen
        (910, 759),  # Confront The Orcs
        (929, 609),  # Moonglen's Festival
        (980, 228),  # North Sea
        (1017, 426),  # Recruit Soldiers
        (1055, 780),  # The Pit
        (1145, 626),  # Protect The Shore
        (1152, 969),  # Sea Monsters
        (1224, 312),  # Free The Prisoners
        (1228, 550),  # Forest Rangers
        (1252, 392),  # Mission To Bayshire
        (1326, 798),  # Train Elf Archers
        (1424, 777),  # Chase the Monster
        (1452, 498),  # Defend Mythshore
    ),
    "Medium": (
        (463, 433),
        (460, 670),
        (502, 330),  # Snow Wolves (AHK position)
        (
            445,
            321,
        ),  # Snow Wolves as placed by the game on 2026-09-05 (icon 57 px west of the AHK point)
        (581, 295),  # Expose the Spy
        (671, 755),  # Cursed Bay
        (705, 592),  # The Lost Chapter
        (797, 504),  # Visit the Abbey
        (867, 543),  # Calamindor Ruins
        (1041, 518),  # Silverwood's Militia
        (1044, 676),  # The Resistance of Goldeff
        (1314, 306),  # Firestone Power
        (1340, 545),  # Explore Hinterlands
        (1435, 683),  # Library of Talamer
        (1438, 871),
        (1442, 418),  # Close The Portal
        (1481, 261),  # Dreadland Shore
    ),
    "Short": (
        (556, 500),  # Jungle Terror
        (655, 357),  # The Hombor King
        (712, 517),
        (733, 229),  # Dark Cavern
        (828, 375),  # Riverside
        (874, 664),  # Escort the Merchants
        (884, 233),  # Stormspire Accident
        (1099, 894),  # The Port of Thal Badur
        (1162, 454),  # Find the Librarian
        (1224, 463),  # Dark River
        (1276, 694),  # Border Patrol
        (1297, 193),  # Search For Survivors
        (1357, 429),
        (1364, 646),  # Watchtower
        (1394, 355),  # Retrieve Water Sample
        (1460, 580),  # Search The Shipwreck
    ),
    "Leftover": (
        (923, 369),
        (538, 190),
        (1221, 467),
        (742, 389),
        (967, 547),
    ),
}


# -- account / guild level (progress.py, measured on the Mac 2026-09-06 at 16:9) ---------------
# Logical rects (x1, y1, x2, y2), top-left anchored, read by vision/digits.py.
ACCOUNT_LEVEL_REGION = (80, 130, 145, 178)  # white level number on the avatar, main screen
GUILD_LEVEL_REGION = (193, 122, 480, 152)  # "Guild level 24" bar under the guild name, guild map


# -- generic dialog close button (fast timing waits, 2026-09-06) -------------------------------
# The orange circle with a cream X at the top right of every full-screen dialog (town, guild
# map, shop...). Its centre is cream-white; on the main screen the settings gear sits there
# with a hole in the middle (pink background), so the probe tells "a dialog is open" from
# "main screen". Measured on the Mac (town X centre 255,249,206; gear 225,151,66).
DIALOG_CLOSE_X = Probe(1849, 81, 1858, 90, 0xFFF9CE, 30, "dialog_close_x")
# Dialogs whose X sits elsewhere (entry probes for `expect=` / open_screen, measured on the
# Mac 2026-09-06). They look at the orange ring 20 logical px left of the cross centre: the
# cream centre alone matched cream text and icons of the main screen, the orange never does.
# Centred dialogs use the centre anchor.
DIALOG_RING = 0xFF6109
MAIL_CLOSE_X = Probe(1588, 71, 1592, 75, DIALOG_RING, 20, "mail_close_x", ANCHOR_CENTER)
BAG_CLOSE_X = Probe(
    1888, 93, 1892, 97, DIALOG_RING, 20, "bag_close_x"
)  # right of the cross: the town X is close by
# Classic style: the bag panel sits lower (its X at logical (1870, 259); measured 2026-09-06)
BAG_CLOSE_X_CLASSIC = Probe(1888, 257, 1892, 261, DIALOG_RING, 20, "bag_close_x_classic")
EVENTS_CLOSE_X = Probe(1467, 75, 1471, 79, DIALOG_RING, 20, "events_close_x", ANCHOR_CENTER)
BP_CLOSE_X = Probe(1857, 124, 1861, 128, DIALOG_RING, 20, "bp_close_x")
TAVERN_CLOSE_X = Probe(1293, 248, 1297, 252, DIALOG_RING, 20, "tavern_close_x", ANCHOR_CENTER)
