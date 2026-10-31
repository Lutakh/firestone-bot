"""A scene bench for the world map's mission popups (a helper module: pytest does not collect
it).

Real crops of game 9.1.3a (the owner's 1920x1009 Epic client, 2026-10-29/30; fixture
mission-popups-913a.npz) are drawn at any client shape by a model that knows nothing of the
atlas or the Viewport, so a wrong anchor in the bot fails here:

- canvas scale s = min(W / 1920, H / 1080), k = s / (1009 / 1080): the size of one reference
  client px (the captures') on the client;
- popups and map are centred horizontally: x' = W / 2 + (x - 960) k;
- vertically, at 16:9 and wider every anchor gives y' = y k (the canvas fills the client's
  height); on a client taller than 16:9 the popups' placement was never seen, so both are
  drawn: held at the canvas centre (y' = H / 2 + (y - 504.5) k) or at the top (y' = y k);
- the client sits at `origin` inside a larger screen (desktop grey around it, like mss).

The fixture (cut from the diagnostics captures, client px of the 1920x1009 client):
- start: 20261029-225856-mission-start-popup.png, x 398..1532, y 118..900;
- paid: 20261029-230202-mission-in-progress.png (red Cancel, Speed up with a gem), x 398..1532,
  y 118..798;
- free_rows: 20261030-230623-mission-paid-speed-up.png (grey Cancel, orange "Free", no gem;
  saved as "paid" while free speed-ups were off for the run), x 398..1532, y 560..798: drawn
  over the paid popup's rows (the header is the reader's business only through its frame);
- rewards: 20261030-225622-mission-gem-dialog.png (Mission Rewards, a purple mystery box),
  x 410..1510, y 118..684;
all BGRA at half resolution (2x2 block means), alpha 0 outside the panel's frame, the
medallion, the X and the ribbon (the map behind belongs to the scene); map:
20261029-233300-map-no-icon.png (missions running, the list, the idle banner), the whole
client at a quarter (4x4 block means), BGR.

A click is answered by a model of the game: Start inside the true green rect starts the
mission and closes the panel, the free orange button opens the Mission Rewards, Okay closes
them, the X closes the panel and so does a tap outside it; a paid orange button, a Cancel or a
reward tile pressed is recorded as a fault, also on a popup that takes no click (`stuck`);
anything else does nothing. A map or list click while a panel is open is a fault too, and so
is a tap meant for a popup with none open (it lands on the map). A drag moves the map. The
real Game runs on it (SceneGame): its captures, input, window and clock are the scene's.

Looks of another interface style (a game update, a style never captured) are the same crops
with red and blue swapped (`reskin`): the reader cannot see them, the centre's look can.
Scenes that change with the virtual clock or with the bot's reads (a price drawn late, a
popup that opens late, a panel missing from a capture) are the subclasses at the end.
"""

from __future__ import annotations

import time as _time
from collections import OrderedDict
from dataclasses import dataclass, field, replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from firestone_bot import game as game_mod
from firestone_bot.features import map_close
from firestone_bot.game import Game
from firestone_bot.platform import capture
from firestone_bot.platform.types import Rect, WindowInfo
from firestone_bot.settings import Settings
from firestone_bot.vision import atlas, mission_popup

REF_W, REF_H = 1920, 1009
S0 = REF_H / 1080
SEA = (146, 66, 17)  # BGR, open sea
DESKTOP = (40, 40, 40)
FIXTURE = Path(__file__).parent / "fixtures" / "mission-popups-913a.npz"

# Client shapes (w, h). Taller than 16:9: both placements of the popups.
SHAPES = [
    (1920, 1009),  # the owner's, maximised on a 1080p screen (Epic)
    (1920, 1017),  # report G8N62Y (Steam)
    (1920, 1080),
    (1280, 720),
    (1366, 768),
    (2560, 1440),
    (3840, 2160),
    (1920, 1200),
    (1680, 1050),
    (1600, 1200),
    (1280, 1024),
    (2560, 1080),
    (3440, 1440),
    (3024, 1964),  # a MacBook's built-in display, fullscreen
    (800, 600),
]
OFFSET = ((1600, 1000), (160, 90), (2560, 1440))  # client, its origin, the screen around it


def taller(w: int, h: int) -> bool:
    return w * 9 < h * 16


def placements(w: int, h: int) -> tuple[str, ...]:
    return ("centre", "top") if taller(w, h) else ("centre",)


def cases(shapes=SHAPES) -> list[tuple[int, int, str]]:
    return [(w, h, p) for w, h in shapes for p in placements(w, h)]


def k_of(w: int, h: int) -> float:
    return min(w / 1920, h / 1080) / S0


# --- the popups, reference client px (x2, y2 exclusive), measured on the 1:1 captures ----
@dataclass(frozen=True)
class Look:
    """A popup as drawn: its fixture layers and its parts by role ("deadx": an X drawn that
    takes no tap)."""

    layers: tuple[tuple[str, tuple[int, int, int, int]], ...]  # (fixture key, ref rect)
    panel: tuple[int, int, int, int]
    parts: dict = field(default_factory=dict)  # role -> rect or list of rects
    edits: tuple = ()  # (rect, BGR) painted over the crop, in ref px
    reskin: bool = False  # the popup's pixels with red and blue swapped (another style)
    popup: bool = True  # False: map art, not a mission popup (no panel to read or close)


