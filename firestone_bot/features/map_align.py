"""World-map alignment: the missions are looked for (features/map_detect.py) on the map at
its default zoom and position. A zoomed or dragged map hides labels beyond the edges of the
screen, the drags that reveal its north and south edges (atlas.MAP_DETECT_SCROLL) start from
there, the missions already clicked are remembered by their place on it (MapStartState.ini),
and the fallback's fixed mission points (a map drawn too small for its labels, map_start)
are valid only there. A zoomed map (mouse wheel over it) shows its slider knob away from the
left end; a dragged map keeps its offset across zooms and even across closing and reopening
the map (verified 2026-09-06). Both are put right before the missions are looked for: wheel
down over the map until the knob is home, then drag the map on open sea by the opposite of
the offset measured on a landmark (the "World of Alandria" title, compared with a reference
recorded at the default position).

The landmark also tells the scale the game drew the map at (SCALE_KEY), which sizes the
labels' thresholds (drawn_scale), places the fallback's points and decides between the two
(map_start.DETECT_MIN_SCALE)."""

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
MIN_CORRELATION = 0.35  # below: the landmark is not there (see align_map: looked for higher once)
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
# Game.vars: the landmark was not found even with the map dragged up (see _look_higher): not
# tried again this run, unless a search beyond the edge may have left the map dragged down
# since (map_start drops it; the runner at each start). A client no reference matches would
# otherwise bounce the map at every alignment.
RECOVERY_OFF = "map_recovery_off"
ALIGN_OFF = "map_align_off"  # Game.vars: dragging did not move the landmark: off this run


def drawn_scale(g: Game) -> float:
    """Screen px per reference-client px of the open map: the client's canvas scale against
    the reference client's (Viewport.rel_scale) times the map's logical scale the landmark
    measured (SCALE_KEY: 1.0 canvas-scaled, FITTED_SCALE fitted; 1.0 before the first
    measure). Exactly 1.0 on the reference client (1920x1009) and on a map fitted at
    1920x1080; 1.070 on a canvas-scaled 2560x1080 map, 0.711 on a 1366x768 map fitted. The
    size of the duration labels (map_detect's thresholds) and the switch to the fixed mission
    points (map_start) follow it; rounded so that a product of two ratios lands on 1.0. A
    window made taller than 16:9 after the game started draws the map at the client's height
    instead (h/1009: 0.89..1.01 at 1440x900, 1600x1000, 1280x1024 on 2026-10-31, where this
    reads 0.71..0.89) and its landmark is not found: this reads low there, which the labels
    tolerate (map_detect) and map_start's switch corrects with the height."""
    return round(g._viewport().rel_scale * g.vars.get(SCALE_KEY, 1.0), 3)


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
    used). The game sizes the world map when it starts: fitted to the width on a 16:9 client
    (fullscreen 1920x1080, the Mac), 1009/1080 of the canvas-scaled map of the reference
    client, which it keeps when the window is resized (1280x720, 2026-09-03). The Mac
    reference matches a fitted map (0.67..0.79, the Windows one 0.33), the Windows one a
    canvas-scaled map (0.83..0.98, the Mac one 0.22; report ANHNX9, MEASUREMENTS
    2026-10-28). Old single-reference files are read too."""
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
    # interrupted detection pass was never found again (2026-09-08, search radius 100). It
    # finds a map left up; one left down hides the landmark under the bottom HUD (align_map
    # drags it up to look, _look_higher)
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
    """Keep the map's scale (drawn_scale: the labels' size, the fallback's points), said when
    it changes."""
    if scale is None:
        return
    if scale != g.vars.get(SCALE_KEY, 1.0):
        if scale == 1.0:
            g.status("Map: drawn at the reference scale")
        else:
            g.status(
                f"Map: drawn at {scale:.3f} of the reference scale (the game started at 16:9), "
                "the labels' size and the mission points follow it"
            )
    g.vars[SCALE_KEY] = scale


def _drag(g: Game, dy: int) -> None:
    """Drag the map `dy` logical px down (up when negative) from open sea."""
    x, y = atlas.MAP_DRAG_FROM
    g.drag(x, y, x, y + dy, anchor=atlas.ANCHOR_CENTER)


def _look_higher(
    g: Game, landmark: list[dict], scores: dict[str, float], c: float
) -> tuple[float, int, int]:
    """The landmark not found: a search beyond the north edge (the map dragged down by
    MAP_DETECT_SCROLL) cut short before its drag back (Stop, the mouse guard's pause, the game
    not in front, a crash) puts the landmark under the bottom HUD, out of any search, and every
    later visit would search a moved map (review of 8558a26, F2). The map is dragged up by that
    much once and the landmark looked for again; still not there (a popup or a panel over it),
    the drag is undone. On a map in place the drag does no harm: the landmark is then found
    MAP_DETECT_SCROLL px up, within the wide search, and the alignment drags it back."""
    scroll = atlas.MAP_DETECT_SCROLL
    g.status(
        f"Map: landmark not found (correlation {c:.2f}), dragging the map up {scroll} px in "
        "case a search beyond its edge left it down"
    )
    _drag(g, -scroll)
    g.sleep(800)
    scores.clear()
    found = landmark_offset(g, landmark, scores)
    if found[0] < MIN_CORRELATION:
        _drag(g, scroll)
        g.sleep(800)
        g.vars[RECOVERY_OFF] = True
    return found


def align_map(g: Game) -> bool:
    """Reset the zoom and the drag offset of the open world map, and measure the scale it is
    drawn at (SCALE_KEY). Returns whether the map is known to be in place (False: landmark
    not found, or still off after MAX_PASSES)."""
    knob = zoom_knob_x(g)
    if knob is not None and knob > atlas.MAP_ZOOM_KNOB_HOME + atlas.MAP_ZOOM_TOLERANCE:
        g.status(f"Map: zoomed in (slider at {knob - atlas.MAP_ZOOM_KNOB_HOME} px), zooming out")
        g.move_to(atlas.MAP_WHEEL_CENTRE)
        g.sleep(200)
        g.wheel(-atlas.MAP_ZOOM_OUT_NOTCHES, 100)
        g.sleep(800)
    landmark = load_landmark()
    if g.vars.get(ALIGN_OFF):
        # gave up earlier in this run (see below); the scale is still measured, a relaunched
        # game may have started at another size (review 2026-10-28)
        scores: dict[str, float] = {}
        if landmark_offset(g, landmark, scores)[0] >= MIN_CORRELATION:
            _note_scale(g, map_scale(scores))
        return False
    previous = None
    looked_higher = False
    for _ in range(MAX_PASSES):
        scores = {}
        c, dx, dy = landmark_offset(g, landmark, scores)
        if c < MIN_CORRELATION and not looked_higher and not g.vars.get(RECOVERY_OFF):
            if not g.found(atlas.DIALOG_CLOSE_X):
                # the map did not open (go_map gave up): no drag on another screen, and the
                # look higher stays for a visit that has the map (review of c515703)
                g.status("Map: the map is not open, alignment skipped")
                return False
            looked_higher = True
            c, dx, dy = _look_higher(g, landmark, scores, c)
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
            g.vars[ALIGN_OFF] = True
            return False
        previous = (dx, dy)
        g.status(f"Map: moved by ({dx}, {dy}) px, dragging it back")
        x, y = atlas.MAP_DRAG_FROM
        g.drag(x, y, x - dx, y - dy, anchor=atlas.ANCHOR_CENTER)
        g.sleep(800)
    g.status("Map: still off after dragging it back, missions may miss")
    return False
