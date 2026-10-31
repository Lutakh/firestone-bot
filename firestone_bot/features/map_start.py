"""Port of Functions/subFunctions/MapStart.ahk: click every mission point of the world map in
priority order, start the mission when its green button shows, stop when no idle troop is
left. Points already clicked this session are remembered in MapStartState.ini.

The mission popup is read by its look (vision/mission_popup.py, 2026-10-31): the fixed Start
probe and click (MS_START_BUTTON, MS_START) followed the bottom of the client while the popup
is held at its top, and fell under the button below a client aspect of about 1.6 (16:10
fullscreen, 4:3, 5:4, a MacBook): "goes to the next mission, which it also doesn't start" (a
player, 2026-10-30). No map point is clicked while a popup is open.

`TimeDiff` (hours since SessionStart) is computed in AHK but never used; not reproduced.
"""

from __future__ import annotations

import numpy as np

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
from firestone_bot.game import Game
from firestone_bot.state import MapState, ahk_now
from firestone_bot.vision import atlas
from firestone_bot.vision.mission_popup import NONE, START, UNKNOWN

MAX_DETECT_ROUNDS = 5  # safety: full searches of the map in one visit
START_TAP_MS = 500  # after the Start press: the screen-change wait (fast timing) or the sleep
# Detection mode (every click is on a mission's label) and a north-edge point (before the
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


def _wait_late(g: Game, before: np.ndarray | None, outcome: str, since: float | None = None) -> str:
    """A click that showed nothing: its popup waited for until LATE_MS after the click
    (`since`: its Game.now(); else 1 s ago), read every LATE_POLL_MS (a hitch of the game),
    before the next click or a drag that drops the look before it (review of 34146d0)."""
    end = (g.now() - 1.0 if since is None else since) + LATE_MS / 1000
    while outcome == NOTHING and g.now() + LATE_POLL_MS / 1000 <= end:
        g.sleep(LATE_POLL_MS)
        outcome = _open_mission(g, before)
    return outcome


def _left_open(g: Game, watch: Watch) -> str:
    """Before a map click: what the last one left open, if anything (see _open_mission)."""
    return _open_mission(g, watch.ref, "something since the last map click")


def _priority_points(g: Game) -> list[tuple[int, int]]:
    points: list[tuple[int, int]] = []
    for key in ("Priority1", "Priority2", "Priority3", "Priority4", "Priority5"):
        points.extend(atlas.MAP_MISSION_GROUPS.get(g.settings.get(key), ()))
    return points


def _drag_map(g: Game, dy: int) -> None:
    x, y = atlas.MAP_NORTH_DRAG_FROM
    g.drag(x, y, x, y + dy, anchor=atlas.ANCHOR_CENTER)
    g.sleep(800)


def _click_mission(g: Game, x: int, y: int) -> tuple[np.ndarray | None, str]:
    """Click a mission point; north-edge points are revealed by a temporary drag (see atlas).
    The points were measured on a canvas-scaled map: on a map the game fitted to a 16:9 width
    (map_align.SCALE_KEY, measured on the landmark) they sit that much nearer the centre.
    Returns the centre's look just before the click (after the drag) and NOTHING; or, when a
    popup showed during the drag, (None, what came of it: STARTED, CLOSED or STUCK) and no
    click."""
    from firestone_bot.features import map_align

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


def _detect_and_click(
    g: Game, state: MapState, offset: int, watch: Watch
) -> tuple[bool, int, bool]:
    """One detection pass on the map as currently shown (`offset`: how far it was dragged
    down, 0 = in place). Missions are remembered at their in-place position so a mission
    seen after a drag is not clicked twice. Returns (idle troops remain, missions started,
    a popup stayed open)."""
    from firestone_bot.features import map_detect

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


def map_start_detected(g: Game, state: MapState, watch: Watch | None = None) -> bool:
    """Detection mode: the missions are the duration labels seen on the map (map_detect).

    Labels near the top or bottom edge fall outside the capture, so while idle troops
    remain the map is dragged down (north revealed) then up (south revealed) and searched
    again; the map is put back in place before leaving (owner request 2026-09-06). False
    when a mission popup stayed open (the map section stops)."""
    from firestone_bot.features import map_align

    scroll = atlas.MAP_DETECT_SCROLL
    watch = watch or Watch()
    moved = stuck = False
    try:
        # The map is searched again as long as missions keep being started: an icon in the
        # middle of the map can be hidden by its neighbours and only shows once one of them
        # is running (Ixyon and the owner, 2026-09-09: a mission was left for a later cycle).
        # When a full search starts nothing while troops are idle, the map is put back to its
        # reference place (a dragged or zoomed map hides the labels) and searched once more
        # with a fresh memory.
        realigned = False
        for _ in range(MAX_DETECT_ROUNDS):
            more, started = True, 0
            for offset in (0, scroll, -scroll):
                if offset:
                    g.status("Map: idle troops left, looking beyond the edge")
                    _drag_map(g, offset)
                    watch.ref = None  # the map moved: its look before is no reference
                    moved = True
                more, n, stuck = _detect_and_click(g, state, offset, watch)
                started += n
                if offset:
                    _drag_map(g, -offset)
                    watch.ref = None
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
    finally:
        # never measured under a stuck popup: a drag it swallows would turn the alignment
        # off for the run; the next visit's alignment puts the map back
        if moved and not stuck:
            map_align.align_map(g)  # recentre exactly before leaving
            watch.ref = None
    return not stuck


def map_start(g: Game, watch: Watch | None = None) -> bool:
    """Start missions while troops are idle (`watch`: the map's look from map_redeem's last
    tap, when the map has not moved since). False when a mission popup stayed open: the map
    section stops (nothing is clicked under it)."""
    state = MapState.load(g.map_state_path)
    if not state.session_start or state.session_start == "0":
        state.session_start = ahk_now()
        state.save()
    watch = watch or Watch()
    if g.settings.get("MapMode") == "detect":
        return map_start_detected(g, state, watch)
    points = _priority_points(g)
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
                # default priorities that follow an empty point)
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
