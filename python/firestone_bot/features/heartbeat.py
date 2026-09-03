"""Port of Functions/SendHeartbeat.ahk: opt-in JSON POST to the owner's log server.

Only when `[SettingsNoGui] EnableHeartbeat=1`. The client id is generated once and stored in
settings.ini like the AHK version (`ClientID=YYYYMMDDHHMMSS-random`).
"""

from __future__ import annotations

import json
import logging
import random
import urllib.request

from firestone_bot.settings import Settings
from firestone_bot.state import ahk_now

SERVER_URL = "https://fs-bot-logs.lutak.ovh/api/heartbeat"
log = logging.getLogger("firestone_bot.heartbeat")


def get_unique_id(settings: Settings) -> str:
    stored = settings.get("ClientID").strip()
    if stored:
        return stored
    new_id = f"{ahk_now()}-{random.randint(100000, 999999)}"
    settings.set("ClientID", new_id)
    settings.save()
    return new_id


def send_heartbeat(
    settings: Settings, msg: str, is_stop: bool = False, important: bool = False
) -> None:
    if not settings.flag("EnableHeartbeat"):
        return
    payload = {
        "client_id": get_unique_id(settings),
        "discord_id": settings.get("DiscordID") or "0",
        "message": msg,
        "is_stop": is_stop,
        "is_important": important,
    }
    req = urllib.request.Request(
        SERVER_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10):
            pass
    except Exception as e:  # noqa: BLE001 - AHK swallows every error here
        log.debug("heartbeat failed: %s", e)
