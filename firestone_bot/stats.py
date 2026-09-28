"""Statistics of every cycle the bot ever ran, kept in settings.ini (section [Stats]).

The dashboard showed the last cycle's duration only, and lost it as soon as the bot was
restarted (owner, 2026-09-09). The three counters below survive restarts and updates: how
many cycles finished, how long they took in total (time spent inside cycles, not the time
the window was open) and how long the last one took.

Hours stopped being readable for the total: the owner's 1567397896 ms showed as "435h23m" on
2026-09-28. A duration of a day or more now shows its two largest units in days, weeks, months
or years ("2w4d"), at most 7 characters. That fits the Camp "Total time" tile at the 980x680
minimum window: the widest string, "10mo30d", left 8 px of its 146 px in the widest skin
(measured 2026-09-28, tests/test_gui_camp.py), where hours alone would have overflowed it
by 1 to 4 px from 1000 h ("1000h00m").
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
MONTH = YEAR // 12  # 30 d 10 h: 12 months make a year, so '12mo' never shows


def fmt_ms(value) -> str:
    """A duration in ms as 45s, 2m30s, 3h05m, 6d10h, 2w4d, 3mo24d or 1y2mo: the two largest
    units, rounded down (a month is a twelfth of a 365-day year); '-' when there is nothing yet.
    Months are 'mo', never 'm': minutes only ever sit next to hours or seconds."""
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
        return f"{s // DAY}d{s % DAY // HOUR}h"
    if s < MONTH:
        return f"{s // WEEK}w{s % WEEK // DAY}d"
    if s < YEAR:
        return f"{s // MONTH}mo{s % MONTH // DAY}d"
    return f"{s // YEAR}y{s % YEAR // MONTH}mo"
