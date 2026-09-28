"""Meteorite research tree: the round nodes, their state, level and research, and the lines
that join them (numpy only).

Measured 2026-09-28 on the owner's Windows Epic client (1920x1009, new style) on meteorite
trees I..X and on tree X again with its two nodes that were not maxed. The tab shows 13 round
nodes (an icon on a disc inside a cyan ring of radius ~50 logical px) joined by cyan lines
into a tree: one START node (layer 0, three lines) and three chains of four nodes (layers
1..4; a layer needs levels in the layer before it on its chain). A small dark label under a
node shows its level. A MAXED node has a light-blue glowing disc (median green 183..199),
any other one a dark navy disc (55..56); both keep the ring. Where the nodes sit changes
from tree to tree (five shapes on trees I..X), so nothing here assumes a position.

Every size below is in LOGICAL px (atlas frame) and is multiplied by `scale`, the capture
px per logical px, so the reader works on any client size (checked on the captures resized
to widths 960..3840: 13 nodes, the right states, lines and start node on every size).

Pipeline (scan):
1. nodes: cyan mask (G >= 200, B >= 200, R <= 150) -> FFT convolution with a ring kernel
   (r 50 +-3) at half resolution -> peaks >= 0.20, 70 px apart -> a cheap check (60 % of 48
   sectors hold a cyan pixel at r 42..58) -> centre = a circle fitted to the first cyan run
   beyond 0.85 R on 72 rays (maxed: the glowing disc's edge, r 46.5..47.0; not maxed: the
   ring's outer edge, r 52.6..53.4; the two are concentric) -> kept when 75 % of 48 sectors
   hold a cyan pixel at r 45..55 (nodes 0.83..1.00, anything else 0.54 at most). A pixel
   count search for the centre sat 2.6 px off on average and 8 px at 1440 px wide; the fit
   agrees within 1.2 logical px on clients 1280..2560 px wide.
2. state: median green of the disc annulus r 36..44 above 120 -> maxed.
3. level: the label's digits (cx-30, cy+48)..(cx+31, cy+80), read by the caller's digit
   reader (130/130 labels at 1920; on resized captures some come back unread, never wrong).
4. research: the icon window +-42 around the centre with its background (B - R >= 70 and
   B >= 100: the glowing and the dark disc, the ring, the lines) zeroed, as 10x10 block
   means of the icon's R, G, B and its coverage (x255); blocks outside the unit circle are
   left out; distance = mean |diff| to a reference, the window slid +-4 logical px. One
   reference per research (vision/meteorite_refs.json, 28 names, from the owner's captures
   of trees I..X). Left-one-tree-out: 124/124 icons named right, the icons with no
   reference all rejected (22.6 at least); a not-maxed icon matches a reference built from
   maxed ones at 1.9..2.2 (next name 24.8 at least). Look-alike pairs (Weak / Powerless
   Boss and Enemy, the three scrolls) can be REJECTED by the ratio test below 1280 px, never
   swapped: `IconRefs.assign` with the tree's own 13 names names them all.
5. lines: line-core mask (G >= 225, B >= 225, R <= 90) on 3 px cells minus the node regions
   (disc r <= 60 and the label); a connected run of cells touching exactly two regions is an
   edge. Runs, not centre-to-centre segments: lines do not always aim at a node's centre
   (both lines into Tank Specialization on trees V and X meet its lower-left edge). The
   start is the only node with three edges; each of its chains gives layers 1..4 and a
   node's parent is the node before it (right on all 10 trees; the wiki's tree V is not).
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np

REFS_PATH = os.path.join(os.path.dirname(__file__), "meteorite_refs.json")

# -- nodes (logical px, relative to a node's centre) -----------------------------------------
NODE_R = 50.0  # the cyan ring's radius
RING_T = 3.0  # ring half thickness of the FFT kernel
FFT_MIN = 0.20  # kernel score of a candidate (real nodes 0.39..0.62, anything else <= 0.33)
MIN_NODE_DIST = 70  # between two candidates (nodes are >= 160 apart)
CHEAP_SECTORS_MIN = 0.60  # before the circle fit, sectors cyan at r 42..58
SECTOR_MIN = 0.75  # after it, sectors cyan at r 45..55
FIT_RADIUS = (0.85, 1.2)  # accepted fitted radius, share of NODE_R
DISC_ANNULUS = (36.0, 44.0)  # the disc ring whose green tells a maxed node
MAXED_G_MIN = 120  # median green there: maxed 183..199, not maxed 55..56
LABEL_REL = (-30, 48, 31, 80)  # the level's digits (x2, y2 exclusive)
LABEL_REGION_REL = (-30, 44, 31, 82)  # the whole dark label: part of the node for the lines

# -- icons -----------------------------------------------------------------------------------
ICON_HALF = 42
ICON_GRID = 10
ICON_SLIDE = 4  # the window is slid +-4 logical px, 1 px steps
ICON_OFFSETS = tuple(
    (dx, dy)
    for dy in range(-ICON_SLIDE, ICON_SLIDE + 1)
    for dx in range(-ICON_SLIDE, ICON_SLIDE + 1)
)
BG_BLUE_MINUS_RED = 70
BG_BLUE_MIN = 100
MAX_DISTANCE = 10.0  # own reference: 4.05 at most on the captures; another name: 6.7 at least
MAX_RATIO = 0.6  # best / runner-up (worst own ratio 0.42 at 1920 px)
POPUP_ICON_SCALE = 1.15  # the popup draws the node's icon 1.15 x bigger

# -- lines -----------------------------------------------------------------------------------
LINE_CELL = 3  # logical px
LINE_MIN_CELLS = 4
LINE_NODE_MARGIN = 10  # a node's region: its disc grown by this, and its label grown by 2


@dataclass
class Node:
    cx: float  # centre, px of the capture given to detect_nodes
    cy: float
    sectors: float  # share of ring sectors holding a cyan pixel
    maxed: bool
    disc_green: float
    level: int | None = None
    name: str | None = None
    distance: float = 0.0  # to the named reference (or to the best one when unnamed)
    runner_up: float = 0.0
    candidates: list[tuple[float, str]] = field(default_factory=list)


# -- masks -----------------------------------------------------------------------------------
def cyan_mask(rgb: np.ndarray) -> np.ndarray:
    r, g, b = (rgb[:, :, i].astype(np.int16) for i in range(3))
    return (g >= 200) & (b >= 200) & (r <= 150)


def line_mask(rgb: np.ndarray) -> np.ndarray:
    r, g, b = (rgb[:, :, i].astype(np.int16) for i in range(3))
    return (g >= 225) & (b >= 225) & (r <= 90)


# -- node detection --------------------------------------------------------------------------
def _block_mean(m: np.ndarray, d: int) -> np.ndarray:
    h, w = (m.shape[0] // d) * d, (m.shape[1] // d) * d
    return m[:h, :w].reshape(h // d, d, w // d, d).mean(axis=(1, 3))


def _ring_kernel(r: float, t: float) -> np.ndarray:
    n = int(np.ceil(r + t)) + 1
    yy, xx = np.mgrid[-n : n + 1, -n : n + 1]
    rr = np.hypot(yy, xx)
    k = ((rr >= r - t) & (rr <= r + t)).astype(np.float64)
    return k / k.sum()


def _convolve(img: np.ndarray, k: np.ndarray) -> np.ndarray:
    """`img` convolved with `k` (same size, zero padded), by FFT."""
    h, w = img.shape
    kh, kw = k.shape
    sh, sw = h + kh, w + kw
    full = np.fft.irfft2(np.fft.rfft2(img, (sh, sw)) * np.fft.rfft2(k, (sh, sw)), (sh, sw))
    return full[kh // 2 : kh // 2 + h, kw // 2 : kw // 2 + w]


def _peaks(score: np.ndarray, min_dist: int, threshold: float, most: int = 40):
    """Greedy maxima at least `min_dist` apart: (x, y) of the score grid."""
    s = score.copy()
    w = s.shape[1]
    out = []
    for _ in range(most):
        y, x = divmod(int(np.argmax(s)), w)
        if s[y, x] < threshold:
            break
        out.append((x, y))
        s[max(0, y - min_dist) : y + min_dist + 1, max(0, x - min_dist) : x + min_dist + 1] = -1
    return out


def fit_circle(
    mask: np.ndarray, cx: float, cy: float, radius: float, rays: int = 72, rounds: int = 2
) -> tuple[float, float, float | None]:
    """Circle fitted to the ring's outer edge around (cx, cy): on each ray, the last cyan
    sample of the first run that starts beyond 0.85 R (one-sample gaps bridged); rays more
    than 0.2 R off the median edge (a line leaving the ring, the label) are dropped.
    (centre x, centre y, radius), radius None when too few rays are left."""
    h, w = mask.shape
    ang = np.arange(rays) * 2 * np.pi / rays
    rs = np.arange(0.7 * radius, 1.4 * radius, 0.5)
    beyond = rs >= 0.85 * radius
    r = None
    for _ in range(rounds):
        xs = np.rint(cx + np.outer(np.cos(ang), rs)).astype(int)
        ys = np.rint(cy + np.outer(np.sin(ang), rs)).astype(int)
        inside = (xs >= 0) & (xs < w) & (ys >= 0) & (ys < h)
        cyan = np.zeros(xs.shape, bool)
        cyan[inside] = mask[ys[inside], xs[inside]]
        edge = np.full(rays, np.nan)
        for a in range(rays):
            idx = np.nonzero(cyan[a] & beyond)[0]
            if not len(idx):
                continue
            j = int(idx[0])
            while j + 1 < len(rs) and (cyan[a, j + 1] or (j + 2 < len(rs) and cyan[a, j + 2])):
                j += 1
            edge[a] = rs[j]
        if np.all(np.isnan(edge)):
            return float(cx), float(cy), None
        keep = np.abs(edge - np.nanmedian(edge)) <= 0.2 * radius
        if keep.sum() < rays // 3:
            return float(cx), float(cy), None
        px = cx + np.cos(ang[keep]) * edge[keep]
        py = cy + np.sin(ang[keep]) * edge[keep]
        a_ = np.c_[2 * px, 2 * py, np.ones(len(px))]
        sol = np.linalg.lstsq(a_, px**2 + py**2, rcond=None)[0]
        cx, cy = float(sol[0]), float(sol[1])
        r = float(np.sqrt(sol[2] + cx**2 + cy**2))
    return cx, cy, r


def sector_coverage(
    mask: np.ndarray, cx: float, cy: float, r0: float, r1: float, sectors: int = 48, steps: int = 6
) -> float:
    """Share of `sectors` angular sectors holding a cyan pixel between radius r0 and r1."""
    h, w = mask.shape
    ang = (np.arange(sectors) + 0.5) * 2 * np.pi / sectors
    rs = np.linspace(r0, r1, steps)
    xs = np.rint(cx + np.outer(rs, np.cos(ang))).astype(int)
    ys = np.rint(cy + np.outer(rs, np.sin(ang))).astype(int)
    inside = (xs >= 0) & (xs < w) & (ys >= 0) & (ys < h)
    hit = np.zeros(inside.shape, bool)
    hit[inside] = mask[ys[inside], xs[inside]]
    return float(hit.any(axis=0).mean())


def disc_green(rgb: np.ndarray, cx: float, cy: float, scale: float = 1.0) -> float:
    """Median green of the disc annulus DISC_ANNULUS around (cx, cy)."""
    n = int(np.ceil(DISC_ANNULUS[1] * scale)) + 1
    x0, y0 = round(cx), round(cy)
    ya, xa = max(0, y0 - n), max(0, x0 - n)
    win = rgb[ya : y0 + n + 1, xa : x0 + n + 1, 1].astype(np.float32)
    yy, xx = np.mgrid[ya : ya + win.shape[0], xa : xa + win.shape[1]]
    rr = np.hypot(yy - cy, xx - cx)
    ring = (rr >= DISC_ANNULUS[0] * scale) & (rr <= DISC_ANNULUS[1] * scale)
    return float(np.median(win[ring])) if ring.any() else 0.0


def detect_nodes(rgb: np.ndarray, scale: float = 1.0) -> list[Node]:
    """The round nodes of an RGB capture of the tree, top to bottom then left to right."""
    m = cyan_mask(rgb)
    d = max(1, round(2 * scale))
    radius, thick = NODE_R * scale, max(1.5, RING_T * scale)
    kernel = _ring_kernel(radius / d, max(1.0, thick / d))
    score = _convolve(_block_mean(m.astype(np.float32), d), kernel)
    out = []
    for x, y in _peaks(score, max(2, int(MIN_NODE_DIST * scale / d)), FFT_MIN):
        cx, cy = d * x + (d - 1) / 2, d * y + (d - 1) / 2
        if sector_coverage(m, cx, cy, radius - 8 * scale, radius + 8 * scale) < CHEAP_SECTORS_MIN:
            continue
        cx, cy, r = fit_circle(m, cx, cy, radius)
        if r is None or not FIT_RADIUS[0] * radius <= r <= FIT_RADIUS[1] * radius:
            continue
        cov = sector_coverage(m, cx, cy, radius - 5 * scale, radius + 5 * scale)
        if cov >= SECTOR_MIN:
            green = disc_green(rgb, cx, cy, scale)
            out.append(Node(cx, cy, cov, green > MAXED_G_MIN, green))
    out.sort(key=lambda n: (round(n.cy / (10 * scale)), n.cx))
    return out


# -- level labels ----------------------------------------------------------------------------
def label_rect(node: Node, scale: float = 1.0) -> tuple[int, int, int, int]:
    """The level digits of `node` in capture px (x1, y1, x2, y2), x2 and y2 exclusive."""
    x1, y1, x2, y2 = LABEL_REL
    return (
        round(node.cx + x1 * scale),
        round(node.cy + y1 * scale),
        round(node.cx + x2 * scale),
        round(node.cy + y2 * scale),
    )


def read_levels(
    rgb: np.ndarray, nodes: list[Node], scale: float, read: Callable[[np.ndarray], int | None]
) -> None:
    """Set each node's level; `read` takes a BGR crop (token_counter.read_image with the
    game's digit reader: None when a glyph touches a side, never a cut number)."""
    for n in nodes:
        x1, y1, x2, y2 = label_rect(n, scale)
        crop = np.ascontiguousarray(rgb[max(0, y1) : y2, max(0, x1) : x2, ::-1])
        n.level = read(crop) if crop.size else None


