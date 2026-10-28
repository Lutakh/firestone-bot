"""The foreground guard: no click or key while the game window is not in front (Windows).

2026-10-25 17:18 to 00:34: the game could not be brought to the foreground and the bot sent
3,000+ clicks and ~2,000 T presses into whatever window was in front. Every test here runs
on fakes: no Win32 call, no real input (the Win32 tests at the end fake user32 and only run
where the Win32 backend can be imported)."""

from __future__ import annotations

import ctypes
import logging
import os
import sys
import threading
from types import SimpleNamespace

import numpy as np
import pytest

from firestone_bot import foreground
from firestone_bot import game as game_mod
from firestone_bot import runner as runner_mod
from firestone_bot.features import game_launch
from firestone_bot.foreground import ForegroundGuard
from firestone_bot.game import BotStopped, Game, GameNotInFront
from firestone_bot.inputguard import UserInterrupted
from firestone_bot.platform.types import GameWindowNotFound, Rect, WindowInfo, same_window
from firestone_bot.settings import Settings
from firestone_bot.vision.viewport import Viewport

GAME_PID = 5150


def _win(handle=0x1A2B, w=1920, h=1009, pid=GAME_PID) -> WindowInfo:
    return WindowInfo(
        handle=handle,
        title="Firestone",
        pid=pid,
        exe="Firestone.exe",
        outer=Rect(0, 0, w, h + 31),
        client=Rect(0, 23, w, h),
        maximized=True,
        fullscreen=False,
    )


class FakeApi:
    """The platform side: whether the game is in front, activations granted in turn."""

    def __init__(
        self,
        front=False,
        grants=(),
        owner=("chrome.exe", "Chrome_WidgetWin_1", 4242),
        hung=False,
    ):
        self.front = front
        self.grants = list(grants)  # True: that activation works; missing: refused
        self.activations = 0
        self.owner = owner
        self.hung = hung

    def is_foreground(self, win):
        return self.front

    def activate(self, win):
        self.activations += 1
        if self.grants and self.grants.pop(0):
            self.front = True
        return self.front

    def foreground_owner(self):
        return self.owner

    def is_hung(self, win):
        return self.hung


class FakeGame:
    def __init__(self, windows=None, present=True):
        self.window = _win()
        self.windows = list(windows or [])  # what refresh_window finds next (then the last)
        self.present = present
        self.refreshes = 0
        self.slept: list[float] = []
        self.lines: list[str] = []
        self.beats: list[tuple[str, bool]] = []
        self.captures: list[str] = []
        self.blocks: list[int] = []
        self.vars: dict = {}

    def refresh_window(self):
        self.refreshes += 1
        if not self.present:
            raise GameWindowNotFound("Firestone process not running")
        if self.windows:
            self.window = self.windows.pop(0)
        return self.window

    def sleep(self, ms):
        self.slept.append(ms)

    def status(self, text):
        self.lines.append(text)

    def heartbeat(self, msg, is_stop=False, important=False):
        self.beats.append((msg, important))

    def save_diagnostic(self, name, block=1):
        self.captures.append(name)
        self.blocks.append(block)


@pytest.fixture
def clock(monkeypatch):
    """The guard's clock only (Game.sleep keeps the real one)."""
    now = [1000.0]
    monkeypatch.setattr(foreground, "time", SimpleNamespace(monotonic=lambda: now[0]))
    return now


# -- the guard ------------------------------------------------------------------------------
def test_game_in_front_costs_one_call_and_nothing_else():
    api, g = FakeApi(front=True), FakeGame()
    ForegroundGuard(api).check(g)
    assert g.slept == [] and g.refreshes == 0 and api.activations == 0 and g.lines == []


def test_a_refused_activation_is_tried_again_and_the_input_goes_on(clock):
    api, g = FakeApi(grants=[False, True]), FakeGame()
    guard = ForegroundGuard(api)
    guard.check(g)
    assert api.activations == 2
    assert g.slept == [0, ForegroundGuard.RETRY_MS]  # the mouse guard's turn, one retry
    assert g.lines == [] and g.captures == [] and guard.since is None


