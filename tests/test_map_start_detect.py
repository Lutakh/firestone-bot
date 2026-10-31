"""Detection mode of map_start: edge-scroll fallback, recentring, the memory of missions, and
the map search stopped by a popup that stays. What a mission click opens is answered here
(started / closed / stuck); the popups themselves are read on real crops at every client
shape in tests/test_map_popup_scenes.py."""

from __future__ import annotations

from firestone_bot.features import map_start
from firestone_bot.vision import atlas


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

    def save_diagnostic(self, name):
        self.captures.append(name)

    def status(self, msg):
        self.log.append(msg)

    def toast(self, *a):
        pass

    def focus(self):
        pass

    def sleep(self, ms):
        pass

    def now(self):
        return 0.0

    def click_at(self, x, y, anchor=None):
        assert not self.popup, "a map point clicked under an open popup"
        self.log.append(("click", x, y))
        self.anchors.append(anchor)
        self.popup = True

    def found(self, probe, variation=None):
        if probe is atlas.MAP_TROOP_IDLE:
            return self.started < self.troops_until
        return False

    def drag(self, x0, y0, x1, y1, anchor=None):
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