X_RING = (1464, 173, 1529, 238)
X_AREA = (1460, 166, 1532, 242)  # the X as cut from the start popup (fixture "start-x")
START_TILES = [(804, 580, 892, 670), (916, 580, 1004, 670), (1028, 580, 1116, 670)]
PROGRESS_TILES = [(804, 438, 892, 528), (916, 438, 1004, 528), (1028, 438, 1116, 528)]
REWARD_TILES = [(755, 390, 875, 512), (899, 390, 1019, 512), (1043, 390, 1167, 512)]
START_LAYERS = (("start", (398, 118, 1532, 900)),)
PAID_LAYERS = (("paid", (398, 118, 1532, 798)),)
FREE_LAYERS = (("paid", (398, 118, 1532, 798)), ("free_rows", (398, 560, 1532, 798)))
REWARDS_LAYERS = (("rewards", (410, 118, 1510, 684)),)
START_GREEN = (958, 798, 1209, 881)
START_ORANGE = (1235, 796, 1492, 885)  # Complete instantly
PAID_ORANGE = (1235, 695, 1492, 784)  # the paid Speed up
FREE_BUTTON = (1235, 695, 1492, 787)  # the free layout's orange "Free" (fixture "free-button")
OKAY = (805, 567, 1115, 638)
GEM_PURPLE = (0x9D, 0x00, 0x9F)  # the measured gem 0x9F009D, BGR
GREEN = (8, 160, 11)  # a Start / Okay (11,160,8), BGR
ORANGE = (66, 155, 242)  # an orange button's body (242,155,66), BGR
CREAM = (173, 206, 225)  # the panels' frame (225,206,173), BGR
PARCHMENT = (129, 165, 203)  # inside a start popup (203,165,129), BGR
REWARDS_INSIDE = (160, 200, 220)  # the Mission Rewards' light inside around its Okay, BGR
# The canvas is 1920 * S0 reference px wide at every client shape (k scales both)
CANVAS_REF_W = 1920 * S0


def shifted(look: Look, dy: int) -> Look:
    """`look` drawn `dy` reference px lower (a popup still moving as it settles)."""

    def mv(r):
        return (r[0], r[1] + dy, r[2], r[3] + dy)

    parts = {
        role: [mv(r) for r in rects] if isinstance(rects, list) else mv(rects)
        for role, rects in look.parts.items()
    }
    return Look(
        tuple((name, mv(r)) for name, r in look.layers),
        mv(look.panel),
        parts,
        tuple((mv(r), bgr) for r, bgr in look.edits),
        look.reskin,
        look.popup,
    )


def centred_box(w_share: float, aspect: float, cy: float = 504.5) -> tuple[int, int, int, int]:
    """A rect `w_share` of the canvas wide, `aspect` times as wide as tall, centred on the
    client's middle column at reference y `cy`."""
    w = w_share * CANVAS_REF_W
    h = w / aspect
    return (round(960 - w / 2), round(cy - h / 2), round(960 + w / 2), round(cy + h / 2))


