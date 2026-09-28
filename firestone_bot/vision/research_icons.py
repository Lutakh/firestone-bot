"""Firestone research tree: the node boxes and the research each one holds, told apart by its
icon (2026-09-28, owner request: research priorities; the bot used to open the boxes from the
right-most one, whatever they were).

A node box of the library's Firestone tab is 383 x 101 logical px (a running one 105 high: its
gold 3D bottom edge): the research icon on the left, the name top right, "Max level" or a level
bar below. Its colour gives its state (measured 2026-09-28 on the owner's 1920x1009 Windows
client, trees I..XIII, 102 views, 702 boxes):

    available  flat dark blue 0x0D49DE with a light-blue rim
    maxed      light-blue gradient around 0x35C0FF, "Max level"
    running    gold gradient 0xFFEB99 (top) .. 0xCB9A26 (bottom)

Boxes are found as colour blobs of the three colours together (box_mask_bgr): no false blob in
the 102 views, and the connector lines (41, 255, 255) fail the light-blue test, so they never
join two boxes. The research is told by its icon, as the bag's chests are (chest_grid.py): a
fixed window over the icon, WINDOW logical px from the box's exact top-left corner (found in the
image: a blob is rounded to its cells), reduced to a THUMB x THUMB grid of mean colours and
compared with reference thumbnails (research_refs.json) recorded on maxed boxes, the only state
most names were ever seen in. The references of the other two states are the maxed ones with
their light-blue background pixels repainted in that state's box colour. Distance = mean
absolute difference over the whole grid (0..255 levels). Leave-one-tree-out on 544 boxes: 0
wrong, 0 unknown; self distance up to 6.7 (a dark-blue box), the nearest other name 17+ away,
an icon without a reference 15.8+ away (MAX_DISTANCE 11).

Two icon pairs differ only by their bottom text: ENEMY / BOSS "HP" (Weaklings, Expose Weakness)
and "DMG" (Powerless Enemy, Powerless Boss), 2 to 4 levels apart on the full grid. The best two
names are therefore compared again on the cells where their references differ by more than
PAIR_DELTA (the pair stage): the true name stays within 6 levels there, the other 35+ away
(worst ratio 0.36 over all names, a gold Guardian Power against Medal of Honor).

A sparkle (white star up to ~75 px) over the icon gives None now and then (a quarter of the
full-size stars on a dark-blue box), never another name in 9,684 synthetic trials: the caller
grabs it again a moment later. A box cut by the tree's left edge comes out None; it is whole at
another scroll stop. Resampled captures (1/2, 2/3, 4/3) identify every box: the window and the
grid are placed in logical px through the Viewport (region_image), whatever the client size.
The references come from Windows captures only. The Mac's sRGB capture reads the dark blue
0x2848D8 (Windows 0x0D49DE): every available box came out None there (review of 2026-09-29).
The box's own colour is therefore measured right of its icon (box_body), and each reference
cell moved by its share of box colour (research_refs.json "masks") times the box's offset from
the recorded colour, for the three states (Refs.stack). On the 571 Windows boxes nothing changes
(offsets within the Windows spread are none); with the Mac's dark blue, a uniform cast of
(+27, -1, -6) or the sRGB -> Display P3 model, every available and maxed box is identified,
and every running one but 4 of 11 under the uniform cast (the gold's red is cut at 255, so
its offset cannot be read), as before; no wrong name in any of them.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from firestone_bot.vision import atlas, blobs

STATES = ("maxed", "available", "running")
PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "research_refs.json")

# Icon window, logical px from the box's top-left corner (left, top, right, bottom): it ends
# before the level bar of an available / running box (x1 + 97, rows y1 + 58 .. y1 + 92).
WINDOW = (4, 4, 96, 98)
THUMB = 12  # rows and columns of the grid
OFFSETS = (-2, -1, 0, 1, 2)  # logical px: the window slid around the corner found
FALLBACK_OFFSETS = (-6, -4, -2, 0, 2, 4, 6)  # no corner found: slid around the blob's own
MAX_DISTANCE = 11.0  # a match: the best name within this (self <= 6.7, unknown icon >= 15.8)...
MAX_PAIR_RATIO = 0.5  # ...and, on the cells telling the best two apart, this much closer
PAIR_DELTA = 20.0  # levels: the cells where two references differ
PAIR_MIN_CELLS = 3  # fewer differing cells than this: the pair stage uses the full grid
# The image identify() reads: PAD logical px above and left of the blob's corner, RECT_W right
# and RECT_H below it (the icon, the corner's surroundings and the start of the box's body).
PAD = 12
RECT_W, RECT_H = 124, 116
CORNER_SLACK = 14  # logical px: the exact corner lies within this of the blob's
# Logical px right of the corner where the icon has ended: the state is read from there, and a
# box whose icon would reach behind the right-hand tab panel is left for another stop.
ICON_W = 110
# The box colour around each state's reference icons, as box_body() reads it right of the icon,
# and how far it strays on Windows (2026-09-29, the 571 Windows boxes of trees I..XIII the
# references come from): the flat dark blue exactly, the median of the light-blue gradient within
# 2 levels, the gold's within 4 (its blue: 93 on Attribute Damage, 101 on Guardian Power). An
# offset within that spread is no colour cast: the Windows boxes are compared as recorded.
REF_BODY = {"maxed": (51, 166, 255), "available": (13, 73, 222), "running": (255, 224, 97)}
BODY_SPREAD = {"maxed": 2, "available": 0, "running": 4}
BODY_MIN_SHARE = 0.1  # fewer box-colour px in the strip right of the icon: no colour correction


def state_masks(rgb: np.ndarray) -> dict[str, np.ndarray]:
    """Pixels of an RGB image that have each state's box colour (the thresholds of the
    2026-09-28 measurements). The dark blue is the node colour of 2026-09-08, 0x1D49DE +-32:
    it holds the Mac's sRGB capture of the box (0x2848D8) as well as Windows' 0x0D49DE, so the
    available boxes are still found there; on the 102 Windows views it finds the same boxes as
    the tighter test of the measurements (0x0D49DE +-14..18)."""
    a = rgb.astype(np.int16)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    light = (r >= 30) & (r <= 110) & (g >= 150) & (g <= 215) & (b >= 235)
    dark = (abs(r - 29) <= 32) & (abs(g - 73) <= 32) & (abs(b - 222) <= 32)
    gold = (r >= 180) & (g >= 135) & (g <= 245) & (b <= 190) & (r - b >= 60) & (g - b >= 40)
    rim = (r >= 240) & (g >= 225) & (g <= 248) & (b >= 150) & (b <= 212)  # the gold's pale top
    return {"maxed": light, "available": dark, "running": gold | rim}


def box_mask(rgb: np.ndarray) -> np.ndarray:
    """Pixels of any node box colour, RGB image."""
    m = state_masks(rgb)
    return m["maxed"] | m["available"] | m["running"]


def box_mask_bgr(bgr: np.ndarray) -> np.ndarray:
    """box_mask of a BGR capture (blobs.find_blobs(mask_fn=...))."""
    return box_mask(bgr[..., 2::-1])


def box_state(rgb: np.ndarray) -> str:
    """The dominant box colour of an RGB image of a box's body."""
    m = state_masks(rgb)
    return max(STATES, key=lambda s: int(m[s].sum()))


