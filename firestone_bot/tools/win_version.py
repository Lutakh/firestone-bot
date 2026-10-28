"""Windows version resource of FirestoneBot.exe, built from __version__ by firestone-bot.spec.

The resource is what Explorer shows in the exe's Properties > Details and what Task Manager
names the process after. PyInstaller's bootloader carries none, and an exe without publisher
or product information is one of the traits antivirus machine-learning models weigh:
Microsoft Defender quarantined the Windows release as Trojan:Win32/Bearfoos.B!ml (players'
reports, 2026-10).

version_tuple() and string_table() are plain Python (unit-tested on every OS);
version_info() builds PyInstaller's VSVersionInfo and runs on Windows only (PyInstaller's
versioninfo module imports pefile, which PyInstaller installs on Windows only).
"""

from __future__ import annotations

import re

PRODUCT_NAME = "Firestone Bot"
PUBLISHER = "Lutakh"  # the GitHub account that publishes the releases
# the holders named by LICENSE (MIT since 2026-10-28, with the AutoHotkey bot's authors' leave)
COPYRIGHT = "Copyright (c) 2025-2026 Lutakh, Deaeth85, GeSpot1. MIT License"
EXE_NAME = "FirestoneBot.exe"
# String table key = language 0x0409 (U.S. English) + code page 1200 (Unicode); the
# VarFileInfo "Translation" entry names the same pair.
LANGUAGE = 0x0409
CODEPAGE = 1200


def version_tuple(version: str) -> tuple[int, ...]:
    """'0.3.34' -> (0, 3, 34, 0): the leading numbers padded to the four 16-bit fields of
    VS_FIXEDFILEINFO; a suffix ('0.4.0rc1', '0.4.0.post2', '+local') is ignored. ValueError
    when there is no number, more than four or one above 65535: a wrong version in a release
    exe is worse than a failed build."""
    m = re.match(r"v?(\d+(?:\.\d+)*)", (version or "").strip())
    if not m:
        raise ValueError(f"no numeric version in {version!r}")
    parts = [int(p) for p in m.group(1).split(".")]
    if len(parts) > 4 or max(parts) > 0xFFFF:
        raise ValueError(f"{version!r} does not fit a Windows file version (4 numbers, 0-65535)")
    return tuple(parts + [0] * (4 - len(parts)))


def string_table(version: str) -> dict[str, str]:
    """The StringFileInfo entries (Properties > Details) of the exe released as `version`."""
    version_tuple(version)  # same validation as the numeric fields
    return {
        "CompanyName": PUBLISHER,
        "FileDescription": PRODUCT_NAME,
        "FileVersion": version,
        "InternalName": "FirestoneBot",
        "LegalCopyright": COPYRIGHT,
        "OriginalFilename": EXE_NAME,
        "ProductName": PRODUCT_NAME,
        "ProductVersion": version,
    }


def version_info(version: str):
    """PyInstaller VSVersionInfo for EXE(version=...) in firestone-bot.spec (Windows only)."""
    from PyInstaller.utils.win32 import versioninfo as vi

    numbers = version_tuple(version)
    strings = [vi.StringStruct(key, value) for key, value in string_table(version).items()]
    return vi.VSVersionInfo(
        ffi=vi.FixedFileInfo(
            filevers=numbers,
            prodvers=numbers,
            mask=0x3F,
            flags=0x0,  # a release: no VS_FF_DEBUG / PRERELEASE / PATCHED flag
            OS=0x40004,  # VOS_NT_WINDOWS32
            fileType=0x1,  # VFT_APP
            subtype=0x0,
            date=(0, 0),
        ),
        kids=[
            vi.StringFileInfo([vi.StringTable(f"{LANGUAGE:04X}{CODEPAGE:04X}", strings)]),
            vi.VarFileInfo([vi.VarStruct("Translation", [LANGUAGE, CODEPAGE])]),
        ],
    )
