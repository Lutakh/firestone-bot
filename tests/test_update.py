"""Self-update: version comparison, release parsing, checksums, payload lookup, updater script."""

import os
import sys

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


def test_updater_script_waits_swaps_and_relaunches():
    text, runner = update.updater_script(
        4242, "/inst/FirestoneBot", "/inst/FirestoneBot.update", ["/inst/FirestoneBot/FirestoneBot"]
    )
    assert "4242" in text
    assert "FirestoneBot.old" in text
    if sys.platform == "win32":
        assert runner == ["cmd", "/c"] and "tasklist" in text
    else:
        assert runner == ["/bin/sh"] and "kill -0 4242" in text
        # the old install is put back when the move of the new one fails
        assert "mv '/inst/FirestoneBot.old' '/inst/FirestoneBot'; exit 1" in text


def test_install_target_is_none_from_source():
    assert update.install_target() is None
    assert update.staging_dir("/x/FirestoneBot") == os.path.join("/x", "FirestoneBot.update")
