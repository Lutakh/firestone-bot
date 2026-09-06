"""Input guard: the bot's own events are ignored, the user's pause the bot thread."""

import threading

import pytest

from firestone_bot import inputguard
from firestone_bot.game import Game
from firestone_bot.platform import input as inp
from firestone_bot.settings import Settings


class _Game:
    def __init__(self):
        self.lines = []
        self.focused = 0

    def status(self, text):
        self.lines.append(text)

    def focus(self):
        self.focused += 1


def test_bot_own_events_are_ignored(monkeypatch):
    guard = inputguard.InputGuard(lambda g: "continue")
    guard.arm()
    monkeypatch.setattr(
        inp, "last_injection", lambda: (inputguard.time.monotonic(), (100.0, 100.0))
    )
    guard._on_move(101, 102)  # right after an injection, at the injected spot
    assert not guard.triggered.is_set()
    monkeypatch.setattr(inp, "last_injection", lambda: (0.0, (100.0, 100.0)))
    guard._on_move(104, 103)  # long after, but where the bot left the pointer
    assert not guard.triggered.is_set()
    guard._on_move(300, 300)  # the user
    assert guard.triggered.is_set() and guard.reason == "mouse moved"


def test_injected_events_use_the_heuristic_and_disarmed_guard_ignores_everything(monkeypatch):
    guard = inputguard.InputGuard(lambda g: "continue")
    guard.arm()
    monkeypatch.setattr(
        inp, "last_injection", lambda: (inputguard.time.monotonic(), (100.0, 100.0))
    )
    guard._on_move(101, 101, True)  # injected right where/when the bot acted: the bot's
    assert not guard.triggered.is_set()
    monkeypatch.setattr(inp, "last_injection", lambda: (0.0, (100.0, 100.0)))
    guard._on_move(300, 300, True)  # injected far away, long after: a remote desktop user
    assert guard.triggered.is_set() and guard.reason == "mouse moved"
    guard.triggered.clear()
    guard._on_click(1, 1, None, True, False)  # not injected: hardware, always the user
    assert guard.triggered.is_set() and guard.reason == "mouse clicked"
    guard.disarm()
    guard._on_press("a")
    assert not guard.triggered.is_set()


def test_check_continues_or_interrupts(monkeypatch):
    monkeypatch.setattr(inp, "last_injection", lambda: (0.0, None))
    restored = []
    monkeypatch.setattr(inp, "restore_position", lambda: restored.append(1))
    g = _Game()
    guard = inputguard.InputGuard(lambda gd: "continue")
    guard.arm()
    guard._on_press("x")
    guard.check(g)
    assert not guard.triggered.is_set() and g.focused == 1 and restored == [1]
    assert g.lines[0].startswith("Paused: keyboard used")
    guard.on_pause = lambda gd: "restart"
    guard._on_move(5, 5)
    with pytest.raises(inputguard.UserInterrupted):
        guard.check(g)
    assert not guard.triggered.is_set()


def test_game_sleep_calls_the_guard():
    g = Game(Settings(), time_scale=0.01)
    calls = []

    def check(game):
        calls.append(game)
        if len(calls) == 1:
            raise inputguard.UserInterrupted("restart")

    g.guard_check = check
    with pytest.raises(inputguard.UserInterrupted):
        g.sleep(1000)
    assert calls == [g]
    g.stop_event = threading.Event()
    g.sleep(50)
    assert len(calls) >= 2