LOOKS = {
    "start": Look(
        START_LAYERS,
        (411, 187, 1509, 897),
        {
            "start": START_GREEN,
            "paid": (1235, 796, 1492, 885),
            "tile": START_TILES,
            "x": X_RING,
        },
    ),
    # a gem in the Start: never pressed
    "start-gem": Look(
        START_LAYERS,
        (411, 187, 1509, 897),
        {"paid": [START_GREEN, (1235, 796, 1492, 885)], "tile": START_TILES, "x": X_RING},
        edits=(((1060, 820, 1094, 854), GEM_PURPLE),),
    ),
    # a white label row across the whole Complete instantly ("Complete instantly" fills its
    # band from end to end): the button reads as two parts, one over the other
    "start-split": Look(
        START_LAYERS,
        (411, 187, 1509, 897),
        {
            "start": START_GREEN,
            "paid": (1235, 796, 1492, 885),
            "tile": START_TILES,
            "x": X_RING,
        },
        edits=(((1238, 836, 1490, 851), (255, 255, 255)),),
    ),
    # a start popup whose Start takes no press (a hitch of the game): only its X closes it
    "start-deaf": Look(
        START_LAYERS,
        (411, 187, 1509, 897),
        {"dead": START_GREEN, "paid": (1235, 796, 1492, 885), "tile": START_TILES, "x": X_RING},
    ),
    # a Start drawn dark (not enough squads?): not a start popup the bot knows
    "start-dark": Look(
        START_LAYERS,
        (411, 187, 1509, 897),
        {"dead": START_GREEN, "paid": (1235, 796, 1492, 885), "tile": START_TILES, "x": X_RING},
        edits=((START_GREEN, (70, 70, 70)),),
    ),
    "paid": Look(
        PAID_LAYERS,
        (411, 187, 1509, 796),
        {
            "cancel": (955, 695, 1211, 783),
            "paid": (1235, 695, 1492, 784),
            "tile": PROGRESS_TILES,
            "x": X_RING,
        },
    ),
    # the frame's right side covered under the X, the left one under the ribbon: the header
    # holds to the body by nothing (map art over a thin frame, a colour cast at 1680x1050)
    "paid-cut": Look(
        PAID_LAYERS,
        (411, 187, 1509, 796),
        {
            "cancel": (955, 695, 1211, 783),
            "paid": (1235, 695, 1492, 784),
            "tile": PROGRESS_TILES,
            "x": X_RING,
        },
        edits=(((1486, 238, 1509, 340), SEA), ((411, 268, 434, 340), SEA)),
    ),
    "free": Look(
        FREE_LAYERS,
        (411, 187, 1509, 796),
        {
            "cancel": (955, 695, 1212, 784),
            "free": (1235, 695, 1492, 787),
            "tile": PROGRESS_TILES,
            "x": X_RING,
        },
    ),
    # the free layout with a gem drawn on its orange button: paid after all
    "free-gem": Look(
        FREE_LAYERS,
        (411, 187, 1509, 796),
        {
            "cancel": (955, 695, 1212, 784),
            "paid": (1235, 695, 1492, 787),
            "tile": PROGRESS_TILES,
            "x": X_RING,
        },
        edits=(((1306, 744, 1340, 776), GEM_PURPLE),),
    ),
    "rewards": Look(REWARDS_LAYERS, (416, 187, 1504, 680), {"okay": OKAY, "tile": REWARD_TILES}),
    # a price in the Okay: never pressed
    "rewards-priced": Look(
        REWARDS_LAYERS,
        (416, 187, 1504, 680),
        {"paid": OKAY, "tile": REWARD_TILES},
        edits=(((1040, 585, 1072, 617), GEM_PURPLE),),
    ),
    # a gem just under the Okay, in its row (0.02 W around it): a price, never pressed
    "rewards-priced-under": Look(
        REWARDS_LAYERS,
        (416, 187, 1504, 680),
        {"paid": OKAY, "tile": REWARD_TILES},
        edits=(((1040, 641, 1074, 655), GEM_PURPLE),),
    ),
    # a second green button beside the Okay: a choice, not the Mission Rewards
    "rewards-two": Look(
        REWARDS_LAYERS,
        (416, 187, 1504, 680),
        {"paid": [OKAY, (1150, 567, 1400, 638)], "tile": REWARD_TILES},
        edits=(((1150, 567, 1400, 638), (8, 160, 11)),),
    ),
    # one green button of a Start's width: not the Mission Rewards' Okay
    "rewards-narrow": Look(
        REWARDS_LAYERS,
        (416, 187, 1504, 680),
        {"paid": OKAY, "tile": REWARD_TILES},
        edits=(
            ((805, 562, 835, 642), (153, 196, 219)),
            ((1085, 562, 1115, 642), (153, 196, 219)),
        ),
    ),
    # the Mission Rewards' look with an X at its corner: a dialog the bot does not know
    "rewards-x": Look(
        (*REWARDS_LAYERS, ("start-x", X_AREA)),
        (416, 187, 1504, 680),
        {"paid": OKAY, "tile": REWARD_TILES, "x": X_RING},
    ),
    # a start popup whose Complete instantly shows no price at all: the free layout's orange
    # "Free" drawn in its place (never captured; a mission under 3 minutes might show it)
    "start-unpriced": Look(
        (*START_LAYERS, ("free-button", (1235, 793, 1492, 885))),
        (411, 187, 1509, 897),
        {"start": START_GREEN, "paid": (1235, 793, 1492, 885), "tile": START_TILES, "x": X_RING},
    ),
    # the same without its X (painted over: the header's cream inside the panel, the map
    # outside): an unpriced orange beside a green is no start popup without it
    "start-unpriced-nox": Look(
        (*START_LAYERS, ("free-button", (1235, 793, 1492, 885))),
        (411, 187, 1509, 897),
        {"paid": [START_GREEN, (1235, 793, 1492, 885)], "tile": START_TILES},
        edits=(
            ((1460, 187, 1509, 242), CREAM),
            ((1460, 160, 1534, 187), SEA),
            ((1509, 187, 1534, 242), SEA),
        ),
    ),
    # an unpriced orange, the X, and a green 0.3 W wide: not a Start (0.23 measured)
    "start-unpriced-wide": Look(
        (*START_LAYERS, ("free-button", (1235, 793, 1492, 885))),
        (411, 187, 1509, 897),
        {"paid": [(883, 798, 1209, 881), (1235, 793, 1492, 885)], "tile": START_TILES, "x": X_RING},
        edits=(((883, 798, 958, 881), GREEN),),
    ),
    # the Complete instantly's gem not drawn (painted orange), its brown label band kept: a
    # price the reader misses, never a start popup
    "start-label-only": Look(
        START_LAYERS,
        (411, 187, 1509, 897),
        {"paid": [START_GREEN, START_ORANGE], "tile": START_TILES, "x": X_RING},
        edits=(((1296, 838, 1350, 884), ORANGE),),
    ),
    # an orange with a gem left of a green: not the start popup's order
    "start-swapped": Look(
        START_LAYERS,
        (411, 187, 1509, 897),
        {"paid": [START_GREEN, START_ORANGE], "tile": START_TILES, "x": X_RING},
        edits=(
            (START_GREEN, ORANGE),
            ((1060, 822, 1094, 856), GEM_PURPLE),
            ((1238, 798, 1490, 882), GREEN),
        ),
    ),
    # the Start raised out of the Complete instantly's row: buttons stacked, not side by side
    "start-stacked": Look(
        START_LAYERS,
        (411, 187, 1509, 897),
        {"paid": [(958, 725, 1209, 795), START_ORANGE], "tile": START_TILES, "x": X_RING},
        edits=((START_GREEN, PARCHMENT), ((958, 725, 1209, 795), GREEN)),
    ),
    # the Start 0.13 W tall (up into the time band): too tall for a button (0.11 W at most)
    "start-tall": Look(
        START_LAYERS,
        (411, 187, 1509, 897),
        {"paid": [(958, 738, 1209, 881), START_ORANGE], "tile": START_TILES, "x": X_RING},
        edits=(((958, 738, 1209, 881), GREEN),),
    ),
    # a green, then two oranges, side by side: not the start popup's two buttons
    "start-three": Look(
        START_LAYERS,
        (411, 187, 1509, 897),
        {
            "paid": [(560, 798, 811, 881), (840, 798, 1091, 881), (1120, 798, 1371, 881)],
            "tile": START_TILES,
            "x": X_RING,
        },
        edits=(
            ((940, 792, 1500, 888), PARCHMENT),
            ((560, 798, 811, 881), GREEN),
            ((840, 798, 1091, 881), ORANGE),
            ((1120, 798, 1371, 881), ORANGE),
        ),
    ),
    # no Complete instantly at all (parchment over it): a lone green beside nothing
    "start-no-orange": Look(
        START_LAYERS,
        (411, 187, 1509, 897),
        {"paid": START_GREEN, "tile": START_TILES, "x": X_RING},
        edits=(((1230, 790, 1498, 892), PARCHMENT),),
    ),
    # the paid Speed up with its gem not drawn (painted orange): its brown label band shows
    # the price
    "paid-label-only": Look(
        PAID_LAYERS,
        (411, 187, 1509, 796),
        {"cancel": (955, 695, 1211, 783), "paid": PAID_ORANGE, "tile": PROGRESS_TILES, "x": X_RING},
        edits=(((1298, 738, 1348, 782), ORANGE),),
    ),
    # the paid layout with no price seen in its orange (label band and gem painted orange):
    # only its red Cancel says more than 3 minutes
    "paid-plain": Look(
        PAID_LAYERS,
        (411, 187, 1509, 796),
        {"cancel": (955, 695, 1211, 783), "paid": PAID_ORANGE, "tile": PROGRESS_TILES, "x": X_RING},
        edits=(((1240, 700, 1488, 746), ORANGE), ((1298, 738, 1348, 782), ORANGE)),
    ),
    # a green box and the Cancel left of the orange: two buttons where one stands
    "paid-green-cancel": Look(
        PAID_LAYERS,
        (411, 187, 1509, 796),
        {
            "paid": [(680, 695, 930, 783), PAID_ORANGE],
            "cancel": (955, 695, 1211, 783),
            "tile": PROGRESS_TILES,
            "x": X_RING,
        },
        edits=(((680, 695, 930, 783), GREEN),),
    ),
    # the paid in-progress popup whose X takes no tap: the second close tap is the one beside it
    "paid-deadx": Look(
        PAID_LAYERS,
        (411, 187, 1509, 796),
        {
            "cancel": (955, 695, 1211, 783),
            "paid": PAID_ORANGE,
            "tile": PROGRESS_TILES,
            "deadx": X_RING,
        },
    ),
    # the Mission Rewards' look with two orange buttons beside its Okay: not the Mission Rewards
    "rewards-three": Look(
        REWARDS_LAYERS,
        (416, 187, 1504, 680),
        {"paid": [OKAY, (470, 600, 740, 672), (1180, 600, 1450, 672)], "tile": REWARD_TILES},
        edits=(((470, 600, 740, 672), ORANGE), ((1180, 600, 1450, 672), ORANGE)),
    ),
    # a red Cancel beside its Okay: a confirmation, not the Mission Rewards
    "rewards-cancel": Look(
        REWARDS_LAYERS,
        (416, 187, 1504, 680),
        {"paid": OKAY, "cancel": (480, 567, 760, 638), "tile": REWARD_TILES},
        edits=(((480, 567, 760, 638), (60, 66, 231)),),
    ),
    # its Okay a green frame round nothing: two bars, 0.37 of the box green (BUTTON_FILL 0.45)
    "rewards-hollow": Look(
        REWARDS_LAYERS,
        (416, 187, 1504, 680),
        {"paid": OKAY, "tile": REWARD_TILES},
        edits=(
            (OKAY, REWARDS_INSIDE),
            ((805, 567, 1115, 580), GREEN),
            ((805, 625, 1115, 638), GREEN),
        ),
    ),
    # its Okay off the panel's centre (0.09 W)
    "rewards-offcentre": Look(
        REWARDS_LAYERS,
        (416, 187, 1504, 680),
        {"paid": (905, 567, 1215, 638), "tile": REWARD_TILES},
        edits=((OKAY, REWARDS_INSIDE), ((905, 567, 1215, 638), GREEN)),
    ),
    # its Okay too tall for the Okay (0.095 W), not for a button
    "rewards-tall": Look(
        REWARDS_LAYERS,
        (416, 187, 1504, 680),
        {"paid": (805, 535, 1115, 638), "tile": REWARD_TILES},
        edits=(((805, 535, 1115, 638), GREEN),),
    ),
    # map art, not popups: a small centred cream dialog (0.25 of the canvas, PANEL_MIN_W 0.35)
    # and a long centred cream bar (a longer idle banner: aspect 14, PANEL_ASPECT up to 2.8)
    "cream-box": Look(
        (), centred_box(0.25, 2.0), edits=((centred_box(0.25, 2.0), CREAM),), popup=False
    ),
    "cream-bar": Look(
        (), centred_box(0.4, 14.0), edits=((centred_box(0.4, 14.0), CREAM),), popup=False
    ),
    # and a cream screen as wide as the canvas (0.98: PANEL_MAX_W 0.95)
    "cream-full": Look(
        (), centred_box(0.98, 1.8), edits=((centred_box(0.98, 1.8), CREAM),), popup=False
    ),
}
# another interface style: the reader cannot see these, the centre's look can
for _name in ("start", "paid", "rewards"):
    LOOKS[_name + "+rb"] = replace(LOOKS[_name], reskin=True)
