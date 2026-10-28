"""tools/win_version: the version resource firestone-bot.spec embeds in FirestoneBot.exe."""

from __future__ import annotations

import os
import shutil
import sys

import pytest

import firestone_bot
from firestone_bot.tools import win_version
from firestone_bot.update import parse_version


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("0.3.34", (0, 3, 34, 0)),
        ("1.2", (1, 2, 0, 0)),
        ("7", (7, 0, 0, 0)),
        ("1.2.3.4", (1, 2, 3, 4)),
        ("v0.3.34", (0, 3, 34, 0)),
        ("0.4.0rc1", (0, 4, 0, 0)),
        ("0.4.0.post2", (0, 4, 0, 0)),
        ("0.4.0+local", (0, 4, 0, 0)),
        ("65535.0", (65535, 0, 0, 0)),
    ],
)
def test_version_tuple_fills_the_four_fields(text, expected):
    assert win_version.version_tuple(text) == expected


@pytest.mark.parametrize("text", ["", "abc", "1.2.3.4.5", "65536.0", "0.70000"])
def test_version_tuple_refuses_what_a_windows_version_cannot_hold(text):
    with pytest.raises(ValueError):
        win_version.version_tuple(text)


def test_the_package_version_fits_and_matches_the_updater_reading():
    version = firestone_bot.__version__
    numbers = parse_version(version)  # how the self-update compares releases
    assert win_version.version_tuple(version) == numbers + (0,) * (4 - len(numbers))
    assert win_version.string_table(version)["ProductVersion"] == version


def test_string_table_names_the_product_and_its_version():
    assert win_version.string_table("0.3.34") == {
        "CompanyName": "Lutakh",
        "FileDescription": "Firestone Bot",
        "FileVersion": "0.3.34",
        "InternalName": "FirestoneBot",
        "LegalCopyright": "Copyright (c) 2025-2026 Lutakh, Deaeth85, GeSpot1. MIT License",
        "OriginalFilename": "FirestoneBot.exe",
        "ProductName": "Firestone Bot",
        "ProductVersion": "0.3.34",
    }
    with pytest.raises(ValueError):
        win_version.string_table("not a version")


def test_the_copyright_line_names_the_holders_of_the_license_file():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "LICENSE"), encoding="utf-8") as f:
        text = f.read()
    assert text.startswith("MIT License\n") and "MIT License" in win_version.COPYRIGHT
    holders = [line.split()[2:] for line in text.splitlines() if line.startswith("Copyright (c)")]
    names = [words[1] if words[0][0].isdigit() else words[0] for words in holders]
    assert names == ["Lutakh", "Deaeth85", "GeSpot1"]
    assert all(name in win_version.COPYRIGHT for name in names)


def _query(path: str, key: str) -> str | None:
    """One version-resource value read through the Win32 API that Explorer and PowerShell use:
    a string under \\StringFileInfo, or the numeric file version for the root key "\\"."""
    import ctypes
    from ctypes import wintypes

    api = ctypes.WinDLL("version")
    vp = ctypes.c_void_p
    api.GetFileVersionInfoSizeW.argtypes = [wintypes.LPCWSTR, vp]
    api.GetFileVersionInfoW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, vp]
    api.VerQueryValueW.argtypes = [vp, wintypes.LPCWSTR, ctypes.POINTER(vp)]
    api.VerQueryValueW.argtypes += [ctypes.POINTER(wintypes.UINT)]
    size = api.GetFileVersionInfoSizeW(path, None)
    if not size:
        return None
    data = ctypes.create_string_buffer(size)
    assert api.GetFileVersionInfoW(path, 0, size, data)
    value, length = vp(), wintypes.UINT()
    if not api.VerQueryValueW(data, key, ctypes.byref(value), ctypes.byref(length)):
        return None
    if key == "\\":  # VS_FIXEDFILEINFO: dwFileVersionMS / LS are its 3rd and 4th DWORDs
        ms, ls = ctypes.cast(value, ctypes.POINTER(wintypes.DWORD * 4)).contents[2:4]
        return f"{ms >> 16}.{ms & 0xFFFF}.{ls >> 16}.{ls & 0xFFFF}"
    return ctypes.wstring_at(value.value, length.value).rstrip("\0")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows version resources")
def test_the_resource_written_into_an_exe_reads_back_through_windows(tmp_path):
    """The write PyInstaller's EXE step makes, on a copy of its windowed bootloader."""
    vi = pytest.importorskip("PyInstaller.utils.win32.versioninfo")
    import PyInstaller

    stub = os.path.join(os.path.dirname(PyInstaller.__file__), "bootloader")
    stub = os.path.join(stub, PyInstaller.PLATFORM, "runw.exe")
    if not os.path.exists(stub):
        pytest.skip(f"no PyInstaller bootloader at {stub}")
    exe = str(tmp_path / "FirestoneBot.exe")
    shutil.copyfile(stub, exe)
    assert _query(exe, "\\StringFileInfo\\040904B0\\ProductName") is None  # the stock stub
    vi.write_version_info_to_executable(exe, win_version.version_info("0.3.34"))
    for key, value in win_version.string_table("0.3.34").items():
        assert _query(exe, f"\\StringFileInfo\\040904B0\\{key}") == value
    assert _query(exe, "\\") == "0.3.34.0"