def box_body(rgb: np.ndarray, state: str) -> np.ndarray | None:
    """The box's own colour: the median of the `state` box pixels of an RGB image of its body
    (right of the icon); None when too few of them show."""
    m = state_masks(rgb)[state]
    if not m.any() or m.sum() < BODY_MIN_SHARE * m.size:
        return None
    return np.median(rgb[m].astype(np.float64), axis=0)


def find_boxes(g, rect: tuple[int, int, int, int]) -> list[blobs.Blob]:
    """Node boxes of every state inside a logical rect of the tree (centre-anchored)."""
    return blobs.find_blobs(
        g,
        rect,
        mask_fn=box_mask_bgr,
        anchor=atlas.ANCHOR_CENTER,
        min_w=atlas.RS_NODE_MIN_W,
        min_h=atlas.RS_NODE_MIN_H,
        cell=atlas.RS_NODE_CELL,
        fill=atlas.RS_NODE_FILL,
    )


def icon_rect(x1: int, y1: int) -> tuple[int, int, int, int]:
    """Logical rect identify() reads for the box whose blob starts at (x1, y1)."""
    return (x1 - PAD, y1 - PAD, x1 + RECT_W, y1 + RECT_H)


def _cumsum2(img: np.ndarray) -> np.ndarray:
    c = np.zeros((img.shape[0] + 1, img.shape[1] + 1) + img.shape[2:], np.float64)
    c[1:, 1:] = img.astype(np.float64).cumsum(0).cumsum(1)
    return c