# the free popup 30 px higher: two reads of a popup still settling disagree
LOOKS["free-up"] = shifted(LOOKS["free"], -30)
# The map's art that could join a panel or pass for a button, drawn under the popups next to
# them (reference px, BGR): the desert's parchment under a popup (the in-progress capture),
# an island's cream sand against its side, a green field and an orange icon just below it.
UNDER = (
    ((850, 797, 1210, 940), (125, 160, 203)),
    ((1509, 420, 1560, 640), (173, 206, 225)),
    ((1240, 900, 1300, 935), (8, 160, 11)),
    ((560, 905, 640, 935), (66, 155, 242)),
)
# A map icon's stars drawn over the X's ring (the start capture: the ring's top hidden)
OVER = (
    ((1488, 162, 1500, 176), (255, 255, 255)),
    ((1505, 164, 1517, 178), (255, 255, 255)),
)


_FIX: dict[str, np.ndarray] | None = None
# Images drawn, the most recent kept within a memory budget: the scenes of one client shape
# share their map and popups (a 4K client image is 25 MB)
_DRAWN: OrderedDict[tuple, np.ndarray] = OrderedDict()
DRAWN_BYTES = 320 * 1024 * 1024


def fixture(key: str) -> np.ndarray:
    global _FIX
    if _FIX is None:
        with np.load(FIXTURE) as z:
            _FIX = {k: z[k] for k in z.files}
        # the start popup's X alone, to draw on another popup (half resolution)
        x1, y1, x2, y2 = X_AREA  # x2: the start crop's right edge
        _FIX["start-x"] = _FIX["start"][
            (y1 - 118) // 2 : (y2 - 118) // 2, (x1 - 398) // 2 : (x2 - 398) // 2
        ]
        # the free layout's orange "Free" alone, to draw on the start popup
        x1, y1, x2, y2 = FREE_BUTTON
        _FIX["free-button"] = _FIX["free_rows"][
            (y1 - 560) // 2 : (y2 - 560) // 2, (x1 - 398) // 2 : (x2 - 398) // 2
        ]
    return _FIX[key]


def _cached(key: tuple, draw) -> np.ndarray:
    if key in _DRAWN:
        _DRAWN.move_to_end(key)
        return _DRAWN[key]
    img = draw()
    _DRAWN[key] = img
    while len(_DRAWN) > 1 and sum(a.nbytes for a in _DRAWN.values()) > DRAWN_BYTES:
        _DRAWN.popitem(last=False)
    return img


# --- resampling ---------------------------------------------------------------------------
def resample(src: np.ndarray, x0: float, y0: float, step: float, w: int, h: int, mode: str):
    """Target pixel (row i, column j) shows the source around (x0 + (j + 0.5) step,
    y0 + (i + 0.5) step) (source pixel n spans [n, n + 1); `step`: source px per target px).
    nearest: that source pixel; smooth: bilinear when enlarging, the footprint's mean when
    reducing. One axis after the other; float32 (h, w, channels) out."""
    src = src.astype(np.float32)
    xs = x0 + (np.arange(w) + 0.5) * step
    ys = y0 + (np.arange(h) + 0.5) * step
    cols = _resample_axis(src, xs, step, mode, axis=1)
    return _resample_axis(cols, ys, step, mode, axis=0)


