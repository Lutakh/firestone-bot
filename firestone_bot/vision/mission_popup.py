"""The world map's mission popups, read by their look from a capture of the whole client.

The popups were read and clicked at fixed logical points mapped through a guessed anchor (the
thirds rule), but they are centred dialogs held at their top edge: at 1920x1009 the start,
in-progress and Mission Rewards popups share their top (client y 187) and their centre (x
959.5) and end at y 896, 795 and 679. Below a client aspect of about 1.6 (16:10 fullscreen,
4:3, 5:4, a MacBook) the Start probe and click fell under the button and the bot "goes to the
next mission, which it also doesn't start" (a player, 2026-10-30); at 21:9 the in-progress
probes were 250 px off; the rewards' Okay point fell on a start popup's middle reward at
every shape. Nothing here depends on an anchor: the panel is found by its colour, its width
is the ruler, the buttons are solid colour boxes in its bottom band, and its own X is an
orange ring around a cream cross at its top-right corner. Boxes are screen px.

Measured on game 9.1.3a at 1920x1009 (Epic, 2026-10-29/30), client px, panel width W 1098
(start / in progress) or 1088 (Mission Rewards):
- panel: a dark line (165,125,99), a light line (255,239,214) and a cream frame (225,206,173)
  around a parchment inside (203,165,129); the screen behind is not dimmed, and the map's
  desert is that parchment, so the panel is found by its cream frame and header alone (the
  desert under the in-progress popup made a parchment blob 57 px too tall).
- start: green Start (11,160,8) 958..1209 x 798..881 (0.23 x 0.077 W) left of the orange
  Complete instantly (242,155,66) 1238..1489, whose brown label band (147,107,57) and gem
  (519 px, 2.5 % of the box) show the price.
- in progress: Cancel 958..1209 x 694..781 and the orange Speed up 1238..1489. With more than
  3 minutes left the Cancel is red (231,66,60) and the Speed up carries the label band and a
  gem (522 px); under 3 minutes the Cancel is grey (156,156,156) and the orange button says
  "Free", no band, no gem (2026-10-30 23:06).
- Mission Rewards: one centred green Okay 804..1115 x 566..637 (0.287 x 0.066 W), no X; the
  rewards above it can be gem purple (the World domination event's mystery box, the paw
  mission's medallion and crystal chest), its row never.
- the X of the start and in-progress popups: a ring (255,69..113,1..16) 1464..1527 x 172..237
  holding a cream cross (255,250,206) 1478..1513 x 186..221; a map icon's stars can hide the
  ring's top (the start capture: 64 x 42 px visible).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from firestone_bot.vision import atlas, gems
from firestone_bot.vision.blobs import Blob, colour_mask, mask_blobs, ring_with_cross
from firestone_bot.vision.viewport import CANVAS_W, canvas_scale

START = "start"
IN_PROGRESS = "in progress"
REWARDS = "rewards"
UNKNOWN = "unknown"
NONE = "none"

# The panel: its width this share of the canvas width (0.61 measured; a client wider than
# 16:9 shows more map, not a wider panel), width / height within these bounds (1.55 start,
# 1.81 in progress, 2.21 rewards). Cream blobs on cells of this many coarse px (the frame is
# about 6 wide).
PANEL_MIN_W = 0.35
PANEL_MAX_W = 0.95
NOMINAL_W = 0.61  # where a popup the reader cannot see would draw (map_close.beside)
PANEL_ASPECT = (1.2, 2.8)
PANEL_CELL = 6
# A header piece: this share of the panel's width at least (0.43: an edge to the medallion),
# at most this many panel widths over or under the rest (the ribbon is 0.058 high).
PANEL_PIECE = 0.25
PANEL_GAP = 0.1
# Everything below is in panel widths. Button row: the bottom of the panel (the buttons' tops
# are 0.089 / 0.092 / 0.104 W above it).
BAND = 0.17
BUTTON_W = (0.17, 0.34)  # 0.23 and 0.287 measured
BUTTON_H = (0.045, 0.11)  # 0.077 and 0.066
BUTTON_FILL = 0.45  # the box's own colour, white label and price aside
COLUMN_FILL = 0.5  # a button's column: this share of a button's least height in its colour
COLUMN_GAP = 0.012  # columns short of it inside a run (two buttons stand 0.026 W apart)
ROW_FILL = 0.5  # a button's row: this share of the run of such columns
ROW_GAP = 0.03  # rows short of it inside a button: its label (0.013 W at most); a wider gap ends it
SAME_ROW = 0.5  # vertical overlap of two buttons side by side, share of the lower one
OKAY_CENTRE_TOL = 0.04  # the Okay's centre off the panel's (0 measured)
# The Okay's size: 0.283..0.292 x 0.063..0.069 measured at every shape of the bench; a lone
# button of a Start's width (0.23) is not the Mission Rewards' Okay
OKAY_W = (0.26, 0.32)
OKAY_H = (0.05, 0.085)
# The brown label band of a paid orange button: 0.36 / 0.41 of the box (start / in progress),
# 0.003 on the free button
LABEL_SHARE = 0.15
OKAY_ROW_MARGIN = 0.02  # above and below the Okay: its row, read for a gem
# Gem purple px in the panel, in W**2: a price's gem 0.00043 (521 px), the free in-progress
# popup 0.000003; the Mission Rewards' purple rewards 0.0023 to 0.0083
GEM_ICON = 0.00012
# The X: searched around the panel's top-right corner, a ring of these widths around a cross
# of these widths (0.058 and 0.032 measured; 0.038 when a map icon's stars hide the ring top).
X_AREA = (-0.10, -0.05, 0.05, 0.09)  # left, top, right, bottom of the corner, in W
X_RING = (0.03, 0.09)
X_CROSS = (0.015, 0.05)
OUTSIDE = 0.05  # a tap this far right of the panel, at its middle height, is outside it
SETTLED = 0.02  # two reads agree when every box moved less than this


@dataclass(frozen=True)
class Box:
    """Screen px, (x2, y2) exclusive."""

    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def cx(self) -> int:
        return (self.x1 + self.x2) // 2

    @property
    def cy(self) -> int:
        return (self.y1 + self.y2) // 2

    @property
    def w(self) -> int:
        return self.x2 - self.x1

    @property
    def h(self) -> int:
        return self.y2 - self.y1

    def contains(self, x: float, y: float) -> bool:
        return self.x1 <= x < self.x2 and self.y1 <= y < self.y2


@dataclass(frozen=True)
class Popup:
    """One read: the kind of panel on the map and its parts (screen px)."""

    kind: str = NONE
    panel: Box | None = None
    green: Box | None = None  # Start / Okay
    orange: Box | None = None  # Complete instantly / Speed up / Free
    cancel: Box | None = None  # red or grey
    close: Box | None = None  # the X's cream cross
    green_gem: bool = False
    orange_gem: bool = False
    orange_label: bool = False  # the brown label band of a paid button
    okay_row_gem: bool = False  # Mission Rewards: gem purple in the Okay's row
    gem: bool = False  # a gem icon anywhere in the panel
    cancel_grey: bool = False  # the Cancel is the grey one of a mission under 3 minutes
    client: Box | None = None  # the client read, screen px

    @property
    def paid(self) -> bool:
        """The orange button shows a price (a gem, or the label band of the paid layout)."""
        return self.orange_gem or self.orange_label

    @property
    def free(self) -> bool:
        """An in-progress popup in the free layout of a mission under 3 minutes (2026-10-30
        23:06): a grey Cancel and an orange button with no price. The absence of a price
        alone is no proof: a red Cancel is the paid layout, whatever its button shows."""
        return self.kind == IN_PROGRESS and self.cancel_grey and not self.paid

    def outside(self) -> tuple[int, int] | None:
        """A screen point beside the panel, at its middle height (a tap there closes it);
        None when it would fall outside the client (another window could take the tap)."""
        p = self.panel
        assert p is not None
        x, y = p.x2 + round(OUTSIDE * p.w), p.cy
        c = self.client
        if c is not None and not (c.x1 <= x < c.x2 - 2 and c.y1 <= y < c.y2):
            return None
        return x, y

    def same_as(self, other: Popup) -> bool:
        """The same panel in the same place, read alike: a popup scaling in or out reads
        differently twice in a row."""
        flags = ("kind", "green_gem", "orange_gem", "orange_label", "okay_row_gem", "cancel_grey")
        if any(getattr(self, f) != getattr(other, f) for f in flags):
            return False
        tol = SETTLED * self.panel.w if self.panel is not None else 0
        for part in ("panel", "green", "orange", "cancel"):
            a, b = getattr(self, part), getattr(other, part)
            if a is None or b is None:
                if a is not b:
                    return False
            elif max(abs(a.x1 - b.x1), abs(a.y1 - b.y1), abs(a.x2 - b.x2), abs(a.y2 - b.y2)) > tol:
                return False
        return True


def _px(img: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    a = img[..., :3].astype(np.int16)
    return a[..., 2], a[..., 1], a[..., 0]


def cream_mask(img: np.ndarray) -> np.ndarray:
    """The panel's frame and header (225,206,173), its light line and the Mission Rewards
    dialog's light inside (221,199,157); not its parchment (203,165,129) nor the desert of
    the map (203,160,125 and darker), told apart by their green (206 / 199 against 165 /
    160). The margins take a colour cast of 8 per channel (macOS colour management)."""
    r, g, b = _px(img)
    rg, gb = r - g, g - b
    return (r >= 195) & (g >= 175) & (b >= 130) & (rg >= -5) & (rg <= 45) & (gb >= 12) & (gb <= 60)


def green_mask(img: np.ndarray) -> np.ndarray:
    """Start / Okay (11,160,8); not the progress bar of a mission in progress (66,182,0)."""
    r, g, b = _px(img)
    return (g >= 110) & (r <= 50) & (b <= 60) & (g - r >= 80) & (g - b >= 80)


def orange_mask(img: np.ndarray) -> np.ndarray:
    """An orange button's body (242,155,66), its lit top (255,178,71) and dark foot
    (225,125,57); not its rim (206,73,0), a red button or the X's ring."""
    r, g, b = _px(img)
    return (r >= 200) & (g >= 100) & (g <= 200) & (b <= 110) & (r - g >= 40) & (g - b >= 45)


