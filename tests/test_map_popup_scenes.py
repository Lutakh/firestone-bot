"""The map section's popups at every client shape: the real map_start / map_redeem code run
through the real Game on a scene of real 9.1.3a crops that answers clicks like the game
(tests/screens.py). The popups were clicked at fixed points through guessed anchors: below a
client aspect of 1.6 the Start was missed and the bot "goes to the next mission, which it also
doesn't start" (a player, 2026-10-30)."""

from __future__ import annotations

import pytest

from firestone_bot.features import map_align, map_detect, map_redeem, map_start
from firestone_bot.features.map_close import STUCK_LINE
from firestone_bot.game import StepAborted
from firestone_bot.vision import atlas
from tests import screens


def _game(monkeypatch, tmp_path, scene, name, **settings):
    """A SceneGame with its own map memory (`name`: a folder under tmp_path)."""
    folder = tmp_path / name
    folder.mkdir(exist_ok=True)
    settings.setdefault("Timing", "safe")
    return screens.scene_game(monkeypatch, scene, folder, **settings)


def _detect(monkeypatch, scene, points):
    """Detection mode: `points` (logical) are the missions found with the map in place."""
    monkeypatch.setattr(
        map_detect, "find_missions", lambda g: list(points) if scene.map_offset == 0 else []
    )
    monkeypatch.setattr(map_align, "align_map", lambda g: None)


def _start_two(monkeypatch, tmp_path, scene, **settings):
    """Two missions started, then no idle squad left."""
    scene.queue, scene.idle = ["start", "start"], 4
    g = _game(monkeypatch, tmp_path, scene, "start", **settings)
    assert map_start.map_start(g) is True
    presses = scene.presses("start", "start")
    assert scene.started == 2 and len(presses) == 2, scene.events
    # each Start pressed well inside the button, and nothing else pressed on the popup
    assert scene.presses("start", "start", inset=0.1) == presses == scene.clicks_on("start")
    assert g.diagnostics.count("mission-start-popup.png") == 1
    assert scene.faults == []
    return g


def _list(monkeypatch, tmp_path, scene, queue, **settings):
    """The mission check on the list's first mission(s)."""
    scene.list_queue = list(queue)
    g = _game(monkeypatch, tmp_path, scene, "list-" + queue[0], **settings)
    assert map_redeem._checks(g) is True
    assert scene.faults == []
    return g


def _closed_by_x(scene, popup):
    clicks = scene.clicks_on(popup)
    assert scene.closed_x == 1 and len(clicks) == 1, scene.events
    assert scene.presses("x", popup) == clicks


@pytest.mark.parametrize(("w", "h", "placement"), screens.cases())
def test_the_map_popups_at_every_shape(monkeypatch, tmp_path, w, h, placement):
    def scene():
        return screens.Scene(w, h, placement)

    # coordinates mode (the default): Start pressed inside it, the mission counted
    _start_two(monkeypatch, tmp_path, scene())

    # more than 3 minutes left: the paid Speed up and the Cancel never pressed, closed by X
    s = scene()
    g = _list(monkeypatch, tmp_path, s, ["paid"])
    _closed_by_x(s, "paid")
    assert "Mission Check: Mission has more than 3 minutes remaining" in g.lines
    assert g.diagnostics == ["mission-in-progress.png"]

    # under 3 minutes: the free speed-up pressed, then the Mission Rewards' Okay (its purple
    # mystery box is no price)
    s = scene()
    g = _list(monkeypatch, tmp_path, s, ["free"])
    assert s.speed_ups == 1 and len(s.presses("free", "free", inset=0.1)) == 1
    assert s.claimed == 1 and len(s.presses("okay", "rewards", inset=0.1)) == 1
    assert g.vars[map_redeem.GEM_SEEN] == 0 and not g.beats

    # a mission already complete: its Mission Rewards confirmed
    s = scene()
    g = _list(monkeypatch, tmp_path, s, ["rewards"])
    assert s.claimed == 1 and len(s.presses("okay", "rewards", inset=0.1)) == 1
    assert "Mission Check: Mission is already complete!" in g.lines

    # a popup the bot does not know: closed by its X, nothing of it pressed, captured
    s = scene()
    g = _list(monkeypatch, tmp_path, s, ["start-dark"])
    _closed_by_x(s, "start-dark")
    assert g.diagnostics == ["mission-dialog-unknown.png"]


