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
    EnlightenCountDaily=1 guardian enlightenments since the last reset (Decorated Heroes event)

While the Decorated Heroes event switch is on ([PythonOptions] EventDecoratedHeroes=1), the
tavern and crystal limits are raised to the event's daily challenges (12 plays, 15 hits)
when lower, and the bot enlightens a guardian 3 times a day.
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


def enlighten_left(settings: Settings) -> int:
    """Guardian enlightenments still to do today (0 unless the event switch is on)."""
    if not event_on(settings):
        return 0
    return max(0, EVENT_ENLIGHTENMENTS - _int(settings, "EnlightenCountDaily"))


def note_enlighten(settings: Settings) -> None:
    settings.set("EnlightenCountDaily", _int(settings, "EnlightenCountDaily") + 1)
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
