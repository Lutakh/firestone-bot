"""When the game is restarted: the age of the game process, and a restart a feature asked for."""

from __future__ import annotations

import pytest

from firestone_bot import runner as runner_mod


class FakeGame:
    def __init__(self):
        self.log = []
        self.vars = {}

    def status(self, msg):
        self.log.append(msg)


def _runner(restart_hours=6.0):
    r = runner_mod.Runner.__new__(runner_mod.Runner)
    r._last_restart = runner_mod._ms()
    r._last_request = 0
    r._restart_ms = restart_hours * 3600000
    r.max_cycles = 0
    return r


def test_due_follows_the_game_process_age(monkeypatch):
    r, g = _runner(), FakeGame()
    monkeypatch.setattr(runner_mod.process, "game_uptime_s", lambda: 3 * 3600)
    assert r._due(g) is False
    monkeypatch.setattr(runner_mod.process, "game_uptime_s", lambda: 7 * 3600)
    assert r._due(g) is True
    assert any("running for" in m for m in g.log)


def test_due_falls_back_to_the_last_restart_when_the_age_is_unknown(monkeypatch):
    r, g = _runner(), FakeGame()
    monkeypatch.setattr(runner_mod.process, "game_uptime_s", lambda: None)
    assert r._due(g) is False  # the bot just started
    r._last_restart = runner_mod._ms() - 7 * 3600000
    assert r._due(g) is True


def test_no_schedule_when_the_delay_is_zero(monkeypatch):
    r, g = _runner(restart_hours=0), FakeGame()
    monkeypatch.setattr(runner_mod.process, "game_uptime_s", lambda: 99 * 3600)
    assert r._due(g) is False


def test_a_requested_restart_is_honoured_once_per_cooldown():
    r, g = _runner(), FakeGame()
    assert r._restart_request(g) == ""
    g.vars["restart_requested"] = "the chaos rift Hit button stayed grey"
    assert r._restart_request(g) == "the chaos rift Hit button stayed grey"
    r._last_request = runner_mod._ms()
    g.vars["restart_requested"] = "the chaos rift Hit button stayed grey"
    assert r._restart_request(g) == ""  # one just happened
    assert any("ignored" in m for m in g.log)
    r._last_request = runner_mod._ms() - r.REQUEST_COOLDOWN_MS - 1
    g.vars["restart_requested"] = "again"
    assert r._restart_request(g) == "again"


class LaunchGame(FakeGame):
    dry_run = False

    def __init__(self):
        super().__init__()
        self.slept = []
        self.beats = []

    def sleep(self, ms):
        self.slept.append(ms)

    def heartbeat(self, msg, is_stop=False, important=False):
        self.beats.append(msg)


class Settings:
    def get(self, key):
        return ""


@pytest.fixture(autouse=True)
def no_game(monkeypatch):
    kills = []
    monkeypatch.setattr(runner_mod.process, "find_game_process", lambda: None)
    monkeypatch.setattr(runner_mod.process, "kill_game", lambda: kills.append(1) or True)
    return kills


def test_a_game_that_does_not_start_is_tried_again_later(monkeypatch, no_game):
    r, g = _runner(), LaunchGame()
    r.settings = Settings()
    monkeypatch.setattr(runner_mod.process, "choose_platform", lambda setting, last: "epic")
    assert r._launch_failed(g) is True  # the bot goes on
    assert r._launch_failed(g) is True
    assert g.slept == [runner_mod.LAUNCH_RETRY_S * 1000] * 2
    assert len(g.beats) == 1  # one message per streak
    assert "next try in 10 min" in g.log[-1]


def test_no_store_known_still_stops(monkeypatch):
    r, g = _runner(), LaunchGame()
    r.settings = Settings()
    monkeypatch.setattr(runner_mod.process, "choose_platform", lambda setting, last: None)
    assert r._launch_failed(g) is False
    assert g.slept == []
    assert g.log[-1] == "The game could not be started; stopping"


def test_the_mouse_during_the_wait_does_not_end_the_run(monkeypatch):
    r, g = _runner(), LaunchGame()
    r.settings = Settings()
    monkeypatch.setattr(runner_mod.process, "choose_platform", lambda setting, last: "steam")

    def sleep(ms):
        raise runner_mod.UserInterrupted

    g.sleep = sleep
    assert r._launch_failed(g) is True


def test_a_game_stuck_before_its_start_screen_is_closed_before_the_wait(monkeypatch, no_game):
    r, g = _runner(), LaunchGame()
    r.settings = Settings()
    monkeypatch.setattr(runner_mod.process, "choose_platform", lambda setting, last: "epic")
    monkeypatch.setattr(runner_mod.process, "find_game_process", lambda: object())
    assert r._launch_failed(g) is True
    assert no_game == [1]  # the next cycle launches it afresh, not on the loading screen
    assert "the game is closed first" in g.log[-1]


@pytest.mark.parametrize("dry_run, max_cycles", [(True, 0), (False, 1)])
def test_dry_runs_and_runs_of_n_cycles_still_stop(monkeypatch, dry_run, max_cycles):
    r, g = _runner(), LaunchGame()
    r.settings = Settings()
    r.max_cycles = max_cycles
    g.dry_run = dry_run
    monkeypatch.setattr(runner_mod.process, "choose_platform", lambda setting, last: "epic")
    assert r._launch_failed(g) is False
    assert g.slept == []
    assert g.log[-1] == "The game could not be started; stopping"
