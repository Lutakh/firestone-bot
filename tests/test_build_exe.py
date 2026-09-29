"""tools/build_exe: what each OS gets replaced (PyInstaller itself is not run)."""

from __future__ import annotations

import os
import subprocess

import pytest

from firestone_bot.tools import build_exe, mac_codesign


def _write(path, text="x") -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


def _read(path) -> str:
    with open(path) as f:
        return f.read()


@pytest.fixture
def tree(tmp_path, monkeypatch):
    stage = tmp_path / "build" / "stage"
    dist = tmp_path / "dist" / "FirestoneBot"
    monkeypatch.setattr(build_exe, "STAGE", str(stage))
    monkeypatch.setattr(build_exe, "DIST", str(dist))
    monkeypatch.setattr(build_exe, "bot_running", lambda: False)
    return stage, dist


def _pyinstaller(monkeypatch, stage, mac: bool) -> None:
    """What PyInstaller leaves in build/stage: FirestoneBot/ always, FirestoneBot.app on macOS."""

    def run(cmd, **kw):
        _write(stage / "FirestoneBot" / "_internal" / "base_library.zip", "new")
        if mac:
            _write(stage / "FirestoneBot" / "FirestoneBot", "new")
            _write(stage / "FirestoneBot.app" / "Contents" / "MacOS" / "FirestoneBot", "new")
        else:
            _write(stage / "FirestoneBot" / "FirestoneBot.exe", "new")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(build_exe.subprocess, "run", run)


def test_windows_keeps_the_user_files(tree, monkeypatch):
    stage, dist = tree
    monkeypatch.setattr(build_exe.sys, "platform", "win32")
    _write(dist / "settings.ini", "mine")
    _write(dist / "FirestoneBot.exe", "old")
    _pyinstaller(monkeypatch, stage, mac=False)
    assert build_exe.main() == 0
    assert _read(dist / "settings.ini") == "mine"
    assert _read(dist / "FirestoneBot.exe") == "new"
    assert _read(dist / "_internal" / "base_library.zip") == "new"


def test_macos_replaces_the_bundle_and_signs_it(tree, monkeypatch, tmp_path):
    stage, dist = tree
    monkeypatch.setattr(build_exe.sys, "platform", "darwin")
    app = dist.parent / "FirestoneBot.app"
    _write(app / "Contents" / "MacOS" / "stale", "old")
    keychain = tmp_path / "firestone-bot.keychain-db"
    keychain.write_text("")
    monkeypatch.setattr(mac_codesign, "KEYCHAIN", str(keychain))
    signed: list[str] = []
    monkeypatch.setattr(mac_codesign, "sign", signed.append)
    _pyinstaller(monkeypatch, stage, mac=True)
    assert build_exe.main() == 0
    assert _read(app / "Contents" / "MacOS" / "FirestoneBot") == "new"
    assert not (app / "Contents" / "MacOS" / "stale").exists()  # replaced, never merged
    assert not os.path.exists(str(app) + ".old")
    assert signed == [str(app)]
    assert not (dist / "FirestoneBot.exe").exists()


def test_macos_without_the_keychain_stays_ad_hoc(tree, monkeypatch, tmp_path):
    stage, dist = tree
    monkeypatch.setattr(build_exe.sys, "platform", "darwin")
    monkeypatch.setattr(mac_codesign, "KEYCHAIN", str(tmp_path / "missing.keychain-db"))

    def sign(app):  # would create an empty keychain on a real Mac
        raise AssertionError("signed without the project's keychain")

    monkeypatch.setattr(mac_codesign, "sign", sign)
    _pyinstaller(monkeypatch, stage, mac=True)
    assert build_exe.main() == 0
    assert (dist.parent / "FirestoneBot.app" / "Contents" / "MacOS" / "FirestoneBot").exists()


def test_macos_untrusted_certificate_fails_the_build(tree, monkeypatch, tmp_path):
    stage, _ = tree
    monkeypatch.setattr(build_exe.sys, "platform", "darwin")
    keychain = tmp_path / "firestone-bot.keychain-db"
    keychain.write_text("")
    monkeypatch.setattr(mac_codesign, "KEYCHAIN", str(keychain))

    def sign(app):
        raise subprocess.CalledProcessError(1, ["codesign"])

    monkeypatch.setattr(mac_codesign, "sign", sign)
    _pyinstaller(monkeypatch, stage, mac=True)
    assert build_exe.main() == 1


def test_the_running_bot_blocks_the_build(tree, monkeypatch):
    monkeypatch.setattr(build_exe, "bot_running", lambda: True)

    def run(cmd, **kw):
        raise AssertionError("PyInstaller started while the bot runs")

    monkeypatch.setattr(build_exe.subprocess, "run", run)
    assert build_exe.main() == 1


def test_target_exe_per_os(tree, monkeypatch):
    _, dist = tree
    monkeypatch.setattr(build_exe.sys, "platform", "darwin")
    assert build_exe.target_exe() == os.path.join(
        str(dist.parent), "FirestoneBot.app", "Contents", "MacOS", "FirestoneBot"
    )
    monkeypatch.setattr(build_exe.sys, "platform", "win32")
    assert build_exe.target_exe() == os.path.join(str(dist), "FirestoneBot.exe")
