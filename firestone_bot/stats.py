"""Statistics of every cycle the bot ever ran, kept in settings.ini (section [Stats]).

The dashboard showed the last cycle's duration only, and lost it as soon as the bot was
restarted (owner, 2026-09-09). The three counters below survive restarts and updates: how
many cycles finished, how long they took in total (time spent inside cycles, not the time
the window was open) and how long the last one took.

Hours stopped being readable for the total: the owner's 1567397896 ms showed as "435h23m" on
2026-09-28, then as "2w4d", which read as a code. A duration of a day or more now reads in
words, its two largest units: "2 weeks 4 days" on Camp, "2 weeks and 4 days" in Workshop.
Below a day the stopwatch forms stay ("45s", "2m30s", "3h05m"): cycles last minutes and the
Camp "Last" and "Average" tiles are narrow. The Camp statistics columns take the width of their
values (dashboard.py), so the widest string below 100 years, "80 years 10 months" (198 px in
Retro at heading 18), still fits the 980x680 minimum window in every skin (measured 2026-09-28,
tests/test_gui_camp.py).
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


MINUTE, HOUR, DAY, WEEK = 60, 3600, 86_400, 7 * 86_400
YEAR = 365 * DAY
MONTH = YEAR // 12  # 30 d 10 h: 12 months make a year, so "12 months" never shows


def _count(n: int, unit: str) -> str:
    return f"{n} {unit}" if n == 1 else f"{n} {unit}s"


def _two_units(s: int, big: int, big_name: str, small: int, small_name: str, joiner: str) -> str:
    first = _count(s // big, big_name)
    rest = s % big // small
    return f"{first}{joiner}{_count(rest, small_name)}" if rest else first


def fmt_ms(value, joiner: str = " ") -> str:
    """A duration in ms: 45s, 2m30s or 3h05m below a day, then its two largest units in words,
    1 day 3 hours, 2 weeks 4 days, 3 months 24 days or 1 year 2 months; a second unit at zero
    is left out (1 week, not 1 week 0 days). Rounded down; a month is a twelfth of a 365-day
    year. `joiner` goes between the two worded units (" and " in Workshop: 2 weeks and 4 days).
    '-' when there is nothing yet."""
    try:
        ms = int(float(str(value).strip() or 0))
    except (ValueError, TypeError):
        ms = 0
    if ms <= 0:
        return "-"
    s = ms // 1000
    if s < MINUTE:
        return f"{s}s"
    if s < HOUR:
        return f"{s // MINUTE}m{s % MINUTE:02d}s"
    if s < DAY:
        return f"{s // HOUR}h{s % HOUR // MINUTE:02d}m"
    if s < WEEK:
        return _two_units(s, DAY, "day", HOUR, "hour", joiner)
    if s < MONTH:
        return _two_units(s, WEEK, "week", DAY, "day", joiner)
    if s < YEAR:
        return _two_units(s, MONTH, "month", DAY, "day", joiner)
    return _two_units(s, YEAR, "year", MONTH, "month", joiner)
