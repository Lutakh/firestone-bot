"""map_start's search of the map by the missions' duration labels (map_detect): edge-scroll
fallback, recentring, the memory of missions, the map search stopped by a popup that stays, a
search beyond the edge cut short, and the switch to the fixed list on a map drawn too small
for its labels (owner, 2026-10-31). What a mission click opens is answered here (started /
closed / stuck); the popups themselves are read on real crops at every client shape in
tests/test_map_popup_scenes.py."""

from __future__ import annotations

import pytest

from firestone_bot.features import map_align, map_start
from firestone_bot.game import BotStopped, GameNotInFront
from firestone_bot.inputguard import UserInterrupted
from firestone_bot.platform.window import Rect
from firestone_bot.vision import atlas
from firestone_bot.vision.viewport import Viewport


class FakeState:
    def __init__(self):
        self.clicked = set()
        self.resets = 0
        self.session_start = "x"

    def was_clicked(self, x, y):
        return (x, y) in self.clicked

    def mark_clicked(self, x, y):
        self.clicked.add((x, y))

    def reset(self):
        self.resets += 1

    def save(self):
        pass


class FakeGame:
    """Idle troops until `troops_until` mission starts; a mission list per drag offset."""

    def __init__(self, missions_by_offset, troops_until):
        self.missions_by_offset = missions_by_offset
        self.offset = 0
        self.started = 0
        self.troops_until = troops_until
        self.log = []
        self.popup = False  # a mission popup is open
        self.stuck = False  # the popup takes no click
        self.vars = {}
        self.captures = []
        self.anchors = []
        # a pass cut short on the dragged map: `cut` raised by its wait number `cut_at` there
        # (0: the one after the drag; Stop, the mouse guard's pause), or the game out of the
        # front from the first input there (`away`: "once", or "stays" for the drag back too)
        self.cut = None
        self.cut_at = 0
        self.waits_dragged = 0
        self.away = None

    def save_diagnostic(self, name):
        self.captures.append(name)

    def status(self, msg):
        self.log.append(msg)

    def toast(self, *a):
        pass

    def focus(self):
        pass

    def sleep(self, ms):
        if self.offset and self.cut is not None:
            self.waits_dragged += 1
            if self.waits_dragged > self.cut_at:
                raise self.cut()

    def now(self):
        return 0.0

    def _front(self):
        if self.offset and self.away:
            if self.away == "once":
                self.away = None
            raise GameNotInFront("the game window could not be brought to the front")

    def click_at(self, x, y, anchor=None):
        self._front()
        assert not self.popup, "a map point clicked under an open popup"
        self.log.append(("click", x, y))
        self.anchors.append(anchor)
        self.popup = True

    def found(self, probe, variation=None):
        if probe is atlas.MAP_TROOP_IDLE:
            return self.started < self.troops_until
        return False

    def drag(self, x0, y0, x1, y1, anchor=None):
        self._front()
        self.offset += y1 - y0
        self.log.append(("drag", y1 - y0))

    # the popup's side, as map_start's helpers would find it
    def open_mission(self, g, before=None, what="the mission click"):
        if not self.popup:
            return map_start.NOTHING  # before a click: nothing left open
        if self.stuck:
            return map_start.STUCK
        self.popup = False
        self.started += 1
        return map_start.STARTED

    def map_clear(self, g, watch=None):
        return not (self.popup and self.stuck)


def _run(g, state, monkeypatch, aligned):
    from firestone_bot.features import map_align, map_detect

    monkeypatch.setattr(map_detect, "find_missions", lambda game: g.missions_by_offset[g.offset])
    monkeypatch.setattr(map_align, "align_map", lambda game: aligned.append(game.offset))
    monkeypatch.setattr(map_start, "_open_mission", g.open_mission)
    monkeypatch.setattr(map_start, "map_clear", g.map_clear)
    monkeypatch.setattr(map_start, "look", lambda game: None)
    return map_start.map_start_detected(g, state)


