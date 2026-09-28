"""Library: keep the two firestone research slots busy (rewritten 2026-09-08 for the
research tree of game 9.1.1; the AHK Research.ahk flow and its slot probes no longer match
anything on screen and its "free completion" click landed on the gem "Speed up" button).

Flow: open the library (entry probe), select the Firestone tab, read the two slot panels at
the bottom (green button = finished, claim it; orange "Speed up" = running; neither =
empty), then while a panel is empty pick a research in the tree and start it: its box is
tapped and the popup's green "Research" button pressed. The gem buttons ("Complete
instantly", "Speed up") are never clicked.

The panels are read again before every claim and start, and a start is confirmed by the
number of busy panels: the game keeps the panels packed to the left with the newest research
first, so a slot followed by its index changed under the bot. With both researches finished
between two visits, the second one was left unclaimed for a whole cycle and the free slot was
reported as not started ("not seeing available research", Qualitas, 2026-09-24).

Research priorities (owner request 2026-09-28: users disliked the bot starting whatever box
sat right-most in the tree; they choose up to five researches, in their order):

- Scan. The tree reopens where it was left: it is wheeled back to its start, then looked at
  in stops of RS_SCAN_NOTCHES to its end (the view stops moving). At every stop the boxes of
  the three states (available, maxed, running) are found and identified by their icon
  (vision/research_icons.py). A box's place in the tree is its place in the view plus how far
  the view has moved (measured on the tree's own pixels, view_shift: 672 px a stop, the last
  one shorter); its column is that place over the column pitch from column 1, the left-most
  box at the tree's start; its row one of the five levels of the columns of 1, 2 or 3 boxes.
  A box seen at several stops counts once; a box whose icon is cut (the view's left edge, the
  right-hand tab panel) is left for another stop; an icon a sparkle hid is grabbed once more.
  Every stop is looked at, as before: a box in the middle of a tree, under the tab panel at
  the start and past the left edge at the end, was never seen when only the two ends were
  (Qualitas, 2026-09-26, "Meteorite hunter" in Tree II). On the owner's captures of trees
  I..XIII (2026-09-28, every stop): 554 whole boxes, all identified, the shifts read within
  8 px of the wheel's, each tree's 16 boxes placed and its layout the only one found.
- Layout. The tree layouts of research_data (the wiki's, with the in-game corrections) that
  hold every box seen at its column and row, and every identified one under its name. Trees
  with the same content are one layout; when layouts of different contents all fit, only what
  they agree on is used (a name in none of them is absent, in all of them it lies at its
  left-most column at least).
- Choice, for each priority in order: seen and available, it is started; seen maxed or
  running, the next priority. In the layout but unseen (a locked column: locked boxes were
  never seen live) or its popup offers no Research button: the research that unlocks it, an
  available box of the nearest seen column before it (a priority first, else the top one),
  the column before that one when all of its boxes are locked too; nothing to start there
  (maxed or running), the next priority. Unseen in a column that shows (columns unlock as a
  whole: the box was missed), absent from the tree (said once per game day and tree): the
  next priority. No priority started: with "Research something else"
  (ResearchAnyOther, on by default) the choice of old, the right-most available box first and
  every one in turn; off, the slot stays free.
- Start. The view goes back to a stop where the box's icon is whole (from the tree's start,
  the scan's own stops), the box is found again by its place and icon, tapped, and the
  popup's Research button pressed. A popup without it is closed. The tree is left at its
  start after the visit, and a search that started nothing pauses the next ones 15 minutes.
"""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np

from firestone_bot import research_data
from firestone_bot.features.big_close import big_close
from firestone_bot.game import Game
from firestone_bot.vision import atlas, blobs, research_icons
from firestone_bot.vision.atlas import Point

log = logging.getLogger("firestone_bot")

NO_NODE_PAUSE_S = 15 * 60  # after a search that started nothing, the next one waits
NO_NODE_UNTIL = "research_no_node_until"  # Game.vars: monotonic second of the next search
SLOT_ANCHOR = (atlas.LEFT, atlas.BOTTOM)
PRIORITY_KEYS = tuple(f"ResearchPriority{i}" for i in range(1, 6))