def test_a_game_never_in_front_gets_no_input_and_one_line_per_episode(clock):
    api, g = FakeApi(), FakeGame()
    guard = ForegroundGuard(api)
    with pytest.raises(GameNotInFront) as e:
        guard.check(g)
    assert not e.value.gone
    assert api.activations == ForegroundGuard.TRIES
    assert len(g.lines) == 1
    assert g.lines[0].startswith("Paused: the game window is not in front")
    assert "chrome.exe, window class Chrome_WidgetWin_1" in g.lines[0]
    assert g.captures == [ForegroundGuard.CAPTURE]
    assert g.beats == []  # a blip of a few seconds pings nobody
    clock[0] += 5
    with pytest.raises(GameNotInFront):
        guard.check(g)
    assert guard.poll(g) == foreground.BACK
    assert len(g.lines) == 1 and len(g.captures) == 1  # the same episode


def test_the_important_heartbeat_waits_for_the_episode_to_last(clock):
    api, g = FakeApi(), FakeGame()
    guard = ForegroundGuard(api)
    with pytest.raises(GameNotInFront):
        guard.check(g)
    clock[0] += ForegroundGuard.HEARTBEAT_AFTER_S - 1
    guard.poll(g)
    assert g.beats == []
    clock[0] += 2
    guard.poll(g)
    clock[0] += 3600
    guard.poll(g)
    assert len(g.beats) == 1 and g.beats[0][1] is True  # important, once


def test_the_game_back_in_front_ends_the_episode(clock):
    api, g = FakeApi(), FakeGame()
    guard = ForegroundGuard(api)
    with pytest.raises(GameNotInFront):
        guard.check(g)
    clock[0] += 3600 + 125
    guard.poll(g)  # the important heartbeat
    api.front = True
    assert guard.poll(g) == foreground.FRONT
    assert g.lines[-1] == "The game window is in front again after 1h02m; going on"
    assert g.beats[-1] == ("Game window in front again, the bot goes on", False)
    assert guard.since is None
    # the next refusal is a new episode, said again
    api.front = False
    with pytest.raises(GameNotInFront):
        guard.check(g)
    assert len(g.lines) == 3 and len(g.captures) == 2


def test_a_short_episode_ends_without_a_heartbeat(clock):
    api, g = FakeApi(), FakeGame()
    guard = ForegroundGuard(api)
    with pytest.raises(GameNotInFront):
        guard.check(g)
    clock[0] += 7
    api.front = True
    guard.check(g)  # the fast path ends it too
    assert g.lines[-1] == "The game window is in front again after 7s; going on"
    assert g.beats == []


def test_a_gone_window_raises_without_an_episode():
    api, g = FakeApi(), FakeGame(present=False)
    guard = ForegroundGuard(api)
    with pytest.raises(GameNotInFront) as e:
        guard.check(g)
    assert e.value.gone
    assert g.lines == [] and g.captures == [] and guard.since is None
    assert guard.poll(g) == foreground.GONE


def test_a_minimised_game_is_restored_and_its_rect_read_again():
    api = FakeApi(grants=[True])
    g = FakeGame(windows=[_win(w=0, h=0), _win()])
    ForegroundGuard(api).check(g)
    assert g.refreshes == 2 and 500 in g.slept and g.window.client.w == 1920


def test_the_relaunched_game_is_found_by_its_new_handle():
    api = FakeApi(grants=[True])
    g = FakeGame(windows=[_win(handle=0x9999)])
    ForegroundGuard(api).check(g)
    assert g.window.handle == 0x9999


def test_stop_and_the_mouse_guard_come_before_any_activation():
    api, g = FakeApi(), FakeGame()

    def stopped(ms):
        raise BotStopped

    g.sleep = stopped
    with pytest.raises(BotStopped):
        ForegroundGuard(api).check(g)
    assert api.activations == 0


@pytest.mark.parametrize(
    "owner, expected",
    [
        (("", "", 0), "no window has the foreground: a locked session or a system prompt?"),
        (("Firestone.exe", "#32770", GAME_PID), "a window of the game itself"),
        (("python.exe", "TkTopLevel", os.getpid()), "a window of the bot itself"),
        (("", "Ghost", 77), "in front: an unknown process, window class Ghost"),
    ],
)
def test_what_holds_the_foreground_is_named(owner, expected, clock):
    g = FakeGame()
    with pytest.raises(GameNotInFront):
        ForegroundGuard(FakeApi(owner=owner)).check(g)
    assert expected in g.lines[0]


def test_an_unreadable_holder_does_not_stop_the_guard(clock):
    api, g = FakeApi(), FakeGame()

    def broken():
        raise OSError("access denied")

    api.foreground_owner = broken
    with pytest.raises(GameNotInFront):
        ForegroundGuard(api).check(g)
    assert "in front: unknown" in g.lines[0]


