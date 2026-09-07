"""Runner._step: a failing or lost feature is skipped and the bot recovers."""

from __future__ import annotations

import pytest

from firestone_bot import runner as runner_mod
from firestone_bot.game import BotStopped, ScreenNotReached
from firestone_bot.inputguard import UserInterrupted


class FakeGame:
    def __init__(self):
        self.log = []

    def status(self, msg):
        self.log.append(msg)

    def save_diagnostic(self, name):
        self.log.append(("diag", name))

    def focus(self):
        pass


def _runner(monkeypatch, g):
    calls = []
    monkeypatch.setattr(runner_mod.big_close, "big_close", lambda game: calls.append("big_close"))
    monkeypatch.setattr(runner_mod.main_menu, "main_menu", lambda game: calls.append("main_menu"))
    monkeypatch.setattr(runner_mod.open_town, "open_town", lambda game: calls.append("open_town"))
    r = runner_mod.Runner.__new__(runner_mod.Runner)
    r.g = g
    return r, calls


def test_ok_step_runs_without_recovery(monkeypatch):
    g = FakeGame()
    r, calls = _runner(monkeypatch, g)
    r._step("Engineer", lambda: g.log.append("ran"), town=True)
    assert g.log == ["ran"] and calls == []


def test_screen_not_reached_skips_and_recovers_in_town(monkeypatch):
    g = FakeGame()
    r, calls = _runner(monkeypatch, g)

    def feature():
        raise ScreenNotReached("dialog_close_x")

    r._step("Engineer", feature, town=True)
    assert "Engineer: its screen (dialog_close_x) did not show, step skipped" in g.log
    assert ("diag", "step-engineer.png") in g.log
    assert calls == ["big_close", "big_close", "main_menu", "open_town"]


def test_exception_skips_and_recovers_without_town(monkeypatch):
    g = FakeGame()
    r, calls = _runner(monkeypatch, g)

    def feature():
        raise ValueError("boom")

    r._step("Daily shop", feature)
    assert any(
        m.startswith("Daily shop: failed (ValueError('boom'))") for m in g.log if isinstance(m, str)
    )
    assert calls == ["big_close", "big_close", "main_menu"]


@pytest.mark.parametrize("exc", [BotStopped, UserInterrupted])
def test_stop_and_pause_unwind_the_cycle(monkeypatch, exc):
    g = FakeGame()
    r, calls = _runner(monkeypatch, g)

    def feature():
        raise exc()

    with pytest.raises(exc):
        r._step("Arena", feature, town=True)
    assert calls == []