def test_visible_missions_enough_no_scroll(monkeypatch):
    g = FakeGame({0: [(500, 400), (700, 420)]}, troops_until=2)
    aligned = []
    assert _run(g, FakeState(), monkeypatch, aligned) is True
    assert (
        g.started == 2
        and aligned == []
        and not any(e[0] == "drag" for e in g.log if isinstance(e, tuple))
    )
    # the detected points are centre-anchored, like the map (report ANHNX9, 1920x1080)
    assert g.anchors == [atlas.ANCHOR_CENTER] * 2


def test_scrolls_both_ways_then_recentres(monkeypatch):
    s = atlas.MAP_DETECT_SCROLL
    g = FakeGame({0: [(500, 400)], s: [(600, 170)], -s: [(650, 900)]}, troops_until=3)
    state = FakeState()
    aligned = []
    _run(g, state, monkeypatch, aligned)
    assert g.started == 3
    drags = [e[1] for e in g.log if isinstance(e, tuple) and e[0] == "drag"]
    assert drags == [s, -s, -s, s]  # down + back, up + back
    assert g.offset == 0 and aligned == [0]
    # missions are remembered at their in-place position
    assert (600, 170 - s) in state.clicked and (650, 900 + s) in state.clicked


def test_mission_seen_twice_is_clicked_once(monkeypatch):
    s = atlas.MAP_DETECT_SCROLL
    g = FakeGame({0: [(500, 400)], s: [(500, 400 + s)], -s: []}, troops_until=9)
    state = FakeState()
    _run(g, state, monkeypatch, [])
    clicks = [e for e in g.log if isinstance(e, tuple) and e[0] == "click"]
    assert len(clicks) == 1 and state.resets >= 1


def test_a_start_popup_left_open_stops_the_map_search(monkeypatch):
    """A popup that stays: no other map point is clicked onto it (its Complete instantly
    costs gems; new game version) and the map section is told to stop."""
    g = FakeGame({0: [(500, 400), (700, 420)]}, troops_until=9)
    g.stuck = True
    assert _run(g, FakeState(), monkeypatch, []) is False
    clicks = [e for e in g.log if isinstance(e, tuple) and e[0] == "click"]
    assert len(clicks) == 1 and g.started == 0


def test_no_alignment_under_a_stuck_popup(monkeypatch):
    """A popup stuck during the pass with the map moved: the map is dragged back, but not
    measured under the popup (a swallowed drag would turn the alignment off for the run)."""
    s = atlas.MAP_DETECT_SCROLL
    g = FakeGame({0: [], s: [], -s: [(650, 900)]}, troops_until=9)
    g.stuck = True
    aligned = []
    _run(g, FakeState(), monkeypatch, aligned)
    drags = [e[1] for e in g.log if isinstance(e, tuple) and e[0] == "drag"]
    assert drags == [s, -s, -s, s] and aligned == []


def test_no_search_while_a_popup_stays_open(monkeypatch):
    """A popup that cannot be closed before the search: its digits are no mission label (the
    in-progress popup's timer was found as one, audit 2026-10-30), nothing is searched."""
    g = FakeGame({0: [(500, 400)]}, troops_until=9)
    g.popup = g.stuck = True
    searched = []

    def find(game):
        searched.append(1)
        return [(500, 400)]

    from firestone_bot.features import map_align, map_detect

    monkeypatch.setattr(map_detect, "find_missions", find)
    monkeypatch.setattr(map_align, "align_map", lambda game: None)
    monkeypatch.setattr(map_start, "_open_mission", g.open_mission)
    monkeypatch.setattr(map_start, "map_clear", g.map_clear)
    monkeypatch.setattr(map_start, "look", lambda game: None)
    assert map_start.map_start_detected(g, FakeState()) is False
    assert searched == [] and not [e for e in g.log if isinstance(e, tuple)]


def _drags(g):
    return [e[1] for e in g.log if isinstance(e, tuple) and e[0] == "drag"]