def _resample_axis(src: np.ndarray, at: np.ndarray, step: float, mode: str, axis: int):
    n = src.shape[axis]
    if mode == "nearest":
        return np.take(src, np.clip(np.floor(at).astype(int), 0, n - 1), axis=axis)
    shape = [1, 1, 1]
    shape[axis] = len(at)
    if step <= 1:
        u = at - 0.5
        u0 = np.floor(u)
        f = (u - u0).astype(np.float32).reshape(shape)
        a = np.take(src, np.clip(u0.astype(int), 0, n - 1), axis=axis)
        b = np.take(src, np.clip(u0.astype(int) + 1, 0, n - 1), axis=axis)
        a *= 1 - f  # in place: a and b are copies
        b *= f
        a += b
        return a
    zero = np.zeros_like(np.take(src, [0], axis=axis), dtype=np.float64)
    integral = np.concatenate([zero, src.cumsum(axis=axis, dtype=np.float64)], axis=axis)
    lo = np.clip(np.round(at - step / 2).astype(int), 0, n - 1)
    hi = np.clip(np.maximum(np.round(at + step / 2).astype(int), lo + 1), 1, n)
    total = np.take(integral, hi, axis=axis) - np.take(integral, lo, axis=axis)
    return (total / (hi - lo).reshape(shape)).astype(np.float32)


@dataclass(frozen=True)
class SBox:
    """A screen rect, float bounds (x2, y2 exclusive)."""

    x1: float
    y1: float
    x2: float
    y2: float

    def contains(self, x: float, y: float, inset: float = 0.0) -> bool:
        dx = max(inset * (self.x2 - self.x1), 2.0) if inset else 0.0
        dy = max(inset * (self.y2 - self.y1), 2.0) if inset else 0.0
        return self.x1 + dx <= x + 0.5 <= self.x2 - dx and self.y1 + dy <= y + 0.5 <= self.y2 - dy


