"""The log file rolls over daily and keeps 7 days (the owner's single log reached 131 MB,
2026-10-22); a file Windows will not rename keeps the log going in the same file."""

from __future__ import annotations

import logging
import os
import time

from firestone_bot import logfile


def _logger(handler):
    log = logging.getLogger(f"test-logfile-{id(handler)}")
    log.propagate = False
    log.handlers = [handler]
    log.setLevel(logging.INFO)
    return log


def test_a_rollover_keeps_seven_days(tmp_path):
    for day in range(1, 10):  # nine days already kept
        (tmp_path / f"{logfile.LOG_NAME}.2026-10-0{day}").write_text("old")
    h = logfile.handler(str(tmp_path))
    log = _logger(h)
    log.info("before midnight")
    h.rolloverAt = int(time.time()) - 1  # midnight has passed
    log.info("after midnight")
    h.close()
    kept = [n for n in os.listdir(tmp_path) if n.startswith(logfile.LOG_NAME + ".")]
    assert len(kept) == logfile.KEEP_DAYS
    assert "after midnight" in (tmp_path / logfile.LOG_NAME).read_text()
    assert "before midnight" not in (tmp_path / logfile.LOG_NAME).read_text()


def test_a_file_that_cannot_be_renamed_keeps_the_log_going(tmp_path, monkeypatch):
    h = logfile.handler(str(tmp_path))
    log = _logger(h)
    log.info("one")

    def refuse(src, dst):
        raise PermissionError("in use")

    monkeypatch.setattr(os, "rename", refuse)
    monkeypatch.setattr(logfile.TimedRotatingFileHandler, "rotate", lambda self, s, d: refuse(s, d))
    h.rolloverAt = int(time.time()) - 1
    log.info("two")
    log.info("three")
    h.close()
    text = (tmp_path / logfile.LOG_NAME).read_text()
    assert "one" in text and "two" in text and "three" in text
    assert h.rolloverAt > time.time()  # the next try is the next midnight, not every line


def test_log_files_newest_first(tmp_path):
    (tmp_path / logfile.LOG_NAME).write_text("today")
    (tmp_path / f"{logfile.LOG_NAME}.2026-10-20").write_text("a")
    (tmp_path / f"{logfile.LOG_NAME}.2026-10-21").write_text("b")
    names = [os.path.basename(p) for p in logfile.log_files(str(tmp_path))]
    assert names == [
        logfile.LOG_NAME,
        f"{logfile.LOG_NAME}.2026-10-21",
        f"{logfile.LOG_NAME}.2026-10-20",
    ]
