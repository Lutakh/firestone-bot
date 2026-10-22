"""The heartbeat never makes the bot wait: a slow or unreachable log server only loses
messages (owner, 2026-10-22)."""

from __future__ import annotations

import threading
import time

from firestone_bot.features import heartbeat


class _Settings:
    def __init__(self, enabled: bool = True, discord: str = "123") -> None:
        self.values = {
            "EnableHeartbeat": "1" if enabled else "0",
            "DiscordID": discord,
            "ClientID": "20261022120000-123456",
        }

    def flag(self, key: str) -> bool:
        return self.values.get(key) == "1"

    def get(self, key: str) -> str:
        return self.values.get(key, "")

    def set(self, key: str, value: str) -> None:
        self.values[key] = value

    def save(self) -> None:
        pass


def _blocking_post(release: threading.Event, sent: list):
    def post(payload: dict) -> None:
        release.wait(10)
        sent.append(payload)

    return post


def test_a_hanging_server_does_not_slow_the_caller(monkeypatch):
    release, sent = threading.Event(), []
    monkeypatch.setattr(heartbeat, "_sender", heartbeat.Sender(_blocking_post(release, sent)))
    start = time.monotonic()
    for i in range(heartbeat.QUEUE_MAX * 2):
        heartbeat.send_heartbeat(_Settings(), f"msg {i}")
    assert time.monotonic() - start < 0.5
    release.set()
    heartbeat.flush(5)
    assert sent and sent[0]["message"] == "msg 0"
    assert sent[0]["client_id"] == "20261022120000-123456"


def test_a_full_queue_drops_messages():
    release, sent = threading.Event(), []
    sender = heartbeat.Sender(_blocking_post(release, sent))
    accepted = sum(sender.submit({"message": i}) for i in range(heartbeat.QUEUE_MAX + 10))
    # the thread holds one message while the queue fills up
    assert heartbeat.QUEUE_MAX <= accepted <= heartbeat.QUEUE_MAX + 1
    release.set()
    sender.flush(5)
    assert len(sent) == accepted


def test_a_failed_send_drops_messages_for_a_while():
    calls = []

    def post(payload: dict) -> None:
        calls.append(payload)
        raise OSError("name resolution failed")

    sender = heartbeat.Sender(post)
    assert sender.submit({"message": "first"})
    sender.flush(5)
    assert len(calls) == 1
    assert sender.down_until > time.monotonic() + heartbeat.BACKOFF_S - 5
    assert not sender.submit({"message": "second"})
    sender.flush(1)
    assert len(calls) == 1
    sender.down_until = 0.0  # the pause is over
    assert sender.submit({"message": "third"})
    sender.flush(5)
    assert [c["message"] for c in calls] == ["first", "third"]


def test_off_or_without_discord_id_sends_nothing(monkeypatch):
    sent = []
    monkeypatch.setattr(heartbeat, "_sender", heartbeat.Sender(sent.append))
    heartbeat.send_heartbeat(_Settings(enabled=False), "off")
    heartbeat.send_heartbeat(_Settings(discord=" "), "no id")
    heartbeat.flush(1)
    assert sent == []
    heartbeat.send_heartbeat(_Settings(), "on", is_stop=True, important=True)
    heartbeat.flush(5)
    assert sent == [
        {
            "client_id": "20261022120000-123456",
            "discord_id": "123",
            "message": "on",
            "is_stop": True,
            "is_important": True,
        }
    ]


def test_flush_gives_up_after_its_timeout():
    release = threading.Event()
    sender = heartbeat.Sender(_blocking_post(release, []))
    sender.submit({"message": "exit"})
    start = time.monotonic()
    sender.flush(0.3)
    assert time.monotonic() - start < 1
    release.set()