def test_reset_forgets_an_episode_of_a_stopped_run(clock):
    api, g = FakeApi(), FakeGame()
    guard = ForegroundGuard(api)
    with pytest.raises(GameNotInFront):
        guard.check(g)
    guard.reset()
    api.front = True
    guard.check(g)
    assert len(g.lines) == 1  # no "in front again" for an episode of another run


# -- Game: every injected event is checked first ------------------------------------------
class RecordingGuard:
    def __init__(self, refuse=False):
        self.refuse = refuse
        self.calls = 0

    def check(self, g):
        self.calls += 1
        if self.refuse:
            raise GameNotInFront("test")


@pytest.fixture
def live_game(monkeypatch):
    s = Settings()
    s.set("Timing", "safe")
    g = Game(s, time_scale=0.0001)
    g.window = _win()
    g.vp = Viewport(g.window.client)
    sent: list[tuple] = []
    fake_inp = SimpleNamespace(
        move=lambda x, y: sent.append(("move", x, y)),
        click=lambda: sent.append(("click",)),
        key=lambda k: sent.append(("key", k)),
        key_down=lambda k: sent.append(("key_down", k)),
        key_up=lambda k: sent.append(("key_up", k)),
        wheel=lambda n, interval=0: sent.append(("wheel", n)),
        drag=lambda *a: sent.append(("drag",) + a),
    )
    monkeypatch.setattr(game_mod, "inp", fake_inp)
    return g, sent


def _every_event(g):
    g.move(100, 100)
    g.click()
    g.move_screen(5, 5)
    g.click_screen(6, 6)
    g.drag(100, 100, 200, 200)
    g.key("t")
    g.key_down("left")
    g.wheel(-2)


def test_every_injected_event_is_checked_before_it_is_sent(live_game):
    g, sent = live_game
    g.front_guard = guard = RecordingGuard()
    _every_event(g)
    # move, click, move_screen, click_screen, drag, key, key_down, then one per wheel notch
    assert guard.calls == 9
    assert [e[0] for e in sent] == [
        "move", "click", "move", "move", "click", "drag", "key", "key_down", "wheel", "wheel"
    ]  # fmt: skip


@pytest.mark.parametrize(
    "event",
    [
        lambda g: g.move(100, 100),
        lambda g: g.click(),
        lambda g: g.move_screen(5, 5),
        lambda g: g.click_screen(6, 6),
        lambda g: g.drag(100, 100, 200, 200),
        lambda g: g.key("t"),
        lambda g: g.key_down("left"),
        lambda g: g.wheel(-3),
        lambda g: g.tap_xy(100, 100),
    ],
)
def test_a_refused_check_sends_nothing(live_game, event):
    g, sent = live_game
    g.front_guard = RecordingGuard(refuse=True)
    with pytest.raises(GameNotInFront):
        event(g)
    assert sent == []


def test_a_key_held_down_always_comes_up(live_game):
    g, sent = live_game
    g.front_guard = RecordingGuard(refuse=True)
    g.key_up("left")
    assert sent == [("key_up", "left")]


def test_a_dry_run_never_checks(live_game):
    g, sent = live_game
    g.dry_run = True
    g.front_guard = guard = RecordingGuard(refuse=True)
    _every_event(g)
    assert guard.calls == 0 and sent == []


def test_no_guard_no_check(live_game):
    g, sent = live_game
    _every_event(g)  # macOS, Linux, the tools: as before
    assert len(sent) == 10


def test_focus_warns_only_without_a_guard(monkeypatch, caplog):
    g = Game(Settings(), time_scale=0.0001)
    monkeypatch.setattr(game_mod, "find_game_window", lambda: _win())
    monkeypatch.setattr(game_mod, "activate", lambda win: False)
    with caplog.at_level(logging.WARNING, logger="firestone_bot"):
        g.focus()
        assert "could not be brought to the foreground" in caplog.text
        caplog.clear()
        g.front_guard = RecordingGuard()
        g.focus()  # the guard reports it, once per episode
        assert caplog.text == ""


def test_focus_ignores_the_none_of_the_macos_backend(monkeypatch, caplog):
    g = Game(Settings(), time_scale=0.0001)
    monkeypatch.setattr(game_mod, "find_game_window", lambda: _win())
    monkeypatch.setattr(game_mod, "activate", lambda win: None)
    with caplog.at_level(logging.WARNING, logger="firestone_bot"):
        g.focus()
    assert caplog.text == ""