class Scene:
    """The map and the popup the game shows, at a client of w x h at `origin` on a screen of
    `screen` (w, h) px."""

    def __init__(
        self,
        w: int,
        h: int,
        placement: str = "centre",
        mode: str = "nearest",
        origin: tuple[int, int] = (0, 0),
        screen: tuple[int, int] | None = None,
        cast: tuple[int, int, int] = (0, 0, 0),
        distractors: bool = True,
    ):
        self.w, self.h = w, h
        self.k = k_of(w, h)
        self.placement = placement
        self.mode = mode
        self.cast = np.array(cast, np.float32)  # BGR added to every pixel (a colour cast)
        self.client = Rect(origin[0], origin[1], w, h)
        sw, sh = screen or (origin[0] + w, origin[1] + h)
        self.screen_size = (sw, sh)
        self.ox = w / 2 - 960 * self.k  # client x of reference x 0
        self.oy = h / 2 - 504.5 * self.k if placement == "centre" else 0.0
        self.distractors = distractors
        # the game
        self.popup: str | None = None
        self.queue: list[str] = []  # popups the next map clicks open
        self.list_queue: list[str] = []  # popups the taps on the list's first card open
        self.stuck = False  # the open popup takes no click
        self.idle = 0  # idle squads
        self.squads = 2  # a start takes this many
        self.after_free = "rewards"  # what the free speed-up opens
        self.map_offset = 0  # logical px the map was dragged down
        # MR_NO_MISSIONS: the real probe never matches the sea of game 9.1.3a (BACKLOG "Any
        # screen shape"), so a visit with no running mission taps the list's place; True: a
        # probe that matches an empty list (older versions)
        self.no_missions_probe = False
        self.source: str | None = None  # "map" / "list" while the bot clicks one of those
        self.pointer = (0, 0)
        self.events: list[tuple] = []  # (what, x, y, popup)
        self.faults: list[str] = []
        self.started = self.claimed = self.speed_ups = self.closed_x = self.closed_out = 0
        self.clock: Clock | None = None  # the virtual clock (scene_game)
        self.reads = 0  # the bot's reads of the client (Game.client_image)

    # geometry -----------------------------------------------------------------------------
    def to_screen(self, rect) -> SBox:
        x1, y1, x2, y2 = rect
        cx, cy = self.client.x, self.client.y
        return SBox(
            cx + self.ox + x1 * self.k,
            cy + self.oy + y1 * self.k,
            cx + self.ox + x2 * self.k,
            cy + self.oy + y2 * self.k,
        )

    def part(self, role: str, popup: str | None = None) -> list[SBox]:
        look = LOOKS[popup or self.popup]
        rects = look.parts.get(role, [])
        if isinstance(rects, tuple):
            rects = [rects]
        return [self.to_screen(r) for r in rects]

    def panel(self, popup: str | None = None) -> SBox:
        return self.to_screen(LOOKS[popup or self.popup].panel)

    # drawing ------------------------------------------------------------------------------
    def _draw(self, img: np.ndarray, ref_rect, f: float, src: np.ndarray) -> None:
        """Draw a layer of reference rect `ref_rect`, `f` source px per reference px, on the
        client image `img` (uint8 BGR): over it through its alpha (BGRA), or in place (BGR)."""
        x1, y1, x2, y2 = ref_rect
        k = self.k
        tx1 = max(0, int(np.floor(self.ox + x1 * k)))
        ty1 = max(0, int(np.floor(self.oy + y1 * k)))
        tx2 = min(self.w, int(np.ceil(self.ox + x2 * k)))
        ty2 = min(self.h, int(np.ceil(self.oy + y2 * k)))
        if tx2 <= tx1 or ty2 <= ty1:
            return
        step = f / k
        sx0 = ((tx1 - self.ox) / k - x1) * f
        sy0 = ((ty1 - self.oy) / k - y1) * f
        w, h = tx2 - tx1, ty2 - ty1
        # nothing of the layer falls outside its rect
        xs = (np.arange(tx1, tx2) + 0.5 - self.ox) / k
        ys = (np.arange(ty1, ty2) + 0.5 - self.oy) / k
        if self.mode == "nearest":  # uint8 all through: the 4K scenes stay quick
            inside = (((ys >= y1) & (ys < y2))[:, None] & ((xs >= x1) & (xs < x2))[None, :])[
                ..., None
            ]
            sh, sw = src.shape[:2]
            xi = np.clip(np.floor(sx0 + (np.arange(w) + 0.5) * step).astype(int), 0, sw - 1)
            yi = np.clip(np.floor(sy0 + (np.arange(h) + 0.5) * step).astype(int), 0, sh - 1)
            out = np.take(np.take(src, xi, axis=1), yi, axis=0)
            keep = inside & (out[..., 3:] >= 128) if src.shape[2] == 4 else inside
            np.copyto(img[ty1:ty2, tx1:tx2], out[..., :3], where=keep)
            return
        # the rows and columns inside (a range of each), blended in place
        rows = np.flatnonzero((ys >= y1) & (ys < y2))
        cols = np.flatnonzero((xs >= x1) & (xs < x2))
        if not len(rows) or not len(cols):
            return
        r0, r1, c0, c1 = rows[0], rows[-1] + 1, cols[0], cols[-1] + 1
        target = img[ty1 + r0 : ty1 + r1, tx1 + c0 : tx1 + c1]
        if src.shape[2] == 4:
            a = src[..., 3:4].astype(np.float32) / 255
            premult = np.concatenate([src[..., :3].astype(np.float32) * a, a], axis=2)
            out = resample(premult, sx0, sy0, step, w, h, self.mode)[r0:r1, c0:c1]
            region = target.astype(np.float32)
            region *= 1 - out[..., 3:4]
            region += out[..., :3]
        else:
            region = resample(src, sx0, sy0, step, w, h, self.mode)[r0:r1, c0:c1]
        target[:] = np.rint(region).clip(0, 255).astype(np.uint8)

    def _fill(self, img, ref_rect, bgr) -> None:
        b = self.to_screen(ref_rect)
        cx, cy = self.client.x, self.client.y
        x1, x2 = max(0, round(b.x1 - cx)), min(self.w, round(b.x2 - cx))
        y1, y2 = max(0, round(b.y1 - cy)), min(self.h, round(b.y2 - cy))
        if x2 > x1 and y2 > y1:
            img[y1:y2, x1:x2] = bgr

    def _extent(self, layers: tuple) -> tuple[int, int, int, int]:
        """The client px rect the layers cover (x2, y2 exclusive)."""
        boxes = [self.to_screen(rect) for _name, rect in layers]
        cx, cy = self.client.x, self.client.y
        x1 = max(0, int(np.floor(min(b.x1 for b in boxes) - cx)))
        y1 = max(0, int(np.floor(min(b.y1 for b in boxes) - cy)))
        x2 = min(self.w, int(np.ceil(max(b.x2 for b in boxes) - cx)))
        y2 = min(self.h, int(np.ceil(max(b.y2 for b in boxes) - cy)))
        return x1, y1, x2, y2

    def _key(self, *more) -> tuple:
        return (self.w, self.h, self.oy, self.mode, self.distractors, self.map_offset, *more)

    def _layers(self, layers: tuple) -> np.ndarray:
        """The map with `layers` drawn over it (none: the map alone: sea, the real map capture
        centred and canvas-scaled, and next to where the popups sit the look-alikes of the
        map's art that could join or fool a panel; all of it moved by the drags, the popups
        not)."""

        def draw():
            if layers:  # over the image of the layers below it (drawn once for all looks)
                img = self._layers(layers[:-1]).copy()
                name, rect = layers[-1]
                self._draw(img, rect, 0.5, fixture(name))
                return img
            rng = np.random.default_rng(7)
            img = np.empty((self.h, self.w, 3), np.uint8)
            img[:] = SEA
            img += rng.integers(0, 4, (self.h, self.w, 1), dtype=np.uint8)
            dy = self.map_offset * S0  # logical px to reference px
            self._draw(img, (0, dy, REF_W, REF_H + dy), 0.25, fixture("map"))
            if self.distractors:
                for (x1, y1, x2, y2), bgr in UNDER:
                    self._fill(img, (x1, y1 + dy, x2, y2 + dy), bgr)
            return img

        return _cached(self._key("layers", layers), draw)

    def client_image(self, popup: str | None) -> np.ndarray:
        """The client's pixels (BGR) with `popup` open (None: the map); not to be written."""

        def draw():
            look = LOOKS[popup] if popup is not None else None
            img = self._layers(look.layers if look else ())
            if look is None and not self.cast.any():
                return img
            img = img.copy()
            if look is not None:
                for rect, bgr in look.edits:
                    self._fill(img, rect, bgr)
                if look.reskin:  # every pixel the popup drew, red and blue swapped
                    x1, y1, x2, y2 = self._extent(look.layers)
                    part = img[y1:y2, x1:x2]
                    drawn = (part != self._layers(())[y1:y2, x1:x2]).any(axis=2)
                    part[drawn] = part[drawn][:, ::-1]
                if self.distractors and ("x" in look.parts or "deadx" in look.parts):
                    for rect, bgr in OVER:
                        self._fill(img, rect, bgr)
            if self.cast.any():
                img = np.rint(img.astype(np.float32) + self.cast).clip(0, 255).astype(np.uint8)
            return img

        return _cached(self._key("client", popup, tuple(self.cast)), draw)

    def screen(self) -> np.ndarray:
        """The whole screen (BGR): the client image itself when the client fills it."""
        img = self.client_image(self.popup)
        c = self.client
        if (c.x, c.y, c.w, c.h) == (0, 0, *self.screen_size):
            return img

        def draw():
            sw, sh = self.screen_size
            s = np.empty((sh, sw, 3), np.uint8)
            s[:] = DESKTOP
            s[c.y : c.y + c.h, c.x : c.x + c.w] = img
            return s

        return _cached(self._key("screen", self.popup, tuple(self.cast), c, self.screen_size), draw)

    # what changes with time (dynamic scenes override these) --------------------------------
    def now(self) -> float:
        """The virtual time, s."""
        return self.clock.t if self.clock is not None else 0.0

    def tick(self) -> None:
        """The screen brought up to the virtual time, before every capture and press."""

    def on_read(self) -> None:
        """The bot is about to read the client (Game.client_image), not a thumbnail."""

    def grab(self, r: Rect) -> np.ndarray:
        """mss's grab, black off the screen; BGR (the bot reads the first three channels of
        mss's BGRA only)."""
        self.tick()
        s = self.screen()
        if r.x >= 0 and r.y >= 0 and r.x + r.w <= s.shape[1] and r.y + r.h <= s.shape[0]:
            return s[r.y : r.y + r.h, r.x : r.x + r.w]
        out = np.zeros((r.h, r.w, 3), np.uint8)
        y1, y2 = max(0, r.y), min(s.shape[0], r.y + r.h)
        x1, x2 = max(0, r.x), min(s.shape[1], r.x + r.w)
        if y2 > y1 and x2 > x1:
            out[y1 - r.y : y2 - r.y, x1 - r.x : x2 - r.x] = s[y1:y2, x1:x2]
        return out

    # the game's answers -------------------------------------------------------------------
    def _open(self, popup: str | None) -> None:
        self.popup = popup

    def press(self, x: int, y: int) -> None:
        self.tick()
        source = self.source or "screen"
        popup = self.popup
        self.events.append((source, x, y, popup))
        if popup is None:
            if source == "map" and self.queue:
                self._open(self.queue.pop(0))
            elif source == "list" and self.list_queue:
                self._open(self.list_queue.pop(0))
            elif source == "screen":
                # a popup's button or a close tap with nothing open lands on the map (it can
                # open a mission there)
                self.faults.append(f"a tap on the map with nothing open at ({x}, {y})")
            return
        if source in ("map", "list"):
            self.faults.append(f"{source} click under an open {popup} popup at ({x}, {y})")

        def on(role, inset=0.0):
            return any(b.contains(x, y, inset) for b in self.part(role, popup))

        # a paid button, a Cancel or a reward pressed is a fault whatever the popup does with
        # the press: one that takes no click (stuck) only changes nothing
        if on("paid"):
            self.faults.append(f"paid button of the {popup} popup pressed at ({x}, {y})")
            if not self.stuck:
                self._open(None)
        elif on("cancel"):
            self.faults.append(f"Cancel of the {popup} popup pressed at ({x}, {y})")
            if not self.stuck:
                self._open(None)
        elif on("tile"):
            self.faults.append(f"a reward of the {popup} popup pressed at ({x}, {y})")
        elif self.stuck:
            return
        elif on("start"):
            self.started += 1
            self.idle = max(0, self.idle - self.squads)
            self._open(None)
        elif on("free"):
            self.speed_ups += 1
            self._open(self.after_free)
        elif on("okay"):
            self.claimed += 1
            self._open(None)
        elif on("x"):
            self.closed_x += 1
            self._open(None)
        elif self.panel(popup).contains(x, y):
            pass  # the panel's text, its frame, a dead button: nothing happens
        else:
            self.closed_out += 1
            self._open(None)

    def presses(self, role: str, popup: str, inset: float = 0.0) -> list[tuple[int, int]]:
        """The clicks that landed on `role` of `popup` (inside its rect shrunk by `inset` of
        its size, 2 px at least, when given)."""
        return [
            (x, y)
            for src, x, y, p in self.events
            if src != "drag"
            and p == popup
            and any(b.contains(x, y, inset) for b in self.part(role, popup))
        ]

    def clicks_on(self, popup: str) -> list[tuple[int, int]]:
        """Every click made while `popup` was open."""
        return [(x, y) for src, x, y, p in self.events if src != "drag" and p == popup]

    def window(self) -> WindowInfo:
        c = self.client
        return WindowInfo(
            handle=1,
            title="Firestone",
            pid=1,
            exe="Firestone.exe",
            outer=Rect(c.x, c.y, c.w, c.h),
            client=c,
            maximized=True,
            fullscreen=False,
        )


