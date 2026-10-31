"""Port of Functions/subFunctions/MapClose.ahk: close a world-map mission popup; and the
popup reads that map_start and map_redeem share.

MapClose.ahk tapped a fixed point beside the popup (MAP_POPUP_CLOSE, through the thirds
rule): nothing checked that the popup went, and it was tapped whether a popup showed or not.
The popup is now read by its look (vision/mission_popup.py), closed by its own X or, without
one (the Mission Rewards dialog has none), by a tap beside the panel found, and the next
reads must show it gone. A popup that stays stops the map section: a map point clicked
through it could land on its paid buttons or its Cancel (several coordinates-mode points do
at 1920x1009, audit 2026-10-30).

The reader only knows the looks it was measured on. A popup it cannot see (another
interface style, a game update, a colour shift past its margins) must not be clicked
through either: the old blind close tap guarded against that (2026-10-22). So the centre of
the client, where every mission popup draws, is also compared before and after each click
on the map (look / changed): a change with no popup read is something open that the bot
does not know, closed beside where any popup draws and checked gone the same way, never
clicked through (review of 2026-10-31).
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from firestone_bot.game import Game
from firestone_bot.vision import gems, mission_popup
from firestone_bot.vision.mission_popup import NONE, UNKNOWN, Popup
from firestone_bot.vision.viewport import CANVAS_W, canvas_scale

READ_PAIRS = 4  # reads after the first before a popup still moving is taken as unknown
GONE_POLLS = 12  # reads GONE_POLL_MS apart: about 3 s for a popup to go
GONE_POLL_MS = 250
CLOSE_TRIES = 2
CLOSE_TAP_MS = 500  # after a close tap: the screen-change wait (fast timing) or the sleep
STUCK_LINE = "Map: a mission popup stays open after two close taps; map section stopped"
UNREAD = "unread"  # read_after: the centre changed and no mission popup is read
# The centre's look: block means of the client's centre column band, LOOK_HALF_W of the
# canvas width each side of its middle (a popup is NOMINAL_W = 0.61 of it wide, centred,
# whatever the client's shape), LOOK_GRID blocks (rows over the client's height, columns
# over the band). The band changed when LOOK_CHANGED of its blocks moved by more than
# LOOK_LEVELS: a mission popup changes most of the rows it covers (a third of the band at
# least), the idle-squads banner or a timer a block or two.
LOOK_HALF_W = 0.2
LOOK_TOP = 0.08  # the top strip left out: a Linux overlay may sit there (gui/overlay.py)
LOOK_GRID = (24, 12)
LOOK_LEVELS = 40
LOOK_CHANGED = 0.12
UNREAD_DIAGNOSTIC = "mission-popup-unread.png"


class Watch:
    """The centre's look of the map with nothing open on it, kept from one map click to the
    next: a screen that differs from it before the next click shows something left open (a
    popup that opened late, after the reads of its own click). None after the map moved (a
    drag, an alignment): nothing to compare with."""

    def __init__(self) -> None:
        self.ref: np.ndarray | None = None
        # the map click `ref` was taken for (Game.now) and what it came to: a north-edge
        # point's drag waits for that click's late popup only when it showed nothing, and
        # only until LATE_MS after it (unset when the ref is the list tap's)
        self.clicked: float | None = None
        self.outcome: str | None = None


def look_of(img: np.ndarray) -> np.ndarray | None:
    """The centre's look of a capture of the client (see LOOK_*)."""
    h, w = img.shape[:2]
    half = LOOK_HALF_W * CANVAS_W * canvas_scale(w, h)
    x1, x2 = max(0, round(w / 2 - half)), min(w, round(w / 2 + half))
    y0 = round(LOOK_TOP * h)
    rows, cols = LOOK_GRID
    bh, bw = (h - y0) // rows, (x2 - x1) // cols
    if bh == 0 or bw == 0:
        return None
    band = img[y0 : y0 + bh * rows, x1 : x1 + bw * cols, :3]
    return band.reshape(rows, bh, cols, bw, 3).mean(axis=(1, 3), dtype=np.float32)


def look(g: Game) -> np.ndarray | None:
    """The centre's look now."""
    img, _client = g.client_image()
    return look_of(img)


def changed(before: np.ndarray | None, now: np.ndarray | None) -> bool:
    """The centre's look moved from `before` to `now` (False when either is missing)."""
    if before is None or now is None or before.shape != now.shape:
        return False
    diff = np.abs(now - before).mean(axis=2)
    return bool((diff > LOOK_LEVELS).mean() >= LOOK_CHANGED)


def read_popup(g: Game) -> Popup:
    """The mission popup on screen, read until two reads CONFIRM_MS apart agree: a popup
    scaling in reads smaller and its boxes move. A gem seen in any of the reads counts, as
    in gems.shows_gem (a gem drawn late is never taken for free). Reads that never agree
    and saw a panel are an unknown popup, whatever the last one read."""
    reads = [mission_popup.read_game(g)]
    for _ in range(READ_PAIRS):
        g.sleep(gems.CONFIRM_MS)
        reads.append(mission_popup.read_game(g))
        if reads[-1].same_as(reads[-2]):
            return replace(
                reads[-1],
                green_gem=any(r.green_gem for r in reads),
                orange_gem=any(r.orange_gem for r in reads),
                orange_label=any(r.orange_label for r in reads),
                okay_row_gem=any(r.okay_row_gem for r in reads),
                gem=any(r.gem for r in reads),
            )
    seen = [r for r in reads if r.kind != NONE]
    if not seen:
        return reads[-1]
    return replace(
        seen[-1],
        kind=UNKNOWN,
        green_gem=any(r.green_gem for r in reads),
        orange_gem=any(r.orange_gem for r in reads),
        orange_label=any(r.orange_label for r in reads),
        okay_row_gem=any(r.okay_row_gem for r in reads),
        gem=any(r.gem for r in reads),
    )