# --- a search beyond the edge cut short (review of 8558a26, F2) ------------------------------
@pytest.mark.parametrize("cut_at", [0, 1])
def test_a_pass_cut_short_drags_the_map_back(monkeypatch, cut_at):
    """The mouse guard's pause (UserInterrupted) while the map is dragged down, right after
    the drag or after a click there: the game brought to the front, then the map dragged back
    on the way out (g.drag does not wait; on macOS and Linux nothing else checks the front),
    nothing aligned, and the exception goes on up. Left 220 px down, the map hid its landmark
    under the bottom HUD for every later visit."""
    s = atlas.MAP_DETECT_SCROLL
    g = FakeGame({0: [], s: [(600, 170 + s)], -s: []}, troops_until=9)
    g.cut, g.cut_at = UserInterrupted, cut_at
    g.vars[map_align.RECOVERY_OFF] = True  # the drag back may meet a popup the click opened
    monkeypatch.setattr(g, "focus", lambda: g.log.append(("focus",)), raising=False)
    aligned = []
    with pytest.raises(UserInterrupted):
        _run(g, FakeState(), monkeypatch, aligned)
    assert _drags(g) == [s, -s] and g.offset == 0 and aligned == []
    assert map_align.RECOVERY_OFF not in g.vars
    assert len([e for e in g.log if isinstance(e, tuple) and e[0] == "click"]) == cut_at
    events = [e[0] for e in g.log if isinstance(e, tuple) and e[0] in ("focus", "drag")]
    assert events[-2:] == ["focus", "drag"]  # the front first, then the drag back


def test_a_stop_set_while_the_pause_unwinds_sends_nothing_more(monkeypatch):
    """The pause's "new cycle" and a Stop in the same poll: UserInterrupted with the stop
    already set. No focus and no drag back after the Stop (review of 3cba41f)."""
    import threading

    s = atlas.MAP_DETECT_SCROLL
    g = FakeGame({0: [], s: [(600, 170 + s)], -s: []}, troops_until=9)
    g.cut, g.cut_at = UserInterrupted, 0
    g.stop_event = threading.Event()
    g.stop_event.set()
    monkeypatch.setattr(g, "focus", lambda: g.log.append(("focus",)), raising=False)
    with pytest.raises(UserInterrupted):
        _run(g, FakeState(), monkeypatch, [])
    assert _drags(g) == [s] and g.offset == s
    assert "Map: stopped with the map dragged; the next alignment looks for it" in g.log


@pytest.mark.parametrize("cut_at", [0, 1])
def test_a_stop_while_the_map_is_dragged_sends_nothing_more(monkeypatch, cut_at):
    """Stop (BotStopped from a wait) while the map is dragged down: not one more input after
    a Stop (as enlighten), so the map stays down, said; the next alignment drags it up to look
    for its landmark (RECOVERY_OFF dropped), and the Stop goes on up."""
    s = atlas.MAP_DETECT_SCROLL
    g = FakeGame({0: [], s: [(600, 170 + s)], -s: []}, troops_until=9)
    g.cut, g.cut_at = BotStopped, cut_at
    g.vars[map_align.RECOVERY_OFF] = True
    with pytest.raises(BotStopped):
        _run(g, FakeState(), monkeypatch, [])
    assert _drags(g) == [s] and g.offset == s
    assert map_align.RECOVERY_OFF not in g.vars
    assert "Map: stopped with the map dragged; the next alignment looks for it" in g.log