def label_mask(img: np.ndarray) -> np.ndarray:
    """The brown label band of a paid orange button (147,107,57); not the start popup's time
    band (113,58,29) nor the panel's dark line (165,125,99)."""
    r, g, b = _px(img)
    rg, gb = r - g, g - b
    return (
        (r >= 120)
        & (r <= 180)
        & (g >= 80)
        & (g <= 135)
        & (b >= 30)
        & (b <= 85)
        & (rg >= 18)
        & (rg <= 65)
        & (gb >= 25)
        & (gb <= 70)
    )


def red_mask(img: np.ndarray) -> np.ndarray:
    """The red Cancel (231,66,60), lit top (231,89,82) to dark foot (222,40,33); not the
    orange rim (206,73,0) or the X's ring (255,85,8), whose blue is far below their green."""
    r, g, b = _px(img)
    return (r >= 180) & (r - g >= 100) & (r - b >= 100) & (np.abs(g - b) <= 35)


def grey_mask(img: np.ndarray) -> np.ndarray:
    """The grey Cancel of a mission under 3 minutes (192,192,192) to (145,145,145)."""
    r, g, b = _px(img)
    hi = np.maximum(np.maximum(r, g), b)
    lo = np.minimum(np.minimum(r, g), b)
    mean = (r + g + b) / 3
    return (hi - lo <= 24) & (mean >= 115) & (mean <= 215)


