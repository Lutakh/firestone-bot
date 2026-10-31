"""Port of Functions/subFunctions/MapStart.ahk: start world-map missions while troops are
idle, each one started when its popup shows a free Start, until no idle troop is left.
Missions already clicked this session are remembered in MapStartState.ini.

The missions are found in one of two ways, chosen at each visit by the scale the map is drawn
at (owner, 2026-10-31: "fix detection, coordinates as a fallback"):
- by the duration label under every mission icon (features/map_detect.py,
  map_start_detected), the map dragged beyond its north and south edges while troops stay
  idle: the missions come at random from a pool that no fixed list covers (owner,
  2026-09-06);
- on a map drawn under DETECT_MIN_SCALE the labels are too small to be read reliably, so
  MapStart.ahk's fixed list of mission points (atlas.MAP_MISSION_GROUPS) is clicked in the
  default category order (map_start_coordinates): the "coordinates mode", a setting and the
  default up to 0.3.36 (its point placement was checked on one icon in a window resized to
  1280x720, MEASUREMENTS 4.6; it was never run end to end at a small size). No setting
  chooses between them since 2026-10-31 (MapMode, Priority1..5).

The mission popup is read by its look (vision/mission_popup.py, 2026-10-31): the fixed Start
probe and click (MS_START_BUTTON, MS_START) followed the bottom of the client while the popup
is held at its top, and fell under the button below a client aspect of about 1.6 (16:10
fullscreen, 4:3, 5:4, a MacBook): "goes to the next mission, which it also doesn't start" (a
player, 2026-10-30). Nothing is clicked on the map while a popup is open.

`TimeDiff` (hours since SessionStart) is computed in AHK but never used; not reproduced.
"""

from __future__ import annotations

import logging

import numpy as np

from firestone_bot.features import map_align, map_detect
from firestone_bot.features.map_close import (
    UNREAD,
    Watch,
    close_unread,
    diagnostic_once,
    look,
    map_clear,
    map_close,
    read_after,
    wait_gone,
)
from firestone_bot.game import BotStopped, Game
from firestone_bot.state import MapState, ahk_now
from firestone_bot.vision import atlas
from firestone_bot.vision.mission_popup import NONE, START, UNKNOWN

log = logging.getLogger("firestone_bot")

# The scale under which the labels are not looked for and the fixed list is clicked instead
# (map_start: the larger of map_align.drawn_scale and the client's height against the
# reference client's). Real captures of the owner's map at small client sizes (2026-10-31,
# the window resized while the game ran, MEASUREMENTS): 10 of the reference's 10 missions at
# 1600x900, 1440x900 and 1920x823, 9 at 1366x768 and 1280x720 (0.714), 8 at 1280x1024, and
# none taken from the empty map at any of them; synthetic (the owner's 27-label capture
# resampled): 22..27 from 0.65 up, 17 at 0.62, 14 at 0.60. 0.7 keeps a margin over that drop;
# no real map was captured under 0.714.
DETECT_MIN_SCALE = 0.7
WAY_KEY = "map_way"  # Game.vars: the way said last ("labels" / "points"), said again per run
MAX_DETECT_ROUNDS = 5  # safety: full searches of the map in one visit
START_TAP_MS = 500  # after the Start press: the screen-change wait (fast timing) or the sleep
# Detection (every click is on a mission's label) and a fixed north-edge point (before the
# drag back): a popup not there 1 s after the click is waited for until LATE_MS after it,
# read every LATE_POLL_MS (a hitch of the game)
LATE_MS = 3000
LATE_POLL_MS = 250
# What a mission click came to (_open_mission)
STARTED, CLOSED, NOTHING, STUCK = "started", "closed", "nothing", "stuck"


