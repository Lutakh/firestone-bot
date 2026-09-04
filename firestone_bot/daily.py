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
    settings.save()
    log.info("daily reset detected: token and arena counters cleared")


def tokens_left(settings: Settings) -> int | None:
    """None = unlimited (MaxTokens is 0), else how many tokens may still be used today."""
    limit = _int(settings, "MaxTokens")
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