def ring_mask(img: np.ndarray) -> np.ndarray:
    """The X's orange ring, by hue: DIALOG_RING within 30 (main_menu.find_dialog_x) loses the
    ring's dark foot (255,69,1) to a colour cast of 8."""
    r, g, b = _px(img)
    return colour_mask(img, atlas.DIALOG_RING, 30) | (
        (r >= 200) & (r - g >= 110) & (g - b >= 30) & (b <= 70)
    )


def cross_mask(img: np.ndarray) -> np.ndarray:
    """The X's cream cross, as main_menu.find_dialog_x reads it."""
    return colour_mask(img, atlas.DIALOG_X_CROSS, 30)


def coarse_step(w: int, h: int) -> int:
    """The sampling step: a panel 490..800 px wide in the coarse image whatever the client
    (1 up to 1366x768, 2 at 1920x1009, 4 at 3840x2160)."""
    return max(1, int(2 * canvas_scale(w, h) + 0.5))


def _find_panel(c: np.ndarray, step: int, w: int, h: int) -> Box | None:
    """The panel in the coarse image `c` (every `step`-th pixel of a w x h client), in client
    px: the largest cream blob that spans the client's centre and has a dialog's shape.

    The panel is centred: a side reaching further than the other took map art (an island's
    sand against the panel's edge) and is cut back. Its header, cream from the panel's edges
    to the medallion, holds to the body by the frame's thin sides only, which the ribbon and
    the X cover there: header pieces reaching the panel's edges just over the body are taken
    in (the in-progress popup at 1680x1050 under a colour cast was read without its header,
    so without its X)."""
    canvas_w = CANVAS_W * canvas_scale(w, h)
    blobs = [
        (x1 * step, y1 * step, x2 * step, y2 * step, n)
        for x1, y1, x2, y2, n in mask_blobs(cream_mask(c), PANEL_CELL, fill=0.4)
    ]
    tol = 2 * PANEL_CELL * step
    for sx1, sy1, sx2, sy2, _n in sorted(blobs, key=lambda b: -b[4]):
        half = min(w / 2 - sx1, sx2 - w / 2)
        if not PANEL_MIN_W * canvas_w <= 2 * half <= PANEL_MAX_W * canvas_w:
            continue
        x1, x2, y1, y2 = w / 2 - half, w / 2 + half, sy1, sy2
        gap = PANEL_GAP * 2 * half
        for _ in range(2):
            for bx1, by1, bx2, by2, _m in blobs:
                if (
                    bx1 >= x1 - tol
                    and bx2 <= x2 + tol
                    and min(abs(bx1 - x1), abs(bx2 - x2)) <= tol
                    and bx2 - bx1 >= PANEL_PIECE * 2 * half
                    and by2 >= y1 - gap
                    and by1 <= y2 + gap
                ):
                    y1, y2 = min(y1, by1), max(y2, by2)
        if PANEL_ASPECT[0] <= 2 * half / (y2 - y1) <= PANEL_ASPECT[1]:
            return Box(round(x1), y1, round(x2), y2)
    return None