def _open_mission(g: Game, before: np.ndarray | None, what: str = "the mission click") -> str:
    """After a mission click (`before`: the centre's look just before it), or before the
    next one (`before`: the look before the last click, for a popup that opened late): what
    is open. A start popup whose Start shows no gem in two reads, beside a Complete
    instantly that carries its gem (green is no proof of free, gem audit 2026-10-22), is
    started: its Start pressed in its middle, and the mission counts once the popup has
    gone. Any other popup is closed (in progress, unknown: never a button of its own but its
    X), and so is something the bot cannot read; one that does not close stops the map
    search."""
    p = read_after(g, before)
    if p.kind == NONE:
        return NOTHING
    if p.kind == UNREAD:
        return CLOSED if close_unread(g, before, what) else STUCK
    if p.kind == START and p.green is not None:
        # one capture a run of a start popup, before any click, whatever the client's shape
        diagnostic_once(g, "mission-start-popup.png")
        if p.green_gem:
            g.status("Mission Start: the Start button shows a gem, not clicked")
            g.save_diagnostic("mission-start-gem.png")
        else:
            g.toast("Mission Start", "Mission found - Starting", 1.5)
            g.focus()
            g.tap_screen(p.green.cx, p.green.cy, START_TAP_MS)
            gone, left = wait_gone(g, before=before)
            if gone:
                return STARTED
            # still there: not started, whatever closes it now (a popup closed from outside
            # was counted as a start)
            if not map_close(
                g,
                left,
                "Mission Start: the popup stays open after Start; map search stopped",
                "mission-start-stuck.png",
                before,
            ):
                return STUCK
            g.status("Mission Start: the popup stayed open after Start; closed")
            return CLOSED
    if p.kind == UNKNOWN and p.green is not None and p.orange is not None and not p.orange_label:
        # a start popup whose Complete instantly shows no price: never seen (a mission under
        # 3 minutes might show it), closed unstarted until a capture shows what it is
        g.status("Mission Start: Complete instantly shows no price; not started")
        diagnostic_once(g, "mission-start-unpriced.png")
    elif p.kind == UNKNOWN:
        diagnostic_once(g, "mission-dialog-unknown.png")  # what other shapes or styles show
    return CLOSED if map_close(g, p, before=before) else STUCK


def _wait_late(g: Game, before: np.ndarray | None, outcome: str, since: float) -> str:
    """A click that showed nothing: its popup waited for until LATE_MS after the click
    (`since`: its Game.now()), read every LATE_POLL_MS (a hitch of the game), before the
    next click or a drag that drops the look before it (review of 34146d0)."""
    end = since + LATE_MS / 1000
    while outcome == NOTHING and g.now() + LATE_POLL_MS / 1000 <= end:
        g.sleep(LATE_POLL_MS)
        outcome = _open_mission(g, before)
    return outcome


def _left_open(g: Game, watch: Watch) -> str:
    """Before a map click: what the last one left open, if anything (see _open_mission)."""
    return _open_mission(g, watch.ref, "something since the last map click")


def _drag(g: Game, dy: int) -> None:
    """Drag the map `dy` logical px down (up when negative) from open sea."""
    x, y = atlas.MAP_DRAG_FROM
    g.drag(x, y, x, y + dy, anchor=atlas.ANCHOR_CENTER)


def _drag_map(g: Game, dy: int) -> None:
    _drag(g, dy)
    g.sleep(800)


# --- the fallback: the fixed list of mission points -------------------------------------------
def _listed_points() -> list[tuple[int, int]]:
    """The fixed mission points in the default category order ("2 Squad", "War", "Medium",
    "Short", "Leftover": the AHK bot's Priority1..5 defaults, no setting since 2026-10-31)."""
    return [p for points in atlas.MAP_MISSION_GROUPS.values() for p in points]


def _click_mission(g: Game, x: int, y: int) -> tuple[np.ndarray | None, str]:
    """Click a mission point; north-edge points are revealed by a temporary drag (see atlas).
    The points were measured on a canvas-scaled map: on a map the game fitted to a 16:9 width
    (map_align.SCALE_KEY, measured on the landmark) they sit that much nearer the centre.
    Returns the centre's look just before the click (after the drag) and NOTHING; or, when a
    popup showed during the drag, (None, what came of it: STARTED, CLOSED or STUCK) and no
    click."""
    f = g.vars.get(map_align.SCALE_KEY, 1.0)
    cx, cy = atlas.REF.x + atlas.REF.w / 2, atlas.REF.y + atlas.REF.h / 2
    lx, ly = round(cx + (x - cx) * f), round(cy + (y - cy) * f)
    if y >= atlas.MAP_NORTH_DRAG_LIMIT:
        before = look(g)
        g.click_at(lx, ly, anchor=atlas.ANCHOR_CENTER)  # Click %x%, %y%
        return before, NOTHING
    dy = atlas.MAP_NORTH_DRAG_DY
    _drag_map(g, dy)
    # a popup the last click opened late, shown during the drag: handled before the look
    # this click is compared with, which would hold it (review of 34146d0)
    pending = _open_mission(g, None, "something since the last map click")
    if pending != NOTHING:
        return None, pending
    before = look(g)
    g.click_at(lx, ly + dy, anchor=atlas.ANCHOR_CENTER)
    return before, NOTHING