# -- the runner: wait, then a new cycle ------------------------------------------------------
class WaitGame:
    def __init__(self, states, sleep_error=None, restart_helps=True):
        self.front_guard = SimpleNamespace(
            POLL_MS=ForegroundGuard.POLL_MS,
            poll=self._poll,
            restart_helps=lambda g: restart_helps,
        )
        self.states = list(states)
        self.sleep_error = sleep_error
        self.slept: list[float] = []
        self.lines: list[str] = []
        self.vars: dict = {}

    def _poll(self, g):
        return self.states.pop(0)

    def sleep(self, ms):
        self.slept.append(ms)
        if self.sleep_error is not None:
            raise self.sleep_error

    def status(self, text):
        self.lines.append(text)


class FlagSettings:
    def __init__(self, **flags):
        self.flags = flags

    def flag(self, key):
        return self.flags.get(key, False)

    def get(self, key):
        return ""


def _waiting_runner(g, restart=False):
    r = runner_mod.Runner.__new__(runner_mod.Runner)
    r.g = g
    r.settings = FlagSettings(RestartGame=restart)
    r._restart_ms = 6 * 3600000 if restart else 0
    r._last_restart = runner_mod._ms()
    return r


def test_the_wait_ends_by_itself_when_the_game_is_in_front():
    g = WaitGame(["back", "back", "front"])
    assert _waiting_runner(g)._wait_for_front() is True
    assert g.slept == [ForegroundGuard.POLL_MS] * 3


def test_the_wait_ends_when_the_game_is_gone():
    g = WaitGame(["back", "gone"])
    assert _waiting_runner(g)._wait_for_front() is False


def test_a_due_restart_ends_the_wait(monkeypatch):
    monkeypatch.setattr(runner_mod.process, "game_uptime_s", lambda: 7 * 3600)
    g = WaitGame(["back"])
    assert _waiting_runner(g, restart=True)._wait_for_front() is False
    assert g.lines == ["The game restart is due: restarting the game meanwhile"]


POSTPONED = (
    "The game restart is due; it is done once the game is in front (a restart would not "
    "remove what is in front)"
)


def test_a_due_restart_waits_while_another_program_holds_the_front(monkeypatch):
    """2026-10-25 20:38: the restart killed the game, and three relaunches behind the same
    holder never got their start button clicked. A restart that cannot clear the holder
    waits for the game to be in front (the next cycle finds it due), said once."""
    monkeypatch.setattr(runner_mod.process, "game_uptime_s", lambda: 7 * 3600)
    g = WaitGame(["back", "back", "back", "front"], restart_helps=False)
    assert _waiting_runner(g, restart=True)._wait_for_front() is True
    assert g.lines == [POSTPONED]


def test_a_restart_a_feature_asked_for_is_done_meanwhile_when_it_helps(monkeypatch):
    """The chaos rift's stuck Hit button asked for a restart, and the game hung: the wait
    ends for the restart, which clears the ghost window."""
    monkeypatch.setattr(runner_mod.process, "game_uptime_s", lambda: 3600)  # not due
    g = WaitGame(["back"])
    g.vars["restart_requested"] = "the chaos rift Hit button stayed grey"
    assert _waiting_runner(g, restart=True)._wait_for_front() is False
    g = WaitGame(["back", "front"], restart_helps=False)
    g.vars["restart_requested"] = "the chaos rift Hit button stayed grey"
    assert _waiting_runner(g, restart=True)._wait_for_front() is True
    assert g.lines == [POSTPONED]


