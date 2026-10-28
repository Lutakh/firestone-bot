"""Port of Functions/subFunctions/MapStart.ahk: click every mission point of the world map in
priority order, start the mission when its green button shows, stop when no idle troop is
left. Points already clicked this session are remembered in MapStartState.ini.

`TimeDiff` (hours since SessionStart) is computed in AHK but never used; not reproduced.
"""

from __future__ import annotations

from firestone_bot.features.map_close import map_close
from firestone_bot.game import Game
from firestone_bot.state import MapState, ahk_now
from firestone_bot.vision import atlas, gems

MAX_DETECT_ROUNDS = 5  # safety: full searches of the map in one visit
START_CLOSE_MS = 3000  # the start popup closes after Start, or after a close tap


def _start_ready(g: Game) -> bool:
    """The green Start button with no gem in it: green is no proof of free (gem audit,
    2026-10-22); a gem means the mission popup is closed unstarted."""
    if not g.found(atlas.MS_START_BUTTON):
        return False
    if gems.shows_gem(g, atlas.MS_START_RECT):
        g.status("Mission Start: the Start button shows a gem, not clicked")
        g.save_diagnostic("mission-start-gem.png")
        return False
    # the start popup of game 9.1.3a has no 1:1 capture yet: one a run, before the click
    key = "map_diag:mission-start-popup.png"
    if not g.vars.get(key):
        g.vars[key] = 1
        g.save_diagnostic("mission-start-popup.png")
    return True


def _left_open(g: Game) -> bool:
    """After a Start click: True when the start popup is still there after a close tap.
    The next map point would be clicked onto it, maybe on its paid Complete instantly
    (new game version, 2026-10-22), so the map search stops."""
    if g.wait_gone(atlas.MS_START_BUTTON, START_CLOSE_MS):
        return False
    map_close(g)
    if g.wait_gone(atlas.MS_START_BUTTON, START_CLOSE_MS):
        g.status("Mission Start: the popup stayed open after Start; closed")
        return False
    g.status("Mission Start: the popup stays open after Start; map search stopped")
    g.save_diagnostic("mission-start-stuck.png")
    return True


def _priority_points(g: Game) -> list[tuple[int, int]]:
    points: list[tuple[int, int]] = []
    for key in ("Priority1", "Priority2", "Priority3", "Priority4", "Priority5"):
        points.extend(atlas.MAP_MISSION_GROUPS.get(g.settings.get(key), ()))
    return points


def _drag_map(g: Game, dy: int) -> None:
    x, y = atlas.MAP_NORTH_DRAG_FROM
    g.drag(x, y, x, y + dy, anchor=atlas.ANCHOR_CENTER)
    g.sleep(800)


def _click_mission(g: Game, x: int, y: int) -> None:
    """Click a mission point; north-edge points are revealed by a temporary drag (see atlas).
    The points were measured on a canvas-scaled map: on a map the game fitted to a 16:9 width
    (map_align.SCALE_KEY, measured on the landmark) they sit that much nearer the centre."""
    from firestone_bot.features import map_align

    f = g.vars.get(map_align.SCALE_KEY, 1.0)
    cx, cy = atlas.REF.x + atlas.REF.w / 2, atlas.REF.y + atlas.REF.h / 2
    lx, ly = round(cx + (x - cx) * f), round(cy + (y - cy) * f)
    if y >= atlas.MAP_NORTH_DRAG_LIMIT:
        g.click_at(lx, ly, anchor=atlas.ANCHOR_CENTER)  # Click %x%, %y%
        return
    dy = atlas.MAP_NORTH_DRAG_DY
    _drag_map(g, dy)
    g.click_at(lx, ly + dy, anchor=atlas.ANCHOR_CENTER)


def _undrag_if_needed(g: Game, y: int) -> None:
    if y < atlas.MAP_NORTH_DRAG_LIMIT:
        _drag_map(g, -atlas.MAP_NORTH_DRAG_DY)


def _detect_and_click(g: Game, state: MapState, offset: int) -> tuple[bool, int, bool]:
    """One detection pass on the map as currently shown (`offset`: how far it was dragged
    down, 0 = in place). Missions are remembered at their in-place position so a mission
    seen after a drag is not clicked twice. Returns (idle troops remain, missions started,
    a start popup stayed open)."""
    from firestone_bot.features import map_detect

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
        g.click_at(x, y, anchor=atlas.ANCHOR_CENTER)  # find_missions' points are centred
        g.sleep(1000)
        state.mark_clicked(x, y - offset)
        if _start_ready(g):
            g.move_to(atlas.MS_START)
            g.toast("Mission Start", "Mission found - Starting", 1.5)
            g.click()
            g.sleep(500)
            if _left_open(g):
                return False, started, True
            started += 1
        else:
            map_close(g)  # mission in progress or unavailable: close the pop-up
        g.toast("Troop Check", "Looking for more idle troops", 2)
        if not g.found(atlas.MAP_TROOP_IDLE):
            g.toast("Troop Check", "No idle troops found - ending mission search", 2)
            return False, started, False
    return g.found(atlas.MAP_TROOP_IDLE), started, False


def map_start_detected(g: Game, state: MapState) -> None:
    """Detection mode: the missions are the duration labels seen on the map (map_detect).

    Labels near the top or bottom edge fall outside the capture, so while idle troops
    remain the map is dragged down (north revealed) then up (south revealed) and searched
    again; the map is put back in place before leaving (owner request 2026-09-06)."""
    from firestone_bot.features import map_align

    scroll = atlas.MAP_DETECT_SCROLL
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
                    moved = True
                more, n, stuck = _detect_and_click(g, state, offset)
                started += n
                if offset:
                    _drag_map(g, -offset)
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


def map_start(g: Game) -> None:
    state = MapState.load(g.map_state_path)
    if g.settings.get("MapMode") == "detect":
        if not state.session_start or state.session_start == "0":
            state.session_start = ahk_now()
            state.save()
        map_start_detected(g, state)
        return
    if not state.session_start or state.session_start == "0":
        state.session_start = ahk_now()
        state.save()
    points = _priority_points(g)
    # Attempt 1 skips what is in memory; attempt 2 clears the memory and redoes everything.
    for attempt in (1, 2):
        for x, y in points:
            if state.was_clicked(x, y):
                continue
            g.focus()
            # The world map is centred (measured at 1280x720, docs/MEASUREMENTS.md 4.6), so
            # every mission point uses the centre anchor, and the map's scale (_click_mission).
            _click_mission(g, x, y)
            g.sleep(1000)
            state.mark_clicked(x, y)
            # Check Start Button (Green)
            if _start_ready(g):
                g.move_to(atlas.MS_START)
                g.toast("Mission Start", "Mission found - Starting", 1.5)
                g.click()
                g.sleep(500)
                if _left_open(g):
                    _undrag_if_needed(g, y)
                    return
                _undrag_if_needed(g, y)
                g.toast("Troop Check", "Looking for more idle troops", 2)
                if g.found(atlas.MAP_TROOP_IDLE):
                    continue
                g.toast("Troop Check", "No idle troops found - ending mission search", 2)
                return
            # No start button (mission in progress or unavailable): close the pop-up
            map_close(g)
            _undrag_if_needed(g, y)
            # Check troops after each interaction (even if not started)
            if not g.found(atlas.MAP_TROOP_IDLE):
                g.toast("Troop Check", "No idle troops found - ending mission search", 2)
                return
        # End of list: troops left after the first attempt means the memory hid something.
        if attempt == 1 and g.found(atlas.MAP_TROOP_IDLE):
            state.reset()
            continue
        break