def _undrag_if_needed(g: Game, y: int) -> None:
    if y < atlas.MAP_NORTH_DRAG_LIMIT:
        _drag_map(g, -atlas.MAP_NORTH_DRAG_DY)


def map_start_coordinates(g: Game, state: MapState, watch: Watch | None = None) -> bool:
    """The fallback on a map drawn too small for its labels: the fixed mission points
    clicked in the default category order, at the scale the landmark measured, on the map
    the visit's alignment put in place. Two passes: the first skips the points in memory,
    the second clears the memory and redoes everything while troops stay idle. False when a
    mission popup stayed open (the map section stops)."""
    watch = watch or Watch()
    points = _listed_points()
    # Attempt 1 skips what is in memory; attempt 2 clears the memory and redoes everything.
    for attempt in (1, 2):
        for x, y in points:
            if state.was_clicked(x, y):
                continue
            g.focus()
            pending = _left_open(g, watch)  # a start popup that opened late is started
            if (
                pending == NOTHING
                and y < atlas.MAP_NORTH_DRAG_LIMIT
                and watch.ref is not None
                and watch.outcome == NOTHING
                and watch.clicked is not None
            ):
                # the drag before a north-edge point drops the look before the last click: a
                # popup that click opened late is waited for first, until LATE_MS after it
                # (review of 34146d0; about 2 s before each of the 2 north groups of the
                # default order that follow an empty point)
                pending = _wait_late(g, watch.ref, pending, watch.clicked)
            if pending == STUCK:
                return False
            if pending == STARTED and not g.found(atlas.MAP_TROOP_IDLE):
                g.toast("Troop Check", "No idle troops found - ending mission search", 2)
                return True
            # The world map is centred (measured at 1280x720, docs/MEASUREMENTS.md 4.6), so
            # every mission point uses the centre anchor, and the map's scale (_click_mission).
            before, pending = _click_mission(g, x, y)
            if pending != NOTHING:
                # a popup showed during the north drag: handled, the point not clicked (it
                # comes again in the second round)
                _undrag_if_needed(g, y)
                watch.ref, watch.clicked, watch.outcome = None, None, None
                if pending == STUCK:
                    return False
                if pending == STARTED and not g.found(atlas.MAP_TROOP_IDLE):
                    g.toast("Troop Check", "No idle troops found - ending mission search", 2)
                    return True
                continue
            clicked = g.now()
            g.sleep(1000)
            state.mark_clicked(x, y)
            outcome = _open_mission(g, before)
            if y < atlas.MAP_NORTH_DRAG_LIMIT:
                # the drag back drops `before`: about 2 s on each north point that shows nothing
                outcome = _wait_late(g, before, outcome, clicked)
            _undrag_if_needed(g, y)
            # a north point's drag moved the map: its look before is no reference
            if y >= atlas.MAP_NORTH_DRAG_LIMIT:
                watch.ref, watch.clicked, watch.outcome = before, clicked, outcome
            else:
                watch.ref, watch.clicked, watch.outcome = None, None, None
            if outcome == STUCK:
                return False
            if outcome == STARTED:
                g.toast("Troop Check", "Looking for more idle troops", 2)
                if g.found(atlas.MAP_TROOP_IDLE):
                    continue
                g.toast("Troop Check", "No idle troops found - ending mission search", 2)
                return True
            # Check troops after each interaction (even if not started)
            if not g.found(atlas.MAP_TROOP_IDLE):
                g.toast("Troop Check", "No idle troops found - ending mission search", 2)
                return True
        # End of list: troops left after the first attempt means the memory hid something.
        if attempt == 1 and g.found(atlas.MAP_TROOP_IDLE):
            state.reset()
            continue
        break
    return True


