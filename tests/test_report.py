"""Send report: the zip (docs/REPORT_API.md), the environment line in the log, the upload."""

from __future__ import annotations

import http.client
import io
import json
import logging
import os
import ssl
import time
import urllib.error
import urllib.parse
import zipfile

import pytest

from firestone_bot import __version__, report

SETTINGS = (
    "[Settings]\nDiscordID=123456789012345678\nMapReset=0\n"
    "[SettingsNoGui]\nClientID=20261022120000-123456\nEnableHeartbeat=1\n"
)


def _base(tmp_path, captures=(), logs=None):
    for name, text in (logs or {"firestone-bot.log": "today\n"}).items():
        (tmp_path / name).write_bytes(text.encode("utf-8"))
    folder = tmp_path / "diagnostics"
    folder.mkdir()
    now = time.time()
    for i, (name, size) in enumerate(captures):
        path = folder / name
        path.write_bytes(b"\x89PNG" + b"x" * (size - 4))
        os.utime(path, (now - 60 * i, now - 60 * i))  # the first is the newest
    return str(tmp_path)


def _zip(data: bytes) -> zipfile.ZipFile:
    return zipfile.ZipFile(io.BytesIO(data))


def test_settings_leave_the_discord_id_and_client_id_out():
    text = report.strip_private(SETTINGS + "discordid = 42\n")
    assert "DiscordID" not in text and "ClientID" not in text and "discordid" not in text
    assert "123456789012345678" not in text
    assert "MapReset=0" in text and "EnableHeartbeat=1" in text and "[Settings]" in text


def test_the_zip_holds_logs_settings_captures_and_report_json(tmp_path):
    base = _base(
        tmp_path,
        captures=[("20261022-120000-a.png", 1000), ("20261021-120000-b.png", 1000)],
        logs={
            "firestone-bot.log": 'x Environment: {"client": "1920x1009"}\ntoday\n',
            "firestone-bot.log.2026-10-21": "yesterday\n",
        },
    )
    z = _zip(report.build(base, SETTINGS, "note é", {"dpi": "a"}))
    names = z.namelist()
    assert "logs/firestone-bot.log" in names and "logs/firestone-bot.log.2026-10-21" in names
    assert "settings.ini" in names
    assert "diagnostics/20261022-120000-a.png" in names
    info = json.loads(z.read("report.json"))
    assert info["version"] == __version__ and info["platform"] in ("windows", "macos", "linux")
    assert "client_id" not in info  # the server has it from the header
    assert info["note"] == "note é"
    assert info["system"]["bot_version"] == __version__ and info["system"]["os"]
    assert info["environment"] == {"client": "1920x1009"}
    assert info["environment_now"] == {"dpi": "a"}
    assert set(info["files"]) == set(names) - {"report.json"}
    assert b"123456789012345678" not in z.read("settings.ini")


def test_without_captures(tmp_path):
    base = _base(tmp_path, captures=[("20261022-120000-a.png", 1000)])
    names = _zip(report.build(base, SETTINGS, captures=False)).namelist()
    assert not [n for n in names if n.startswith("diagnostics/")]


def test_the_home_folder_is_replaced_in_the_logs(tmp_path):
    home = os.path.expanduser("~")
    line = f"updater started: {home}\\FirestoneBot -> {home.replace(chr(92), '/')}/x\n"
    base = _base(tmp_path, logs={"firestone-bot.log": line})
    text = _zip(report.build(base)).read("logs/firestone-bot.log").decode()
    assert home not in text and home.replace("\\", "/") not in text
    assert "~" in text


def test_the_newest_log_text_within_its_budget(tmp_path):
    today = "".join(f"line {i:05d}\n" for i in range(2000))  # 22 kB
    base = _base(
        tmp_path, logs={"firestone-bot.log": today, "firestone-bot.log.2026-10-21": "old\n"}
    )
    z = _zip(report.build(base, log_budget=1000))
    text = z.read("logs/firestone-bot.log").decode()
    assert text.endswith("line 01999\n") and text.startswith("line ")  # whole lines, the end
    assert len(text) <= 1000
    assert "logs/firestone-bot.log.2026-10-21" not in z.namelist()  # cut: older days left out


def test_captures_newest_first_within_the_size_cap(tmp_path):
    captures = [(f"2026102{i}-c{i}.png", 300_000) for i in range(6)]
    base = _base(tmp_path, captures=captures)
    data = report.build(base, SETTINGS, max_bytes=1_200_000)
    assert len(data) <= 1_200_000
    kept = [n for n in _zip(data).namelist() if n.startswith("diagnostics/")]
    assert kept == [
        "diagnostics/20261020-c0.png",
        "diagnostics/20261021-c1.png",
        "diagnostics/20261022-c2.png",
    ]


def test_the_last_environment_line_wins_newest_file_first(tmp_path):
    base = _base(
        tmp_path,
        logs={
            "firestone-bot.log": "no environment today\n",
            "firestone-bot.log.2026-10-21": 'a Environment: {"v": 1}\nb Environment: {"v": 2}\n',
            "firestone-bot.log.2026-10-20": 'c Environment: {"v": 0}\n',
        },
    )
    assert report.last_environment(base) == {"v": 2}