def _boxes(mask: np.ndarray, step: int, pw: float, ox: int, oy: int) -> list[Box]:
    """Button-sized solid boxes of a coarse mask of the button row, left to right, in client
    px (`ox`, `oy`: the mask's origin), told by projections as buttons.green_boxes does: the
    columns that hold a button's height of the colour, then the rows that fill half of such
    a run. Holes do not cut a box (a label across the whole button, "Complete instantly"; the
    gem and the price), and the buttons of the row stand side by side, never stacked; a blend
    of the start popup's time band into the parchment has the label's brown in a strip at its
    ends, too narrow to fill a row of a button."""
    cols = mask.sum(axis=0) >= BUTTON_H[0] * pw / step * COLUMN_FILL
    edges = np.flatnonzero(np.diff(np.concatenate(([0], cols.astype(np.int8), [0]))))
    runs: list[list[int]] = []
    for x1, x2 in zip(edges[::2], edges[1::2], strict=True):
        if runs and x1 - runs[-1][1] <= COLUMN_GAP * pw / step:
            runs[-1][1] = x2  # a few columns of gem and label, not a gap between buttons
        else:
            runs.append([x1, x2])
    out = []
    for x1, x2 in runs:
        if not BUTTON_W[0] * pw <= (x2 - x1) * step <= BUTTON_W[1] * pw:
            continue
        rows = np.flatnonzero(mask[:, x1:x2].sum(axis=1) >= (x2 - x1) * ROW_FILL)
        if not len(rows):
            continue
        # the rows in one piece, the tallest: a line of the colour above the button is no
        # part of it (the empty progress bar of a short mission has a grey top line across
        # the grey Cancel's columns, 70 px over it: the free popup of the World domination
        # event's mystery mission read unknown, 2026-10-31 04:54)
        pieces = np.split(rows, np.flatnonzero(np.diff(rows) > max(1, ROW_GAP * pw / step)) + 1)
        piece = max(pieces, key=len)
        y1, y2 = piece[0], piece[-1] + 1
        if not BUTTON_H[0] * pw <= (y2 - y1) * step <= BUTTON_H[1] * pw:
            continue
        if mask[y1:y2, x1:x2].mean() < BUTTON_FILL:
            continue
        out.append(Box(ox + x1 * step, oy + y1 * step, ox + x2 * step, oy + y2 * step))
    return out


