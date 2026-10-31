"""The map section's popups when the screen changes under the bot's reads (tests/screens.py's
scenes on the virtual clock): a price drawn a frame late or gone after the first read, a popup
that never settles, a panel missing from a read, a popup that opens late; and popups the
reader cannot see (another interface style, or the reader blinded), told by the centre's look
(map_close.look / changed) and closed beside where any popup draws, never clicked through."""

from __future__ import annotations

import numpy as np
import pytest

from firestone_bot.features import map_align, map_detect, map_redeem, map_start
from firestone_bot.game import StepAborted
from firestone_bot.vision import atlas, mission_popup
from tests import screens

UNREAD_LINE = "Map: {} opened something the bot cannot read; closing it"
UNREAD_STUCK = "Map: what opened stays open after two close taps; map section stopped"
POINTS = [(800, 500), (1100, 600), (600, 700)]  # detection mode: the labels found


def _game(monkeypatch, tmp_path, scene, name, **settings):
    folder = tmp_path / name
    folder.mkdir(exist_ok=True)
    settings.setdefault("Timing", "safe")
    return screens.scene_game(monkeypatch, scene, folder, **settings)


def _detect(monkeypatch, scene, points=POINTS):
    monkeypatch.setattr(
        map_detect, "find_missions", lambda g: list(points) if scene.map_offset == 0 else []
    )
    monkeypatch.setattr(map_align, "align_map", lambda g: None)


def _one_group(settings: dict) -> dict:
    """Coordinates mode on the "2 Squad" points only (22): a quicker visit."""
    return {**settings, **{f"Priority{i}": "" for i in range(2, 6)}}


def _closed_beside(scene, popup, times=1):
    """`popup` opened `times` and each time closed by one tap beside its panel, nothing else
    clicked while it was open."""
    clicks = scene.clicks_on(popup)
    assert len(clicks) == times, scene.events
    assert not any(scene.panel(popup).contains(x, y) for x, y in clicks)


# --- a price drawn late, a price gone, a popup that never settles --------------------------
@pytest.mark.parametrize("timing", ["safe", "fast"])
@pytest.mark.parametrize("shape", [(1920, 1009, "centre"), (1600, 1200, "top")])
def test_a_price_drawn_after_the_first_read_is_seen(monkeypatch, tmp_path, shape, timing):
    """The free layout's orange gets its gem 50 ms after the bot's first read of it, before
    the second (gems.CONFIRM_MS later): the reads disagree, the next two agree on the gem,
    and the Speed up is a price (pressed, it would be the paid button)."""
    s = screens.Morph(*shape, morphs={"free": "free-gem"})
    s.list_queue = ["free"]
    g = _game(monkeypatch, tmp_path, s, "late-gem", Timing=timing)
    assert map_redeem._checks(g) is True
    assert s.switched and s.switched[0] >= 2  # the first reads saw no price
    assert s.speed_ups == 0 and s.faults == []
    assert s.popup is None and s.closed_x == 1 and s.clicks_on("free") == []
    assert "Mission Check: Mission has more than 3 minutes remaining" in g.lines


def test_a_price_seen_once_counts(monkeypatch, tmp_path):
    """A gem in the first read only (the popup turns free under the bot's eyes): a gem seen
    in any read counts, as in gems.shows_gem; closed by its X, the Free never pressed."""
    s = screens.Morph(1920, 1009, morphs={"free-gem": "free"})
    s.list_queue = ["free-gem"]
    g = _game(monkeypatch, tmp_path, s, "gem-once")
    assert map_redeem._checks(g) is True
    assert s.switched and s.switched[0] >= 2  # the later reads saw no price
    assert s.speed_ups == 0 and s.faults == [] and s.closed_x == 1
    assert "Mission Check: Mission has more than 3 minutes remaining" in g.lines


def test_reads_that_never_agree_are_an_unknown_popup(monkeypatch, tmp_path):
    """The free popup 30 px higher at every other read: never two reads alike, so whatever
    the reads said it is unknown: closed by its X, the Free never pressed."""
    s = screens.Flicker(1920, 1009)
    s.list_queue = ["free"]
    g = _game(monkeypatch, tmp_path, s, "flicker")
    assert map_redeem._checks(g) is True
    assert s.speed_ups == 0 and s.faults == [] and s.closed_x == 1
    assert g.diagnostics == ["mission-dialog-unknown.png"]