def _strip_blobs(g: Game, colour: int, variation: int) -> list[blobs.Blob]:
    return blobs.find_blobs(
        g,
        atlas.RS_SLOT_STRIP,
        colour,
        variation,
        anchor=SLOT_ANCHOR,
        min_w=atlas.RS_BUTTON_MIN_W,
        min_h=atlas.RS_BUTTON_MIN_H,
    )


def slot_buttons(g: Game) -> dict[int, tuple[str, Point]]:
    """State and button of each busy slot, read from the strip covering both panels.

    A green button ('done', to claim) wins over the orange "Speed up" ('running'); a slot with
    neither is empty. The rightmost blob of a slot is its button: the "Completed" progress bar
    is green too and sits left of the Claim button.
    """
    out: dict[int, tuple[str, Point]] = {}
    found: list[tuple[str, blobs.Blob]] = []
    for colour in atlas.RS_SLOT_DONE:
        found += [("done", b) for b in _strip_blobs(g, colour, atlas.RS_SLOT_DONE_VAR)]
    found += [
        ("running", b) for b in _strip_blobs(g, atlas.RS_SLOT_RUNNING, atlas.RS_SLOT_RUNNING_VAR)
    ]
    for slot in range(atlas.RS_SLOT_COUNT):
        here = [(kind, b) for kind, b in found if (b.cx < atlas.RS_SLOT_SPLIT) == (slot == 0)]
        for kind in ("done", "running"):
            same = [b for k, b in here if k == kind]
            if same:
                b = max(same, key=lambda b: b.cx)
                out[slot] = (kind, Point(b.cx, b.cy, SLOT_ANCHOR))
                break
    return out


def slot_state(g: Game, slot: int) -> str:
    """'done' (green button), 'running' (orange Speed up), or 'empty'."""
    return slot_buttons(g).get(slot, ("empty", None))[0]


PARK_MS = 300  # a hovered button is lighter: let it fade before the strip is read
START_CONFIRM_MS = 3000  # the new research can reach its panel after a server round trip
MAX_ACTIONS = 6  # claims and starts in one visit (two slots: four is the most needed)
LABELS = {"running": "in progress", "done": "finished, not claimed", "empty": "free"}


def panels(g: Game) -> list[tuple[str, Point | None]]:
    """State and button of each panel, left to right, read with the pointer parked."""
    g.move_to(atlas.RS_PARK)
    g.sleep(PARK_MS)
    found = slot_buttons(g)
    return [found.get(i, ("empty", None)) for i in range(atlas.RS_SLOT_COUNT)]


def busy_count(states: list[tuple[str, Point | None]]) -> int:
    return sum(kind != "empty" for kind, _ in states)


def _started(g: Game, busy: int) -> bool:
    """A research was started: more panels are busy than before the click. The panels are
    counted, not looked up by index: the game shows the newest research in the first panel
    and moves the others right, so "slot 2 did not start" was logged for a research that
    had started in slot 1 (owner's log: 9 visits, then 3 more Research clicks on a full
    queue)."""
    waited = 0
    while True:
        if busy_count(panels(g)) > busy:
            return True
        if waited >= START_CONFIRM_MS:
            return False
        g.sleep(500)
        waited += 500 + PARK_MS


def _claimed(g: Game, done: int) -> bool:
    """The claim was taken: fewer panels show a green button than before the click. Until
    then the panels are not trusted: a read taken before the game answered still shows the
    claimed panel, and a second click at that spot could land on the orange gem "Speed up"
    of the research that slides into it."""
    waited = 0
    while True:
        states = panels(g)
        if sum(kind == "done" for kind, _ in states) < done:
            return True
        if waited >= START_CONFIRM_MS:
            return False
        g.sleep(500)
        waited += 500 + PARK_MS


# --- the tree view ------------------------------------------------------------------------
STILL_PX = 25  # logical px: a smaller move is no move (the tree's start or end reached)
MAX_STOPS = 8  # scan stops from the start (a tree takes 5: 2478 px at 672 a stop)
MAX_FIT = 6.0  # mean levels: a worse fit of two profiles is no view shift at all