def _same_row(a: Box, b: Box) -> bool:
    overlap = min(a.y2, b.y2) - max(a.y1, b.y1)
    return overlap >= SAME_ROW * min(a.h, b.h)


def _share(img: np.ndarray, box: Box, fn) -> float:
    crop = img[max(0, box.y1) : box.y2, max(0, box.x1) : box.x2]
    return float(fn(crop).mean()) if crop.size else 0.0


def _find_x(img: np.ndarray, panel: Box) -> Box | None:
    """The popup's own X near the panel's top-right corner: a ring holding a cream cross
    (client px of the cross)."""
    pw = panel.w
    h, w = img.shape[:2]
    ax1 = max(0, panel.x2 + round(X_AREA[0] * pw))
    ay1 = max(0, panel.y1 + round(X_AREA[1] * pw))
    ax2 = min(w, panel.x2 + round(X_AREA[2] * pw))
    ay2 = min(h, panel.y1 + round(X_AREA[3] * pw))
    if ax2 <= ax1 or ay2 <= ay1:
        return None
    step = max(1, round(pw / 1100))  # the cross 30..40 px wide
    crop = img[ay1:ay2:step, ax1:ax2:step]
    cell = max(2, round(0.005 * pw / step))

    def blobs_of(mask, size):
        out = []
        for x1, y1, x2, y2, n in mask_blobs(mask, cell, fill=0.25):
            bw, bh = (x2 - x1) * step, (y2 - y1) * step
            if size[0] * pw <= bw <= size[1] * pw and size[0] * pw <= bh <= size[1] * pw:
                out.append(Blob(x1, y1, x2, y2, n))
        return out

    crosses = blobs_of(cross_mask(crop), X_CROSS)
    ring = ring_with_cross(blobs_of(ring_mask(crop), X_RING), crosses)
    if ring is None:
        return None
    cross = next(c for c in crosses if ring.x1 <= c.cx <= ring.x2 and ring.y1 <= c.cy <= ring.y2)
    return Box(
        ax1 + cross.x1 * step, ay1 + cross.y1 * step, ax1 + cross.x2 * step, ay1 + cross.y2 * step
    )


def _classify(
    panel: Box, green: list[Box], orange: list[Box], cancel: list[Box], close: Box | None
) -> tuple[str, Box | None, Box | None, Box | None]:
    """(kind, green, orange, cancel): START is a green box left of an orange one in the same
    row, IN_PROGRESS a Cancel (red or grey) left of an orange one, REWARDS one green box of
    the Okay's size in the middle, and no X; nothing else in the row. Anything else is
    UNKNOWN."""
    pw = panel.w
    if len(orange) == 1:
        o = orange[0]
        left = green + cancel
        if len(left) == 1 and left[0].x2 <= o.x1 and _same_row(left[0], o):
            if green:
                return START, green[0], o, None
            return IN_PROGRESS, None, o, cancel[0]
    elif (
        len(green) == 1
        and not orange
        and not cancel
        and close is None
        and abs(green[0].cx - panel.cx) <= OKAY_CENTRE_TOL * pw
        and OKAY_W[0] * pw <= green[0].w <= OKAY_W[1] * pw
        and OKAY_H[0] * pw <= green[0].h <= OKAY_H[1] * pw
    ):
        return REWARDS, green[0], None, None
    return UNKNOWN, None, None, None


