"""World-map alignment: the mission points of MapStart are fixed coordinates, valid only when
the map is at its default zoom and position. A zoomed map (mouse wheel over it) shows its
slider knob away from the left end; a dragged map keeps its offset across zooms and even
across closing and reopening the map (verified 2026-09-06). Both are put right before the
missions are clicked: wheel down over the map until the knob is home, then drag the map on
open sea by the opposite of the offset measured on a landmark (the "World of Alandria"
title, compared with a reference recorded at the default position)."""

from __future__ import annotations

import json
import math
import os

import numpy as np

from firestone_bot.game import Game
from firestone_bot.platform import capture
from firestone_bot.platform.types import Rect
from firestone_bot.vision import atlas

LANDMARK_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "vision", "map_landmark.json"
)
MIN_CORRELATION = 0.35  # below: the landmark is not there (a popup over it), do not move
TOLERANCE = 4  # logical px of offset left alone
# The game ignores a drag shorter than about 10 screen px: such an offset is left alone too
# (report ANHNX9, 1920x1080, 2026-10-25: "moved by (-4, -8)", a 9.6 px drag did nothing and
# the alignment was given up for the whole run). 10 px is well inside a 65 px mission icon.
MIN_DRAG_PX = 10
MAX_PASSES = 3
# The game sizes the world map when it starts. Started on a 16:9 client (fullscreen 1920x1080,
# the Mac) it fits the map to the width: 1009/1080 of the canvas-scaled map the mission points
# were measured on (report ANHNX9, 1920x1080, 2026-10-25: 25 map labels at scale 1.003 from
# the reference client where the canvas is at 1.070, so in coordinates mode a third of the
# points were clicked over 30 px beside their icon). Started on the reference client, the map
# keeps the canvas scale when the window is resized (1280x720, 2026-09-03). The landmark tells
# them apart: the reference recorded on the Mac matches a fitted map (0.67..0.79, the Windows
# one 0.33), the Windows one a canvas-scaled map (0.83..0.98, the Mac one 0.22).
FITTED_REF = "mac-original"
FITTED_SCALE = 1009 / 1080  # logical size of a fitted map against the mission points'
FITTED_MARGIN = 0.15  # correlation by which the Mac reference must win
SCALE_KEY = "map_scale"  # Game.vars: the open map's logical scale (1.0 until measured)


def zoom_knob_x(g: Game) -> int | None:
    """Logical x of the slider knob (its dark rim above the track), None when not visible."""
    x1, y1, x2, y2 = atlas.MAP_ZOOM_KNOB_ROW
    img = g.region_image((x1, y1, x2, y2)).astype(int)
    b, gr, r = img[:, :, 0], img[:, :, 1], img[:, :, 2]
    dark = (r > 70) & (r < 170) & (gr < 110) & (b < 90)
    cols = np.nonzero(dark.sum(axis=0) > 0)[0]
    if not len(cols):
        return None
    px_per_logical = img.shape[1] / (x2 - x1)
    return round(x1 + (cols.min() + cols.max()) / 2 / px_per_logical)


def _resample(img: np.ndarray, out_w: int, out_h: int) -> np.ndarray:
    ys = (np.arange(out_h) * img.shape[0] / out_h).astype(int)
    xs = (np.arange(out_w) * img.shape[1] / out_w).astype(int)
    return img[ys][:, xs]


def _gray_logical(g: Game, rect, scale: float) -> np.ndarray:
    """Grey capture of a centre-anchored logical rect, resampled to `scale` px per logical."""
    vp = g._viewport()
    sx1, sy1 = vp.to_screen(rect[0], rect[1], atlas.ANCHOR_CENTER)
    sx2, sy2 = vp.to_screen(rect[2], rect[3], atlas.ANCHOR_CENTER)
    img = capture.grab(Rect(sx1, sy1, sx2 - sx1, sy2 - sy1))[:, :, :3].astype(float).mean(axis=2)
    return _resample(img, round((rect[2] - rect[0]) * scale), round((rect[3] - rect[1]) * scale))


def load_landmark(path: str = LANDMARK_PATH) -> list[dict]:
    """The bundled references (one per client the map was recorded on: the title's size
    differs between the Mac and the Windows clients, so the best-correlating reference is
    used). Old single-reference files are read too."""
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    refs = d.get("refs", [d])
    for r in refs:
        r["gray"] = np.array(r["gray"], dtype=float).reshape(r["h"], r["w"])
    return refs


def best_match(big: np.ndarray, ref: np.ndarray, step: int = 1) -> tuple[float, int, int]:
    """(correlation, dx, dy) of `ref` inside `big` (top-left of the best window)."""
    th, tw = ref.shape
    t = ref - ref.mean()
    tn = float(np.sqrt((t * t).sum()))
    best = (-2.0, 0, 0)
    for dy in range(0, big.shape[0] - th + 1, step):
        for dx in range(0, big.shape[1] - tw + 1, step):
            w = big[dy : dy + th, dx : dx + tw]
            w = w - w.mean()
            d = float(np.sqrt((w * w).sum())) * tn
            c = float((w * t).sum() / d) if d else 0.0
            if c > best[0]:
                best = (c, dx, dy)
    return best