# -- icons -----------------------------------------------------------------------------------
def icon_integral(rgb: np.ndarray) -> np.ndarray:
    """Integral image of (icon R, G, B with the background zeroed, 255 x icon coverage)."""
    w = rgb.astype(np.float32)
    bg = ((w[:, :, 2] - w[:, :, 0]) >= BG_BLUE_MINUS_RED) & (w[:, :, 2] >= BG_BLUE_MIN)
    icon = (~bg).astype(np.float32)[:, :, None]
    four = np.concatenate([w * icon, 255 * icon], axis=2)
    s = np.zeros((rgb.shape[0] + 1, rgb.shape[1] + 1, 4), np.float64)
    s[1:, 1:] = four.cumsum(0).cumsum(1)
    return s


def icon_thumbs(
    integral: np.ndarray, cx: float, cy: float, scale: float = 1.0, offsets=ICON_OFFSETS
) -> np.ndarray:
    """(len(offsets), ICON_GRID, ICON_GRID, 4) block means of the icon window around
    (cx + dx, cy + dy), offsets in logical px."""
    offs = np.array(offsets, np.float64).reshape(-1, 2)
    t = np.linspace(-ICON_HALF, ICON_HALF, ICON_GRID + 1)
    xe = np.rint(cx + (offs[:, :1] + t[None, :]) * scale).astype(int)
    ye = np.rint(cy + (offs[:, 1:] + t[None, :]) * scale).astype(int)
    h, w = integral.shape[0] - 1, integral.shape[1] - 1
    xe, ye = np.clip(xe, 0, w), np.clip(ye, 0, h)
    g = integral[ye[:, :, None], xe[:, None, :]]
    sums = g[:, 1:, 1:] - g[:, :-1, 1:] - g[:, 1:, :-1] + g[:, :-1, :-1]
    area = np.diff(ye, axis=1)[:, :, None] * np.diff(xe, axis=1)[:, None, :]
    return sums / np.maximum(area, 1)[:, :, :, None]


