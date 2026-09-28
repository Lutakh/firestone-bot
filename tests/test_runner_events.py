"""Runner: the events step runs again right after a shop visit that detected the daily reset,
so the Decorated Heroes check of the new game day turns the switch off before mail, the town
and the guild spend with the event's limits. LastTokenReset is when the shop detected the
reset: after a bot started hours after a reset, the events step before the shop is not near
the next one and a recent sighting keeps it from looking (review 2026-09-28)."""

from __future__ import annotations

import threading
from datetime import datetime, timedelta

import pytest

from firestone_bot import daily
from firestone_bot import runner as runner_mod
from firestone_bot.features import claim_events, event_watch
from firestone_bot.settings import Settings
from tests.test_decorated_heroes import FakeEvents, patch_events


def _stamp(hours_ago):
    """A LastTokenReset `hours_ago` (local time, AHK A_Now format, as state.hours_since)."""
    past = datetime.now() - timedelta(hours=hours_ago)  # noqa: DTZ005
    return past.strftime("%Y%m%d%H%M%S")


class CycleGame(FakeEvents):
    """The events list fake, with what the rest of a runner cycle asks of the game."""

    def __init__(self, settings, **kw):
        super().__init__(settings, **kw)
        self.stop_event = threading.Event()
        self.stats = {}

    def locked(self, feature):
        return True  # the town's optional buildings: skipped


# the steps after the shop, faked; recorded with the switch as they found it
LATER_STEPS = [
    ("check_mail", "check_mail", "Mail"),
    ("open_chests", "open_bag", "Open chests"),
    ("guardian", "guardian", "Guardian"),
    ("claim_beer", "claim_beer", "Tavern beer"),
    ("research", "go_research", "Research"),
    ("guild", "guild", "Guild"),
    ("hero_upgrade", "hero_upgrade", "Hero upgrades"),
]


@pytest.fixture
def cycle(monkeypatch, tmp_path):
    """make(reset=..., **FakeEvents options) -> (runner, game, steps): one cycle with the
    switch on, the last detected reset 20 h old, the event's page seen 20 min ago (the
    events step before the shop does not look), no bell; `reset`: the shop visit detects the
    daily reset."""
    patch_events(monkeypatch, [])
    clock = [50_000_000]
    monkeypatch.setattr(event_watch, "_now_ms", lambda: clock[0])
    steps = []

    def record(name):
        return lambda g: steps.append((name, daily.event_on(g.settings)))

    real_claim = claim_events.claim_events

    def events(g):
        steps.append(("Events", daily.event_on(g.settings)))
        real_claim(g)

    monkeypatch.setattr(claim_events, "claim_events", events)
    for module, fn, name in LATER_STEPS:
        monkeypatch.setattr(getattr(runner_mod, module), fn, record(name))
    for module, fn, value in [
        ("game_launch", "ensure_game_running", True),
        ("main_menu", "main_menu", True),
        ("main_menu", "close_chooser", None),
        ("open_town", "open_town", True),
        ("open_town", "town_is_open", True),
        ("big_close", "big_close", None),
    ]:
        monkeypatch.setattr(getattr(runner_mod, module), fn, lambda g, v=value: v)
    monkeypatch.setattr(runner_mod.open_chests, "bag_plan", lambda s: (1,))
    monkeypatch.setattr(runner_mod.layouts, "detect_style", lambda *a: "new")
    monkeypatch.setattr(runner_mod.layouts, "new_style_seen", lambda g: True)
    monkeypatch.setattr(runner_mod.stats, "note_cycle", lambda s, ms: None)
    monkeypatch.setattr(runner_mod.Runner, "_progress_checks", lambda self: None)

    def make(reset, **kw):
        s = Settings(path=str(tmp_path / "settings.ini"), loaded=True)
        values = {
            "EventDecoratedHeroes": "1",
            "Events": "1",
            "LastTokenReset": _stamp(20),
            "RestartGame": "0",
            "BattlePass": "0",
            "Quests": "0",
            "Mail": "1",
            "SellEx": "0",
            "MapMissions": "0",
        }
        for k, v in values.items():
            s.set(k, v)
        s.save()
        kw.setdefault("bells", ())
        g = CycleGame(s, **kw)
        event_watch.note_seen(g)
        clock[0] += 20 * 60_000

        def shop(game):
            steps.append(("Daily shop", daily.event_on(s)))
            if reset:
                daily.mark_daily_reset(s)

        monkeypatch.setattr(runner_mod.shop, "shop", shop)
        r = runner_mod.Runner(s, g)
        r.max_cycles = 1
        r._last_arena = 0
        r._last_restart = runner_mod._ms()
        r._last_request = 0
        r._restart_ms = 0
        return r, g, steps

    return make


def _names(steps):
    return [name for name, _ in steps]


def test_a_reset_detected_late_turns_the_switch_off_before_the_town(cycle):
    r, g, steps = cycle(reset=True, cards=("basic",))
    assert r._cycle() is False  # max cycles reached
    assert _names(steps)[:4] == ["Events", "Daily shop", "Events", "Mail"]
    assert steps[:3] == [("Events", True), ("Daily shop", True), ("Events", True)]
    # the events step before the shop did not look (a sighting 20 min ago, reset not near)
    assert g.openings == 2  # both looks after the reset
    assert all(on is False for _, on in steps[3:])
    assert ("Guardian", False) in steps and ("Tavern beer", False) in steps
    assert ("Guild", False) in steps
    assert not g.settings.flag("EventDecoratedHeroes")
    assert ("Decorated Heroes event not active: switch turned off", True) in g.beats


def test_the_event_still_running_after_the_reset_keeps_the_switch(cycle):
    r, g, steps = cycle(reset=True, cards=("dh",))
    r._cycle()
    assert _names(steps)[:4] == ["Events", "Daily shop", "Events", "Mail"]
    assert g.openings == 1 and g.card_taps() == [0]
    assert all(on for _, on in steps)
    assert g.vars[event_watch._seen_key(g)]  # seen under the new game day


def test_no_reset_no_second_events_step(cycle):
    r, g, steps = cycle(reset=False, cards=("basic",))
    r._cycle()
    assert _names(steps)[:3] == ["Events", "Daily shop", "Mail"]
    assert _names(steps).count("Events") == 1
    assert g.openings == 0 and g.settings.flag("EventDecoratedHeroes")


def test_switch_off_no_second_events_step(cycle):
    r, g, steps = cycle(reset=True, cards=("basic",))
    g.settings.set("EventDecoratedHeroes", "0")
    g.settings.set("Events", "0")
    r._cycle()
    assert "Events" not in _names(steps)
    assert _names(steps)[:2] == ["Daily shop", "Mail"]
