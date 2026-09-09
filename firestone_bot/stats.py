"""Statistics of every cycle the bot ever ran, kept in settings.ini (section [Stats]).

The dashboard showed the last cycle's duration only, and lost it as soon as the bot was
restarted (owner, 2026-09-09). The three counters below survive restarts and updates: how
many cycles finished, how long they took in total (time spent inside cycles, not the time
the window was open) and how long the last one took.
"""

from __future__ import annotations

from firestone_bot.settings import Settings

KEYS = ("CyclesTotal", "CycleMsTotal", "LastCycleMs")


def _int(settings: Settings, key: str) -> int:
    try:
        return int(float(str(settings.get(key)).strip() or 0))
    except (ValueError, TypeError):
        return 0


def note_cycle(settings: Settings, took_ms: float) -> None:
    """Record one finished cycle and save."""
    took = max(0, int(took_ms))
    settings.set("CyclesTotal", _int(settings, "CyclesTotal") + 1)
    settings.set("CycleMsTotal", _int(settings, "CycleMsTotal") + took)
    settings.set("LastCycleMs", took)
    settings.save()


def cycles_total(settings: Settings) -> int:
    return _int(settings, "CyclesTotal")


def average_cycle_ms(settings: Settings) -> int:
    n = _int(settings, "CyclesTotal")
    return _int(settings, "CycleMsTotal") // n if n else 0


def fmt_ms(value) -> str:
    """A duration in ms as 45s, 2m30s or 3h05m; '-' when there is nothing yet."""
    try:
        ms = int(float(str(value).strip() or 0))
    except (ValueError, TypeError):
        ms = 0
    if ms <= 0:
        return "-"
    s = ms // 1000
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m{s % 60:02d}s"
    return f"{s // 3600}h{(s % 3600) // 60:02d}m"