def read(img: np.ndarray, origin: tuple[int, int] = (0, 0)) -> Popup:
    """The mission popup on a capture of the whole client (BGR), boxes in screen px
    (`origin`: the client's top-left corner on the screen). Masks and blobs run on every
    `coarse_step`-th pixel; the gem shares on the full pixels of the boxes found."""
    h, w = img.shape[:2]
    step = coarse_step(w, h)
    c = img[step // 2 :: step, step // 2 :: step]
    panel = _find_panel(c, step, w, h)
    if panel is None:
        return Popup()
    pw = panel.w
    # the button row: the panel's bottom (and a little under it: the frame found is rounded
    # to the blob cells)
    cy1 = max(panel.y1 + panel.h // 2, panel.y2 - round(BAND * pw)) // step
    cy2 = -(-min(h, panel.y2 + round(0.01 * pw)) // step)
    cx1, cx2 = panel.x1 // step, -(-panel.x2 // step)
    band = c[cy1:cy2, cx1:cx2]
    ox, oy = cx1 * step, cy1 * step
    greys = _boxes(grey_mask(band), step, pw, ox, oy)
    cancel = _boxes(red_mask(band), step, pw, ox, oy) + greys
    close = _find_x(img, panel)
    kind, g_box, o_box, x_box = _classify(
        panel,
        _boxes(green_mask(band), step, pw, ox, oy),
        _boxes(orange_mask(band) | label_mask(band), step, pw, ox, oy),
        cancel,
        close,
    )
    green_gem = g_box is not None and _share(img, g_box, gems.gem_mask) > gems.GEM_SHARE_MAX
    orange_gem = o_box is not None and _share(img, o_box, gems.gem_mask) > gems.GEM_SHARE_MAX
    orange_label = o_box is not None and _share(img, o_box, label_mask) >= LABEL_SHARE
    if kind == START and not orange_gem:
        # a Start is told by the paid Complete instantly beside it. One with no price at all
        # was never seen (a mission under 3 minutes might show it): a dialog pricing its
        # green elsewhere would look the same, so it is closed, said and captured (its green
        # and orange boxes are kept for that); a label without its gem is a price missed
        kind = UNKNOWN
    okay_row_gem = False
    if kind == REWARDS and g_box is not None:
        m = round(OKAY_ROW_MARGIN * pw)
        row = Box(panel.x1, g_box.y1 - m, panel.x2, g_box.y2 + m)
        okay_row_gem = _share(img, row, gems.gem_mask) > gems.GEM_SHARE_MAX
    inside = c[panel.y1 // step : panel.y2 // step, cx1:cx2]
    gem_px = int(gems.gem_mask(inside).sum()) * step * step
    dx, dy = origin

    def moved(b: Box | None) -> Box | None:
        return None if b is None else Box(b.x1 + dx, b.y1 + dy, b.x2 + dx, b.y2 + dy)

    return Popup(
        kind=kind,
        panel=moved(panel),
        green=moved(g_box),
        orange=moved(o_box),
        cancel=moved(x_box),
        close=moved(close),
        green_gem=green_gem,
        orange_gem=orange_gem,
        orange_label=orange_label,
        okay_row_gem=okay_row_gem,
        gem=gem_px >= GEM_ICON * pw * pw,
        cancel_grey=kind == IN_PROGRESS and x_box in greys,
        client=Box(dx, dy, dx + w, dy + h),
    )


def read_game(g) -> Popup:
    """read() on a fresh capture of the game's client."""
    img, client = g.client_image()
    return read(img, (client.x, client.y))