@pytest.mark.parametrize("away", ["once", "stays"])
def test_a_pass_cut_by_the_game_leaving_the_front(monkeypatch, away):
    """GameNotInFront from the click on the dragged map: the drag back is sent once the game
    is in front again. Still not in front, g.drag's check raises again: the map stays down,
    said, and the next alignment may drag it up to look for its landmark (RECOVERY_OFF
    dropped, as for any pass cut short); GameNotInFront goes on up either way."""
    s = atlas.MAP_DETECT_SCROLL
    g = FakeGame({0: [], s: [(600, 170 + s)], -s: []}, troops_until=9)
    g.away = away
    g.vars[map_align.RECOVERY_OFF] = True
    with pytest.raises(GameNotInFront):
        _run(g, FakeState(), monkeypatch, [])
    assert map_align.RECOVERY_OFF not in g.vars
    if away == "once":
        assert _drags(g) == [s, -s] and g.offset == 0
    else:
        assert _drags(g) == [s] and g.offset == s
        assert (
            "Map: the map could not be dragged back after a search beyond its edge; the next "
            "alignment looks for it"
        ) in g.log


def test_a_drag_back_under_a_stuck_popup_lets_the_next_alignment_look_higher(monkeypatch):
    """The drag back made under a popup that stays may be swallowed: the next visit's
    alignment may drag the map up to look for its landmark."""
    s = atlas.MAP_DETECT_SCROLL
    g = FakeGame({0: [], s: [(600, 170 + s)], -s: []}, troops_until=9)
    g.stuck = True
    g.vars[map_align.RECOVERY_OFF] = True
    assert _run(g, FakeState(), monkeypatch, []) is False
    assert _drags(g) == [s, -s] and map_align.RECOVERY_OFF not in g.vars


# --- the way the missions are found: labels, or the fixed list -------------------------------
class _WayGame:
    """map_start's view of a game for the switch: the client, the map scale measured, the
    lines said."""

    def __init__(self, tmp_path, client, scale=None, settings=None):
        self.vp = Viewport(Rect(0, 0, *client))
        self.vars = {} if scale is None else {map_align.SCALE_KEY: scale}
        self.lines = []
        self.settings = settings
        self.map_state_path = str(tmp_path / "MapStartState.ini")

    def _viewport(self):
        return self.vp

    def status(self, text):
        self.lines.append(text)


def _ways(monkeypatch):
    """The way each map_start call took ("labels" / "points"), and the arguments."""
    ways = []

    def way(name):
        def search(g, state, watch=None):
            ways.append((name, g, state, watch))
            return True

        return search

    monkeypatch.setattr(map_start, "map_start_detected", way("labels"))
    monkeypatch.setattr(map_start, "map_start_coordinates", way("points"))
    return ways


def _switch_scale(g) -> float:
    """map_start's scale: the client's height against the reference client's (the drawn
    scale never exceeds it; a window made taller than 16:9 draws the map at its height)."""
    height = round(g.vp.client.h / atlas.REF.h, 3)
    assert map_align.drawn_scale(g) <= height
    return height


@pytest.mark.parametrize(
    ("client", "scale", "way"),
    [
        ((1920, 1009), None, "labels"),  # the owner's client, before any measure
        ((1920, 1080), map_align.FITTED_SCALE, "labels"),  # ANHNX9: 1.0
        # near the threshold (0.7): on the side DETECT_MIN_SCALE puts them, so that it can
        # be moved alone
        ((1366, 768), None, None),  # 0.761, the owner's window resized
        ((1366, 768), map_align.FITTED_SCALE, None),  # drawn 0.711, its height 0.761
        ((1280, 720), map_align.FITTED_SCALE, None),  # drawn 0.667, its height 0.714
        ((1152, 648), None, None),  # 0.642
        # made taller than 16:9: the map follows the height (2026-10-31), drawn 0.571
        ((1024, 768), None, "labels"),
        ((1024, 576), None, "points"),  # 0.571
        ((800, 600), None, "points"),  # drawn 0.446, its height 0.595
        # a maximised window on a screen 768 px tall: about 697 px (0.691) on the owner's PC
        ((1366, 697), None, "points"),
    ],
)
def test_the_way_follows_the_scale_the_map_is_drawn_at(monkeypatch, tmp_path, client, scale, way):
    """Labels from DETECT_MIN_SCALE up, the fixed list under it; said once, with the scale."""
    g = _WayGame(tmp_path, client, scale)
    switch = _switch_scale(g)
    if way is None:
        way = "labels" if switch >= map_start.DETECT_MIN_SCALE else "points"
    assert (switch >= map_start.DETECT_MIN_SCALE) == (way == "labels"), "the case moved sides"
    ways = _ways(monkeypatch)
    assert map_start.map_start(g) is True and map_start.map_start(g) is True
    assert [w[0] for w in ways] == [way, way] and len(g.lines) == 1
    drawn = map_align.drawn_scale(g)
    if way == "labels":
        line = (
            f"Map: missions are found by their duration labels (window height {switch:.3f} "
            f"of the reference, map drawn at {drawn:.3f})"
        )
    else:
        line = (
            f"Map: the window is too small for the labels (height {switch:.3f} of the "
            f"reference, under {map_start.DETECT_MIN_SCALE}); missions are clicked from the "
            "fixed list"
        )
    assert g.lines == [line]


