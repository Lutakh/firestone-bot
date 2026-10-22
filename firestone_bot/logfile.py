"""The bot's log file: one file a day, the last 7 days kept.

firestone-bot.log is always today's file; at midnight it becomes firestone-bot.log.YYYY-MM-DD
and the oldest beyond KEEP_DAYS are deleted (the owner's single log had grown to 131 MB,
2026-10-22). A file left from a previous day is rolled over at the first line of the day.
"""

from __future__ import annotations

import logging
import os
import time
from logging.handlers import TimedRotatingFileHandler

LOG_NAME = "firestone-bot.log"
KEEP_DAYS = 7


class DailyLogHandler(TimedRotatingFileHandler):
    """TimedRotatingFileHandler that survives a file it cannot rename or delete: Windows does
    not let a file another program keeps open (an editor, an antivirus scan) be renamed. The
    log then goes on in the same file and the next midnight tries again, instead of an error
    at every line."""

    def __init__(self, path: str, keep_days: int = KEEP_DAYS) -> None:
        super().__init__(path, when="midnight", backupCount=keep_days, encoding="utf-8")

    def doRollover(self) -> None:
        try:
            super().doRollover()
        except OSError:
            if self.stream is None:
                self.stream = self._open()
            self.rolloverAt = self.computeRollover(int(time.time()))


def log_files(base: str) -> list[str]:
    """Today's log and the kept days, newest first (for a report or the GUI)."""
    path = os.path.join(base, LOG_NAME)
    try:
        names = os.listdir(base)
    except OSError:
        return []
    days = sorted((n for n in names if n.startswith(LOG_NAME + ".")), reverse=True)
    out = [path] if os.path.exists(path) else []
    return out + [os.path.join(base, n) for n in days]


def handler(base: str) -> logging.Handler:
    return DailyLogHandler(os.path.join(base, LOG_NAME))