def _block_means(c: np.ndarray, ys: np.ndarray, xs: np.ndarray) -> np.ndarray:
    s = (
        c[ys[1:]][:, xs[1:]]
        - c[ys[:-1]][:, xs[1:]]
        - c[ys[1:]][:, xs[:-1]]
        + c[ys[:-1]][:, xs[:-1]]
    )
    area = np.outer(np.diff(ys), np.diff(xs)).astype(np.float64)
    return s / area[..., None]


def window_thumbs(
    rgb: np.ndarray, cx: float, cy: float, fx: float, fy: float, offsets=OFFSETS
) -> list[np.ndarray]:
    """Thumbnails of the icon window for a box corner at image px (cx, cy), slid by `offsets`
    logical px each way; fx, fy = image px per logical px. The cell edges are floored, as the
    references' were: another rounding raised the self distances."""
    c = _cumsum2(rgb)
    h, w = rgb.shape[:2]
    out = []
    for dy in offsets:
        for dx in offsets:
            x0 = cx + (WINDOW[0] + dx) * fx
            x1 = cx + (WINDOW[2] + dx) * fx
            y0 = cy + (WINDOW[1] + dy) * fy
            y1 = cy + (WINDOW[3] + dy) * fy
            if x0 < 0 or y0 < 0 or x1 > w or y1 > h:
                continue
            ys = np.floor(np.linspace(y0, y1, THUMB + 1) + 1e-6).astype(int)
            xs = np.floor(np.linspace(x0, x1, THUMB + 1) + 1e-6).astype(int)
            if (np.diff(ys) <= 0).any() or (np.diff(xs) <= 0).any():
                continue  # a capture too small for the grid
            out.append(_block_means(c, ys, xs))
    return out


def find_corner(
    rgb: np.ndarray, fx: float, fy: float, ax: float, ay: float
) -> tuple[int, int] | None:
    """The box's exact top-left corner (image px) near (ax, ay): the first row where the box
    colours fill 60 % of the columns right of the icon, then the first column where they fill
    30 % of that box's rows (the icon covers the rest). None when it is not that close."""
    m = box_mask(rgb)
    w = m.shape[1]
    xa = min(w - 1, int(ax + 100 * fx))  # the name / level bar part of the box
    rows = m[:, xa:].mean(axis=1)
    ok = np.nonzero(rows >= 0.6)[0]
    if not len(ok):
        return None
    top = int(ok[0])
    ra, rb = int(top + 8 * fy), int(top + 92 * fy)
    if rb - ra < 4:
        return None
    ok = np.nonzero(m[ra:rb].mean(axis=0) >= 0.3)[0]
    if not len(ok):
        return None
    left = int(ok[0])
    if abs(left - ax) > CORNER_SLACK * fx or abs(top - ay) > CORNER_SLACK * fy:
        return None
    return left, top


class Refs:
    """research_refs.json: per state, one reference thumbnail per research name, and per name
    the share of icon pixels of each cell ("masks"; the rest is the box's colour)."""

    def __init__(self, data: dict) -> None:
        n = int(data["thumb"])
        self.names = sorted(data["refs"]["maxed"])
        self.stacks = {
            s: np.array([data["refs"][s][name] for name in self.names], np.float64).reshape(
                len(self.names), n, n, 3
            )
            for s in STATES
        }
        masks = data.get("masks")
        icon = (
            np.array([masks[name] for name in self.names], np.float64)
            if masks
            else np.ones((len(self.names), n * n))  # no masks: nothing to correct
        )
        self.background = 1.0 - icon.reshape(len(self.names), n, n, 1)

    def stack(self, state: str, body=None) -> np.ndarray:
        """The references of `state` for a box whose own colour is `body` (box_body; None: as
        recorded): each cell moved by its share of box colour times the box's offset from
        REF_BODY (less the Windows spread). The Mac's sRGB capture reads the dark blue 0x2848D8
        against Windows' 0x0D49DE: 11 levels on every background cell, half the icon window,
        which used up the whole MAX_DISTANCE budget (review of 2026-09-29: every available box
        None with the Mac's colours)."""
        stack = self.stacks[state]
        if body is None:
            return stack
        offset = np.asarray(body, np.float64) - REF_BODY[state]
        offset = np.sign(offset) * np.maximum(np.abs(offset) - BODY_SPREAD[state], 0)
        if not offset.any():
            return stack
        return np.clip(stack + self.background * offset, 0, 255)

    @classmethod
    def load(cls, path: str = PATH) -> Refs:
        with open(path, encoding="utf-8") as f:
            return cls(json.load(f))