def test_a_gem_in_reads_that_never_agree_after_a_speed_up_is_a_gem_met(monkeypatch, tmp_path):
    """After the free speed-up, a window that never settles and shows a gem in some reads
    only (the last one without): an unknown popup, but a gem seen counts: never confirmed,
    a gem met, closed by its X."""
    s = screens.Flicker(1920, 1009, pair=("free-gem", "free-up"))
    s.list_queue, s.after_free = ["free"], "free-gem"
    g = _game(monkeypatch, tmp_path, s, "flicker-gem")
    assert map_redeem._checks(g) is True
    assert s.speed_ups == 1 and s.faults == [] and s.closed_x == 1
    assert g.vars[map_redeem.GEM_SEEN] == 1 and "mission-gem-dialog.png" in g.diagnostics


@pytest.mark.parametrize(("gap", "timing"), [(1, "safe"), (2, "safe"), (1, "fast"), (2, "fast")])
def test_a_panel_missing_from_a_read_is_not_gone(monkeypatch, tmp_path, gap, timing):
    """A Start that takes no press, and the panel missing from the next one or two reads (a
    re-layout): gone needs two reads without a panel and the centre as before the click; the
    popup is closed by its X and the mission not counted."""
    s = screens.Gap(1920, 1009, gap=gap)
    s.queue, s.idle = ["start-deaf"], 4
    _detect(monkeypatch, s, POINTS[:1])
    g = _game(monkeypatch, tmp_path, s, "gap", MapMode="detect", Timing=timing)
    assert map_start.map_start(g) is True
    assert s.started == 0 and s.faults == [] and s.closed_x == 1
    assert "Mission Start: the popup stayed open after Start; closed" in g.lines
    assert not any("mission(s) started" in line for line in g.lines)


# --- a popup that opens late ----------------------------------------------------------------
@pytest.mark.parametrize("timing", ["safe", "fast"])
@pytest.mark.parametrize("delay", [1.2, 1.6, 2.5])
def test_a_start_popup_that_opens_late_is_started_detect(monkeypatch, tmp_path, delay, timing):
    """Detection mode (every click on a mission's label), a game that hitches: each popup
    shows 1.2 to 2.5 s after its click. It is started before the next click, none closed,
    no click made while one is coming."""
    s = screens.LateScene(1920, 1009, delay=delay)
    s.queue, s.idle = ["start"] * 3, 6
    _detect(monkeypatch, s)
    g = _game(monkeypatch, tmp_path, s, "late", MapMode="detect", Timing=timing)
    assert map_start.map_start(g) is True
    assert s.started == 3 and s.closed_x == s.closed_out == 0, g.lines
    assert s.early == [] and s.faults == []


@pytest.mark.parametrize("looks", [["start"] * 3, ["start+rb", "paid+rb", "start+rb"]])
def test_a_popup_later_than_the_wait_is_found_before_the_next_click(monkeypatch, tmp_path, looks):
    """Detection mode, safe timing, popups 3.5 s after their click (past the 3 s waited
    for): found by the look before the next click, the last one before the pass ends and
    the map is dragged (the drag drops that look); started, or of another style closed
    beside; nothing clicked on them."""
    s = screens.LateScene(1920, 1009, delay=3.5)
    s.queue, s.idle = list(looks), 6
    _detect(monkeypatch, s)
    g = _game(monkeypatch, tmp_path, s, "later", MapMode="detect")
    assert map_start.map_start(g) is True
    assert s.early == [] and s.faults == []
    if looks[0] == "start":
        assert s.started == 3 and s.closed_x == s.closed_out == 0
    else:
        assert s.started == 0 and s.closed_out == 3


def test_the_look_before_a_click_is_dropped_when_the_map_moves(monkeypatch, tmp_path):
    """Detection mode, missions found with the map in place and moved up: the look before
    the last click (on the moved map) is no reference once the map is dragged back; kept, the
    next search would take the map's move for something open and tap beside it on the map."""
    s = screens.Scene(1920, 1009)
    s.queue, s.idle = ["start", "start"], 6
    scroll = atlas.MAP_DETECT_SCROLL
    found = {0: [(800, 500)], -scroll: [(600, 700 - scroll)]}
    monkeypatch.setattr(map_detect, "find_missions", lambda g: list(found.get(s.map_offset, [])))
    monkeypatch.setattr(map_align, "align_map", lambda g: None)
    g = _game(monkeypatch, tmp_path, s, "moved", MapMode="detect")
    assert map_start.map_start(g) is True
    assert s.started == 2 and s.faults == [] and s.closed_out == 0
    assert not any("cannot read" in line for line in g.lines)


