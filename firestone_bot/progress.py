"""Account progress: what the account can already do (owner request 2026-09-06).

A new account has most town and guild features locked behind an account level (the
engineer at 50, the alchemist at 120, the oracle at 200...) and some guild features behind
the guild level. The AHK bot clicked them anyway and closed the "reach level N" popup; the
rework reads the levels and skips a locked feature, without touching the user's options:
the feature runs as soon as the account qualifies.

- The account level is read on the avatar at every cycle start until it reaches
  ALL_UNLOCKED_LEVEL (200, everything unlocked): from then on the check is skipped.
- The guild level is read on the guild map (top-left banner) until it reaches
  GUILD_ALL_LEVEL (5); the read is retried a few times as the map settles.
- An unreadable number never gates anything (a misread would silently disable features on
  a layout the reader was not tuned for); it is logged and the previous value is kept.

Levels are remembered in progress.json next to the other user files.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass

log = logging.getLogger("firestone_bot.progress")

ALL_UNLOCKED_LEVEL = 200
GUILD_ALL_LEVEL = 5

# feature -> account level (from the game's unlock popups, 2026-09-06)
ACCOUNT_LEVELS = {
    "engineer": 50,
    "arena": 50,
    "scarab": 60,
    "emblem_chests": 65,
    "alchemist": 120,
    "oracle": 200,
    "guild_awaken": 50,
    "guild_crystal": 50,
    "guild_chaos": 100,
}
GUILD_LEVELS = {"guild_crystal": 5}
LABELS = {
    "engineer": "Engineer",
    "arena": "Arena",
    "scarab": "Scarab game",
    "emblem_chests": "Emblem chests (exotic merchant)",
    "alchemist": "Alchemist",
    "oracle": "Oracle",
    "guild_awaken": "Hero awakening",
    "guild_crystal": "Arcane crystal",
    "guild_chaos": "Chaos rift",
}


@dataclass
class Progress:
    account_level: int | None = None
    guild_level: int | None = None
    account_read_at: float = 0.0
    guild_read_at: float = 0.0

    # -- persistence ------------------------------------------------------------------------
    @classmethod
    def load(cls, path: str) -> Progress:
        p = cls()
        p.path = path
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            p.account_level = _int_or_none(data.get("account_level"))
            p.guild_level = _int_or_none(data.get("guild_level"))
            p.account_read_at = float(data.get("account_read_at") or 0)
            p.guild_read_at = float(data.get("guild_read_at") or 0)
        except (OSError, ValueError):
            pass
        return p

    def save(self) -> None:
        path = getattr(self, "path", "")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(asdict(self), f, indent=2)
        except OSError:
            log.exception("cannot write %s", path)

    # -- updates ----------------------------------------------------------------------------
    def need_account_check(self) -> bool:
        return self.account_level is None or self.account_level < ALL_UNLOCKED_LEVEL

    def need_guild_check(self) -> bool:
        return self.guild_level is None or self.guild_level < GUILD_ALL_LEVEL

    def set_account_level(self, level: int | None) -> None:
        self.account_read_at = time.time()
        if level is None:
            return
        if self.account_level != level:
            log.info("account level %s", level)
        self.account_level = level
        self.save()

    def set_guild_level(self, level: int | None) -> None:
        self.guild_read_at = time.time()
        if level is None:
            return
        if self.guild_level != level:
            log.info("guild level %s", level)
        self.guild_level = level
        self.save()

    # -- gating -----------------------------------------------------------------------------
    def locked_reason(self, feature: str) -> str | None:
        """Why `feature` is skipped for now, None when it may run (or is unknown)."""
        need = ACCOUNT_LEVELS.get(feature)
        if need and self.account_level is not None and self.account_level < need:
            return f"needs account level {need} (now {self.account_level})"
        need = GUILD_LEVELS.get(feature)
        if need and self.guild_level is not None and self.guild_level < need:
            return f"needs guild level {need} (now {self.guild_level})"
        return None

    def summary(self) -> str:
        acc = "?" if self.account_level is None else str(self.account_level)
        gld = "?" if self.guild_level is None else str(self.guild_level)
        return f"account level {acc}, guild level {gld}"


def _int_or_none(v) -> int | None:
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None