def tree_profile(g: Game) -> np.ndarray:
    """Mean brightness of each column of the tree band: what the view shift is read on."""
    img = g.region_image(atlas.RS_TREE_BAND, atlas.ANCHOR_CENTER)
    return img.astype(np.float32).mean(axis=(0, 2))


def _fit(before: np.ndarray, after: np.ndarray) -> tuple[float, int, int] | None:
    """(mean difference, px, profile length) of the best move right of `after` against
    `before`, None when the profiles are too short."""
    n = min(len(before), len(after))
    if n < 20:
        return None
    before, after = before[:n], after[:n]
    best = None
    for s in range(n - n // 5):
        d = float(np.abs(after[s:] - before[: n - s]).mean())
        if best is None or d < best[0]:
            best = (d, s, n)
    return best


def view_shift(before: np.ndarray, after: np.ndarray) -> float | None:
    """How far the tree moved right between two profiles, as a share of the band width
    (0 = the same view); None when no shift matches (the view changed otherwise)."""
    best = _fit(before, after)
    if best is None or best[0] > MAX_FIT:
        return None
    return best[1] / best[2]


def _scrolled(before: np.ndarray, after: np.ndarray) -> float | None:
    """How far the view went toward the tree's end between two profiles (the tree moved
    left), logical px; negative toward its start; None when no shift fits."""
    band = atlas.RS_TREE_BAND[2] - atlas.RS_TREE_BAND[0]
    fits = []
    right = _fit(before, after)  # the tree moved right: toward the start
    if right is not None and right[0] <= MAX_FIT:
        fits.append((right[0], -right[1] / right[2] * band))
    left = _fit(after, before)  # the tree moved left: toward the end
    if left is not None and left[0] <= MAX_FIT:
        fits.append((left[0], left[1] / left[2] * band))
    return min(fits)[1] if fits else None


def _still(before: np.ndarray, after: np.ndarray) -> bool:
    moved = _scrolled(before, after)
    return moved is not None and abs(moved) < STILL_PX


def _wheel(g: Game, notches: int) -> None:
    g.move_to(atlas.RS_TREE_HOVER)
    g.wheel(notches)
    g.wait_still()


def rewind(g: Game, first: int = atlas.RS_SCAN_NOTCHES) -> bool:
    """Wheel the tree back to its start: until a wheel up leaves the view where it was.
    `first`: the notches of the first wheel (enough to reach the start when the view's place
    is known). False when the view kept changing."""
    before = tree_profile(g)
    for notches in (first, atlas.RS_SCAN_NOTCHES, atlas.RS_REWIND_NOTCHES, atlas.RS_SCAN_NOTCHES):
        _wheel(g, notches)
        after = tree_profile(g)
        if _still(before, after):
            return True
        before = after
    return False


def _view_edges(g: Game) -> tuple[float, float]:
    """The tree view's left edge and the right-hand tab panel's left edge, as logical x in
    the tree's centre-anchored frame: a client narrower than the reference cuts the view at
    its own edge (logical 63 at 16:9), and the panel is anchored to the right."""
    vp = g._viewport()
    c = vp.client
    left = vp.to_logical(c.x, c.y + c.h // 2, atlas.ANCHOR_CENTER)[0]
    sx, sy = vp.to_screen(atlas.RS_TAB_PANEL_X, 500, (atlas.RIGHT, atlas.CENTER))
    panel = vp.to_logical(sx, sy, atlas.ANCHOR_CENTER)[0]
    return max(atlas.RS_TREE_AREA[0], left), panel


def _area(panel: float) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = atlas.RS_TREE_AREA
    return x1, y1, min(x2, int(panel) - 3), y2


# --- the scan -------------------------------------------------------------------------------
CUT_PX = 3  # a box starting this close to the view's left edge is cut there
COLUMN_SLACK = 60  # logical px off the column grid: a box's part (a shooting star split it)
ROW_SLACK = 40  # logical px off the row levels (121 apart)
REGRAB_MS = 400  # an icon a sparkle hid is grabbed again after this
BOUNCE_MS = 500  # a tapped box bounces after its popup closes (identified at 9.8 against 11)
FIND_PX = 60  # logical px: the chosen box is found again this close to where the scan saw it


@dataclass
class Seen:
    """A box at one stop: its blob, exact left and top edges (view, logical) and research."""

    blob: blobs.Blob
    x: float
    y: float
    name: str | None
    state: str


@dataclass
class Box:
    """A node box of the tree as the scan saw it."""

    col: int  # 1 = the left-most column
    row: int  # level 0..4: columns of 3 boxes use 0/2/4, of 2 boxes 1/3, of 1 box 2
    name: str | None  # None: its icon was never identified
    state: str  # "available", "maxed" or "running"
    x: float = 0.0  # left edge, tree px (the view's x plus the view's shift)
    stops: list[int] = field(default_factory=list)  # scan stops where its icon is whole

    @property
    def label(self) -> str:
        return self.name or f"the column {self.col} research"


@dataclass
class Scan:
    boxes: list[Box]
    shifts: list[float] = field(default_factory=list)  # view shift of each stop, tree px
    profiles: list[np.ndarray] = field(default_factory=list)
    at: int = 0  # the stop on screen, -1 unknown
    complete: bool = False  # the tree's end was reached


def row_of(y: float) -> int | None:
    """Row level of a box from its top (logical, centre-anchored)."""
    tops = atlas.RS_ROW_TOPS
    i = min(range(len(tops)), key=lambda k: abs(y - tops[k]))
    return i if abs(y - tops[i]) <= ROW_SLACK else None


def column_of(x: float, origin: float) -> int | None:
    """Column of a box from its left edge in tree px, column 1 starting at `origin`."""
    k = (x - origin) / atlas.RS_COLUMN_PITCH
    col = round(k)
    if col < 0 or abs(k - col) * atlas.RS_COLUMN_PITCH > COLUMN_SLACK:
        return None
    return col + 1


def _cut(b: blobs.Blob, left: float, panel: float) -> bool:
    return b.x1 <= left + CUT_PX or b.x1 + research_icons.ICON_W > panel


def _seen(b: blobs.Blob, m: research_icons.Match) -> Seen:
    return Seen(b, b.x1 + m.dx, b.y1 + m.dy, m.name, m.state)


def stop_boxes(g: Game) -> list[Seen]:
    """The boxes of the view whose icon is whole, identified (an unknown icon twice)."""
    left, panel = _view_edges(g)
    out = []
    for b in research_icons.find_boxes(g, _area(panel)):
        if not _cut(b, left, panel):
            out.append(_seen(b, research_icons.identify(g, b)))
    if any(s.name is None for s in out):
        g.sleep(REGRAB_MS)  # a sparkle over an icon lasts a moment
        out = [s if s.name else _seen(s.blob, research_icons.identify(g, s.blob)) for s in out]
    return out


def _moved_by_boxes(before: list[Seen], after: list[Seen]) -> float | None:
    """The view's move from the boxes identified at both stops (when the profiles do not
    fit, a sparkle or a shooting star over the band)."""
    moves = [
        b.x - a.x
        for b in before
        for a in after
        if b.name and b.name == a.name and abs(b.y - a.y) < ROW_SLACK
    ]
    return float(np.median(moves)) if moves else None


def merge(stops: list[list[Seen]], shifts: list[float]) -> list[Box]:
    """The boxes of every stop placed in the tree, each once, left to right."""
    origin = min((s.x for s in stops[0]), default=atlas.RS_COLUMN1_X) if stops else 0
    boxes: dict[tuple[int, int], Box] = {}
    for stop, (here, shift) in enumerate(zip(stops, shifts, strict=True)):
        for s in here:
            x = s.x + shift
            col, row = column_of(x, origin), row_of(s.y)
            if col is None or row is None:
                log.debug("research box off the grid: %s at x %.0f y %.0f", s.name, x, s.y)
                continue
            box = boxes.get((col, row))
            if box is None:
                boxes[(col, row)] = Box(col, row, s.name, s.state, x, [stop])
                continue
            box.stops.append(stop)
            if box.name is None and s.name is not None:
                box.name, box.state = s.name, s.state
            elif s.name is not None and s.name != box.name:
                log.debug("research box %d/%d read %s and %s", col, row, box.name, s.name)
    return sorted(boxes.values(), key=lambda b: (b.col, b.row))


def scan_tree(g: Game) -> Scan:
    """Every box of the tree, from its start to its end (the view is left at the end)."""
    if not rewind(g):
        g.status("Research: the tree kept moving on its way back to its start")
    scan = Scan([])
    stops: list[list[Seen]] = []
    shift = 0.0
    for stop in range(MAX_STOPS):
        if stop:
            _wheel(g, -atlas.RS_SCAN_NOTCHES)
        profile = tree_profile(g)
        moved = _scrolled(scan.profiles[-1], profile) if stop else 0.0
        if moved is not None and stop and abs(moved) < STILL_PX:
            scan.complete = True  # the end: this stop is the one before
            break
        here = stop_boxes(g)
        if moved is None or moved < 0:  # the profiles do not fit: the boxes seen at both stops
            moved = _moved_by_boxes(stops[-1], here)
            if moved is not None and abs(moved) < STILL_PX:
                scan.complete = True
                break
        if moved is None or moved < 0:  # a WheelDown never moves the view back
            g.status(f"Research: the tree view could not be followed past stop {stop}")
            scan.at = -1
            break
        shift += moved
        scan.shifts.append(shift)
        scan.profiles.append(profile)
        stops.append(here)
        scan.at = stop
    scan.boxes = merge(stops, scan.shifts)
    return scan


def _goto(g: Game, scan: Scan, k: int) -> float | None:
    """Show the scan's stop k (from the tree's start, the scan's own stops); how far the view
    is further toward the end than the scan saw it there (logical px), None unmeasured."""
    if scan.at != k:
        if scan.at < 0 or scan.at > k:
            known = scan.at >= 0
            hint = (
                math.ceil(scan.shifts[scan.at] / atlas.RS_PX_PER_NOTCH) + 2
                if known
                else atlas.RS_REWIND_NOTCHES
            )
            rewind(g, hint)
            scan.at = 0
        while scan.at < k:
            _wheel(g, -atlas.RS_SCAN_NOTCHES)
            scan.at += 1
    return _scrolled(scan.profiles[k], tree_profile(g))


def to_start(g: Game, scan: Scan) -> None:
    """Leave the tree at its start (the tree reopens where it was left)."""
    if scan.at == 0:
        return
    if scan.at > 0:
        rewind(g, math.ceil(scan.shifts[scan.at] / atlas.RS_PX_PER_NOTCH) + 2)
    else:
        rewind(g, atlas.RS_REWIND_NOTCHES)
    scan.at = 0


def find_again(g: Game, scan: Scan, box: Box, k: int, error: float | None) -> blobs.Blob | None:
    """The blob of `box` in the view of stop k: an available box of its row where the scan
    saw it (FIND_PX) with its icon, an icon a sparkle hides, or any icon when the scan could
    not read it; else one with its icon anywhere in the view."""
    left, panel = _view_edges(g)
    expected = box.x - scan.shifts[k] - (error or 0.0)
    here = [
        b
        for b in research_icons.find_boxes(g, _area(panel))
        if not _cut(b, left, panel) and row_of(b.y1) == box.row
    ]
    for b in sorted(here, key=lambda b: abs(b.x1 - expected)):
        near = abs(b.x1 - expected) <= FIND_PX
        if not near and box.name is None:
            break  # a box the scan could not read is only known by its place
        m = research_icons.identify(g, b)
        if m.state != "available":
            continue
        if m.name == box.name or (near and (m.name is None or box.name is None)):
            return b
    return None


def try_box(g: Game, scan: Scan, box: Box, busy: int) -> str:
    """Tap `box` and press its popup's Research button: "started", "locked" (the popup
    offers no Research button), "failed" (pressed, no panel filled) or "missing" (the box
    was not found again)."""
    ahead = [s for s in box.stops if s >= scan.at] if scan.at >= 0 else []
    k = min(ahead) if ahead else min(box.stops)  # no wheel, or the fewest
    error = _goto(g, scan, k)
    g.move_to(atlas.RS_PARK)  # off the boxes: a hovered one is drawn lighter
    blob = find_again(g, scan, box, k, error)
    if blob is None:
        g.status(f"Research: {box.label} was lost from view, skipped")
        return "missing"
    g.tap(Point(blob.cx, blob.cy, atlas.ANCHOR_CENTER), 800)
    g.wait_still()
    result = "locked"
    if g.found(atlas.RS_POPUP_RESEARCH):
        g.tap(atlas.RS_POPUP_RESEARCH_BUTTON, 1000)
        g.wait_still()
        if _started(g, busy):
            box.state = "running"
            return "started"
        g.status("Research: the Research button did not start a research")
        result = "failed"
    if g.found(atlas.RS_POPUP_CLOSE_X):
        g.tap(atlas.RS_POPUP_CLOSE, 500)
        g.wait_still()
    g.move_to(atlas.RS_PARK)  # the popup's X lies over the tree's top row
    g.sleep(BOUNCE_MS)
    return result


# --- layouts and the choice -----------------------------------------------------------------
ROWS = {1: (2,), 2: (1, 3), 3: (0, 2, 4)}  # row levels of a column of 1, 2 or 3 boxes
_ROMAN = ((10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"))


def roman(n: int) -> str:
    out = ""
    for value, digits in _ROMAN:
        while n >= value:
            out += digits
            n -= value
    return out


@dataclass(frozen=True)
class Layout:
    """One tree content: the trees (research_data keys) that have it, its columns' names."""

    trees: tuple[str, ...]
    columns: tuple[tuple[str, ...], ...]

    def place(self, name: str) -> tuple[int, int] | None:
        """(column, row) of a research, None when the tree has none of that name."""
        for c, col in enumerate(self.columns, start=1):
            if name in col:
                return c, ROWS[len(col)][col.index(name)]
        return None

    def has(self, col: int, row: int) -> bool:
        return 1 <= col <= len(self.columns) and row in ROWS.get(len(self.columns[col - 1]), ())

    @property
    def label(self) -> str:
        numbers = [roman(int(t)) for t in self.trees if t.isdigit()]
        return "/".join(numbers) + ("/..." if len(numbers) < len(self.trees) else "")


@lru_cache(maxsize=1)
def layouts() -> tuple[Layout, ...]:
    groups: dict[tuple[tuple[str, ...], ...], list[str]] = {}
    for key in research_data.load()["firestone"]:
        cols = tuple(tuple(n for n, _ in col) for col in research_data.firestone_columns(key))
        groups.setdefault(cols, []).append(key)
    return tuple(Layout(tuple(keys), cols) for cols, keys in groups.items())


def matching_layouts(boxes: list[Box]) -> list[Layout]:
    """The layouts with a box at every place one was seen, and every identified research
    at its place."""
    return [
        lay
        for lay in layouts()
        if all(
            lay.has(b.col, b.row) and (b.name is None or lay.place(b.name) == (b.col, b.row))
            for b in boxes
        )
    ]


def tree_label(cands: list[Layout]) -> str:
    if not cands:
        return "tree layout unknown"
    if len(cands) > 3:
        return f"{len(cands)} possible tree layouts"
    return "tree like " + " or ".join(c.label for c in cands)


def place_in(cands: list[Layout], name: str) -> tuple[str, int | None, tuple[int, int] | None]:
    """What the layouts agree on for a research: (kind, column, place). kind "absent": in
    none of them; "column": in all of them, column = the left-most of its columns, place =
    its (column, row) when they all agree on it; "unclear": in some only, or no layout."""
    if not cands:
        return "unclear", None, None
    places = [c.place(name) for c in cands]
    if all(p is None for p in places):
        return "absent", None, None
    if any(p is None for p in places):
        return "unclear", None, None
    same = places[0] if all(p == places[0] for p in places) else None
    return "column", min(p[0] for p in places), same


def summary(boxes: list[Box], cands: list[Layout], complete: bool = True) -> str:
    counts = [
        f"{n} {state}"
        for state in ("available", "running", "maxed")
        if (n := sum(b.state == state for b in boxes))
    ]
    unknown = sum(b.name is None for b in boxes)
    if unknown:
        counts.append(f"{unknown} unidentified")
    line = f"Research: {tree_label(cands)}, {len(boxes)} boxes"
    if counts:
        line += f" ({', '.join(counts)})"
    return line if complete else line + ", the end of the tree was out of reach"


@dataclass
class Choice:
    box: Box | None  # the research started
    line: str  # the status line of the decision ("" when nothing could be started)


class Chooser:
    """The choice of a research for a free slot, over what the scan saw (pure: a tap on a
    box is `attempt`, a status line said once a game day `say_once`)."""

    def __init__(
        self,
        boxes: list[Box],
        cands: list[Layout],
        priorities: list[tuple[int, str]],
        any_other: bool,
        attempt: Callable[[Box], str],
        say_once: Callable[[str, str], None],
    ) -> None:
        self.boxes = boxes
        self.cands = cands
        self.priorities = priorities  # (rank 1..5, research name)
        self.any_other = any_other
        self.attempt = attempt
        self.say_once = say_once
        self.by_name = {b.name.lower(): b for b in boxes if b.name}
        self.at_place = {(b.col, b.row): b for b in boxes if b.name is None}
        self.results: dict[tuple[int, int], str] = {}
        self.passed: list[tuple[str, str]] = []  # (priority, why it was passed over)
        self.tree = tree_label(cands)

    def _try(self, box: Box) -> str:
        key = (box.col, box.row)
        if key not in self.results:  # a box is tapped once per decision
            self.results[key] = self.attempt(box)
        return self.results[key]

    def _rank(self, name: str | None) -> int:
        for i, (_, p) in enumerate(self.priorities):
            if name and p.lower() == name.lower():
                return i
        return len(self.priorities)

    def unlock(self, col: int) -> Box | None:
        """Start an available box of the nearest seen column before `col` (a priority first,
        else the top one); the column before when every one of them is locked too."""
        for c in range(col - 1, 0, -1):
            here = [b for b in self.boxes if b.col == c]
            if not here:
                continue  # a locked column
            available = sorted(
                (b for b in here if b.state == "available"),
                key=lambda b: (self._rank(b.name), b.row),
            )
            if not available:
                return None  # maxed or running: nothing to start there
            results = []
            for b in available:
                results.append(self._try(b))
                if results[-1] == "started":
                    return b
            if any(r != "locked" for r in results):
                return None
        return None

    def priority(self, rank: int, name: str) -> Choice | None:
        box = self.by_name.get(name.lower())
        kind, col, place = place_in(self.cands, name)
        if box is None and place is not None:
            box = self.at_place.get(place)  # an unidentified box where every layout has it
        if box is not None and box.state != "available":
            self.passed.append((name, box.state))
            return None
        if box is not None:
            result = self._try(box)
            if result == "started":
                return Choice(box, f"Research: {name} started (priority {rank})")
            if result != "locked":
                self.passed.append((name, "unconfirmed" if result == "failed" else "lost"))
                return None
            col = box.col  # its popup offers no Research button: locked
        else:
            if kind == "absent":
                self.say_once(
                    f"absent:{name}:{self.tree}",
                    f"Research: {name} is absent from this tree ({self.tree}), "
                    f"priority {rank} skipped",
                )
                self.passed.append((name, "absent from this tree"))
                return None
            if kind == "unclear":
                self.say_once(
                    f"unclear:{name}:{self.tree}",
                    f"Research: {name} is unseen and its place differs between the possible "
                    f"trees ({self.tree}), priority {rank} skipped",
                )
                self.passed.append((name, "unseen"))
                return None
            if len({c.place(name)[0] for c in self.cands}) == 1 and any(
                b.col == col for b in self.boxes
            ):
                # its column shows (a column unlocks as a whole), its box did not: nothing
                # to unlock, and nothing to tap
                self.passed.append((name, "unseen"))
                return None
        started = self.unlock(col)
        if started is not None:
            return Choice(
                started, f"Research: {started.label} started to unlock {name} (priority {rank})"
            )
        self.passed.append((name, "locked"))
        return None

    def reason(self) -> str:
        if not self.priorities:
            return "the priority list is empty"
        whys = {why for _, why in self.passed}
        if whys and whys <= {"maxed", "running"}:
            return "the priorities are maxed or running"
        return "priorities: " + ", ".join(f"{n} {why}" for n, why in self.passed)

    def choose(self) -> Choice:
        for rank, name in self.priorities:
            choice = self.priority(rank, name)
            if choice is not None:
                return choice
        if not self.any_other:
            return Choice(
                None,
                f"Research: slot left free ({self.reason()}; Research "
                "something else is off), next search in 15 min",
            )
        kind = "other research" if self.priorities else "any research"
        for b in sorted(
            (b for b in self.boxes if b.state == "available"), key=lambda b: (-b.col, b.row)
        ):
            if self._try(b) == "started":
                return Choice(b, f"Research: {b.label} started ({kind}, {self.reason()})")
        return Choice(None, "")


def priorities(g: Game) -> list[tuple[int, str]]:
    """The user's priorities (rank, in-game name), empty ones left out, names matched
    whatever their case; an unknown name is said once a game day."""
    names = {n.lower(): n for n in research_data.firestone_names()}
    out: list[tuple[int, str]] = []
    for rank, key in enumerate(PRIORITY_KEYS, start=1):
        raw = str(g.settings.get(key) or "").strip()
        if not raw:
            continue
        name = names.get(raw.lower())
        if name is None:
            _say_once(g, f"name:{raw}", f"Research: priority {rank} ({raw}) is an unknown name")
        elif all(name != n for _, n in out):
            out.append((rank, name))
    return out


def _say_once(g: Game, key: str, text: str) -> None:
    """A status line said once per game day (the daily reset found by the shop)."""
    k = f"research_said:{key}:{g.settings.get('LastTokenReset')}"
    if not g.vars.get(k):
        g.vars[k] = 1
        g.status(text)


def start_research(g: Game, busy: int) -> bool:
    """Start a research while `busy` panels are in use; True when one more is busy
    afterwards. Leaves the tree at its start."""
    scan = scan_tree(g)
    cands = matching_layouts(scan.boxes)
    g.status(summary(scan.boxes, cands, scan.complete))
    chooser = Chooser(
        scan.boxes,
        cands,
        priorities(g),
        g.settings.flag("ResearchAnyOther"),
        lambda box: try_box(g, scan, box, busy),
        lambda key, text: _say_once(g, key, text),
    )
    choice = chooser.choose()
    if choice.box is not None:
        g.status(choice.line)
        to_start(g, scan)
        return True
    to_start(g, scan)
    if choice.line:  # left free on purpose
        g.status(choice.line)
    else:
        g.status("Research: a slot is free but no research could start, next search in 15 min")
        g.save_diagnostic("research-no-node.png")
    g.vars[NO_NODE_UNTIL] = int(time.monotonic()) + NO_NODE_PAUSE_S
    return False


def go_research(g: Game) -> None:
    g.focus()
    g.status("Research: opening the library")
    g.require_screen(atlas.TOWN_LIBRARY, atlas.DIALOG_CLOSE_X, via_town=True)
    g.tap(atlas.RS_FIRESTONE_TREE, 1000)
    g.wait_still()
    claiming = True
    for _ in range(MAX_ACTIONS):
        states = panels(g)
        kinds = [kind for kind, _ in states]
        if "done" in kinds and claiming:
            # both finished between two visits: each claim moves the other panel left, so
            # the panels are read again before every action
            i = max(j for j, kind in enumerate(kinds) if kind == "done")
            g.status(f"Research: slot {i + 1} finished, claiming it")
            g.tap(states[i][1], 1500)
            g.wait_still()
            if not _claimed(g, kinds.count("done")):
                g.status("Research: the claim did not show, no more claims this visit")
                g.save_diagnostic("research-claim.png")
                claiming = False
            continue
        if "empty" not in kinds:
            break
        if time.monotonic() < g.vars.get(NO_NODE_UNTIL, 0):
            # nothing could be started a moment ago: the whole tree is not scrolled again
            # at every cycle (firestones take a while to come)
            break
        g.status("Research: a slot is free, looking for a research to start")
        if not start_research(g, busy_count(states)):
            break
    for i, (kind, _) in enumerate(panels(g)):
        g.status(f"Research: slot {i + 1} {LABELS[kind]}")
    big_close(g)


research = go_research  # entry point for tools/run_feature.py