def block_mask(n: int = ICON_GRID) -> np.ndarray:
    """The blocks whose centre lies inside the unit circle (the round icon)."""
    c = (np.arange(n) + 0.5) / n * 2 - 1
    yy, xx = np.meshgrid(c, c, indexing="ij")
    return np.hypot(yy, xx) <= 1.0


class IconRefs:
    """One reference thumbnail per research name."""

    def __init__(self, refs: dict[str, np.ndarray]):
        self.refs = refs
        self.mask = block_mask()

    @classmethod
    def load(cls, path: str = REFS_PATH) -> IconRefs:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        n = raw["grid"]
        return cls({k: np.array(v, np.float64).reshape(n, n, 4) for k, v in raw["refs"].items()})

    def distances(self, thumbs: np.ndarray, names=None) -> list[tuple[float, str]]:
        """(distance, name) to every reference (only `names` when given), closest first."""
        out = []
        for name, ref in self.refs.items():
            if names is not None and name not in names:
                continue
            d = np.abs(thumbs - ref[None])[:, self.mask].mean(axis=(1, 2))
            out.append((float(d.min()), name))
        return sorted(out)

    def classify(self, integral: np.ndarray, cx: float, cy: float, scale: float = 1.0, names=None):
        """(name or None, best distance, runner-up distance, every (distance, name)): a name
        when the best is within MAX_DISTANCE and MAX_RATIO x the runner-up."""
        ds = self.distances(icon_thumbs(integral, cx, cy, scale), names)
        if not ds:
            return None, 1e9, 1e9, ds
        d1, n1 = ds[0]
        d2 = ds[1][0] if len(ds) > 1 else 1e9
        ok = d1 <= MAX_DISTANCE and d1 <= MAX_RATIO * d2
        return (n1 if ok else None), d1, d2, ds

    def assign(self, integral: np.ndarray, nodes: list[Node], scale: float = 1.0, names=None):
        """Name every node. With `names` (the tree's own set) each name goes to one node at
        most, the closest pairs first, without the ratio test: a look-alike pair of the
        tree is then told apart by the pair itself."""
        pairs = []
        for i, n in enumerate(nodes):
            name, d1, d2, ds = self.classify(integral, n.cx, n.cy, scale, names)
            n.name, n.distance, n.runner_up, n.candidates = name, d1, d2, ds
            pairs += [(d, i, nm) for d, nm in ds if d <= MAX_DISTANCE]
        if names is None:
            return
        for n in nodes:
            n.name = None
        used = set()
        for d, i, nm in sorted(pairs):
            if nodes[i].name is None and nm not in used:
                nodes[i].name, nodes[i].distance = nm, d
                used.add(nm)


