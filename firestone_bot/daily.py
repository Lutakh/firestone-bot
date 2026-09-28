"""Daily counters (Python-only feature, not in the AHK bot).

The game day is detected by the free mystery box of the daily shop becoming claimable again
(see features/shop.py). Everything is persisted in settings.ini so a restarted bot keeps its
counters:

    [CommonOptions]
    MaxTokens=12          user setting: tavern tokens the bot may use per game day (0 = no limit)
    TokenCountDaily=3     tokens used since the last detected reset
    LastTokenReset=...    timestamp of the last detected daily reset (AHK A_Now format)
    ArenaDoneDaily=1      the five arena battles were done since the last reset
    MaxChaos=10           chaos rift hits with FREE tokens per game day (0 = no limit)
    ChaosCountDaily=4     hits since the last reset
    MaxScarab=10          scarab game plays with FREE tokens per game day (0 = no limit)
    ScarabCountDaily=2    plays since the last reset
    MaxCrystals=5         pickaxe hits on the guild's arcane crystal per game day (0 = no limit)
    CrystalCountDaily=3   hits since the last reset
    MaxEnlighten=3        guardian enlightenments per game day (0 = no limit)
    MaxEnlightenDust=0    strange dust spent on them per game day (0 = no limit)
    EnlightenDustReserve=0 strange dust always kept (0 = none)
    EnlightenCountDaily=1 guardian enlightenments since the last reset (event and automation)
    EnlightenDustDaily=20 strange dust they took since the last reset

While the Decorated Heroes event switch is on ([PythonOptions] EventDecoratedHeroes=1), the
tavern and crystal limits are raised to the event's daily challenges (12 plays, 15 hits)
when lower, and the bot enlightens a guardian 3 times a day. The enlightenment automation
([PythonOptions] GuardianEnlighten=1, owner request 2026-09-28) spends more strange dust
within the three limits above, the strictest winning; the event's 3 are made whatever its
dust cap and reserve say, and count toward its totals.
"""

from __future__ import annotations

import logging

from firestone_bot.settings import Settings
from firestone_bot.state import ahk_now

log = logging.getLogger("firestone_bot.daily")


def _int(settings: Settings, name: str) -> int:
    try:
        return int(settings.get(name).strip() or 0)
    except ValueError:
        return 0


def mark_daily_reset(settings: Settings) -> None:
    """The daily shop free box was claimable: a new game day started."""
    settings.set("LastTokenReset", ahk_now())
    settings.set("TokenCountDaily", 0)
    settings.set("ArenaDoneDaily", 0)
    settings.set("ChaosCountDaily", 0)
    settings.set("LastChaosReset", settings.get("LastTokenReset"))
    settings.set("ScarabCountDaily", 0)
    settings.set("ChaosBooksDaily", 0)
    settings.set("MailSweepDaily", 0)
    settings.set("CrystalCountDaily", 0)
    settings.set("EnlightenCountDaily", 0)
    settings.set("EnlightenDustDaily", 0)
    settings.save()
    log.info("daily reset detected: token and arena counters cleared")


# Decorated Heroes event: the top tier of its daily challenges (wiki, checked in game
# 2026-09-25: "Play 12 times with the cards at the tavern", "Hit the arcane crystal 15
# times", "Enlighten guardians 3 times").
EVENT_TAVERN_PLAYS = 12
EVENT_CRYSTAL_HITS = 15
EVENT_ENLIGHTENMENTS = 3


def event_on(settings: Settings) -> bool:
    return settings.flag("EventDecoratedHeroes")


def _event_limit(settings: Settings, key: str, own_switch_on: bool, event: int) -> int:
    """The daily limit in force (0 = no limit): the user's, raised to the event's challenge
    while the event switch is on. With the user's own switch off, the event alone asks for
    exactly its challenge (a stored 0 = "no limit" must not start spending everything)."""
    limit = _int(settings, key)
    if not event_on(settings):
        return limit
    if not own_switch_on:
        return event
    return event if 0 < limit < event else limit


def token_limit(settings: Settings) -> int:
    return _event_limit(settings, "MaxTokens", settings.flag("Token"), EVENT_TAVERN_PLAYS)


def crystal_limit(settings: Settings) -> int:
    return _event_limit(settings, "MaxCrystals", settings.flag("Crystal"), EVENT_CRYSTAL_HITS)


# -- guardian enlightenment ------------------------------------------------------------------
# One enlightenment costs 20 strange dust; the screen's multiplier buys 1, 5, 10 or 20 at once
# for 20 x N ("Enlightenment 1 / 20" ... "Enlightenment 20 / 400", measured 2026-09-28).
# Every limit below is a number of enlightenments or of dust, never of clicks. The helpers
# return None for "no limit": test them against None, never for truthiness.
ENLIGHTEN_DUST = 20


def enlighten_on(settings: Settings) -> bool:
    """The enlightenment automation's own switch (the event alone does not turn it on)."""
    return settings.flag("GuardianEnlighten")


def event_enlighten_need(settings: Settings) -> int:
    """Enlightenments the Decorated Heroes event still needs today (0 when its switch is off)."""
    if not event_on(settings):
        return 0
    return max(0, EVENT_ENLIGHTENMENTS - _int(settings, "EnlightenCountDaily"))


def enlighten_limit(settings: Settings) -> int:
    """Enlightenments per game day in force (0 = no limit), raised to 3 by the event."""
    return _event_limit(settings, "MaxEnlighten", enlighten_on(settings), EVENT_ENLIGHTENMENTS)


