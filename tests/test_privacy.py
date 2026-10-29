"""The privacy policy in the app (SignPath's terms, 2026-10-29): the notice shown until it is
closed once, the first start's update check held back behind it, the switch for the automatic
update check, the texts and where they lead. MainWindow's side of the notice (waiting behind an
update notice, ✕, the button) is in test_gui_window.py."""

from __future__ import annotations

import inspect
import os
from types import SimpleNamespace

from firestone_bot.app import App
from firestone_bot.gui import help_text
from firestone_bot.gui.catalog import OPTIONS
from firestone_bot.gui.search_catalog import SEARCH_TARGETS, TARGETS_BY_ID, search_launcher
from firestone_bot.settings import EXTRA_SETTINGS, Settings

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class _Root:
    def __init__(self) -> None:
        self.after_calls: list[tuple[int, object]] = []

    def after(self, ms, fn) -> None:
        self.after_calls.append((ms, fn))


def _window(seen: bool = False) -> SimpleNamespace:
    win = SimpleNamespace(gui_state={}, root=_Root(), shown=[])
    if seen:
        win.gui_state[App.PRIVACY_SEEN] = True
    win.show_notice = lambda *args: win.shown.append(args)
    win.open_privacy = lambda: None
    return win


def _app(win, auto: bool = True) -> SimpleNamespace:
    checks: list[bool] = []
    app = SimpleNamespace(
        window=win,
        PRIVACY_SEEN=App.PRIVACY_SEEN,
        PRIVACY_GRACE_MS=App.PRIVACY_GRACE_MS,
        UPDATE_CHECK_INTERVAL_S=App.UPDATE_CHECK_INTERVAL_S,
        settings=SimpleNamespace(flag=lambda key: auto if key == "AutoUpdateCheck" else False),
        check_updates=lambda manual=False: checks.append(manual),
        checks=checks,
        _update={"last": 0.0},
    )
    app._auto_check_updates = lambda first=False: App._auto_check_updates(app, first)
    return app


def test_the_automatic_update_check_follows_the_switch():
    for first in (False, True):
        on, off = _app(_window(seen=True), auto=True), _app(_window(seen=True), auto=False)
        App._auto_check_updates(on, first)
        App._auto_check_updates(off, first)
        assert on.checks == [False] and off.checks == []  # automatic, not the button's check


def test_the_first_check_waits_a_minute_while_the_notice_was_never_closed():
    app = _app(_window(seen=False), auto=True)
    App._auto_check_updates(app, first=True)
    assert app.checks == [] and app._update["last"] > 0  # the daily tick waits too
    assert app.window.root.after_calls == [(60_000, app._auto_check_updates)]
    later = app.window.root.after_calls[0][1]
    later()  # a minute on: the check goes out...
    assert app.checks == [False]
    off = _app(_window(seen=False), auto=True)
    App._auto_check_updates(off, first=True)
    off.settings = SimpleNamespace(flag=lambda key: False)  # ...unless the switch went off
    off.window.root.after_calls[0][1]()
    assert off.checks == []
    daily = _app(_window(seen=False), auto=True)
    App._auto_check_updates(daily)  # the daily tick is not held back
    assert daily.checks == [False]


def test_the_daily_tick_goes_through_the_switch():
    app = _app(_window(), auto=False)
    ticks = []
    app._update = {"last": -1e12}  # a day is long past
    app._auto_check_updates = lambda: ticks.append("auto")
    app._update_tick = object()
    App._update_tick(app)
    assert ticks == ["auto"] and app.window.root.after_calls == [(60_000, app._update_tick)]


def test_start_up_schedules_the_notice_then_the_held_back_check():
    source = inspect.getsource(App)
    assert "after(2800, self._privacy_notice)" in source
    assert "after(3000, lambda: self._auto_check_updates(first=True))" in source
    assert "after(3000, self.check_updates)" not in source


def test_the_switch_is_on_by_default_and_off_survives_a_save(tmp_path):
    assert EXTRA_SETTINGS["AutoUpdateCheck"] == ("PythonOptions", "1")
    path = str(tmp_path / "settings.ini")
    settings = Settings(path=path, loaded=True)
    assert settings.flag("AutoUpdateCheck")
    settings.set("AutoUpdateCheck", "0")
    settings.save()
    assert not Settings.load(path).flag("AutoUpdateCheck")


def test_the_notice_is_queued_until_it_was_closed_once():
    win = _window(seen=False)
    App._privacy_notice(_app(win))
    assert win.shown == [
        (help_text.PRIVACY_NOTICE, "Privacy policy", win.open_privacy, App.PRIVACY_SEEN)
    ]
    closed = _window(seen=True)
    App._privacy_notice(_app(closed))
    assert closed.shown == []


def test_the_texts_name_every_destination_and_the_switch():
    label = OPTIONS["AutoUpdateCheck"].label
    assert label == "Check for updates automatically"
    for name in ("GitHub", "fs-bot-logs.lutak.ovh", "Discord", "Send report", label):
        assert name in help_text.PRIVACY, name
    for words in ("GitHub", "update check", "start-up", "daily"):
        assert words in help_text.PRIVACY_NOTICE, words
    assert len(help_text.PRIVACY_NOTICE) <= 90  # one banner line, which does not wrap
    assert help_text.PRIVACY_URL == "https://github.com/Lutakh/firestone-bot#privacy"
    with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
        readme = f.read()
    assert "\n## Privacy\n" in readme  # the #privacy anchor of PRIVACY_URL
    assert label in readme.split("\n## Privacy\n")[1].split("\n## ")[0]


def test_search_finds_the_switch_and_the_privacy_card_after_the_update_button():
    switch = TARGETS_BY_ID["option:AutoUpdateCheck"]
    assert (switch.page, switch.section, switch.key) == ("workshop", "files", "AutoUpdateCheck")
    privacy = TARGETS_BY_ID["value:workshop:privacy"]  # with the other help cards
    assert (privacy.page, privacy.section, privacy.key) == ("workshop", "help", "privacy")
    ids = [target.id for target in SEARCH_TARGETS]
    assert ids.index("action:workshop:check_update") < ids.index("option:AutoUpdateCheck")
    for query in ("Check for updates", "update check", "updates"):
        assert search_launcher(query)[0].id == "action:workshop:check_update", query
