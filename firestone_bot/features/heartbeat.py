"""Port of Functions/SendHeartbeat.ahk: opt-in JSON POST to the owner's log server.

Only when `[SettingsNoGui] EnableHeartbeat=1`. The client id is generated once and stored in
settings.ini like the AHK version (`ClientID=YYYYMMDDHHMMSS-random`).

Never waited for by the bot: a message goes into a small queue that a background thread
sends with a short timeout. The AHK sent it on the spot, and a slow or unreachable server
slowed every click of the bot (heartbeat off by default since; owner, 2026-10-22: better no
message than a slower bot). A full queue drops the message; after a failed send, messages
are dropped for BACKOFF_S without trying (a broken DNS lookup is not bounded by the timeout).
"""

from __future__ import annotations

import json
import logging
import queue
import random
import threading
import time
import urllib.request

from firestone_bot.settings import Settings
from firestone_bot.state import ahk_now

SERVER_URL = "https://fs-bot-logs.lutak.ovh/api/heartbeat"
QUEUE_MAX = 32  # messages waiting to be sent; more are dropped
SEND_TIMEOUT_S = 5
BACKOFF_S = 300  # after a failed send, no message is tried for this long
log = logging.getLogger("firestone_bot.heartbeat")


def get_unique_id(settings: Settings) -> str:
    stored = settings.get("ClientID").strip()
    if stored:
        return stored
    new_id = f"{ahk_now()}-{random.randint(100000, 999999)}"
    settings.set("ClientID", new_id)
    settings.save()
    return new_id


def _post(payload: dict) -> None:
    req = urllib.request.Request(
        SERVER_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=SEND_TIMEOUT_S):
        pass


class Sender:
    """The queue and its background thread (started at the first message)."""

    def __init__(self, post=None) -> None:
        self.post = post or _post
        self.queue: queue.Queue = queue.Queue(QUEUE_MAX)
        self.thread: threading.Thread | None = None
        self.lock = threading.Lock()
        self.down_until = 0.0  # time.monotonic() until which messages are dropped
        self.failing = False  # said once until a send works again

    def submit(self, payload: dict) -> bool:
        """Queue a message without ever waiting; False when it was dropped."""
        if time.monotonic() < self.down_until:
            return False
        try:
            self.queue.put_nowait(payload)
        except queue.Full:
            return False
        with self.lock:
            if self.thread is None or not self.thread.is_alive():
                self.thread = threading.Thread(target=self._run, name="heartbeat", daemon=True)
                self.thread.start()
        return True

    def _run(self) -> None:
        while True:
            payload = self.queue.get()
            try:
                if time.monotonic() >= self.down_until:
                    self._send(payload)
            finally:
                self.queue.task_done()

    def _send(self, payload: dict) -> None:
        try:
            self.post(payload)
        except Exception as e:  # noqa: BLE001 - a heartbeat must never stop the bot
            self.down_until = time.monotonic() + BACKOFF_S
            level = logging.DEBUG if self.failing else logging.INFO
            log.log(
                level,
                "Heartbeat: the log server did not answer (%s); messages dropped for %d min",
                e,
                BACKOFF_S // 60,
            )
            self.failing = True
        else:
            self.failing = False

    def flush(self, timeout_s: float) -> None:
        """Wait up to `timeout_s` for the queued messages (the last one, at exit)."""
        end = time.monotonic() + timeout_s
        while self.queue.unfinished_tasks and time.monotonic() < end:
            time.sleep(0.05)


_sender = Sender()


def send_heartbeat(
    settings: Settings, msg: str, is_stop: bool = False, important: bool = False
) -> None:
    # Opt-in only: the toggle must be on AND a Discord ID must be set (owner decision).
    if not settings.flag("EnableHeartbeat") or not settings.get("DiscordID").strip():
        return
    payload = {
        "client_id": get_unique_id(settings),
        "discord_id": settings.get("DiscordID") or "0",
        "message": msg,
        "is_stop": is_stop,
        "is_important": important,
    }
    _sender.submit(payload)


def flush(timeout_s: float) -> None:
    _sender.flush(timeout_s)