def test_a_client_inside_a_larger_screen(monkeypatch, tmp_path):
    """A window away from the screen's corner: every box is clicked in screen px."""
    (w, h), origin, screen = screens.OFFSET
    _start_two(monkeypatch, tmp_path, screens.Scene(w, h, origin=origin, screen=screen))
    s = screens.Scene(w, h, origin=origin, screen=screen)
    _list(monkeypatch, tmp_path, s, ["free"])
    assert s.speed_ups == 1 and s.claimed == 1


@pytest.mark.parametrize("shape", [(1920, 1009, "centre"), (1600, 1200, "top")])
def test_detection_mode_presses_the_start_inside(monkeypatch, tmp_path, shape):
    s = screens.Scene(*shape)
    _detect(monkeypatch, s, [(800, 500), (1100, 600)])
    _start_two(monkeypatch, tmp_path, s, MapMode="detect")


def test_the_owners_setup_in_fast_timing(monkeypatch, tmp_path):
    """1920x1009, detection mode, fast timing: screen-change waits and still-screen waits."""
    s = screens.Scene(1920, 1009)
    _detect(monkeypatch, s, [(800, 500), (1100, 600)])
    _start_two(monkeypatch, tmp_path, s, MapMode="detect", Timing="fast")
    s = screens.Scene(1920, 1009)
    _list(monkeypatch, tmp_path, s, ["free", "rewards"], Timing="fast")
    assert s.speed_ups == 1 and s.claimed == 2


@pytest.mark.parametrize("shape", [(1920, 1009, "centre"), (1280, 1024, "top")])
def test_a_start_button_showing_a_gem_is_never_pressed(monkeypatch, tmp_path, shape):
    """Green is no proof of free (gem audit, 2026-10-22): the popup is closed unstarted."""
    s = screens.Scene(*shape)
    s.queue, s.idle = ["start-gem"], 4
    _detect(monkeypatch, s, [(800, 500)])
    g = _game(monkeypatch, tmp_path, s, "gem", MapMode="detect")
    assert map_start.map_start(g) is True
    assert s.started == 0 and s.faults == []
    _closed_by_x(s, "start-gem")
    assert "Mission Start: the Start button shows a gem, not clicked" in g.lines
    assert "mission-start-gem.png" in g.diagnostics


def test_a_popup_the_bot_does_not_know_is_closed_and_captured(monkeypatch, tmp_path):
    """A mission click that opens anything but a start popup with its free Start (here the
    Start drawn dark): closed by its X, nothing of it pressed, one capture a run."""
    s = screens.Scene(1680, 1050, "top")
    s.queue, s.idle = ["start-dark", "paid"], 4
    _detect(monkeypatch, s, [(800, 500), (1100, 600)])
    g = _game(monkeypatch, tmp_path, s, "unknown", MapMode="detect")
    assert map_start.map_start(g) is True
    assert s.started == 0 and s.faults == [] and s.closed_x == 2
    assert s.presses("x", "start-dark") == s.clicks_on("start-dark")
    assert s.presses("x", "paid") == s.clicks_on("paid")
    assert g.diagnostics.count("mission-dialog-unknown.png") == 1


def test_a_start_that_does_not_take_is_not_counted(monkeypatch, tmp_path):
    """The popup still there after Start is closed by its X: no mission started (a popup
    closed from outside was counted as a start, audit 2026-10-30)."""
    s = screens.Scene(1920, 1009)
    s.queue, s.idle = ["start-deaf"], 4
    _detect(monkeypatch, s, [(800, 500)])
    g = _game(monkeypatch, tmp_path, s, "deaf", MapMode="detect")
    assert map_start.map_start(g) is True
    assert s.started == 0 and s.faults == [] and s.closed_x == 1
    assert len(s.presses("dead", "start-deaf", inset=0.1)) == 1
    assert "Mission Start: the popup stayed open after Start; closed" in g.lines
    assert not any("mission(s) started" in line for line in g.lines)


