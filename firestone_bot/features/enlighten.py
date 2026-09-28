"""Guardian enlightenment: strange dust spent on the trained guardian (owner request 2026-09-28).

Until 0.3.29 the bot enlightened only for the Decorated Heroes event (3 a day at x1). The
automation (GuardianEnlighten, default off) spends more, within up to three daily limits the
user combines, the strictest winning (daily.py): a number of enlightenments, a strange dust
cap and a reserve of dust always kept. With every limit at 0 it spends all the dust, at most
MAX_CLICKS_PER_VISIT clicks per visit. The event's 3 are made whatever the dust cap and the
reserve say, and count toward the automation's totals.

Measured on the owner's game (2026-09-28, Epic, 1920x1009, new style): the multiplier label
top right of the panel steps x20 -> x1 -> x5 -> x10 -> x20 and sets how many enlightenments
one click buys; the button then reads "Enlightenment 1 / 20", "5 / 100", "10 / 200",
"20 / 400" (20 strange dust and +120 XP each) and stayed green at every multiplier with
10,518 dust.

How the dust is spent:
- the event's need first, as separate x1 clicks (whether its challenge counts clicks or
  enlightenments is unknown; x1 is right either way);
- then the automation's remainder, planned greedily with x20/x10/x5/x1 (425 = 21 x20 +
  1 x5) and made in the order the label steps from where it stands, so every multiplier is
  reached with forward clicks; the user's multiplier is put back at the end, whatever
  happened;
- before the first click at a multiplier the button's cost must read 20 x N: a label read
  wrong would buy another number. Unreadable or wrong above x1, that multiplier is not used
  and x1 clicks make up for it; wrong at x1, nothing is spent;
- before every click the button must be green and the budget must still allow it on a fresh
  dust read; a click counts only by the dust the counter says it took. More than the cost
  (a multiplier read wrong) stops the enlightenments for the game day.

Trip saver: with GuardianVisit off, the guardian screen is opened only for this. A visit that
could not spend (the reserve, the dust cap, a grey button, an unreadable counter) makes the
next ones wait an hour, the dust coming back slowly, unless the event still needs its 3.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from firestone_bot import daily
from firestone_bot.features import multiplier, token_counter
from firestone_bot.game import BotStopped, Game
from firestone_bot.vision import atlas

log = logging.getLogger("firestone_bot")

ENLIGHTEN_TAKEN_MS = 15000  # the counter drops at once (live); patience for a slow server
MULTIPLIER_CYCLE = (20, 1, 5, 10)  # what the label reads after each click, round and round
MAX_MULTIPLIER_STEPS = len(MULTIPLIER_CYCLE)
TIERS = (20, 10, 5, 1)  # multipliers for the plan, largest first
MAX_UNCONFIRMED = 2  # clicks the dust counter never showed, per game day, before giving up
MAX_CLICKS_PER_VISIT = 30  # "spend everything" ends: 30 clicks at x20 = 12,000 dust a visit
PAUSE_S = 3600  # after a visit that could not spend, the next trip waits this long
PAUSE_KEY = "enlighten_pause_until"  # Game.vars, time.monotonic() seconds
PAUSE_REASONS = ("unread", "reserve", "cap", "poor", "grey", "cost", "multiplier", "spent")

monotonic = time.monotonic  # the tests move the clock


def train_position(g: Game) -> int:
    """Roster position (1..4) of the guardian the user trains (GuardianTrain; the legacy
    value "Vermilion" is the first guardian)."""
    value = g.settings.get("GuardianTrain").strip()
    return int(value) if value in ("1", "2", "3", "4") else 1


def _multiplier(g: Game) -> int | None:
    g.move_to(atlas.GUARDIAN_MULTIPLIER_PARK)
    g.sleep(300)
    return multiplier.read_multiplier(g, atlas.GUARDIAN_MULTIPLIER_LABEL, None)


def _step_multiplier_to(g: Game, target: int) -> int | None:
    """Click the guardian screen's multiplier until it reads `target`; the value read last,
    None when a read does not follow the known cycle (a label read wrong: "x10" cut to
    "x1" must never pass for x1)."""
    value = _multiplier(g)
    steps = 0
    while value is not None and value != target and steps < MAX_MULTIPLIER_STEPS:
        if value not in MULTIPLIER_CYCLE:
            return None
        expected = MULTIPLIER_CYCLE[(MULTIPLIER_CYCLE.index(value) + 1) % MAX_MULTIPLIER_STEPS]
        g.tap(atlas.GUARDIAN_MULTIPLIER, 600)
        value = _multiplier(g)
        steps += 1
        if value != expected:
            return None
    return value


def button_cost(g: Game) -> int | None:
    """The strange dust the Enlightenment button asks (the number under its label), None
    when unreadable."""
    try:
        return token_counter.read_image(g, g.region_image(atlas.GUARDIAN_ENLIGHTEN_COST, None))
    except Exception:  # a capture error, missing digit templates: treated as unreadable
        log.debug("enlightenment cost unreadable", exc_info=True)
        return None


def plan_clicks(n: int) -> dict[int, int]:
    """Clicks per multiplier for `n` enlightenments, largest first (425: 21 x20 + 1 x5)."""
    plan = {}
    for m in TIERS:
        count, n = divmod(n, m)
        if count:
            plan[m] = count
    return plan


def _day(g: Game) -> str:
    return g.settings.get("LastTokenReset")


def _unconfirmed_key(g: Game) -> str:
    return f"enlighten_unconfirmed:{_day(g)}"


def _blocked_key(g: Game) -> str:
    return f"enlighten_blocked:{_day(g)}"


def due(g: Game) -> bool:
    """Whether the guardian screen should be opened, or used, for enlightenments now."""
    s = g.settings
    if not daily.enlighten_wanted(s):
        return False
    if g.vars.get(_blocked_key(g)) or g.vars.get(_unconfirmed_key(g), 0) >= MAX_UNCONFIRMED:
        return False
    if daily.event_enlighten_need(s):
        return True  # the event's 3 are tried every cycle, as before the automation
    return monotonic() >= g.vars.get(PAUSE_KEY, 0.0)


@dataclass
class _Visit:
    prefix: str
    mult: int | None  # what the label read last; None once a read broke the cycle
    dust: int | None = None  # the counter read last
    unit: int = daily.ENLIGHTEN_DUST  # dust one enlightenment takes
    checked: set[int] = field(default_factory=set)  # multipliers whose cost was read
    clicks: int = 0
    made: int = 0
    stop: str = ""  # why the visit ended early


def enlighten(g: Game) -> int:
    """Guardian screen open on its first tab: enlighten the trained guardian as far as the
    Decorated Heroes event and the user's limits allow, each enlightenment counted only when
    the strange dust counter drops. The user's multiplier is put back afterwards. Returns
    the number of enlightenments made."""
    if not due(g):
        return 0
    s = g.settings
    event_only = not daily.enlighten_on(s)
    v = _Visit(
        "Guardian enlightenment (Decorated Heroes):" if event_only else "Guardian enlightenment:",
        None,
    )
    g.wait_still()  # the training animation may still be playing
    g.tap(atlas.GUARDIAN_ROSTER[train_position(g) - 1][1])
    g.wait_still()
    before = _multiplier(g)
    if before not in MULTIPLIER_CYCLE:
        g.status(f"{v.prefix} the guardian multiplier is not readable, no enlightenment")
        g.save_diagnostic("enlighten-multiplier.png")
        g.vars[PAUSE_KEY] = monotonic() + PAUSE_S
        return 0
    v.mult = before
    stopped = False
    try:
        _spend(g, v)
    except BotStopped:
        stopped = True  # the user stopped the bot: not one more click, not even to restore
        raise
    finally:
        if not stopped and v.mult != before and _step_multiplier_to(g, before) != before:
            g.status(f"{v.prefix} the guardian multiplier could not be put back to x{before}")
            g.save_diagnostic("enlighten-multiplier.png")
    if v.stop in PAUSE_REASONS:
        g.vars[PAUSE_KEY] = monotonic() + PAUSE_S
    return v.made


def _spend(g: Game, v: _Visit) -> None:
    s = g.settings
    v.dust = token_counter.read_stable(g, atlas.GUARDIAN_DUST_DIGITS)
    if daily.enlightenments_allowed(s, v.dust, v.unit) <= 0:
        _nothing(g, v, v.dust, 1)
        return
    if daily.event_enlighten_need(s):
        # the event's own need first, one x1 click per enlightenment
        if not _set_multiplier(g, v, 1) or not _cost_ok(g, v, 1):
            return
        while daily.event_enlighten_need(s):
            if not _click(g, v, 1):
                return
    if not daily.enlighten_on(s):
        return
    dust = v.dust = token_counter.read_stable(g, atlas.GUARDIAN_DUST_DIGITS)
    n = daily.enlightenments_allowed(s, dust, v.unit)
    if n <= 0:
        _nothing(g, v, dust, 1)
        return
    plan = plan_clicks(n) if dust is not None else {1: n}  # blind: x1 clicks only
    while (m := _next_tier(v.mult, plan)) is not None:
        count = plan.pop(m)
        if not _set_multiplier(g, v, m):
            return
        if not _cost_ok(g, v, m):
            if v.stop:
                return
            plan[1] = plan.get(1, 0) + count * m  # this multiplier is not trusted: x1 instead
            continue
        for _ in range(count):
            if not _click(g, v, m):
                return
    if daily.enlighten_wanted(s) and daily.enlightenments_allowed(s, v.dust, v.unit) <= 0:
        v.stop = "spent"  # down to the reserve (or below one): the next trip can wait too


def _next_tier(current: int | None, plan: dict[int, int]) -> int | None:
    """The next multiplier with clicks left, forward along the cycle from `current`."""
    if current not in MULTIPLIER_CYCLE:
        return None
    i = MULTIPLIER_CYCLE.index(current)
    order = MULTIPLIER_CYCLE[i:] + MULTIPLIER_CYCLE[:i]
    return next((m for m in order if plan.get(m)), None)


def _set_multiplier(g: Game, v: _Visit, m: int) -> bool:
    if v.mult != m:
        v.mult = _step_multiplier_to(g, m)
    if v.mult == m:
        return True
    g.status(f"{v.prefix} the guardian multiplier did not go to x{m}")
    g.save_diagnostic("enlighten-multiplier.png")
    v.stop = "multiplier"
    return False


def _cost_ok(g: Game, v: _Visit, m: int) -> bool:
    """Before the first click at x`m`: the button asks `unit` x m strange dust. False with
    v.stop set: spend nothing more; False alone: do not use this multiplier."""
    if m in v.checked:
        return True
    v.checked.add(m)
    g.move_to(atlas.GUARDIAN_CHAOS_PARK)  # hovered, the button reads lighter
    g.sleep(300)
    cost = button_cost(g)
    if m == 1:
        if cost is None or cost == v.unit:
            return True
        if v.dust is None and cost > 0:
            v.unit = cost  # blind clicks are counted at the price the button shows
            return True
        g.status(
            f"{v.prefix} the button asks {cost} strange dust at x1, not {v.unit}: nothing spent"
        )
        g.save_diagnostic("enlighten-cost.png")
        v.stop = "cost"
        return False
    if cost == v.unit * m:
        return True
    shown = "no readable cost" if cost is None else f"a cost of {cost}"
    g.status(f"{v.prefix} the button shows {shown} at x{m}, not {v.unit * m}: x1 instead")
    g.save_diagnostic("enlighten-cost.png")
    return False


def _click(g: Game, v: _Visit, m: int) -> bool:
    """One click at x`m`, counted by the dust it took; False ends the visit."""
    s = g.settings
    if v.clicks >= MAX_CLICKS_PER_VISIT:
        g.status(f"{v.prefix} {v.clicks} clicks this visit, the rest waits for the next one")
        v.stop = "clicks"
        return False
    g.move_to(atlas.GUARDIAN_CHAOS_PARK)  # hovered, the green button reads lighter
    g.sleep(300)
    if not g.found(atlas.GUARDIAN_ENLIGHTEN_READY):
        g.status(f"{v.prefix} the Enlightenment button is not green (strange dust?)")
        v.stop = "grey"
        return False
    dust = v.dust = token_counter.read_stable(g, atlas.GUARDIAN_DUST_DIGITS)
    if (dust is None and m > 1) or daily.enlightenments_allowed(s, dust, v.unit) < m:
        _nothing(g, v, dust, m)
        return False
    g.tap(atlas.GUARDIAN_ENLIGHTEN, 0)
    g.sleep(300)
    g.move_to(atlas.GUARDIAN_CHAOS_PARK)
    v.clicks += 1
    if dust is None:
        g.sleep(1000)
        daily.note_enlighten(s, 1, v.unit)  # counter unreadable: an x1 click counts as made
        v.made += 1
        _report(g, v, 1, None)
        return True
    after = token_counter.wait_drop(g, atlas.GUARDIAN_DUST_DIGITS, dust, ENLIGHTEN_TAKEN_MS)
    if after is None:
        # not counted (another cycle tries again), but a click the counter never shows
        # must not turn into one paid enlightenment per cycle all day long
        key = _unconfirmed_key(g)
        g.vars[key] = g.vars.get(key, 0) + 1
        g.status(f"{v.prefix} the enlightenment spent no strange dust, not counted")
        g.save_diagnostic("enlighten-not-taken.png")
        v.stop = "unconfirmed"
        return False
    v.dust = after
    spent = dust - after
    cost = v.unit * m
    count = m if spent == cost else spent // v.unit
    daily.note_enlighten(s, count, spent)
    v.made += count
    if spent > cost:
        # the label read x{m} but the screen held more: the click bought several at once
        g.vars[_blocked_key(g)] = 1
        g.status(
            f"{v.prefix} one click took {spent:,} strange dust instead of {cost}, the "
            f"multiplier is not x{m}: no more enlightenments today"
        )
        g.save_diagnostic("enlighten-multiplier.png")
        v.stop = "blocked"
        return False
    _report(g, v, m, after)
    if spent < cost:
        g.status(f"{v.prefix} the click took {spent} strange dust instead of {cost}, stopping")
        v.stop = "partial"
        return False
    return True


def _report(g: Game, v: _Visit, m: int, left: int | None) -> None:
    s = g.settings
    count = daily._int(s, "EnlightenCountDaily")
    limit = daily.enlighten_limit(s) if daily.enlighten_on(s) else daily.EVENT_ENLIGHTENMENTS
    today = f"{count}/{limit}" if limit > 0 else f"{count}"
    dust = "dust counter unreadable" if left is None else f"{left:,} left"
    g.status(
        f"{v.prefix} guardian {train_position(g)} x{m} ({today} today, "
        f"{daily._int(s, 'EnlightenDustDaily'):,} dust today, {dust})"
    )


def _say_once(g: Game, reason: str, text: str) -> None:
    """A status line said once per game day per reason (the checks run every cycle)."""
    key = f"enlighten_said:{reason}:{_day(g)}"
    if not g.vars.get(key):
        g.vars[key] = 1
        g.status(text)


def _nothing(g: Game, v: _Visit, dust: int | None, m: int) -> None:
    """The budget allows no click at x`m`: say why (once a day) and end the visit."""
    s = g.settings
    need = v.unit * m
    reserve = daily.enlighten_reserve(s)
    dust_left = daily.enlighten_dust_left(s)
    count_left = daily.enlighten_count_left(s)
    if dust is None:
        v.stop = "unread"
        text = "the strange dust counter is not readable, nothing spent"
    elif reserve and dust - reserve < need:
        v.stop = "reserve"
        text = f"{dust:,} strange dust, the {reserve:,} kept in reserve are not spent"
    elif dust_left is not None and dust_left < need:
        v.stop = "cap"
        text = f"today's cap of {daily._int(s, 'MaxEnlightenDust'):,} strange dust is reached"
    elif count_left is not None and count_left < m:
        v.stop = "count"
        text = "today's enlightenments are done"
    else:
        v.stop = "poor"
        text = f"{dust:,} strange dust, not enough for an enlightenment"
    _say_once(g, v.stop, f"{v.prefix} {text}")