def enlighten_count_left(settings: Settings) -> int | None:
    """None = no count limit, else enlightenments still allowed today; with the automation
    off, only what the event still needs (0 when it is off too)."""
    if not enlighten_on(settings):
        return event_enlighten_need(settings)
    limit = enlighten_limit(settings)
    if limit <= 0:
        return None
    return max(0, limit - _int(settings, "EnlightenCountDaily"))


def enlighten_dust_left(settings: Settings) -> int | None:
    """None = no daily dust cap (or the automation is off), else the strange dust it may
    still spend today."""
    cap = _int(settings, "MaxEnlightenDust")
    if not enlighten_on(settings) or cap <= 0:
        return None
    return max(0, cap - _int(settings, "EnlightenDustDaily"))


def enlighten_reserve(settings: Settings) -> int:
    """Strange dust the automation always keeps (the event alone keeps none)."""
    return _int(settings, "EnlightenDustReserve") if enlighten_on(settings) else 0


def enlighten_wanted(settings: Settings) -> bool:
    """Something may still be enlightened today as far as the counters tell (the dust itself
    is only read on the guardian screen)."""
    if event_enlighten_need(settings):
        return True
    if not enlighten_on(settings):
        return False
    dust_left = enlighten_dust_left(settings)
    return enlighten_count_left(settings) != 0 and (
        dust_left is None or dust_left >= ENLIGHTEN_DUST
    )


def plan_enlightenments(
    dust: int | None,
    unit: int,
    event_need: int,
    count_left: int | None,
    dust_left: int | None,
    reserve: int,
) -> int:
    """How many enlightenments may be done now (pure). `dust` is the counter (None when
    unreadable), `unit` the dust one enlightenment takes, `count_left` / `dust_left` None
    for no limit, `reserve` the dust always kept.

    The event's need is always allowed: whether it is affordable is the button's business
    (grey without dust), as before the automation. The automation's own allowance needs the
    counter to honour a dust cap or a reserve; unreadable, it may only make x1 clicks up to
    a count limit that is its sole limit (a click then counts as made, as the event's did),
    and with no limit at all it spends nothing it cannot see."""
    if dust is None:
        own = 0
        if count_left is not None and dust_left is None and reserve <= 0:
            own = count_left
        return max(event_need, own)
    own = (dust - max(reserve, 0)) // unit
    if dust_left is not None:
        own = min(own, dust_left // unit)
    if count_left is not None:
        own = min(own, count_left)
    return max(event_need, own, 0)


def enlightenments_allowed(settings: Settings, dust: int | None, unit: int = ENLIGHTEN_DUST) -> int:
    """plan_enlightenments with today's counters and the user's limits."""
    return plan_enlightenments(
        dust,
        unit,
        event_enlighten_need(settings),
        enlighten_count_left(settings),
        enlighten_dust_left(settings),
        enlighten_reserve(settings),
    )


def note_enlighten(settings: Settings, count: int = 1, dust: int = ENLIGHTEN_DUST) -> None:
    """`count` enlightenments that took `dust` (one x20 click: 20 and 400), one save."""
    settings.set("EnlightenCountDaily", _int(settings, "EnlightenCountDaily") + count)
    settings.set("EnlightenDustDaily", _int(settings, "EnlightenDustDaily") + dust)
    settings.save()


def tokens_left(settings: Settings) -> int | None:
    """None = unlimited (MaxTokens is 0), else how many tokens may still be used today."""
    limit = token_limit(settings)
    if limit <= 0:
        return None
    return max(0, limit - _int(settings, "TokenCountDaily"))


def note_token_used(settings: Settings) -> None:
    settings.set("TokenCountDaily", _int(settings, "TokenCountDaily") + 1)
    settings.save()


def arena_done(settings: Settings) -> bool:
    return _int(settings, "ArenaDoneDaily") == 1


def note_arena_done(settings: Settings) -> None:
    settings.set("ArenaDoneDaily", 1)
    settings.save()


def chaos_left(settings: Settings) -> int | None:
    """None = unlimited (MaxChaos is 0), else free-token hits still allowed today."""
    limit = _int(settings, "MaxChaos")
    if limit <= 0:
        return None
    return max(0, limit - _int(settings, "ChaosCountDaily"))


def note_chaos_hit(settings: Settings) -> None:
    settings.set("ChaosCountDaily", _int(settings, "ChaosCountDaily") + 1)
    settings.save()


def scarab_left(settings: Settings) -> int | None:
    """None = unlimited (MaxScarab is 0), else free-token plays still allowed today."""
    limit = _int(settings, "MaxScarab")
    if limit <= 0:
        return None
    return max(0, limit - _int(settings, "ScarabCountDaily"))


def note_scarab_play(settings: Settings) -> None:
    settings.set("ScarabCountDaily", _int(settings, "ScarabCountDaily") + 1)
    settings.save()


def mail_swept(settings: Settings) -> bool:
    return _int(settings, "MailSweepDaily") == 1


def note_mail_swept(settings: Settings) -> None:
    settings.set("MailSweepDaily", 1)
    settings.save()


def books_done(settings: Settings) -> bool:
    return _int(settings, "ChaosBooksDaily") == 1


def note_books_done(settings: Settings) -> None:
    settings.set("ChaosBooksDaily", 1)
    settings.save()


def crystal_left(settings: Settings) -> int | None:
    """None = unlimited (MaxCrystals is 0), else crystal hits still allowed today."""
    limit = crystal_limit(settings)
    if limit <= 0:
        return None
    return max(0, limit - _int(settings, "CrystalCountDaily"))


def note_crystal_hit(settings: Settings) -> None:
    settings.set("CrystalCountDaily", _int(settings, "CrystalCountDaily") + 1)
    settings.save()