# --- detection: the duration labels -------------------------------------------------------
def _detect_and_click(
    g: Game, state: MapState, offset: int, watch: Watch
) -> tuple[bool, int, bool]:
    """One detection pass on the map as currently shown (`offset`: how far it was dragged
    down, 0 = in place). Missions are remembered at their in-place position so a mission
    seen after a drag is not clicked twice. Returns (idle troops remain, missions started,
    a popup stayed open)."""
    # a popup's digits are no map label: its timer was taken for a mission (audit 2026-10-30)
    if not map_clear(g, watch):
        return False, 0, True
    points = map_detect.find_missions(g)
    where = "" if not offset else (" (map moved down)" if offset > 0 else " (map moved up)")
    g.status(f"Map: {len(points)} mission icon(s) detected on the screen{where}")
    if not points:
        g.save_diagnostic("map-no-icon.png")
    started = 0
    for x, y in points:
        if state.was_clicked(x, y - offset):
            continue
        g.focus()
        pending = _left_open(g, watch)  # a start popup that opened late is started
        if pending == STUCK:
            return False, started, True
        if pending == STARTED:
            started += 1
            if not g.found(atlas.MAP_TROOP_IDLE):
                g.toast("Troop Check", "No idle troops found - ending mission search", 2)
                return False, started, False
        before = look(g)
        g.click_at(x, y, anchor=atlas.ANCHOR_CENTER)  # find_missions' points are centred
        clicked = g.now()
        g.sleep(1000)
        state.mark_clicked(x, y - offset)
        # a popup that opens late is waited for before the next click: the next click went
        # to the map while it was coming, and once the pass ended its start popup was closed
        # unstarted by the next search's clear, or, of another style, not seen after the
        # drag that drops the look before the click and clicked through (review of 34146d0)
        outcome = _wait_late(g, before, _open_mission(g, before), clicked)
        watch.ref, watch.clicked, watch.outcome = before, clicked, outcome
        if outcome == STUCK:
            return False, started, True
        if outcome == STARTED:
            started += 1
        g.toast("Troop Check", "Looking for more idle troops", 2)
        if not g.found(atlas.MAP_TROOP_IDLE):
            g.toast("Troop Check", "No idle troops found - ending mission search", 2)
            return False, started, False
    # what the last click left open, before a drag drops the look before it
    pending = _left_open(g, watch)
    if pending == STUCK:
        return False, started, True
    if pending == STARTED:
        started += 1
    return g.found(atlas.MAP_TROOP_IDLE), started, False


def _undo_drag(g: Game, dy: int, error: BaseException) -> None:
    """The drag back of a pass cut short by `error` (the mouse guard's pause, the game not in
    front, an error): the game is brought to the front first (on macOS and Linux nothing else
    checks it, and the drag would go to the window over it), then the map dragged back. After
    a Stop nothing is sent (the user stopped the bot: not one more input, as enlighten), and
    when the drag cannot be sent either (g.drag's foreground check may wait and raise the Stop
    or the pause again), the map stays dragged: the next alignment drags it up to look for its
    landmark (map_align._look_higher)."""
    stop = getattr(g, "stop_event", None)
    if isinstance(error, BotStopped) or (stop is not None and stop.is_set()):
        # also a Stop set while the pause or the game leaving the front unwinds
        g.status("Map: stopped with the map dragged; the next alignment looks for it")
        return
    try:
        g.focus()
        _drag(g, dy)
    except Exception:  # whatever cut the pass short goes on up, not this
        log.debug("the drag back of a cut pass failed", exc_info=True)
        g.status(
            "Map: the map could not be dragged back after a search beyond its edge; the next "
            "alignment looks for it"
        )


def _dragged_pass(g: Game, state: MapState, offset: int, watch: Watch) -> tuple[bool, int, bool]:
    """A detection pass on the map dragged `offset` px (down: its north edge shown; up: its
    south edge), dragged back after it. Cut short (BotStopped from a wait, UserInterrupted
    from the mouse guard's pause, GameNotInFront, an error), the pass still drags the map back
    on its way out: left 220 px down, the map hid its landmark under the bottom HUD and every
    later visit searched a moved map (review of 8558a26, F2). A drag back that may have been
    lost (not sent, or made under a popup that stays) lets the next alignment drag the map up
    to look for its landmark (map_align.RECOVERY_OFF dropped)."""
    _drag(g, offset)
    watch.ref = None  # the map moved: its look before is no reference
    try:
        g.sleep(800)
        result = _detect_and_click(g, state, offset, watch)
        _drag(g, -offset)
    except Exception as error:
        # a popup the last click opened may swallow the drag back as well
        g.vars.pop(map_align.RECOVERY_OFF, None)
        _undo_drag(g, -offset, error)
        raise
    watch.ref = None
    if result[2]:
        # dragged back under the popup that stays (as the 80 px north drag of the fixed
        # points was): the drag may be swallowed
        g.vars.pop(map_align.RECOVERY_OFF, None)
    g.sleep(800)
    return result