@pytest.mark.parametrize("timing", ["safe", "fast"])
@pytest.mark.parametrize("delay", [1.2, 2.5])
def test_a_start_popup_that_opens_late_is_started_coordinates(monkeypatch, tmp_path, delay, timing):
    """Coordinates mode, the same hitch: every popup is started, none closed, nothing clicked
    on an open popup (the next point is clicked while it is still coming: see below)."""
    s = screens.LateScene(1920, 1009, delay=delay)
    s.queue, s.idle = ["start"] * 3, 6
    g = _game(monkeypatch, tmp_path, s, "late-xy", Timing=timing)
    assert map_start.map_start(g) is True
    assert s.started == 3 and s.closed_x == s.closed_out == 0 and s.faults == []


NORTH_FIRST = [(1300, 26), (384, 1009), (484, 920)]  # a north-edge point, then two others


def test_a_start_popup_that_opens_while_the_map_is_dragged_back_is_started(monkeypatch, tmp_path):
    """Coordinates mode, a north-edge point (the map dragged down for it, then back): its
    popup shows 1.2 s after the click, during the drag back; found before the next click
    and started, nothing clicked on it."""
    s = screens.LateScene(1920, 1009, delay=1.2)
    s.queue, s.idle = ["start", "start"], 4
    monkeypatch.setattr(map_start, "_priority_points", lambda g: list(NORTH_FIRST))
    g = _game(monkeypatch, tmp_path, s, "north")
    assert map_start.map_start(g) is True
    assert s.faults == [] and s.started == 2 and s.closed_x == s.closed_out == 0


def test_a_popup_the_reader_cannot_see_opening_while_the_map_is_dragged_back(monkeypatch, tmp_path):
    """A north-edge point's drag back drops its look before the click (the map moved): a
    late popup is waited for before it, so one the reader cannot see, showing 1.2 s after
    the click, is closed beside it and the next point is not clicked on it."""
    s = screens.LateScene(1920, 1009, delay=1.2)
    s.queue, s.idle = ["start+rb", "start"], 4
    monkeypatch.setattr(map_start, "_priority_points", lambda g: list(NORTH_FIRST))
    g = _game(monkeypatch, tmp_path, s, "north-rb")
    assert map_start.map_start(g) is True
    assert s.faults == []


@pytest.mark.parametrize("look", ["start", "start+rb"])
def test_a_late_popup_showing_during_a_north_points_drag(monkeypatch, tmp_path, look):
    """Coordinates mode: the drag before a north-edge point drops the look before the last
    click, so a popup that click opened late is waited for before the drag (and one that
    shows during the drag is read before the north click): never clicked on."""
    s = screens.LateScene(1920, 1009, delay=1.2)
    s.queue, s.idle = [look, "start"], 4
    monkeypatch.setattr(map_start, "_priority_points", lambda g: [(384, 1009), *NORTH_FIRST])
    g = _game(monkeypatch, tmp_path, s, "north-second")
    map_start.map_start(g)
    assert s.faults == []


@pytest.mark.xfail(
    strict=True,
    reason="coordinates mode clicks the next point 1.0 s after a click that showed nothing "
    "(the AHK timing): waiting 2.5 s for a late popup would cost 1.5 s on every point without "
    "a mission, up to 2 x 78 points a visit; the late popup is started after that click",
)
@pytest.mark.parametrize("delay", [1.2, 2.5])
def test_coordinates_mode_waits_for_a_late_popup(monkeypatch, tmp_path, delay):
    s = screens.LateScene(1920, 1009, delay=delay)
    s.queue, s.idle = ["start"] * 3, 6
    g = _game(monkeypatch, tmp_path, s, "late-xy-wait", Timing="fast")
    assert map_start.map_start(g) is True
    assert s.early == []


# --- popups the reader cannot see ---------------------------------------------------------
@pytest.mark.parametrize("mode", ["coordinates", "detect"])
def test_a_mission_popup_of_another_style_is_closed_beside_it(monkeypatch, tmp_path, mode):
    """A map click opens a popup the reader cannot see (red and blue swapped: another
    interface style): the centre changed, so it is closed beside where any popup draws,
    captured once, and no map point is clicked through it."""
    s = screens.Scene(1920, 1009)
    s.queue, s.idle = ["start+rb", "paid+rb"], 4
    _detect(monkeypatch, s, POINTS[:2])
    g = _game(monkeypatch, tmp_path, s, "rb-" + mode, **_one_group({"MapMode": mode}))
    assert map_start.map_start(g) is True
    assert s.faults == [] and s.started == 0 and s.closed_out == 2
    _closed_beside(s, "start+rb")
    _closed_beside(s, "paid+rb")
    assert g.lines.count(UNREAD_LINE.format("the mission click")) == 2
    assert g.diagnostics.count("mission-popup-unread.png") == 1


