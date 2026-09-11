"""An unattended Windows start re-creates itself outside the launcher's job (platform/detach)."""

from firestone_bot.platform import detach


def test_only_an_unattended_windows_exe_detaches():
    assert detach.should_detach(["--start"], True, "win32")
    assert not detach.should_detach([], True, "win32")  # double-click: left alone
    assert not detach.should_detach(["--start"], False, "win32")  # from source
    assert not detach.should_detach(["--start"], True, "darwin")
    assert not detach.should_detach(["--start", detach.DETACHED_FLAG], True, "win32")  # once


def test_command_line_quotes_paths_with_spaces():
    cmd = detach.command_line(r"C:\Program Files\Bot\FirestoneBot.exe", ["--start", "--detached"])
    assert cmd == '"C:\\Program Files\\Bot\\FirestoneBot.exe" --start --detached'


def test_powershell_literal_doubles_single_quotes():
    assert detach._ps_quote(r"C:\Users\O'Neil\Bot") == r"'C:\Users\O''Neil\Bot'"