class Clock:
    """A virtual clock for game.py: every wait of the bot takes no real time."""

    def __init__(self):
        self.t = 1000.0

    def monotonic(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.t += max(0.0, s)

    def time(self) -> float:
        return 1.8e9 + self.t

    def strftime(self, fmt: str, *a) -> str:
        return _time.strftime(fmt, *a)


class SceneGame(Game):
    """The real Game on a scene: captures, input, window and time are the scene's. The left
    list's and the HUD's probes are answered by the scene (their look is a later step)."""

    def __init__(self, scene: Scene, settings: Settings, tmp_path):
        super().__init__(settings)
        self.scene = scene
        self.lines: list[str] = []
        self.status_cb = self.lines.append
        self.diagnostics: list[str] = []
        self.beats: list[tuple[str, bool]] = []
        self.heartbeat_cb = lambda msg, stop, important: self.beats.append((msg, important))
        self.map_state_path = str(Path(tmp_path) / "MapStartState.ini")
        self.window = scene.window()
        self.vp = None

    def save_diagnostic(self, name: str, block: int = 1) -> None:
        self.diagnostics.append(name)

    def found(self, p, variation=None) -> bool:
        s = self.scene
        if p is atlas.MAP_TROOP_IDLE:
            return s.idle >= s.squads
        if p is atlas.MR_NO_MISSIONS:
            return s.no_missions_probe and not s.list_queue
        if p is atlas.MR_MISSION_DONE:
            return bool(s.list_queue) and s.list_queue[0].startswith("rewards")
        if p in (atlas.MR_SECOND_MISSION_NOT_DONE, atlas.MR_FREE_RESET, atlas.MR_RESET_AVAILABLE):
            return False
        return super().found(p, variation)

    def click_at(self, x: int, y: int, anchor=None) -> None:
        self.scene.source = "map"
        try:
            super().click_at(x, y, anchor)
        finally:
            self.scene.source = None

    def tap(self, p, settle_ms: float = 1500, expect=None) -> None:
        if p is atlas.MR_FIRST_MISSION:
            self.scene.source = "list"
        try:
            super().tap(p, settle_ms, expect)
        finally:
            self.scene.source = None

    def drag(self, x1: int, y1: int, x2: int, y2: int, anchor=None) -> None:
        self.scene.map_offset += y2 - y1
        super().drag(x1, y1, x2, y2, anchor)

    def client_image(self):
        self.scene.on_read()
        self.scene.reads += 1
        return super().client_image()


def _once(fn):
    """fn(img, *args) once per image the scene drew (mission_popup.read, map_close.look_of):
    the same pixels give the same answer, and the bot reads a screen several times (a quicker
    bench, nothing else; a scene that changes draws another image)."""
    seen: dict[tuple, tuple] = {}

    def once(img: np.ndarray, *args):
        root = img
        while isinstance(root.base, np.ndarray):
            root = root.base
        offset = img.__array_interface__["data"][0] - root.__array_interface__["data"][0]
        key = (id(root), offset, img.shape, img.strides, *(tuple(a) for a in args))
        if key not in seen:
            seen[key] = (root, fn(img, *args))  # the image kept: its id stays its own
        return seen[key][1]

    return once


def scene_game(monkeypatch, scene: Scene, tmp_path, **settings) -> SceneGame:
    """A SceneGame with the platform patched: capture, input, the game window, the clock."""
    s = Settings()
    s.set("Campaign", "0")
    for key, value in settings.items():
        s.set(key, value)
    g = SceneGame(scene, s, tmp_path)

    def move(x, y):
        scene.pointer = (x, y)

    def click():
        scene.press(*scene.pointer)

    def drag(x1, y1, x2, y2):
        scene.events.append(("drag", x1, y1, scene.popup))
        scene.pointer = (x2, y2)

    fake_inp = SimpleNamespace(
        move=move,
        click=click,
        drag=drag,
        wheel=lambda n, interval=0: None,
        key=lambda k: None,
        key_down=lambda k: None,
        key_up=lambda k: None,
    )
    monkeypatch.setattr(game_mod, "inp", fake_inp)
    monkeypatch.setattr(capture, "grab", scene.grab)
    monkeypatch.setattr(game_mod, "find_game_window", scene.window)
    monkeypatch.setattr(game_mod, "activate", lambda win: True)
    monkeypatch.setattr(mission_popup, "read", _once(mission_popup.read))
    monkeypatch.setattr(map_close, "look_of", _once(map_close.look_of))
    scene.clock = Clock()
    monkeypatch.setattr(game_mod, "time", scene.clock)
    return g


# --- scenes that change with the virtual clock or with the bot's reads ---------------------
class LateScene(Scene):
    """A game that hitches: a map click or a tap on the list opens its popup `delay` s
    (virtual time) after it. A map click made while a popup is still coming is taken by
    nothing; it is kept in `early` (x, y, the time the popup still needed)."""

    def __init__(self, *a, delay: float = 1.2, **k):
        super().__init__(*a, **k)
        self.delay = delay
        self.pending: tuple[str, float] | None = None
        self.early: list[tuple[int, int, float]] = []

    def tick(self) -> None:
        if self.pending is not None and self.now() >= self.pending[1]:
            if self.popup is None:
                self._open(self.pending[0])
            self.pending = None

    def press(self, x: int, y: int) -> None:
        self.tick()
        queue = {"map": self.queue, "list": self.list_queue}.get(self.source or "")
        if self.popup is None and queue is not None and (self.pending or queue):
            self.events.append((self.source, x, y, None))
            if self.pending is not None:
                self.early.append((x, y, round(self.pending[1] - self.now(), 3)))
            else:
                self.pending = (queue.pop(0), self.now() + self.delay)
            return
        super().press(x, y)


class Morph(Scene):
    """A popup whose look changes `after` s (virtual time) after the bot's first read of it:
    `morphs` maps a look to the one it turns into (a price drawn a frame late, or one that
    goes). Captures and presses from then on see the new look; `switched` keeps the number of
    reads the bot had made of the client when it changed."""

    def __init__(self, *a, morphs: dict[str, str], after: float = 0.05, **k):
        super().__init__(*a, **k)
        self.morphs = morphs
        self.after = after
        self.first_read: float | None = None
        self.switched: list[int] = []

    def _open(self, popup: str | None) -> None:
        super()._open(popup)
        self.first_read = None

    def on_read(self) -> None:
        if self.popup in self.morphs and self.first_read is None:
            self.first_read = self.now()

    def tick(self) -> None:
        if (
            self.popup in self.morphs
            and self.first_read is not None
            and self.now() >= self.first_read + self.after
        ):
            self.popup = self.morphs[self.popup]
            self.first_read = None
            self.switched.append(self.reads)


class Flicker(Scene):
    """A popup that never settles: from the second read of it on, every read shows the other
    look of `pair` (the same popup a few px higher or lower, still moving)."""

    def __init__(self, *a, pair: tuple[str, str] = ("free", "free-up"), **k):
        super().__init__(*a, **k)
        self.pair = pair
        self.seen = False

    def _open(self, popup: str | None) -> None:
        super()._open(popup)
        self.seen = False

    def on_read(self) -> None:
        a, b = self.pair
        if self.popup in self.pair:
            if self.seen:
                self.popup = b if self.popup == a else a
            self.seen = True


class Gap(Scene):
    """After a press on a popup's `dead` part (a Start that takes no press), its panel is
    missing from the next `gap` reads of the client (a re-layout), then back."""

    def __init__(self, *a, gap: int = 1, **k):
        super().__init__(*a, **k)
        self.gap = gap
        self.hide = 0
        self.hiding = False

    def press(self, x: int, y: int) -> None:
        dead = self.popup is not None and any(b.contains(x, y) for b in self.part("dead"))
        super().press(x, y)
        if dead:
            self.hide = self.gap

    def on_read(self) -> None:
        self.hiding = self.hide > 0
        self.hide -= self.hiding

    def grab(self, r: Rect) -> np.ndarray:
        if not self.hiding:
            return super().grab(r)
        self.hiding = False
        keep, self.popup = self.popup, None
        try:
            return super().grab(r)
        finally:
            self.popup = keep


class AfterOkay(Scene):
    """The Mission Rewards' Okay closes them, and `delay` s (virtual time) later `then` opens
    once (another window of the game after a claim: a level-up, an achievement)."""

    def __init__(self, *a, then: str, delay: float = 1.5, **k):
        super().__init__(*a, **k)
        self.then: str | None = then
        self.delay = delay
        self.due: float | None = None

    def tick(self) -> None:
        if self.due is not None and self.now() >= self.due:
            if self.popup is None:
                self._open(self.then)
            self.due = self.then = None

    def press(self, x: int, y: int) -> None:
        claimed = self.claimed
        super().press(x, y)
        if self.claimed > claimed and self.then is not None and self.due is None:
            self.due = self.now() + self.delay
