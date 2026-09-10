"""When the game is restarted: the age of the game process, and a restart a feature asked for."""

from __future__ import annotations

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
