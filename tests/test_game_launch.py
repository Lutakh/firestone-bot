"""ensure_game_running: a game process that never shows a window is restarted, once."""

from __future__ import annotations

import threading

import pytest

from firestone_bot.features import game_launch
from firestone_bot.game import BotStopped
from firestone_bot.platform.window import GameWindowNotFound


class FakeGame:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def status(self, text: str) -> None:
        self.lines.append(text)


@pytest.fixture
def world(monkeypatch):
    state = {"process": True, "window": False, "kills": 0, "launches": 0, "waits": 0}

    def find_window():
        if not state["window"]:
            raise GameWindowNotFound("no window")

    def wait(g):
        state["waits"] += 1
        return state["window"]

    def kill():
        state["kills"] += 1
        state["process"] = False

    def launch(g):
        state["launches"] += 1
        return True

    monkeypatch.setattr(game_launch.process, "find_game_process", lambda: state["process"] or None)
    monkeypatch.setattr(game_launch.process, "kill_game", kill)
    monkeypatch.setattr(game_launch, "find_game_window", find_window)
    monkeypatch.setattr(game_launch, "wait_for_start_button", wait)
    monkeypatch.setattr(game_launch, "launch_game", launch)
    return state


def test_a_process_without_a_window_is_killed_and_launched_again(world):
    g = FakeGame()
    assert game_launch.ensure_game_running(g)
    assert world["kills"] == 1 and world["launches"] == 1
    assert any("has no window" in line for line in g.lines)


def test_a_process_whose_window_comes_during_the_wait_is_kept(world, monkeypatch):
    def wait(g):
        world["waits"] += 1
        world["window"] = True  # the loading screen showed and its button was clicked
        return True

    monkeypatch.setattr(game_launch, "wait_for_start_button", wait)
    assert game_launch.ensure_game_running(FakeGame())
    assert world["kills"] == 0 and world["launches"] == 0


def test_a_process_gone_during_the_wait_is_launched_without_a_kill(world, monkeypatch):
    def wait(g):
        world["waits"] += 1
        world["process"] = False
        return False

    monkeypatch.setattr(game_launch, "wait_for_start_button", wait)
    assert game_launch.ensure_game_running(FakeGame())
    assert world["kills"] == 0 and world["launches"] == 1


class LaunchGame(FakeGame):
    dry_run = False

    def __init__(self, platform: str) -> None:
        super().__init__()
        self.platform = platform
        self.settings = self

    def get(self, key: str) -> str:
        return self.platform if key == "GamePlatform" else ""

    def set(self, key: str, value: str) -> None:
        pass

    def save(self) -> None:
        pass


@pytest.fixture
def store(monkeypatch):
    """A store whose launches only work once its client was restarted (Epic's "Application is
    busy" window held every launch, 2026-09-29)."""
    state = {"launches": 0, "closed": 0, "blocked": True}
    monkeypatch.setattr(
        game_launch.process,
        "launch_game",
        lambda p: state.__setitem__("launches", state["launches"] + 1),
    )

    def close():
        state["closed"] += 1
        state["blocked"] = False
        return True

    monkeypatch.setattr(game_launch.process, "close_epic", close)
    monkeypatch.setattr(game_launch, "wait_for_game", lambda g: not state["blocked"])
    monkeypatch.setattr(game_launch, "wait_for_start_button", lambda g: True)
    return state


def test_epic_holding_the_launch_is_restarted_once(store):
    g = LaunchGame("epic")
    assert game_launch.launch_game(g)
    assert store["closed"] == 1 and store["launches"] == 2
    assert any("reopening the Epic launcher" in line for line in g.lines)


def test_epic_still_holding_after_its_restart_gives_up(store, monkeypatch):
    monkeypatch.setattr(game_launch, "wait_for_game", lambda g: False)
    g = LaunchGame("epic")
    assert not game_launch.launch_game(g)
    assert store["closed"] == 1 and store["launches"] == 2
    assert "after the Epic restart, giving up" in g.lines[-1]


def test_steam_is_not_touched_by_the_epic_restart(store):
    g = LaunchGame("steam")
    assert not game_launch.launch_game(g)
    assert store["closed"] == 0 and store["launches"] == 1
    assert g.lines[-1] == "Game launch: the process did not appear, giving up"


def test_a_stop_ends_the_wait_for_the_game(monkeypatch):
    g = FakeGame()
    g.stop_event = threading.Event()
    g.stop_event.set()
    monkeypatch.setattr(game_launch.process, "find_game_process", lambda: None)
    with pytest.raises(BotStopped):
        game_launch.wait_for_game(g, timeout_s=5)


def test_the_wait_for_the_game_ends_when_it_shows(monkeypatch):
    g = FakeGame()
    g.stop_event = threading.Event()
    monkeypatch.setattr(game_launch.process, "find_game_process", lambda: object())
    assert game_launch.wait_for_game(g, timeout_s=5)
