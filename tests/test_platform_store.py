"""Which store the game came from, when its path says nothing (Epic on another drive)."""

import json

from firestone_bot.platform import process


def test_folder_markers_tell_the_store(tmp_path):
    epic = tmp_path / "D" / "Games" / "FirestoneOnlineIdleRPG"
    (epic / ".egstore").mkdir(parents=True)
    (epic / "Firestone.exe").write_bytes(b"")
    steam = tmp_path / "E" / "Library" / "Firestone"
    steam.mkdir(parents=True)
    (steam / "steam_api64.dll").write_bytes(b"")
    plain = tmp_path / "F" / "Firestone"
    plain.mkdir(parents=True)
    assert process.detect_platform(str(epic / "Firestone.exe")) == "epic"
    assert process.detect_platform(str(steam / "Firestone.exe")) == "steam"
    assert process.detect_platform(str(plain / "Firestone.exe")) == "unknown"
    assert process.detect_platform("") == "unknown"


def test_path_markers_still_win(tmp_path):
    assert process.detect_platform(r"C:\Program Files\Epic Games\X\Firestone.exe") == "epic"
    assert (
        process.detect_platform(r"D:\SteamLibrary\steamapps\common\Firestone\Firestone.exe")
        == "steam"
    )


def test_epic_install_found_through_the_launcher_manifests(tmp_path):
    install = tmp_path / "G" / "FirestoneOnlineIdleRPG"
    install.mkdir(parents=True)
    (install / "FirestoneEos.exe").write_bytes(b"")
    manifests = tmp_path / "Manifests"
    manifests.mkdir()
    (manifests / "other.item").write_text(
        json.dumps({"CatalogItemId": "abc", "InstallLocation": "x"})
    )
    (manifests / "fs.item").write_text(
        json.dumps(
            {
                "CatalogItemId": process.EPIC_CATALOG_ITEM.upper(),
                "InstallLocation": str(install),
                "LaunchExecutable": "FirestoneEos.exe",
            }
        )
    )
    assert process.epic_install_from_manifests(str(manifests)) == str(install)
    assert process.epic_install_from_manifests(str(tmp_path / "missing")) is None