def test_the_bench_sees_a_paid_press_on_a_popup_that_takes_no_click():
    """A popup stuck open still records a press on its paid button, its Cancel or a reward
    (nothing else changes): the taps on a popup that stays are checked too."""
    s = screens.Scene(1920, 1009)
    s.popup, s.stuck = "paid", True
    for role in ("paid", "cancel", "tile"):
        b = s.part(role)[0]
        s.press(round((b.x1 + b.x2) / 2), round((b.y1 + b.y2) / 2))
    assert len(s.faults) == 3 and s.popup == "paid"
    x = s.part("x")[0]
    s.press(round((x.x1 + x.x2) / 2), round((x.y1 + x.y2) / 2))
    assert s.popup == "paid" and s.closed_x == 0 and len(s.faults) == 3


@pytest.mark.parametrize("mode", ["coordinates", "detect"])
def test_a_start_popup_that_stays_stops_the_map_section(monkeypatch, tmp_path, mode):
    """A Start that does not close the popup: it is not counted, its X is tried, and when it
    stays nothing more is clicked on the map (its Complete instantly costs gems): the taps
    on it are its Start, its X and beside it, never its paid button (the bench records a
    paid press on a popup that takes no click)."""
    s = screens.Scene(1920, 1009)
    s.queue, s.idle, s.stuck = ["start", "start", "start"], 6, True
    _detect(monkeypatch, s, [(800, 500), (1100, 600), (600, 700)])
    g = _game(monkeypatch, tmp_path, s, "stuck", MapMode=mode)
    assert map_start.map_start(g) is False
    assert s.started == 0 and s.faults == []
    maps = [e for e in s.events if e[0] == "map"]
    assert len(maps) == 1  # the click that opened it, none after
    start, x, beside = s.clicks_on("start")
    assert s.presses("start", "start") == [start] and s.presses("x", "start") == [x]
    assert not s.panel("start").contains(*beside)
    assert "Mission Start: the popup stays open after Start; map search stopped" in g.lines
    assert "mission-start-stuck.png" in g.diagnostics


def test_an_in_progress_popup_that_stays_stops_the_detection_search(monkeypatch, tmp_path):
    """Detection mode (the owner's), a mission click opens an in-progress popup that takes no
    click: its X, then beside it; nothing more is clicked on the map (its paid Speed up and
    its Cancel lie where map points fall)."""
    s = screens.Scene(1920, 1009)
    s.queue, s.idle, s.stuck = ["paid", "start"], 4, True
    _detect(monkeypatch, s, [(800, 500), (1100, 600)])
    g = _game(monkeypatch, tmp_path, s, "stuck-paid", MapMode="detect")
    assert map_start.map_start(g) is False
    assert s.faults == [] and len([e for e in s.events if e[0] == "map"]) == 1
    x, beside = s.clicks_on("paid")
    assert s.presses("x", "paid") == [x] and not s.panel("paid").contains(*beside)
    assert g.lines.count(STUCK_LINE) == 1 and "mission-popup-stuck.png" in g.diagnostics


@pytest.mark.parametrize("shape", [(1920, 1009, "centre"), (1600, 1200, "top")])
def test_a_popup_whose_x_takes_no_tap_is_closed_beside_it(monkeypatch, tmp_path, shape):
    """The X found and tapped does nothing: the second tap is beside the panel, never on its
    paid Speed up or its Cancel."""
    s = screens.Scene(*shape)
    g = _list(monkeypatch, tmp_path, s, ["paid-deadx"])
    x, beside = s.clicks_on("paid-deadx")
    assert s.presses("deadx", "paid-deadx") == [x] and not s.panel("paid-deadx").contains(*beside)
    assert s.closed_out == 1 and s.closed_x == 0 and s.speed_ups == 0
    assert "Mission Check: Mission has more than 3 minutes remaining" in g.lines