@lru_cache(maxsize=1)
def default_refs() -> Refs:
    return Refs.load()


@dataclass(frozen=True)
class Ranked:
    """One name, its best distance over the window positions, and what gave it."""

    name: str
    distance: float
    ref: np.ndarray
    thumb: np.ndarray


def rank(thumbs: list[np.ndarray], state: str, refs: Refs, body=None) -> list[Ranked]:
    """Every name with its best distance over the thumbnails (window positions), closest
    first; `body`: the box's own colour (Refs.stack)."""
    stack = refs.stack(state, body)
    t = np.array(thumbs, np.float64)
    d = np.abs(t[:, None] - stack[None]).mean(axis=(2, 3, 4))  # thumbs x names
    best = d.argmin(axis=0)
    out = [
        Ranked(name, float(d[best[i], i]), stack[i], t[best[i]])
        for i, name in enumerate(refs.names)
    ]
    return sorted(out, key=lambda r: r.distance)


def pair_distances(a: Ranked, b: Ranked) -> tuple[float, float, int]:
    """The pair stage: each candidate's distance on the cells where their references differ
    by more than PAIR_DELTA (the full distances when fewer than PAIR_MIN_CELLS do)."""
    cells = np.abs(a.ref - b.ref).mean(axis=-1) > PAIR_DELTA
    n = int(cells.sum())
    if n < PAIR_MIN_CELLS:
        return a.distance, b.distance, n
    pa = float(np.abs(a.thumb - a.ref).mean(axis=-1)[cells].mean())
    pb = float(np.abs(b.thumb - b.ref).mean(axis=-1)[cells].mean())
    return pa, pb, n


def classify_thumbs(
    thumbs: list[np.ndarray], state: str, refs: Refs, body=None
) -> tuple[str | None, float, float]:
    """(name, distance, runner-up distance) for the thumbnails of one box; the name is None
    when no reference is within MAX_DISTANCE or when the pair stage cannot tell the best two
    apart (the pair-stage distances are returned then). `body`: the box's own colour."""
    if not thumbs:
        return None, 1e9, 1e9
    ranked = rank(thumbs, state, refs, body)
    first, second = ranked[0], ranked[1]
    if first.distance > MAX_DISTANCE:
        return None, first.distance, second.distance
    p1, p2, _ = pair_distances(first, second)
    if p1 > MAX_PAIR_RATIO * p2:
        return None, p1, p2
    return first.name, first.distance, second.distance


@dataclass(frozen=True)
class Match:
    """What identify() saw. dx, dy: the box's exact corner, logical px from the blob's (0 when
    the corner was not found)."""

    name: str | None
    state: str
    distance: float
    runner_up: float
    dx: float = 0.0
    dy: float = 0.0


def classify_image(bgr: np.ndarray, state: str | None = None, refs: Refs | None = None) -> Match:
    """Identify the box whose blob corner sits PAD logical px inside `bgr` (the BGR
    region_image of icon_rect). state None: read from the box's body right of the icon, where
    the box's own colour is measured too (the references are moved to it: Refs.stack)."""
    refs = refs or default_refs()
    h, w = bgr.shape[:2]
    if h < 8 or w < 8:
        return Match(None, state or "available", 1e9, 1e9)
    rgb = bgr[..., 2::-1]
    fx, fy = w / (RECT_W + PAD), h / (RECT_H + PAD)
    body_rgb = rgb[int(PAD * fy) :, int((PAD + ICON_W) * fx) :]
    if state is None:
        state = box_state(body_rgb)
    body = box_body(body_rgb, state)
    corner = find_corner(rgb, fx, fy, PAD * fx, PAD * fy)
    if corner is None:  # the blob's own corner, slid further
        thumbs = window_thumbs(rgb, PAD * fx, PAD * fy, fx, fy, FALLBACK_OFFSETS)
        dx = dy = 0.0
    else:
        thumbs = window_thumbs(rgb, corner[0], corner[1], fx, fy)
        dx, dy = corner[0] / fx - PAD, corner[1] / fy - PAD
    name, d1, d2 = classify_thumbs(thumbs, state, refs, body)
    return Match(name, state, d1, d2, dx, dy)


def identify(g, blob: blobs.Blob, refs: Refs | None = None) -> Match:
    """The research of the box found as `blob` (find_boxes), from a fresh capture."""
    bgr = g.region_image(icon_rect(blob.x1, blob.y1), atlas.ANCHOR_CENTER)
    return classify_image(bgr, None, refs)