def read_after(g: Game, before: np.ndarray | None) -> Popup:
    """What a click on the map opened (`before`: the centre's look just before it): the
    popup, read until two reads agree; kind NONE when nothing shows and the centre looks as
    before; kind UNREAD when the centre changed but no mission popup is read (close it with
    close_unread, never click through it)."""
    img, client = g.client_image()
    p = mission_popup.read(img, (client.x, client.y))
    if p.kind == NONE:
        if before is None or not changed(before, look_of(img)):
            return p
        g.wait_still()  # something is drawing: a popup scaling in late, or a look not known
    p = read_popup(g)
    if p.kind == NONE and before is not None and changed(before, look(g)):
        return replace(p, kind=UNREAD)
    return p


def wait_gone(
    g: Game, polls: int = GONE_POLLS, before: np.ndarray | None = None
) -> tuple[bool, Popup]:
    """Reads until no panel shows twice in a row and, with `before` (the centre's look
    before the click that opened it), the centre looks as it did; at most `polls` reads
    GONE_POLL_MS apart. (gone, the last read)."""
    p = mission_popup.read_game(g)
    for _ in range(polls):
        if p.kind == NONE:
            g.sleep(gems.CONFIRM_MS)
            p = mission_popup.read_game(g)
            if p.kind == NONE and (before is None or not changed(before, look(g))):
                return True, p
        g.sleep(GONE_POLL_MS)
        p = mission_popup.read_game(g)
    return False, p


def beside(g: Game) -> tuple[int, int]:
    """A screen point right of where any mission popup draws, at the client's middle height:
    a tap there closes a popup the reader cannot see (the tap beside the panel that closes
    the popups at 1920x1009), and lands on the map, left of its right-hand buttons."""
    c = g._viewport().client
    cw = CANVAS_W * canvas_scale(c.w, c.h)
    dx = (0.5 + mission_popup.OUTSIDE) * mission_popup.NOMINAL_W * cw
    return round(c.x + c.w / 2 + dx), round(c.y + c.h / 2)


def _close_point(g: Game, p: Popup, attempt: int) -> tuple[int, int] | None:
    """Where to tap to close `p`: its X first, then beside its panel (inside the client), or
    beside where any popup draws when none is read."""
    if p.close is not None and not attempt:
        return p.close.cx, p.close.cy
    if p.panel is not None:
        return p.outside()
    return beside(g)


def map_close(
    g: Game,
    p: Popup | None = None,
    stuck_line: str = STUCK_LINE,
    stuck_diagnostic: str = "mission-popup-stuck.png",
    before: np.ndarray | None = None,
) -> bool:
    """Close the mission popup that shows (`p`: as just read; `before`: the centre's look
    before the click that opened it, which must come back): its X, or a tap beside the
    panel (without an X, and at the second try: a tap outside closed the popups at
    1920x1009, the owner's logs 2026-10-30); True once the reads show no panel (or none
    showed). One that stays after CLOSE_TRIES taps, or with nowhere safe to tap, is said and
    captured, and False: the caller clicks nothing more."""
    if p is None:
        p = mission_popup.read_game(g)
    if p.kind == NONE and (before is None or not changed(before, look(g))):
        return True
    for attempt in range(CLOSE_TRIES):
        point = _close_point(g, p, attempt)
        if point is None:
            break  # no X, and beside the panel is off the client: nothing safe to tap
        g.focus()
        g.tap_screen(*point, CLOSE_TAP_MS)
        gone, p = wait_gone(g, before=before)
        if gone:
            return True
    g.status(stuck_line)
    g.save_diagnostic(stuck_diagnostic)
    return False


def close_unread(g: Game, before: np.ndarray | None, what: str) -> bool:
    """`what` changed the centre of the screen but no mission popup is read (`before`: its
    look before): something open that the bot does not know, captured once a run and closed
    beside where any popup draws, until the centre looks as before. False when it stays."""
    g.status(f"Map: {what} opened something the bot cannot read; closing it")
    diagnostic_once(g, UNREAD_DIAGNOSTIC)
    return map_close(
        g,
        replace(Popup(), kind=UNREAD),
        "Map: what opened stays open after two close taps; map section stopped",
        before=before,
    )


def map_clear(g: Game, watch: Watch | None = None) -> bool:
    """Before a map click or a search of the map: no mission popup left open, or it is closed
    first; with a `watch`, a centre that changed since the last map click with no popup read
    is closed as something unknown. False when it stays (the map section stops)."""
    ref = watch.ref if watch is not None else None
    p = read_after(g, ref)
    if p.kind == NONE:
        return True
    if p.kind == UNREAD:
        return close_unread(g, ref, "something since the last map click")
    g.status(f"Map: a mission popup ({p.kind}) is open before a map click, closing it")
    return map_close(g, p, before=ref)


def diagnostic_once(g: Game, name: str) -> None:
    """One capture of a kind a run: the popups of today's interface, at the players' shapes."""
    key = f"map_diag:{name}"
    if not g.vars.get(key):
        g.vars[key] = 1
        g.save_diagnostic(name)