def map_start_detected(g: Game, state: MapState, watch: Watch | None = None) -> bool:
    """The missions are the duration labels seen on the map (map_detect).

    Labels near the top or bottom edge fall outside the capture, so while idle troops
    remain the map is dragged down (north revealed) then up (south revealed) and searched
    again; the map is put back in place before leaving (owner request 2026-09-06). False
    when a mission popup stayed open (the map section stops)."""
    scroll = atlas.MAP_DETECT_SCROLL
    watch = watch or Watch()
    moved = stuck = False
    # The map is searched again as long as missions keep being started: an icon in the middle
    # of the map can be hidden by its neighbours and only shows once one of them is running
    # (Ixyon and the owner, 2026-09-09: a mission was left for a later cycle). When a full
    # search starts nothing while troops are idle, the map is put back to its reference place
    # (a dragged or zoomed map hides the labels) and searched once more with a fresh memory.
    realigned = False
    for _ in range(MAX_DETECT_ROUNDS):
        more, started = True, 0
        for offset in (0, scroll, -scroll):
            if offset:
                g.status("Map: idle troops left, looking beyond the edge")
                more, n, stuck = _dragged_pass(g, state, offset, watch)
                moved = True
            else:
                more, n, stuck = _detect_and_click(g, state, offset, watch)
            started += n
            if not more:
                break
        if not more or not g.found(atlas.MAP_TROOP_IDLE):
            break
        if started:
            g.status(f"Map: {started} mission(s) started, looking for the ones they hid")
            continue
        state.reset()  # every icon tried: the memory hid something
        if not realigned:
            g.status("Map: idle troops left after a full search, re-aligning and retrying")
            map_align.align_map(g)
            watch.ref = None
            moved = False
            realigned = True
            continue
        g.status("Map: idle troops left but no mission to start was found")
        g.save_diagnostic("map-troops-left.png")
        break
    # Every dragged pass dragged the map back itself, also when an exception cut it short (the
    # visit ends there; the next one starts with an alignment). The final alignment corrects
    # what a drag lost; never measured under a stuck popup (a drag it swallows would turn the
    # alignment off for the run): the next visit's alignment puts the map back, dragging it up
    # to look for its landmark when the drag back under the popup was lost (map_align).
    if moved and not stuck:
        map_align.align_map(g)  # recentre exactly before leaving
        watch.ref = None
    return not stuck


def _say_way(g: Game, labels: bool, height: float, drawn: float) -> None:
    """Say which way the missions are found and why: once a run (the runner drops WAY_KEY at
    each start) and again when it changes (a window resized, a game started at another
    size)."""
    way = "labels" if labels else "points"
    if g.vars.get(WAY_KEY) == way:
        return
    g.vars[WAY_KEY] = way
    if labels:
        g.status(
            "Map: missions are found by their duration labels (window height "
            f"{height:.3f} of the reference, map drawn at {drawn:.3f})"
        )
    else:
        g.status(
            f"Map: the window is too small for the labels (height {height:.3f} of the "
            f"reference, under {DETECT_MIN_SCALE}); missions are clicked from the fixed list"
        )


def map_start(g: Game, watch: Watch | None = None) -> bool:
    """Start missions while troops are idle (`watch`: the map's look from map_redeem's last
    tap, when the map has not moved since): by their labels, or from the fixed list on a map
    drawn under DETECT_MIN_SCALE, by the client's height against the reference client's
    (map_align.drawn_scale never exceeds it): a window made taller than 16:9 after the game
    started draws the map at its height (1440x900, 1600x1000, 1280x1024 on 2026-10-31: 0.89..1.01
    where drawn_scale reads 0.71..0.89, and the landmark is not found there), so its labels
    stay readable (a size factor too small is tolerated, map_detect) and the fixed points,
    placed at the canvas scale, would miss (review of c515703). In practice the fixed list is
    clicked on a client under 706 px tall (a maximised window on a screen 768 px tall: about
    697). False when a mission popup stayed open: the map section stops (nothing is clicked
    under it)."""
    state = MapState.load(g.map_state_path)
    if not state.session_start or state.session_start == "0":
        state.session_start = ahk_now()
        state.save()
    watch = watch or Watch()
    # the client's height decides: drawn_scale never exceeds it (the canvas scale is
    # min(w / 1793.8, h / 1009), the map scale 1.0 or less), and a window made taller than
    # 16:9 after the game started draws the map at its height
    height = round(g._viewport().client.h / atlas.REF.h, 3)
    labels = height >= DETECT_MIN_SCALE
    _say_way(g, labels, height, map_align.drawn_scale(g))
    if labels:
        return map_start_detected(g, state, watch)
    return map_start_coordinates(g, state, watch)