def test_the_way_is_said_again_when_it_changes(monkeypatch, tmp_path):
    """The window resized (or the game restarted at another size) between two visits: the
    other way, said; a new run says it again (the runner drops WAY_KEY)."""
    g = _WayGame(tmp_path, (1920, 1009))
    ways = _ways(monkeypatch)
    map_start.map_start(g)
    g.vp = Viewport(Rect(0, 0, 1024, 576))
    g.vars[map_align.SCALE_KEY] = map_align.FITTED_SCALE  # 0.533, its height 0.571
    map_start.map_start(g)
    map_start.map_start(g)
    assert [w[0] for w in ways] == ["labels", "points", "points"] and len(g.lines) == 2
    g.vars.pop(map_start.WAY_KEY)
    map_start.map_start(g)
    assert len(g.lines) == 3 and g.lines[-1] == g.lines[1]


@pytest.mark.parametrize(
    ("mode", "client", "way"),
    [("coordinates", (1920, 1009), "labels"), ("detect", (800, 600), "points")],
)
def test_an_older_settings_file_does_not_choose_the_way(monkeypatch, tmp_path, mode, client, way):
    """MapMode and the category order of an older settings.ini are not read (no setting since
    2026-10-31): the map's scale chooses. The session's memory is started and map_redeem's
    look goes with the search."""
    from firestone_bot.features.map_close import Watch
    from firestone_bot.settings import Settings
    from firestone_bot.state import MapState

    ini = tmp_path / "settings.ini"
    ini.write_text(
        f"[MissionPriority]\nMapMode={mode}\nPriority1=War\nPriority2=2 Squad\n"
        "Priority3=Medium\nPriority4=Short\nPriority5=Leftover\nMapReset=0\n",
        encoding="utf-8-sig",
    )
    g = _WayGame(tmp_path, client, settings=Settings.load(str(ini)))
    ways = _ways(monkeypatch)
    watch = Watch()
    assert map_start.map_start(g, watch) is True
    ((name, game, state, passed),) = ways
    assert name == way and game is g and passed is watch and isinstance(state, MapState)
    assert MapState.load(g.map_state_path).session_start


def test_each_run_says_the_way_again_and_may_look_higher_again():
    """Game.vars outlives a Stop: the runner drops the way said and the alignment's give-up
    on the drag up when a run starts; the map scale measured stays (the next alignment reads
    it again)."""
    from types import SimpleNamespace

    from firestone_bot import runner
    from firestone_bot.settings import Settings

    scale = {map_align.SCALE_KEY: map_align.FITTED_SCALE}
    g = SimpleNamespace(
        front_guard=None, vars={map_start.WAY_KEY: "labels", map_align.RECOVERY_OFF: True, **scale}
    )
    r = runner.Runner.__new__(runner.Runner)
    r.g, r.settings = g, Settings()
    r._cycle = lambda: False
    r.main_script()
    assert g.vars == scale