@pytest.fixture
def blind(monkeypatch):
    """The reader blinded: its panel colour matches nothing (a colour shift past its margins,
    a style it was never measured on); everything else on screen as it is."""
    monkeypatch.setattr(mission_popup, "cream_mask", lambda img: np.zeros(img.shape[:2], bool))


@pytest.mark.parametrize(
    "shape", [(1920, 1009, "centre"), (1280, 1024, "top"), (3440, 1440, "centre")]
)
def test_with_the_reader_blind_the_popups_are_closed_beside_them(
    monkeypatch, tmp_path, blind, shape
):
    """Every popup a map click opens, unread: closed beside it, nothing of it pressed (its
    Complete instantly, Speed up and Cancel lie where coordinates-mode points fall)."""
    s = screens.Scene(*shape)
    s.queue, s.idle = ["start", "paid", "free"], 4
    g = _game(monkeypatch, tmp_path, s, "blind", **_one_group({}))
    assert map_start.map_start(g) is True
    assert s.faults == [] and s.started == s.speed_ups == 0 and s.closed_out == 3
    for popup in ("start", "paid", "free"):
        _closed_beside(s, popup)


def test_the_list_tap_opens_what_the_reader_cannot_see(monkeypatch, tmp_path, blind):
    """The list's in-progress popup, unread: closed beside it, and the visit goes to the
    troops (never the paid Speed up or the Cancel)."""
    s = screens.Scene(1920, 1009)
    s.list_queue = ["paid"]
    g = _game(monkeypatch, tmp_path, s, "blind-list")
    assert map_redeem._checks(g) is True
    assert s.faults == [] and s.speed_ups == 0
    _closed_beside(s, "paid")
    assert UNREAD_LINE.format("the tap on the mission list") in g.lines
    assert g.diagnostics == ["mission-popup-unread.png"]


def test_a_window_the_reader_cannot_see_after_a_speed_up_is_a_gem_met(monkeypatch, tmp_path):
    """The free speed-up pressed, then a window of another style: never confirmed, counted as
    a gem met (twice in a row: free speed-ups off), closed beside it, Goto Troops."""
    s = screens.Scene(1920, 1009)
    s.list_queue, s.after_free = ["free", "free"], "rewards+rb"
    g = _game(monkeypatch, tmp_path, s, "rb-after-free")
    assert map_redeem._checks(g) is True
    assert s.speed_ups == 1 and s.claimed == 0 and s.faults == []
    _closed_beside(s, "rewards+rb")
    assert g.vars[map_redeem.GEM_SEEN] == 1 and "mission-gem-dialog.png" in g.diagnostics
    what = "a window the bot cannot read opened after a speed-up click"
    assert f"Mission Check: {what}: not confirmed" in g.lines
    assert UNREAD_LINE.format("the speed-up click") in g.lines


@pytest.mark.parametrize(("delay", "timing"), [(0.0, "safe"), (1.5, "safe"), (1.5, "fast")])
def test_a_window_the_reader_cannot_see_after_a_claim_is_closed_first(
    monkeypatch, tmp_path, delay, timing
):
    """A window of another style that opens after the Mission Rewards' Okay (a level-up):
    at once, the Okay's own check sees the centre still changed and closes it beside; once
    they are gone, the next check sees the centre changed since its tap on the list and
    closes it beside (and says so), before the next tap on the list."""
    s = screens.AfterOkay(1920, 1009, then="paid+rb", delay=delay)
    s.list_queue = ["rewards", "paid"]
    g = _game(monkeypatch, tmp_path, s, "after-okay", Timing=timing)
    assert map_redeem._checks(g) is True
    assert s.claimed == 1 and s.faults == [] and s.closed_x == 1
    _closed_beside(s, "paid+rb")
    said = UNREAD_LINE.format("something since the last map click") in g.lines
    assert said == (delay > 0)


