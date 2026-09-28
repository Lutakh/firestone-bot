"""ensure_game_running: a game process that never shows a window is restarted, once."""

from __future__ import annotations

import pytest

from firestone_bot.features import game_launch
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