@pytest.fixture
def fresh_env(monkeypatch, caplog):
    monkeypatch.setattr(report, "_env", {})
    monkeypatch.setattr(report, "_env_logged", "")
    caplog.set_level(logging.INFO, logger="firestone_bot.report")

    def lines():
        return [r.getMessage() for r in caplog.records if report.ENV_MARK in r.getMessage()]

    return lines


def _env_of(line: str) -> dict:
    return json.loads(line.split(report.ENV_MARK, 1)[1])


def test_the_environment_is_logged_once_and_again_when_it_changes(fresh_env):
    report.note_environment({"client": "1920x1009", "capture": "OK 1920x1009 in 12 ms"})
    report.note_environment({"client": "1920x1009", "capture": "OK 1920x1009 in 30 ms"})
    assert len(fresh_env()) == 1
    env = _env_of(fresh_env()[0])
    assert env["client"] == "1920x1009" and env["bot_version"] == __version__
    report.note_environment({"style": "new"})
    assert len(fresh_env()) == 2
    env = _env_of(fresh_env()[1])
    assert env["style"] == "new" and env["client"] == "1920x1009"


def test_the_environment_is_logged_again_the_next_day(fresh_env, monkeypatch):
    report.note_environment({"client": "1920x1009"})
    monkeypatch.setattr(report.time, "strftime", lambda fmt, *a: "2099-01-01 ")
    report.note_environment({"client": "1920x1009"})
    assert len(fresh_env()) == 2


def test_a_new_window_drops_the_old_capture_size(fresh_env):
    report.note_environment({"client": "1920x1009", "capture": "OK 1920x1009 in 9 ms"})
    report.note_environment({"client": "2560x1349"})  # the runner knows no capture
    assert _env_of(fresh_env()[-1])["capture"] == "-"


class _Answer(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_upload_sends_the_contract_headers_and_streams_the_body(monkeypatch):
    seen = {}

    def urlopen(req, timeout, context):
        seen.update(req=req, timeout=timeout, context=context, body=req.data.read())
        return _Answer(b'{"id": "7F3K2Q", "size": 3, "expires": "2026-11-21"}')

    monkeypatch.setattr(report.urllib.request, "urlopen", urlopen)
    note = "Ça bloque " + "x" * 600
    answer = report.upload(b"PK\x03\x04", "cid", " 123 ", note)
    assert answer["id"] == "7F3K2Q"
    req = seen["req"]
    assert req.full_url == report.REPORT_URL and req.get_method() == "POST"
    assert seen["body"] == b"PK\x03\x04"  # a file body: sent block by block
    assert isinstance(seen["context"], ssl.SSLContext)  # certifi roots for the macOS bundle
    headers = {k.lower(): v for k, v in req.header_items()}
    assert headers["content-length"] == "4"  # not chunked
    assert headers["content-type"] == "application/zip"
    assert headers["x-client-id"] == "cid" and headers["x-bot-version"] == __version__
    assert headers["x-platform"] in ("windows", "macos", "linux")
    assert headers["x-discord-id"] == "123"
    decoded = urllib.parse.unquote(headers["x-report-note"])
    assert decoded.startswith("Ça bloque") and len(decoded) == report.NOTE_MAX
    assert headers["x-report-note"].isascii()


@pytest.mark.parametrize("discord", ["", "  ", "１２３", "abc"])
def test_upload_without_a_plain_discord_id_or_note_sends_neither(monkeypatch, discord):
    seen = {}

    def urlopen(req, timeout, context):
        seen["headers"] = {k.lower() for k, _ in req.header_items()}
        return _Answer(b'{"id": "ABCDEF"}')

    monkeypatch.setattr(report.urllib.request, "urlopen", urlopen)
    report.upload(b"PK\x03\x04", "cid", discord, "  ")
    assert "x-discord-id" not in seen["headers"] and "x-report-note" not in seen["headers"]


def _http_error(code, body, headers=None):
    return urllib.error.HTTPError(report.REPORT_URL, code, "x", headers or {}, io.BytesIO(body))


@pytest.mark.parametrize(
    ("error", "said"),
    [
        (_http_error(429, b'{"error": "too many reports", "retry_after": 1800}'), "30 min"),
        (_http_error(413, b'{"error": "too large"}'), "too large"),
        (_http_error(400, b'{"error": "body is not a zip"}'), "body is not a zip"),
        (_http_error(502, b"<html>bad gateway</html>"), "refused it \\(502"),
        (urllib.error.URLError("timed out"), "did not answer"),
        (urllib.error.URLError(ConnectionAbortedError(10053, "aborted")), "cut the connection"),
        (http.client.IncompleteRead(b"x", 10), "did not answer"),
    ],
)
def test_upload_failures_are_said_plainly(monkeypatch, error, said):
    def urlopen(req, timeout, context):
        raise error

    monkeypatch.setattr(report.urllib.request, "urlopen", urlopen)
    with pytest.raises(report.ReportError, match=said):
        report.upload(b"PK\x03\x04", "cid")


@pytest.mark.parametrize(("body", "said"), [(b"not json", "unreadable"), (b"{}", "no report ID")])
def test_an_odd_answer_is_said_plainly(monkeypatch, body, said):
    monkeypatch.setattr(
        report.urllib.request, "urlopen", lambda req, timeout, context: _Answer(body)
    )
    with pytest.raises(report.ReportError, match=said):
        report.upload(b"PK\x03\x04", "cid")