@pytest.mark.parametrize("mode", ["coordinates", "detect"])
def test_a_popup_the_reader_cannot_see_that_opens_late(monkeypatch, tmp_path, mode):
    """The hitch and the other style together: closed beside it once it shows, before any
    map click lands on it."""
    s = screens.LateScene(1920, 1009, delay=1.6)
    s.queue, s.idle = ["paid+rb", "start+rb"], 4
    _detect(monkeypatch, s, POINTS[:2])
    g = _game(monkeypatch, tmp_path, s, "rb-late", **_one_group({"MapMode": mode}))
    assert map_start.map_start(g) is True
    assert s.faults == [] and s.started == 0 and s.closed_out == 2
    _closed_beside(s, "paid+rb")
    _closed_beside(s, "start+rb")


@pytest.mark.parametrize("timing", ["safe", "fast"])
def test_what_the_list_tap_opens_late_is_closed_before_the_first_map_click(
    monkeypatch, tmp_path, timing
):
    """The list tap's popup, of another style, shows after the reads of the check: the
    look before that tap goes with the visit to the troops (map_redeem's Watch), so the
    change is seen before the map is searched and clicked, and closed beside, never clicked
    through (detection mode: the hitch delays the mission's popup too)."""
    s = screens.LateScene(1920, 1009, delay=1.5)
    s.list_queue, s.queue, s.idle = ["paid+rb"], ["start"], 2
    _detect(monkeypatch, s, POINTS[:1])
    g = _game(monkeypatch, tmp_path, s, "rb-late-list", MapMode="detect", Timing=timing)
    map_redeem.map_redeem(g)
    assert [e[0] for e in s.events] == ["list", "screen", "map", "screen"]
    assert s.faults == [] and s.early == [] and s.started == 1
    _closed_beside(s, "paid+rb")
    assert UNREAD_LINE.format("something since the last map click") in g.lines


def test_a_panel_with_nowhere_to_tap_beside_it_stops_the_visit(monkeypatch, tmp_path):
    """A cream panel almost as wide as the client and no X (here at 16:9): no point beside
    it on the client, so nothing is tapped (another window could take it), it is said and
    captured, and map_redeem raises StepAborted."""
    box = screens.centred_box(0.93, 1.8)
    monkeypatch.setitem(
        screens.LOOKS, "cream-wide", screens.Look((), box, edits=((box, screens.CREAM),))
    )
    s = screens.Scene(1920, 1080)
    s.list_queue, s.queue, s.idle = ["cream-wide"], ["start"], 2
    g = _game(monkeypatch, tmp_path, s, "wide")
    with pytest.raises(StepAborted, match=map_redeem.STUCK):
        map_redeem.map_redeem(g)
    assert [e[0] for e in s.events] == ["list"] and s.faults == []
    assert g.diagnostics == ["mission-dialog-unknown.png", "mission-popup-stuck.png"]


@pytest.mark.parametrize("mode", ["coordinates", "detect"])
def test_what_a_map_click_opens_unread_and_stuck_stops_the_search(monkeypatch, tmp_path, mode):
    """A map click opens a popup of another style that the taps beside it do not close:
    said, captured, and nothing more is clicked on the map."""
    s = screens.Scene(1920, 1009)
    s.queue, s.idle, s.stuck = ["start+rb", "start"], 4, True
    _detect(monkeypatch, s, POINTS[:2])
    g = _game(monkeypatch, tmp_path, s, "rb-stuck-map", MapMode=mode)
    assert map_start.map_start(g) is False
    assert [e[0] for e in s.events] == ["map", "screen", "screen"] and s.faults == []
    assert UNREAD_STUCK in g.lines and "mission-popup-stuck.png" in g.diagnostics


def test_what_the_reader_cannot_see_and_does_not_close_stops_the_visit(monkeypatch, tmp_path):
    """Unread after the list tap and still there after two taps beside it: said, captured,
    and map_redeem raises StepAborted (the runner goes back to the main screen): no mission
    started under it, no campaign."""
    s = screens.Scene(1920, 1009)
    s.list_queue, s.stuck, s.queue, s.idle = ["paid+rb"], True, ["start"], 4
    claimed = []
    monkeypatch.setattr(map_redeem, "claim_campaign", lambda g: claimed.append(1))
    g = _game(monkeypatch, tmp_path, s, "rb-stuck", Campaign="1")
    with pytest.raises(StepAborted, match=map_redeem.STUCK):
        map_redeem.map_redeem(g)
    assert [e[0] for e in s.events] == ["list", "screen", "screen"]
    assert not any(s.panel("paid+rb").contains(x, y) for x, y in s.clicks_on("paid+rb"))
    assert UNREAD_STUCK in g.lines and "mission-popup-stuck.png" in g.diagnostics
    assert s.faults == [] and s.started == 0 and claimed == []