def test_a_popup_left_open_is_closed_before_any_map_click(monkeypatch, tmp_path):
    """A popup left open (in progress, its paid Speed up and Cancel where map points fall)
    is closed by its X before the map is searched or clicked: a popup's timer was taken for
    a mission label (audit 2026-10-30)."""
    s = screens.Scene(1920, 1009)
    s.popup, s.queue, s.idle = "paid", ["start"], 2
    searched = []
    monkeypatch.setattr(map_align, "align_map", lambda g: None)
    monkeypatch.setattr(
        map_detect, "find_missions", lambda g: searched.append(s.popup) or [(800, 500)]
    )
    g = _game(monkeypatch, tmp_path, s, "left", MapMode="detect")
    assert map_start.map_start(g) is True
    assert searched[0] is None and s.started == 1 and s.faults == []
    _closed_by_x(s, "paid")
    assert "Map: a mission popup (in progress) is open before a map click, closing it" in g.lines


def test_a_popup_that_cannot_be_closed_stops_the_map_section(monkeypatch, tmp_path):
    """Neither the Okay nor a tap beside the dialog closes it: said once, captured, and the map
    section ends there (no mission started, no campaign)."""
    s = screens.Scene(1920, 1009)
    s.list_queue, s.stuck, s.idle = ["rewards"], True, 4
    s.queue = ["start"]
    g = _game(monkeypatch, tmp_path, s, "stuck-rewards", Campaign="1")
    with pytest.raises(StepAborted):  # the runner goes back to the main screen
        map_redeem.map_redeem(g)
    assert [e[0] for e in s.events] == ["list", "screen", "screen", "screen"]
    assert g.lines.count(STUCK_LINE) == 1
    assert "mission-popup-stuck.png" in g.diagnostics
    assert s.started == 0 and s.faults == []
    assert not any("open before a map click" in line for line in g.lines)  # stopped at once


def test_an_in_progress_popup_that_stays_after_the_list_tap_stops_the_visit(monkeypatch, tmp_path):
    """The list's paid in-progress popup takes no click: its X, then beside it, then the
    visit stops there (StepAborted), before the troops."""
    s = screens.Scene(1920, 1009)
    s.list_queue, s.stuck, s.queue, s.idle = ["paid"], True, ["start"], 4
    g = _game(monkeypatch, tmp_path, s, "stuck-list-paid")
    with pytest.raises(StepAborted, match=map_redeem.STUCK):
        map_redeem.map_redeem(g)
    assert [e[0] for e in s.events] == ["list", "screen", "screen"] and s.faults == []
    assert g.lines.count(STUCK_LINE) == 1
    assert not any(line.startswith("Troop Check") for line in g.lines)


class _StuckAfterFree(screens.Scene):
    """The free speed-up works, what it opens takes no click."""

    def _open(self, popup):
        super()._open(popup)
        self.stuck = popup is not None and popup == self.after_free


def test_the_mission_rewards_that_stay_after_a_speed_up_stop_the_visit(monkeypatch, tmp_path):
    """The free speed-up opens the Mission Rewards, whose Okay and the taps beside it do
    nothing: the visit stops there (StepAborted), nothing else tried on the map."""
    s = _StuckAfterFree(1920, 1009)
    s.list_queue, s.queue, s.idle = ["free"], ["start"], 4
    g = _game(monkeypatch, tmp_path, s, "stuck-after-free")
    with pytest.raises(StepAborted, match=map_redeem.STUCK):
        map_redeem.map_redeem(g)
    assert s.speed_ups == 1 and s.claimed == 0 and s.faults == []
    assert [e[0] for e in s.events] == ["list", "screen", "screen", "screen", "screen"]
    assert g.lines.count(STUCK_LINE) == 1
    assert not any("open before a map click" in line for line in g.lines)


def test_a_gem_after_a_speed_up_is_never_confirmed(monkeypatch, tmp_path):
    """Second line of defence: a gem where the dialog's price would show (its Okay's row)
    means the click was not free. Never confirmed; the second time in a row free speed-ups
    stop for the run, with an important heartbeat; the next visit does not press it."""
    s = screens.Scene(1920, 1009)
    s.after_free = "rewards-priced"
    g = _game(monkeypatch, tmp_path, s, "priced")
    for visit in (1, 2, 3):
        s.list_queue = ["free"]
        assert map_redeem._checks(g) is True
        assert s.faults == [] and s.claimed == 0
        assert s.speed_ups == min(visit, 2)
        assert s.popup is None
    line = "Mission Check: a gem showed after a speed-up click: not confirmed"
    assert g.lines.count(line) == 1
    assert g.vars[map_redeem.PAID_OFF] == 1
    beat = "Map missions: a gem showed after a speed-up click, nothing confirmed (see the log)"
    assert g.beats == [(beat, True)]
    assert g.diagnostics.count("mission-gem-dialog.png") == 2
    assert "Mission Check: the speed-up button costs gems, not clicked" in g.lines
    assert "mission-paid-speed-up.png" in g.diagnostics


