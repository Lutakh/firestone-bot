"""Send report dialog: built and sent off the Tk thread, the ID shown, a failure offers the file."""

from __future__ import annotations

import time
import tkinter as tk

import pytest

ctk = pytest.importorskip("customtkinter")

from firestone_bot import report
from firestone_bot.gui import theme
from firestone_bot.gui.report_dialog import ReportDialog
from firestone_bot.settings import Settings


@pytest.fixture
def root():
    theme.set_skin("Fieldbook")
    try:
        root = ctk.CTk()
    except tk.TclError as error:
        pytest.skip(f"no display: {error}")
    root.geometry("900x700")
    yield root
    root.destroy()


class _Settings(Settings):
    saves = 0

    def save(self, *args, **kwargs):  # the dialog must never save itself
        type(self).saves += 1


def _settings(tmp_path, client_id="20261022120000-123456", heartbeat="0"):
    settings = _Settings(path=str(tmp_path / "settings.ini"), loaded=True)
    settings.set("ClientID", client_id)
    settings.set("DiscordID", "123")
    settings.set("EnableHeartbeat", heartbeat)
    return settings


def _wait(root, dialog, text, timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        root.update()
        if text in dialog.status.cget("text"):
            return
        time.sleep(0.02)
    raise AssertionError(dialog.status.cget("text"))


def _fake(monkeypatch, fail=False):
    calls = {"build": [], "upload": []}

    def build(base, settings, note, env_now, captures=True):
        calls["build"].append({"settings": settings, "note": note, "captures": captures})
        return b"PK\x03\x04zip"

    def upload(data, client_id, discord_id, note):
        calls["upload"].append({"client_id": client_id, "discord_id": discord_id, "note": note})
        if fail:
            raise report.ReportError("the report server did not answer (timed out)")
        return {"id": "7F3K2Q", "size": len(data)}

    monkeypatch.setattr(report, "build", build)
    monkeypatch.setattr(report, "upload", upload)
    return calls


def test_sent_shows_the_report_id_once(root, tmp_path, monkeypatch):
    calls = _fake(monkeypatch)
    dialog = ReportDialog(root, str(tmp_path), _settings(tmp_path), {"dpi": "x"})
    dialog.note.insert("1.0", "The map spent gems")
    dialog._send()
    _wait(root, dialog, "Report sent: 7F3K2Q")
    assert calls["upload"] == [
        {"client_id": "20261022120000-123456", "discord_id": "", "note": "The map spent gems"}
    ]
    assert "DiscordID=123" in calls["build"][0]["settings"]  # stripped by build itself
    assert dialog.send_btn.cget("state") == "disabled"
    assert dialog.copy_btn.winfo_manager() == "pack"
    dialog._start(str(tmp_path / "copy.zip"))  # saving after a send...
    _wait(root, dialog, "Report saved")
    assert dialog.send_btn.cget("state") == "disabled"  # ...does not allow a second send
    dialog._close()


def test_the_discord_id_follows_the_heartbeat_and_the_box(root, tmp_path, monkeypatch):
    calls = _fake(monkeypatch)
    dialog = ReportDialog(root, str(tmp_path), _settings(tmp_path, heartbeat="1"))
    assert dialog.with_discord.get()
    dialog._send()
    _wait(root, dialog, "Report sent")
    assert calls["upload"][-1]["discord_id"] == "123"
    dialog._close()
    dialog = ReportDialog(root, str(tmp_path), _settings(tmp_path, heartbeat="1"))
    dialog.with_discord.set(False)
    dialog.with_captures.set(False)
    dialog._send()
    _wait(root, dialog, "Report sent")
    assert calls["upload"][-1]["discord_id"] == ""
    assert calls["build"][-1]["captures"] is False
    dialog._close()


def test_a_new_client_id_is_kept_without_saving_from_the_dialog(root, tmp_path, monkeypatch):
    _fake(monkeypatch)
    settings = _settings(tmp_path, client_id="")
    persisted = []
    _Settings.saves = 0
    dialog = ReportDialog(root, str(tmp_path), settings, persist=lambda: persisted.append(1))
    assert dialog.client_id and settings.get("ClientID") == dialog.client_id
    assert persisted == [1] and _Settings.saves == 0
    dialog._close()


def test_a_failed_upload_offers_the_file_and_reuses_the_zip(root, tmp_path, monkeypatch):
    calls = _fake(monkeypatch, fail=True)
    dialog = ReportDialog(root, str(tmp_path), _settings(tmp_path))
    dialog._send()
    _wait(root, dialog, "Not sent: the report server did not answer")
    assert dialog.save_btn.cget("state") == "normal"
    assert dialog.send_btn.cget("state") == "normal"  # nothing sent: may try again
    target = tmp_path / "out.zip"
    dialog._start(str(target))
    _wait(root, dialog, "Report saved: out.zip")
    assert target.read_bytes() == b"PK\x03\x04zip"
    assert len(calls["build"]) == 1  # same choices: the zip built for the send is saved
    dialog._close()


def test_closing_while_it_sends_only_hides_the_dialog(root, tmp_path, monkeypatch):
    import threading

    release = threading.Event()
    calls = _fake(monkeypatch)
    real_upload = report.upload

    def slow_upload(*args):
        release.wait(5)
        return real_upload(*args)

    monkeypatch.setattr(report, "upload", slow_upload)
    dialog = ReportDialog(root, str(tmp_path), _settings(tmp_path))
    dialog._send()
    _wait(root, dialog, "Sending the report")
    dialog._close()
    assert dialog.alive() and dialog.top.state() == "withdrawn"
    release.set()
    _wait(root, dialog, "Report sent: 7F3K2Q")
    assert len(calls["upload"]) == 1
    dialog._close()
    assert not dialog.alive()


def test_the_dialog_says_where_the_report_goes_and_links_the_policy(root, tmp_path, monkeypatch):
    from firestone_bot.gui import report_dialog
    from firestone_bot.gui.help_text import PRIVACY_URL

    assert "Discord" in report_dialog.WHAT
    opened = []
    monkeypatch.setattr("webbrowser.open", opened.append)
    dialog = ReportDialog(root, str(tmp_path), _settings(tmp_path))
    root.update()
    dialog.privacy_btn.invoke()
    assert opened == [PRIVACY_URL]
    dialog._close()
