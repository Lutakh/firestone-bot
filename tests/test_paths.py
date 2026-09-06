"""Per-OS data folder and macOS protected-folder detection."""

import os

from firestone_bot import paths


def test_data_dir_from_source_is_cwd():
    assert paths.data_dir() == os.getcwd()
    assert paths.bundle_path() is None


def test_protected_mac_folders(monkeypatch, tmp_path):
    monkeypatch.setattr(paths.sys, "platform", "darwin")
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(tmp_path)))
    assert paths.is_protected_mac_folder(str(tmp_path / "Downloads"))
    assert paths.is_protected_mac_folder(str(tmp_path / "Documents" / "bots" / "x"))
    assert not paths.is_protected_mac_folder(str(tmp_path / "Games"))
    assert not paths.is_protected_mac_folder(str(tmp_path / "DownloadsX"))
    monkeypatch.setattr(paths.sys, "platform", "linux")
    assert not paths.is_protected_mac_folder(str(tmp_path / "Downloads"))


def test_in_applications(monkeypatch, tmp_path):
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(tmp_path)))
    assert paths.in_applications("/Applications/FirestoneBot.app")
    assert paths.in_applications(str(tmp_path / "Applications" / "FirestoneBot.app"))
    assert not paths.in_applications(str(tmp_path / "Downloads" / "FirestoneBot.app"))