def test_the_mystery_box_rewards_are_confirmed_every_time(monkeypatch, tmp_path):
    """World domination (2026-10-29/30): the purple reward read as a gem price; the second
    time in a row free speed-ups were off for the run (the owner's bot, report G8N62Y)."""
    s = screens.Scene(1920, 1009)
    g = _list(monkeypatch, tmp_path, s, ["free"] * map_redeem.CHECKS_CAP)
    assert s.speed_ups == s.claimed == map_redeem.CHECKS_CAP
    assert f"MapRedeem: safety cap of {map_redeem.CHECKS_CAP} iterations reached" in g.lines
    assert not g.vars.get(map_redeem.PAID_OFF) and not g.beats
    assert not any("a gem showed" in line for line in g.lines)


def test_the_in_progress_popup_is_captured_once_a_run(monkeypatch, tmp_path):
    """Game 9.1.3a's in-progress popup at the players' shapes: one capture a run."""
    s = screens.Scene(1920, 1009)
    g = _game(monkeypatch, tmp_path, s, "twice")
    for _ in range(2):
        s.list_queue = ["paid"]
        assert map_redeem._checks(g) is True
    assert s.closed_x == 2 and s.faults == []
    assert g.diagnostics == ["mission-in-progress.png"]
    assert g.lines.count("Mission Check: Mission has more than 3 minutes remaining") == 2


@pytest.mark.parametrize("look", ["rewards-two", "rewards-narrow"])
def test_another_one_button_dialog_is_not_confirmed(monkeypatch, tmp_path, look):
    """Only the Mission Rewards' own Okay is pressed: a second green button beside it is a
    choice, a narrower one another dialog. Closed beside it (no X), never pressed."""
    s = screens.Scene(1600, 1200, "top")
    g = _list(monkeypatch, tmp_path, s, [look])
    assert s.claimed == 0 and s.closed_out == 1
    assert g.diagnostics == ["mission-dialog-unknown.png"]


def test_a_rewards_look_with_an_x_is_closed_by_it(monkeypatch, tmp_path):
    """The Mission Rewards dialog has no X: one that has is another dialog, its Okay never
    pressed."""
    s = screens.Scene(3024, 1964, "centre")
    g = _list(monkeypatch, tmp_path, s, ["rewards-x"])
    assert s.claimed == 0
    _closed_by_x(s, "rewards-x")
    assert g.diagnostics == ["mission-dialog-unknown.png"]


@pytest.mark.parametrize("shape", [(1920, 1009, "centre"), (2560, 1080, "centre")])
def test_a_gem_on_the_free_layout_is_a_price(monkeypatch, tmp_path, shape):
    """Orange is no proof of free (three users' missions completed with gems after a game
    update, 2026-10-22): a gem in the orange button, whatever its layout, keeps it unpressed."""
    s = screens.Scene(*shape)
    g = _list(monkeypatch, tmp_path, s, ["free-gem"])
    assert s.speed_ups == 0
    _closed_by_x(s, "free-gem")
    assert "Mission Check: Mission has more than 3 minutes remaining" in g.lines


def test_the_brown_label_alone_is_a_price(monkeypatch, tmp_path):
    """The paid Speed up with its gem not seen: its label band says paid, closed by its X."""
    s = screens.Scene(1600, 1200, "top")
    g = _list(monkeypatch, tmp_path, s, ["paid-label-only"])
    assert s.speed_ups == 0
    _closed_by_x(s, "paid-label-only")
    assert "Mission Check: Mission has more than 3 minutes remaining" in g.lines


