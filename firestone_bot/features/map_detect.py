"""World-map missions found on the screen instead of a fixed coordinate list (owner request
2026-09-06: "click only where there is a mission, never in the void").

Every mission marker on the map carries a duration label under its icon: bold white digits
with a dark outline ("27:36", "4:57", "2:15:35"). The marker itself changes with the mission
(telescope, gift, sword...) and pulses, so the label is the stable cue. The label is looked
for at capture resolution inside the map area, the icon sits a fixed distance above it.

Measured on the Mac client (3024x1709), new-adventure style: digits 14..34 px tall, a label
45..200 px wide, the ring centre about 18 logical px above the label centre. On the Windows
reference client (1920x1009, 2026-09-06) the same digits are 10 px tall and a label 43 px
wide, so every threshold below is in LOGICAL px and scaled by the capture factor (capture px
per logical px: 1.0 on that client, about 1.6 on the Mac).

The left HUD panel lists the missions in progress with their remaining time, in the same
font: labels there are not missions on the map and are dropped (owner's cycle 2026-09-06:
the bot opened the running Trade Route from that panel every cycle).
"""

from __future__ import annotations

import math
from collections import deque

import numpy as np

from firestone_bot.game import Game
from firestone_bot.vision import atlas

WHITE_MIN = 240  # every channel at least this: the digit body
DARK_MAX = 90  # every channel below this: the outline
# Logical px (multiplied by the capture factor in find_labels)
OUTLINE_REACH = 2  # between a digit pixel and its outline
DIGIT_H = (8, 21)  # digit blob height (a whole digit)
FRAGMENT_H = 4  # a digit cut in two by anti-aliasing at the zoomed-out size (a "0" or a "5"
# splits into 5 + 6 px halves, Windows 2026-09-08): fragments join a label but do not make one
# Two halves stacked at most this far apart are joined back into one digit first: "15:55" has
# a whole "1" and three split "5"s, so it never had two whole digits and its mission stayed
# unstarted for 35 minutes (owner, 2026-10-27 17:54-18:29; 11 such episodes since 2026-09-12)
SPLIT_GAP = 1  # rows between the two halves of a split digit
DIGIT_W = (2, 38)  # digit blob width (merged digits allowed)
ROW_GAP = 12  # largest gap between two blobs of one label (a colon plus a split digit)
ROW_ALIGN = 5  # vertical centre tolerance inside one label
LABEL_W = (22, 125)  # whole label width
PANEL_MAX_X = 285  # logical: labels left of this are the HUD panel of running missions


def _blobs(mask: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Bounding boxes (x0, y0, x1, y1) of the 8-connected components of `mask`."""
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    out = []
    for y, x in zip(*np.nonzero(mask)):
        if seen[y, x]:
            continue
        seen[y, x] = True
        q = deque([(y, x)])
        x0 = x1 = x
        y0 = y1 = y
        while q:
            cy, cx = q.popleft()
            x0, x1, y0, y1 = min(x0, cx), max(x1, cx), min(y0, cy), max(y1, cy)
            for ny in (cy - 1, cy, cy + 1):
                for nx in (cx - 1, cx, cx + 1):
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        q.append((ny, nx))
        out.append((x0, y0, x1 + 1, y1 + 1))
    return out


def _join_split(digits, digit_h, gap):
    """Join the two halves of a digit cut by anti-aliasing (a "5" drawn as 6 + 5 px blobs):
    two fragments (each shorter than a whole digit) stacked in one column, overlapping in x
    by half the narrower one and at most `gap` rows apart, become one box when that box has
    a whole digit's height and is taller than wide. Whole digits are never touched."""
    frags = sorted((b for b in digits if b[3] - b[1] < digit_h[0]), key=lambda b: b[1])
    out = [b for b in digits if b[3] - b[1] >= digit_h[0]]
    used = [False] * len(frags)
    for i, a in enumerate(frags):
        if used[i]:
            continue
        for j in range(i + 1, len(frags)):
            b = frags[j]
            if used[j]:
                continue
            ov = min(a[2], b[2]) - max(a[0], b[0])
            vgap = max(a[1], b[1]) - min(a[3], b[3])
            box = (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))
            h, w = box[3] - box[1], box[2] - box[0]
            if (
                ov >= 0.5 * min(a[2] - a[0], b[2] - b[0])
                and vgap <= gap
                and digit_h[0] <= h <= digit_h[1]
                and w < h
            ):
                used[i] = used[j] = True
                out.append(box)
                break
        if not used[i]:
            out.append(a)
    return out