# --- the guards of the second review's follow-ups (third review, 2026-10-31) -------------
TRADE_THEN_NORTH = [(1255, 853), (1533, 98), (1608, 119)]


@pytest.mark.parametrize("look", ["start", "paid"])
def test_a_popup_shown_during_the_north_drag_is_handled_and_the_map_put_back(
    monkeypatch, tmp_path, look
):
    """Trade Route's popup shows 3.4 s after its click: after the wait before the north drag,
    during the drag. Read before the north click and handled (started, or closed by its X),
    the map dragged back, the north point left for the second round."""
    s = screens.LateScene(1920, 1009, delay=3.4)
    s.queue, s.idle = [look, "start"], 6
    monkeypatch.setattr(map_start, "_priority_points", lambda g: list(TRADE_THEN_NORTH))
    g = _game(monkeypatch, tmp_path, s, "north-drag-" + look, Timing="fast")
    assert map_start.map_start(g) is True
    assert s.faults == [] and s.map_offset == 0
    assert [e[0] for e in s.events][:4] == ["map", "drag", "screen", "drag"], s.events


def test_a_list_popup_shown_after_the_checks_is_closed_before_the_campaign(monkeypatch, tmp_path):
    """No idle troops (the owner's usual visit) and the list tap's popup 1.8 s late, after
    the checks' reads: closed by its X before the campaign icon is tapped."""
    s = screens.LateScene(1920, 1009, delay=1.8)
    s.list_queue, s.idle = ["paid"], 0
    seen = []
    monkeypatch.setattr(map_redeem, "claim_campaign", lambda g: (s.tick(), seen.append(s.popup)))
    g = _game(monkeypatch, tmp_path, s, "late-campaign", Timing="fast", Campaign="1")
    map_redeem.map_redeem(g)
    assert seen == [None] and s.closed_x == 1 and s.faults == []


def test_a_list_popup_shown_after_the_checks_is_closed_before_the_paid_reset(monkeypatch, tmp_path):
    """MapReset=1 with the reset offered and no idle troops: the list tap's popup 1.8 s late
    is closed by its X before the reset button is pressed (its confirm is a blind point)."""
    s = screens.LateScene(1920, 1009, delay=1.8)
    s.list_queue, s.idle = ["paid"], 0
    g = _game(monkeypatch, tmp_path, s, "late-reset", Timing="fast", MapReset="1")
    found = g.found
    g.found = lambda p, variation=None: p is atlas.MR_RESET_AVAILABLE or found(p, variation)
    at_reset, pressed = [], []
    move_to, click = g.move_to, g.click

    def move(p):
        if p is atlas.MR_RESET_BUTTON:
            s.tick()
            at_reset.append(s.popup)
            pressed.append(1)
        move_to(p)

    g.move_to = move
    g.click = lambda: None if pressed else click()
    map_redeem.map_redeem(g)
    assert at_reset == [None] and s.closed_x == 1, (at_reset, s.events)


def test_the_look_is_dropped_after_the_final_alignment(monkeypatch, tmp_path):
    """Detection mode, a mission found only once the map was moved, and the final alignment
    moving the map (modelled: 120 px): the campaign's check must not compare the screen
    with the look taken before the last click, which would stop the visit."""
    s = screens.Scene(1920, 1009)
    s.queue, s.idle = ["start", "start"], 4
    calls = []

    def find(g):  # a second mission shows in place once the first runs (the second round)
        if s.map_offset:
            return []
        calls.append(1)
        return [(800, 500)] if len(calls) == 1 else [(800, 500), (900, 600)]

    monkeypatch.setattr(map_detect, "find_missions", find)

    def align(g):
        s.map_offset += 120

    monkeypatch.setattr(map_align, "align_map", align)
    claimed = []
    monkeypatch.setattr(map_redeem, "claim_campaign", lambda g: claimed.append(1))
    g = _game(
        monkeypatch, tmp_path, s, "final-align", Timing="fast", MapMode="detect", Campaign="1"
    )
    map_redeem.map_redeem(g)
    assert claimed == [1] and s.faults == []
    assert not any("cannot read" in line for line in g.lines), g.lines
