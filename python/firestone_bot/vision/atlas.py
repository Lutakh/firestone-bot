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

# --- ClaimBeer.ahk / UseTavernToken.ahk / CraftArtifact.ahk -----------------------------------
TAVERN_BEER_TAB = Point(773, 500)  # ClaimBeer.ahk:18
TAVERN_TOKEN_SHOP = Point(1735, 69)  # :23
TAVERN_BEER_CLAIM_READY = Probe(616, 610, 697, 656, 0xFFBB33, 3, "tavern_beer_claim")  # :27
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
    ("Firecracker", 0xEA4019),
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
    "Health": ("health",),
    "Armor": ("armor",),
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

# --- MapStart.ahk (partial; the rest comes with the map_start port) -------------------------
MAP_TROOP_IDLE = Probe(1175, 996, 1187, 1012, IDLE_TROOP, 10, "map_troop_idle")  # :179
