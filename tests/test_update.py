"""Self-update: version comparison, release parsing, checksums, payload lookup, updater script."""

import os

import pytest

from firestone_bot import update


def test_version_parsing_and_comparison():
    assert update.parse_version("v1.2.3") == (1, 2, 3)
    assert update.parse_version("0.1") == (0, 1)
    assert update.parse_version("nightly") == ()
    assert update.is_newer("v0.2.0", "0.1.0")
    assert update.is_newer("0.1.1", "0.1")
    assert not update.is_newer("0.1.0", "0.1.0")
    assert not update.is_newer("v0.0.9", "0.1.0")
    assert not update.is_newer("beta", "0.1.0")


def test_release_from_api_picks_assets_and_notes():
    r = update.release_from_api(
        {
            "tag_name": "v0.3.0",
            "body": "notes",
            "html_url": "https://x/releases/v0.3.0",
            "assets": [
                {"name": "FirestoneBot-windows.zip", "browser_download_url": "u1"},
                {"name": "SHA256SUMS.txt", "browser_download_url": "u2"},
                {"name": "broken"},
            ],
        }
    )
    assert r.version == "0.3.0" and r.tag == "v0.3.0" and r.notes == "notes"
    assert r.assets == {"FirestoneBot-windows.zip": "u1", "SHA256SUMS.txt": "u2"}
    assert r.checksums_url == "u2"


def test_asset_name_per_platform():
    assert update.asset_name("win32").endswith("windows.zip")
    assert update.asset_name("darwin").endswith("macos.zip")
    assert update.asset_name("linux").endswith("linux.tar.gz")
    assert update.asset_name("freebsd") == update.asset_name("linux")


def test_parse_checksums():
    text = (
        "ab" * 32 + "  FirestoneBot-windows.zip\n" + "cd" * 32 + " *FirestoneBot-macos.zip\nnoise\n"
    )
    assert update.parse_checksums(text) == {
        "FirestoneBot-windows.zip": "ab" * 32,
        "FirestoneBot-macos.zip": "cd" * 32,
    }


def test_find_payload_layouts(tmp_path):
    win = tmp_path / "win"
    (win / "_internal").mkdir(parents=True)
    (win / "FirestoneBot.exe").write_text("")
    assert update.find_payload(str(win)) == str(win)
    lin = tmp_path / "lin" / "FirestoneBot"
    (lin / "_internal").mkdir(parents=True)
    (lin / "FirestoneBot").write_text("")
    assert update.find_payload(str(tmp_path / "lin")) == str(lin)
    mac = tmp_path / "mac"
    (mac / "FirestoneBot.app").mkdir(parents=True)
    assert update.find_payload(str(mac)) == str(mac / "FirestoneBot.app")
    with pytest.raises(update.UpdateError):
        update.find_payload(str(tmp_path))


def test_safe_members_rejects_escapes():
    with pytest.raises(update.UpdateError):
        update._safe_members(["ok/x", "../evil"])
    with pytest.raises(update.UpdateError):
        update._safe_members(["/abs"])


def test_swap_script_posix_moves_only_program_files_and_keeps_previous():
    text, runner = update.swap_script(
        4242,
        "/inst",
        "/FirestoneBot.update",
        ["FirestoneBot", "_internal"],
        ["/inst/FirestoneBot"],
        platform="linux",
    )
    assert runner == ["/bin/sh"] and "kill -0 4242" in text
    # settings.ini lives in /inst: only the program entries move
    assert "mv '/inst/FirestoneBot' '/inst/FirestoneBot.swap/FirestoneBot' || undo" in text
    assert "mv '/inst/_internal' '/inst/FirestoneBot.swap/_internal' || undo" in text
    assert "mv '/FirestoneBot.update/FirestoneBot' '/inst/FirestoneBot' || undo" in text
    assert "mv '/inst'" not in text
    # the replaced version is kept for a rollback, and put back on failure
    assert "mv '/inst/FirestoneBot.swap' '/inst/FirestoneBot.previous'" in text
    assert "mv '/inst/FirestoneBot.swap/_internal' '/inst/_internal'" in text


def test_swap_script_macos_swaps_the_bundle_and_reopens_it():
    text, _ = update.swap_script(
        7, "/Apps/FirestoneBot.app", "/Apps/FirestoneBot.update", ["FirestoneBot.app"], [], "darwin"
    )
    assert "mv '/Apps/FirestoneBot.app' '/Apps/FirestoneBot.swap/FirestoneBot.app' || undo" in text
    assert "mv '/Apps/FirestoneBot.update/FirestoneBot.app' '/Apps/FirestoneBot.app'" in text
    assert "open -n '/Apps/FirestoneBot.app' &" in text
    assert "mv '/Apps/FirestoneBot.swap' '/Apps/FirestoneBot.previous'" in text


def test_swap_script_windows_has_undo_label():
    text, runner = update.swap_script(
        99,
        r"C:\Bot",
        r"C:\FirestoneBot.update",
        ["FirestoneBot.exe", "_internal"],
        [r"C:\Bot\FirestoneBot.exe"],
        "win32",
    )
    assert runner == ["cmd", "/c"] and "tasklist" in text
    assert (
        r'move "C:\Bot\FirestoneBot.exe" "C:\Bot\FirestoneBot.swap\FirestoneBot.exe" || goto undo'
        in text
    )
    assert r'move "C:\FirestoneBot.update\_internal" "C:\Bot\_internal" || goto undo' in text
    assert r'move "C:\Bot\FirestoneBot.swap" "C:\Bot\FirestoneBot.previous"' in text
    assert text.index(":undo") > text.index('start ""')


def test_program_entries_per_platform():
    assert update.program_entries("/x/FirestoneBot.app", "darwin") == ["FirestoneBot.app"]
    assert update.program_entries(r"C:\Bot", "win32") == ["FirestoneBot.exe", "_internal"]
    assert update.program_entries("/inst", "linux") == ["FirestoneBot", "_internal"]


def test_previous_version_reads_marker(tmp_path, monkeypatch):
    monkeypatch.setattr(update.sys, "platform", "linux")
    inst = tmp_path / "inst"
    inst.mkdir()
    assert update.previous_version(str(inst)) is None
    prev = inst / "FirestoneBot.previous"
    (prev / "_internal").mkdir(parents=True)
    (prev / "FirestoneBot").write_text("")
    assert update.previous_version(str(inst)) == "unknown"
    (inst / "FirestoneBot.previous.json").write_text('{"version": "0.1.9"}')
    assert update.previous_version(str(inst)) == "0.1.9"
    with pytest.raises(update.UpdateError):
        update.rollback(str(tmp_path / "nothing"))


def test_install_target_is_none_from_source():
    assert update.install_target() is None
    assert update.staging_dir("/x/FirestoneBot") == os.path.join("/x", "FirestoneBot.update")
