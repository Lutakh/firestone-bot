"""Detection mode of map_start: edge-scroll fallback and recentring."""

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
        self.started += 1

    def click_at(self, x, y, anchor=None):
        self.log.append(("click", x, y))

    def found(self, probe, variation=None):
        if probe is atlas.MS_START_BUTTON:
            return True
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
    assert len(clicks) == 1 and state.resets == 1
