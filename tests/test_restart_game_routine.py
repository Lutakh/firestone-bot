"""restart_game_routine: a launch the Epic launcher holds gets a fresh launcher before the next
attempt (its "Application is busy" window after an update, 2026-09-29)."""

from __future__ import annotations

import pytest

from firestone_bot.features import restart_game_routine as rgr


class FakeGame:
    dry_run = False

    def __init__(self, cap: str = "3") -> None:
        self.lines: list[str] = []
        self.vars: dict = {}
        self.cap = cap
        self.settings = self

    def get(self, key: str) -> str:
        return self.cap if key == "SafetyCap" else ""

    def status(self, text: str) -> None:
        self.lines.append(text)

    def toast(self, title: str, text: str, seconds: float) -> None:
        pass

    def heartbeat(self, msg: str, is_stop: bool = False, important: bool = False) -> None:
        pass

    def sleep(self, ms: float) -> None:
        pass


@pytest.fixture
def store(monkeypatch):
    state = {"platform": "epic", "launches": 0, "closed": 0, "steam": 0, "started": False}

    def launch(platform):
        state["launches"] += 1

    def close():
        state["closed"] += 1
        state["started"] = True  # the next launch goes through
        return True

    monkeypatch.setattr(rgr.process, "detect_platform", lambda: state["platform"])
    monkeypatch.setattr(rgr.process, "kill_game", lambda: True)
    monkeypatch.setattr(rgr.process, "launch_game", launch)
    monkeypatch.setattr(rgr.process, "close_epic", close)
    monkeypatch.setattr(
        rgr.process, "restart_steam", lambda: state.__setitem__("steam", state["steam"] + 1)
    )
    monkeypatch.setattr(
        rgr.process, "find_game_process", lambda: object() if state["started"] else None
    )
    monkeypatch.setattr(rgr, "wait_for_start_button", lambda g, timeout: state["started"])
    return state


def test_epic_is_closed_when_the_game_never_started(store):
    g = FakeGame()
    assert rgr.restart_game_routine(g)
    assert store["closed"] == 1 and store["launches"] == 2
    assert any("closing the Epic launcher" in line for line in g.lines)
    assert g.lines[-1] == "Game restart: start screen found, resuming the cycle"


def test_epic_is_left_alone_when_the_game_runs_without_its_start_screen(store, monkeypatch):
    monkeypatch.setattr(rgr.process, "find_game_process", lambda: object())
    g = FakeGame(cap="2")
    assert rgr.restart_game_routine(g)  # cap reached
    assert store["closed"] == 0 and store["launches"] == 2


def test_steam_keeps_its_client_restart(store):
    store["platform"] = "steam"
    g = FakeGame(cap="1")
    assert rgr.restart_game_routine(g)
    assert store["steam"] == 1 and store["closed"] == 0
