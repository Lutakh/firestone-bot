"""Logging handler that forwards records to the GUI queue (no Tk calls, any thread)."""

from __future__ import annotations

import logging
import queue


class QueueLogHandler(logging.Handler):
    def __init__(self, ui_queue: queue.Queue, level: int = logging.INFO) -> None:
        super().__init__(level)
        self.ui_queue = ui_queue
        self.setFormatter(logging.Formatter("%(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.ui_queue.put(("log", self.format(record)))
        except Exception:  # noqa: BLE001
            self.handleError(record)