def test_the_mouse_guard_can_end_the_wait_while_a_restored_game_settles():
    """poll() waits 500 ms (Game.sleep) for a game it restored from the taskbar; a new cycle
    chosen in the mouse guard's pop-up then must end the wait, not the run (it escaped the
    GameNotInFront handler and Runner._run logged "Crashed, see log")."""

    class Restored(FakeGame):
        def __init__(self):
            super().__init__(windows=[_win(w=0, h=0), _win()])
            self.front_guard = ForegroundGuard(FakeApi(grants=[True]))
            self.stop_event = threading.Event()

        def sleep(self, ms):
            self.slept.append(ms)
            if ms == 500:
                raise UserInterrupted("restart")

    g = Restored()
    r = _waiting_runner(g)
    assert r._wait_for_front() is True
    # and through the worker's entry point: the run goes on to a new cycle
    g = Restored()
    r = _waiting_runner(g)
    r.thread, r.on_finished = None, None
    outcomes = iter([GameNotInFront("x"), False])

    def cycle():
        outcome = next(outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    back = []
    r._cycle = cycle
    r._back_to_main_screen = lambda: back.append(1)
    r._run()
    assert back == [1] and "Crashed, see log" not in g.lines


@pytest.mark.parametrize(
    "owner, hung, helps",
    [
        (("chrome.exe", "Chrome_WidgetWin_1", 4242), False, False),  # another program
        (("", "", 0), False, False),  # locked session, UAC prompt
        (("python.exe", "TkTopLevel", os.getpid()), False, False),  # the bot itself
        (("Firestone.exe", "#32770", GAME_PID), False, True),  # a dialog of the game
        (("dwm.exe", "Ghost", 88), True, True),  # the game hung: its ghost in front
    ],
)
def test_a_restart_helps_only_when_the_game_itself_is_in_the_way(owner, hung, helps):
    guard = ForegroundGuard(FakeApi(owner=owner, hung=hung))
    assert guard.restart_helps(FakeGame()) is helps


def test_an_unreadable_holder_lets_the_restart_go_ahead():
    api = FakeApi()

    def broken(win):
        raise OSError("access denied")

    api.is_hung = broken
    assert ForegroundGuard(api).restart_helps(FakeGame()) is True


def test_the_episode_capture_is_coarse(clock):
    g = FakeGame()
    with pytest.raises(GameNotInFront):
        ForegroundGuard(FakeApi()).check(g)
    assert g.captures == [ForegroundGuard.CAPTURE] and g.blocks == [8]  # 1920 px: 240 wide


@pytest.mark.parametrize("width, block", [(1280, 8), (1920, 8), (2560, 10), (3840, 16)])
def test_the_capture_blocks_grow_with_the_client(width, block):
    g = FakeGame()
    g.window = _win(w=width)
    assert ForegroundGuard(FakeApi()).capture_block(g) == block


def test_a_coarse_image_keeps_the_light_and_loses_the_text():
    """Text-like strokes (1 px lines, 2 px apart) over a page: 8 x 8 block means leave one
    flat grey per block, the dim level of a dark layer survives."""
    img = np.full((1009, 1920, 4), 255, np.uint8)
    img[100:300:2, 100:900, :3] = 0  # "text" rows
    small = game_mod.coarse_image(img, 8)
    assert small.shape == (126, 240, 3) and small.dtype == np.uint8
    block = small[13:37, 13:112]  # inside the strokes
    assert block.min() == block.max() == 128  # one flat grey: no stroke can be told apart
    dim = game_mod.coarse_image((img * 0.275).astype(np.uint8), 8)
    assert dim[0, 0, 0] == 70  # a 27.5 % layer reads as such (2026-10-25: white read 70)


class RestartGame(FakeGame):
    def __init__(self, api, dry_run=False):
        super().__init__()
        self.front_guard = ForegroundGuard(api)
        self.dry_run = dry_run


@pytest.mark.parametrize(
    "api, dry_run",
    [
        (FakeApi(front=True), False),  # the game in front
        (FakeApi(grants=[True]), False),  # brought back by the poll
        (FakeApi(hung=True), False),  # a hung game: the restart clears it
        (FakeApi(owner=("Firestone.exe", "#32770", GAME_PID)), False),  # a dialog of the game
        (FakeApi(), True),  # a dry run restarts nothing anyway
    ],
)
def test_a_restart_goes_ahead_when_it_can_end_in_front(api, dry_run, clock):
    _waiting_runner(None)._restart_waits_for_front(RestartGame(api, dry_run), "")


def test_a_restart_goes_ahead_for_a_game_whose_window_is_gone(clock):
    g = RestartGame(FakeApi())
    g.present = False
    _waiting_runner(g)._restart_waits_for_front(g, "")


def test_a_restart_waits_while_another_program_holds_the_front(clock):
    """Review 2026-10-28: the restart of a cycle that started behind another program's window
    (the end-of-cycle park refused, or the window came during the Delay) killed the game,
    and the relaunch's start button could never be clicked. It waits for the game instead,
    and a feature's request is kept for the cycle that finds the game in front."""
    g = RestartGame(FakeApi())
    with pytest.raises(GameNotInFront):
        _waiting_runner(g)._restart_waits_for_front(g, "")
    assert g.lines[0].startswith("Paused: the game window is not in front")
    with pytest.raises(GameNotInFront):
        _waiting_runner(g)._restart_waits_for_front(g, "the chaos rift Hit button stayed grey")
    assert g.vars["restart_requested"] == "the chaos rift Hit button stayed grey"


def test_a_cycle_does_not_restart_the_game_behind_another_window(monkeypatch, clock):
    """The whole start of a cycle: due restart, holder in front, no kill."""

    def restart(game):
        pytest.fail("the game was restarted behind another program's window")

    monkeypatch.setattr(runner_mod.restart_game_routine, "restart_game_routine", restart)
    monkeypatch.setattr(runner_mod.process, "game_uptime_s", lambda: 25 * 3600)
    g = RestartGame(FakeApi())
    r = _waiting_runner(g, restart=True)
    r._last_request = 0
    g.heartbeat = lambda *a, **k: None
    with pytest.raises(GameNotInFront):
        r._cycle()


def test_no_restart_while_waiting_when_restarts_are_off(monkeypatch):
    monkeypatch.setattr(runner_mod.process, "game_uptime_s", lambda: 99 * 3600)
    g = WaitGame(["back", "back", "front"])
    assert _waiting_runner(g, restart=False)._wait_for_front() is True


def test_stop_ends_the_wait_and_a_new_cycle_too():
    with pytest.raises(BotStopped):
        _waiting_runner(WaitGame([], sleep_error=BotStopped()))._wait_for_front()
    g = WaitGame([], sleep_error=UserInterrupted("restart"))
    assert _waiting_runner(g)._wait_for_front() is True


def test_main_script_waits_then_starts_a_new_cycle(monkeypatch):
    events = []
    guard = SimpleNamespace(reset=lambda: events.append("reset"))
    g = SimpleNamespace(front_guard=guard, status=events.append, vars={})
    r = runner_mod.Runner.__new__(runner_mod.Runner)
    r.g, r.settings = g, FlagSettings()
    results = iter([GameNotInFront("x"), GameNotInFront("y", gone=True), False])

    def cycle():
        events.append("cycle")
        outcome = next(results)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    waits = iter([True, False])
    r._cycle = cycle
    r._wait_for_front = lambda: events.append("wait") or next(waits)
    r._back_to_main_screen = lambda: events.append("main screen")
    r.main_script()
    assert events == [
        "reset", "cycle", "wait", "main screen", "cycle", "wait", "cycle"
    ]  # fmt: skip


def test_a_step_does_not_recover_by_clicking(monkeypatch):
    calls = []
    for module, fn in [
        ("big_close", "big_close"),
        ("main_menu", "main_menu"),
        ("main_menu", "close_chooser"),
        ("open_town", "open_town"),
    ]:
        monkeypatch.setattr(getattr(runner_mod, module), fn, lambda g, n=fn: calls.append(n))
    r = runner_mod.Runner.__new__(runner_mod.Runner)
    r.g = SimpleNamespace(
        found=lambda p: True, status=calls.append, save_diagnostic=calls.append, focus=lambda: None
    )

    def feature():
        raise GameNotInFront("x")

    with pytest.raises(GameNotInFront):
        r._step("Arena", feature, town=True)
    assert calls == []


def test_back_to_main_screen_gives_up_quietly_when_not_in_front(monkeypatch):
    lines = []
    g = SimpleNamespace(focus=lambda: None, status=lines.append)

    def refused(game):
        raise GameNotInFront("x")

    monkeypatch.setattr(runner_mod.big_close, "big_close", refused)
    runner_mod.Runner._back_to_main_screen(SimpleNamespace(g=g))
    assert lines == []


@pytest.mark.parametrize("supported", [True, False])
def test_the_runner_installs_the_guard_on_windows_only(monkeypatch, supported):
    monkeypatch.setattr(ForegroundGuard, "supported", staticmethod(lambda: supported))
    g = SimpleNamespace(stop_event=threading.Event(), front_guard=None)
    runner_mod.Runner(FlagSettings(), g)
    assert isinstance(g.front_guard, ForegroundGuard) is supported


def test_an_episode_from_the_refused_click_to_the_resume(monkeypatch, live_game, clock):
    """2026-10-25 replayed on fakes: the click that met another window in front is not
    sent, the runner waits without input, and the game back in front ends it."""
    g, sent = live_game
    lines, captures, beats = [], [], []
    g.status_cb = lines.append
    g.heartbeat_cb = lambda msg, stop, important: beats.append((msg, important))
    monkeypatch.setattr(g, "save_diagnostic", lambda name, block=1: captures.append(name))
    monkeypatch.setattr(game_mod, "find_game_window", lambda: _win())
    api = FakeApi(owner=("SomeOverlay.exe", "OverlayWindowClass", 777))
    g.front_guard = guard = ForegroundGuard(api)
    with pytest.raises(GameNotInFront):
        g.tap_xy(1455, 821)  # the bag icon
    real_poll, polls = guard.poll, []

    def poll(game):
        polls.append(1)
        clock[0] += 5
        if len(polls) == 12:
            api.front = True  # whatever held the foreground went away
        return real_poll(game)

    guard.poll = poll
    assert _waiting_runner(g)._wait_for_front() is True
    assert sent == []  # not one event in the whole episode
    assert lines[0].startswith("Paused: the game window is not in front")
    assert "in front: SomeOverlay.exe, window class OverlayWindowClass" in lines[0]
    assert lines[-1] == "The game window is in front again after 1m00s; going on"
    assert captures == [ForegroundGuard.CAPTURE]
    assert [b for b in beats if b[1]] == [
        ("Paused: the game window cannot be brought to the front, no input until it is", True)
    ]
    g.tap_xy(1455, 821)
    assert sent[-1] == ("click",)


def test_a_guard_already_there_is_kept(monkeypatch):
    monkeypatch.setattr(ForegroundGuard, "supported", staticmethod(lambda: True))
    mine = ForegroundGuard(FakeApi())
    g = SimpleNamespace(stop_event=threading.Event(), front_guard=mine)
    runner_mod.Runner(FlagSettings(), g)
    assert g.front_guard is mine


# -- a relaunched game: the start-button wait polls on, it never clicks blind --------------
class StartGame:
    def __init__(self, refusals, now):
        self.window = _win()
        self.refusals = refusals  # moves refused before the game is in front
        self.now = now
        self.clicks = 0
        self.moves = 0

    def focus(self):
        pass

    def sleep(self, ms):
        self.now[0] += ms / 1000

    def move_to(self, p):
        if self.refusals:
            self.refusals -= 1
            raise GameNotInFront("not in front")
        self.moves += 1

    def found(self, probe):
        return True

    def click(self):
        self.clicks += 1


@pytest.fixture
def launch_clock(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(game_launch, "time", SimpleNamespace(monotonic=lambda: now[0]))
    return now


def test_the_start_button_is_clicked_once_the_game_is_in_front(launch_clock):
    g = StartGame(refusals=2, now=launch_clock)
    assert game_launch.wait_for_start_button(g, timeout_s=300) is True
    assert g.moves == 1 and g.clicks == 1


def test_a_game_never_in_front_gets_no_click_and_the_wait_times_out(launch_clock):
    g = StartGame(refusals=10**6, now=launch_clock)
    assert game_launch.wait_for_start_button(g, timeout_s=60) is False
    assert g.moves == 0 and g.clicks == 0


def test_another_programs_window_does_not_use_up_the_start_wait(launch_clock):
    """Review 2026-10-28: a relaunch behind another program's window timed out as "no start
    screen", and the launch killed the game (Steam: and restarted Steam) every few minutes.
    The wait goes on while that window holds the front, then clicks the start button."""
    g = StartGame(refusals=100, now=launch_clock)  # 100 rounds of 5.5 s: past the timeout
    g.front_guard = SimpleNamespace(restart_helps=lambda game: False)
    assert game_launch.wait_for_start_button(g, timeout_s=60) is True
    assert g.clicks == 1


@pytest.mark.parametrize("helps, gone", [(True, False), (False, True)])
def test_a_hung_game_or_a_gone_window_keeps_the_start_wait_timeout(launch_clock, helps, gone):
    g = StartGame(refusals=10**6, now=launch_clock)
    g.front_guard = SimpleNamespace(restart_helps=lambda game: helps)
    real_move = g.move_to

    def move_to(p):
        try:
            real_move(p)
        except GameNotInFront as e:
            raise GameNotInFront(str(e), gone=gone) from None

    g.move_to = move_to
    assert game_launch.wait_for_start_button(g, timeout_s=60) is False
    assert g.clicks == 0


# -- window handles ----------------------------------------------------------------------------
def test_window_handles_compare_on_their_low_32_bits():
    h = 0x80001234  # bit 31 set: a C int return reads it negative, a pointer sign-extended
    assert same_window(h - (1 << 32), 0xFFFFFFFF80001234)
    assert same_window(h, h - (1 << 32))
    assert same_window(0x1A2B, 0x1A2B)
    assert not same_window(0x1A2B, 0x1A2C)
    assert not same_window(0, 0) and not same_window(None, None) and not same_window(None, 5)


# -- the Win32 backend on a fake user32 (where it can be imported) ---------------------------
win32 = pytest.mark.skipif(sys.platform != "win32", reason="the Win32 backend needs ctypes.windll")


class FakeUser32:
    def __init__(self, fg=0x1234, pid=4321, cls="Chrome_WidgetWin_1", allow=False):
        self.fg = fg
        self.pid = pid
        self.cls = cls
        self.allow = allow  # whether SetForegroundWindow is honoured
        self.calls: list[str] = []

    def GetForegroundWindow(self):
        return self.fg

    def GetWindowThreadProcessId(self, hwnd, ref):
        if ref is not None:
            ref._obj.value = self.pid
        return 99

    def GetClassNameW(self, hwnd, buf, size):
        buf.value = self.cls
        return len(self.cls)

    def GetWindowTextW(self, *a):
        raise AssertionError("the window title must never be read")

    GetWindowTextLengthW = GetWindowTextW

    def IsIconic(self, hwnd):
        return 0

    def ShowWindow(self, hwnd, cmd):
        self.calls.append("ShowWindow")

    def SetForegroundWindow(self, hwnd):
        self.calls.append("SetForegroundWindow")
        if self.allow:
            self.fg = hwnd
        return int(self.allow)

    def BringWindowToTop(self, hwnd):
        self.calls.append("BringWindowToTop")

    def AttachThreadInput(self, a, b, on):
        self.calls.append(f"AttachThreadInput {bool(on)}")
        return 1

    def IsHungAppWindow(self, hwnd):
        self.calls.append("IsHungAppWindow")
        return 1 if hwnd == 0xDEAD else 0


@pytest.fixture
def winmod(monkeypatch):
    from firestone_bot.platform.win import window as winmod

    monkeypatch.setattr(winmod, "kernel32", SimpleNamespace(GetCurrentThreadId=lambda: 7))
    monkeypatch.setattr(winmod, "_process_name", lambda pid: "chrome.exe" if pid == 4321 else "")
    return winmod


@win32
def test_the_foreground_owner_is_named_by_exe_and_class_never_by_title(monkeypatch, winmod):
    monkeypatch.setattr(winmod, "user32", FakeUser32())
    assert winmod.foreground_owner() == ("chrome.exe", "Chrome_WidgetWin_1", 4321)


@win32
def test_no_foreground_window_names_nothing(monkeypatch, winmod):
    monkeypatch.setattr(winmod, "user32", FakeUser32(fg=0))
    assert winmod.foreground_owner() == ("", "", 0)


@win32
def test_a_hung_game_window_is_told(monkeypatch, winmod):
    monkeypatch.setattr(winmod, "user32", FakeUser32())
    assert winmod.is_hung(_win(handle=0xDEAD)) is True
    assert winmod.is_hung(_win(handle=0x1A2B)) is False


@win32
def test_activate_says_whether_it_worked_and_never_warns(monkeypatch, winmod, caplog):
    game = _win(handle=0x1A2B)
    with caplog.at_level(logging.WARNING):
        monkeypatch.setattr(winmod, "user32", FakeUser32(allow=True))
        assert winmod.activate(game) is True and winmod.is_foreground(game)
        refusing = FakeUser32(allow=False)
        monkeypatch.setattr(winmod, "user32", refusing)
        assert winmod.activate(game) is False and not winmod.is_foreground(game)
        # the second try attached to the foreground thread, and detached again
        assert refusing.calls[-1] == "AttachThreadInput False"
    assert caplog.text == ""


@win32
def test_the_guard_runs_on_the_real_backend_functions(monkeypatch, winmod, clock):
    """The guard's default api over the Win32 module (user32 faked): refused, named."""
    monkeypatch.setattr(winmod, "user32", FakeUser32())
    monkeypatch.setattr(foreground.winapi, "is_foreground", winmod.is_foreground)
    monkeypatch.setattr(foreground.winapi, "activate", winmod.activate)
    monkeypatch.setattr(foreground.winapi, "foreground_owner", winmod.foreground_owner)
    g = FakeGame()
    with pytest.raises(GameNotInFront):
        ForegroundGuard().check(g)
    assert "in front: chrome.exe, window class Chrome_WidgetWin_1" in g.lines[0]


@win32
def test_ctypes_byref_exposes_its_object():
    """FakeUser32 writes the pid through ctypes.byref(...)._obj, as the real call does."""
    from ctypes import wintypes

    pid = wintypes.DWORD()
    ref = ctypes.byref(pid)
    ref._obj.value = 12
    assert pid.value == 12