def landmark_offset(
    g: Game, landmark: list[dict] | None = None, scores: dict[str, float] | None = None
) -> tuple[float, int, int]:
    """(correlation, dx, dy): how far (logical px) the landmark sits from its reference place
    (the reference that correlates best wins). `scores` receives each reference's best
    correlation, by name."""
    best = (-2.0, 0, 0)
    # a near search first (0.5 s), then a wide one (2.5 s): the map left 220 px off by an
    # interrupted detection pass was never found again (2026-09-08, search radius 100)
    for m in (atlas.MAP_LANDMARK_SEARCH, atlas.MAP_LANDMARK_SEARCH_WIDE):
        for lm in landmark or load_landmark():
            x1, y1, x2, y2 = lm["rect"]
            s = lm["scale"]
            big = _gray_logical(g, (x1 - m, y1 - m, x2 + m, y2 + m), s)
            c, dx, dy = best_match(big, lm["gray"])
            if scores is not None:
                name = lm.get("name", "")
                scores[name] = max(c, scores.get(name, -2.0))
            if c > best[0]:
                best = (c, round(dx / s) - m, round(dy / s) - m)
        if best[0] >= MIN_CORRELATION:
            break
    return best


def map_scale(scores: dict[str, float]) -> float | None:
    """The open map's logical scale against the mission points', from the landmark's scores:
    FITTED_SCALE when the Mac reference wins clearly, 1.0 when another one does, None when
    no reference wins clearly (a panel or a popup over the title, the map dragged far off:
    the scale measured before is kept, review 2026-10-28)."""
    fitted = scores.get(FITTED_REF, -2.0)
    other = max((c for name, c in scores.items() if name != FITTED_REF), default=-2.0)
    if fitted >= MIN_CORRELATION and fitted - other >= FITTED_MARGIN:
        return FITTED_SCALE
    if other >= MIN_CORRELATION and other - fitted >= FITTED_MARGIN:
        return 1.0
    return None


def _note_scale(g: Game, scale: float | None) -> None:
    """Keep the map's scale for the mission points (map_start), said when it changes."""
    if scale is None:
        return
    if scale != g.vars.get(SCALE_KEY, 1.0):
        if scale == 1.0:
            g.status("Map: drawn at the reference scale, mission points used as measured")
        else:
            g.status(
                f"Map: drawn at {scale:.3f} of the reference scale (the game started at 16:9), "
                "mission points moved towards the centre"
            )
    g.vars[SCALE_KEY] = scale


def align_map(g: Game) -> bool:
    """Reset the zoom and the drag offset of the open world map. Returns whether the map is
    known to be in place (False: landmark not found, or still off after MAX_PASSES)."""
    knob = zoom_knob_x(g)
    if knob is not None and knob > atlas.MAP_ZOOM_KNOB_HOME + atlas.MAP_ZOOM_TOLERANCE:
        g.status(f"Map: zoomed in (slider at {knob - atlas.MAP_ZOOM_KNOB_HOME} px), zooming out")
        g.move_to(atlas.MAP_WHEEL_CENTRE)
        g.sleep(200)
        g.wheel(-atlas.MAP_ZOOM_OUT_NOTCHES, 100)
        g.sleep(800)
    landmark = load_landmark()
    if g.vars.get("map_align_off"):
        # gave up earlier in this run (see below); the scale is still measured, a relaunched
        # game may have started at another size (review 2026-10-28)
        scores: dict[str, float] = {}
        if landmark_offset(g, landmark, scores)[0] >= MIN_CORRELATION:
            _note_scale(g, map_scale(scores))
        return False
    previous = None
    for _ in range(MAX_PASSES):
        scores = {}
        c, dx, dy = landmark_offset(g, landmark, scores)
        if c < MIN_CORRELATION:
            g.status(f"Map: landmark not found (correlation {c:.2f}), map left as is")
            return False  # the scale measured before is kept
        _note_scale(g, map_scale(scores))  # at each pass: the last one sees the map in place
        if abs(dx) <= TOLERANCE and abs(dy) <= TOLERANCE:
            return True
        if math.hypot(dx, dy) * g._viewport().rel_scale < MIN_DRAG_PX:
            return True  # a drag this short is ignored by the game
        if (
            previous is not None
            and abs(dx - previous[0]) <= TOLERANCE
            and abs(dy - previous[1]) <= TOLERANCE
        ):
            # The drag changed nothing: the map is already where the game puts it and the
            # reference is off for this client (a user, 2026-09-08: "out of position while
            # at default, fails to move it every time"). Leave it and stop trying this run.
            g.status("Map: dragging does not move the landmark, keeping the map as it is")
            g.save_diagnostic("map-align-stuck.png")
            g.vars["map_align_off"] = True
            return False
        previous = (dx, dy)
        g.status(f"Map: moved by ({dx}, {dy}) px, dragging it back")
        x, y = atlas.MAP_NORTH_DRAG_FROM
        g.drag(x, y, x - dx, y - dy, anchor=atlas.ANCHOR_CENTER)
        g.sleep(800)
    g.status("Map: still off after dragging it back, missions may miss")
    return False
