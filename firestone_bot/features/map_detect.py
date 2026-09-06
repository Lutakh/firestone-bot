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

from collections import deque

import numpy as np

from firestone_bot.game import Game
from firestone_bot.vision import atlas

WHITE_MIN = 240  # every channel at least this: the digit body
DARK_MAX = 90  # every channel below this: the outline
# Logical px (multiplied by the capture factor in find_labels)
OUTLINE_REACH = 2  # between a digit pixel and its outline
DIGIT_H = (8, 21)  # digit blob height
DIGIT_W = (2, 38)  # digit blob width (merged digits allowed)
ROW_GAP = 9  # largest gap between two blobs of one label
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
    digits = [
        b
        for b in _blobs(white & near)
        if digit_h[0] <= b[3] - b[1] <= digit_h[1] and digit_w[0] <= b[2] - b[0] <= digit_w[1]
    ]
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
        if len(group) < 2:
            continue
        x0, y0 = min(g[0] for g in group), min(g[1] for g in group)
        x1, y1 = max(g[2] for g in group), max(g[3] for g in group)
        if label_w[0] <= x1 - x0 <= label_w[1]:
            labels.append((x0, y0, x1, y1))
    return labels


def find_missions(g: Game) -> list[tuple[int, int]]:
    """Logical (x, y) of every mission icon on the open map, top to bottom then left to right."""
    x1, y1, x2, y2 = atlas.MAP_DETECT_AREA
    img = g.region_image((x1, y1, x2, y2))
    fx = (x2 - x1) / img.shape[1]
    fy = (y2 - y1) / img.shape[0]
    points = []
    for lx0, ly0, lx1, ly1 in find_labels(img, 1 / fx):
        cx = x1 + int((lx0 + lx1) / 2 * fx)
        cy = y1 + int((ly0 + ly1) / 2 * fy) - atlas.MAP_LABEL_TO_ICON
        if cx < PANEL_MAX_X:
            continue  # remaining time of a running mission in the left HUD panel
        points.append((cx, cy))
    points.sort(key=lambda p: (p[1] // 40, p[0]))
    return points