def test_no_price_beside_a_red_cancel_is_never_pressed(monkeypatch, tmp_path):
    """Free is the grey Cancel's layout: a red Cancel beside an orange that shows no price is
    a price the reader misses (a game update changed the paid button once, 2026-10-22)."""
    s = screens.Scene(1920, 1009)
    g = _list(monkeypatch, tmp_path, s, ["paid-plain"])
    assert s.speed_ups == 0
    _closed_by_x(s, "paid-plain")
    line = "Mission Check: the speed-up shows no price beside a red Cancel, not clicked"
    assert line in g.lines and g.diagnostics == ["mission-speed-up-unpriced.png"]


@pytest.mark.parametrize(
    "look",
    ["rewards-three", "rewards-cancel", "rewards-hollow", "rewards-offcentre", "rewards-tall"],
)
def test_a_one_green_dialog_that_is_not_the_mission_rewards(monkeypatch, tmp_path, look):
    """Orange buttons or a Cancel beside the green, a green frame round nothing, a green off
    the panel's centre or taller than the Okay: not the Mission Rewards, closed beside it (no
    X), its green never pressed."""
    s = screens.Scene(1920, 1009)
    g = _list(monkeypatch, tmp_path, s, [look])
    assert s.claimed == 0 and s.closed_out == 1 and len(s.clicks_on(look)) == 1
    assert g.diagnostics == ["mission-dialog-unknown.png"]


@pytest.mark.parametrize("shape", [(1920, 1009, "centre"), (1280, 1024, "top")])
def test_a_start_popup_whose_orange_shows_no_price_is_not_started(monkeypatch, tmp_path, shape):
    """A Complete instantly with no price at all (never captured: a mission under 3 minutes
    might show the in-progress popup's "Free", but a dialog pricing its green elsewhere would
    look the same, second review of 2026-10-31): closed by its X unstarted, said, and
    captured once so that a player's report shows what it is."""
    s = screens.Scene(*shape)
    s.queue, s.idle = ["start-unpriced"], 2
    _detect(monkeypatch, s, [(800, 500)])
    g = _game(monkeypatch, tmp_path, s, "unpriced", MapMode="detect")
    assert map_start.map_start(g) is True
    assert s.started == 0 and s.faults == []
    _closed_by_x(s, "start-unpriced")
    assert "Mission Start: Complete instantly shows no price; not started" in g.lines
    assert g.diagnostics.count("mission-start-unpriced.png") == 1


UNPRICED = "mission-start-unpriced.png"
UNKNOWN = "mission-dialog-unknown.png"


@pytest.mark.parametrize(
    ("look", "by_x", "capture"),
    [
        ("start-unpriced-nox", False, UNPRICED),
        ("start-unpriced-wide", True, UNPRICED),
        ("start-label-only", True, UNKNOWN),
        ("start-swapped", True, UNKNOWN),
        ("start-no-orange", True, UNKNOWN),
        ("start-stacked", True, UNKNOWN),
        ("start-three", True, UNKNOWN),
        ("start-tall", True, UNKNOWN),
        ("paid-green-cancel", True, UNKNOWN),
    ],
)
def test_a_green_beside_an_orange_the_bot_does_not_know(monkeypatch, tmp_path, look, by_x, capture):
    """An unpriced orange without the popup's X or beside a green wider than a Start, a price
    label without its gem, an orange with a gem left of the green, a green with no orange, a
    green out of the orange's row, two oranges, a green too tall for a button, a green and a
    Cancel: not a start popup, closed (by its X, else beside it), nothing of it pressed."""
    s = screens.Scene(1920, 1009)
    s.queue, s.idle = [look], 2
    _detect(monkeypatch, s, [(800, 500)])
    g = _game(monkeypatch, tmp_path, s, "green-" + look, MapMode="detect")
    assert map_start.map_start(g) is True
    assert s.started == 0 and s.faults == []
    if by_x:
        _closed_by_x(s, look)
    else:
        assert s.closed_out == 1 and len(s.clicks_on(look)) == 1
    assert g.diagnostics.count(capture) == 1


@pytest.mark.parametrize("look", ["rewards-priced", "rewards-priced-under"])
def test_a_priced_okay_after_the_list_tap_is_never_pressed(monkeypatch, tmp_path, look):
    """A Mission Rewards look with a gem in its Okay's row (on the Okay, or just under it),
    opened by the tap on the list (not after a speed-up): never confirmed, closed beside it."""
    s = screens.Scene(1920, 1009)
    g = _list(monkeypatch, tmp_path, s, [look])
    assert s.claimed == 0 and s.closed_out == 1 and len(s.clicks_on(look)) == 1
    assert g.diagnostics == ["mission-dialog-unknown.png"]


