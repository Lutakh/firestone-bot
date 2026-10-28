"""Detection mode of map_start: edge-scroll fallback and recentring."""

from __future__ import annotations

import numpy as np

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
        self.popup = False  # a start popup is open
        self.stuck = False  # the popup ignores Start and close taps
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

    def move_to(self, p):
        pass

    def click(self):
        if not self.stuck:
            self.started += 1
            self.popup = False

    def click_at(self, x, y, anchor=None):
        self.log.append(("click", x, y))
        self.anchors.append(anchor)
        self.popup = True

    def tap(self, p, settle_ms=1500, expect=None):
        self.log.append(("tap", p.x, p.y))
        if not self.stuck:
            self.popup = False

    def wait_gone(self, probe, timeout_ms=0):
        return not self.found(probe)

    def region_image(self, rect, anchor=None):
        x1, y1, x2, y2 = rect
        return np.zeros((y2 - y1, x2 - x1, 3), np.uint8)  # the Start button: no gem

    def found(self, probe, variation=None):
        if probe is atlas.MS_START_BUTTON:
            return self.popup
        if probe is atlas.MAP_TROOP_IDLE:
            return self.started < self.troops_until
        return False

    def drag(self, x0, y0, x1, y1, anchor=None):
        self.offset += y1 - y0
        self.log.append(("drag", y1 - y0))


def _run(g, state, monkeypatch, aligned):
    from firestone_bot.features import map_align, map_detect

    monkeypatch.setattr(map_detect, "find_missions", lambda game: g.missions_by_offset[g.offset])
    monkeypatch.setattr(map_align, "align_map", lambda game: aligned.append(game.offset))
    map_start.map_start_detected(g, state)


def test_visible_missions_enough_no_scroll(monkeypatch):
    g = FakeGame({0: [(500, 400), (700, 420)]}, troops_until=2)
    aligned = []
    _run(g, FakeState(), monkeypatch, aligned)
    assert (
        g.started == 2
        and aligned == []
        and not any(e[0] == "drag" for e in g.log if isinstance(e, tuple))
    )
    # the start popup of game 9.1.3a is captured once a run, before its first Start click
    assert g.captures.count("mission-start-popup.png") == 1
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


def test_a_start_button_with_a_gem_is_never_clicked():
    """Green is no proof of free (gem audit, 2026-10-22): a gem in the Start button keeps
    the mission unstarted and its popup is closed."""
    g = FakeGame({0: []}, troops_until=5)
    g.popup = True
    g.region_image = lambda rect, anchor=None: np.full(
        (rect[3] - rect[1], rect[2] - rect[0], 3), (0x9D, 0x00, 0x9F), np.uint8
    )
    assert not map_start._start_ready(g)
    assert "Mission Start: the Start button shows a gem, not clicked" in g.log


def test_a_start_popup_left_open_stops_the_map_search(monkeypatch):
    """A Start that does not close the popup: closed once, and when it stays, no other map
    point is clicked onto it (its Complete instantly costs gems; new game version)."""
    g = FakeGame({0: [(500, 400), (700, 420)]}, troops_until=9)
    g.stuck = True
    _run(g, FakeState(), monkeypatch, [])
    clicks = [e for e in g.log if isinstance(e, tuple) and e[0] == "click"]
    assert len(clicks) == 1 and g.started == 0
    assert "Mission Start: the popup stays open after Start; map search stopped" in g.log


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