def find_labels(img: np.ndarray, factor: float = 1.0) -> list[tuple[int, int, int, int]]:
    """Label rectangles (capture px) in a BGR image: rows of outlined white digit blobs.
    `factor` = capture px per logical px (scales the size thresholds)."""
    f = max(factor, 0.5)
    digit_h = (DIGIT_H[0] * f, DIGIT_H[1] * f)
    digit_w = (DIGIT_W[0] * f, DIGIT_W[1] * f)
    row_gap, row_align = ROW_GAP * f, ROW_ALIGN * f
    label_w = (LABEL_W[0] * f, LABEL_W[1] * f)
    a = img.astype(int)
    white = a.min(axis=2) >= WHITE_MIN
    dark = a.max(axis=2) < DARK_MAX
    near = np.zeros_like(dark)
    r = max(1, round(OUTLINE_REACH * f))
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            near |= np.roll(np.roll(dark, dy, 0), dx, 1)
    fragment_h = FRAGMENT_H * f
    digits = [
        b
        for b in _blobs(white & near)
        if fragment_h <= b[3] - b[1] <= digit_h[1] and digit_w[0] <= b[2] - b[0] <= digit_w[1]
    ]
    digits = _join_split(digits, digit_h, max(1, round(SPLIT_GAP * f)))
    digits.sort(key=lambda b: b[0])
    used = [False] * len(digits)
    labels = []
    for i, b in enumerate(digits):
        if used[i]:
            continue
        used[i] = True
        cy = (b[1] + b[3]) / 2
        group = [b]
        right = b[2]
        for j in range(i + 1, len(digits)):
            c = digits[j]
            if used[j] or c[0] - right > row_gap:
                continue
            if abs((c[1] + c[3]) / 2 - cy) <= row_align:
                group.append(c)
                used[j] = True
                right = max(right, c[2])
        whole = [c for c in group if c[3] - c[1] >= digit_h[0] and c[2] - c[0] < c[3] - c[1]]
        if len(group) < 2 or len(whole) < 2:
            continue  # a lone blob, fragments only, or wide shapes (the stars over an icon)
        x0, y0 = min(g[0] for g in group), min(g[1] for g in group)
        x1, y1 = max(g[2] for g in group), max(g[3] for g in group)
        if label_w[0] <= x1 - x0 <= label_w[1]:
            labels.append((x0, y0, x1, y1))
    return labels


def find_missions(g: Game) -> list[tuple[int, int]]:
    """Logical (x, y) of every mission icon on the open map, top to bottom then left to right.
    The points are centre-anchored, like the map: click them with atlas.ANCHOR_CENTER."""
    x1, y1, x2, y2 = atlas.MAP_DETECT_AREA
    vp = g._viewport()
    img = g.region_image((x1, y1, x2, y2))
    # The capture's corners follow the HUD edges (region_image's anchors) but the map is
    # centred, so a label goes through its screen pixel and the centre anchor. Scaled by the
    # area's corners and clicked with the thirds rule, labels were clicked up to 45 px beside
    # their icon on a 1920x1080 client (report ANHNX9, 2026-10-25), 170 px at 21:9.
    ox, oy = vp.to_screen(x1, y1)
    panel_x = vp.to_screen(PANEL_MAX_X, 0, (0.0, 0.0))[0]  # the HUD panel is left-anchored
    avatar_x, avatar_y = vp.to_screen(*atlas.MAP_DETECT_AVATAR, (0.0, 0.0))
    hud_bottom = vp.to_screen(0, atlas.MAP_DETECT_HUD_BOTTOM, (0.0, 0.0))[1]
    info_x, info_y = vp.to_screen(*atlas.MAP_DETECT_INFO, (0.0, 0.0))
    to_icon = atlas.MAP_LABEL_TO_ICON * vp.rel_scale
    points = []
    for lx0, ly0, lx1, ly1 in find_labels(img, img.shape[1] / (x2 - x1)):
        sx, sy = ox + (lx0 + lx1) / 2, oy + (ly0 + ly1) / 2
        if sx < panel_x:
            continue  # remaining time of a running mission in the left HUD panel
        if sx < avatar_x and sy < avatar_y:
            continue  # the XP numbers or the rank title under the avatar
        if sy - to_icon < hud_bottom:
            continue  # its icon is under a HUD counter: the click would hit the counter
        if sx < info_x and sy - to_icon < info_y:
            continue  # the click would open the rank info; found again lower once dragged
        # floored first: on the reference client the points are 0.3.34's exactly (MapState
        # remembers the points clicked, exact matches)
        cx, cy = vp.to_logical(math.floor(sx), math.floor(sy), atlas.ANCHOR_CENTER)
        points.append((cx, cy - atlas.MAP_LABEL_TO_ICON))
    points.sort(key=lambda p: (p[1] // 40, p[0]))
    return points