@pytest.mark.parametrize("look", ["rewards-x", "free-gem"])
def test_a_gem_in_another_dialog_after_a_speed_up_is_a_gem_met(monkeypatch, tmp_path, look):
    """After the free speed-up, a dialog that is not the Mission Rewards (its look with an X,
    or the in-progress popup with a price) and shows a gem: never confirmed, counted as a gem
    met, closed by its X."""
    s = screens.Scene(1920, 1009)
    s.after_free = look
    g = _list(monkeypatch, tmp_path, s, ["free"])
    assert s.speed_ups == 1 and s.claimed == 0
    _closed_by_x(s, look)
    assert g.vars[map_redeem.GEM_SEEN] == 1 and "mission-gem-dialog.png" in g.diagnostics


def test_a_gem_after_a_speed_up_ends_the_checks(monkeypatch, tmp_path):
    """Goto Troops after a gem (as before 2026-10-31): two missions under 3 minutes in the
    list, one press a visit; the second visit's gem turns free speed-ups off."""
    s = screens.Scene(1920, 1009)
    s.after_free, s.list_queue = "rewards-priced", ["free", "free"]
    g = _game(monkeypatch, tmp_path, s, "gem-twice")
    assert map_redeem._checks(g) is True
    assert s.speed_ups == 1 and s.list_queue == ["free"]
    assert g.vars[map_redeem.GEM_SEEN] == 1 and not g.vars.get(map_redeem.PAID_OFF)
    assert map_redeem._checks(g) is True
    assert s.speed_ups == 2 and g.vars[map_redeem.PAID_OFF] == 1 and len(g.beats) == 1
    assert s.claimed == 0 and s.faults == []


def test_a_visit_without_a_running_mission_goes_on_to_the_troops(monkeypatch, tmp_path):
    """MR_NO_MISSIONS never matches the sea of 9.1.3a: the tap on the list's place opens
    nothing, and the visit goes on to start missions (and to the campaign)."""
    s = screens.Scene(1920, 1009)
    s.queue, s.idle = ["start"], 2
    claimed = []
    monkeypatch.setattr(map_redeem, "claim_campaign", lambda g: claimed.append(1))
    g = _game(monkeypatch, tmp_path, s, "empty", Campaign="1")
    map_redeem.map_redeem(g)
    assert [e[0] for e in s.events][:2] == ["list", "map"]
    assert s.started == 1 and s.faults == [] and claimed == [1]


def test_an_empty_list_the_probe_sees(monkeypatch, tmp_path):
    """A probe that matches an empty list (older versions): no tap on it."""
    s = screens.Scene(1920, 1009)
    s.queue, s.idle, s.no_missions_probe = ["start"], 2, True
    g = _game(monkeypatch, tmp_path, s, "empty-seen")
    map_redeem.map_redeem(g)
    assert [e[0] for e in s.events][:1] == ["map"] and s.started == 1
    assert "Mission Check: No active missions found" in g.lines


def test_a_popup_that_stays_in_the_troops_step_stops_the_visit(monkeypatch, tmp_path):
    """map_start stopped on a start popup that stays: map_redeem raises StepAborted (the
    runner goes back to the main screen), no paid map reset, no campaign under it."""
    s = screens.Scene(1920, 1009)
    s.queue, s.idle, s.stuck = ["start"], 4, True
    claimed = []
    monkeypatch.setattr(map_redeem, "claim_campaign", lambda g: claimed.append(1))
    g = _game(monkeypatch, tmp_path, s, "stuck-troops", Campaign="1", MapReset="1")
    found = g.found
    g.found = lambda p, variation=None: p is atlas.MR_RESET_AVAILABLE or found(p, variation)
    with pytest.raises(StepAborted, match=map_redeem.STUCK):
        map_redeem.map_redeem(g)
    assert claimed == [] and s.faults == [] and s.started == 0
    assert [e[0] for e in s.events if e[0] in ("list", "map")] == ["list", "map"]
    assert "mission-start-stuck.png" in g.diagnostics