@lru_cache(maxsize=1)
def references() -> IconRefs:
    """The references shipped with the bot, loaded once."""
    return IconRefs.load()


def popup_research(
    refs: IconRefs, rgb: np.ndarray, cx: float, cy: float, scale: float, names=None
) -> tuple[str | None, float]:
    """The research whose icon a node's popup shows at (cx, cy) of `rgb` (capture px,
    `scale` capture px per logical px): the closest reference within MAX_DISTANCE, else
    None. Measured: Tank Specialization 1.74 (next 24.4), Attribute Armor 2.15 (next 30.4)."""
    ds = refs.distances(icon_thumbs(icon_integral(rgb), cx, cy, scale * POPUP_ICON_SCALE), names)
    if not ds or ds[0][0] > MAX_DISTANCE:
        return None, ds[0][0] if ds else 1e9
    return ds[0][1], ds[0][0]


# -- lines -----------------------------------------------------------------------------------
def tree_edges(rgb: np.ndarray, nodes: list[Node], scale: float = 1.0):
    """(i, j, cells) for each pair of nodes joined by a line (i < j)."""
    m = line_mask(rgb)
    cs = max(1, round(LINE_CELL * scale))
    h, w = (m.shape[0] // cs) * cs, (m.shape[1] // cs) * cs
    grid = m[:h, :w].reshape(h // cs, cs, w // cs, cs).any(axis=(1, 3))
    gh, gw = grid.shape
    yc = (np.arange(gh) + 0.5) * cs
    xc = (np.arange(gw) + 0.5) * cs
    owner = np.full((gh, gw), -1, int)
    x1, y1, x2, y2 = LABEL_REGION_REL
    for k, n in enumerate(nodes):
        region = (
            np.hypot(yc[:, None] - n.cy, xc[None, :] - n.cx) <= (NODE_R + LINE_NODE_MARGIN) * scale
        )
        region |= (
            (xc[None, :] >= n.cx + (x1 - 2) * scale)
            & (xc[None, :] < n.cx + (x2 + 2) * scale)
            & (yc[:, None] >= n.cy + (y1 - 2) * scale)
            & (yc[:, None] < n.cy + (y2 + 2) * scale)
        )
        owner[region] = k
    line = grid & (owner < 0)
    seen = np.zeros_like(line)
    edges: dict[tuple[int, int], int] = {}
    for gy, gx in zip(*np.nonzero(line), strict=True):
        if seen[gy, gx]:
            continue
        stack = [(gy, gx)]
        seen[gy, gx] = True
        size, touch = 0, set()
        while stack:
            y, x = stack.pop()
            size += 1
            for yy in (y - 1, y, y + 1):
                for xx in (x - 1, x, x + 1):
                    if 0 <= yy < gh and 0 <= xx < gw:
                        if owner[yy, xx] >= 0:
                            touch.add(int(owner[yy, xx]))
                        elif line[yy, xx] and not seen[yy, xx]:
                            seen[yy, xx] = True
                            stack.append((yy, xx))
        if size >= LINE_MIN_CELLS and len(touch) == 2:
            key = tuple(sorted(touch))
            edges[key] = edges.get(key, 0) + size
    return [(i, j, s) for (i, j), s in sorted(edges.items())]


def chains(n: int, edges) -> tuple[int, list[list[int]]] | None:
    """(start node, its chains from layer 1 on) when the `n` nodes and `edges` form the
    expected tree (n - 1 edges, one node with three, none with more); None otherwise (a
    line missed or crossing another: the caller falls back to the wiki layout)."""
    adj: dict[int, set[int]] = {i: set() for i in range(n)}
    for i, j, _ in edges:
        adj[i].add(j)
        adj[j].add(i)
    deg3 = [i for i in adj if len(adj[i]) == 3]
    if len(edges) != n - 1 or len(deg3) != 1 or any(not a or len(a) > 3 for a in adj.values()):
        return None
    start = deg3[0]
    out = []
    for first in sorted(adj[start]):
        seq, prev = [first], start
        while True:
            nxt = [k for k in adj[seq[-1]] if k != prev]
            if len(nxt) != 1:
                break
            prev = seq[-1]
            seq.append(nxt[0])
        out.append(seq)
    if sum(len(s) for s in out) != n - 1:
        return None
    return start, out


def parents(graph: tuple[int, list[list[int]]]) -> dict[int, int | None]:
    """Node index -> the index of the node it needs (None for the start)."""
    start, runs = graph
    out: dict[int, int | None] = {start: None}
    for run in runs:
        prev = start
        for k in run:
            out[k] = prev
            prev = k
    return out


# -- one call --------------------------------------------------------------------------------
@dataclass
class Tree:
    nodes: list[Node]
    edges: list[tuple[int, int, int]]
    graph: tuple[int, list[list[int]]] | None  # (start, chains) or None
    scale: float


def scan(
    rgb: np.ndarray,
    scale: float,
    refs: IconRefs | None = None,
    read: Callable[[np.ndarray], int | None] | None = None,
    names=None,
) -> Tree:
    """Nodes (levels when `read`, research names when `refs`, with `names` the tree's own
    set), lines and chains of an RGB capture of the tree."""
    nodes = detect_nodes(rgb, scale)
    if read is not None:
        read_levels(rgb, nodes, scale, read)
    if refs is not None:
        refs.assign(icon_integral(rgb), nodes, scale, names)
    edges = tree_edges(rgb, nodes, scale)
    return Tree(nodes, edges, chains(len(nodes), edges), scale)
