"""Port of Functions/subFunctions/MapStart.ahk: click every mission point of the world map in
priority order, start the mission when its green button shows, stop when no idle troop is
left. Points already clicked this session are remembered in MapStartState.ini.

`TimeDiff` (hours since SessionStart) is computed in AHK but never used; not reproduced.
"""

from __future__ import annotations

from firestone_bot.features.map_close import map_close
from firestone_bot.game import Game
from firestone_bot.state import MapState, ahk_now
from firestone_bot.vision import atlas


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
    """Click a mission point; north-edge points are revealed by a temporary drag (see atlas)."""
    if y >= atlas.MAP_NORTH_DRAG_LIMIT:
        g.click_at(x, y, anchor=atlas.ANCHOR_CENTER)  # Click %x%, %y%
        return
    dy = atlas.MAP_NORTH_DRAG_DY
    _drag_map(g, dy)
    g.click_at(x, y + dy, anchor=atlas.ANCHOR_CENTER)


def _undrag_if_needed(g: Game, y: int) -> None:
    if y < atlas.MAP_NORTH_DRAG_LIMIT:
        _drag_map(g, -atlas.MAP_NORTH_DRAG_DY)


def _try_mission(g: Game, state: MapState, x: int, y: int, anchor) -> bool:
    """Click one mission point and start it if the green button shows. True while idle troops
    remain (the search continues), False when the map can be left."""
    g.focus()
    g.click_at(x, y, anchor=anchor)
    g.sleep(1000)
    state.mark_clicked(x, y)
    if g.found(atlas.MS_START_BUTTON):
        g.move_to(atlas.MS_START)
        g.toast("Mission Start", "Mission found - Starting", 1.5)
        g.click()
        g.sleep(500)
    else:
        map_close(g)  # mission in progress or unavailable: close the pop-up
    g.toast("Troop Check", "Looking for more idle troops", 2)
    if g.found(atlas.MAP_TROOP_IDLE):
        return True
    g.toast("Troop Check", "No idle troops found - ending mission search", 2)
    return False


def map_start_detected(g: Game, state: MapState) -> None:
    """Detection mode: the missions are the duration labels seen on the map (map_detect)."""
    from firestone_bot.features import map_detect

    for attempt in (1, 2):
        points = map_detect.find_missions(g)
        g.status(f"Map: {len(points)} mission icon(s) detected on the screen")
        fresh = [p for p in points if not state.was_clicked(*p)]
        for x, y in fresh:
            if not _try_mission(g, state, x, y, None):
                return
        if attempt == 1 and fresh and g.found(atlas.MAP_TROOP_IDLE):
            state.reset()  # every icon tried: the memory hid something, redo them all
            continue
        break


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
            # The world map is centred and scaled with the canvas (measured at 1280x720,
            # docs/MEASUREMENTS.md 4.6), so every mission point uses the centre anchor.
            _click_mission(g, x, y)
            g.sleep(1000)
            state.mark_clicked(x, y)
            # Check Start Button (Green)
            if g.found(atlas.MS_START_BUTTON):
                g.move_to(atlas.MS_START)
                g.toast("Mission Start", "Mission found - Starting", 1.5)
                g.click()
                g.sleep(500)
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
