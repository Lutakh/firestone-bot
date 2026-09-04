"""Binder (Tk-free): inverted keys, atomic writes, debounce, deferral, reload."""

from firestone_bot.gui.binding import Binder
from firestone_bot.settings import Settings


class FakeVar:
    def __init__(self, value=""):
        self._value = value
        self._traces = []

    def get(self):
        return self._value

    def set(self, value):
        self._value = value
        for fn in self._traces:
            fn()

    def trace_add(self, _mode, fn):
        self._traces.append(fn)


class FakeScheduler:
    """Collects after() callbacks; `fire()` runs the pending ones."""

    def __init__(self):
        self.pending = {}
        self.next_id = 0

    def after(self, _ms, fn):
        self.next_id += 1
        self.pending[self.next_id] = fn
        return self.next_id

    def after_cancel(self, ident):
        self.pending.pop(ident, None)

    def fire(self):
        for fn in list(self.pending.values()):
            fn()
        self.pending.clear()


def make(tmp_path, running=False):
    settings = Settings(path=str(tmp_path / "settings.ini"))
    saves = []
    original = settings.save

    def counting_save(path=None):
        saves.append(dict(settings.values))
        original(path)

    settings.save = counting_save
    sched = FakeScheduler()
    states = []
    flags = {"running": running}
    binder = Binder(
        settings,
        sched,
        lambda kind, text: states.append((kind, text)),
        lambda: flags["running"],
        var_factory=FakeVar,
    )
    return settings, binder, sched, saves, states, flags


def test_inverted_var_flips_on_read_and_write(tmp_path):
    settings, binder, *_ = make(tmp_path)
    settings.set("Beer", "0")
    v = binder.var("Beer", inverted=True)
    assert v.get() == "1"  # ON = the bot claims beer
    v.set("0")
    assert settings.get("Beer") == "1"
    plain = binder.var("Mail")
    plain.set("0")
    assert settings.get("Mail") == "0"


def test_set_many_writes_exactly_one_sell_flag(tmp_path):
    settings, binder, sched, saves, states, _flags = make(tmp_path)
    keys = ["SellScrolls", "SellNoGold", "SellAll", "SellNone"]
    binder.register(*keys)
    binder.set_many({k: "1" if k == "SellNoGold" else "0" for k in keys})
    assert [settings.get(k) for k in keys] == ["0", "1", "0", "0"]
    assert set(keys) <= binder.keys()
    assert states[-1][0] == "unsaved"
    sched.fire()
    assert len(saves) == 1


def test_debounce_collapses_quick_changes(tmp_path):
    _settings, binder, sched, saves, states, _flags = make(tmp_path)
    v = binder.var("Mail")
    v.set("0")
    v.set("1")
    assert len(sched.pending) == 1
    sched.fire()
    assert len(saves) == 1 and saves[0]["Mail"] == "1"
    assert states[-1][0] == "saved" and "created" in states[-1][1]
    assert not binder.dirty


def test_save_deferred_while_running_then_flushed(tmp_path):
    _settings, binder, sched, saves, states, flags = make(tmp_path, running=True)
    binder.var("Token").set("1")
    sched.fire()
    assert saves == [] and states[-1][0] == "deferred"
    assert binder.dirty
    flags["running"] = False
    binder.flush()  # the window calls this on the running -> idle transition
    assert len(saves) == 1 and saves[0]["Token"] == "1"


def test_flush_while_running_is_deferred_unless_forced(tmp_path):
    # Ctrl+S / Save now must not race the bot thread's own settings.save(); the exit path
    # forces the write once the runner has stopped.
    _settings, binder, _sched, saves, states, _flags = make(tmp_path, running=True)
    binder.var("Token").set("1")
    binder.flush()
    assert saves == [] and states[-1][0] == "deferred" and binder.dirty
    binder.flush(force=True)
    assert len(saves) == 1 and saves[0]["Token"] == "1" and not binder.dirty


def test_reload_does_not_save_and_refreshes_vars(tmp_path):
    settings, binder, sched, saves, _states, _flags = make(tmp_path)
    v = binder.var("Mail")
    beer = binder.var("Beer", inverted=True)
    settings.set("Mail", "0")
    settings.set("Beer", "1")
    settings.save()
    saves.clear()
    v.set("1")  # unsaved change, pending debounce
    binder.reload()
    assert v.get() == "0" and settings.get("Mail") == "0"
    assert beer.get() == "0"
    assert saves == [] and not sched.pending and not binder.dirty


def test_save_failure_reports_error_and_keeps_dirty(tmp_path):
    settings, binder, sched, _saves, states, _flags = make(tmp_path)
    errors = []
    binder.on_save_error = errors.append

    def boom(path=None):
        raise OSError("disk full")

    settings.save = boom
    binder.var("Mail").set("0")
    sched.fire()
    assert states[-1][0] == "error" and "disk full" in states[-1][1]
    assert binder.dirty and errors == ["disk full"]
    sched.fire()  # no pending callback: nothing happens
    binder.var("Mail").set("1")
    sched.fire()
    assert errors == ["disk full"]  # one dialog per session
